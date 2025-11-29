"""Trick Play Generator - Refactored FFMpegManager for Lambda."""

import json
import os
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

from shared.aws_helpers import S3Helper
from shared.config import Config
from shared.errors import FFMpegError
from shared.logger import StructuredLogger


class TrickPlayGenerator:
    """Generate trick play thumbnails using FFmpeg."""

    def __init__(self, region_name: str = "us-east-1"):
        self.s3 = S3Helper(region_name)
        self.config = Config

    def generate_thumbnails(
        self,
        hls_url: str,
        media_key: str,
        bucket: str,
        media_path: str,
    ) -> Tuple[List[str], List[str]]:
        """
        Generate trick play thumbnails from HLS stream.

        Args:
            hls_url: S3 URL or path to HLS manifest
            media_key: Unique identifier for media
            bucket: S3 bucket name
            media_path: Path in S3 for media (e.g., "content/video123/")

        Returns:
            Tuple of (small_thumbnails, big_thumbnails) - lists of S3 keys
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                StructuredLogger.info(
                    "Starting thumbnail generation",
                    media_key=media_key,
                    hls_url=hls_url,
                    media_path=media_path,
                )

                # Download HLS manifest
                manifest_path = os.path.join(tmpdir, "manifest.m3u8")
                self.s3.download_file(bucket, hls_url.replace("s3://", "").split("/", 1)[1], manifest_path)

                # Generate small thumbnails (320x180)
                small_dir = os.path.join(tmpdir, "small")
                os.makedirs(small_dir, exist_ok=True)
                small_thumbnails = self._generate_resolution_thumbnails(
                    hls_url,
                    media_key,
                    small_dir,
                    bucket,
                    media_path,
                    width=self.config.THUMBNAIL_WIDTH,
                    height=self.config.THUMBNAIL_HEIGHT,
                    suffix=self.config.THUMBNAIL_SMALL_SUFFIX,
                )

                # Generate big thumbnails (640x360)
                big_dir = os.path.join(tmpdir, "big")
                os.makedirs(big_dir, exist_ok=True)
                big_thumbnails = self._generate_resolution_thumbnails(
                    hls_url,
                    media_key,
                    big_dir,
                    bucket,
                    media_path,
                    width=self.config.THUMBNAIL_BIG_WIDTH,
                    height=self.config.THUMBNAIL_BIG_HEIGHT,
                    suffix=self.config.THUMBNAIL_BIG_SUFFIX,
                )

                StructuredLogger.info(
                    "Thumbnail generation completed",
                    media_key=media_key,
                    small_count=len(small_thumbnails),
                    big_count=len(big_thumbnails),
                )

                return small_thumbnails, big_thumbnails

            except Exception as e:
                StructuredLogger.error(
                    "Thumbnail generation failed",
                    media_key=media_key,
                    exception=e,
                )
                raise FFMpegError(f"Failed to generate thumbnails for {media_key}: {str(e)}") from e

    def _generate_resolution_thumbnails(
        self,
        hls_url: str,
        media_key: str,
        output_dir: str,
        bucket: str,
        media_path: str,
        width: int,
        height: int,
        suffix: str,
    ) -> List[str]:
        """
        Generate thumbnails at specific resolution.

        Uses FFmpeg filter to extract frames at intervals.
        """
        try:
            # FFmpeg filter: extract one frame every THUMBNAIL_INTERVAL seconds
            # select filter: if(not(floor(mod(t,10)))*lt(ld(1),1),st(1,1)+st(2,n)+st(3,t));...
            # This is optimized for picking frames at regular intervals
            ffmpeg_filter = (
                f"select='if(not(floor(mod(t,{self.config.THUMBNAIL_INTERVAL})))*lt(ld(1),1),"
                f"st(1,1)+st(2,n)+st(3,t));if(eq(ld(1),1)*lt(n,ld(2)+1),1,if(trunc(t-ld(3)),st(1,0)))'"
            )

            output_pattern = os.path.join(output_dir, f"{media_key}{suffix}.%05d.{self.config.THUMBNAIL_FORMAT}")

            # FFmpeg command
            cmd = [
                "ffmpeg",
                "-i",
                hls_url,
                "-vf",
                ffmpeg_filter,
                "-vsync",
                "0",
                "-s",
                f"{width}x{height}",
                output_pattern,
            ]

            StructuredLogger.info(
                "Running FFmpeg",
                media_key=media_key,
                resolution=f"{width}x{height}",
                suffix=suffix,
            )

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8") if stderr else "Unknown FFmpeg error"
                raise FFMpegError(f"FFmpeg failed for {media_key}: {error_msg}")

            # Upload generated thumbnails to S3
            thumbnail_keys = []
            thumbnails_folder = f"{media_path}{self.config.THUMBNAILS_FOLDER}/"

            for filename in sorted(os.listdir(output_dir)):
                if filename.endswith(f".{self.config.THUMBNAIL_FORMAT}"):
                    file_path = os.path.join(output_dir, filename)
                    s3_key = f"{thumbnails_folder}{filename}"

                    self.s3.upload_file(
                        bucket,
                        s3_key,
                        file_path,
                        content_type=f"image/{self.config.THUMBNAIL_FORMAT}",
                        public=True,
                    )

                    thumbnail_keys.append(s3_key)

                    StructuredLogger.debug(
                        "Thumbnail uploaded",
                        media_key=media_key,
                        s3_key=s3_key,
                    )

            StructuredLogger.info(
                "Resolution thumbnails generated and uploaded",
                media_key=media_key,
                resolution=f"{width}x{height}",
                count=len(thumbnail_keys),
            )

            return thumbnail_keys

        except Exception as e:
            StructuredLogger.error(
                "Resolution thumbnail generation failed",
                media_key=media_key,
                resolution=f"{width}x{height}",
                exception=e,
            )
            raise
