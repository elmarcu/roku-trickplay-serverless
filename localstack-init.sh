#!/bin/bash
# LocalStack initialization script for local development

awslocal s3 mb s3://trick-play-bucket
awslocal sqs create-queue --queue-name manifest-queue
awslocal sqs create-queue --queue-name invalidation-queue

echo "LocalStack initialized with S3 bucket and SQS queues"
