#!/bin/bash
# Load .env file and update Modal secrets

if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi

# Update Modal secret from .env file
poetry run modal secret create story-prep-secrets --force --from-dotenv .env

echo "✓ Modal secrets updated successfully"
