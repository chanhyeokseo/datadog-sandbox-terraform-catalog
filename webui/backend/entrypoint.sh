#!/bin/bash
set -e

echo "🚀 Starting Terraform Web UI Backend..."

cd /terraform

echo "📦 Initializing Terraform with upgrade..."
terraform init -upgrade -no-color

cd /app

echo "🌐 Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
