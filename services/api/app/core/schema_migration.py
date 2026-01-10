from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from app.core.settings import settings


@dataclass(frozen=True)
class SchemaMigrationConfig:
    mode: str
    enable_v2_shadow_read: bool
    rollout_phase: str
    window_start: str
    window_end: str
    enable_progressive_v2_reads: bool
    v2_read_rollout_percent: int


def _parse_iso_utc(s: str) -> datetime | None:
    raw = (s or "").strip()
    if not raw:
        return None
    try:
        # Allow trailing Z.
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _in_window(start: datetime | None, end: datetime | None) -> bool:
    # If neither is set, treat as always enabled.
    if start is None and end is None:
        return True
    now = _now_utc()
    if start is not None and now < start:
        return False
    if end is not None and now >= end:
        return False
    return True


def get_schema_migration_config() -> SchemaMigrationConfig:
    mode = (getattr(settings, "schema_migration_mode", None) or "v1_only").strip().lower()
    if mode not in {"v1_only", "dual_write", "v2_only"}:
        mode = "v1_only"

    enable_v2_shadow_read = bool(getattr(settings, "enable_v2_shadow_read", False))

    rollout_phase = (getattr(settings, "rollout_phase", None) or "internal").strip() or "internal"
    window_start = (getattr(settings, "schema_migration_window_start", None) or "").strip()
    window_end = (getattr(settings, "schema_migration_window_end", None) or "").strip()
    enable_progressive_v2_reads = bool(getattr(settings, "enable_progressive_v2_reads", False))
    try:
        v2_read_rollout_percent = int(getattr(settings, "v2_read_rollout_percent", 0) or 0)
    except Exception:
        v2_read_rollout_percent = 0
    v2_read_rollout_percent = max(0, min(100, v2_read_rollout_percent))

    return SchemaMigrationConfig(
        mode=mode,
        enable_v2_shadow_read=enable_v2_shadow_read,
        rollout_phase=rollout_phase,
        window_start=window_start,
        window_end=window_end,
        enable_progressive_v2_reads=enable_progressive_v2_reads,
        v2_read_rollout_percent=v2_read_rollout_percent,
    )


def dual_write_enabled() -> bool:
    cfg = get_schema_migration_config()
    # Dual-write is a *transition* mode. v2_only means primary writes are V2 only.
    if cfg.mode != "dual_write":
        return False
    start = _parse_iso_utc(cfg.window_start)
    end = _parse_iso_utc(cfg.window_end)
    return _in_window(start, end)


def v2_write_enabled() -> bool:
    """Return True when V2 writes should be attempted.

    - dual_write: true only within the configured window
    - v2_only: always true
    - v1_only: false
    """
    cfg = get_schema_migration_config()
    if cfg.mode == "v2_only":
        return True
    if cfg.mode != "dual_write":
        return False
    start = _parse_iso_utc(cfg.window_start)
    end = _parse_iso_utc(cfg.window_end)
    return _in_window(start, end)


def v1_read_authoritative() -> bool:
    return get_schema_migration_config().mode in {"v1_only", "dual_write"}


def v2_read_authoritative() -> bool:
    return get_schema_migration_config().mode == "v2_only"


def v1_writes_allowed() -> bool:
    """Return True if the app should write to V1 truth tables.

    Note: DB-level guards may also exist. This function is for app-level policy.
    """
    try:
        if bool(getattr(settings, "disable_v1_writes", False)):
            return False
    except Exception:
        pass
    cfg = get_schema_migration_config()
    return cfg.mode in {"v1_only", "dual_write"}


def inventory_truth_write_table() -> str:
    """Authoritative truth write target for pantry inventory."""
    cfg = get_schema_migration_config()
    try:
        if bool(getattr(settings, "disable_v1_writes", False)):
            return "inventory_items_v2"
    except Exception:
        pass
    if cfg.mode == "v2_only":
        return "inventory_items_v2"
    return "inventory_items"


def inventory_truth_read_table_for_user(user_id: str) -> str:
    """Truth read table selector for a given user.

    - v1_only: always V1
    - v2_only: always V2
    - dual_write: progressive per-user V2 reads, if enabled and gated
    """
    return "inventory_items_v2" if should_read_v2_for_user(user_id) else "inventory_items"


def _parse_allowlist(value: str) -> set[str]:
    try:
        parts = [p.strip().lower() for p in (value or "").split(",")]
        return {p for p in parts if p}
    except Exception:
        return set()


def _phase_to_percent(phase: str) -> int:
    p = (phase or "").strip().lower()
    if p in {"100%", "100", "full", "all"}:
        return 100
    if p in {"10%", "10"}:
        return 10
    if p in {"1%", "1"}:
        return 1
    # internal/default
    return 0


def v2_shadow_read_enabled() -> bool:
    cfg = get_schema_migration_config()
    # Only meaningful while V1 is the read contract.
    if not (cfg.enable_v2_shadow_read and cfg.mode in {"v1_only", "dual_write"}):
        return False
    start = _parse_iso_utc(cfg.window_start)
    end = _parse_iso_utc(cfg.window_end)
    return _in_window(start, end)


def current_rollout_phase() -> str:
    return get_schema_migration_config().rollout_phase


def should_read_v2_for_user(user_id: str) -> bool:
    """Progressive flip-read path selector.

    Default OFF. When enabled, uses a stable hash of user_id to bucket users.
    """
    cfg = get_schema_migration_config()
    # Emergency rollback.
    try:
        if bool(getattr(settings, "force_read_v1", False)):
            return False
    except Exception:
        pass

    if cfg.mode == "v2_only":
        return True

    # Don't flip reads unless V2 is being kept current.
    if cfg.mode != "dual_write":
        return False

    # Explicit gates: rollout_phase determines target percent unless an explicit percent is provided.
    phase = (cfg.rollout_phase or "internal").strip()
    phase_percent = _phase_to_percent(phase)
    target_percent = cfg.v2_read_rollout_percent if cfg.v2_read_rollout_percent > 0 else phase_percent

    # Internal gate: only allowlisted users.
    if phase_percent == 0:
        allow = _parse_allowlist(getattr(settings, "internal_user_allowlist", "") or "")
        uid_norm = (user_id or "").strip().lower()
        return bool(uid_norm) and uid_norm in allow

    if not (cfg.enable_progressive_v2_reads and target_percent > 0):
        return False

    uid = (user_id or "").strip().lower()
    if not uid:
        return False
    h = hashlib.sha256(uid.encode("utf-8", errors="ignore")).hexdigest()
    bucket = int(h[:8], 16) % 100
    return bucket < max(0, min(100, int(target_percent)))
