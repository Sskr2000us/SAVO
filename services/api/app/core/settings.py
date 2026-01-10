from pydantic import BaseModel
import os
from pathlib import Path


def _find_repo_root(start: Path) -> Path | None:
    # Look upwards for the repo root marker: docs/spec/prompt-pack.gpt-5.2.json
    current = start
    for _ in range(10):
        candidate = current / "docs" / "spec" / "prompt-pack.gpt-5.2.json"
        if candidate.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def _default_prompt_pack_path() -> str:
    here = Path(__file__).resolve()
    repo_root = _find_repo_root(here.parent)
    if repo_root is None:
        # Fall back to a relative best-effort path; callers can override via env.
        return str((here.parent / ".." / ".." / ".." / ".." / "docs" / "spec" / "prompt-pack.gpt-5.2.json").resolve())
    return str((repo_root / "docs" / "spec" / "prompt-pack.gpt-5.2.json").resolve())


class Settings(BaseModel):
    # Legacy provider setting (kept for backward compatibility)
    llm_provider: str = os.getenv("SAVO_LLM_PROVIDER", "mock")
    llm_fallback_provider: str = os.getenv("SAVO_LLM_FALLBACK_PROVIDER", "")
    
    # Dual-provider system for optimal performance
    # Vision: Google Gemini excels at image understanding
    # Reasoning: OpenAI GPT excels at structured JSON and reasoning
    vision_provider: str = os.getenv("SAVO_VISION_PROVIDER", "google")
    reasoning_provider: str = os.getenv(
        "SAVO_REASONING_PROVIDER",
        os.getenv("SAVO_LLM_PROVIDER", "openai")  # Fallback to legacy for compatibility
    )
    
    # Custom vision model settings (Phase 2)
    use_custom_vision_model: bool = os.getenv(
        "SAVO_USE_CUSTOM_VISION",
        "false"
    ).lower() == "true"
    
    custom_vision_model_path: str = os.getenv(
        "SAVO_VISION_MODEL_PATH",
        "./models/savo_yolo_v8.pt"
    )
    
    vision_confidence_threshold: float = float(
        os.getenv("SAVO_VISION_CONFIDENCE", "0.5")
    )
    
    # Training data collection
    collect_training_data: bool = os.getenv(
        "SAVO_COLLECT_TRAINING_DATA",
        "true"
    ).lower() == "true"
    
    prompt_pack_path: str = os.getenv("SAVO_PROMPT_PACK_PATH", _default_prompt_pack_path())

    # Second-tier trust guardrail: ask an LLM judge to sanity-check authenticity/realism.
    # Default ON (trust-first): reject and regenerate semantically invalid / inauthentic plans.
    enable_authenticity_judge: bool = os.getenv(
        "SAVO_ENABLE_AUTHENTICITY_JUDGE",
        "true",
    ).lower() == "true"

    # If true, any judge-reported issues will force a regenerate (fail-closed).
    # If false, judge issues will be logged but not block the response.
    authenticity_judge_fail_closed: bool = os.getenv(
        "SAVO_AUTHENTICITY_JUDGE_FAIL_CLOSED",
        "true",
    ).lower() == "true"

    # ------------------------------------------------------------------
    # Side-by-side schema migration controls (V1 + V2)
    #
    # Modes:
    # - v1_only:   read/write V1 tables only (default)
    # - dual_write: write both V1 + V2, reads remain V1
    # - v2_only:   read/write V2 tables only (future cutover)
    # ------------------------------------------------------------------
    schema_migration_mode: str = os.getenv("SAVO_SCHEMA_MIGRATION_MODE", "v1_only")

    # When true (and mode is v1_only/dual_write), compute V2 shadow reads and
    # log divergence events to public.event_log. Never blocks responses.
    enable_v2_shadow_read: bool = os.getenv(
        "SAVO_ENABLE_V2_SHADOW_READ",
        "false",
    ).lower() == "true"

    # Optional time-bounded window for enabling dual-write / shadow-read.
    # ISO-8601 strings, e.g. 2026-01-10T00:00:00Z
    schema_migration_window_start: str = os.getenv("SAVO_SCHEMA_MIGRATION_WINDOW_START", "")
    schema_migration_window_end: str = os.getenv("SAVO_SCHEMA_MIGRATION_WINDOW_END", "")

    # Rollout phase tagging for audit/reports: internal|1%|10%|100% (free-form).
    rollout_phase: str = os.getenv("SAVO_ROLLOUT_PHASE", "internal")

    # Emergency rollback: force all reads to V1 immediately (no schema changes).
    force_read_v1: bool = os.getenv("SAVO_FORCE_READ_V1", "false").lower() == "true"

    # Internal rollout gate: only these user_ids are eligible for V2 reads when rollout_phase=internal.
    # Comma-separated UUIDs.
    internal_user_allowlist: str = os.getenv("SAVO_INTERNAL_USER_ALLOWLIST", "")

    # Optional hard guard: disallow any app-level V1 writes (useful post-cutover).
    # When true, write paths should either write V2-only or raise a controlled error.
    disable_v1_writes: bool = os.getenv("SAVO_DISABLE_V1_WRITES", "false").lower() == "true"

    # Flip-read path (progressive rollout). Default OFF (0%).
    enable_progressive_v2_reads: bool = os.getenv(
        "SAVO_ENABLE_PROGRESSIVE_V2_READS",
        "false",
    ).lower() == "true"
    v2_read_rollout_percent: int = int(os.getenv("SAVO_V2_READ_ROLLOUT_PERCENT", "0") or "0")

    # Admin-only report access token (optional; when set, enables system-wide report queries).
    admin_report_token: str = os.getenv("SAVO_ADMIN_REPORT_TOKEN", "")

    # ------------------------------------------------------------------
    # Quantity aggregation policy (for shadow validation + analytics)
    #
    # Base units in UnitConverter are grams (weight), ml (volume), pieces (count).
    # These settings control the *canonical presentation* in reports.
    # Examples:
    # - kg/L/each:
    #     SAVO_QTY_CANONICAL_WEIGHT_UNIT=kg
    #     SAVO_QTY_CANONICAL_VOLUME_UNIT=liters
    #     SAVO_QTY_CANONICAL_COUNT_UNIT=pieces
    # - Split count types in reports:
    #     SAVO_QTY_COUNT_BREAKDOWN=true
    # ------------------------------------------------------------------
    qty_canonical_weight_unit: str = os.getenv("SAVO_QTY_CANONICAL_WEIGHT_UNIT", "grams")
    qty_canonical_volume_unit: str = os.getenv("SAVO_QTY_CANONICAL_VOLUME_UNIT", "ml")
    qty_canonical_count_unit: str = os.getenv("SAVO_QTY_CANONICAL_COUNT_UNIT", "pieces")
    qty_count_breakdown: bool = os.getenv("SAVO_QTY_COUNT_BREAKDOWN", "false").lower() == "true"

    # ------------------------------------------------------------------
    # Vector intelligence layer (V2.5) - gated entry
    #
    # Default OFF. When enabled, vector sync is event-driven only.
    # ------------------------------------------------------------------
    vector_enabled: bool = os.getenv("SAVO_VECTOR_ENABLED", "false").lower() == "true"

    # Entry thresholds (global gates): keep non-vector paths until scale justifies.
    vector_min_active_pantry_items: int = int(os.getenv("SAVO_VECTOR_MIN_ACTIVE_PANTRY_ITEMS", "0") or "0")
    vector_min_recipes: int = int(os.getenv("SAVO_VECTOR_MIN_RECIPES", "0") or "0")

    # Conceptual over literal: when true, semantic search is preferred where available.
    vector_conceptual_search: bool = os.getenv("SAVO_VECTOR_CONCEPTUAL_SEARCH", "false").lower() == "true"

    # Provider wiring (pluggable by env; implementations are deliberately abstract).
    embedding_provider: str = os.getenv("SAVO_EMBEDDING_PROVIDER", "noop")
    embedding_version: str = os.getenv("SAVO_EMBEDDING_VERSION", "v0")
    vector_db_provider: str = os.getenv("SAVO_VECTOR_DB_PROVIDER", "noop")


settings = Settings()
