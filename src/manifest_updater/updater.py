"""Manifest Updater - Refactored TrickPlayManager for Lambda."""

from typing import Dict, List, Optional

from shared.aws_helpers import S3Helper
from shared.config import Config
from shared.errors import ManifestGenerationError
from shared.logger import StructuredLogger


class ManifestUpdater:
    """Generate and update HLS trick play manifests."""

    def __init__(self, region_name: str = "us-east-1"):
        self.s3 = S3Helper(region_name)
        self.config = Config

    def create_manifests_and_update_playlist(
        self,
        bucket: str,
        media_path: str,
        hls_url: str,
        small_thumbnails: List[str],
        big_thumbnails: List[str],
    ) -> Dict[str, str]:
        """
        Create trick play M3U8 manifests and update main playlist.

        Returns:
            Dict with status messages for each resolution
        """
        try:
            StructuredLogger.info(
                "Creating manifests",
                media_path=media_path,
                small_count=len(small_thumbnails),
                big_count=len(big_thumbnails),
            )

            results = {}

            # Create small resolution manifest
            if small_thumbnails:
                results["small"] = self._create_manifest(
                    bucket=bucket,
                    media_path=media_path,
                    hls_url=hls_url,
                    thumbnails=small_thumbnails,
                    resolution=self.config.THUMBNAIL_SMALL_RESOLUTION,
                    bandwidth=self.config.THUMBNAIL_SMALL_BANDWIDTH,
                    suffix="small",
                )

            # Create big resolution manifest
            if big_thumbnails:
                results["big"] = self._create_manifest(
                    bucket=bucket,
                    media_path=media_path,
                    hls_url=hls_url,
                    thumbnails=big_thumbnails,
                    resolution=self.config.THUMBNAIL_BIG_RESOLUTION,
                    bandwidth=self.config.THUMBNAIL_BIG_BANDWIDTH,
                    suffix="big",
                )

            StructuredLogger.info(
                "Manifests created successfully",
                media_path=media_path,
                resolutions=list(results.keys()),
            )

            return results

        except Exception as e:
            StructuredLogger.error(
                "Manifest creation failed",
                media_path=media_path,
                exception=e,
            )
            raise ManifestGenerationError(f"Failed to create manifests for {media_path}: {str(e)}") from e

    def _create_manifest(
        self,
        bucket: str,
        media_path: str,
        hls_url: str,
        thumbnails: List[str],
        resolution: str,
        bandwidth: int,
        suffix: str,
    ) -> str:
        """Create M3U8 manifest for single resolution."""
        try:
            # Determine relative path (whether in hls/ subfolder or not)
            relative_path = "../thumbs/" if "hls/" in media_path else "thumbs/"

            # Build manifest content
            manifest_lines = [
                "#EXTM3U",
                f"#EXT-X-TARGETDURATION:{self.config.THUMBNAIL_INTERVAL}",
                "#EXT-X-VERSION:7",
                "#EXT-X-MEDIA-SEQUENCE:1",
                "#EXT-X-PLAYLIST-TYPE:VOD",
                "#EXT-X-IMAGES-ONLY",
                "",
            ]

            # Add entries for each thumbnail
            for thumbnail_key in thumbnails:
                thumbnail_name = thumbnail_key.split("/")[-1]
                manifest_lines.append(f"#EXTINF:{self.config.THUMBNAIL_INTERVAL}.000,")
                manifest_lines.append(
                    f"#EXT-X-TILES:RESOLUTION={resolution},LAYOUT=1x1,DURATION={self.config.THUMBNAIL_INTERVAL}.000"
                )
                manifest_lines.append(f"{relative_path}{thumbnail_name}")
                manifest_lines.append("")

            manifest_lines.append("#EXT-X-ENDLIST")
            manifest_content = "\n".join(manifest_lines)

            # Upload manifest
            manifest_filename = f"thumbs_{resolution}.m3u8"
            manifest_key = f"{media_path}{manifest_filename}"

            self.s3.put_object(
                bucket=bucket,
                key=manifest_key,
                body=manifest_content,
                content_type="application/vnd.apple.mpegurl",
                public=True,
            )

            # Update main playlist with image stream
            self._update_main_playlist(bucket, media_path, hls_url, manifest_filename, resolution, bandwidth)

            StructuredLogger.info(
                "Manifest created",
                media_path=media_path,
                resolution=resolution,
                manifest_key=manifest_key,
            )

            return f"Created {manifest_filename} for {resolution}"

        except Exception as e:
            StructuredLogger.error(
                "Manifest creation failed",
                resolution=resolution,
                exception=e,
            )
            raise

    def _update_main_playlist(
        self,
        bucket: str,
        media_path: str,
        hls_url: str,
        manifest_filename: str,
        resolution: str,
        bandwidth: int,
    ) -> None:
        """Add image stream to main HLS playlist."""
        try:
            # Get current main playlist
            playlist_key = hls_url.replace("s3://", "").split("/", 1)[1]
            playlist_content = self.s3.get_object(bucket, playlist_key)

            # Check if already updated
            if manifest_filename in playlist_content:
                StructuredLogger.info(
                    "Playlist already updated",
                    playlist_key=playlist_key,
                    resolution=resolution,
                )
                return

            # Add image stream line
            image_stream_line = (
                f'#EXT-X-IMAGE-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={resolution},'
                f'CODECS="jpeg",URI="{manifest_filename}"\n'
            )

            # Insert before #EXT-X-STREAM-INF (if exists) or at end
            if "#EXT-X-STREAM-INF" in playlist_content:
                # Insert before first STREAM-INF
                updated_content = playlist_content.replace(
                    "#EXT-X-STREAM-INF",
                    image_stream_line + "#EXT-X-STREAM-INF",
                    1,
                )
            else:
                # Append before #EXT-X-ENDLIST
                updated_content = playlist_content.replace(
                    "#EXT-X-ENDLIST",
                    image_stream_line + "#EXT-X-ENDLIST",
                )

            # Upload updated playlist
            self.s3.put_object(
                bucket=bucket,
                key=playlist_key,
                body=updated_content,
                content_type="application/vnd.apple.mpegurl",
                public=True,
            )

            StructuredLogger.info(
                "Playlist updated",
                playlist_key=playlist_key,
                resolution=resolution,
            )

        except Exception as e:
            StructuredLogger.error(
                "Playlist update failed",
                resolution=resolution,
                exception=e,
            )
            raise
