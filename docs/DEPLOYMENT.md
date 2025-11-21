# Deployment Guide

## Backend Deployment

### Option 1: Render.com (Recommended)

1. **Create Render Account**
   - Sign up at render.com
   - Connect your GitHub repository

2. **Create Web Service**
   - Choose "Web Service"
   - Connect repository: `your-username/SubliminalGen`
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **Environment Variables**
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   SUPABASE_SERVICE_KEY=your_service_key
   AWS_ACCESS_KEY_ID=your_aws_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret
   AWS_REGION=us-east-1
   S3_BUCKET_NAME=subliminal-gen
   ELEVENLABS_API_KEY=your_elevenlabs_key
   OPENAI_API_KEY=your_openai_key
   ENVIRONMENT=production
   DEBUG=false
   ```

4. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment to complete
   - Note the service URL

### Option 2: Railway

1. **Create Railway Account**
   - Sign up at railway.app
   - Connect GitHub repository

2. **Deploy from GitHub**
   - Click "Deploy from GitHub"
   - Select repository and `backend` folder
   - Railway auto-detects Python and installs dependencies

3. **Environment Variables**
   - Add same variables as Render option
   - Set `PORT` to `8000`

4. **Custom Start Command**
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

### Option 3: Supabase Edge Functions

1. **Install Supabase CLI**
   ```bash
   npm install -g supabase
   ```

2. **Initialize Functions**
   ```bash
   supabase functions new subliminal-api
   ```

3. **Deploy Function**
   ```bash
   supabase functions deploy subliminal-api
   ```

## Database Setup (Supabase)

1. **Create Project**
   - Go to supabase.com
   - Create new project
   - Note URL and anon key

2. **Enable Extensions**
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. **Run Schema**
   - Copy SQL from `scripts/setup.sh`
   - Run in Supabase SQL editor

4. **Configure RLS**
   - Enable Row Level Security
   - Set up policies for user_creations table

## Storage Setup (AWS S3)

1. **Create S3 Bucket**
   ```bash
   aws s3 mb s3://subliminal-gen
   ```

2. **Configure CORS**
   ```json
   [
     {
       "AllowedHeaders": ["*"],
       "AllowedMethods": ["GET", "PUT", "POST"],
       "AllowedOrigins": ["*"],
       "ExposeHeaders": []
     }
   ]
   ```

3. **Set Lifecycle Policy**
   ```json
   {
     "Rules": [
       {
         "ID": "DeleteTempFiles",
         "Status": "Enabled",
         "Filter": {"Prefix": "temp/"},
         "Expiration": {"Days": 1}
       }
     ]
   }
   ```

4. **Create IAM User**
   - Create user with S3 access
   - Generate access keys
   - Attach policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject"
         ],
         "Resource": "arn:aws:s3:::subliminal-gen/*"
       }
     ]
   }
   ```

## iOS App Deployment

### TestFlight (Beta)

1. **Archive Build**
   - Open project in Xcode
   - Select "Any iOS Device"
   - Product → Archive

2. **Upload to App Store Connect**
   - Use Xcode Organizer
   - Select archive and click "Distribute App"
   - Choose "App Store Connect"

3. **Configure TestFlight**
   - Go to App Store Connect
   - Add beta testers
   - Submit for review

### App Store (Production)

1. **Prepare App Store Listing**
   - Screenshots (required sizes)
   - App description
   - Keywords
   - Privacy policy URL

2. **Submit for Review**
   - Complete app information
   - Set pricing and availability
   - Submit for App Store review

## Monitoring & Maintenance

### Backend Monitoring

1. **Health Check Endpoint**
   ```python
   @app.get("/health")
   async def health_check():
       return {"status": "healthy", "timestamp": datetime.now()}
   ```

2. **Logging**
   - Use structured logging
   - Monitor error rates
   - Set up alerts for failures

3. **Performance Monitoring**
   - Track API response times
   - Monitor cache hit rates
   - Watch S3 usage costs

### Database Maintenance

1. **Regular Backups**
   - Supabase handles automatic backups
   - Consider additional backup strategy for critical data

2. **Index Optimization**
   - Monitor query performance
   - Add indexes for slow queries

3. **Cleanup Jobs**
   - Remove unused cached assets
   - Clean up expired temp files

## Security Considerations

1. **API Keys**
   - Use environment variables only
   - Rotate keys regularly
   - Monitor usage for anomalies

2. **CORS Configuration**
   - Restrict origins in production
   - Use specific domains instead of "*"

3. **Rate Limiting**
   - Implement rate limiting per user
   - Use Redis for distributed rate limiting

4. **Input Validation**
   - Validate all user inputs
   - Sanitize file uploads
   - Check file sizes and types

## Cost Optimization

1. **S3 Storage Classes**
   - Use Standard for active files
   - Move old files to IA or Glacier

2. **API Usage**
   - Monitor ElevenLabs usage
   - Optimize cache hit rates
   - Set usage alerts

3. **Database Optimization**
   - Monitor connection pool usage
   - Optimize expensive queries
   - Use read replicas if needed