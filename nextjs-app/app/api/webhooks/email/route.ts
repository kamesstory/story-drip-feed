import { NextRequest, NextResponse } from "next/server";
import { createStory } from "@/lib/db";

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
 * Transformed email format for Modal API
 */
interface TransformedEmail {
  email_id: string;
  from: string;
  subject: string;
  html: string;
  text: string;
}

/**
 * Transform Brevo email item to Modal API format
 */
function transformBrevoEmail(item: BrevoEmailItem): TransformedEmail {
  // Use MessageId if available, otherwise generate from timestamp and sender
  const email_id =
    item.MessageId ||
    `${Date.now()}-${item.From.Address.replace(/[^a-z0-9]/gi, "_")}`;

  return {
    email_id,
    from: item.From.Address,
    subject: item.Subject,
    html: item.RawHtmlBody || "",
    text: item.RawTextBody || "",
  };
}

/**
 * Process a single email (to be implemented in Task 5)
 * For now, just create a story record in pending state
 */
async function processEmail(email: TransformedEmail): Promise<void> {
  try {
    console.log("Processing email:", {
      email_id: email.email_id,
      from: email.from,
      subject: email.subject,
    });

    // Create story record in pending state
    const story = await createStory({
      email_id: email.email_id,
      title: email.subject,
      source: "email",
    });

    console.log("Story created:", {
      id: story.id,
      email_id: email.email_id,
      status: story.status,
    });

    // TODO (Task 5): Call story ingestion endpoint to process with Modal API
    // For now, we just create the story record in pending state
  } catch (error) {
    console.error("Failed to process email:", {
      email_id: email.email_id,
      error: error instanceof Error ? error.message : String(error),
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

    // Transform all emails from Brevo format to Modal API format
    const transformedEmails = body.items.map(transformBrevoEmail);

    // Log transformed emails for debugging
    transformedEmails.forEach((email) => {
      console.log("Transformed email:", {
        email_id: email.email_id,
        from: email.from,
        subject: email.subject,
        text_length: email.text.length,
        html_length: email.html.length,
      });
    });

    // Respond immediately with 200 OK
    const response = NextResponse.json({
      message: "Emails received and queued for processing",
      count: transformedEmails.length,
      email_ids: transformedEmails.map((e) => e.email_id),
    });

    // Process all emails in parallel (non-blocking)
    // Note: This happens after the response is sent due to Next.js behavior
    Promise.all(
      transformedEmails.map((email) =>
        processEmail(email).catch((error) => {
          console.error("Failed to process email:", {
            email_id: email.email_id,
            error: error instanceof Error ? error.message : String(error),
          });
          // Don't throw - we want all emails to be processed independently
        })
      )
    ).then(() => {
      console.log("All emails processed successfully");
    });

    return response;
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
