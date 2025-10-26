import { NextRequest, NextResponse } from "next/server";
import { createStory } from "@/lib/db";
import { uploadJSON } from "@/lib/storage";
import { v4 as uuidv4 } from "uuid";

/**
 * Brevo inbound email webhook format
 */
interface BrevoEmailItem {
  From: {
    Address: string;
    Name?: string;
  };
  To: Array<{
    Address: string;
    Name?: string;
  }>;
  Subject: string;
  RawHtmlBody: string;
  RawTextBody: string;
  Headers?: Record<string, string>;
  MessageId?: string;
}

interface BrevoWebhookPayload {
  items: BrevoEmailItem[];
}

/**
 * Transformed email format for storage and processing
 */
interface TransformedEmail {
  email_id: string;
  storage_id: string;
  storage_path: string;
  from: string;
  subject: string;
  html: string;
  text: string;
}

/**
 * Transform Brevo email item and prepare for storage
 */
async function transformBrevoEmail(
  item: BrevoEmailItem
): Promise<TransformedEmail> {
  // Use MessageId if available, otherwise generate from timestamp and sender
  const email_id =
    item.MessageId ||
    `${Date.now()}-${item.From.Address.replace(/[^a-z0-9]/gi, "_")}`;

  // Generate unique storage ID for this story
  const storage_id = uuidv4();

  // Storage path for email data
  const storage_path = `email-data/${storage_id}/email.json`;

  return {
    email_id,
    storage_id,
    storage_path,
    from: item.From.Address,
    subject: item.Subject,
    html: item.RawHtmlBody || "",
    text: item.RawTextBody || "",
  };
}

/**
 * Process a single email - persist email data and trigger ingestion
 */
async function processEmail(email: TransformedEmail): Promise<void> {
  const startTime = Date.now();

  try {
    console.log("📧 Processing email:", {
      email_id: email.email_id,
      storage_id: email.storage_id,
      from: email.from,
      subject: email.subject,
    });

    // 1. Upload email data to Supabase Storage FIRST (before creating story record)
    //    This ensures we don't lose data if webhook fails after DB write
    console.log(`📤 Uploading email data to storage: ${email.storage_path}`);
    await uploadJSON("epubs", email.storage_path, {
      email_id: email.email_id,
      from: email.from,
      subject: email.subject,
      html: email.html,
      text: email.text,
      received_at: new Date().toISOString(),
    });
    console.log(`✅ Email data persisted to storage`);

    // 2. Create story record in pending state with storage reference
    const story = await createStory({
      email_id: email.email_id,
      title: email.subject,
      source: "email",
    });

    console.log("✅ Story created in database:", {
      id: story.id,
      email_id: email.email_id,
      status: story.status,
      duration_ms: Date.now() - startTime,
    });

    // 3. Trigger async processing by calling ingestion endpoint
    //    This happens in the background, don't await
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000";

    console.log(`🔄 Triggering async processing for story ${story.id}`);

    // Don't await - let it run in background
    fetch(`${baseUrl}/api/stories/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        story_id: story.id,
        storage_id: email.storage_id,
        storage_path: email.storage_path,
      }),
    }).catch((error) => {
      console.error(
        `❌ Failed to trigger ingestion for story ${story.id}:`,
        error
      );
    });

    console.log(`✅ Email processing complete (${Date.now() - startTime}ms)`);
  } catch (error) {
    console.error("❌ Failed to process email:", {
      email_id: email.email_id,
      storage_id: email.storage_id,
      error: error instanceof Error ? error.message : String(error),
      duration_ms: Date.now() - startTime,
    });
    throw error;
  }
}

/**
 * POST /api/webhooks/email
 *
 * Handles inbound emails from Brevo webhook.
 * Transforms Brevo format to Modal API format and processes emails in parallel.
 */
export async function POST(request: NextRequest) {
  try {
    // Parse request body
    const body = (await request.json()) as BrevoWebhookPayload;

    // Validate payload structure
    if (!body.items || !Array.isArray(body.items)) {
      console.error("Invalid webhook payload: missing items array");
      return NextResponse.json(
        { error: "Invalid payload: missing items array" },
        { status: 400 }
      );
    }

    if (body.items.length === 0) {
      console.warn("Webhook received with empty items array");
      return NextResponse.json({ message: "No emails to process" });
    }

    console.log(`Received ${body.items.length} email(s) from Brevo webhook`);

    // Transform all emails from Brevo format and prepare for storage
    const transformedEmails = await Promise.all(
      body.items.map(transformBrevoEmail)
    );

    // Log transformed emails for debugging
    transformedEmails.forEach((email) => {
      console.log("Transformed email:", {
        email_id: email.email_id,
        storage_id: email.storage_id,
        from: email.from,
        subject: email.subject,
        text_length: email.text.length,
        html_length: email.html.length,
      });
    });

    // Process all emails in parallel and WAIT for persistence
    // This ensures email data is safely stored before we return success to Brevo
    const results = await Promise.allSettled(
      transformedEmails.map((email) => processEmail(email))
    );

    // Check for failures
    const failures = results.filter((r) => r.status === "rejected");
    if (failures.length > 0) {
      console.error(
        `❌ Failed to process ${failures.length}/${results.length} emails`
      );
      failures.forEach((failure, idx) => {
        if (failure.status === "rejected") {
          console.error(`  - Email ${idx + 1}: ${failure.reason}`);
        }
      });
    }

    const successCount = results.filter((r) => r.status === "fulfilled").length;
    console.log(
      `✅ Successfully processed ${successCount}/${results.length} emails`
    );

    // Return success to Brevo (email data is now safely persisted)
    return NextResponse.json({
      message: "Emails received and persisted",
      count: transformedEmails.length,
      success_count: successCount,
      email_ids: transformedEmails.map((e) => e.email_id),
    });
  } catch (error) {
    console.error("Error handling email webhook:", error);
    return NextResponse.json(
      {
        error: "Internal server error",
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/webhooks/email
 *
 * Returns information about the webhook endpoint (for debugging/verification)
 */
export async function GET() {
  return NextResponse.json({
    endpoint: "/api/webhooks/email",
    method: "POST",
    description: "Receives inbound emails from Brevo webhook",
    expected_payload: {
      items: [
        {
          From: { Address: "sender@example.com", Name: "Sender Name" },
          To: [{ Address: "recipient@example.com", Name: "Recipient Name" }],
          Subject: "Email Subject",
          RawHtmlBody: "<html>...</html>",
          RawTextBody: "Plain text...",
          MessageId: "unique-message-id",
        },
      ],
    },
  });
}
