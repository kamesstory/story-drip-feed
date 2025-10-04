# Nighttime Story Prep

Automatically processes Patreon stories from email, chunks them into readable segments (~10k words), converts to EPUB, and sends to Kindle.

## Features

- **Automatic email processing**: Receives stories via email webhook
- **Intelligent chunking**: Splits stories into ~10k word segments (extensible for AI-based chunking)
- **EPUB generation**: Creates properly formatted EPUB files
- **Kindle delivery**: Automatically sends to your Kindle email
- **Robust error handling**: Tracks processing status and retries failures

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up Modal
```bash
modal token new
```

### 3. Create Modal secret with credentials
```bash
modal secret create story-prep-secrets \
  KINDLE_EMAIL=your-kindle@kindle.com \
  SMTP_HOST=smtp.gmail.com \
  SMTP_PORT=587 \
  SMTP_USER=your-email@gmail.com \
  SMTP_PASSWORD=your-app-password
```

**For Gmail users**: Use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

### 4. Deploy to Modal
```bash
modal deploy main.py
```

This will output your webhook URL (e.g., `https://username--nighttime-story-prep-webhook.modal.run`)

### 5. Configure email forwarding

Set up an email service (Mailgun, SendGrid, or Cloudflare Email Workers) to forward Patreon emails to your webhook URL.

**Example with Mailgun:**
1. Add your domain to Mailgun
2. Create a route that forwards to your webhook URL
3. Forward Patreon notification emails to your Mailgun address

## Testing

Run locally with test data:
```bash
modal run main.py
```

## Architecture

- **Email ingestion**: Webhook receives parsed emails from email service
- **Processing**: Modal functions parse, chunk, and convert stories
- **Storage**: SQLite on Modal Volume tracks processing status
- **Delivery**: SMTP sends EPUBs to Kindle email
- **Retry logic**: Cron job retries failed stories every 6 hours (max 3 attempts)

## Project Structure

```
├── main.py             # Modal app with webhook and processing logic
├── database.py         # SQLite database for tracking stories
├── email_parser.py     # Extract story content from emails (strategy pattern)
├── chunker.py          # Text chunking (strategy pattern, extensible)
├── epub_generator.py   # EPUB file generation
├── kindle_sender.py    # SMTP delivery to Kindle
└── requirements.txt    # Python dependencies
```
