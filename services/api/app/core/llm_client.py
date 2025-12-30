from __future__ import annotations

from datetime import date, timedelta
import ast
import base64
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _parse_json_from_text(text: str) -> Any:
    """Best-effort JSON extraction from model output.

    Handles common wrappers like markdown code fences and prefixed explanations.
    Raises json.JSONDecodeError if no JSON can be parsed.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return json.loads(cleaned)  # will raise JSONDecodeError

    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    # First try strict parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as first_error:
        # Try to locate the first JSON value inside the text
        decoder = json.JSONDecoder()
        candidates = [pos for pos in (cleaned.find("{"), cleaned.find("[")) if pos != -1]
        if not candidates:
            raise first_error

        start = min(candidates)
        slice_text = cleaned[start:]

        # Try strict JSON from the first bracket
        try:
            value, _end = decoder.raw_decode(slice_text)
            return value
        except json.JSONDecodeError:
            # Fallback: some models output Python-ish dicts (single quotes, None, True/False).
            # ast.literal_eval is safe for literals and can recover many of these.
            try:
                value = ast.literal_eval(slice_text)
                return value
            except Exception:
                raise first_error


class RateLimitException(Exception):
    """Raised when LLM provider returns 429 rate limit error"""
    def __init__(self, provider: str, retry_after: int | None = None):
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded for provider: {provider}")


class LlmClient:
    async def generate_json(self, *, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class OpenAIClient(LlmClient):
    """OpenAI LLM client with JSON schema support and Vision API"""
    
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")  # Updated to gpt-4o (current model)
        self.vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")  # gpt-4o has best vision + text reading
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
            # Retry logic for rate limits
            max_retries = 3
            for attempt in range(max_retries):
                try:
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
                            "max_tokens": 8192,  # Increased to handle full meal plans
                        }
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    # Extract content from OpenAI response
                    content = result["choices"][0]["message"]["content"]
                    
                    # Check if response was truncated
                    finish_reason = result["choices"][0].get("finish_reason")
                    if finish_reason == "length":
                        logger.warning(f"OpenAI response truncated (finish_reason=length). Increase max_tokens.")
                        raise ValueError("Response truncated - increase max_tokens")
                    
                    return json.loads(content)
                    
                except httpx.HTTPStatusError as e:
                    # Log error details for debugging
                    error_body = e.response.text if hasattr(e.response, 'text') else str(e)
                    logger.error(f"OpenAI API error {e.response.status_code}: {error_body}")
                    logger.error(f"Request model: {self.model}")
                    
                    if e.response.status_code == 429:
                        # Rate limited
                        retry_after = None
                        if "retry-after" in e.response.headers:
                            try:
                                retry_after = int(e.response.headers["retry-after"])
                            except ValueError:
                                pass
                        
                        if attempt < max_retries - 1:
                            # Wait with exponential backoff (respect Retry-After if present)
                            wait_time = retry_after if retry_after else (2 ** attempt)  # 1s, 2s, 4s
                            import asyncio
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Final attempt exhausted, raise RateLimitException for fallback
                            raise RateLimitException("openai", retry_after)
                    raise  # Re-raise if not 429

    async def generate_json_multimodal(
        self,
        *,
        system: str,
        user: str,
        inline_images: list[dict[str, str]],
        max_output_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Any:
        """Generate JSON from text + images using OpenAI Vision API.
        
        inline_images items must be: {"mimeType": "image/jpeg", "data": "<base64>"}
        OpenAI Vision (gpt-4o) excels at reading text on product labels and packaging.
        """
        
        # Build content array with text and images
        content = []
        
        # Add system + user instructions as text
        combined_text = ""
        if system:
            combined_text += f"SYSTEM: {system}\n\n"
        combined_text += f"USER: {user}"
        
        content.append({
            "type": "text",
            "text": combined_text
        })
        
        # Add images
        for img in inline_images or []:
            mime = img.get("mimeType", "image/jpeg")
            data = img.get("data", "")
            if not data:
                continue
                
            # OpenAI expects: data:image/jpeg;base64,<data>
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{data}"
                }
            })
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.vision_model,  # Use gpt-4o for vision
                    "messages": [
                        {
                            "role": "user",
                            "content": content
                        }
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": max_output_tokens,
                    "temperature": temperature,
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Parse JSON from response
            text = result["choices"][0]["message"]["content"]
            return _parse_json_from_text(text)


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


class GoogleClient(LlmClient):
    """Google Gemini LLM client with JSON schema support"""
    
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is required for Google provider")
        
        self.model = model or os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
        self.timeout = timeout
    
    async def generate_json(self, *, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        """Generate JSON using Google Gemini with structured output"""
        
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
        
        # Combine system messages and convert to Gemini format
        system_parts = []
        user_parts = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "user":
                user_parts.append(msg["content"])
        
        # Add schema instruction to system prompt
        system_parts.append(schema_instruction["content"])

        # Explicit JSON-only rule (helps Gemini avoid prose/codefences)
        system_parts.append(
            "Return ONLY a valid JSON value. No markdown, no code fences, no commentary."
        )

        # Keep the output compact to avoid truncation (which frequently produces invalid JSON).
        system_parts.append(
            "COMPACTNESS REQUIREMENTS (must follow): "
            "- Use EXACTLY 2 recipe_options per course (not 3). "
            "- Set youtube_references to [] for EVERY recipe (empty array). "
            "- Set new_ingredients_optional to [] unless absolutely necessary. "
            "- Use 1–2 steps per recipe; each instruction <= 120 chars; tips must be []. "
            "- Keep health_fit.flags=[] and health_fit.adjustments=[]; scores may be {}. "
            "- Keep leftover_forecast.reuse_ideas to [] and expected_leftover_servings=0 unless clearly needed. "
            "- Keep preservation_guidance.reheat_methods to [] or 1 item; quality_notes <= 80 chars. "
            "- Prefer short strings everywhere; do NOT pretty-print; output minified JSON with no newlines."
        )
        
        # Gemini format: combine all into a single user message
        combined_text = ""
        if system_parts:
            combined_text += "SYSTEM INSTRUCTIONS:\n" + "\n\n".join(system_parts) + "\n\n"
        if user_parts:
            combined_text += "USER REQUEST:\n" + "\n\n".join(user_parts)
        
        contents = [{
            "role": "user",
            "parts": [{"text": combined_text}]
        }]
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Retry logic for rate limits
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Prefer JSON-mode if supported by the model.
                    # NOTE: Gemini's response schema feature does NOT accept full JSON Schema.
                    # Our prompt-pack schemas contain keywords like if/then/allOf/additionalProperties,
                    # which Gemini rejects with INVALID_ARGUMENT. We enforce schema on our side.
                    generation_config: dict[str, Any] = {
                        "temperature": 0.1,
                        # Allow a larger response to reduce truncation-induced invalid JSON.
                        "maxOutputTokens": 8192,
                        "responseMimeType": "application/json",
                    }

                    response = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                        headers={
                            "Content-Type": "application/json",
                        },
                        params={
                            "key": self.api_key
                        },
                        json={
                            "contents": contents,
                            "generationConfig": generation_config,
                        }
                    )

                    # Some models/tiers reject responseMimeType; retry once without it.
                    if response.status_code == 400 and attempt < max_retries - 1:
                        body_text = response.text or ""
                        rejected_fields: list[str] = []
                        if "responseMimeType" in body_text or "response_mime_type" in body_text:
                            rejected_fields.append("responseMimeType")
                        # Defensive: if the API starts reporting schema errors, we don't use it.
                        if "responseSchema" in body_text or "response_schema" in body_text:
                            rejected_fields.append("responseSchema")

                        if rejected_fields:
                            logger.warning(
                                f"Gemini rejected {', '.join(rejected_fields)}; retrying without structured output fields"
                            )
                            for f in rejected_fields:
                                if f == "responseMimeType":
                                    generation_config.pop("responseMimeType", None)
                                if f == "responseSchema":
                                    generation_config.pop("responseSchema", None)
                            response = await client.post(
                                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                                headers={
                                    "Content-Type": "application/json",
                                },
                                params={
                                    "key": self.api_key
                                },
                                json={
                                    "contents": contents,
                                    "generationConfig": generation_config,
                                }
                            )
                    
                    if response.status_code != 200:
                        error_detail = response.text
                        logger.error(f"Google API error response: {error_detail}")
                        raise httpx.HTTPStatusError(
                            f"Google API error: {error_detail}",
                            request=response.request,
                            response=response
                        )
                    
                    result = response.json()
                    logger.info(f"Google API response structure: {json.dumps(result, indent=2)[:500]}")
                    
                    # Extract content from Google response
                    if "candidates" not in result or not result["candidates"]:
                        logger.error(f"No candidates in response: {result}")
                        raise ValueError(f"No candidates in Gemini response: {result}")
                    
                    candidate = result["candidates"][0]
                    if "content" not in candidate:
                        logger.error(f"No content in candidate: {candidate}")
                        raise ValueError(f"No content in candidate: {candidate}")
                    
                    parts = candidate.get("content", {}).get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
                    content_text = "\n".join(text_parts).strip()

                    parsed = _parse_json_from_text(content_text)
                    if not isinstance(parsed, dict):
                        # Keep the contract consistent with other providers
                        raise json.JSONDecodeError(
                            "Expected a JSON object", content_text, 0
                        )
                    return parsed
                    
                except httpx.HTTPStatusError as e:
                    logger.error(f"Google API HTTP error: {e.response.text if hasattr(e.response, 'text') else str(e)}")
                    if e.response.status_code == 429 and attempt < max_retries - 1:
                        # Rate limited - wait with exponential backoff
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        import asyncio
                        await asyncio.sleep(wait_time)
                        continue
                    raise  # Re-raise if not 429 or final attempt

    async def generate_json_multimodal(
        self,
        *,
        system: str,
        user: str,
        inline_images: list[dict[str, str]],
        max_output_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Any:
        """Generate JSON from text + one or more inline images.

        inline_images items must be: {"mimeType": "image/jpeg", "data": "<base64>"}
        """

        system_text = (system or "").strip()
        user_text = (user or "").strip()

        parts: list[dict[str, Any]] = []
        combined = ""
        if system_text:
            combined += "SYSTEM INSTRUCTIONS:\n" + system_text + "\n\n"
        combined += "USER REQUEST:\n" + user_text
        parts.append({"text": combined})

        # Add images as inlineData parts
        for img in inline_images or []:
            mime = (img.get("mimeType") or "image/jpeg").strip()
            data = (img.get("data") or "").strip()
            if not data:
                continue
            # Defensive: accept raw bytes encoded accidentally
            if not isinstance(data, str):
                data = base64.b64encode(data).decode("ascii")
            parts.append({"inlineData": {"mimeType": mime, "data": data}})

        contents = [{"role": "user", "parts": parts}]

        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                headers={"Content-Type": "application/json"},
                params={"key": self.api_key},
                json={
                    "contents": contents,
                    "generationConfig": generation_config,
                },
            )

            # Some models reject responseMimeType; retry once without it.
            if response.status_code == 400:
                body_text = response.text or ""
                if "responseMimeType" in body_text or "response_mime_type" in body_text:
                    generation_config.pop("responseMimeType", None)
                    response = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                        headers={"Content-Type": "application/json"},
                        params={"key": self.api_key},
                        json={
                            "contents": contents,
                            "generationConfig": generation_config,
                        },
                    )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Google API error response: {error_detail}")
                raise httpx.HTTPStatusError(
                    f"Google API error: {error_detail}",
                    request=response.request,
                    response=response,
                )

            result = response.json()
            if "candidates" not in result or not result["candidates"]:
                raise ValueError(f"No candidates in Gemini response: {result}")

            candidate = result["candidates"][0]
            parts_out = candidate.get("content", {}).get("parts", [])
            text_parts = [p.get("text", "") for p in parts_out if isinstance(p, dict) and p.get("text")]
            content_text = "\n".join(text_parts).strip()

            return _parse_json_from_text(content_text)


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
    - google: Google Gemini models
    """
    if provider == "mock":
        return MockLlmClient()
    elif provider == "openai":
        return OpenAIClient()
    elif provider == "anthropic":
        return AnthropicClient()
    elif provider == "google":
        return GoogleClient()
    else:
        raise ValueError(f"Unsupported SAVO_LLM_PROVIDER: {provider}. Use 'mock', 'openai', 'anthropic', or 'google'.")


def get_vision_provider() -> str:
    """
    Get the provider for vision tasks (image scanning).
    Defaults to Google Gemini Vision which excels at image understanding.
    """
    return os.getenv("SAVO_VISION_PROVIDER", "google")


def get_reasoning_provider() -> str:
    """
    Get the provider for reasoning tasks (meal planning, recipes, YouTube ranking).
    Defaults to OpenAI GPT for superior structured JSON outputs and reasoning.
    Falls back to SAVO_LLM_PROVIDER for backward compatibility.
    """
    reasoning = os.getenv("SAVO_REASONING_PROVIDER")
    if reasoning:
        return reasoning
    # Fallback to legacy SAVO_LLM_PROVIDER for backward compatibility
    return os.getenv("SAVO_LLM_PROVIDER", "openai")


def get_vision_client() -> LlmClient:
    """
    Get LLM client for vision tasks (image scanning).
    Uses Google Gemini Vision by default for optimal image understanding.
    """
    provider = get_vision_provider()
    return get_llm_client(provider)


def get_reasoning_client() -> LlmClient:
    """
    Get LLM client for reasoning tasks (planning, recipes, ranking).
    Uses OpenAI GPT by default for superior structured outputs and reasoning.
    """
    provider = get_reasoning_provider()
    return get_llm_client(provider)


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
