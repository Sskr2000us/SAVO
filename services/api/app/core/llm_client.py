from __future__ import annotations

from datetime import date, timedelta
import json
import os
from typing import Any

import httpx


class LlmClient:
    async def generate_json(self, *, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class OpenAIClient(LlmClient):
    """OpenAI LLM client with JSON schema support"""
    
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        self.timeout = timeout
        self.base_url = "https://api.openai.com/v1"
    
    async def generate_json(self, *, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        """Generate JSON using OpenAI with structured output"""
        
        # Inject schema into messages for better adherence
        schema_instruction = {
            "role": "system",
            "content": (
                f"You MUST return a JSON object that EXACTLY matches this schema structure. "
                f"All field names, types, and nesting must be EXACTLY as specified:\n\n"
                f"{json.dumps(schema, indent=2)}\n\n"
                f"CRITICAL RULES:\n"
                f"- Use EXACT field names from schema (e.g., 'total_calories_kcal' not 'total_calories')\n"
                f"- If schema says 'array', return [], not an object\n"
                f"- Include ALL required properties\n"
                f"- Do NOT add extra properties not in schema\n"
                f"- Match types exactly (string, number, boolean, array, object)"
            )
        }
        
        # Insert schema instruction after system message
        enhanced_messages = [messages[0], schema_instruction] + messages[1:]
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": enhanced_messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract content from OpenAI response
            content = result["choices"][0]["message"]["content"]
            return json.loads(content)


class AnthropicClient(LlmClient):
    """Anthropic Claude LLM client with JSON schema support"""
    
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")
        
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.timeout = timeout
        self.base_url = "https://api.anthropic.com/v1"
    
    async def generate_json(self, *, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        """Generate JSON using Anthropic Claude"""
        
        # Convert messages to Anthropic format (system separate from messages)
        system_content = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add JSON schema instruction
        if system_content:
            system_content += "\n\nYou must respond with valid JSON only. Do not include any text outside the JSON object."
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "system": system_content,
                    "messages": anthropic_messages,
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract content from Anthropic response
            content = result["content"][0]["text"]
            return json.loads(content)


class MockLlmClient(LlmClient):
    async def generate_json(self, *, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        required = set(schema.get("required", []))

        if "normalized_inventory" in required:
            return {
                "normalized_inventory": [],
                "staples_policy_applied": {"enabled": False, "staples_included": [], "staples_excluded": []},
            }

        if "ranked_videos" in required:
            return {
                "ranked_videos": [
                    {
                        "video_id": "vid_demo_1",
                        "title": "Demo Video",
                        "channel": "Demo Channel",
                        "trust_score": 0.7,
                        "match_score": 0.6,
                        "reasons": ["Mock ranking"],
                    }
                ]
            }

        context = _extract_context(messages)
        mode = _infer_menu_mode(messages)

        if mode == "party":
            return _mock_party_plan(context)

        if mode == "weekly":
            return _mock_weekly_plan(context)

        return _mock_daily_plan()


def get_llm_client(provider: str) -> LlmClient:
    """
    Factory function to create LLM client based on provider.
    
    Supported providers:
    - mock: Mock client for testing
    - openai: OpenAI GPT models
    - anthropic: Anthropic Claude models
    """
    if provider == "mock":
        return MockLlmClient()
    elif provider == "openai":
        return OpenAIClient()
    elif provider == "anthropic":
        return AnthropicClient()
    else:
        raise ValueError(f"Unsupported SAVO_LLM_PROVIDER: {provider}. Use 'mock', 'openai', or 'anthropic'.")


def _extract_context(messages: list[dict[str, str]]) -> dict[str, Any] | None:
    for m in messages:
        content = m.get("content") or ""
        if content.startswith("CONTEXT_JSON="):
            raw = content[len("CONTEXT_JSON=") :]
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _infer_menu_mode(messages: list[dict[str, str]]) -> str:
    text = "\n".join([(m.get("content") or "") for m in messages]).lower()
    if "party" in text or "guest_count" in text:
        return "party"
    if "weekly" in text or "weekly_day" in text or "planning_window" in text:
        return "weekly"
    return "daily"


def _base_recipe_option(*, recipe_id: str, recipe_name: str, cuisine: str, agent_mode: str) -> dict[str, Any]:
    return {
        "recipe_id": recipe_id,
        "recipe_name": {"en": recipe_name},
        "cuisine": cuisine,
        "difficulty": "easy",
        "estimated_times": {"prep_minutes": 10, "cook_minutes": 10, "total_minutes": 20},
        "cooking_method": "stovetop",
        "ingredients_used": [
            {"inventory_id": "inv_demo", "canonical_name": "tomato", "amount": 2, "unit": "pcs"}
        ],
        "new_ingredients_optional": [
            {"canonical_name": "basil", "amount": 10, "unit": "g", "reason": "Improves flavor"}
        ],
        "steps": [
            {
                "step": 1,
                "instruction": {"en": "Do the prep and cook the dish."},
                "time_minutes": 10,
                "tips": ["Taste and adjust seasoning."],
            }
        ],
        "nutrition_per_serving": {
            "calories_kcal": 400,
            "macros": {"protein_g": 20, "carbs_g": 40, "fat_g": 15},
            "micros": {"fiber_g": 6, "sodium_mg": 500},
        },
        "health_fit": {"flags": [], "scores": {"simplicity": 0.8}, "adjustments": []},
        "leftover_forecast": {"expected_leftover_servings": 0, "reuse_ideas": ["N/A"]},
        "preservation_guidance": {
            "storage": "refrigerate",
            "safe_duration_hours": 24,
            "reheat_methods": ["microwave"],
            "quality_notes": "Best within a day.",
        },
        "youtube_references": [],
        "agent_mode": agent_mode,
    }


def _base_courses(*, cuisine: str, agent_mode: str) -> list[dict[str, Any]]:
    return [
        {
            "course_header": "Starter",
            "recipe_options": [
                _base_recipe_option(recipe_id="r_starter_1", recipe_name="Starter Option A", cuisine=cuisine, agent_mode=agent_mode),
                _base_recipe_option(recipe_id="r_starter_2", recipe_name="Starter Option B", cuisine=cuisine, agent_mode=agent_mode),
            ],
        },
        {
            "course_header": "Main",
            "recipe_options": [
                _base_recipe_option(recipe_id="r_main_1", recipe_name="Main Option A", cuisine=cuisine, agent_mode=agent_mode),
                _base_recipe_option(recipe_id="r_main_2", recipe_name="Main Option B", cuisine=cuisine, agent_mode=agent_mode),
            ],
        },
        {
            "course_header": "Side",
            "recipe_options": [
                _base_recipe_option(recipe_id="r_side_1", recipe_name="Side Option A", cuisine=cuisine, agent_mode=agent_mode),
                _base_recipe_option(recipe_id="r_side_2", recipe_name="Side Option B", cuisine=cuisine, agent_mode=agent_mode),
            ],
        },
    ]


def _base_plan_envelope(*, selected_cuisine: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "selected_cuisine": selected_cuisine,
        "menu_headers": ["Starter", "Main", "Side"],
        "menus": [],
        "variety_log": {"rules_applied": ["mock"], "excluded_recent": [], "diversity_scores": {"overall": 0.5}},
        "nutrition_summary": {"total_calories_kcal": 1200, "per_member_estimates": [], "warnings": []},
        "waste_summary": {
            "expiring_items_used": [],
            "waste_reduction_score": 0.5,
            "waste_avoided_value_estimate": {"currency": "USD", "value": 2.5},
        },
        "shopping_suggestions": [
            {"canonical_name": "basil", "quantity": 10, "unit": "g", "reason": "Improves flavor", "optional": True}
        ],
    }


def _mock_daily_plan() -> dict[str, Any]:
    cuisine = "italian"
    plan = _base_plan_envelope(selected_cuisine=cuisine)
    plan["menus"] = [
        {
            "menu_type": "daily",
            "servings": {"count": 2, "scaling_factor": 1.0},
            "courses": _base_courses(cuisine=cuisine, agent_mode="beginner_coach"),
        }
    ]
    return plan


def _mock_party_plan(context: dict[str, Any] | None) -> dict[str, Any]:
    cuisine = "italian"
    party_settings = (context or {}).get("party_settings") or {}
    guest_count = int(party_settings.get("guest_count") or 10)
    guest_count = max(2, min(80, guest_count))

    age_counts = party_settings.get("age_group_counts") or {}
    child_count = int(age_counts.get("child_0_12") or 0)
    agent_mode = "kid_friendly" if child_count > 0 else "beginner_coach"

    plan = _base_plan_envelope(selected_cuisine=cuisine)
    plan["menus"] = [
        {
            "menu_type": "party",
            "servings": {"count": guest_count, "scaling_factor": guest_count / 2.0},
            "courses": _base_courses(cuisine=cuisine, agent_mode=agent_mode),
        }
    ]
    return plan


def _mock_weekly_plan(context: dict[str, Any] | None) -> dict[str, Any]:
    cuisine = "italian"
    session_request = (context or {}).get("session_request") or {}

    start_date_str = session_request.get("start_date") or "2026-01-01"
    num_days = int(session_request.get("num_days") or 4)
    num_days = max(1, min(4, num_days))
    timezone = session_request.get("timezone") or "UTC"

    try:
        start = date.fromisoformat(start_date_str)
    except ValueError:
        start = date(2026, 1, 1)

    plan = _base_plan_envelope(selected_cuisine=cuisine)
    plan["planning_window"] = {"start_date": start.isoformat(), "num_days": num_days, "timezone": timezone}

    menus: list[dict[str, Any]] = []
    for i in range(num_days):
        menus.append(
            {
                "menu_type": "weekly_day",
                "day_index": i,
                "date": (start + timedelta(days=i)).isoformat(),
                "servings": {"count": 2, "scaling_factor": 1.0},
                "courses": _base_courses(cuisine=cuisine, agent_mode="beginner_coach"),
            }
        )
    plan["menus"] = menus
    return plan
