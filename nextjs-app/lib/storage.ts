import { getSupabaseClient } from './supabase';

const EPUB_BUCKET = 'epubs';

/**
 * Upload an EPUB file to Supabase Storage
 * @param fileName - Name of the file (e.g., "story-title_part1.epub")
 * @param fileBuffer - Buffer containing the EPUB file data
 * @returns Storage path of the uploaded file
 */
export async function uploadEpub(
  fileName: string,
  fileBuffer: Buffer
): Promise<string> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase.storage
    .from(EPUB_BUCKET)
    .upload(fileName, fileBuffer, {
      contentType: 'application/epub+zip',
      upsert: true, // Replace if exists
    });

  if (error) {
    throw new Error(`Failed to upload EPUB: ${error.message}`);
  }

  return data.path;
}

/**
 * Download an EPUB file from Supabase Storage
 * @param storagePath - Storage path of the file
 * @returns Buffer containing the EPUB file data
 */
export async function downloadEpub(storagePath: string): Promise<Buffer> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase.storage
    .from(EPUB_BUCKET)
    .download(storagePath);

  if (error) {
    throw new Error(`Failed to download EPUB: ${error.message}`);
  }

  // Convert Blob to Buffer
  const arrayBuffer = await data.arrayBuffer();
  return Buffer.from(arrayBuffer);
}

/**
 * Delete an EPUB file from Supabase Storage
 * @param storagePath - Storage path of the file
 */
export async function deleteEpub(storagePath: string): Promise<void> {
  const supabase = getSupabaseClient();
  
  const { error } = await supabase.storage
    .from(EPUB_BUCKET)
    .remove([storagePath]);

  if (error) {
    throw new Error(`Failed to delete EPUB: ${error.message}`);
  }
}

/**
 * Get public URL for an EPUB file
 * @param storagePath - Storage path of the file
 * @returns Public URL for the file
 */
export async function getPublicUrl(storagePath: string): Promise<string> {
  const supabase = getSupabaseClient();
  
  const { data } = supabase.storage
    .from(EPUB_BUCKET)
    .getPublicUrl(storagePath);

  return data.publicUrl;
}

/**
 * Get signed URL for an EPUB file (expires after specified time)
 * @param storagePath - Storage path of the file
 * @param expiresIn - Number of seconds until URL expires (default 3600 = 1 hour)
 * @returns Signed URL for the file
 */
export async function getSignedUrl(
  storagePath: string,
  expiresIn: number = 3600
): Promise<string> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase.storage
    .from(EPUB_BUCKET)
    .createSignedUrl(storagePath, expiresIn);

  if (error) {
    throw new Error(`Failed to create signed URL: ${error.message}`);
  }

  return data.signedUrl;
}

/**
 * List all EPUB files in storage
 * @param limit - Maximum number of files to return (default 100)
 * @returns Array of file metadata
 */
export async function listEpubs(limit: number = 100) {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase.storage
    .from(EPUB_BUCKET)
    .list('', {
      limit,
      sortBy: { column: 'created_at', order: 'desc' },
    });

  if (error) {
    throw new Error(`Failed to list EPUBs: ${error.message}`);
  }

  return data;
}

/**
 * Check if an EPUB file exists in storage
 * @param storagePath - Storage path of the file
 * @returns True if file exists, false otherwise
 */
export async function epubExists(storagePath: string): Promise<boolean> {
  const supabase = getSupabaseClient();
  
  const { data, error } = await supabase.storage
    .from(EPUB_BUCKET)
    .list('', {
      search: storagePath,
    });

  if (error) {
    return false;
  }

  return data.length > 0;
}

