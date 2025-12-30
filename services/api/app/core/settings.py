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


settings = Settings()
