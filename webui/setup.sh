#!/bin/bash

# Setup script for Terraform Web UI persistent storage
# This script creates and configures the /etc/dogstac directory for persistent data storage

set -e

STORAGE_PATH="${TERRAFORM_DATA_PATH:-/etc/dogstac}"

echo "Setting up persistent storage at: $STORAGE_PATH"

# Check if directory already exists
if [ -d "$STORAGE_PATH" ]; then
    echo "Directory $STORAGE_PATH already exists"

    # Check if we have write permissions
    if [ -w "$STORAGE_PATH" ]; then
        echo "Write permissions OK"
    else
        echo "No write permissions. Attempting to fix..."
        sudo chown -R $USER:$USER "$STORAGE_PATH"
        echo "Permissions updated"
    fi
else
    # Create directory
    if [[ "$STORAGE_PATH" == /etc/* ]]; then
        # System directory requires sudo
        echo "Creating system directory (requires sudo)..."
        sudo mkdir -p "$STORAGE_PATH"
        sudo chown -R $USER:$USER "$STORAGE_PATH"
    else
        # Regular directory
        echo "Creating directory..."
        mkdir -p "$STORAGE_PATH"
    fi
    echo "Directory created successfully"
fi

# Verify permissions
if [ -w "$STORAGE_PATH" ]; then
    echo "Setup complete! Storage path: $STORAGE_PATH"
    echo "You can now start the services with: docker-compose up -d"
else
    echo "Error: Unable to set write permissions on $STORAGE_PATH"
    exit 1
fi
