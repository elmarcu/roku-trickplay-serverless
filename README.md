# Roku Trick Play - Serverless Edition

Generate trick play thumbnails for Roku streaming applications using AWS Lambda, S3, and CloudFront.

## Architecture

```
MediaConvert Completion
    ↓
EventBridge Rule
    ↓
trick-play-generator Lambda
    ├─ Generate thumbnails (320x180, 640x360)
    ├─ Upload to S3
    └─ → SQS (manifest-queue)
    ↓
manifest-updater Lambda
    ├─ Create M3U8 playlists
    ├─ Update main HLS playlist
    └─ → SQS (invalidation-queue)
    ↓
cache-invalidator Lambda
    └─ Invalidate CloudFront cache
```

## Project Structure

```
roku-trickplay-serverless/
├── shared/                          # Shared utilities
│   ├── logger.py                   # Structured logging
│   ├── errors.py                   # Custom exceptions
│   ├── config.py                   # Configuration
│   └── aws_helpers.py              # AWS service helpers
│
├── src/                            # Lambda functions
│   ├── trick_play_generator/
│   │   ├── handler.py             # Lambda entry point
│   │   ├── generator.py           # Core logic
│   │   └── requirements.txt
│   ├── manifest_updater/
│   │   ├── handler.py
│   │   ├── updater.py
│   │   └── requirements.txt
│   └── cache_invalidator/
│       ├── handler.py
│       ├── invalidator.py
│       └── requirements.txt
│
├── lambda_layers/                  # Lambda layers
│   ├── ffmpeg/
│   └── shared_libs/
│
├── terraform/                      # Infrastructure as Code
│
├── tests/
│
├── docker-compose.yml              # Local development
├── Dockerfile
├── local-dev-server.py            # Local Lambda runtime
└── localstack-init.sh
```

## Local Development

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- FFmpeg (if running outside Docker)

### Start Local Environment

```bash
docker-compose up -d
```

This starts:
- LocalStack (S3, SQS, CloudFront mock)
- Local Lambda development server on `http://localhost:8000`

### Test Trick Play Generator

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{
    "function_name": "trick_play_generator",
    "event": {
      "detail": {
        "mediaKey": "test-video-123",
        "mediaKeyId": "content/test-video-123/",
        "outputGroupDetails": [{
          "outputDetails": [{
            "outputFilePaths": ["s3://trick-play-bucket/content/test-video-123/play.m3u8"]
          }]
        }]
      }
    }
  }'
```

## Environment Variables

### Required

- `AWS_S3_BUCKET`: S3 bucket for videos and thumbnails
- `AWS_CLOUDFRONT_DISTRIBUTION_ID`: CloudFront distribution ID

### Optional

- `AWS_REGION`: AWS region (default: us-east-1)
- `THUMBNAIL_INTERVAL`: Seconds between thumbnails (default: 10)
- `THUMBNAIL_WIDTH`: Small thumbnail width (default: 320)
- `THUMBNAIL_HEIGHT`: Small thumbnail height (default: 180)
- `THUMBNAIL_BIG_WIDTH`: Large thumbnail width (default: 640)
- `THUMBNAIL_BIG_HEIGHT`: Large thumbnail height (default: 360)
- `SQS_MANIFEST_QUEUE_URL`: SQS queue for manifest updates
- `SQS_CACHE_INVALIDATION_QUEUE_URL`: SQS queue for cache invalidation
- `ENABLE_SLACK_NOTIFICATIONS`: Send notifications to Slack (default: False)
- `SLACK_WEBHOOK_URL`: Slack webhook URL

## Deployment

### Prerequisites

- Terraform installed
- AWS credentials configured
- FFmpeg layer built (see below)

### Build FFmpeg Layer

```bash
cd lambda_layers/ffmpeg
./build.sh
```

### Deploy to AWS

```bash
cd terraform

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var-file=terraform.tfvars

# Apply
terraform apply -var-file=terraform.tfvars
```

## Lambda Layer

FFmpeg must be provided as a Lambda layer since it's not available in the standard Python runtime.

The layer structure:

```
lambda_layers/ffmpeg/
├── python/
│   └── lib/
│       ├── ffmpeg (binary)
│       └── ffprobe (binary)
└── build.sh
```

Building the layer:

```bash
cd lambda_layers/ffmpeg

# Download pre-built ffmpeg for Lambda
# https://github.com/lambci/lambda-packages
bash build.sh

# Creates: ffmpeg-layer.zip
```

## Testing

### Unit Tests

```bash
pytest tests/unit/
```

### Integration Tests (with LocalStack)

```bash
pytest tests/integration/
```

## Configuration Files

### Development (.env.example)

```env
AWS_REGION=us-east-1
AWS_S3_BUCKET=my-bucket
AWS_CLOUDFRONT_DISTRIBUTION_ID=E123ABC456
THUMBNAIL_INTERVAL=10
ENABLE_SLACK_NOTIFICATIONS=False
```

## API Events

### MediaConvert Completion Event

Triggered by EventBridge when MediaConvert finishes encoding:

```json
{
  "detail": {
    "eventType": "JOB_COMPLETE",
    "mediaKey": "unique-video-id",
    "mediaKeyId": "content/video123/",
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
```

### SQS Messages

**Manifest Update Queue:**

```json
{
  "media_key": "unique-video-id",
  "media_path": "content/video123/",
  "hls_url": "s3://bucket/content/video123/play.m3u8",
  "small_thumbnails": ["content/video123/thumbs/video-id_small.00001.jpg", ...],
  "big_thumbnails": ["content/video123/thumbs/video-id_big.00001.jpg", ...],
  "request_id": "..."
}
```

**Cache Invalidation Queue:**

```json
{
  "media_key": "unique-video-id",
  "media_path": "content/video123/",
  "paths_to_invalidate": [
    "/content/video123/play.m3u8",
    "/content/video123/thumbs_320x180.m3u8",
    "/content/video123/thumbs_640x360.m3u8",
    "/content/video123/thumbs/*"
  ],
  "request_id": "..."
}
```

## Monitoring

CloudWatch metrics and alarms:

- `trick_play_generator` errors/duration
- `manifest_updater` errors/duration
- `cache_invalidator` errors/duration
- SQS Dead Letter Queue (DLQ) messages
- CloudFront invalidation status

## Troubleshooting

### FFmpeg errors

Check CloudWatch logs for detailed error messages:

```bash
aws logs tail /aws/lambda/trick-play-generator --follow
```

### S3 permissions

Ensure Lambda IAM role has:
- `s3:GetObject` on source videos
- `s3:PutObject` on thumbnails path

### CloudFront invalidation failures

Ensure:
- Distribution ID is correct
- Paths are properly formatted (e.g., `/path/to/file.m3u8`)
- CloudFront has cache behavior for the paths

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT License - See [LICENSE](LICENSE)
