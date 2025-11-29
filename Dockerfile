FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared utilities
COPY shared/ shared/

# Copy Lambda function code
COPY src/ src/

# Create entrypoint for local testing
COPY local-dev-server.py .

ENV PYTHONUNBUFFERED=1
ENV AWS_REGION=us-east-1

EXPOSE 8000

CMD ["python", "local-dev-server.py"]
