import { NextRequest, NextResponse } from "next/server";
import {
  getStoryById,
  updateStoryStatus,
  updateStoryMetadata,
  createChunk,
  incrementRetryCount,
} from "@/lib/db";
import { downloadJSON, downloadText } from "@/lib/storage";
import { uploadEpub } from "@/lib/storage";
import { extractContent, chunkStory } from "@/lib/modal-client";
import { generateEPUB, generateEPUBFilename } from "@/lib/epub-generator";
import {
  sendChunkingCompleteNotification,
  sendErrorNotification,
} from "@/lib/email/notifications";

/**
 * Request body format
 */
interface IngestRequest {
  story_id: number;
  storage_id: string;
  storage_path: string;
}

/**
 * Email data stored in Supabase Storage
 */
interface StoredEmailData {
  email_id: string;
  from: string;
  subject: string;
  html: string;
  text: string;
  received_at: string;
}

/**
 * Process a story through the full pipeline
 */
async function processStory(
  storyId: number,
  storageId: string,
  storagePath: string
): Promise<void> {
  const startTime = Date.now();
  let currentStep = "initialization";

  try {
    console.log(`\n${"=".repeat(80)}`);
    console.log(`📚 STORY PROCESSING PIPELINE - Story ID: ${storyId}`);
    console.log(`${"=".repeat(80)}`);
    console.log(`Storage ID: ${storageId}`);
    console.log(`Storage Path: ${storagePath}`);
    console.log(`Started: ${new Date().toISOString()}`);

    // Step 1: Fetch email data from storage
    currentStep = "fetch_email_data";
    console.log(`\n[Step 1/7] 📥 Fetching email data from storage...`);
    const emailData = await downloadJSON<StoredEmailData>("epubs", storagePath);
    console.log(`✅ Email data fetched:`, {
      email_id: emailData.email_id,
      subject: emailData.subject,
      from: emailData.from,
      text_length: emailData.text.length,
      html_length: emailData.html.length,
    });

    // Step 2: Update story status to 'processing'
    currentStep = "update_status_processing";
    console.log(`\n[Step 2/7] 🔄 Updating story status to 'processing'...`);
    await updateStoryStatus(storyId, "processing");
    console.log(`✅ Story status updated to 'processing'`);

    // Step 3: Call Modal API to extract content
    currentStep = "extract_content";
    console.log(`\n[Step 3/7] 🤖 Calling Modal API to extract content...`);
    const extractionResult = await extractContent({
      email_data: {
        email_id: emailData.email_id,
        from: emailData.from,
        subject: emailData.subject,
        html: emailData.html,
        text: emailData.text,
      },
      storage_id: storageId,
    });

    console.log(`✅ Content extracted:`, {
      content_url: extractionResult.content_url,
      title: extractionResult.metadata.title,
      author: extractionResult.metadata.author,
      word_count: extractionResult.metadata.word_count,
      extraction_method: extractionResult.metadata.extraction_method,
    });

    // Step 4: Update story with extraction metadata
    currentStep = "update_metadata";
    console.log(`\n[Step 4/7] 📝 Updating story metadata...`);
    await updateStoryMetadata(storyId, {
      title: extractionResult.metadata.title,
      author: extractionResult.metadata.author || undefined,
      word_count: extractionResult.metadata.word_count,
      extraction_method: extractionResult.metadata.extraction_method,
    });
    console.log(`✅ Story metadata updated`);

    // Step 5: Call Modal API to chunk story
    currentStep = "chunk_story";
    console.log(`\n[Step 5/7] ✂️  Calling Modal API to chunk story...`);
    const targetWords = parseInt(process.env.TARGET_WORDS || "5000", 10);
    const chunkingResult = await chunkStory({
      content_url: extractionResult.content_url,
      storage_id: storageId,
      target_words: targetWords,
    });

    console.log(`✅ Story chunked:`, {
      total_chunks: chunkingResult.total_chunks,
      total_words: chunkingResult.total_words,
      chunking_strategy: chunkingResult.chunking_strategy,
    });

    // Step 6: Generate EPUBs and save chunks to database
    currentStep = "generate_epubs";
    console.log(
      `\n[Step 6/7] 📖 Generating EPUBs for ${chunkingResult.total_chunks} chunks...`
    );

    for (const chunkInfo of chunkingResult.chunks) {
      console.log(
        `  Processing chunk ${chunkInfo.chunk_number}/${chunkingResult.total_chunks}...`
      );

      // Download chunk text from storage
      const chunkText = await downloadText("epubs", chunkInfo.url);

      // Generate EPUB
      const epubBuffer = await generateEPUB({
        title: extractionResult.metadata.title,
        author: extractionResult.metadata.author,
        content: chunkText,
        chunkNumber: chunkInfo.chunk_number,
        totalChunks: chunkingResult.total_chunks,
      });

      // Upload EPUB to storage
      const epubFilename = generateEPUBFilename(
        extractionResult.metadata.title,
        chunkInfo.chunk_number
      );
      const epubStoragePath = await uploadEpub(epubFilename, epubBuffer);

      // Create chunk record in database
      await createChunk({
        story_id: storyId,
        chunk_number: chunkInfo.chunk_number,
        total_chunks: chunkingResult.total_chunks,
        chunk_text: chunkText,
        word_count: chunkInfo.word_count,
        storage_path: epubStoragePath,
      });

      console.log(
        `  ✅ Chunk ${chunkInfo.chunk_number}: EPUB generated and saved (${epubBuffer.length} bytes)`
      );
    }

    console.log(
      `✅ All ${chunkingResult.total_chunks} EPUBs generated and saved`
    );

    // Step 7: Update story status to 'chunked'
    currentStep = "update_status_chunked";
    console.log(`\n[Step 7/7] ✅ Updating story status to 'chunked'...`);
    await updateStoryStatus(storyId, "chunked");
    console.log(`✅ Story status updated to 'chunked'`);

    // Send success notification
    console.log(`\n📧 Sending success notification email...`);
    await sendChunkingCompleteNotification({
      title: extractionResult.metadata.title,
      author: extractionResult.metadata.author,
      storyId: storyId,
      totalChunks: chunkingResult.total_chunks,
      totalWords: chunkingResult.total_words,
    });

    const duration = Date.now() - startTime;
    console.log(`\n${"=".repeat(80)}`);
    console.log(`✅ STORY PROCESSING COMPLETE`);
    console.log(`${"=".repeat(80)}`);
    console.log(`Story ID: ${storyId}`);
    console.log(`Title: ${extractionResult.metadata.title}`);
    console.log(`Chunks: ${chunkingResult.total_chunks}`);
    console.log(`Total Duration: ${(duration / 1000).toFixed(2)}s`);
    console.log(`${"=".repeat(80)}\n`);
  } catch (error) {
    const duration = Date.now() - startTime;
    const errorMessage = error instanceof Error ? error.message : String(error);

    console.error(`\n${"=".repeat(80)}`);
    console.error(`❌ STORY PROCESSING FAILED`);
    console.error(`${"=".repeat(80)}`);
    console.error(`Story ID: ${storyId}`);
    console.error(`Failed at step: ${currentStep}`);
    console.error(`Error: ${errorMessage}`);
    console.error(`Duration: ${(duration / 1000).toFixed(2)}s`);
    console.error(`${"=".repeat(80)}\n`);

    if (error instanceof Error && error.stack) {
      console.error("Stack trace:", error.stack);
    }

    // Update story status to 'failed' with error message
    try {
      await updateStoryStatus(storyId, "failed", errorMessage);
      await incrementRetryCount(storyId);
    } catch (dbError) {
      console.error("Failed to update story status to failed:", dbError);
    }

    // Send error notification
    try {
      // Get story details for notification
      const story = await getStoryById(storyId);
      await sendErrorNotification({
        title: story?.title || undefined,
        storyId: storyId,
        errorMessage: `Failed at step: ${currentStep}\n\n${errorMessage}`,
        errorType: currentStep.includes("extract")
          ? "extraction"
          : currentStep.includes("chunk")
          ? "chunking"
          : "general",
      });
    } catch (notifError) {
      console.error("Failed to send error notification:", notifError);
    }

    throw error;
  }
}

/**
 * POST /api/stories/ingest
 *
 * Main story processing endpoint. Receives story ID and storage reference,
 * then processes through the full pipeline:
 * 1. Fetch email data from storage
 * 2. Extract content via Modal API
 * 3. Chunk story via Modal API
 * 4. Generate EPUBs
 * 5. Save chunks to database
 * 6. Send notifications
 *
 * Returns 202 Accepted immediately and processes in background.
 */
export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as IngestRequest;

    // Validate request
    if (!body.story_id || !body.storage_id || !body.storage_path) {
      return NextResponse.json(
        {
          error: "Bad Request",
          message:
            "Missing required fields: story_id, storage_id, storage_path",
        },
        { status: 400 }
      );
    }

    console.log("📥 Story ingestion request received:", {
      story_id: body.story_id,
      storage_id: body.storage_id,
      storage_path: body.storage_path,
    });

    // Verify story exists
    const story = await getStoryById(body.story_id);
    if (!story) {
      return NextResponse.json(
        {
          error: "Not Found",
          message: `Story ${body.story_id} not found`,
        },
        { status: 404 }
      );
    }

    // Process story in background (don't await)
    processStory(body.story_id, body.storage_id, body.storage_path).catch(
      (error) => {
        console.error("Background processing failed:", error);
      }
    );

    // Return 202 Accepted immediately
    return NextResponse.json(
      {
        message: "Story accepted for processing",
        story_id: body.story_id,
        status: "processing",
      },
      { status: 202 }
    );
  } catch (error) {
    console.error("Error in story ingestion endpoint:", error);
    return NextResponse.json(
      {
        error: "Internal Server Error",
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/stories/ingest
 *
 * Returns information about the ingestion endpoint
 */
export async function GET() {
  return NextResponse.json({
    endpoint: "/api/stories/ingest",
    method: "POST",
    description:
      "Process a story through extraction, chunking, and EPUB generation",
    required_fields: {
      story_id: "number - Database ID of the story",
      storage_id: "string - Unique storage identifier",
      storage_path: "string - Path to email data in storage",
    },
    response: {
      success: {
        status: 202,
        body: {
          message: "Story accepted for processing",
          story_id: "number",
          status: "processing",
        },
      },
    },
  });
}
