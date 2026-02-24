import io
from PIL import Image, ExifTags
from collections import Counter
import structlog

log = structlog.get_logger()


class ImageProcessor:
    """Pure image processing — no I/O, no side effects."""

    def create_thumbnail(self, image_bytes: bytes, size: int) -> tuple[bytes, dict]:
        """Create a square thumbnail, center-cropped, as WebP."""
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")

        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        img = img.crop((left, top, left + min_dim, top + min_dim))

        img = img.resize((size, size), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=80)

        return buf.getvalue(), {"width": size, "height": size}

    def create_resized(self, image_bytes: bytes, max_dimension: int) -> tuple[bytes, dict]:
        """Resize to fit within max_dimension, maintaining aspect ratio. Output as WebP."""
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")

        w, h = img.size

        if max(w, h) > max_dimension:
            if w > h:
                new_w = max_dimension
                new_h = int(h * (max_dimension / w))
            else:
                new_h = max_dimension
                new_w = int(w * (max_dimension / h))
            img = img.resize((new_w, new_h), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=85)

        final_w, final_h = img.size
        return buf.getvalue(), {"width": final_w, "height": final_h}

    def extract_metadata(self, image_bytes: bytes) -> dict:
        """Extract dimensions, format, EXIF data, and dominant color."""
        img = Image.open(io.BytesIO(image_bytes))

        metadata = {
            "width": img.size[0],
            "height": img.size[1],
            "format": img.format or "unknown",
        }

        # EXIF
        try:
            exif_data = img._getexif()
            if exif_data:
                exif = {}
                for tag_id, value in exif_data.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    if isinstance(value, (str, int, float)):
                        exif[str(tag)] = str(value)
                metadata["exif"] = exif if exif else None
            else:
                metadata["exif"] = None
        except Exception:
            metadata["exif"] = None

        # Dominant color
        try:
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size
            cx, cy = w // 2, h // 2
            sample_size = min(50, w, h)
            half = sample_size // 2
            region = rgb_img.crop((cx - half, cy - half, cx + half, cy + half))
            region = region.resize((10, 10), Image.NEAREST)

            pixels = list(region.getdata())
            quantized = [
                (r // 32 * 32, g // 32 * 32, b // 32 * 32)
                for r, g, b in pixels
            ]
            most_common = Counter(quantized).most_common(1)[0][0]
            metadata["dominant_color"] = "#{:02x}{:02x}{:02x}".format(*most_common)
        except Exception:
            metadata["dominant_color"] = "#666666"

        return metadata
