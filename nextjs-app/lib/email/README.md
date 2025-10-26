# Email Integration

This directory contains the Brevo email integration for the story preparation system.

## Files

### `brevo-smtp.ts`

SMTP client for sending emails via Brevo's SMTP relay.

**Key Functions:**

- `createBrevoTransporter()` - Creates configured nodemailer transporter
- `sendEmail(params)` - Sends email via Brevo SMTP
- `sendEmailWithAttachment(params)` - Alias for sending emails with attachments (e.g., EPUB to Kindle)

**Environment Variables Required:**

- `BREVO_SMTP_HOST` - SMTP host (default: smtp-relay.brevo.com)
- `BREVO_SMTP_PORT` - SMTP port (default: 587)
- `BREVO_SMTP_USER` - Your Brevo SMTP username
- `BREVO_SMTP_PASSWORD` - Your Brevo SMTP password
- `TEST_MODE` - Set to "true" to skip actual email sends (for testing)

### `notifications.ts`

Notification email templates and functions for various events.

**Functions:**

- `sendNewStoryNotification()` - Story received and queued
- `sendChunkingCompleteNotification()` - Story successfully chunked
- `sendDeliveryNotification()` - Chunk delivered to Kindle
- `sendErrorNotification()` - Processing error occurred
- `sendQueueEmptyNotification()` - No chunks available for delivery

**Environment Variables Required:**

- `FROM_EMAIL` - Verified sender email address
- `ADMIN_EMAIL` - Recipient for all notifications

## Usage

```typescript
import { sendEmail } from "@/lib/email/brevo-smtp";
import { sendNewStoryNotification } from "@/lib/email/notifications";

// Send a simple email
await sendEmail({
  to: "recipient@example.com",
  from: "sender@example.com",
  subject: "Hello",
  text: "Plain text body",
  html: "<p>HTML body</p>",
});

// Send a notification
await sendNewStoryNotification({
  title: "My Story",
  author: "Author Name",
  source: "email",
  storyId: 123,
});
```

## Testing

Run the test script to verify email integration:

```bash
./scripts/test/test-email.sh
```

Set `TEST_MODE=true` in your environment to skip actual email sends during testing.
