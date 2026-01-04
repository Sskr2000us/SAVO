"""Recipe endpoints - image generation, import, and sharing."""

from datetime import datetime, timedelta, timezone
import html as _html

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from uuid import uuid4
from typing import Any, Optional
import json
import re
import html
import os
import httpx

from openai import AsyncOpenAI

from app.middleware.auth import get_current_user
from fastapi import Depends
from app.core.llm_client import get_reasoning_client
from app.core.database import get_db_client

router = APIRouter()
public_router = APIRouter()


def _recipe_schema() -> dict[str, Any]:
    # Matches the Flutter `Recipe` model in apps/mobile/lib/models/planning.dart
    return {
        "type": "object",
        "properties": {
            "recipe_id": {"type": "string"},
            "recipe_name": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            "cuisine": {"type": "string"},
            "difficulty": {"type": "string"},
            "estimated_times": {
                "type": "object",
                "properties": {
                    "prep_minutes": {"type": "integer"},
                    "cook_minutes": {"type": "integer"},
                    "total_minutes": {"type": "integer"},
                },
                "required": ["prep_minutes", "cook_minutes", "total_minutes"],
                "additionalProperties": False,
            },
            "cooking_method": {"type": "string"},
            "ingredients_used": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "inventory_id": {"type": "string"},
                        "canonical_name": {"type": "string"},
                        "amount": {"type": "number"},
                        "unit": {"type": "string"},
                    },
                    "required": ["inventory_id", "canonical_name", "amount", "unit"],
                    "additionalProperties": False,
                },
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "integer"},
                        "instruction": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "time_minutes": {"type": "integer"},
                        "tips": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["step", "instruction", "time_minutes", "tips"],
                    "additionalProperties": False,
                },
            },
            "nutrition_per_serving": {"type": "object"},
            "health_benefits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
            },
            "leftover_forecast": {"type": "object"},
        },
        "required": [
            "recipe_id",
            "recipe_name",
            "cuisine",
            "difficulty",
            "estimated_times",
            "cooking_method",
            "ingredients_used",
            "steps",
            "nutrition_per_serving",
            "leftover_forecast",
        ],
        "additionalProperties": True,
    }


def _clean_html_to_text(html_text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _translate_recipe_fields(
    *,
    recipe: dict[str, Any],
    target_language: str,
) -> dict[str, Any]:
    target_language = (target_language or "").strip().lower()
    if not target_language or target_language == "en":
        return recipe

    # Only translate if English exists
    name_en = ((recipe.get("recipe_name") or {}).get("en") or "").strip()
    steps = recipe.get("steps") or []
    steps_en = [((s.get("instruction") or {}).get("en") or "").strip() for s in steps]

    if not name_en and not any(steps_en):
        return recipe

    schema = {
        "type": "object",
        "properties": {
            "recipe_name": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["recipe_name", "steps"],
        "additionalProperties": False,
    }

    client = get_reasoning_client()
    messages = [
        {
            "role": "system",
            "content": (
                "You are a precise culinary translator. Translate the recipe name and each step into the requested language. "
                "Do not add or remove steps. Keep quantities, units, temperatures, and timings unchanged. Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "target_language": target_language,
                    "recipe_name_en": name_en,
                    "steps_en": steps_en,
                }
            ),
        },
    ]

    translated = await client.generate_json(messages=messages, schema=schema)
    translated_name = (translated.get("recipe_name") or "").strip()
    translated_steps = translated.get("steps") or []

    recipe_name = recipe.get("recipe_name") or {}
    if translated_name:
        recipe_name[target_language] = translated_name
    recipe["recipe_name"] = recipe_name

    for i, step in enumerate(steps):
        if i >= len(translated_steps):
            break
        t = (translated_steps[i] or "").strip()
        if not t:
            continue
        instr = step.get("instruction") or {}
        instr[target_language] = t
        step["instruction"] = instr
        steps[i] = step
    recipe["steps"] = steps
    return recipe


class RecipeImportRequest(BaseModel):
    source_url: Optional[str] = Field(default=None, description="Recipe URL to import")
    source_text: Optional[str] = Field(default=None, description="Recipe text to import")
    output_language: str = Field(default="en", description="Primary output language (currently 'en')")
    secondary_language: Optional[str] = Field(default=None, description="Secondary language for bilingual output")


class RecipeShareRequest(BaseModel):
    recipe: dict[str, Any]
    expires_hours: int = Field(default=24 * 7, ge=1, le=24 * 30)


@router.post("/import")
async def import_recipe(
    req: RecipeImportRequest,
    user_id: str = Depends(get_current_user),
):
    """Import a recipe from URL or pasted text and return a SAVO recipe JSON."""
    _ = user_id  # reserved for future per-user storage

    has_url = bool(req.source_url and req.source_url.strip())
    has_text = bool(req.source_text and req.source_text.strip())
    if has_url == has_text:
        raise HTTPException(status_code=400, detail="Provide exactly one of source_url or source_text")

    source_text = ""
    if has_url:
        url = req.source_url.strip()
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                r = await client.get(url)
                r.raise_for_status()
                source_text = _clean_html_to_text(r.text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}")
    else:
        source_text = req.source_text.strip()

    # Guardrails for token size
    source_text = source_text[:20000]

    recipe_id = str(uuid4())
    schema = _recipe_schema()

    client = get_reasoning_client()
    messages = [
        {
            "role": "system",
            "content": (
                "You are SAVO's recipe importer. Extract a single recipe from the provided content. "
                "Return JSON ONLY that matches the given schema. "
                "If some fields are not stated, fill with reasonable defaults. "
                "ingredients_used should include canonical_name, amount, unit; use inventory_id as empty string. "
                "steps must be numbered starting at 1 and include instruction.en."
            ),
        },
        {
            "role": "user",
            "content": source_text,
        },
    ]

    recipe = await client.generate_json(messages=messages, schema=schema)

    # Ensure required shape + stable id
    recipe["recipe_id"] = recipe.get("recipe_id") or recipe_id
    recipe.setdefault("recipe_name", {})
    if isinstance(recipe["recipe_name"], dict) and "en" not in recipe["recipe_name"]:
        # best-effort: use any existing name
        if recipe["recipe_name"]:
            first_key = next(iter(recipe["recipe_name"].keys()))
            recipe["recipe_name"]["en"] = recipe["recipe_name"].get(first_key, "")

    recipe = await _translate_recipe_fields(recipe=recipe, target_language=req.secondary_language or "")
    return {"recipe": recipe}


@router.post("/share")
async def share_recipe(
    req: RecipeShareRequest,
    user_id: str = Depends(get_current_user),
):
    """Create a shareable recipe link.

    Stores the recipe payload server-side and returns a share id.
    """

    supabase = get_db_client()
    share_id = str(uuid4())

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=req.expires_hours)

    # Ensure recipe id exists for client-side convenience.
    recipe = dict(req.recipe or {})
    if not (recipe.get("recipe_id") or "").strip():
        recipe["recipe_id"] = str(uuid4())

    payload = {
        "id": share_id,
        "owner_user_id": user_id,
        "recipe": recipe,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    try:
        supabase.table("shared_recipes").insert(payload).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create share link: {e}")

    return {
        "success": True,
        "share_id": share_id,
        "expires_at": expires_at.isoformat(),
        "share_path": f"/r/{share_id}",
    }


@router.get("/shared/{share_id}")
async def get_shared_recipe(share_id: str):
    """Fetch a shared recipe payload (public)."""

    supabase = get_db_client()
    try:
        result = (
            supabase.table("shared_recipes")
            .select("id,recipe,expires_at")
            .eq("id", share_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load shared recipe: {e}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Shared recipe not found")

    row = result.data[0]
    expires_at = row.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                raise HTTPException(status_code=410, detail="Shared recipe expired")
        except HTTPException:
            raise
        except Exception:
            # If parse fails, do not hard-fail; treat as valid.
            pass

    recipe = row.get("recipe") or {}
    return {"success": True, "recipe": recipe, "share_id": row.get("id")}


@router.delete("/shared/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_shared_recipe(
    share_id: str,
    user_id: str = Depends(get_current_user),
):
    """Revoke (delete) a previously created share link.

    Only the owner of the share may revoke it.
    """

    supabase = get_db_client()
    try:
        result = (
            supabase.table("shared_recipes")
            .select("id,owner_user_id")
            .eq("id", share_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load share: {e}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Shared recipe not found")

    row = result.data[0]
    owner_user_id = str(row.get("owner_user_id") or "")
    if owner_user_id != str(user_id):
        raise HTTPException(status_code=403, detail="Not allowed to revoke this share")

    try:
        supabase.table("shared_recipes").delete().eq("id", share_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke share: {e}")

    return None


@public_router.get("/r/{share_id}", response_class=HTMLResponse)
async def shared_recipe_page(share_id: str):
    """Simple shareable recipe page (public HTML)."""

    try:
        data = await get_shared_recipe(share_id)
        recipe = data.get("recipe") or {}
    except HTTPException as e:
        title = "Shared Recipe"
        if e.status_code == 410:
            message = "This shared recipe link has expired."
        elif e.status_code == 404:
            message = "This shared recipe link was not found."
        else:
            message = "Could not load this shared recipe."

        body = f"""<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{_html.escape(title)} - SAVO</title>
    <style>
        body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #0b0b0c; color: #f2f2f3; }}
        .wrap {{ max-width: 820px; margin: 0 auto; padding: 24px; }}
        h1 {{ margin: 0 0 8px; font-size: 24px; }}
        .sub {{ opacity: .8; margin-bottom: 16px; }}
        .card {{ background: rgba(255,255,255,.06); border-radius: 12px; padding: 16px; margin: 16px 0; }}
        a {{ color: #9fd3ff; }}
    </style>
</head>
<body>
    <div class=\"wrap\">
        <h1>{_html.escape(title)}</h1>
        <div class=\"sub\">Shared via SAVO</div>
        <div class=\"card\">{_html.escape(message)}</div>
    </div>
</body>
</html>"""

    return HTMLResponse(content=body, status_code=e.status_code)

    def esc(v: Any) -> str:
        return _html.escape(str(v or ""))

    name = recipe.get("recipe_name") or {}
    title = esc((name.get("en") if isinstance(name, dict) else str(name)) or "Shared Recipe")

    ingredients = recipe.get("ingredients_used") or []
    steps = recipe.get("steps") or []

    ing_items = []
    if isinstance(ingredients, list):
        for it in ingredients:
            if not isinstance(it, dict):
                continue
            canonical = esc(it.get("canonical_name"))
            amt = it.get("amount")
            unit = esc(it.get("unit"))
            amt_txt = esc(amt) if amt is not None else ""
            line = (f"{amt_txt} {unit} {canonical}").strip()
            if line:
                ing_items.append(f"<li>{line}</li>")

    step_items = []
    if isinstance(steps, list):
        for s in steps:
            if not isinstance(s, dict):
                continue
            instr = s.get("instruction") or {}
            text = ""
            if isinstance(instr, dict):
                text = instr.get("en") or next(iter(instr.values()), "")
            else:
                text = str(instr)
            text = esc(text)
            if text:
                step_items.append(f"<li>{text}</li>")

    body = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title} - SAVO</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #0b0b0c; color: #f2f2f3; }}
    .wrap {{ max-width: 820px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    .sub {{ opacity: .8; margin-bottom: 16px; }}
    .card {{ background: rgba(255,255,255,.06); border-radius: 12px; padding: 16px; margin: 16px 0; }}
    a {{ color: #9fd3ff; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>{title}</h1>
    <div class=\"sub\">Shared via SAVO</div>

    <div class=\"card\">
      <h2 style=\"margin-top:0\">Ingredients</h2>
      <ul>{''.join(ing_items) if ing_items else '<li>(No ingredients listed)</li>'}</ul>
    </div>

    <div class=\"card\">
      <h2 style=\"margin-top:0\">Steps</h2>
      <ol>{''.join(step_items) if step_items else '<li>(No steps listed)</li>'}</ol>
    </div>

    <div class=\"sub\">Tip: if you have the SAVO app, open this link there for the full experience.</div>
  </div>
</body>
</html>"""

    return HTMLResponse(content=body)


@router.post("/import/image")
async def import_recipe_from_image(
    image: UploadFile = File(..., description="Image file (JPEG/PNG)"),
    output_language: str = Form(default="en"),
    secondary_language: Optional[str] = Form(default=None),
    user_id: str = Depends(get_current_user),
):
    """Import a recipe from an image (photo/screenshot) using vision + structured extraction."""
    _ = user_id

    if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
        raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")

    image_data = await image.read()
    if len(image_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")

    # Vision extraction via OpenAI directly (image_url content)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured for image recipe import")

    client = AsyncOpenAI(api_key=api_key)

    schema = _recipe_schema()
    prompt = (
        "Extract ONE recipe from this image (it may be a cookbook page, a website screenshot, or a recipe card). "
        "Return JSON ONLY matching the provided schema. "
        "If a value is unknown, use a reasonable default. "
        "Use inventory_id as empty string for each ingredient. "
        "Ensure instructions are clear and step numbers start at 1."
    )

    import base64

    b64 = base64.b64encode(image_data).decode("utf-8")
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You MUST return a JSON object that EXACTLY matches this schema structure:\n{json.dumps(schema)}"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=2000,
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            recipe = json.loads(cleaned)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                raise ValueError("No JSON object found in model output")
            recipe = json.loads(match.group(0))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import recipe from image: {e}")

    recipe["recipe_id"] = recipe.get("recipe_id") or str(uuid4())
    recipe = await _translate_recipe_fields(recipe=recipe, target_language=secondary_language or "")
    return {"recipe": recipe}


class RecipeImageRequest(BaseModel):
    """Request for recipe image URL"""
    recipe_name: str = Field(..., description="Recipe name to generate image for")
    cuisine: str = Field(default="general", description="Cuisine type")


class RecipeImageResponse(BaseModel):
    """Response with recipe image URL"""
    recipe_name: str
    image_url: str
    source: str = Field(default="unsplash", description="Image source provider")


@router.post("/image", response_model=RecipeImageResponse)
async def get_recipe_image(req: RecipeImageRequest):
    """
    Get a recipe image URL from Unsplash (free, no API key needed)
    
    Alternative sources:
    - Unsplash: Free, high-quality food photos (used here)
    - Pexels: Free, requires API key
    - Pixabay: Free, simple API
    - DALL-E 3: $0.04/image, OpenAI API (best quality, custom generated)
    """
    try:
        # Use Unsplash Source API (no key required for basic usage)
        # Format: https://source.unsplash.com/featured/?food,pasta,italian
        
        # Clean recipe name for search query
        query_parts = [
            "food",
            req.cuisine.lower() if req.cuisine != "general" else "",
            req.recipe_name.lower().replace(" ", ",")
        ]
        query = ",".join(p for p in query_parts if p)
        
        # Unsplash featured random image (1200x800)
        image_url = f"https://source.unsplash.com/1200x800/?{query}"
        
        # Alternative: Use Unsplash API for consistent images
        # This requires an access key but gives better control
        # For production, consider using:
        # - Unsplash API with access key (free tier: 50 req/hour)
        # - Cache image URLs in database to avoid repeated lookups
        # - Pre-generate images for common recipes
        
        return RecipeImageResponse(
            recipe_name=req.recipe_name,
            image_url=image_url,
            source="unsplash"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate image: {str(e)}"
        )


@router.get("/image/{recipe_name}")
async def get_recipe_image_by_name(recipe_name: str, cuisine: str = "general"):
    """Get recipe image by name (GET endpoint for convenience)"""
    req = RecipeImageRequest(recipe_name=recipe_name, cuisine=cuisine)
    return await get_recipe_image(req)
