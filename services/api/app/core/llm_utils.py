from __future__ import annotations

import asyncio
from typing import Any

from app.core.llm_client import LlmClient, RateLimitException


async def generate_json_with_retries(
    *,
    client: LlmClient,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    max_attempts: int = 2,
    repair_hint: str | None = None,
    mode_hint: str | None = None,
    temperature: float | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
) -> dict[str, Any]:
    """Generate JSON with a small retry/repair loop.

    Goal: keep endpoints robust against occasional non-JSON/truncated outputs without
    increasing latency too much.

    - Retries at most once by default.
    - Adds a compactness + JSON-only "repair" system message on retry.
    """

    base_messages = list(messages)
    last_error: Exception | None = None

    max_attempts = max(1, min(int(max_attempts or 1), 3))

    for attempt in range(max_attempts):
        try:
            return await client.generate_json(
                messages=base_messages,
                schema=schema,
                mode_hint=mode_hint,
                temperature=temperature,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
        except RateLimitException as e:
            last_error = e
            # Keep this quick; we only sleep if provider explicitly gives a short retry_after.
            retry_after = getattr(e, "retry_after", None)
            if retry_after is None or attempt >= max_attempts - 1:
                raise
            try:
                await asyncio.sleep(min(1.0, float(retry_after)))
            except Exception:
                await asyncio.sleep(0.5)
        except Exception as e:
            last_error = e
            if attempt >= max_attempts - 1:
                break

            # Insert a stronger system instruction right after the first system message
            # (or at the start if the caller provided only user messages).
            repair_lines = [
                "Your previous response was invalid JSON or did not match the required structure.",
                "Return ONLY valid JSON matching the schema. No markdown, no code fences, no commentary.",
                "Be MORE concise to avoid truncation:",
                "- Keep strings <= 120 chars",
                "- Keep steps <= 8 and tips <= 4",
                "- Avoid optional fields unless clearly helpful",
            ]
            if repair_hint and str(repair_hint).strip():
                repair_lines.append(f"Repair hint: {str(repair_hint).strip()}")

            repair_msg = {"role": "system", "content": "\n".join(repair_lines)}

            retry_messages = list(base_messages)
            if retry_messages and retry_messages[0].get("role") == "system":
                retry_messages.insert(1, repair_msg)
            else:
                retry_messages.insert(0, repair_msg)

            base_messages = retry_messages

    assert last_error is not None
    raise last_error
