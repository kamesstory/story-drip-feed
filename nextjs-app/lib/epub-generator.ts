/**
 * EPUB Generator
 *
 * Generate EPUB files from text content using epub-gen-memory.
 * Matches functionality of Python EPUBGenerator class.
 */

import { EPub } from "epub-gen-memory";

export interface EPUBOptions {
  title: string;
  author?: string;
  content: string;
  chunkNumber?: number;
  totalChunks?: number;
}

/**
 * Sanitize filename to remove invalid characters
 */
function sanitizeFilename(filename: string): string {
  const invalidChars = /[<>:"/\\|?*]/g;
  let sanitized = filename.replace(invalidChars, "_");

  // Limit length
  const maxLength = 200;
  if (sanitized.length > maxLength) {
    sanitized = sanitized.substring(0, maxLength);
  }

  return sanitized.trim();
}

/**
 * Check if text contains HTML tags
 */
function isHTML(text: string): boolean {
  const htmlPattern =
    /<(?:p|div|article|section|h[1-6]|br|span|em|strong|a)\b[^>]*>/i;
  return htmlPattern.test(text);
}

/**
 * Convert plain text to HTML paragraphs
 */
function textToHTML(text: string): string {
  const paragraphs = text.split("\n\n");
  const htmlParts: string[] = [];

  for (const para of paragraphs) {
    const trimmed = para.trim();
    if (trimmed) {
      // Preserve single line breaks within paragraphs
      const withBreaks = trimmed.replace(/\n/g, "<br/>");
      htmlParts.push(`<p>${withBreaks}</p>`);
    }
  }

  return htmlParts.join("\n");
}

/**
 * Prepare content for EPUB - handles both HTML and plain text
 */
function prepareHTMLContent(text: string): string {
  if (isHTML(text)) {
    // Content is already HTML, use it directly
    return text;
  } else {
    // Plain text, convert to HTML paragraphs
    return textToHTML(text);
  }
}

/**
 * Generate an EPUB file from text content
 *
 * @returns Buffer containing the EPUB file data
 */
export async function generateEPUB(options: EPUBOptions): Promise<Buffer> {
  const {
    title,
    author = "Unknown Author",
    content,
    chunkNumber,
    totalChunks,
  } = options;

  // Build full title with chunk info
  let fullTitle = title;
  if (chunkNumber && totalChunks) {
    fullTitle = `${title} - Part ${chunkNumber}/${totalChunks}`;
  } else if (chunkNumber) {
    fullTitle = `${title} - Part ${chunkNumber}`;
  }

  // Prepare HTML content
  const htmlContent = prepareHTMLContent(content);

  // Configure EPUB options
  const epubOptions = {
    title: fullTitle,
    author: author,
    publisher: "Nighttime Story Prep",
    lang: "en",
  };

  // Configure content
  const epubContent = [
    {
      title: fullTitle,
      content: `<h1>${fullTitle}</h1>${htmlContent}`,
    },
  ];

  try {
    // Generate EPUB in memory
    const epub = new EPub(epubOptions, epubContent);
    const buffer = await epub.genEpub();

    console.log(
      `[EPUB] Generated EPUB for "${fullTitle}" (${buffer.length} bytes)`
    );

    return buffer;
  } catch (error) {
    console.error("[EPUB] Failed to generate EPUB:", error);
    throw new Error(
      `Failed to generate EPUB: ${
        error instanceof Error ? error.message : String(error)
      }`
    );
  }
}

/**
 * Generate filename for EPUB
 */
export function generateEPUBFilename(
  title: string,
  chunkNumber?: number
): string {
  const safeTitle = sanitizeFilename(title);

  if (chunkNumber) {
    return `${safeTitle}_part${chunkNumber}.epub`;
  }

  return `${safeTitle}.epub`;
}

/**
 * Generate multiple EPUBs from chunk data
 */
export async function generateMultipleEPUBs(
  chunks: Array<{ text: string; wordCount: number }>,
  title: string,
  author?: string
): Promise<Array<{ buffer: Buffer; filename: string; chunkNumber: number }>> {
  const totalChunks = chunks.length;
  const epubs: Array<{
    buffer: Buffer;
    filename: string;
    chunkNumber: number;
  }> = [];

  for (let i = 0; i < chunks.length; i++) {
    const chunkNumber = i + 1;
    const chunk = chunks[i];

    const buffer = await generateEPUB({
      title,
      author,
      content: chunk.text,
      chunkNumber,
      totalChunks,
    });

    const filename = generateEPUBFilename(title, chunkNumber);

    epubs.push({
      buffer,
      filename,
      chunkNumber,
    });
  }

  return epubs;
}
