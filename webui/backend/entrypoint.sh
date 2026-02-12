#!/bin/bash
set -e

echo "🚀 Starting Terraform Web UI Backend..."

# Create terraform working directory if not exists
mkdir -p /app/terraform/instances

# Clone instances repository if INSTANCES_REPO_URL is provided
if [ -n "$INSTANCES_REPO_URL" ]; then
    echo "📦 Cloning instances from: $INSTANCES_REPO_URL"

    # Remove existing instances if any
    rm -rf /app/terraform/instances/*

    # Clone the repository
    if git clone "$INSTANCES_REPO_URL" /tmp/instances-repo; then
        echo "✅ Successfully cloned instances repository"

        # Copy instances to terraform directory
        if [ -d "/tmp/instances-repo/instances" ]; then
            cp -r /tmp/instances-repo/instances/* /app/terraform/instances/
        else
            # If repo root has the instance folders directly
            cp -r /tmp/instances-repo/* /app/terraform/instances/
        fi

        # Cleanup
        rm -rf /tmp/instances-repo

        echo "✅ Instances ready: $(ls -1 /app/terraform/instances | wc -l) directories"
    else
        echo "⚠️  Failed to clone instances repository"
    fi
else
    echo "⚠️  INSTANCES_REPO_URL not set - instances directory will be empty"
fi

# Load configuration from Parameter Store if available
echo "🔄 Loading configuration from Parameter Store..."
python3 -m app.init_config || echo "⚠️  Config initialization skipped (first run or AWS credentials not available)"

echo "🌐 Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
