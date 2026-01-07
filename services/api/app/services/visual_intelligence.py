"""
Visual Intelligence Service
Handles ingredient identification using GPT-4 Vision, visual feature extraction, and similarity search
"""

import os
import base64
import io
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from PIL import Image
import numpy as np
from openai import AsyncOpenAI

@dataclass
class VisualFeatures:
    """Visual features extracted from image"""
    dominant_colors: List[str]
    color_histogram: Dict[str, float]
    texture_description: str
    shape_features: List[str]
    brightness: float
    contrast: float

@dataclass
class IngredientMatch:
    """Single ingredient match result"""
    ingredient_id: str
    canonical_name: str
    confidence: float
    reasoning: str
    visual_similarity: float

@dataclass
class IdentificationResult:
    """Complete identification result"""
    top_matches: List[IngredientMatch]
    visual_features: VisualFeatures
    detected_state: str  # raw_whole, sliced, powdered, cooked
    confidence_score: float
    processing_time_ms: int
    model_version: str

class VisualIntelligenceService:
    """Service for visual ingredient intelligence using GPT-4 Vision"""
    
    def __init__(self, openai_api_key: str = None):
        """Initialize with OpenAI API key"""
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model_version = "gpt-4-vision-preview"
    
    async def identify_ingredient(
        self,
        image_data: bytes,
        context: Optional[Dict] = None
    ) -> IdentificationResult:
        """
        Identify ingredient from image using GPT-4 Vision
        
        Args:
            image_data: Image bytes (JPEG, PNG, WebP)
            context: Optional context (user_location, cuisine_preference, etc.)
        
        Returns:
            IdentificationResult with top matches and visual features
        """
        import time
        start_time = time.time()
        
        # Extract visual features
        visual_features = await self._extract_visual_features(image_data)
        
        # Prepare image for GPT-4 Vision
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Build prompt with context
        prompt = self._build_identification_prompt(visual_features, context)
        
        # Call GPT-4 Vision
        response = await self.client.chat.completions.create(
            model=self.model_version,
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
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.2  # Low temperature for consistent results
        )
        
        # Parse response
        result_text = response.choices[0].message.content
        matches = self._parse_identification_response(result_text)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return IdentificationResult(
            top_matches=matches,
            visual_features=visual_features,
            detected_state=self._detect_state(visual_features, result_text),
            confidence_score=matches[0].confidence if matches else 0.0,
            processing_time_ms=processing_time,
            model_version=self.model_version
        )
    
    async def _extract_visual_features(self, image_data: bytes) -> VisualFeatures:
        """Extract visual features from image using PIL"""
        
        # Load image
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize for processing
        image.thumbnail((800, 800))
        
        # Extract dominant colors
        dominant_colors = self._extract_dominant_colors(image)
        
        # Calculate color histogram
        color_histogram = self._calculate_color_histogram(image)
        
        # Calculate brightness and contrast
        brightness, contrast = self._calculate_brightness_contrast(image)
        
        # Texture description (simplified)
        texture = self._analyze_texture(image)
        
        return VisualFeatures(
            dominant_colors=dominant_colors,
            color_histogram=color_histogram,
            texture_description=texture,
            shape_features=[],  # TODO: Implement shape detection
            brightness=brightness,
            contrast=contrast
        )
    
    def _extract_dominant_colors(self, image: Image.Image, num_colors: int = 3) -> List[str]:
        """Extract dominant colors using k-means clustering"""
        from sklearn.cluster import KMeans
        
        # Resize for faster processing
        small_image = image.copy()
        small_image.thumbnail((100, 100))
        
        # Convert to numpy array
        pixels = np.array(small_image).reshape(-1, 3)
        
        # K-means clustering
        kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        # Get cluster centers (dominant colors)
        colors = kmeans.cluster_centers_.astype(int)
        
        # Convert to color names
        color_names = [self._rgb_to_color_name(tuple(color)) for color in colors]
        
        return color_names
    
    def _rgb_to_color_name(self, rgb: Tuple[int, int, int]) -> str:
        """Convert RGB to color name (simplified)"""
        r, g, b = rgb
        
        # Simplified color mapping
        if r > 200 and g > 200 and b > 200:
            return "white"
        elif r < 50 and g < 50 and b < 50:
            return "black"
        elif r > g and r > b:
            if r > 150:
                return "red"
            else:
                return "brown"
        elif g > r and g > b:
            return "green"
        elif b > r and b > g:
            return "blue"
        elif r > 150 and g > 150:
            if b < 100:
                return "yellow"
            else:
                return "white"
        elif r > 100 and g > 50 and b < 50:
            return "orange"
        else:
            return "brown"
    
    def _calculate_color_histogram(self, image: Image.Image) -> Dict[str, float]:
        """Calculate color distribution"""
        # Convert to numpy array
        pixels = np.array(image)
        
        # Simple histogram by channel
        r_mean = np.mean(pixels[:, :, 0]) / 255.0
        g_mean = np.mean(pixels[:, :, 1]) / 255.0
        b_mean = np.mean(pixels[:, :, 2]) / 255.0
        
        return {
            "red": float(r_mean),
            "green": float(g_mean),
            "blue": float(b_mean)
        }
    
    def _calculate_brightness_contrast(self, image: Image.Image) -> Tuple[float, float]:
        """Calculate brightness and contrast"""
        # Convert to grayscale
        grayscale = image.convert('L')
        pixels = np.array(grayscale)
        
        brightness = float(np.mean(pixels) / 255.0)
        contrast = float(np.std(pixels) / 255.0)
        
        return brightness, contrast
    
    def _analyze_texture(self, image: Image.Image) -> str:
        """Analyze texture (simplified)"""
        # Convert to grayscale
        grayscale = image.convert('L')
        pixels = np.array(grayscale)
        
        # Calculate variance (texture roughness indicator)
        variance = np.var(pixels)
        
        if variance < 500:
            return "smooth"
        elif variance < 2000:
            return "slightly_textured"
        elif variance < 5000:
            return "textured"
        else:
            return "rough"
    
    def _build_identification_prompt(
        self,
        visual_features: VisualFeatures,
        context: Optional[Dict]
    ) -> str:
        """Build prompt for GPT-4 Vision"""
        
        prompt = f"""You are an expert ingredient identification system for a food inventory app.

Analyze this ingredient image and identify it precisely.

Visual features detected:
- Dominant colors: {', '.join(visual_features.dominant_colors)}
- Texture: {visual_features.texture_description}
- Brightness: {visual_features.brightness:.2f}

Instructions:
1. Identify the ingredient (be specific: "Turmeric Root" not just "Spice")
2. Determine the state (raw_whole, raw_cut, powdered, cooked, etc.)
3. Provide confidence score (0-100)
4. Explain your reasoning
5. List up to 3 possible matches if unsure

Format your response as:
INGREDIENT: <name>
STATE: <state>
CONFIDENCE: <score>
REASONING: <explanation>
ALTERNATIVES: <alt1>, <alt2>, <alt3> (if applicable)

Example:
INGREDIENT: Turmeric Root
STATE: raw_whole
CONFIDENCE: 95
REASONING: Bright yellow-orange color, knobby finger-like shape, rough texture typical of fresh turmeric rhizome
ALTERNATIVES: Ginger Root (lighter color, smoother texture)

Context: {context if context else 'None provided'}
"""
        
        return prompt
    
    def _parse_identification_response(self, response: str) -> List[IngredientMatch]:
        """Parse GPT-4 Vision response into matches"""
        
        matches = []
        
        # Parse primary match
        lines = response.strip().split('\n')
        ingredient_name = ""
        confidence = 0.0
        reasoning = ""
        
        for line in lines:
            if line.startswith("INGREDIENT:"):
                ingredient_name = line.replace("INGREDIENT:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip()) / 100.0
                except:
                    confidence = 0.8
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()
        
        if ingredient_name:
            matches.append(IngredientMatch(
                ingredient_id="",  # Will be filled by service layer
                canonical_name=ingredient_name,
                confidence=confidence,
                reasoning=reasoning,
                visual_similarity=confidence
            ))
        
        # TODO: Parse alternatives if present
        
        return matches
    
    def _detect_state(self, visual_features: VisualFeatures, response_text: str) -> str:
        """Detect ingredient state from response"""
        state_keywords = {
            "raw_whole": ["whole", "intact", "uncut", "fresh"],
            "raw_cut": ["sliced", "diced", "chopped", "cut"],
            "powdered": ["powder", "ground", "dust"],
            "cooked": ["cooked", "roasted", "fried", "boiled"]
        }
        
        response_lower = response_text.lower()
        
        for state, keywords in state_keywords.items():
            if any(keyword in response_lower for keyword in keywords):
                return state
        
        return "raw_whole"  # Default
    
    async def extract_visual_signature(self, image_data: bytes) -> Dict:
        """Extract complete visual signature for similarity search"""
        features = await self._extract_visual_features(image_data)
        
        return {
            "dominant_colors": features.dominant_colors,
            "color_histogram": features.color_histogram,
            "texture": features.texture_description,
            "brightness": features.brightness,
            "contrast": features.contrast
        }
    
    async def find_visually_similar(
        self,
        target_features: VisualFeatures,
        candidate_features: List[Tuple[str, VisualFeatures]],
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Find visually similar ingredients
        
        Args:
            target_features: Features of target ingredient
            candidate_features: List of (ingredient_id, features) tuples
            limit: Maximum number of results
        
        Returns:
            List of (ingredient_id, similarity_score) tuples
        """
        similarities = []
        
        for ingredient_id, features in candidate_features:
            similarity = self._calculate_similarity(target_features, features)
            similarities.append((ingredient_id, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:limit]
    
    def _calculate_similarity(
        self,
        features1: VisualFeatures,
        features2: VisualFeatures
    ) -> float:
        """Calculate similarity score between two visual feature sets"""
        
        # Color similarity (dominant colors overlap)
        color_overlap = len(set(features1.dominant_colors) & set(features2.dominant_colors))
        color_score = color_overlap / max(len(features1.dominant_colors), len(features2.dominant_colors))
        
        # Histogram similarity (euclidean distance)
        hist1 = np.array([features1.color_histogram.get(c, 0) for c in ['red', 'green', 'blue']])
        hist2 = np.array([features2.color_histogram.get(c, 0) for c in ['red', 'green', 'blue']])
        hist_distance = np.linalg.norm(hist1 - hist2)
        hist_score = 1.0 - min(hist_distance, 1.0)
        
        # Texture similarity
        texture_score = 1.0 if features1.texture_description == features2.texture_description else 0.5
        
        # Brightness/contrast similarity
        brightness_diff = abs(features1.brightness - features2.brightness)
        contrast_diff = abs(features1.contrast - features2.contrast)
        tone_score = 1.0 - (brightness_diff + contrast_diff) / 2.0
        
        # Weighted average
        total_score = (
            color_score * 0.4 +
            hist_score * 0.3 +
            texture_score * 0.2 +
            tone_score * 0.1
        )
        
        return float(total_score)
