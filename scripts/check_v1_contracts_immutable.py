import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "services" / "api" / "migrations"
REGISTRY_PATH = ROOT / "contracts" / "immutable_field_registry_v1.json"
VERSION_PATH = ROOT / "contracts" / "v1_contract_version.txt"
CHANGELOG_PATH = ROOT / "contracts" / "v1_contract_changelog.md"
CONTRACT_DOC_PATH = ROOT / "contracts" / "v1_contracts.md"


V1_RELATIONS = [
    # Pantry truth (mutable state) and core audit/observation streams (append-only).
    {"schema": "public", "name": "inventory_items", "entity_mutability": "mutable"},
    {"schema": "public", "name": "event_log", "entity_mutability": "append-only"},
    {"schema": "observations", "name": "scan_observations", "entity_mutability": "append-only"},
    # Media retention tracking + learning signals.
    {"schema": "public", "name": "media_assets", "entity_mutability": "append-only"},
    {"schema": "public", "name": "confirmation_deltas", "entity_mutability": "append-only"},
    {"schema": "public", "name": "scan_training_labels", "entity_mutability": "append-only"},
]


TYPE_STOPWORDS = {
    "DEFAULT",
    "NOT",
    "NULL",
    "CHECK",
    "REFERENCES",
    "PRIMARY",
    "UNIQUE",
    "CONSTRAINT",
    "GENERATED",
    "COLLATE",
}


@dataclass(frozen=True)
class Relation:
    schema: str
    name: str


def _run_git(args: List[str]) -> Tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return p.returncode, p.stdout.strip()
    except FileNotFoundError:
        return 1, "git not found"


def _in_git_repo() -> bool:
    code, out = _run_git(["rev-parse", "--is-inside-work-tree"])
    return code == 0 and out.strip() == "true"


def _read_version() -> str:
    if not VERSION_PATH.exists():
        raise SystemExit(f"Missing {VERSION_PATH}")
    return VERSION_PATH.read_text(encoding="utf-8").strip()


def _split_top_level_commas(s: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    start = 0
    in_single_quote = False
    in_double_quote = False

    for i, ch in enumerate(s):
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif in_single_quote or in_double_quote:
            continue
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(s[start:i].strip())
            start = i + 1

    tail = s[start:].strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def _extract_type_tokens(rest: str) -> str:
    tokens = rest.strip().rstrip(",").split()
    type_tokens: List[str] = []
    for token in tokens:
        upper = token.upper()
        if upper in TYPE_STOPWORDS:
            break
        type_tokens.append(token)
    return " ".join(type_tokens).strip()


def _parse_create_table_columns(body: str) -> Dict[str, str]:
    columns: Dict[str, str] = {}
    for item in _split_top_level_commas(body):
        if not item:
            continue
        head = item.lstrip()
        upper_head = head.upper()
        if upper_head.startswith("CONSTRAINT"):
            continue
        if upper_head.startswith("PRIMARY KEY"):
            continue
        if upper_head.startswith("FOREIGN KEY"):
            continue
        if upper_head.startswith("UNIQUE"):
            continue
        if upper_head.startswith("CHECK"):
            continue

        m = re.match(r'^"?(?P<col>[A-Za-z_][A-Za-z0-9_]*)"?\s+(?P<rest>.+)$', head, flags=re.S)
        if not m:
            continue
        col = m.group("col")
        type_str = _extract_type_tokens(m.group("rest"))
        if col and type_str:
            columns[col] = type_str
    return columns


def _iter_migration_files() -> List[Path]:
    if not MIGRATIONS_DIR.exists():
        raise SystemExit(f"Missing migrations dir: {MIGRATIONS_DIR}")

    files = [p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file()]

    def key(p: Path) -> Tuple[int, str]:
        m = re.match(r"^(?P<num>\d{3})", p.name)
        n = int(m.group("num")) if m else 999
        return (n, p.name)

    return sorted(files, key=key)


def _build_schema_from_migrations() -> Dict[Relation, Dict[str, str]]:
    wanted = {Relation(x["schema"], x["name"]) for x in V1_RELATIONS}
    schema: Dict[Relation, Dict[str, str]] = {}

    create_table_re = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<schema>[A-Za-z_][A-Za-z0-9_]*)\.(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<body>.*?)\)\s*;",
        flags=re.I | re.S,
    )

    alter_add_col_re = re.compile(
        r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?P<schema>[A-Za-z_][A-Za-z0-9_]*)\.(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+(?P<col>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<rest>[^;\n]+)",
        flags=re.I,
    )

    for path in _iter_migration_files():
        sql = path.read_text(encoding="utf-8", errors="replace")

        for m in create_table_re.finditer(sql):
            rel = Relation(m.group("schema"), m.group("table"))
            if rel not in wanted:
                continue
            cols = _parse_create_table_columns(m.group("body"))
            schema.setdefault(rel, {}).update(cols)

        for m in alter_add_col_re.finditer(sql):
            rel = Relation(m.group("schema"), m.group("table"))
            if rel not in wanted:
                continue
            col = m.group("col")
            type_str = _extract_type_tokens(m.group("rest"))
            if col and type_str:
                schema.setdefault(rel, {})[col] = type_str

    return schema


def generate_registry() -> dict:
    version = _read_version()
    inferred = _build_schema_from_migrations()

    entities = []
    for rel_def in V1_RELATIONS:
        rel = Relation(rel_def["schema"], rel_def["name"])
        fields = []
        cols = inferred.get(rel, {})

        field_mutability = "mutable" if rel_def["entity_mutability"] == "mutable" else "immutable"

        for col_name in sorted(cols.keys()):
            fields.append(
                {
                    "name": col_name,
                    "type": cols[col_name],
                    "mutability": field_mutability,
                }
            )

        entities.append(
            {
                "entity": f"{rel.schema}.{rel.name}",
                "entity_mutability": rel_def["entity_mutability"],
                "fields": fields,
            }
        )

    return {
        "contract_version": version,
        "notes": "Generated from SQL migrations. Treat as canonical V1 field registry.",
        "entities": entities,
    }


def _stable_json(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def write_registry() -> None:
    registry = generate_registry()
    REGISTRY_PATH.write_text(_stable_json(registry), encoding="utf-8")


def _get_changed_files_vs_base() -> List[str]:
    if not _in_git_repo():
        return []

    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref:
        # Pull request workflow.
        code, out = _run_git(["diff", "--name-only", f"origin/{base_ref}...HEAD"])
        if code == 0 and out:
            return [x.strip() for x in out.splitlines() if x.strip()]

    # Fallback: compare against previous commit.
    code, out = _run_git(["diff", "--name-only", "HEAD~1...HEAD"])
    if code == 0 and out:
        return [x.strip() for x in out.splitlines() if x.strip()]

    return []


def check_registry_matches() -> None:
    generated = generate_registry()

    if not REGISTRY_PATH.exists():
        raise SystemExit(
            f"Missing {REGISTRY_PATH}. Run: python scripts/check_v1_contracts_immutable.py --write"
        )

    committed = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if _stable_json(committed) != _stable_json(generated):
        raise SystemExit(
            "V1 registry mismatch. A migration likely changed a V1 contract entity. "
            "Regenerate and commit registry changes with a version bump + changelog entry:\n"
            "  python scripts/check_v1_contracts_immutable.py --write\n"
        )


def check_approval_workflow() -> None:
    changed = set(_get_changed_files_vs_base())
    if not changed:
        return

    registry_changed = str(REGISTRY_PATH.relative_to(ROOT)).replace("\\", "/") in changed
    if not registry_changed:
        return

    version_changed = str(VERSION_PATH.relative_to(ROOT)).replace("\\", "/") in changed
    changelog_changed = str(CHANGELOG_PATH.relative_to(ROOT)).replace("\\", "/") in changed

    if not version_changed or not changelog_changed:
        raise SystemExit(
            "V1 registry was modified but approval workflow is incomplete. "
            "You must update BOTH contracts/v1_contract_version.txt and contracts/v1_contract_changelog.md"
        )


def check_required_files_exist() -> None:
    missing = [p for p in [VERSION_PATH, CHANGELOG_PATH, CONTRACT_DOC_PATH] if not p.exists()]
    if missing:
        raise SystemExit("Missing required V1 contract files: " + ", ".join(str(p) for p in missing))


def main() -> int:
    parser = argparse.ArgumentParser(description="Guardrail: freeze V1 contracts")
    parser.add_argument("--write", action="store_true", help="Write generated registry to contracts/")
    args = parser.parse_args()

    check_required_files_exist()

    if args.write:
        write_registry()
        print(f"Wrote {REGISTRY_PATH}")
        return 0

    check_registry_matches()
    check_approval_workflow()
    print("V1 contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
