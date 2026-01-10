"""
Vision API Integration for Ingredient Detection
Uses OpenAI GPT-4 Vision to analyze pantry/fridge images and detect ingredients
"""

import os
import base64
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import json
import logging
from io import BytesIO

from openai import AsyncOpenAI
from PIL import Image
from PIL import ImageEnhance, ImageOps
import hashlib

logger = logging.getLogger(__name__)


class VisionAPIClient:
    """Client for Vision API ingredient detection"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Allow overriding to support auditability and controlled rollouts.
        self.model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
        
        # Confidence thresholds
        self.HIGH_CONFIDENCE = Decimal("0.80")
        self.MEDIUM_CONFIDENCE = Decimal("0.50")
        
    async def analyze_image(
        self,
        image_data: bytes,
        scan_type: str = "pantry",
        location_hint: Optional[str] = None,
        user_preferences: Optional[Dict] = None,
        barcode: Optional[str] = None,
        barcode_name_hint: Optional[str] = None,
        barcode_quantity_hint: Optional[float] = None,
        barcode_unit_hint: Optional[str] = None,
    ) -> Dict:
        """
        Analyze image and detect ingredients with confidence scores
        
        Args:
            image_data: Raw image bytes
            scan_type: "pantry", "fridge", "counter", etc.
            location_hint: Optional hint about location
            user_preferences: Optional user profile data for context
            
        Returns:
            {
                "success": bool,
                "ingredients": [
                    {
                        "detected_name": str,
                        "confidence": Decimal,
                        "category": str,
                        "bbox": {x, y, width, height},
                        "close_alternatives": [{name, likelihood, reason}],
                        "visual_similarity_group": str
                    }
                ],
                "metadata": {
                    "image_hash": str,
                    "image_size": tuple,
                    "processing_time_ms": int
                }
            }
        """
        import time
        start_time = time.time()
        
        try:
            # Validate image
            image_hash, image_size = self._process_image(image_data)
            
            # Build prompt
            prompt = self._build_detection_prompt(
                scan_type,
                location_hint,
                user_preferences,
                barcode=barcode,
                barcode_name_hint=barcode_name_hint,
                barcode_quantity_hint=barcode_quantity_hint,
                barcode_unit_hint=barcode_unit_hint,
            )
            
            # Encode image for API
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Call OpenAI Vision API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"  # High resolution for better detection
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.3  # Lower temp for more deterministic results
            )
            
            # Parse response
            content = response.choices[0].message.content
            detected_data = self._parse_detection_response(content)
            
            # Calculate confidence scores and close alternatives
            ingredients = []
            for item in detected_data.get("ingredients", []):
                ingredient = self._enrich_detection(item, user_preferences)
                ingredients.append(ingredient)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                "success": True,
                "ingredients": ingredients,
                "metadata": {
                    "image_hash": image_hash,
                    "image_size": image_size,
                    "processing_time_ms": processing_time,
                    "total_detected": len(ingredients),
                    "high_confidence_count": sum(1 for i in ingredients if i["confidence"] >= self.HIGH_CONFIDENCE),
                    "medium_confidence_count": sum(1 for i in ingredients if self.MEDIUM_CONFIDENCE <= i["confidence"] < self.HIGH_CONFIDENCE),
                    "low_confidence_count": sum(1 for i in ingredients if i["confidence"] < self.MEDIUM_CONFIDENCE)
                }
            }
            
        except Exception as e:
            logger.error(f"Vision API analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "ingredients": []
            }

    async def analyze_receipt(
        self,
        image_data: bytes,
        user_preferences: Optional[Dict] = None,
    ) -> Dict:
        """Analyze a receipt image and extract purchased grocery items.

        Returns:
            {
                "success": bool,
                "items": [
                    {
                        "raw_name": str,
                        "canonical_name": str,
                        "quantity": Optional[float],
                        "unit": Optional[str],
                        "confidence": Decimal,
                        "raw_line": Optional[str],
                    }
                ],
                "metadata": {...}
            }
        """
        import time

        start_time = time.time()

        try:
            image_hash, image_size = self._process_image(image_data)

            # Preprocess receipts to improve OCR robustness (contrast/rotation/scale).
            try:
                processed_image_data = self._preprocess_receipt_image(image_data)
            except Exception:
                processed_image_data = image_data

            prompt = """You are an expert receipt-parsing AI for SAVO, a cooking assistant app.

TASK: Read this grocery receipt image and extract ALL line-items that look like grocery/food products.

GOAL:
- Be comprehensive. If you are unsure about an item, STILL include it with low confidence.

RULES:
- Ignore store header/address, cashier info, loyalty messages, payment details, totals, taxes, fees.
- Ignore coupons/discount lines.
- Prefer including ambiguous abbreviations as-is in `name` rather than dropping them.
- Non-food items should be excluded when clearly non-food.
- Quantity:
    - If explicitly present (e.g., "2x", weights), include it.
    - If not explicit, set quantity to 1 and unit to "pieces".

OUTPUT (JSON only):
{
    "raw_text": "(best-effort full OCR transcription of the receipt)",
    "items": [
        {
            "raw_line": "string", 
            "name": "string",
            "quantity": 1.0,
            "unit": "pieces|pounds|ounces|grams|kilograms|liters|milliliters",
            "confidence": 0.0
        }
    ]
}
"""

            base64_image = base64.b64encode(processed_image_data).decode("utf-8")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=2400,
                temperature=0.0,
            )

            content = response.choices[0].message.content
            parsed = self._parse_detection_response(content)

            raw_text = None
            if isinstance(parsed, dict) and parsed.get("raw_text"):
                raw_text = str(parsed.get("raw_text"))

            from .ingredient_normalization import IngredientNormalizer

            normalizer = IngredientNormalizer()

            items_out = []
            for item in (parsed.get("items") or []):
                if not isinstance(item, dict):
                    continue

                raw_name = (item.get("name") or "").strip()
                if not raw_name:
                    continue

                canonical_name = normalizer.normalize_name(raw_name)
                if not canonical_name:
                    continue

                qty = item.get("quantity")
                unit = item.get("unit")

                conf_val = item.get("confidence", 0.0)
                try:
                    confidence = Decimal(str(conf_val))
                except Exception:
                    confidence = Decimal("0")

                items_out.append(
                    {
                        "raw_name": raw_name,
                        "canonical_name": canonical_name,
                        "quantity": qty,
                        "unit": unit,
                        "confidence": confidence,
                        "raw_line": item.get("raw_line"),
                    }
                )

            processing_time = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "items": items_out,
                "raw_text": raw_text,
                "metadata": {
                    "image_hash": image_hash,
                    "image_size": image_size,
                    "processing_time_ms": processing_time,
                    "total_items_detected": len(items_out),
                },
            }
        except Exception as e:
            logger.error(f"Receipt analysis failed: {e}")
            return {"success": False, "error": str(e), "items": []}

    def _preprocess_receipt_image(self, image_data: bytes) -> bytes:
        """Improve receipt OCR by normalizing orientation, boosting contrast, and upscaling."""

        image = Image.open(BytesIO(image_data))
        image = ImageOps.exif_transpose(image)

        # Convert to grayscale for OCR and enhance contrast/sharpness.
        image = image.convert("L")
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(1.6)
        image = ImageEnhance.Sharpness(image).enhance(1.3)

        # Upscale modestly (helps small receipt fonts).
        w, h = image.size
        scale = 1.6
        image = image.resize((int(w * scale), int(h * scale)))

        out = BytesIO()
        image.save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue()
    
    def _process_image(self, image_data: bytes) -> Tuple[str, Tuple[int, int]]:
        """
        Validate and process image, return hash and dimensions
        """
        try:
            # Open image
            image = Image.open(BytesIO(image_data))
            
            # Get dimensions
            size = image.size
            
            # Calculate hash for deduplication
            image_hash = hashlib.sha256(image_data).hexdigest()
            
            return image_hash, size
            
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise ValueError(f"Invalid image data: {e}")
    
    def _build_detection_prompt(
        self,
        scan_type: str,
        location_hint: Optional[str],
        user_preferences: Optional[Dict],
        barcode: Optional[str] = None,
        barcode_name_hint: Optional[str] = None,
        barcode_quantity_hint: Optional[float] = None,
        barcode_unit_hint: Optional[str] = None,
    ) -> str:
        """
        Build prompt for Vision API with context
        """
        prompt = f"""You are an expert ingredient detection AI for SAVO, a cooking assistant app.

TASK: Analyze this {scan_type} image and identify ALL visible food ingredients and items.

DETECTION REQUIREMENTS:
1. List EVERY ingredient you can see clearly
2. Provide confidence score (0.0 to 1.0) for each detection
3. Use common grocery names (e.g., "eggs" not "chicken eggs")
4. Include category: protein/vegetable/fruit/dairy/grain/spice/condiment/beverage/other
5. Detect BOTH packaged goods and loose items (produce, grains, pulses, spices)
6. For each item, set item_form: packaged|loose|unknown
7. For uncertain items: suggest 2-3 close alternatives
8. **EXTRACT QUANTITIES** from package labels, nutrition labels, or visible text
9. **COUNT** items if countable (e.g., "3 apples", "2 cans")
10. **ESTIMATE** quantities if no label visible

QUANTITY DETECTION RULES:
- Read package labels: "16 oz", "500g", "2 lbs", "1 gallon", "250 ml"
- Count visible items: apples, tomatoes, eggs, cans, bottles
- For bulk items without labels: estimate based on container size if visible
- Provide quantity_confidence (0.0-1.0): how sure you are about the quantity
- If no quantity visible: set quantity to null

CONFIDENCE GUIDELINES:
- 0.90-1.00: Absolutely certain (clear label, distinctive shape)
- 0.70-0.89: Very confident (typical packaging, clear characteristics)
- 0.50-0.69: Somewhat confident (partially visible, common item)
- 0.30-0.49: Uncertain (poor lighting, obscured, generic container)
- 0.00-0.29: Guess (very unclear, need user confirmation)

RESPONSE FORMAT (JSON):
{{
  "ingredients": [
    {{
      "detected_name": "ingredient name",
      "confidence": 0.85,
      "category": "vegetable",
            "item_form": "packaged|loose|unknown",
      "reason": "why you're confident/uncertain",
      "quantity": 500,
      "unit": "grams",
      "quantity_confidence": 0.90,
      "quantity_source": "package_label|count|estimate",
      "close_alternatives": [
        {{"name": "similar_item", "likelihood": "high/medium/low", "reason": "why similar"}}
      ]
    }}
  ],
  "image_quality": "excellent/good/fair/poor",
  "visibility_issues": ["glare", "shadows", "partial_view"],
  "total_items_detected": 5
}}

"""
        
        # Add location context
        if location_hint:
            prompt += f"\nLOCATION CONTEXT: User indicated this is from '{location_hint}'\n"

        # Optional barcode context (best-effort).
        bc = (barcode or "").strip()
        bcn = (barcode_name_hint or "").strip()
        if bc or bcn or barcode_quantity_hint is not None:
            prompt += "\nBARCODE CONTEXT (OPTIONAL):\n"
            if bc:
                prompt += f"- A barcode was scanned: {bc}\n"
            if bcn:
                prompt += f"- Barcode lookup suggests product name: {bcn}\n"
            if barcode_quantity_hint is not None:
                bu = (barcode_unit_hint or "").strip() or "unknown"
                prompt += f"- Barcode lookup suggests net quantity: {barcode_quantity_hint} {bu}\n"
            prompt += "INSTRUCTIONS: Use barcode hints only if you can visually match a packaged item in the image. If the barcode hints do not match what you see, ignore them and rely on the image.\n"
        
        # Add user context (cuisine preferences can help)
        if user_preferences:
            cuisines = user_preferences.get("favorite_cuisines", [])
            if cuisines:
                prompt += f"\nUSER CONTEXT: User enjoys {', '.join(cuisines)} cuisine (may have related ingredients)\n"
        
        prompt += "\nIMPORTANT: Be thorough but honest about confidence. It's better to mark as uncertain than to misidentify.\n"
        
        return prompt
    
    def _parse_detection_response(self, response_text: str) -> Dict:
        """
        Parse JSON response from Vision API
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            data = json.loads(json_str)
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Vision API response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            
            # Fallback: Try to extract ingredients manually
            return {"ingredients": [], "error": "parse_failed"}
    
    def _enrich_detection(
        self,
        item: Dict,
        user_preferences: Optional[Dict]
    ) -> Dict:
        """
        Enrich detection with visual similarity groups and additional metadata
        """
        from .ingredient_normalization import IngredientNormalizer
        
        normalizer = IngredientNormalizer()
        
        detected_name = (item.get("detected_name") or item.get("name") or "")
        if isinstance(detected_name, str):
            detected_name = detected_name.strip()
        confidence = Decimal(str(item.get("confidence", 0.0)))
        
        # Extract quantity information
        quantity = item.get("quantity")
        unit = item.get("unit")
        quantity_confidence = item.get("quantity_confidence", 0.0) if quantity else None
        quantity_source = item.get("quantity_source", "")

        # Packaged vs loose (best-effort)
        item_form = item.get("item_form")
        if isinstance(item_form, str):
            item_form = item_form.strip().lower()
        else:
            item_form = None

        if item_form not in {"packaged", "loose", "unknown"}:
            # Heuristic fallback if the model didn't provide it.
            qs = (quantity_source or "").strip().lower()
            cat = (item.get("category") or "other").strip().lower()
            if qs == "package_label":
                item_form = "packaged"
            elif cat in {"vegetable", "fruit"}:
                item_form = "loose"
            elif cat in {"grain", "spice"} and qs in {"estimate", "count", ""}:
                item_form = "loose"
            else:
                item_form = "unknown"
        
        # Normalize ingredient name
        canonical_name = normalizer.normalize_name(detected_name) if detected_name else ""
        
        # Get visual similarity group
        similarity_group = normalizer.get_visual_similarity_group(canonical_name)
        
        # Get close alternatives if confidence is medium
        close_alternatives = []
        if self.MEDIUM_CONFIDENCE <= confidence < self.HIGH_CONFIDENCE:
            # Use provided alternatives or generate them
            provided_alternatives = item.get("close_alternatives", [])
            if provided_alternatives:
                close_alternatives = provided_alternatives
            else:
                # Generate from similarity group
                close_alternatives = normalizer.get_close_ingredients(
                    canonical_name,
                    user_preferences=user_preferences
                )
        
        # Check for allergen warnings (if user preferences provided)
        allergen_warnings = []
        if user_preferences:
            allergen_warnings = self._check_allergen_warnings(
                canonical_name,
                user_preferences
            )
        
        return {
            "detected_name": detected_name,
            "canonical_name": canonical_name,
            "confidence": confidence,
            "category": item.get("category", "other"),
            "item_form": item_form,
            "reason": item.get("reason", ""),
            "quantity": quantity,
            "unit": unit,
            "quantity_confidence": quantity_confidence,
            "quantity_source": quantity_source,
            "close_alternatives": close_alternatives,
            "visual_similarity_group": similarity_group,
            "allergen_warnings": allergen_warnings,
            "bbox": item.get("bbox")  # Bounding box if available
        }
    
    def _check_allergen_warnings(
        self,
        ingredient_name: str,
        user_preferences: Dict
    ) -> List[Dict]:
        """
        Check if ingredient triggers any allergen warnings
        """
        warnings = []
        
        # Get user's allergens from all family members
        all_allergens = set()
        for member in user_preferences.get("members", []):
            allergens = member.get("allergens", [])
            all_allergens.update(allergens)
        
        if not all_allergens:
            return warnings
        
        # Check each allergen
        ingredient_lower = ingredient_name.lower()
        
        # Allergen keyword mapping
        allergen_keywords = {
            "dairy": ["milk", "cheese", "butter", "cream", "yogurt", "whey", "casein"],
            "eggs": ["egg"],
            "peanuts": ["peanut"],
            "tree_nuts": ["almond", "walnut", "cashew", "pistachio", "pecan", "hazelnut"],
            "soy": ["soy", "tofu", "edamame"],
            "wheat": ["wheat", "flour", "bread"],
            "fish": ["fish", "salmon", "tuna", "cod"],
            "shellfish": ["shrimp", "crab", "lobster", "clam", "mussel"],
            "sesame": ["sesame", "tahini"]
        }
        
        for allergen in all_allergens:
            allergen_lower = allergen.lower()
            keywords = allergen_keywords.get(allergen_lower, [allergen_lower])
            
            for keyword in keywords:
                if keyword in ingredient_lower:
                    warnings.append({
                        "allergen": allergen,
                        "severity": "critical",
                        "message": f"Contains {allergen} (declared allergen for your household)"
                    })
                    break
        
        return warnings
    
    async def estimate_api_cost(self, image_data: bytes) -> int:
        """
        Estimate API cost in cents for processing this image
        
        Returns:
            Cost in cents
        """
        # OpenAI GPT-4 Vision pricing (as of 2024):
        # - $0.01 per image (detail: high)
        # - Plus token costs
        
        # Rough estimate: 1 cent per image + 0.5 cents for tokens
        return 2  # 2 cents per scan
    
    def get_confidence_category(self, confidence: Decimal) -> str:
        """
        Categorize confidence level
        """
        if confidence >= self.HIGH_CONFIDENCE:
            return "high"
        elif confidence >= self.MEDIUM_CONFIDENCE:
            return "medium"
        else:
            return "low"
    
    async def analyze_single_item(
        self,
        image_data: bytes,
        scan_type: str = "pantry",
        user_preferences: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze image containing a SINGLE ingredient (optimized for continuous scanning)
        
        Args:
            image_data: Raw image bytes
            scan_type: "pantry", "fridge", etc.
            user_preferences: Optional user profile for context
            
        Returns:
            {
                "success": bool,
                "ingredient": {...},
                "metadata": {...}
            }
        """
        try:
            import time
            start_time = time.time()
            
            # Calculate image hash for deduplication
            image_hash = hashlib.sha256(image_data).hexdigest()
            
            # Get image dimensions
            image = Image.open(BytesIO(image_data))
            image_size = image.size
            
            # Encode image
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Build optimized prompt for SINGLE item
            prompt = f"""Analyze this image containing a SINGLE food ingredient or grocery item.

Focus ONLY on the main centered item in the image.

Return a JSON object with:
{{
  "name": "ingredient name (simple, canonical)",
  "confidence": 0.0-1.0,
  "category": "vegetable|fruit|grain|protein|dairy|spice|condiment|beverage|other",
  "quantity": number or null,
  "unit": "grams|ml|pieces|kg|lbs|oz|cups|tbsp|tsp" or null
}}

Extract quantity ONLY if clearly visible on a label. Otherwise return null.
Use confidence 0.9+ if very clear, 0.7-0.9 if somewhat clear, below 0.7 if uncertain.

Example response:
{{"name": "milk", "confidence": 0.95, "category": "dairy", "quantity": 1000, "unit": "ml"}}

Return ONLY the JSON object, no other text."""
            
            # Call Vision API with optimized settings for speed
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Faster, cheaper model for single items
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "low"  # Low detail for speed
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300,  # Much smaller for single item
                temperature=0.2
            )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            
            # Extract JSON (handle potential markdown formatting)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            detected = json.loads(content)

            # The single-item prompt asks for `name`, but the rest of the pipeline
            # expects `detected_name`.
            if isinstance(detected, dict):
                if "detected_name" not in detected and "name" in detected:
                    detected["detected_name"] = detected.get("name")
                dn = detected.get("detected_name")
                if isinstance(dn, str):
                    detected["detected_name"] = dn.strip()

            # Guardrail: don't return empty/unknown junk items.
            dn_val = detected.get("detected_name") if isinstance(detected, dict) else None
            if not isinstance(dn_val, str) or not dn_val.strip() or dn_val.strip().lower() in {"unknown", "n/a", "na"}:
                raise ValueError("Could not confidently identify single item")
            
            # Enrich with additional data
            ingredient = self._enrich_detection(detected, user_preferences)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                "success": True,
                "ingredient": ingredient,
                "metadata": {
                    "image_hash": image_hash,
                    "image_size": image_size,
                    "processing_time_ms": processing_time,
                    "model": "gpt-4o-mini"
                }
            }
            
        except Exception as e:
            logger.error(f"Single-item vision analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "ingredient": None
            }


# Singleton instance
_vision_client = None

def get_vision_client() -> VisionAPIClient:
    """Get or create Vision API client singleton"""
    global _vision_client
    if _vision_client is None:
        _vision_client = VisionAPIClient()
    return _vision_client
