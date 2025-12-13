#!/bin/bash

# SubliminalGen Backend - Google Cloud Run Deployment Script
set -e

PROJECT_ID="avid-sphere-479819-v5"
SERVICE_NAME="subliminalgen-backend"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying SubliminalGen Backend to Google Cloud Run..."
echo "📦 Project: $PROJECT_ID"
echo "🌍 Region: $REGION"
echo "🐳 Image: $IMAGE_NAME"

# Build and push Docker image
echo "🔨 Building Docker image..."
gcloud builds submit --tag $IMAGE_NAME

# Deploy to Cloud Run
echo "☁️ Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --region $REGION \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --allow-unauthenticated \
  --concurrency 10 \
  --port 8080

echo "✅ Deployment complete!"
echo "🌐 Service URL: https://$SERVICE_NAME-311287456014.$REGION.run.app"
echo ""
echo "🧪 Test endpoints:"
echo "curl https://$SERVICE_NAME-311287456014.$REGION.run.app/"
echo "curl https://$SERVICE_NAME-311287456014.$REGION.run.app/health"