#!/bin/bash
set -e

echo "🚀 Starting Terraform Web UI Backend..."

# Create terraform working directory if not exists
mkdir -p /app/terraform

# Clone instances and modules using sparse checkout if INSTANCES_REPO_URL is provided
if [ -n "$INSTANCES_REPO_URL" ]; then
    echo "📦 Sparse cloning instances and modules from: $INSTANCES_REPO_URL"

    # Remove existing directories if any
    rm -rf /app/terraform/instances /app/terraform/modules

    # Initialize git repository with sparse checkout
    mkdir -p /tmp/sparse-repo
    cd /tmp/sparse-repo
    git init
    git remote add origin "$INSTANCES_REPO_URL"

    # Enable sparse checkout
    git config core.sparseCheckout true

    # Specify directories to checkout
    echo "instances/" >> .git/info/sparse-checkout
    echo "modules/" >> .git/info/sparse-checkout

    # Get the branch to use (default to webui if not specified)
    REPO_BRANCH="${INSTANCES_REPO_BRANCH:-webui}"

    # Fetch and checkout
    if git fetch --depth=1 origin "$REPO_BRANCH" && git checkout "$REPO_BRANCH"; then
        echo "✅ Successfully sparse cloned from $REPO_BRANCH branch"

        # Copy to terraform directory
        if [ -d "instances" ]; then
            cp -r instances /app/terraform/
            echo "✅ Instances ready: $(ls -1 /app/terraform/instances | wc -l) directories"
        fi

        if [ -d "modules" ]; then
            cp -r modules /app/terraform/
            echo "✅ Modules ready: $(ls -1 /app/terraform/modules | wc -l) directories"
        fi
    else
        echo "⚠️  Failed to sparse clone repository"
    fi

    # Cleanup
    cd /app
    rm -rf /tmp/sparse-repo
else
    echo "⚠️  INSTANCES_REPO_URL not set - using built-in instances/modules"
    # If instances/modules are baked into the image, they'll already be there
fi

# Load configuration from Parameter Store if available
echo "🔄 Loading configuration from Parameter Store..."
python3 -m app.init_config || echo "⚠️  Config initialization skipped (first run or AWS credentials not available)"

echo "🌐 Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
