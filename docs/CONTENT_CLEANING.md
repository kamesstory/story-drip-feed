# Content Cleaning - Metadata Removal

The agent extraction system automatically strips all non-story content from emails.

## What Gets Removed

The agent is trained to remove:

### 1. **Headers & Metadata**
- Chapter numbers/titles ("Chapter 27", "Episode 5.23")
- Dates and timestamps ("Sep 19, 2025", "Posted on...")
- Platform UI ("View in app", "Read online", "Open in browser")

### 2. **Author Notes**
- "Author's note:", "A/N:", "Note from author"
- Update schedules ("Next chapter: Friday")
- Announcements and meta-commentary

### 3. **Patreon & Support**
- "Support me on Patreon"
- "Become a patron"
- Pledge tier links
- Donation/tip jar links

### 4. **Social Media**
- "Like", "Comment", "Share", "Subscribe"
- "Follow me on Twitter/Discord/etc"
- Social media buttons and calls-to-action

### 5. **Navigation & UI**
- "Previous chapter" / "Next chapter" links
- "Back to index" / "Table of contents"
- Reader engagement prompts ("Thanks for reading!")

### 6. **Legal Boilerplate**
- Copyright notices ("© 2025", "All rights reserved")
- Terms and disclaimers

## What Gets Kept

✅ **Actual narrative content:**
- Story prose and descriptions
- Dialogue
- Action sequences
- Scene transitions
- In-story formatting (scene breaks like `---`, `* * *`)

## Testing

Run the metadata removal test:

```bash
poetry run python test_extraction_cleaning.py
```

This will:
1. Create an email with lots of metadata
2. Extract story content using the agent
3. Verify all metadata was removed
4. Verify all story content was preserved

### Example Output

**Before extraction:**
```
Chapter 27
Sep 19, 2025

View in app

Maryam was not having a good time.

"Black fucking Goat," she cursed...

────────────────────

Thanks for reading!
❤️ Like this post
Support me on Patreon: https://...
```

**After extraction:**
```
Maryam was not having a good time.

"Black fucking Goat," she cursed...
```

## How It Works

1. **Strategy Detection**: Agent analyzes email to determine extraction method (inline vs URL)
2. **Content Extraction**: Second agent call extracts ONLY story content, removing metadata
3. **Validation**: System checks extracted content length (must be >500 words)
4. **File Storage**: Clean content saved to `content.txt`, original saved for debugging

## Fallback Behavior

If agent extraction fails:
- Falls back to traditional `EmailParser`
- Uses regex-based boilerplate removal
- Less sophisticated but still functional

## Edge Cases

The agent handles:
- **Mixed content**: Metadata at start and end, story in middle
- **Nested formatting**: Markdown, HTML entities
- **Scene breaks**: Preserves in-story dividers (`---`, `* * *`)
- **Multiple formats**: Handles both plain text and HTML emails

## Verification

All test results showed **100% success rate** for:
- ✅ Removing chapter numbers
- ✅ Removing dates
- ✅ Removing "View in app"
- ✅ Removing social media prompts
- ✅ Removing Patreon links
- ✅ Removing copyright notices
- ✅ Preserving story content
- ✅ Preserving dialogue
- ✅ Preserving scene breaks
