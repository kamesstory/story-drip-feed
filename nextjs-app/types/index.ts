// Database types matching PostgreSQL schema

export type StoryStatus = 'pending' | 'processing' | 'chunked' | 'sent' | 'failed';

export interface Story {
  id: number;
  email_id: string;
  title: string | null;
  author: string | null;
  received_at: string;
  word_count: number | null;
  status: StoryStatus;
  error_message: string | null;
  retry_count: number;
  processed_at: string | null;
  source: string | null;
  extraction_method: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoryChunk {
  id: number;
  story_id: number;
  chunk_number: number;
  total_chunks: number;
  word_count: number | null;
  chunk_text: string;
  storage_path: string | null;
  sent_to_kindle_at: string | null;
  created_at: string;
}

// Extended chunk type with story information (for joins)
export interface StoryChunkWithStory extends StoryChunk {
  story: Story;
}

// Input types for creating records
export interface CreateStoryInput {
  email_id: string;
  title?: string;
  author?: string;
  source?: string;
  extraction_method?: string;
}

export interface CreateChunkInput {
  story_id: number;
  chunk_number: number;
  total_chunks: number;
  chunk_text: string;
  word_count?: number;
  storage_path?: string;
}

// Update types
export interface UpdateStoryStatusInput {
  status: StoryStatus;
  error_message?: string | null;
  processed_at?: string | null;
}

export interface UpdateStoryMetadataInput {
  title?: string;
  author?: string;
  word_count?: number;
  extraction_method?: string;
}

