#!/bin/bash
#
# Database utilities for test scripts
# Provides: Supabase query helpers, verification functions
#

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check if DATABASE_URL is set
check_database_connection() {
  if [ -z "$DATABASE_URL" ]; then
    error "DATABASE_URL environment variable is not set"
    info "This should be your Supabase PostgreSQL connection string"
    return 1
  fi
  
  debug "DATABASE_URL is set"
  return 0
}

# Execute SQL query
query_db() {
  local sql=$1
  
  if ! check_database_connection; then
    return 1
  fi
  
  debug "Executing SQL: $sql"
  
  psql "$DATABASE_URL" -t -A -c "$sql" 2>&1
  return $?
}

# Execute SQL query with formatting
query_db_formatted() {
  local sql=$1
  
  if ! check_database_connection; then
    return 1
  fi
  
  debug "Executing SQL: $sql"
  
  psql "$DATABASE_URL" -c "$sql" 2>&1
  return $?
}

# Get story by ID
get_story() {
  local story_id=$1
  
  local sql="SELECT id, email_id, title, author, source, status, word_count, extraction_method, received_at, processed_at FROM stories WHERE id = $story_id;"
  
  query_db_formatted "$sql"
}

# Get story status
get_story_status() {
  local story_id=$1
  
  local sql="SELECT status FROM stories WHERE id = $story_id;"
  
  query_db "$sql" | tr -d ' '
}

# Get story title
get_story_title() {
  local story_id=$1
  
  local sql="SELECT title FROM stories WHERE id = $story_id;"
  
  query_db "$sql" | tr -d ' '
}

# Check if story exists
story_exists() {
  local story_id=$1
  
  local sql="SELECT COUNT(*) FROM stories WHERE id = $story_id;"
  local count=$(query_db "$sql" | tr -d ' ')
  
  [ "$count" -gt 0 ]
  return $?
}

# Get chunks for story
get_story_chunks() {
  local story_id=$1
  
  local sql="SELECT id, chunk_number, total_chunks, word_count, CASE WHEN sent_to_kindle_at IS NULL THEN 'PENDING' ELSE 'SENT' END as status, sent_to_kindle_at FROM story_chunks WHERE story_id = $story_id ORDER BY chunk_number;"
  
  query_db_formatted "$sql"
}

# Count chunks for story
count_story_chunks() {
  local story_id=$1
  
  local sql="SELECT COUNT(*) FROM story_chunks WHERE story_id = $story_id;"
  
  query_db "$sql" | tr -d ' '
}

# Get latest story ID
get_latest_story_id() {
  local sql="SELECT id FROM stories ORDER BY received_at DESC LIMIT 1;"
  
  query_db "$sql" | tr -d ' '
}

# List recent stories
list_recent_stories() {
  local limit=${1:-10}
  
  local sql="SELECT id, title, status, word_count, received_at FROM stories ORDER BY received_at DESC LIMIT $limit;"
  
  query_db_formatted "$sql"
}

# List stories with test prefix
list_test_stories() {
  local limit=${1:-50}
  
  local sql="SELECT id, email_id, title, status, word_count, received_at FROM stories WHERE email_id LIKE 'test-%' ORDER BY received_at DESC LIMIT $limit;"
  
  query_db_formatted "$sql"
}

# Get next unsent chunk
get_next_unsent_chunk() {
  local sql="SELECT sc.id, sc.story_id, s.title, sc.chunk_number, sc.total_chunks FROM story_chunks sc JOIN stories s ON sc.story_id = s.id WHERE sc.sent_to_kindle_at IS NULL AND s.status = 'chunked' ORDER BY sc.created_at ASC, sc.chunk_number ASC LIMIT 1;"
  
  query_db_formatted "$sql"
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

