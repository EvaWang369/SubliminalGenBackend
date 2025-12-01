# Google Cloud Deployment Commands

## Enable Required Services
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable storage-api.googleapis.com
```

## Create Storage Bucket
```bash
gsutil mb gs://avid-sphere-479819-v5-builds
```

## Set IAM Permissions
```bash
gcloud projects add-iam-policy-binding avid-sphere-479819-v5 \
    --member="serviceAccount:311287456014-compute@developer.gserviceaccount.com" \
    --role="roles/storage.admin"
```

## Build and Deploy
```bash
# Navigate to backend directory
cd /Users/eva/SubliminalGen/backend/gemini-api

# Build container image
gcloud builds submit --tag gcr.io/avid-sphere-479819-v5/subliminalgen-backend

# Deploy to Cloud Run
gcloud run deploy subliminalgen-backend \
  --image gcr.io/avid-sphere-479819-v5/subliminalgen-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --concurrency 10 \
  --port 8080
```

## Update Environment Variables
```bash
gcloud run services update subliminalgen-backend \
  --region us-central1 \
  --set-env-vars "SUPABASE_URL=<SUPABASE_URL>,SUPABASE_KEY=<SUPABASE_KEY>,SUPABASE_SERVICE_KEY=<SUPABASE_SERVICE_KEY>,GEMINI_API_KEY=<GEMINI_API_KEY>,GOOGLE_CLIENT_ID=<GOOGLE_CLIENT_ID>,BASE_URL=<BASE_URL>"
```

## Project Details
- **Project ID**: avid-sphere-479819-v5
- **Service Account**: 311287456014-compute@developer.gserviceaccount.com
- **Region**: us-central1
- **Container Registry**: gcr.io/avid-sphere-479819-v5/subliminalgen-backend
- **Service URL**: https://subliminalgen-backend-311287456014.us-central1.run.app