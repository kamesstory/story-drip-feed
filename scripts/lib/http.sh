#!/bin/bash
#
# HTTP utilities for test scripts
# Provides: HTTP request helpers, response parsing, retry logic
#

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# HTTP request wrapper with retries
http_request() {
  local method=$1
  local url=$2
  local data=$3
  local description=${4:-"HTTP request"}
  local retries=${5:-3}
  local retry_delay=${6:-2}
  
  subsection "$description"
  log "Request: $method $url"
  
  if [ -n "$data" ] && [ "${VERBOSE:-false}" = "true" ]; then
    info "Request body:"
    print_json "$data"
  fi
  
  local attempt=1
  while [ $attempt -le $retries ]; do
    debug "Attempt $attempt/$retries"
    
    local response
    local http_code
    
    if [ -n "$data" ]; then
      response=$(curl -s -w "\n%{http_code}" -X "$method" \
        -H "Content-Type: application/json" \
        -d "$data" \
        "$url" 2>&1)
    else
      response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" 2>&1)
    fi
    
    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    log "HTTP Status: $http_code"
    
    # Success codes (2xx)
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
      if [ "${VERBOSE:-false}" = "true" ]; then
        info "Response body:"
        print_json "$body"
      fi
      
      # Return both code and body (separated by newline)
      echo "$http_code"
      echo "$body"
      return 0
    fi
    
    # Client errors (4xx) - don't retry
    if [ "$http_code" -ge 400 ] && [ "$http_code" -lt 500 ]; then
      error "Client error (HTTP $http_code)"
      if [ "${VERBOSE:-false}" = "false" ]; then
        error "Response:"
        print_json "$body"
      fi
      
      echo "$http_code"
      echo "$body"
      return 1
    fi
    
    # Server errors (5xx) - retry
    if [ $attempt -lt $retries ]; then
      warning "Server error (HTTP $http_code), retrying in ${retry_delay}s..."
      sleep $retry_delay
      attempt=$((attempt + 1))
      continue
    fi
    
    error "Request failed after $retries attempts (HTTP $http_code)"
    error "Response:"
    print_json "$body"
    
    echo "$http_code"
    echo "$body"
    return 1
  done
}

# Parse JSON field from response
parse_json_field() {
  local json=$1
  local field=$2
  
  if command -v jq &> /dev/null; then
    echo "$json" | jq -r ".$field" 2>/dev/null || echo ""
  elif command -v python3 &> /dev/null; then
    echo "$json" | python3 -c "import sys, json; print(json.load(sys.stdin).get('$field', ''))" 2>/dev/null || echo ""
  else
    # Fallback to grep/sed (less reliable)
    echo "$json" | grep -o "\"$field\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | sed 's/.*"\([^"]*\)"/\1/'
  fi
}

# Parse nested JSON field (e.g., "metadata.title")
parse_json_nested() {
  local json=$1
  local path=$2
  
  if command -v jq &> /dev/null; then
    echo "$json" | jq -r ".$path" 2>/dev/null || echo ""
  else
    echo ""
  fi
}

# Check if JSON field exists
json_has_field() {
  local json=$1
  local field=$2
  
  if command -v jq &> /dev/null; then
    echo "$json" | jq -e "has(\"$field\")" > /dev/null 2>&1
    return $?
  else
    echo "$json" | grep -q "\"$field\""
    return $?
  fi
}

# HTTP GET helper
http_get() {
  local url=$1
  local description=${2:-"GET request"}
  local retries=${3:-3}
  
  http_request "GET" "$url" "" "$description" "$retries"
}

# HTTP POST helper
http_post() {
  local url=$1
  local data=$2
  local description=${3:-"POST request"}
  local retries=${4:-3}
  
  http_request "POST" "$url" "$data" "$description" "$retries"
}

# HTTP POST with authentication
http_post_auth() {
  local url=$1
  local data=$2
  local auth_token=$3
  local description=${4:-"POST request (authenticated)"}
  local retries=${5:-3}
  
  subsection "$description"
  log "Request: POST $url (with auth)"
  
  if [ -n "$data" ] && [ "${VERBOSE:-false}" = "true" ]; then
    info "Request body:"
    print_json "$data"
  fi
  
  local attempt=1
  while [ $attempt -le $retries ]; do
    debug "Attempt $attempt/$retries"
    
    local response
    local http_code
    
    response=$(curl -s -w "\n%{http_code}" -X POST \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $auth_token" \
      -d "$data" \
      "$url" 2>&1)
    
    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    log "HTTP Status: $http_code"
    
    # Success
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
      if [ "${VERBOSE:-false}" = "true" ]; then
        info "Response body:"
        print_json "$body"
      fi
      
      echo "$http_code"
      echo "$body"
      return 0
    fi
    
    # Client error - don't retry
    if [ "$http_code" -ge 400 ] && [ "$http_code" -lt 500 ]; then
      error "Client error (HTTP $http_code)"
      error "Response:"
      print_json "$body"
      
      echo "$http_code"
      echo "$body"
      return 1
    fi
    
    # Server error - retry
    if [ $attempt -lt $retries ]; then
      warning "Server error (HTTP $http_code), retrying in 2s..."
      sleep 2
      attempt=$((attempt + 1))
      continue
    fi
    
    error "Request failed after $retries attempts (HTTP $http_code)"
    
    echo "$http_code"
    echo "$body"
    return 1
  done
}

# Check if HTTP endpoint is healthy
check_endpoint_health() {
  local url=$1
  local service_name=${2:-"Service"}
  
  subsection "Checking $service_name health"
  log "GET $url"
  
  local response=$(curl -s -w "\n%{http_code}" "$url")
  local http_code=$(echo "$response" | tail -n1)
  local body=$(echo "$response" | sed '$d')
  
  if [ "$http_code" = "200" ]; then
    success "$service_name is healthy (HTTP 200)"
    if [ "${VERBOSE:-false}" = "true" ]; then
      print_json "$body"
    fi
    return 0
  else
    error "$service_name health check failed (HTTP $http_code)"
    if [ "${VERBOSE:-false}" = "false" ]; then
      error "Response:"
      print_json "$body"
    fi
    return 1
  fi
}

# Export functions
export -f http_request http_get http_post http_post_auth
export -f parse_json_field parse_json_nested json_has_field
export -f check_endpoint_health

