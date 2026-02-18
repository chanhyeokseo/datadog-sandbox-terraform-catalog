#!/bin/bash
set -e

echo "Starting Terraform Web UI Backend..."

# Create terraform working directory if not exists
mkdir -p /app/terraform

# Check if instances data already exists
INSTANCES_EXIST=false
if [ -d "/app/terraform/instances" ] && [ -n "$(ls -A /app/terraform/instances 2>/dev/null)" ]; then
    INSTANCES_EXIST=true
fi

# Force re-initialization if requested
if [ "$FORCE_REINIT" = "true" ]; then
    echo "FORCE_REINIT=true - clearing existing data..."
    rm -rf /app/terraform/instances /app/terraform/apps
    INSTANCES_EXIST=false
fi

# Clone instances and modules using sparse checkout if needed
if [ "$INSTANCES_EXIST" = "true" ]; then
    echo "Using existing instances data from persistent volume"
    echo "Instances: $(ls -1 /app/terraform/instances 2>/dev/null | wc -l) directories"
else
    echo "Seeding terraform data from image..."
    if [ -d "/app/terraform-source/instances" ]; then
        cp -r /app/terraform-source/instances /app/terraform/
        echo "Instances ready: $(ls -1 /app/terraform/instances | wc -l) directories"
    else
        echo "WARNING: /app/terraform-source/instances not found in image"
    fi
    if [ -d "/app/terraform-source/apps" ]; then
        cp -r /app/terraform-source/apps /app/terraform/
        echo "Apps ready"
    fi
fi

echo "Loading configuration from Parameter Store..."
python3 -m app.init_config || echo "Config initialization skipped (first run or AWS credentials not available)"

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
