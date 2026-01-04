"""Generate an API endpoints reference from FastAPI route files.

Parses:
- services/api/app/api/router.py (include_router wiring)
- services/api/app/api/routes/*.py (APIRouter prefixes + decorators)

Writes:
- API_ENDPOINTS_GENERATED.md (repo root)

This is best-effort static parsing (no imports/execution).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTER_PY = REPO_ROOT / "services" / "api" / "app" / "api" / "router.py"
ROUTES_DIR = REPO_ROOT / "services" / "api" / "app" / "api" / "routes"
OUTPUT_MD = REPO_ROOT / "API_ENDPOINTS_GENERATED.md"

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


@dataclass(frozen=True)
class IncludedRouter:
    alias: str
    module: Optional[str]
    include_prefix: str


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    auth: str
    source: str


def _norm_prefix(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/")


def _norm_path(p: str) -> str:
    p = (p or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    return p


def _join_paths(*parts: str) -> str:
    out = ""
    for part in parts:
        part = (part or "").strip()
        if not part:
            continue
        if not out:
            out = part
        else:
            out = out.rstrip("/") + "/" + part.lstrip("/")
    if not out.startswith("/"):
        out = "/" + out
    return out


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_router_imports(router_source: str) -> dict[str, str]:
    """Return mapping: imported alias name -> module name (e.g. recipes_router -> recipes)."""

    alias_to_module: dict[str, str] = {}
    for line in router_source.splitlines():
        line = line.strip()
        if not line.startswith("from app.api.routes."):
            continue

        # Example:
        # from app.api.routes.recipes import router as recipes_router, public_router as recipes_public_router
        m = re.match(r"from\s+app\.api\.routes\.(\w+)\s+import\s+(.+)", line)
        if not m:
            continue
        module = m.group(1)
        imports_part = m.group(2)
        for chunk in imports_part.split(","):
            chunk = chunk.strip()
            # router as recipes_router
            m2 = re.match(r"(\w+)\s+as\s+(\w+)", chunk)
            if m2:
                alias = m2.group(2)
                alias_to_module[alias] = module
    return alias_to_module


def _parse_includes(router_source: str, alias_to_module: dict[str, str]) -> list[IncludedRouter]:
    includes: list[IncludedRouter] = []

    for line in router_source.splitlines():
        line = line.strip()
        if "include_router(" not in line:
            continue

        # Example: api_router.include_router(recipes_router, prefix="/recipes", tags=[...])
        m = re.search(r"include_router\((\w+)(?:,\s*prefix=\"([^\"]+)\")?", line)
        if not m:
            continue

        alias = m.group(1)
        include_prefix = _norm_prefix(m.group(2) or "")
        includes.append(
            IncludedRouter(
                alias=alias,
                module=alias_to_module.get(alias),
                include_prefix=include_prefix,
            )
        )

    return includes


def _const_str(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_depends_get_current_user(expr: ast.AST) -> bool:
    # Depends(get_current_user)
    if not isinstance(expr, ast.Call):
        return False
    if not isinstance(expr.func, ast.Name) or expr.func.id != "Depends":
        return False
    if not expr.args:
        return False
    arg0 = expr.args[0]
    return isinstance(arg0, ast.Name) and arg0.id == "get_current_user"


def _func_requires_auth(fn: ast.AST) -> bool:
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    args = fn.args

    # Scan positional-with-defaults
    for default in args.defaults:
        if _is_depends_get_current_user(default):
            return True

    # Scan kwonly defaults
    for default in args.kw_defaults:
        if default is not None and _is_depends_get_current_user(default):
            return True

    return False


def _parse_route_file(module: str, file_path: Path) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    """Return (router_prefix_by_var, routes[(router_var, method, decorator_path)])."""

    source = _read_text(file_path)
    tree = ast.parse(source, filename=str(file_path))

    router_prefix: dict[str, str] = {}
    routes: list[tuple[str, str, str]] = []

    # Pass 1: capture <name> = APIRouter(prefix="...")
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Name) or call.func.id != "APIRouter":
            continue

        prefix = ""
        for kw in call.keywords:
            if kw.arg == "prefix":
                prefix = _const_str(kw.value) or ""
                break
        router_prefix[target.id] = _norm_prefix(prefix)

    # Pass 2: endpoints via decorators
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        auth = "auth" if _func_requires_auth(node) else "public"

        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            if not isinstance(dec.func, ast.Attribute):
                continue
            attr = dec.func.attr
            if attr not in HTTP_METHODS:
                continue
            if not isinstance(dec.func.value, ast.Name):
                continue

            router_var = dec.func.value.id
            raw_path = ""
            if dec.args:
                raw_path = _const_str(dec.args[0]) or ""
            if not raw_path:
                continue

            routes.append((router_var, attr.upper(), _norm_path(raw_path)))

    return router_prefix, [(rv, m, p + ("|" + module) + ("|" + ("auth" if m else ""))) for rv, m, p in []]  # unused


def _parse_route_file_endpoints(module: str, file_path: Path) -> tuple[dict[str, str], list[tuple[str, str, str, str]]]:
    """Return (router_prefix_by_var, endpoints[(router_var, method, decorator_path, auth)])."""

    source = _read_text(file_path)
    tree = ast.parse(source, filename=str(file_path))

    router_prefix: dict[str, str] = {}
    endpoints: list[tuple[str, str, str, str]] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Name) or call.func.id != "APIRouter":
            continue

        prefix = ""
        for kw in call.keywords:
            if kw.arg == "prefix":
                prefix = _const_str(kw.value) or ""
                break
        router_prefix[target.id] = _norm_prefix(prefix)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        auth = "auth" if _func_requires_auth(node) else "public"
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            method = dec.func.attr
            if method not in HTTP_METHODS:
                continue
            if not isinstance(dec.func.value, ast.Name):
                continue
            router_var = dec.func.value.id

            if not dec.args:
                continue
            path = _const_str(dec.args[0])
            if not path:
                continue

            endpoints.append((router_var, method.upper(), _norm_path(path), auth))

    return router_prefix, endpoints


def main() -> int:
    if not ROUTER_PY.exists():
        raise SystemExit(f"Router file not found: {ROUTER_PY}")

    router_source = _read_text(ROUTER_PY)
    alias_to_module = _parse_router_imports(router_source)
    includes = _parse_includes(router_source, alias_to_module)

    # Build endpoints
    seen: set[tuple[str, str]] = set()
    endpoints_out: list[Endpoint] = []

    for inc in includes:
        if not inc.module:
            continue
        route_file = ROUTES_DIR / f"{inc.module}.py"
        if not route_file.exists():
            continue

        router_prefix_by_var, endpoints = _parse_route_file_endpoints(inc.module, route_file)

        # Every include_router alias points at some router var in that module; we don't know which
        # var it is, but endpoints carry router_var, and we can still compute full paths by combining
        # include_prefix + router_var_prefix + decorator path.
        for router_var, method, dec_path, auth in endpoints:
            full_path = _join_paths(inc.include_prefix, router_prefix_by_var.get(router_var, ""), dec_path)
            key = (method, full_path)
            if key in seen:
                continue
            seen.add(key)
            endpoints_out.append(
                Endpoint(
                    method=method,
                    path=full_path,
                    auth=auth,
                    source=f"services/api/app/api/routes/{inc.module}.py:{router_var}",
                )
            )

    endpoints_out.sort(key=lambda e: (e.path, e.method))

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    lines: list[str] = []
    lines.append("# API Endpoints (Generated)")
    lines.append("")
    lines.append(f"Generated from FastAPI route files at {generated_at}.")
    lines.append("")
    lines.append("- Source of truth: services/api/app/api/router.py + services/api/app/api/routes/*.py")
    lines.append("- Note: This is static parsing (best-effort); confirm behavior in the app where needed.")
    lines.append("")
    lines.append("## Endpoints")
    lines.append("")
    lines.append("| Method | Path | Auth | Source |")
    lines.append("| --- | --- | --- | --- |")
    for e in endpoints_out:
        lines.append(f"| {e.method} | {e.path} | {e.auth} | {e.source} |")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUTPUT_MD}")
    print(f"Endpoints: {len(endpoints_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
