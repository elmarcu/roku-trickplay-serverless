"""Custom exceptions for trick play processing."""


class TrickPlayError(Exception):
    """Base exception for trick play errors."""

    pass


class S3Error(TrickPlayError):
    """S3 operation errors."""

    pass


class FFMpegError(TrickPlayError):
    """FFmpeg processing errors."""

    pass


class ManifestGenerationError(TrickPlayError):
    """Manifest/M3U8 generation errors."""

    pass


class CDNInvalidationError(TrickPlayError):
    """CloudFront cache invalidation errors."""

    pass


class ConfigurationError(TrickPlayError):
    """Configuration or environment variable errors."""

    pass
