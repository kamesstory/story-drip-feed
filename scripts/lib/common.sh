#!/bin/bash
#
# Common utilities for test scripts
# Provides: colors, logging, timestamps, formatting helpers
#

# Colors
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export CYAN='\033[0;36m'
export MAGENTA='\033[0;35m'
export NC='\033[0m' # No Color

# Logging functions
log() {
  echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $1"
}

success() {
  echo -e "${GREEN}✅ $1${NC}"
}

error() {
  echo -e "${RED}❌ $1${NC}"
}

warning() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

info() {
  echo -e "${BLUE}ℹ️  $1${NC}"
}

debug() {
  if [ "${VERBOSE:-false}" = "true" ]; then
    echo -e "${MAGENTA}[DEBUG]${NC} $1"
  fi
}

# Section headers
section() {
  echo ""
  echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}$1${NC}"
  echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
  echo ""
}

subsection() {
  echo ""
  echo -e "${YELLOW}─── $1 ───${NC}"
}

# Format JSON prettily
print_json() {
  local json=$1
  if command -v jq &> /dev/null; then
    echo "$json" | jq '.' 2>/dev/null || echo "$json"
  elif command -v python3 &> /dev/null; then
    echo "$json" | python3 -m json.tool 2>/dev/null || echo "$json"
  else
    echo "$json"
  fi
}

# Generate timestamp
timestamp() {
  date +%s
}

timestamp_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Generate test ID
generate_test_id() {
  echo "test-$(timestamp)"
}

# Check if a command exists
command_exists() {
  command -v "$1" &> /dev/null
}

# Check if service is running at URL
is_service_running() {
  local url=$1
  curl -sf "$url" > /dev/null 2>&1
}

# Wait for service to be ready
wait_for_service() {
  local url=$1
  local service_name=$2
  local max_attempts=${3:-30}
  local attempt=1
  
  log "Waiting for $service_name to be ready..."
  
  while [ $attempt -le $max_attempts ]; do
    if curl -sf "$url" > /dev/null 2>&1; then
      success "$service_name is ready"
      return 0
    fi
    
    if [ $attempt -eq $max_attempts ]; then
      error "$service_name did not become ready after $max_attempts attempts"
      return 1
    fi
    
    sleep 1
    attempt=$((attempt + 1))
  done
}

# Check required environment variables
check_env_var() {
  local var_name=$1
  local var_value="${!var_name}"
  
  if [ -z "$var_value" ]; then
    error "Required environment variable $var_name is not set"
    return 1
  fi
  
  debug "$var_name is set"
  return 0
}

check_required_env() {
  local missing=0
  
  for var in "$@"; do
    if ! check_env_var "$var"; then
      missing=1
    fi
  done
  
  return $missing
}

# Load environment variables from file
load_env_file() {
  local env_file=$1
  
  if [ ! -f "$env_file" ]; then
    warning "Environment file not found: $env_file"
    return 1
  fi
  
  debug "Loading environment from $env_file"
  
  # Export variables from .env file (skip comments and empty lines)
  while IFS='=' read -r key value; do
    # Skip comments and empty lines
    if [[ $key =~ ^[[:space:]]*# ]] || [[ -z $key ]]; then
      continue
    fi
    
    # Remove quotes from value
    value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    
    # Export the variable
    export "$key=$value"
    debug "Loaded $key"
  done < "$env_file"
  
  return 0
}

# Calculate duration
duration_seconds() {
  local start=$1
  local end=${2:-$(date +%s)}
  echo $((end - start))
}

duration_formatted() {
  local seconds=$(duration_seconds "$@")
  
  if [ $seconds -lt 60 ]; then
    echo "${seconds}s"
  elif [ $seconds -lt 3600 ]; then
    echo "$((seconds / 60))m $((seconds % 60))s"
  else
    echo "$((seconds / 3600))h $(((seconds % 3600) / 60))m"
  fi
}

# Cleanup function registration
declare -a CLEANUP_FUNCTIONS=()

register_cleanup() {
  CLEANUP_FUNCTIONS+=("$1")
}

run_cleanup() {
  for cleanup_fn in "${CLEANUP_FUNCTIONS[@]}"; do
    debug "Running cleanup: $cleanup_fn"
    $cleanup_fn
  done
}

# Set up trap for cleanup
trap run_cleanup EXIT

# Export functions so they can be used in subshells
export -f log success error warning info debug
export -f section subsection print_json
export -f timestamp timestamp_iso generate_test_id
export -f command_exists is_service_running wait_for_service
export -f check_env_var check_required_env load_env_file
export -f duration_seconds duration_formatted

