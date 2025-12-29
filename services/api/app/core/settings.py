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
    llm_provider: str = os.getenv("SAVO_LLM_PROVIDER", "mock")
    prompt_pack_path: str = os.getenv("SAVO_PROMPT_PACK_PATH", _default_prompt_pack_path())


settings = Settings()
