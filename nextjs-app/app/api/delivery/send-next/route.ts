import { NextRequest, NextResponse } from "next/server";
import { getNextUnsentChunk, markChunkSent } from "@/lib/db";
import { downloadEpub } from "@/lib/storage";
import { sendEmail } from "@/lib/email/brevo-smtp";
import {
  sendDeliveryNotification,
  sendQueueEmptyNotification,
  sendErrorNotification,
} from "@/lib/email/notifications";

/**
 * Daily Delivery Endpoint
 *
 * Called by Vercel Cron (daily at 12pm PT / 8pm UTC)
 * Sends the next unsent story chunk to Kindle via email
 */
export async function POST(request: NextRequest) {
  console.log("[Delivery] Starting daily delivery process");

  try {
    // Verify Cron Secret if configured
    const cronSecret = process.env.CRON_SECRET;
    if (cronSecret) {
      const authHeader = request.headers.get("authorization");
      const expectedAuth = `Bearer ${cronSecret}`;

      if (authHeader !== expectedAuth) {
        console.error(
          "[Delivery] Unauthorized: Invalid or missing cron secret"
        );
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
      }
      console.log("[Delivery] Cron secret verified");
    } else {
      console.log("[Delivery] No CRON_SECRET set, skipping auth check");
    }

    // Get required environment variables
    const kindleEmail = process.env.KINDLE_EMAIL;
    const fromEmail = process.env.FROM_EMAIL;
    const adminEmail = process.env.ADMIN_EMAIL;
    const testMode = process.env.TEST_MODE === "true";

    if (!kindleEmail || !fromEmail) {
      const error = "KINDLE_EMAIL and FROM_EMAIL must be configured";
      console.error(`[Delivery] Configuration error: ${error}`);

      await sendErrorNotification({
        errorMessage: error,
        errorType: "delivery",
      });

      return NextResponse.json(
        { error: "Server configuration error" },
        { status: 500 }
      );
    }

    // In TEST_MODE, send to admin email instead of Kindle
    const deliveryEmail = testMode && adminEmail ? adminEmail : kindleEmail;

    if (testMode) {
      console.log(
        `[Delivery] TEST_MODE enabled - sending to admin email (${adminEmail}) instead of Kindle`
      );
    }

    // Get next unsent chunk
    console.log("[Delivery] Querying for next unsent chunk...");
    const chunk = await getNextUnsentChunk();

    if (!chunk) {
      console.log("[Delivery] Queue is empty - no chunks to send");

      // Send queue empty notification
      await sendQueueEmptyNotification();

      return NextResponse.json({
        success: true,
        message: "Queue is empty - no chunks to deliver",
        queueEmpty: true,
      });
    }

    console.log(`[Delivery] Found chunk to deliver:`, {
      chunkId: chunk.id,
      storyId: chunk.story_id,
      title: chunk.title,
      chunkNumber: chunk.chunk_number,
      totalChunks: chunk.total_chunks,
      storagePath: chunk.storage_path,
    });

    // Validate storage path
    if (!chunk.storage_path) {
      const error = `Chunk ${chunk.id} has no storage_path`;
      console.error(`[Delivery] Error: ${error}`);

      await sendErrorNotification({
        title: chunk.title || undefined,
        storyId: chunk.story_id,
        errorMessage: error,
        errorType: "delivery",
      });

      return NextResponse.json(
        { error: "Chunk has no storage path" },
        { status: 500 }
      );
    }

    // Download EPUB from storage
    console.log(
      `[Delivery] Downloading EPUB from storage: ${chunk.storage_path}`
    );
    const epubBuffer = await downloadEpub(chunk.storage_path);
    console.log(`[Delivery] Downloaded EPUB (${epubBuffer.length} bytes)`);

    // Prepare email subject and body
    const title = chunk.title || "Untitled Story";
    const author = chunk.author || "Unknown Author";
    const subject = `${title} - Part ${chunk.chunk_number}/${chunk.total_chunks}`;
    const emailBody = `
Delivering part ${chunk.chunk_number} of ${chunk.total_chunks} of "${title}" by ${author}.

Chunk ID: ${chunk.id}
Story ID: ${chunk.story_id}

Sent via Nighttime Story Prep
    `.trim();

    // Extract filename from storage path
    const filename = chunk.storage_path.split("/").pop() || "story.epub";

    // Send email to Kindle (or admin in TEST_MODE)
    const recipient = testMode && adminEmail ? adminEmail : kindleEmail;
    const recipientLabel = testMode
      ? `admin (${recipient})`
      : `Kindle (${recipient})`;

    console.log(`[Delivery] Sending email to ${recipientLabel}`);
    await sendEmail({
      to: recipient,
      from: fromEmail,
      subject: testMode ? `[TEST] ${subject}` : subject,
      text: testMode
        ? `[TEST MODE - Would have sent to ${kindleEmail}]\n\n${emailBody}`
        : emailBody,
      attachments: [
        {
          filename,
          content: epubBuffer,
          contentType: "application/epub+zip",
        },
      ],
    });
    console.log("[Delivery] Email sent successfully");

    // Mark chunk as sent
    console.log(`[Delivery] Marking chunk ${chunk.id} as sent`);
    await markChunkSent(chunk.id);
    console.log("[Delivery] Chunk marked as sent in database");

    // Send delivery notification to admin
    console.log("[Delivery] Sending delivery notification to admin");
    await sendDeliveryNotification({
      title,
      author,
      chunkNumber: chunk.chunk_number,
      totalChunks: chunk.total_chunks,
      chunkId: chunk.id,
    });

    console.log("[Delivery] Delivery completed successfully");

    return NextResponse.json({
      success: true,
      message: "Chunk delivered successfully",
      testMode,
      deliveredTo: recipient,
      chunk: {
        id: chunk.id,
        storyId: chunk.story_id,
        title,
        author,
        chunkNumber: chunk.chunk_number,
        totalChunks: chunk.total_chunks,
        storagePath: chunk.storage_path,
      },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error("[Delivery] Delivery failed:", error);

    // Send error notification
    try {
      await sendErrorNotification({
        errorMessage: errorMessage,
        errorType: "delivery",
      });
    } catch (notifError) {
      console.error(
        "[Delivery] Failed to send error notification:",
        notifError
      );
    }

    return NextResponse.json(
      {
        success: false,
        error: "Delivery failed",
        details: errorMessage,
      },
      { status: 500 }
    );
  }
}

// Also support GET for manual testing/triggering
export async function GET(request: NextRequest) {
  return POST(request);
}
