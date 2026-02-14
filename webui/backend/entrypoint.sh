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
    rm -rf /app/terraform/instances
    INSTANCES_EXIST=false
fi

# Clone instances and modules using sparse checkout if needed
if [ "$INSTANCES_EXIST" = "true" ]; then
    echo "Using existing instances data from persistent volume"
    echo "Instances: $(ls -1 /app/terraform/instances 2>/dev/null | wc -l) directories"
elif [ -n "$INSTANCES_REPO_URL" ]; then
    echo "First run detected - cloning from $INSTANCES_REPO_URL"

    # Remove any partial/corrupted directories
    rm -rf /app/terraform/instances

    # Initialize git repository with sparse checkout
    mkdir -p /tmp/sparse-repo
    cd /tmp/sparse-repo
    git init
    git remote add origin "$INSTANCES_REPO_URL"

    # Enable sparse checkout
    git config core.sparseCheckout true

    # Specify directories to checkout
    echo "instances/" >> .git/info/sparse-checkout
    echo "apps/" >> .git/info/sparse-checkout

    # Get the branch to use (default to webui if not specified)
    REPO_BRANCH="${INSTANCES_REPO_BRANCH:-webui}"

    # Fetch and checkout
    if git fetch --depth=1 origin "$REPO_BRANCH" && git checkout "$REPO_BRANCH"; then
        echo "Successfully cloned from $REPO_BRANCH branch"

        # Copy to terraform directory
        if [ -d "instances" ]; then
            cp -r instances /app/terraform/
            echo "Instances ready: $(ls -1 /app/terraform/instances | wc -l) directories"
        fi

        if [ -d "apps" ]; then
            cp -r apps /app/terraform/
            echo "Apps ready"
        fi

        echo "Data persisted to volume - will be reused on next startup"
    else
        echo "Failed to clone repository"
        echo "Container will continue with empty/existing terraform directory"
    fi

    # Cleanup
    cd /app
    rm -rf /tmp/sparse-repo
else
    echo "INSTANCES_REPO_URL not set - using built-in or existing instances"
fi

# Load configuration from Parameter Store if available
echo "Loading configuration from Parameter Store..."
python3 -m app.init_config || echo "Config initialization skipped (first run or AWS credentials not available)"

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
