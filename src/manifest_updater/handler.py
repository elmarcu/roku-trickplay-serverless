"""Lambda handler for manifest update."""

import json
from typing import Any, Dict

from shared.aws_helpers import SQSHelper
from shared.config import Config
from shared.errors import ManifestGenerationError, TrickPlayError
from shared.logger import StructuredLogger
from updater import ManifestUpdater


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process SQS message to update trick play manifests.

    Expected SQS message body:
    {
        "media_key": "unique-video-id",
        "media_path": "content/video123/",
        "hls_url": "s3://bucket/content/video123/play.m3u8",
        "small_thumbnails": [...],
        "big_thumbnails": [...],
        "request_id": "..."
    }
    """
    try:
        StructuredLogger.info("Manifest updater lambda invoked", request_id=context.request_id)

        Config.validate()

        # Process each SQS record
        for record in event.get("Records", []):
            try:
                message_body = json.loads(record["body"])
                receipt_handle = record["receiptHandle"]

                StructuredLogger.info(
                    "Processing manifest update",
                    media_key=message_body.get("media_key"),
                    request_id=context.request_id,
                )

                # Update manifests
                updater = ManifestUpdater(region_name=Config.AWS_REGION)
                results = updater.create_manifests_and_update_playlist(
                    bucket=Config.AWS_S3_BUCKET,
                    media_path=message_body["media_path"],
                    hls_url=message_body["hls_url"],
                    small_thumbnails=message_body.get("small_thumbnails", []),
                    big_thumbnails=message_body.get("big_thumbnails", []),
                )

                # Publish to SQS for cache invalidation
                sqs = SQSHelper(region_name=Config.AWS_REGION)
                invalidation_message = {
                    "media_key": message_body["media_key"],
                    "media_path": message_body["media_path"],
                    "paths_to_invalidate": _build_invalidation_paths(message_body["media_path"]),
                    "request_id": context.request_id,
                }

                if Config.SQS_CACHE_INVALIDATION_QUEUE_URL:
                    sqs.send_message(Config.SQS_CACHE_INVALIDATION_QUEUE_URL, invalidation_message)

                # Delete message from SQS
                sqs.delete_message(Config.SQS_MANIFEST_QUEUE_URL, receipt_handle)

                StructuredLogger.info(
                    "Manifest update succeeded",
                    media_key=message_body.get("media_key"),
                    results=results,
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
            "body": json.dumps({"message": "Manifests updated successfully"}),
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
            "Unexpected error in manifest updater",
            exception=e,
            request_id=context.request_id,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def _build_invalidation_paths(media_path: str) -> list:
    """Build CloudFront invalidation paths."""
    return [
        f"/{media_path}play.m3u8",
        f"/{media_path}thumbs_320x180.m3u8",
        f"/{media_path}thumbs_640x360.m3u8",
        f"/{media_path}thumbs/*",
    ]
