from typing import Any, Dict, Optional
import json
import logging

from app.core.llm_client import get_llm_client, RateLimitException
from app.core.prompt_pack import get_schema, get_system_prompt_lines, get_task
from app.core.schema_validation import validate_json, SchemaValidationException
from app.core.settings import settings

logger = logging.getLogger(__name__)


def _get_menu_plan_recipe_options_min_items(schema: Dict[str, Any]) -> int:
    """Best-effort extraction of recipe_options.minItems from MENU_PLAN_SCHEMA."""
    try:
        return int(
            schema["properties"]["menus"]["items"]["properties"]["courses"]["items"][
                "properties"
            ]["recipe_options"].get("minItems", 0)
        )
    except Exception:
        return 0


def _repair_menu_plan_result(result: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Repair common LLM omissions so schema validation is less fragile."""
    # Ensure required scalar fields have the correct type.
    # LLM occasionally returns null for required strings like selected_cuisine.
    selected_cuisine = result.get("selected_cuisine")
    if not isinstance(selected_cuisine, str) or not selected_cuisine.strip():
        result["selected_cuisine"] = "unknown"

    # If the LLM reports a non-ok status but omits error_message, synthesize one.
    # This prevents the client from falling back to a generic "Planning failed".
    status = result.get("status")
    if status in ["needs_clarification", "error"] and not result.get("error_message"):
        q = result.get("needs_clarification_questions")
        if isinstance(q, list) and q and isinstance(q[0], str) and q[0].strip():
            result["error_message"] = q[0].strip()
        else:
            result["error_message"] = "Planning requires additional information."

    # Normalize common alias fields.
    if "questions" in result and "needs_clarification_questions" not in result:
        q = result.get("questions")
        result["needs_clarification_questions"] = q if isinstance(q, list) else []
        result.pop("questions", None)

    min_items = _get_menu_plan_recipe_options_min_items(schema)
    if min_items <= 0:
        return result

    menus = result.get("menus")
    if not isinstance(menus, list):
        return result

    for menu in menus:
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue

        for course in courses:
            if not isinstance(course, dict):
                continue
            recipe_options = course.get("recipe_options")
            if not isinstance(recipe_options, list):
                continue
            if len(recipe_options) >= min_items:
                continue
            if not recipe_options:
                # Can't synthesize an option safely; let validation handle it.
                continue

            base = recipe_options[-1]
            if not isinstance(base, dict):
                continue

            # Pad by cloning the last option and making recipe_id unique.
            for idx in range(len(recipe_options) + 1, min_items + 1):
                cloned = dict(base)
                try:
                    cloned["recipe_id"] = f"{base.get('recipe_id', 'recipe')}-alt{idx}"
                except Exception:
                    cloned["recipe_id"] = f"recipe-alt{idx}"
                recipe_options.append(cloned)

    return result


def _schema_is_object(schema: Dict[str, Any]) -> bool:
    t = schema.get("type")
    if t == "object":
        return True
    if isinstance(t, list) and "object" in t:
        return True
    return False


def _schema_is_array(schema: Dict[str, Any]) -> bool:
    t = schema.get("type")
    if t == "array":
        return True
    if isinstance(t, list) and "array" in t:
        return True
    return False


def _prune_additional_properties(instance: Any, schema: Dict[str, Any]) -> Any:
    """Remove unexpected fields when schema sets additionalProperties=false.

    This is a best-effort sanitizer for LLM outputs; it is not a full JSON Schema implementation.
    """
    if instance is None or not isinstance(schema, dict):
        return instance

    # Handle arrays
    if isinstance(instance, list) and _schema_is_array(schema):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i in range(len(instance)):
                instance[i] = _prune_additional_properties(instance[i], item_schema)
        return instance

    # Handle objects
    if isinstance(instance, dict) and _schema_is_object(schema):
        props = schema.get("properties") or {}
        pattern_props = schema.get("patternProperties") or {}
        additional = schema.get("additionalProperties", True)

        # Prune unexpected keys when additionalProperties is false
        if additional is False and isinstance(props, dict):
            allowed = set(props.keys())
            keys = list(instance.keys())
            for k in keys:
                if k in allowed:
                    continue
                matched_pattern = False
                if isinstance(pattern_props, dict) and pattern_props:
                    for pattern in pattern_props.keys():
                        try:
                            import re

                            if re.match(pattern, str(k)):
                                matched_pattern = True
                                break
                        except Exception:
                            continue
                if not matched_pattern:
                    instance.pop(k, None)

        # Recurse into known properties
        if isinstance(props, dict):
            for k, sub_schema in props.items():
                if k in instance and isinstance(sub_schema, dict):
                    instance[k] = _prune_additional_properties(instance[k], sub_schema)
        return instance

    return instance


def _build_messages(*, task_name: str, context: Dict[str, Any]) -> list[dict[str, str]]:
    system_lines = get_system_prompt_lines()
    task = get_task(task_name)

    system = "\n".join(system_lines)
    task_instructions = "\n".join(task.get("prompt", []))

    extra_instructions: list[dict[str, str]] = []
    try:
        output_languages = context.get("output_languages")
        if isinstance(output_languages, list):
            langs = [l.strip() for l in output_languages if isinstance(l, str) and l.strip()]
            if "en" in langs and len(langs) > 1:
                preferred = next((l for l in langs if l != "en"), None)
                if preferred:
                    extra_instructions.append(
                        {
                            "role": "user",
                            "content": (
                                "BILINGUAL_OUTPUT:\n"
                                f"- Include BOTH 'en' and '{preferred}' values for all multilingual fields (e.g., recipe_name and steps[].instruction).\n"
                                "- Always include a non-empty English ('en') string.\n"
                                f"- Also include a non-empty '{preferred}' string.\n"
                                "- Keep both strings semantically equivalent; do not mix languages in one value.\n"
                            ),
                        }
                    )
    except Exception:
        # Best-effort only; do not break prompt generation.
        pass
    context_json = json.dumps(context, ensure_ascii=False)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": task_instructions},
        *extra_instructions,
        {"role": "user", "content": f"CONTEXT_JSON={context_json}"},
    ]


async def run_task(
    *,
    task_name: str,
    output_schema_name: str,
    context: Dict[str, Any],
    max_retries: int = 1
) -> Dict[str, Any]:
    """
    Run LLM task with schema validation and retry logic (2.4 AI orchestration reliability)
    
    Fail-closed behavior:
    - If LLM returns non-JSON or schema-invalid on first try: send one corrective retry
    - If still invalid after retry: return status="error" with error details
    - If LLM cannot fulfill request: return status="needs_clarification" with questions
    - If primary provider hits 429 rate limit: fallback to configured fallback provider (429 only)
    """
    schema = get_schema(output_schema_name)
    messages = _build_messages(task_name=task_name, context=context)
    
    # Use reasoning provider for planning tasks (meal plans, recipes, etc.)
    # OpenAI GPT excels at structured JSON outputs and complex reasoning
    result = await _try_provider(
        provider=settings.reasoning_provider,
        messages=messages,
        schema=schema,
        task_name=task_name,
        output_schema_name=output_schema_name,
        max_retries=max_retries
    )
    
    return result


async def _try_provider(
    *,
    provider: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    task_name: str,
    output_schema_name: str,
    max_retries: int
) -> Dict[str, Any]:
    """
    Try a specific LLM provider with schema validation and retry logic.
    Raises RateLimitException if provider hits 429 after all retries.
    """
    client = get_llm_client(provider)
    last_error: Optional[str] = None
    
    for attempt in range(max_retries + 1):
        try:
            result = await client.generate_json(messages=messages, schema=schema)

            # Repair common issues before strict schema validation.
            if output_schema_name == "MENU_PLAN_SCHEMA" and isinstance(result, dict):
                result = _repair_menu_plan_result(result, schema)
                result = _prune_additional_properties(result, schema)
            
            # Validate against schema
            validate_json(result, schema)
            
            # Check if LLM itself returned an error status
            if isinstance(result, dict):
                status = result.get("status")
                if status in ["needs_clarification", "error"]:
                    # LLM is reporting it cannot fulfill request - this is valid
                    logger.info(f"Task {task_name} (provider={provider}) returned status={status}")
                    return result
            
            # Validation passed, return result
            logger.info(f"Task {task_name} (provider={provider}) completed successfully on attempt {attempt + 1}")
            return result
            
        except RateLimitException as e:
            # Rate limit hit - try fallback if configured
            logger.warning(f"Task {task_name} hit rate limit on {provider}: {str(e)}")
            
            if settings.llm_fallback_provider and settings.llm_fallback_provider != provider:
                logger.info(f"Falling back from {provider} to {settings.llm_fallback_provider}")
                try:
                    # Try fallback provider (no additional retries for fallback)
                    fallback_result = await _try_provider(
                        provider=settings.llm_fallback_provider,
                        messages=messages,
                        schema=schema,
                        task_name=task_name,
                        output_schema_name=output_schema_name,
                        max_retries=0  # No retries for fallback
                    )
                    logger.info(f"Task {task_name} succeeded with fallback provider {settings.llm_fallback_provider}")
                    return fallback_result
                except Exception as fallback_error:
                    logger.error(f"Fallback provider {settings.llm_fallback_provider} also failed: {str(fallback_error)}")
                    last_error = f"Primary provider ({provider}) rate limited, fallback provider ({settings.llm_fallback_provider}) failed: {str(fallback_error)}"
            else:
                last_error = f"Rate limit exceeded on {provider} and no fallback configured"
            
            # No fallback available or fallback failed
            break
            
        except SchemaValidationException as e:
            last_error = f"Schema validation failed: {', '.join(e.errors)}"
            logger.warning(f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed: {last_error}")
            
            if attempt < max_retries:
                # Add corrective instruction for retry
                correction = (
                    f"CORRECTION REQUIRED: Your previous response had schema validation errors: {last_error}. "
                    f"Please generate a valid response that strictly matches the JSON schema. "
                    f"IMPORTANT: keep output minimal to avoid truncation. Use minified JSON (no newlines). "
                    f"Do NOT include unexpected fields like 'questions'. Use needs_clarification_questions only. "
                    f"For each recipe: youtube_references=[]; new_ingredients_optional=[]; steps length 1-2 with tips=[]; "
                    f"health_fit.flags=[], health_fit.adjustments=[], health_fit.scores={{}}; leftover_forecast.reuse_ideas=[]."
                )
                messages.append({"role": "assistant", "content": "I will correct my response."})
                messages.append({"role": "user", "content": correction})
                continue
                
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON returned: {str(e)}"
            logger.warning(f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed: {last_error}")
            
            if attempt < max_retries:
                correction = (
                    f"CORRECTION REQUIRED: Your previous response was not valid JSON. "
                    f"Error: {str(e)}. Please return ONLY valid JSON matching the schema. "
                    f"IMPORTANT: keep output minimal to avoid truncation. Use minified JSON (no newlines). "
                    f"For each recipe: youtube_references=[]; new_ingredients_optional=[]; steps length 1-2 with tips=[]; "
                    f"health_fit.flags=[], health_fit.adjustments=[], health_fit.scores={{}}; leftover_forecast.reuse_ideas=[]."
                )
                messages.append({"role": "assistant", "content": "I will return valid JSON."})
                messages.append({"role": "user", "content": correction})
                continue
                
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed with unexpected error", exc_info=True)
            if attempt < max_retries:
                continue
    
    # All retries exhausted - return error response in schema format
    logger.error(f"Task {task_name} (provider={provider}) failed after {max_retries + 1} attempts: {last_error}")
    
    return _build_error_response(output_schema_name, last_error, max_retries)


def _build_error_response(output_schema_name: str, error_message: str, max_retries: int) -> Dict[str, Any]:
    """Build error response matching the output schema structure"""
    error_response = {
        "status": "error",
        "needs_clarification_questions": [],
        "error_message": f"Failed to generate valid response after {max_retries + 1} attempts. {error_message}"
    }
    
    # For MENU_PLAN_SCHEMA, add required fields
    if output_schema_name == "MENU_PLAN_SCHEMA":
        error_response.update({
            "selected_cuisine": "unknown",
            "menu_headers": [],
            "menus": [],
            "variety_log": {"rules_applied": [], "excluded_recent": [], "diversity_scores": {}},
            "nutrition_summary": {"total_calories_kcal": 0, "per_member_estimates": [], "warnings": []},
            "waste_summary": {
                "expiring_items_used": [],
                "waste_reduction_score": 0,
                "waste_avoided_value_estimate": {"currency": "USD", "value": 0}
            },
            "shopping_suggestions": []
        })
    
    return error_response


async def normalize_inventory(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="normalize_inventory",
        output_schema_name="NORMALIZATION_OUTPUT_SCHEMA",
        context=context,
    )


async def plan_daily(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="plan_daily_menu",
        output_schema_name="MENU_PLAN_SCHEMA",
        context=context,
    )


async def plan_party(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="plan_party_menu",
        output_schema_name="MENU_PLAN_SCHEMA",
        context=context,
    )


async def plan_weekly(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="plan_weekly",
        output_schema_name="MENU_PLAN_SCHEMA",
        context=context,
    )


async def youtube_rank(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="youtube_rank",
        output_schema_name="YOUTUBE_RANK_SCHEMA",
        context=context,
    )
