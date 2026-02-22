#!/bin/bash
set -e

echo "Starting Terraform Web UI Backend..."

mkdir -p /app/terraform /app/terraform/.plugin-cache

echo "Cleaning terraform-data (preserving .plugin-cache)..."
find /app/terraform -mindepth 1 -maxdepth 1 ! -name '.plugin-cache' -exec rm -rf {} +

# Sync modules and apps from image (skip if bind-mounted from host)
if mountpoint -q /app/terraform/modules 2>/dev/null; then
    echo "Modules: using bind mount ($(ls -1 /app/terraform/modules | wc -l) directories)"
elif [ -d "/app/terraform-source/modules" ]; then
    rm -rf /app/terraform/modules
    cp -r /app/terraform-source/modules /app/terraform/
    echo "Modules ready: $(ls -1 /app/terraform/modules | wc -l) directories"
fi
if mountpoint -q /app/terraform/apps 2>/dev/null; then
    echo "Apps: using bind mount"
elif [ -d "/app/terraform-source/apps" ]; then
    rm -rf /app/terraform/apps
    cp -r /app/terraform-source/apps /app/terraform/
    echo "Apps ready"
fi

echo "Seeding instances from image..."
if [ -d "/app/terraform-source/instances" ]; then
    cp -r /app/terraform-source/instances /app/terraform/
    echo "Instances ready: $(ls -1 /app/terraform/instances | wc -l) directories"
else
    echo "WARNING: /app/terraform-source/instances not found in image"
fi

echo "Loading configuration from Parameter Store..."
python3 -m app.init_config || echo "Config initialization skipped (first run or AWS credentials not available)"

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
