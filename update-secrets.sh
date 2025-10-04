#!/bin/bash
# Load .env file and update Modal secrets

if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi

# Source the .env file
export $(cat .env | grep -v '^#' | xargs)

# Update Modal secret
modal secret create story-prep-secrets \
  --force \
  KINDLE_EMAIL="$KINDLE_EMAIL" \
  SMTP_HOST="$SMTP_HOST" \
  SMTP_PORT="$SMTP_PORT" \
  SMTP_USER="$SMTP_USER" \
  SMTP_PASSWORD="$SMTP_PASSWORD" \
  TEST_MODE="${TEST_MODE:-false}"

echo "✓ Modal secrets updated successfully"
