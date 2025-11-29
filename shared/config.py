"""Configuration management."""

import os
from typing import Optional


class Config:
    """Centralized configuration from environment variables."""

    # AWS Configuration
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
    AWS_CLOUDFRONT_DISTRIBUTION_ID = os.environ.get("AWS_CLOUDFRONT_DISTRIBUTION_ID")

    # Trick Play Configuration
    THUMBNAIL_INTERVAL = int(os.environ.get("THUMBNAIL_INTERVAL", "10"))  # seconds
    THUMBNAIL_WIDTH = int(os.environ.get("THUMBNAIL_WIDTH", "320"))
    THUMBNAIL_HEIGHT = int(os.environ.get("THUMBNAIL_HEIGHT", "180"))
    THUMBNAIL_FORMAT = os.environ.get("THUMBNAIL_FORMAT", "jpg")  # jpg or png

    # Thumbnail file naming
    THUMBNAIL_SMALL_RESOLUTION = f"{THUMBNAIL_WIDTH}x{THUMBNAIL_HEIGHT}"
    THUMBNAIL_SMALL_SUFFIX = "_small"
    THUMBNAIL_BIG_WIDTH = int(os.environ.get("THUMBNAIL_BIG_WIDTH", "640"))
    THUMBNAIL_BIG_HEIGHT = int(os.environ.get("THUMBNAIL_BIG_HEIGHT", "360"))
    THUMBNAIL_BIG_RESOLUTION = f"{THUMBNAIL_BIG_WIDTH}x{THUMBNAIL_BIG_HEIGHT}"
    THUMBNAIL_BIG_SUFFIX = "_big"

    # Bandwidth for HLS (bits per second)
    THUMBNAIL_SMALL_BANDWIDTH = int(os.environ.get("THUMBNAIL_SMALL_BANDWIDTH", "16460"))
    THUMBNAIL_BIG_BANDWIDTH = int(os.environ.get("THUMBNAIL_BIG_BANDWIDTH", "32920"))

    # S3 Paths
    THUMBNAILS_FOLDER = os.environ.get("THUMBNAILS_FOLDER", "thumbs")

    # Queue Configuration
    SQS_MANIFEST_QUEUE_URL = os.environ.get("SQS_MANIFEST_QUEUE_URL")
    SQS_CACHE_INVALIDATION_QUEUE_URL = os.environ.get("SQS_CACHE_INVALIDATION_QUEUE_URL")

    # Feature flags
    ENABLE_SLACK_NOTIFICATIONS = os.environ.get("ENABLE_SLACK_NOTIFICATIONS", "False").lower() == "true"
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration is set."""
        required = ["AWS_S3_BUCKET", "AWS_CLOUDFRONT_DISTRIBUTION_ID"]
        missing = [var for var in required if not getattr(cls, var, None)]

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return True
