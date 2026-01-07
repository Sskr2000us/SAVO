"""Image processing utilities for ingredient thumbnails and visual verification."""

import io
import hashlib
from typing import Optional, Tuple, Dict
from PIL import Image, ImageDraw, ImageFont
import logging

from app.core.media_storage import upload_file_to_storage

logger = logging.getLogger(__name__)


class IngredientImageProcessor:
    """Process and crop ingredient images for visual verification."""
    
    # Thumbnail configuration
    THUMBNAIL_SIZE = (200, 200)  # Square thumbnails for consistency
    THUMBNAIL_QUALITY = 85
    THUMBNAIL_FORMAT = "JPEG"
    
    # Badge configuration
    CONFIDENCE_COLORS = {
        "high": "#10B981",     # Green
        "medium": "#F59E0B",   # Orange
        "low": "#EF4444"       # Red
    }
    
    @staticmethod
    def crop_ingredient_thumbnail(
        image_data: bytes,
        bbox: Optional[Dict] = None,
        padding_percent: float = 0.1
    ) -> Tuple[bytes, str]:
        """
        Crop ingredient from image using bounding box with padding.
        
        Args:
            image_data: Original image bytes
            bbox: Bounding box dict with {x, y, width, height} (normalized 0-1)
            padding_percent: Padding around crop (default 10%)
            
        Returns:
            (thumbnail_bytes, content_type)
        """
        try:
            img = Image.open(io.BytesIO(image_data))
            
            if bbox and all(k in bbox for k in ['x', 'y', 'width', 'height']):
                # Convert normalized coordinates to pixels
                img_width, img_height = img.size
                x = int(bbox['x'] * img_width)
                y = int(bbox['y'] * img_height)
                width = int(bbox['width'] * img_width)
                height = int(bbox['height'] * img_height)
                
                # Add padding
                padding_x = int(width * padding_percent)
                padding_y = int(height * padding_percent)
                
                # Calculate crop box with padding
                left = max(0, x - padding_x)
                top = max(0, y - padding_y)
                right = min(img_width, x + width + padding_x)
                bottom = min(img_height, y + height + padding_y)
                
                # Crop the image
                img = img.crop((left, top, right, bottom))
            
            # Resize to thumbnail size (maintaining aspect ratio)
            img.thumbnail(IngredientImageProcessor.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            
            # Create square canvas with white background
            canvas = Image.new('RGB', IngredientImageProcessor.THUMBNAIL_SIZE, (255, 255, 255))
            
            # Center the image on canvas
            offset_x = (IngredientImageProcessor.THUMBNAIL_SIZE[0] - img.size[0]) // 2
            offset_y = (IngredientImageProcessor.THUMBNAIL_SIZE[1] - img.size[1]) // 2
            canvas.paste(img, (offset_x, offset_y))
            
            # Convert to bytes
            output = io.BytesIO()
            canvas.save(
                output,
                format=IngredientImageProcessor.THUMBNAIL_FORMAT,
                quality=IngredientImageProcessor.THUMBNAIL_QUALITY,
                optimize=True
            )
            thumbnail_bytes = output.getvalue()
            
            return thumbnail_bytes, f"image/{IngredientImageProcessor.THUMBNAIL_FORMAT.lower()}"
            
        except Exception as e:
            logger.error(f"Failed to crop thumbnail: {e}")
            # Fallback: return resized original image
            return IngredientImageProcessor._create_fallback_thumbnail(image_data)
    
    @staticmethod
    def _create_fallback_thumbnail(image_data: bytes) -> Tuple[bytes, str]:
        """Create a simple resized thumbnail if cropping fails."""
        try:
            img = Image.open(io.BytesIO(image_data))
            img.thumbnail(IngredientImageProcessor.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(
                output,
                format=IngredientImageProcessor.THUMBNAIL_FORMAT,
                quality=IngredientImageProcessor.THUMBNAIL_QUALITY
            )
            return output.getvalue(), "image/jpeg"
        except Exception as e:
            logger.error(f"Fallback thumbnail creation failed: {e}")
            raise
    
    @staticmethod
    def add_confidence_badge(
        thumbnail_data: bytes,
        confidence: float,
        confidence_category: str
    ) -> bytes:
        """
        Add a confidence indicator badge to thumbnail (optional enhancement).
        
        Args:
            thumbnail_data: Thumbnail image bytes
            confidence: Confidence score 0-1
            confidence_category: "high", "medium", or "low"
            
        Returns:
            Modified thumbnail bytes with badge
        """
        try:
            img = Image.open(io.BytesIO(thumbnail_data))
            draw = ImageDraw.Draw(img)
            
            # Badge parameters
            badge_color = IngredientImageProcessor.CONFIDENCE_COLORS.get(
                confidence_category, "#6B7280"
            )
            badge_radius = 8
            badge_pos = (img.width - 30, 10)
            
            # Draw confidence circle
            draw.ellipse(
                [
                    badge_pos[0], badge_pos[1],
                    badge_pos[0] + 20, badge_pos[1] + 20
                ],
                fill=badge_color
            )
            
            # Add confidence percentage
            confidence_text = f"{int(confidence * 100)}"
            try:
                font = ImageFont.truetype("arial.ttf", 10)
            except:
                font = ImageFont.load_default()
            
            # Center text in circle
            bbox = draw.textbbox((0, 0), confidence_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_pos = (
                badge_pos[0] + (20 - text_width) // 2,
                badge_pos[1] + (20 - text_height) // 2
            )
            draw.text(text_pos, confidence_text, fill="white", font=font)
            
            # Convert back to bytes
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=85)
            return output.getvalue()
            
        except Exception as e:
            logger.warning(f"Failed to add confidence badge: {e}")
            return thumbnail_data  # Return original if badge fails
    
    @staticmethod
    async def process_and_upload_thumbnail(
        user_id: str,
        scan_id: str,
        detected_id: str,
        image_data: bytes,
        bbox: Optional[Dict] = None,
        confidence: Optional[float] = None,
        confidence_category: Optional[str] = None,
        add_badge: bool = False
    ) -> Optional[str]:
        """
        Complete workflow: crop, optionally add badge, and upload thumbnail.
        
        Args:
            user_id: User ID for storage path
            scan_id: Scan ID for organizing thumbnails
            detected_id: Detected ingredient ID
            image_data: Original scan image bytes
            bbox: Bounding box coordinates
            confidence: Confidence score
            confidence_category: "high", "medium", or "low"
            add_badge: Whether to add confidence badge
            
        Returns:
            Storage URL of uploaded thumbnail or None if failed
        """
        try:
            # Crop thumbnail
            thumbnail_bytes, content_type = IngredientImageProcessor.crop_ingredient_thumbnail(
                image_data, bbox
            )
            
            # Optionally add confidence badge
            if add_badge and confidence is not None and confidence_category:
                thumbnail_bytes = IngredientImageProcessor.add_confidence_badge(
                    thumbnail_bytes, confidence, confidence_category
                )
            
            # Generate unique filename
            content_hash = hashlib.sha256(thumbnail_bytes).hexdigest()[:12]
            filename = f"thumbnails/{user_id}/{scan_id}/{detected_id}_{content_hash}.jpg"
            
            # Upload to storage
            storage_url = upload_file_to_storage(
                file_content=thumbnail_bytes,
                file_path=filename,
                content_type=content_type,
                bucket_name="ingredient-images"  # Separate bucket for thumbnails
            )
            
            logger.info(f"Uploaded thumbnail for {detected_id}: {storage_url}")
            return storage_url
            
        except Exception as e:
            logger.error(f"Failed to process and upload thumbnail: {e}")
            return None
    
    @staticmethod
    def create_placeholder_thumbnail(
        ingredient_name: str,
        color_hex: str = "#E5E7EB"
    ) -> bytes:
        """
        Create a simple placeholder thumbnail with ingredient name.
        Useful when no image is available.
        
        Args:
            ingredient_name: Name to display
            color_hex: Background color
            
        Returns:
            Thumbnail image bytes
        """
        try:
            # Create canvas
            img = Image.new('RGB', IngredientImageProcessor.THUMBNAIL_SIZE, color_hex)
            draw = ImageDraw.Draw(img)
            
            # Load font
            try:
                font = ImageFont.truetype("arial.ttf", 18)
            except:
                font = ImageFont.load_default()
            
            # Draw ingredient name (centered, wrapped)
            text = ingredient_name.title()
            if len(text) > 15:
                # Split long names
                words = text.split()
                text = '\n'.join([words[0], ' '.join(words[1:])])
            
            bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            position = (
                (IngredientImageProcessor.THUMBNAIL_SIZE[0] - text_width) // 2,
                (IngredientImageProcessor.THUMBNAIL_SIZE[1] - text_height) // 2
            )
            
            draw.multiline_text(position, text, fill="#374151", font=font, align="center")
            
            # Convert to bytes
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=85)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to create placeholder: {e}")
            raise


# Utility functions for easy access
async def upload_ingredient_thumbnail(
    user_id: str,
    scan_id: str,
    detected_id: str,
    image_data: bytes,
    bbox: Optional[Dict] = None,
    confidence: Optional[float] = None,
    confidence_category: Optional[str] = None
) -> Optional[str]:
    """Shortcut function to process and upload ingredient thumbnail."""
    processor = IngredientImageProcessor()
    return await processor.process_and_upload_thumbnail(
        user_id=user_id,
        scan_id=scan_id,
        detected_id=detected_id,
        image_data=image_data,
        bbox=bbox,
        confidence=confidence,
        confidence_category=confidence_category,
        add_badge=False  # Can be enabled via config
    )
