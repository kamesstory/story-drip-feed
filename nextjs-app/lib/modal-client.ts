/**
 * Modal API Client
 *
 * TypeScript client for calling Modal API endpoints with authentication,
 * type safety, and error handling.
 */

const MODAL_API_URL = process.env.MODAL_API_URL || "";
const MODAL_API_KEY = process.env.MODAL_API_KEY || "";

export interface ExtractContentRequest {
  email_data: {
    email_id: string;
    from: string;
    subject: string;
    html: string;
    text: string;
  };
  storage_id: string;
}

export interface ExtractContentResponse {
  status: "success";
  content_url: string;
  metadata: {
    title: string;
    author?: string;
    word_count: number;
    extraction_method: string;
  };
}

export interface ChunkStoryRequest {
  content_url: string;
  storage_id: string;
  target_words?: number;
}

export interface ChunkStoryResponse {
  status: "success";
  chunks: Array<{
    chunk_number: number;
    url: string;
    word_count: number;
  }>;
  total_chunks: number;
  total_words: number;
  chunking_strategy: string;
}

export interface ModalHealthResponse {
  status: string;
  services: {
    anthropic_api: string;
    supabase_storage: string;
  };
}

export class ModalAPIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public response?: unknown
  ) {
    super(message);
    this.name = "ModalAPIError";
  }
}

/**
 * Call Modal API with authentication and error handling
 */
async function callModalAPI<T>(
  endpoint: string,
  data: unknown,
  options: {
    retries?: number;
    retryDelay?: number;
  } = {}
): Promise<T> {
  const { retries = 3, retryDelay = 1000 } = options;

  if (!MODAL_API_URL) {
    throw new ModalAPIError("MODAL_API_URL environment variable not set");
  }

  const url = `${MODAL_API_URL}${endpoint}`;

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      console.log(
        `[Modal API] Calling ${endpoint} (attempt ${attempt}/${retries})`
      );

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(MODAL_API_KEY
            ? { Authorization: `Bearer ${MODAL_API_KEY}` }
            : {}),
        },
        body: JSON.stringify(data),
      });

      const responseData = await response.json();

      if (!response.ok) {
        const errorMessage =
          responseData.message || responseData.error || "Unknown error";

        // Don't retry on 4xx errors (client errors)
        if (response.status >= 400 && response.status < 500) {
          throw new ModalAPIError(
            `Modal API error: ${errorMessage}`,
            response.status,
            responseData
          );
        }

        // Retry on 5xx errors (server errors)
        if (attempt < retries) {
          console.warn(
            `[Modal API] Request failed (${response.status}), retrying in ${retryDelay}ms...`
          );
          await new Promise((resolve) => setTimeout(resolve, retryDelay));
          continue;
        }

        throw new ModalAPIError(
          `Modal API error after ${retries} attempts: ${errorMessage}`,
          response.status,
          responseData
        );
      }

      console.log(`[Modal API] Successfully called ${endpoint}`);
      return responseData as T;
    } catch (error) {
      if (error instanceof ModalAPIError) {
        throw error;
      }

      // Network error or other issues
      if (attempt < retries) {
        console.warn(
          `[Modal API] Network error, retrying in ${retryDelay}ms...`,
          error
        );
        await new Promise((resolve) => setTimeout(resolve, retryDelay));
        continue;
      }

      throw new ModalAPIError(
        `Failed to call Modal API after ${retries} attempts: ${
          error instanceof Error ? error.message : String(error)
        }`,
        undefined,
        error
      );
    }
  }

  // Should never reach here
  throw new ModalAPIError(`Failed to call Modal API after ${retries} attempts`);
}

/**
 * Check Modal API health
 */
export async function checkModalHealth(): Promise<ModalHealthResponse> {
  if (!MODAL_API_URL) {
    throw new ModalAPIError("MODAL_API_URL environment variable not set");
  }

  const url = `${MODAL_API_URL}/health`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new ModalAPIError(`Health check failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Extract content from email data
 */
export async function extractContent(
  request: ExtractContentRequest
): Promise<ExtractContentResponse> {
  return callModalAPI<ExtractContentResponse>("/extract-content", request, {
    retries: 2, // Lower retries for content extraction (can be expensive)
    retryDelay: 2000,
  });
}

/**
 * Chunk story content
 */
export async function chunkStory(
  request: ChunkStoryRequest
): Promise<ChunkStoryResponse> {
  return callModalAPI<ChunkStoryResponse>("/chunk-story", request, {
    retries: 2, // Lower retries for chunking (can be expensive)
    retryDelay: 2000,
  });
}
