"""
Image Processing Utilities for Clinical Advisor

This module provides utilities for handling Base64-encoded images
for the Clinical Advisor's X-ray and clinical image analysis features.
"""

import base64
import logging
import re
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

# Supported image MIME types
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/gif": [".gif"],
    "image/webp": [".webp"],
}

# Maximum image size (10MB)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# Data URI regex pattern
DATA_URI_PATTERN = re.compile(
    r'^data:(?P<mime>image/(?:jpeg|png|gif|webp));base64,(?P<data>.+)$',
    re.IGNORECASE
)


def validate_base64_image(image_data: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate a Base64-encoded image string with STRICT security checks.

    Security validations performed:
    1. Base64 encoding validity
    2. Image size limits
    3. File signature (magic bytes) verification
    4. MIME type consistency check (declared vs actual)

    Args:
        image_data: The Base64 string (with or without data URI prefix)

    Returns:
        Tuple of (is_valid, mime_type, error_message)
        - is_valid: True if the image is valid
        - mime_type: The detected MIME type (e.g., "image/jpeg")
        - error_message: Error description if invalid, None if valid
    """
    if not image_data:
        return False, None, "Image data is empty"

    if not isinstance(image_data, str):
        return False, None, "Image data must be a string"

    # Check for suspiciously large base64 strings before processing
    # Base64 is ~4/3 of original size, so 10MB image = ~13.3MB base64
    MAX_BASE64_LENGTH = int(MAX_IMAGE_SIZE_BYTES * 1.4)
    if len(image_data) > MAX_BASE64_LENGTH:
        return False, None, f"Image data exceeds maximum allowed size"

    # Check if it's a data URI
    match = DATA_URI_PATTERN.match(image_data)

    if match:
        declared_mime_type = match.group("mime").lower()
        base64_data = match.group("data")
    else:
        # Raw base64 without data URI - we'll detect the type from content
        declared_mime_type = None
        base64_data = image_data

    # Validate Base64 encoding
    try:
        # Remove any whitespace that might have been added
        base64_data = base64_data.strip().replace(" ", "").replace("\n", "").replace("\r", "")

        # Validate base64 characters (security check)
        import re
        if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', base64_data):
            return False, None, "Invalid Base64 characters detected"

        # Decode to check validity and size
        decoded = base64.b64decode(base64_data, validate=True)

        # Check minimum size (valid images need at least some bytes)
        if len(decoded) < 100:
            return False, None, "Image data too small to be a valid image"

        # Check maximum size
        if len(decoded) > MAX_IMAGE_SIZE_BYTES:
            size_mb = len(decoded) / (1024 * 1024)
            return False, None, f"Image too large: {size_mb:.1f}MB. Maximum: {MAX_IMAGE_SIZE_BYTES / (1024 * 1024):.0f}MB"

        # Detect actual image type from file signature
        actual_mime_type = _detect_actual_image_type(decoded)

        if actual_mime_type is None:
            return False, None, "File does not have a valid image signature. Only JPEG, PNG, GIF, and WebP are supported."

        # If a MIME type was declared, verify it matches the actual content
        if declared_mime_type:
            if declared_mime_type != actual_mime_type:
                logger.warning(
                    f"MIME type mismatch: declared={declared_mime_type}, actual={actual_mime_type}"
                )
                return False, None, f"Declared image type ({declared_mime_type}) does not match actual content ({actual_mime_type})"

        # Verify the signature matches (double-check with the strict validator)
        if not _has_valid_image_signature(decoded, actual_mime_type):
            return False, None, "Image file signature validation failed"

        # Final check: verify MIME type is in our supported list
        if actual_mime_type not in SUPPORTED_IMAGE_TYPES:
            return False, None, f"Unsupported image type: {actual_mime_type}. Supported: {list(SUPPORTED_IMAGE_TYPES.keys())}"

        return True, actual_mime_type, None

    except base64.binascii.Error as e:
        return False, None, f"Invalid Base64 encoding: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error validating image: {e}")
        return False, None, f"Error validating image: {str(e)}"


def _has_valid_image_signature(data: bytes, expected_mime: str) -> bool:
    """
    Check if the decoded data has a valid image file signature.

    This function performs STRICT validation - it only returns True if the
    file signature exactly matches known image formats. This prevents
    malicious files from being processed as images.

    Args:
        data: The decoded image bytes
        expected_mime: The expected MIME type

    Returns:
        True if the signature matches expected image type
    """
    if len(data) < 12:  # Need at least 12 bytes for reliable detection
        return False

    # Image file signatures (magic bytes)
    # These are the definitive signatures for each format
    signatures = {
        "image/jpeg": [b'\xff\xd8\xff'],
        "image/png": [b'\x89PNG\r\n\x1a\n'],
        "image/gif": [b'GIF87a', b'GIF89a'],
        "image/webp": [],  # WebP needs special handling (RIFF + WEBP)
    }

    # Special handling for WebP which has a more complex signature
    if expected_mime == "image/webp":
        # WebP format: RIFF....WEBP
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return True
        return False

    expected_sigs = signatures.get(expected_mime, [])

    for sig in expected_sigs:
        if data[:len(sig)] == sig:
            return True

    # STRICT: No lenient fallback - if signature doesn't match, reject
    # This prevents malicious files from being processed
    return False


def _detect_actual_image_type(data: bytes) -> Optional[str]:
    """
    Detect the actual image type from file data based on magic bytes.

    This is used to verify that the declared MIME type matches the actual content,
    preventing MIME type confusion attacks.

    Args:
        data: The decoded image bytes

    Returns:
        The detected MIME type, or None if not a recognized image
    """
    if len(data) < 12:
        return None

    # Check signatures in order of specificity
    if data[:3] == b'\xff\xd8\xff':
        return "image/jpeg"
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    elif data[:6] in [b'GIF87a', b'GIF89a']:
        return "image/gif"
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp"

    return None


def normalize_image_data(image_data: str) -> str:
    """
    Normalize image data to a consistent data URI format.

    Args:
        image_data: The image data (with or without data URI prefix)

    Returns:
        Normalized data URI string (e.g., "data:image/jpeg;base64,...")
    """
    if not image_data:
        return image_data

    # Check if already a data URI
    match = DATA_URI_PATTERN.match(image_data)

    if match:
        # Already a data URI, normalize the MIME type to lowercase
        mime_type = match.group("mime").lower()
        base64_data = match.group("data").strip()
        return f"data:{mime_type};base64,{base64_data}"
    else:
        # Raw Base64, wrap in data URI with default MIME type
        # Try to detect the image type from the data
        mime_type = detect_image_type(image_data) or "image/jpeg"
        return f"data:{mime_type};base64,{image_data.strip()}"


def detect_image_type(base64_data: str) -> Optional[str]:
    """
    Detect the image MIME type from Base64 data.

    Args:
        base64_data: Raw Base64 string (without data URI prefix)

    Returns:
        Detected MIME type or None if unknown
    """
    try:
        # Decode just enough to check the signature
        # Base64 encodes 3 bytes into 4 characters, so 12 chars = 9 bytes
        partial_data = base64.b64decode(base64_data[:100] + "==")

        if partial_data[:3] == b'\xff\xd8\xff':
            return "image/jpeg"
        elif partial_data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif partial_data[:6] in [b'GIF87a', b'GIF89a']:
            return "image/gif"
        elif partial_data[:4] == b'RIFF':
            return "image/webp"

        return None
    except Exception:
        return None


def get_image_size_kb(image_data: str) -> Optional[float]:
    """
    Get the approximate size of a Base64 image in kilobytes.

    Args:
        image_data: Base64 string (with or without data URI prefix)

    Returns:
        Size in KB or None if unable to calculate
    """
    try:
        # Extract just the Base64 data
        match = DATA_URI_PATTERN.match(image_data)
        if match:
            base64_data = match.group("data")
        else:
            base64_data = image_data

        # Base64 size is approximately 4/3 of the original
        # So decoded size is approximately 3/4 of Base64 length
        estimated_bytes = len(base64_data) * 3 / 4
        return estimated_bytes / 1024

    except Exception:
        return None


def prepare_image_for_openai(image_data: str, detail: str = "high") -> dict:
    """
    Prepare an image for the OpenAI Vision API.

    Args:
        image_data: Base64 image data (with or without data URI prefix)
        detail: Image detail level ("low", "high", or "auto")

    Returns:
        Dict formatted for OpenAI's image_url content type
    """
    normalized = normalize_image_data(image_data)

    return {
        "type": "image_url",
        "image_url": {
            "url": normalized,
            "detail": detail
        }
    }


def build_multimodal_content(
    text: str,
    images: Optional[List[str]] = None,
    image_detail: str = "high"
) -> List[dict]:
    """
    Build a multimodal content array for OpenAI's chat API.

    Args:
        text: The text message
        images: Optional list of Base64 image strings
        image_detail: Detail level for images

    Returns:
        List of content items for the OpenAI API
    """
    content = [{"type": "text", "text": text}]

    if images:
        for image_data in images:
            if image_data:
                content.append(prepare_image_for_openai(image_data, image_detail))

    return content
