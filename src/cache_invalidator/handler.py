"""Lambda handler for cache invalidation."""

import json
from typing import Any, Dict

from shared.config import Config
from shared.errors import CDNInvalidationError, TrickPlayError
from shared.logger import StructuredLogger
from invalidator import CacheInvalidator


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process SQS message to invalidate CloudFront cache.

    Expected SQS message body:
    {
        "media_key": "unique-video-id",
        "media_path": "content/video123/",
        "paths_to_invalidate": [
            "/content/video123/play.m3u8",
            "/content/video123/thumbs_320x180.m3u8",
            ...
        ],
        "request_id": "..."
    }
    """
    try:
        StructuredLogger.info("Cache invalidator lambda invoked", request_id=context.request_id)

        Config.validate()

        # Process each SQS record
        for record in event.get("Records", []):
            try:
                message_body = json.loads(record["body"])
                receipt_handle = record["receiptHandle"]

                media_key = message_body.get("media_key")
                paths = message_body.get("paths_to_invalidate", [])

                StructuredLogger.info(
                    "Processing cache invalidation",
                    media_key=media_key,
                    paths_count=len(paths),
                    request_id=context.request_id,
                )

                # Invalidate cache
                invalidator = CacheInvalidator(region_name=Config.AWS_REGION)
                invalidation_id = invalidator.invalidate_cache(
                    paths=paths,
                    distribution_id=Config.AWS_CLOUDFRONT_DISTRIBUTION_ID,
                )

                StructuredLogger.info(
                    "Cache invalidation succeeded",
                    media_key=media_key,
                    invalidation_id=invalidation_id,
                )

            except json.JSONDecodeError as e:
                StructuredLogger.error(
                    "Invalid SQS message format",
                    exception=e,
                    request_id=context.request_id,
                )
            except Exception as e:
                StructuredLogger.error(
                    "Error processing SQS record",
                    exception=e,
                    request_id=context.request_id,
                )

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Cache invalidation completed"}),
        }

    except TrickPlayError as e:
        StructuredLogger.error(
            "Trick play error",
            exception=e,
            request_id=context.request_id,
        )
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(e)}),
        }
    except Exception as e:
        StructuredLogger.error(
            "Unexpected error in cache invalidator",
            exception=e,
            request_id=context.request_id,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
