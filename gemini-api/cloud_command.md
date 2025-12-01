# Navigate to your backend directory
cd /Users/eva/SubliminalGen/backend/gemini-api

# Build and push new Docker image
gcloud builds submit --tag gcr.io/avid-sphere-479819-v5/subliminalgen-backend

# Deploy the new version
gcloud run deploy subliminalgen-backend \
  --image gcr.io/avid-sphere-479819-v5/subliminalgen-backend \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --allow-unauthenticated