import { sendEmail } from "./brevo-smtp";

const FROM_EMAIL = process.env.FROM_EMAIL || "noreply@example.com";
const ADMIN_EMAIL = process.env.ADMIN_EMAIL || "";

/**
 * Send notification that a new story has been received and queued for processing
 */
export async function sendNewStoryNotification(params: {
  title: string;
  author?: string;
  source: string;
  storyId: number;
}) {
  if (!ADMIN_EMAIL) {
    console.warn("ADMIN_EMAIL not set, skipping new story notification");
    return;
  }

  const subject = `📚 New Story Received: ${params.title}`;
  const text = `
A new story has been received and queued for processing.

Title: ${params.title}
Author: ${params.author || "Unknown"}
Source: ${params.source}
Story ID: ${params.storyId}

The story will be processed and chunked automatically.
  `.trim();

  const html = `
<h2>📚 New Story Received</h2>
<p>A new story has been received and queued for processing.</p>
<ul>
  <li><strong>Title:</strong> ${params.title}</li>
  <li><strong>Author:</strong> ${params.author || "Unknown"}</li>
  <li><strong>Source:</strong> ${params.source}</li>
  <li><strong>Story ID:</strong> ${params.storyId}</li>
</ul>
<p>The story will be processed and chunked automatically.</p>
  `.trim();

  return sendEmail({
    to: ADMIN_EMAIL,
    from: FROM_EMAIL,
    subject,
    text,
    html,
  });
}

/**
 * Send notification that story has been successfully chunked
 */
export async function sendChunkingCompleteNotification(params: {
  title: string;
  author?: string;
  storyId: number;
  totalChunks: number;
  totalWords?: number;
}) {
  if (!ADMIN_EMAIL) {
    console.warn(
      "ADMIN_EMAIL not set, skipping chunking complete notification"
    );
    return;
  }

  const subject = `✅ Story Chunked: ${params.title} (${params.totalChunks} chunks)`;
  const text = `
Story has been successfully chunked and is ready for delivery.

Title: ${params.title}
Author: ${params.author || "Unknown"}
Story ID: ${params.storyId}
Total Chunks: ${params.totalChunks}
${params.totalWords ? `Total Words: ${params.totalWords}` : ""}

Chunks will be delivered daily to your Kindle.
  `.trim();

  const html = `
<h2>✅ Story Chunked Successfully</h2>
<p>Story has been successfully chunked and is ready for delivery.</p>
<ul>
  <li><strong>Title:</strong> ${params.title}</li>
  <li><strong>Author:</strong> ${params.author || "Unknown"}</li>
  <li><strong>Story ID:</strong> ${params.storyId}</li>
  <li><strong>Total Chunks:</strong> ${params.totalChunks}</li>
  ${
    params.totalWords
      ? `<li><strong>Total Words:</strong> ${params.totalWords}</li>`
      : ""
  }
</ul>
<p>Chunks will be delivered daily to your Kindle.</p>
  `.trim();

  return sendEmail({
    to: ADMIN_EMAIL,
    from: FROM_EMAIL,
    subject,
    text,
    html,
  });
}

/**
 * Send notification that a chunk has been delivered to Kindle
 */
export async function sendDeliveryNotification(params: {
  title: string;
  author?: string;
  chunkNumber: number;
  totalChunks: number;
  chunkId: number;
}) {
  if (!ADMIN_EMAIL) {
    console.warn("ADMIN_EMAIL not set, skipping delivery notification");
    return;
  }

  const subject = `📖 Delivered: ${params.title} (Part ${params.chunkNumber}/${params.totalChunks})`;
  const text = `
A chunk has been delivered to your Kindle.

Title: ${params.title}
Author: ${params.author || "Unknown"}
Part: ${params.chunkNumber} of ${params.totalChunks}
Chunk ID: ${params.chunkId}

Check your Kindle for the new content.
  `.trim();

  const html = `
<h2>📖 Chunk Delivered to Kindle</h2>
<p>A chunk has been delivered to your Kindle.</p>
<ul>
  <li><strong>Title:</strong> ${params.title}</li>
  <li><strong>Author:</strong> ${params.author || "Unknown"}</li>
  <li><strong>Part:</strong> ${params.chunkNumber} of ${params.totalChunks}</li>
  <li><strong>Chunk ID:</strong> ${params.chunkId}</li>
</ul>
<p>Check your Kindle for the new content.</p>
  `.trim();

  return sendEmail({
    to: ADMIN_EMAIL,
    from: FROM_EMAIL,
    subject,
    text,
    html,
  });
}

/**
 * Send error notification when processing fails
 */
export async function sendErrorNotification(params: {
  title?: string;
  storyId?: number;
  errorMessage: string;
  errorType: "extraction" | "chunking" | "delivery" | "general";
}) {
  if (!ADMIN_EMAIL) {
    console.warn("ADMIN_EMAIL not set, skipping error notification");
    return;
  }

  const errorTypeLabel = {
    extraction: "Content Extraction",
    chunking: "Story Chunking",
    delivery: "Delivery",
    general: "Processing",
  }[params.errorType];

  const subject = `❌ Error: ${errorTypeLabel} Failed${
    params.title ? ` - ${params.title}` : ""
  }`;
  const text = `
An error occurred during story processing.

Error Type: ${errorTypeLabel}
${params.title ? `Title: ${params.title}` : ""}
${params.storyId ? `Story ID: ${params.storyId}` : ""}

Error Message:
${params.errorMessage}

Please check the logs for more details.
  `.trim();

  const html = `
<h2>❌ Processing Error</h2>
<p>An error occurred during story processing.</p>
<ul>
  <li><strong>Error Type:</strong> ${errorTypeLabel}</li>
  ${params.title ? `<li><strong>Title:</strong> ${params.title}</li>` : ""}
  ${
    params.storyId
      ? `<li><strong>Story ID:</strong> ${params.storyId}</li>`
      : ""
  }
</ul>
<p><strong>Error Message:</strong></p>
<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px;">${
    params.errorMessage
  }</pre>
<p>Please check the logs for more details.</p>
  `.trim();

  return sendEmail({
    to: ADMIN_EMAIL,
    from: FROM_EMAIL,
    subject,
    text,
    html,
  });
}

/**
 * Send notification that the queue is empty
 */
export async function sendQueueEmptyNotification() {
  if (!ADMIN_EMAIL) {
    console.warn("ADMIN_EMAIL not set, skipping queue empty notification");
    return;
  }

  const subject = "⚠️ Story Queue Empty";
  const text = `
The story delivery queue is empty.

No chunks are available for delivery. Please add more stories to continue daily deliveries.
  `.trim();

  const html = `
<h2>⚠️ Story Queue Empty</h2>
<p>The story delivery queue is empty.</p>
<p>No chunks are available for delivery. Please add more stories to continue daily deliveries.</p>
  `.trim();

  return sendEmail({
    to: ADMIN_EMAIL,
    from: FROM_EMAIL,
    subject,
    text,
    html,
  });
}
