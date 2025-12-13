#!/bin/bash

# SubliminalGen Backend - Endpoint Testing Script
BASE_URL="https://subliminalgen-backend-311287456014.us-central1.run.app"

echo "🧪 Testing SubliminalGen Backend Endpoints"
echo "🌐 Base URL: $BASE_URL"
echo ""

# Test 1: Root endpoint
echo "1️⃣ Testing root endpoint..."
curl -s "$BASE_URL/" | jq '.'
echo ""

# Test 2: Health check
echo "2️⃣ Testing health endpoint..."
curl -s "$BASE_URL/health" | jq '.'
echo ""

# Test 3: Music generation endpoint (should require auth)
echo "3️⃣ Testing music generation endpoint..."
curl -s -X POST "$BASE_URL/api/music/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "relaxing meditation music", "duration": 30}' | jq '.'
echo ""

# Test 4: Auth signup endpoint (test with dummy data)
echo "4️⃣ Testing auth signup endpoint..."
curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123", "name": "Test User"}' | jq '.'
echo ""

echo "✅ Endpoint testing complete!"
echo ""
echo "📋 Available endpoints:"
echo "  GET  $BASE_URL/"
echo "  GET  $BASE_URL/health"
echo "  POST $BASE_URL/auth/signup"
echo "  POST $BASE_URL/auth/signin"
echo "  POST $BASE_URL/auth/google"
echo "  POST $BASE_URL/api/music/generate"
echo "  POST $BASE_URL/api/music/{user_id}"
echo ""
echo "🔗 Service URL: $BASE_URL"