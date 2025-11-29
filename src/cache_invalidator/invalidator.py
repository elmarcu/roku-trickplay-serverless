"""Cache Invalidator - CloudFront cache clearing."""

from typing import Dict, List

from shared.aws_helpers import CloudFrontHelper
from shared.config import Config
from shared.errors import CDNInvalidationError
from shared.logger import StructuredLogger


class CacheInvalidator:
    """Invalidate CloudFront cache for trick play assets."""

    def __init__(self, region_name: str = "us-east-1"):
        self.cloudfront = CloudFrontHelper(region_name)
        self.config = Config

    def invalidate_cache(self, paths: List[str], distribution_id: str = None) -> str:
        """
        Invalidate CloudFront cache for given paths.

        Args:
            paths: List of paths to invalidate (e.g., ["/content/video123/play.m3u8"])
            distribution_id: CloudFront distribution ID (uses config default if not provided)

        Returns:
            Invalidation ID
        """
        try:
            dist_id = distribution_id or self.config.AWS_CLOUDFRONT_DISTRIBUTION_ID

            if not dist_id:
                raise CDNInvalidationError("CloudFront distribution ID not configured")

            if not paths:
                StructuredLogger.warning("No paths provided for invalidation")
                return None

            StructuredLogger.info(
                "Invalidating CloudFront cache",
                distribution_id=dist_id,
                paths_count=len(paths),
            )

            invalidation_id = self.cloudfront.invalidate_paths(dist_id, paths)

            StructuredLogger.info(
                "Cache invalidation completed",
                distribution_id=dist_id,
                invalidation_id=invalidation_id,
            )

            return invalidation_id

        except Exception as e:
            StructuredLogger.error(
                "Cache invalidation failed",
                exception=e,
            )
            raise CDNInvalidationError(f"Failed to invalidate cache: {str(e)}") from e
