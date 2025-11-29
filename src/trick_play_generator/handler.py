"""Lambda handler for trick play thumbnail generation."""

import json
from typing import Any, Dict

from generator import TrickPlayGenerator
from shared.aws_helpers import SQSHelper
from shared.config import Config
from shared.errors import FFMpegError, TrickPlayError
from shared.logger import StructuredLogger


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process MediaConvert completion event and generate trick play thumbnails.

    Expected event format (from MediaConvert via EventBridge):
    {
        "detail": {
            "eventType": "JOB_COMPLETE",
            "mediaKeyId": "content/video123/",
            "mediaKey": "unique-video-id",
            "outputGroupDetails": [
                {
                    "outputDetails": [
                        {
                            "outputFilePaths": ["s3://bucket/content/video123/play.m3u8"]
                        }
                    ]
                }
            ]
        }
    }
    """
    try:
        StructuredLogger.info("Trick play generator lambda invoked", request_id=context.request_id)

        # Validate configuration
        Config.validate()

        # Parse event
        detail = event.get("detail", {})
        media_key = detail.get("mediaKey")
        media_path = detail.get("mediaKeyId")

        if not media_key or not media_path:
            raise ValueError("Missing required fields: mediaKey, mediaKeyId")

        # Extract HLS manifest path
        hls_url = _extract_hls_url(detail)
        if not hls_url:
            raise ValueError("No HLS manifest found in event")

        StructuredLogger.info(
            "Processing media",
            media_key=media_key,
            media_path=media_path,
            hls_url=hls_url,
        )

        # Generate thumbnails
        generator = TrickPlayGenerator(region_name=Config.AWS_REGION)
        small_thumbs, big_thumbs = generator.generate_thumbnails(
            hls_url=hls_url,
            media_key=media_key,
            bucket=Config.AWS_S3_BUCKET,
            media_path=media_path,
        )

        # Publish to SQS for manifest update
        sqs = SQSHelper(region_name=Config.AWS_REGION)
        manifest_message = {
            "media_key": media_key,
            "media_path": media_path,
            "hls_url": hls_url,
            "small_thumbnails": small_thumbs,
            "big_thumbnails": big_thumbs,
            "request_id": context.request_id,
        }

        if Config.SQS_MANIFEST_QUEUE_URL:
            sqs.send_message(Config.SQS_MANIFEST_QUEUE_URL, manifest_message)

        StructuredLogger.info(
            "Trick play generation succeeded",
            media_key=media_key,
            request_id=context.request_id,
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Trick play thumbnails generated successfully",
                "media_key": media_key,
                "small_thumbnails_count": len(small_thumbs),
                "big_thumbnails_count": len(big_thumbs),
            }),
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
            "Unexpected error in trick play generator",
            exception=e,
            request_id=context.request_id,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def _extract_hls_url(detail: Dict[str, Any]) -> str:
    """Extract HLS manifest URL from MediaConvert event."""
    try:
        output_groups = detail.get("outputGroupDetails", [])
        for output_group in output_groups:
            outputs = output_group.get("outputDetails", [])
            for output in outputs:
                paths = output.get("outputFilePaths", [])
                for path in paths:
                    if "m3u8" in path:
                        return path
        return None
    except Exception as e:
        StructuredLogger.error("Error extracting HLS URL from event", exception=e)
        return None
