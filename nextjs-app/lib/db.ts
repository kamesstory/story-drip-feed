import { getSupabaseClient } from './supabase';
import type {
  Story,
  StoryChunk,
  StoryStatus,
  CreateStoryInput,
  CreateChunkInput,
  UpdateStoryStatusInput,
  UpdateStoryMetadataInput,
} from '@/types';

/**
 * Create a new story record
 */
export async function createStory(input: CreateStoryInput): Promise<Story> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('stories')
    .insert({
      email_id: input.email_id,
      title: input.title || null,
      author: input.author || null,
      source: input.source || 'email',
      extraction_method: input.extraction_method || null,
      status: 'pending',
      received_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to create story: ${error.message}`);
  }

  return data;
}

/**
 * Update story status with optional error message and processed timestamp
 */
export async function updateStoryStatus(
  storyId: number,
  status: StoryStatus,
  errorMessage?: string | null
): Promise<Story> {
  const supabase = getSupabaseClient();
  
  const updates: UpdateStoryStatusInput & { processed_at?: string } = {
    status,
    error_message: errorMessage || null,
  };

  // Set processed_at timestamp for chunked status
  if (status === 'chunked') {
    updates.processed_at = new Date().toISOString();
  }

  const { data, error } = await supabase
    .from('stories')
    .update(updates)
    .eq('id', storyId)
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to update story status: ${error.message}`);
  }

  return data;
}

/**
 * Update story metadata (title, author, word count, extraction method)
 */
export async function updateStoryMetadata(
  storyId: number,
  metadata: UpdateStoryMetadataInput
): Promise<Story> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('stories')
    .update(metadata)
    .eq('id', storyId)
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to update story metadata: ${error.message}`);
  }

  return data;
}

/**
 * Increment retry count for a failed story
 */
export async function incrementRetryCount(storyId: number): Promise<void> {
  const supabase = getSupabaseClient();
  
  const { error } = await supabase.rpc('increment_retry_count', {
    story_id: storyId,
  });

  if (error) {
    // If the function doesn't exist, do it manually
    const { data: story } = await supabase
      .from('stories')
      .select('retry_count')
      .eq('id', storyId)
      .single();
    
    if (story) {
      await supabase
        .from('stories')
        .update({ retry_count: story.retry_count + 1 })
        .eq('id', storyId);
    }
  }
}

/**
 * Create a story chunk record
 */
export async function createChunk(input: CreateChunkInput): Promise<StoryChunk> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('story_chunks')
    .insert({
      story_id: input.story_id,
      chunk_number: input.chunk_number,
      total_chunks: input.total_chunks,
      chunk_text: input.chunk_text,
      word_count: input.word_count || null,
      storage_path: input.storage_path || null,
    })
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to create chunk: ${error.message}`);
  }

  return data;
}

/**
 * Mark a chunk as sent to Kindle
 */
export async function markChunkSent(chunkId: number): Promise<StoryChunk> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('story_chunks')
    .update({
      sent_to_kindle_at: new Date().toISOString(),
    })
    .eq('id', chunkId)
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to mark chunk as sent: ${error.message}`);
  }

  return data;
}

/**
 * Get the next unsent chunk (earliest created, not yet sent)
 */
export async function getNextUnsentChunk(): Promise<(StoryChunk & { title: string | null; author: string | null }) | null> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('story_chunks')
    .select(`
      *,
      story:stories!inner(title, author)
    `)
    .is('sent_to_kindle_at', null)
    .eq('story.status', 'chunked')
    .order('created_at', { ascending: true })
    .order('chunk_number', { ascending: true })
    .limit(1)
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      // No rows found
      return null;
    }
    throw new Error(`Failed to get next unsent chunk: ${error.message}`);
  }

  // Flatten the nested story data
  const story = data.story as { title: string | null; author: string | null };
  const { story: _, ...chunk } = data as any;
  
  return {
    ...chunk,
    title: story.title,
    author: story.author,
  };
}

/**
 * Get a story by ID
 */
export async function getStoryById(storyId: number): Promise<Story | null> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('stories')
    .select('*')
    .eq('id', storyId)
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      return null;
    }
    throw new Error(`Failed to get story: ${error.message}`);
  }

  return data;
}

/**
 * Get a story by email ID
 */
export async function getStoryByEmailId(emailId: string): Promise<Story | null> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('stories')
    .select('*')
    .eq('email_id', emailId)
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      return null;
    }
    throw new Error(`Failed to get story by email ID: ${error.message}`);
  }

  return data;
}

/**
 * Get all chunks for a story
 */
export async function getStoryChunks(storyId: number): Promise<StoryChunk[]> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('story_chunks')
    .select('*')
    .eq('story_id', storyId)
    .order('chunk_number', { ascending: true });

  if (error) {
    throw new Error(`Failed to get story chunks: ${error.message}`);
  }

  return data || [];
}

/**
 * Get a specific chunk by ID
 */
export async function getChunkById(chunkId: number): Promise<StoryChunk | null> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('story_chunks')
    .select('*')
    .eq('id', chunkId)
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      return null;
    }
    throw new Error(`Failed to get chunk: ${error.message}`);
  }

  return data;
}

/**
 * Get all stories with optional limit
 */
export async function getAllStories(limit: number = 50): Promise<Story[]> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('stories')
    .select('*')
    .order('received_at', { ascending: false })
    .limit(limit);

  if (error) {
    throw new Error(`Failed to get all stories: ${error.message}`);
  }

  return data || [];
}

/**
 * Get pending stories
 */
export async function getPendingStories(): Promise<Story[]> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('stories')
    .select('*')
    .eq('status', 'pending')
    .order('received_at', { ascending: true });

  if (error) {
    throw new Error(`Failed to get pending stories: ${error.message}`);
  }

  return data || [];
}

/**
 * Get failed stories that haven't exceeded max retries
 */
export async function getFailedStories(maxRetries: number = 3): Promise<Story[]> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase
    .from('stories')
    .select('*')
    .eq('status', 'failed')
    .lt('retry_count', maxRetries)
    .order('received_at', { ascending: false });

  if (error) {
    throw new Error(`Failed to get failed stories: ${error.message}`);
  }

  return data || [];
}

/**
 * Delete a story and all its chunks (cascades automatically)
 */
export async function deleteStory(storyId: number): Promise<boolean> {
  const supabase = getSupabaseClient();
  
  const { error } = await supabase
    .from('stories')
    .delete()
    .eq('id', storyId);

  if (error) {
    throw new Error(`Failed to delete story: ${error.message}`);
  }

  return true;
}

/**
 * Reset chunk status (mark as unsent for re-testing)
 */
export async function resetChunkStatus(chunkId: number): Promise<boolean> {
  const supabase = getSupabaseClient();
  
  const { error } = await supabase
    .from('story_chunks')
    .update({ sent_to_kindle_at: null })
    .eq('id', chunkId);

  if (error) {
    throw new Error(`Failed to reset chunk status: ${error.message}`);
  }

  return true;
}

/**
 * Delete all stories and chunks (USE WITH CAUTION!)
 */
export async function deleteAllStories(): Promise<void> {
  const supabase = getSupabaseClient();
  
  // Delete stories first (chunks will cascade)
  const { error } = await supabase
    .from('stories')
    .delete()
    .neq('id', 0); // Delete all rows

  if (error) {
    throw new Error(`Failed to delete all stories: ${error.message}`);
  }
}

