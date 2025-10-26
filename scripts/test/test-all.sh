#!/bin/bash
#
# Master test runner - runs all tests in order
#
# Usage:
#   ./test-all.sh [--quick] [--component] [--e2e] [--verbose]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"

# Test modes
RUN_HEALTH=true
RUN_COMPONENT=true
RUN_E2E=true
export VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --quick)
      RUN_E2E=false
      shift
      ;;
    --component)
      RUN_E2E=false
      RUN_HEALTH=false
      shift
      ;;
    --e2e)
      RUN_COMPONENT=false
      RUN_HEALTH=false
      shift
      ;;
    --verbose|-v)
      export VERBOSE=true
      shift
      ;;
    *)
      shift
      ;;
  esac
done

START_TIME=$(timestamp)

section "Test Suite - Nighttime Story Prep"

info "Test mode:"
[ "$RUN_HEALTH" = "true" ] && echo "  ✓ Health checks"
[ "$RUN_COMPONENT" = "true" ] && echo "  ✓ Component tests"
[ "$RUN_E2E" = "true" ] && echo "  ✓ E2E tests"
echo ""

# Track results
declare -a PASSED_TESTS=()
declare -a FAILED_TESTS=()

run_test() {
  local test_name=$1
  local test_script=$2
  
  echo ""
  subsection "Running: $test_name"
  
  if "$SCRIPT_DIR/$test_script"; then
    PASSED_TESTS+=("$test_name")
    success "$test_name passed"
  else
    FAILED_TESTS+=("$test_name")
    error "$test_name failed"
    return 1
  fi
}

# Health tests
if [ "$RUN_HEALTH" = "true" ]; then
  section "Health Checks"
  
  run_test "Health Check" "test-health.sh" || true
fi

# Component tests
if [ "$RUN_COMPONENT" = "true" ]; then
  section "Component Tests"
  
  # Only run if Modal API is configured
  if [ -n "$MODAL_API_URL" ] && [ -n "$MODAL_API_KEY" ]; then
    run_test "Modal API" "test-modal-api.sh" || true
    run_test "Extraction" "test-extraction.sh" || true
    run_test "Chunking" "test-chunking.sh" || true
  else
    warning "Modal API not configured, skipping Modal tests"
    info "Set MODAL_API_URL and MODAL_API_KEY to run these tests"
  fi
  
  # Database and storage tests (require local setup)
  if [ -n "$DATABASE_URL" ]; then
    run_test "Database Operations" "test-database.sh" || true
    run_test "Storage Operations" "test-storage.sh" || true
  else
    warning "DATABASE_URL not set, skipping database tests"
  fi
fi

# E2E tests
if [ "$RUN_E2E" = "true" ]; then
  section "End-to-End Tests"
  
  if [ -n "$NEXT_PUBLIC_BASE_URL" ] || [ -n "$MODAL_API_URL" ]; then
    run_test "Email Webhook" "test-email-webhook.sh" || true
    run_test "Full Ingestion Pipeline" "test-ingest-e2e.sh" || true
  else
    warning "Services not configured, skipping E2E tests"
    info "Set NEXT_PUBLIC_BASE_URL and MODAL_API_URL to run these tests"
  fi
fi

# Summary
DURATION=$(duration_formatted $START_TIME)

echo ""
echo ""
section "Test Summary"

echo "Duration: $DURATION"
echo ""

if [ ${#PASSED_TESTS[@]} -gt 0 ]; then
  success "Passed tests (${#PASSED_TESTS[@]}):"
  for test in "${PASSED_TESTS[@]}"; do
    echo "  ✅ $test"
  done
  echo ""
fi

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
  error "Failed tests (${#FAILED_TESTS[@]}):"
  for test in "${FAILED_TESTS[@]}"; do
    echo "  ❌ $test"
  done
  echo ""
  
  section "❌ Some Tests Failed"
  exit 1
else
  section "✅ All Tests Passed"
  exit 0
fi

