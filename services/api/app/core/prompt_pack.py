import json
from functools import lru_cache
from typing import Any, Dict

from app.core.settings import settings


@lru_cache(maxsize=1)
def load_prompt_pack() -> Dict[str, Any]:
    with open(settings.prompt_pack_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_schema(schema_name: str) -> Dict[str, Any]:
    pack = load_prompt_pack()
    schemas = pack.get("prompt_pack", {}).get("schemas", {})
    if schema_name not in schemas:
        raise KeyError(f"Schema not found in prompt pack: {schema_name}")
    return schemas[schema_name]


def get_task(task_name: str) -> Dict[str, Any]:
    pack = load_prompt_pack()
    tasks = pack.get("prompt_pack", {}).get("prompts", {}).get("tasks", [])
    for t in tasks:
        if t.get("name") == task_name:
            return t
    raise KeyError(f"Task not found in prompt pack: {task_name}")


def get_system_prompt_lines() -> list[str]:
    pack = load_prompt_pack()
    return pack.get("prompt_pack", {}).get("prompts", {}).get("system", {}).get("content", [])
