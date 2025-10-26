#!/bin/bash
#
# Database utilities for test scripts
# Provides: Supabase query helpers, verification functions
# Uses Supabase REST API (no DATABASE_URL needed!)
#

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check if Supabase credentials are set
check_database_connection() {
  if [ -z "$NEXT_PUBLIC_SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    error "Supabase credentials not set"
    info "Required: NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY"
    info "These should be in your nextjs-app/.env.local file"
    return 1
  fi
  
  debug "Supabase credentials found"
  return 0
}

# Query Supabase via REST API
supabase_query() {
  local table=$1
  local query_params=$2
  
  if ! check_database_connection; then
    return 1
  fi
  
  local url="${NEXT_PUBLIC_SUPABASE_URL}/rest/v1/${table}?${query_params}"
  
  debug "Querying: $url"
  
  curl -s -X GET "$url" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json"
}

# For custom SQL queries, we still need DATABASE_URL or psql
# This is a fallback for complex queries
query_db() {
  local sql=$1
  
  if [ -n "$DATABASE_URL" ]; then
    debug "Using DATABASE_URL for query: $sql"
    psql "$DATABASE_URL" -t -A -c "$sql" 2>&1
    return $?
  else
    warning "DATABASE_URL not set - complex SQL queries not available"
    warning "Use specific functions like get_story(), list_stories(), etc."
    return 1
  fi
}

# Execute SQL query with formatting (requires DATABASE_URL)
query_db_formatted() {
  local sql=$1
  
  if [ -n "$DATABASE_URL" ]; then
    debug "Using DATABASE_URL for formatted query: $sql"
    psql "$DATABASE_URL" -c "$sql" 2>&1
    return $?
  else
    warning "DATABASE_URL not set - formatted queries not available"
    warning "Set DATABASE_URL for custom SQL queries"
    return 1
  fi
}

# Get story by ID (using Supabase REST API)
get_story() {
  local story_id=$1
  
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "stories" "id=eq.${story_id}&select=*")
  
  if command -v jq &> /dev/null; then
    echo "$result" | jq -r '.[0] | "ID: \(.id)\nEmail ID: \(.email_id)\nTitle: \(.title)\nAuthor: \(.author // "N/A")\nStatus: \(.status)\nWord Count: \(.word_count // 0)\nReceived: \(.received_at)\nProcessed: \(.processed_at // "N/A")"'
  else
    echo "$result"
  fi
}

# Get story status (using Supabase REST API)
get_story_status() {
  local story_id=$1
  
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "stories" "id=eq.${story_id}&select=status")
  
  if command -v jq &> /dev/null; then
    echo "$result" | jq -r '.[0].status // ""'
  else
    echo "$result" | grep -o '"status":"[^"]*"' | cut -d'"' -f4
  fi
}

# Get story title (using Supabase REST API)
get_story_title() {
  local story_id=$1
  
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "stories" "id=eq.${story_id}&select=title")
  
  if command -v jq &> /dev/null; then
    echo "$result" | jq -r '.[0].title // ""'
  else
    echo "$result" | grep -o '"title":"[^"]*"' | cut -d'"' -f4
  fi
}

# Check if story exists (using Supabase REST API)
story_exists() {
  local story_id=$1
  
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "stories" "id=eq.${story_id}&select=id")
  
  if command -v jq &> /dev/null; then
    local count=$(echo "$result" | jq 'length')
    [ "$count" -gt 0 ]
  else
    echo "$result" | grep -q "\"id\":"
  fi
  
  return $?
}

# Get chunks for story (using Supabase REST API)
get_story_chunks() {
  local story_id=$1
  
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "story_chunks" "story_id=eq.${story_id}&select=*&order=chunk_number.asc")
  
  if command -v jq &> /dev/null; then
    echo "ID | Chunk | Total | Words | Status | Sent At"
    echo "---|-------|-------|-------|--------|--------"
    echo "$result" | jq -r '.[] | "\(.id) | \(.chunk_number)/\(.total_chunks) | \(.total_chunks) | \(.word_count) | \(if .sent_to_kindle_at then "SENT" else "PENDING" end) | \(.sent_to_kindle_at // "N/A")"'
  else
    echo "$result"
  fi
}

# Count chunks for story (using Supabase REST API)
count_story_chunks() {
  local story_id=$1
  
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "story_chunks" "story_id=eq.${story_id}&select=id")
  
  if command -v jq &> /dev/null; then
    echo "$result" | jq 'length'
  else
    echo "$result" | grep -o '"id"' | wc -l | tr -d ' '
  fi
}

# Get latest story ID (using Supabase REST API)
get_latest_story_id() {
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "stories" "select=id&order=received_at.desc&limit=1")
  
  if command -v jq &> /dev/null; then
    echo "$result" | jq -r '.[0].id // ""'
  else
    echo "$result" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2
  fi
}

# List recent stories (using Supabase REST API)
list_recent_stories() {
  local limit=${1:-10}
  
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "stories" "select=id,title,status,word_count,received_at&order=received_at.desc&limit=${limit}")
  
  if command -v jq &> /dev/null; then
    echo "ID | Title | Status | Words | Received"
    echo "---|-------|--------|-------|----------"
    echo "$result" | jq -r '.[] | "\(.id) | \(.title) | \(.status) | \(.word_count // 0) | \(.received_at)"'
  else
    echo "$result"
  fi
}

# List stories with test prefix (using Supabase REST API)
list_test_stories() {
  local limit=${1:-50}
  
  if ! check_database_connection; then
    return 1
  fi
  
  local result=$(supabase_query "stories" "select=id,email_id,title,status,word_count,received_at&email_id=like.test-*&order=received_at.desc&limit=${limit}")
  
  if command -v jq &> /dev/null; then
    echo "ID | Email ID | Title | Status | Words | Received"
    echo "---|----------|-------|--------|-------|----------"
    echo "$result" | jq -r '.[] | "\(.id) | \(.email_id) | \(.title) | \(.status) | \(.word_count // 0) | \(.received_at)"'
  else
    echo "$result"
  fi
}

# Get next unsent chunk (requires DATABASE_URL for JOIN query)
get_next_unsent_chunk() {
  if [ -n "$DATABASE_URL" ]; then
    local sql="SELECT sc.id, sc.story_id, s.title, sc.chunk_number, sc.total_chunks FROM story_chunks sc JOIN stories s ON sc.story_id = s.id WHERE sc.sent_to_kindle_at IS NULL AND s.status = 'chunked' ORDER BY sc.created_at ASC, sc.chunk_number ASC LIMIT 1;"
    query_db_formatted "$sql"
  else
    # Fallback: get unsent chunks without JOIN (simplified)
    if ! check_database_connection; then
      return 1
    fi
    
    local result=$(supabase_query "story_chunks" "select=id,story_id,chunk_number,total_chunks&sent_to_kindle_at=is.null&order=created_at.asc&limit=1")
    
    if command -v jq &> /dev/null; then
      echo "$result" | jq -r '.[] | "ID: \(.id) | Story: \(.story_id) | Chunk: \(.chunk_number)/\(.total_chunks)"'
    else
      echo "$result"
    fi
    
    warning "Use DATABASE_URL for full details including story title"
  fi
}

# Verify story exists
verify_story_exists() {
  local story_id=$1
  
  if story_exists "$story_id"; then
    success "Story $story_id exists"
    return 0
  else
    error "Story $story_id does not exist"
    return 1
  fi
}

# Verify story status
verify_story_status() {
  local story_id=$1
  local expected_status=$2
  
  local actual_status=$(get_story_status "$story_id")
  
  if [ "$actual_status" = "$expected_status" ]; then
    success "Story $story_id status is '$expected_status'"
    return 0
  else
    error "Story $story_id status is '$actual_status', expected '$expected_status'"
    return 1
  fi
}

# Verify chunks were created
verify_chunks_created() {
  local story_id=$1
  local expected_count=${2:-}
  
  local actual_count=$(count_story_chunks "$story_id")
  
  if [ "$actual_count" -gt 0 ]; then
    if [ -n "$expected_count" ]; then
      if [ "$actual_count" = "$expected_count" ]; then
        success "Story $story_id has $actual_count chunk(s) (expected $expected_count)"
        return 0
      else
        error "Story $story_id has $actual_count chunk(s), expected $expected_count"
        return 1
      fi
    else
      success "Story $story_id has $actual_count chunk(s)"
      return 0
    fi
  else
    error "Story $story_id has no chunks"
    return 1
  fi
}

# Wait for story status to change
wait_for_story_status() {
  local story_id=$1
  local expected_status=$2
  local max_wait=${3:-120}
  local check_interval=${4:-3}
  
  log "Waiting for story $story_id to reach status '$expected_status' (max ${max_wait}s)..."
  
  local elapsed=0
  while [ $elapsed -lt $max_wait ]; do
    local current_status=$(get_story_status "$story_id")
    
    if [ "$current_status" = "$expected_status" ]; then
      success "Story $story_id reached status '$expected_status' after ${elapsed}s"
      return 0
    fi
    
    # Check for failed status
    if [ "$current_status" = "failed" ] && [ "$expected_status" != "failed" ]; then
      error "Story $story_id failed during processing"
      return 1
    fi
    
    debug "Current status: $current_status (waiting for $expected_status)"
    
    sleep $check_interval
    elapsed=$((elapsed + check_interval))
    
    # Print progress every 15 seconds
    if [ $((elapsed % 15)) -eq 0 ]; then
      log "Still waiting... (${elapsed}s elapsed, status: $current_status)"
    fi
  done
  
  error "Timeout: Story $story_id did not reach status '$expected_status' after ${max_wait}s"
  local final_status=$(get_story_status "$story_id")
  error "Final status: $final_status"
  return 1
}

# Delete test stories (cleanup)
delete_test_stories() {
  local sql="DELETE FROM stories WHERE email_id LIKE 'test-%';"
  
  warning "Deleting test stories..."
  query_db "$sql"
  
  success "Test stories deleted"
}

# Get database stats
get_db_stats() {
  local sql="
    SELECT 
      (SELECT COUNT(*) FROM stories) as total_stories,
      (SELECT COUNT(*) FROM stories WHERE status = 'pending') as pending_stories,
      (SELECT COUNT(*) FROM stories WHERE status = 'processing') as processing_stories,
      (SELECT COUNT(*) FROM stories WHERE status = 'chunked') as chunked_stories,
      (SELECT COUNT(*) FROM stories WHERE status = 'failed') as failed_stories,
      (SELECT COUNT(*) FROM story_chunks) as total_chunks,
      (SELECT COUNT(*) FROM story_chunks WHERE sent_to_kindle_at IS NULL) as unsent_chunks;
  "
  
  query_db_formatted "$sql"
}

# Export functions
export -f check_database_connection query_db query_db_formatted
export -f get_story get_story_status get_story_title story_exists
export -f get_story_chunks count_story_chunks
export -f get_latest_story_id list_recent_stories list_test_stories
export -f get_next_unsent_chunk
export -f verify_story_exists verify_story_status verify_chunks_created
export -f wait_for_story_status
export -f delete_test_stories get_db_stats

