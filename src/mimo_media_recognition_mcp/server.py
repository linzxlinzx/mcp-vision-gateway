"""
Vision MCP Server

An MCP server that enables AI assistants to understand and analyze
images, audio, and video using configurable multimodal model providers.
"""

import base64
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("vision-mcp")

# ============================================================================
# Configuration
# ============================================================================

# Cached provider config
_providers_cache: dict[str, Any] | None = None
_default_provider: str | None = None


def _load_providers_from_file() -> dict[str, Any]:
    """Load provider definitions from providers.json."""
    config_path = os.getenv("VISION_PROVIDERS_FILE", "").strip()
    if not config_path:
        # Try default locations
        candidates = [
            Path.cwd() / "providers.json",
            Path(__file__).parent / "providers.json",
        ]
        for p in candidates:
            if p.exists():
                config_path = str(p)
                break

    if not config_path or not Path(config_path).exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("providers", {})


def _load_providers_from_env() -> dict[str, Any]:
    """Load a single provider from environment variables (backward compatible)."""
    api_key = os.getenv("VISION_API_KEY", "").strip()
    api_base = os.getenv("VISION_API_BASE", "").strip()
    model = os.getenv("VISION_MODEL", "").strip()

    if not api_key and not api_base and not model:
        return {}

    missing = []
    if not api_key:
        missing.append("VISION_API_KEY")
    if not api_base:
        missing.append("VISION_API_BASE")
    if not model:
        missing.append("VISION_MODEL")

    if missing:
        raise RuntimeError(
            f"Missing required env config: {', '.join(missing)}. "
            "Set all of VISION_API_KEY, VISION_API_BASE, VISION_MODEL, "
            "or use a providers.json config file."
        )

    auth_type = os.getenv("VISION_AUTH_TYPE", "bearer").strip()
    name = os.getenv("VISION_PROVIDER_NAME", "default").strip() or "default"
    return {
        name: {
            "api_key": api_key,
            "api_base": api_base,
            "model": model,
            "auth_type": auth_type,
        }
    }


def load_providers() -> tuple[dict[str, Any], str]:
    """Load all provider configs and return (providers, default_name)."""
    global _providers_cache, _default_provider

    if _providers_cache is not None:
        return _providers_cache, _default_provider or ""

    file_providers = _load_providers_from_file()
    env_providers = _load_providers_from_env()

    # Merge: env takes precedence for a single provider
    providers = {**file_providers, **env_providers}

    if not providers:
        raise RuntimeError(
            "No vision providers configured. "
            "Create a providers.json file or set VISION_API_KEY, "
            "VISION_API_BASE, VISION_MODEL environment variables."
        )

    # Resolve api_key from env vars for file-based providers
    for name, cfg in providers.items():
        api_key_env = cfg.get("api_key_env", "")
        if api_key_env and not cfg.get("api_key"):
            cfg["api_key"] = os.getenv(api_key_env, "").strip()
        if not cfg.get("api_key"):
            raise RuntimeError(
                f"Provider '{name}': api_key not found. "
                f"Set it directly or via api_key_env='{api_key_env}'."
            )
        # Defaults
        cfg.setdefault("auth_type", "bearer")
        cfg.setdefault("api_base", "")

    # Determine default
    config_default = ""
    if file_providers:
        # Try to read default from config file
        config_path = os.getenv("VISION_PROVIDERS_FILE", "")
        if not config_path:
            candidates = [
                Path.cwd() / "providers.json",
                Path(__file__).parent / "providers.json",
            ]
            for p in candidates:
                if p.exists():
                    config_path = str(p)
                    break
        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config_default = data.get("default_provider", "")

    if env_providers:
        default = next(iter(env_providers))
    elif config_default and config_default in providers:
        default = config_default
    else:
        default = next(iter(providers))

    _providers_cache = providers
    _default_provider = default

    return providers, default


def get_provider(name: str | None = None) -> dict[str, Any]:
    """Get a specific provider config by name, or the default."""
    providers, default = load_providers()
    target = name or default

    if target not in available_providers():
        raise ValueError(
            f"Unknown provider: '{target}'. "
            f"Available: {', '.join(available_providers())}"
        )

    return providers[target]


def available_providers() -> list[str]:
    """List available provider names."""
    providers, _ = load_providers()
    return list(providers.keys())


def build_chat_completions_url(api_base: str) -> str:
    """Build the complete chat completions URL."""
    api_base = api_base.rstrip("/")
    if api_base.endswith("/chat/completions"):
        return api_base
    return f"{api_base}/chat/completions"


def get_media_limits() -> dict[str, int]:
    """Get media size/count limits from env or defaults."""
    return {
        "max_image_size_mb": int(os.getenv("VISION_MAX_IMAGE_SIZE_MB", "20")),
        "max_audio_size_mb": int(os.getenv("VISION_MAX_AUDIO_SIZE_MB", "50")),
        "max_video_size_mb": int(os.getenv("VISION_MAX_VIDEO_SIZE_MB", "200")),
        "max_images": int(os.getenv("VISION_MAX_IMAGES", "6")),
        "max_audios": int(os.getenv("VISION_MAX_AUDIOS", "3")),
        "max_videos": int(os.getenv("VISION_MAX_VIDEOS", "1")),
    }


# ============================================================================
# MIME Type Detection
# ============================================================================

def guess_mime_type(file_path: Path, media_type: str) -> str:
    """Guess MIME type from file extension."""
    mime_type, _ = mimetypes.guess_type(str(file_path))

    if mime_type is not None:
        return mime_type

    ext = file_path.suffix.lower()

    if media_type == "image":
        mapping = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }
    elif media_type == "audio":
        mapping = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
        }
    elif media_type == "video":
        mapping = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm",
            ".flv": "video/x-flv",
        }
    else:
        raise ValueError(f"Unknown media type: {media_type}")

    if ext in mapping:
        return mapping[ext]

    supported = ", ".join(mapping.keys())
    raise ValueError(f"Unsupported {media_type} format: {ext}. Supported: {supported}")


# ============================================================================
# File Processing
# ============================================================================

def local_file_to_data_url(file_path: str, media_type: str, max_size_mb: int) -> str:
    """Convert local file to data URL."""
    if not file_path or not file_path.strip():
        raise ValueError(f"{media_type.capitalize()} path cannot be empty")

    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    size_mb = path.stat().st_size / 1024 / 1024
    if size_mb > max_size_mb:
        raise ValueError(f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)")

    mime_type = guess_mime_type(path, media_type)

    with path.open("rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


def validate_url(url: str, media_type: str) -> str:
    """Validate URL format."""
    if not url or not url.strip():
        raise ValueError(f"{media_type.capitalize()} URL cannot be empty")

    url = url.strip()
    valid_prefixes = ("http://", "https://", "data:")

    if not any(url.startswith(p) for p in valid_prefixes):
        raise ValueError("URL must start with http://, https://, or data:")

    return url


def build_media_urls(
    media_type: str,
    file_path: str | None = None,
    file_url: str | None = None,
    file_paths: list[str] | None = None,
    file_urls: list[str] | None = None,
    max_files: int = 6,
    max_size_mb: int = 20,
) -> list[str]:
    """Build list of media URLs from various input sources."""
    result: list[str] = []

    if file_path:
        result.append(local_file_to_data_url(file_path, media_type, max_size_mb))

    if file_paths:
        if not isinstance(file_paths, (list, tuple)):
            raise ValueError(f"{media_type}_paths must be a list")
        for path in file_paths:
            result.append(local_file_to_data_url(path, media_type, max_size_mb))

    if file_url:
        result.append(validate_url(file_url, media_type))

    if file_urls:
        if not isinstance(file_urls, (list, tuple)):
            raise ValueError(f"{media_type}_urls must be a list")
        for url in file_urls:
            result.append(validate_url(url, media_type))

    if not result:
        raise ValueError(
            f"At least one {media_type} required: "
            f"provide {media_type}_path, {media_type}_url, "
            f"{media_type}_paths, or {media_type}_urls"
        )

    if len(result) > max_files:
        raise ValueError(
            f"Too many {media_type} files: {len(result)} (max: {max_files})"
        )

    return result


# ============================================================================
# API Client
# ============================================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def call_vision_api(
    media_urls: list[str],
    media_type: str,
    prompt: str,
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
    provider: str | None = None,
) -> str:
    """Call a vision API with retry logic."""
    if not prompt or not prompt.strip():
        raise ValueError("prompt cannot be empty")
    if not 0 <= temperature <= 2:
        raise ValueError("temperature must be between 0 and 2")
    if not 1 <= max_tokens <= 32000:
        raise ValueError("max_tokens must be between 1 and 32000")

    cfg = get_provider(provider)
    endpoint = build_chat_completions_url(cfg["api_base"])

    messages: list[dict[str, Any]] = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})

    # Build content based on media type
    content: list[dict[str, Any]] = []
    for url in media_urls:
        if media_type == "image":
            content.append({"type": "image_url", "image_url": {"url": url}})
        elif media_type == "audio":
            content.append({"type": "audio_url", "audio_url": {"url": url}})
        elif media_type == "video":
            content.append({"type": "video_url", "video_url": {"url": url}})

    content.append({"type": "text", "text": prompt})
    messages.append({"role": "user", "content": content})

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Build auth header based on auth_type
    auth_type = cfg.get("auth_type", "bearer")
    if auth_type == "api-key":
        headers = {
            "api-key": cfg["api_key"],
            "Content-Type": "application/json",
        }
    else:  # bearer (default)
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }

    timeout = float(os.getenv("VISION_TIMEOUT", "180"))

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


# ============================================================================
# MCP Tools - Image
# ============================================================================

@mcp.tool()
async def understand_image(
    prompt: str,
    image_path: str | None = None,
    image_url: str | None = None,
    image_paths: list[str] | None = None,
    image_urls: list[str] | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 12000,
    provider: str | None = None,
) -> str:
    """
    Analyze images using a configurable multimodal vision model.

    Args:
        prompt: Analysis task (e.g., "Describe this image", "Extract text")
        image_path: Path to a single local image
        image_url: URL of a single remote image
        image_paths: List of paths to local images
        image_urls: List of URLs to remote images
        system_prompt: Optional system prompt
        temperature: Randomness (0-2), default: 0.2
        max_tokens: Maximum response length
        provider: Vision provider name (default: first configured provider)

    Returns:
        The model's analysis of the image(s)
    """
    limits = get_media_limits()

    urls = build_media_urls(
        media_type="image",
        file_path=image_path,
        file_url=image_url,
        file_paths=image_paths,
        file_urls=image_urls,
        max_files=limits["max_images"],
        max_size_mb=limits["max_image_size_mb"],
    )

    return await call_vision_api(
        media_urls=urls,
        media_type="image",
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    )


# ============================================================================
# MCP Tools - Audio
# ============================================================================

@mcp.tool()
async def understand_audio(
    prompt: str,
    audio_path: str | None = None,
    audio_url: str | None = None,
    audio_paths: list[str] | None = None,
    audio_urls: list[str] | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 12000,
    provider: str | None = None,
) -> str:
    """
    Analyze audio files using a configurable multimodal model.

    Supports: speech recognition, audio content analysis,
    music genre detection, sound event detection, etc.

    Args:
        prompt: Analysis task (e.g., "Transcribe this audio")
        audio_path: Path to a single local audio file
        audio_url: URL of a single remote audio file
        audio_paths: List of paths to local audio files
        audio_urls: List of URLs to remote audio files
        system_prompt: Optional system prompt
        temperature: Randomness (0-2), default: 0.2
        max_tokens: Maximum response length
        provider: Vision provider name (default: first configured provider)

    Returns:
        The model's analysis of the audio
    """
    limits = get_media_limits()

    urls = build_media_urls(
        media_type="audio",
        file_path=audio_path,
        file_url=audio_url,
        file_paths=audio_paths,
        file_urls=audio_urls,
        max_files=limits["max_audios"],
        max_size_mb=limits["max_audio_size_mb"],
    )

    return await call_vision_api(
        media_urls=urls,
        media_type="audio",
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    )


# ============================================================================
# MCP Tools - Video
# ============================================================================

@mcp.tool()
async def understand_video(
    prompt: str,
    video_path: str | None = None,
    video_url: str | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 12000,
    provider: str | None = None,
) -> str:
    """
    Analyze video files using a configurable multimodal model.

    Supports: video content description, scene analysis,
    action recognition, object tracking, etc.

    Args:
        prompt: Analysis task (e.g., "Describe what's happening in this video")
        video_path: Path to a local video file
        video_url: URL of a remote video file
        system_prompt: Optional system prompt
        temperature: Randomness (0-2), default: 0.2
        max_tokens: Maximum response length
        provider: Vision provider name (default: first configured provider)

    Returns:
        The model's analysis of the video
    """
    limits = get_media_limits()

    urls = build_media_urls(
        media_type="video",
        file_path=video_path,
        file_url=video_url,
        max_files=limits["max_videos"],
        max_size_mb=limits["max_video_size_mb"],
    )

    return await call_vision_api(
        media_urls=urls,
        media_type="video",
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
    )


# ============================================================================
# MCP Tools - Utility
# ============================================================================

@mcp.tool()
async def list_providers() -> str:
    """
    List all configured vision providers and their capabilities.

    Returns:
        A formatted list of available providers with model info
    """
    providers, default = load_providers()
    lines = ["Available vision providers:\n"]

    for name in available_providers():
        cfg = providers[name]
        is_default = " (default)" if name == default else ""
        lines.append(f"  - {name}{is_default}")
        lines.append(f"    Model: {cfg['model']}")
        lines.append(f"    API: {cfg['api_base']}")
        lines.append(f"    Auth: {cfg.get('auth_type', 'bearer')}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# MCP Resources
# ============================================================================

@mcp.resource("vision://config")
def get_config() -> str:
    """Get current vision provider configuration (API keys are masked)."""
    try:
        providers, default = load_providers()
        limits = get_media_limits()
        lines = ["Vision MCP Configuration\n"]
        lines.append(f"Default provider: {default}\n")

        for name in available_providers():
            cfg = providers[name]
            key = cfg.get("api_key", "")
            if len(key) >= 10:
                masked = f"{key[:6]}...{key[-4:]}"
            elif len(key) > 0:
                masked = "***"
            else:
                masked = "not set"

            is_default = " (default)" if name == default else ""
            lines.append(f"[{name}]{is_default}")
            lines.append(f"  API Base: {cfg['api_base']}")
            lines.append(f"  Model: {cfg['model']}")
            lines.append(f"  API Key: {masked}")
            lines.append(f"  Auth: {cfg.get('auth_type', 'bearer')}")
            lines.append("")

        lines.append("Media Limits:")
        lines.append(f"  Image: max {limits['max_images']} files, {limits['max_image_size_mb']}MB each")
        lines.append(f"  Audio: max {limits['max_audios']} files, {limits['max_audio_size_mb']}MB each")
        lines.append(f"  Video: max {limits['max_videos']} files, {limits['max_video_size_mb']}MB each")

        return "\n".join(lines)
    except RuntimeError as e:
        return f"Configuration error: {e}"


# ============================================================================
# Entry Point
# ============================================================================

def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
