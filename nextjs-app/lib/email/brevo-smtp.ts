import nodemailer from "nodemailer";
import type { Transporter } from "nodemailer";

/**
 * Create a nodemailer transporter configured for Brevo SMTP
 */
export function createBrevoTransporter(): Transporter {
  const host = process.env.BREVO_SMTP_HOST || "smtp-relay.brevo.com";
  const port = parseInt(process.env.BREVO_SMTP_PORT || "587", 10);
  const user = process.env.BREVO_SMTP_USER;
  const pass = process.env.BREVO_SMTP_PASSWORD;

  if (!user || !pass) {
    throw new Error("BREVO_SMTP_USER and BREVO_SMTP_PASSWORD must be set");
  }

  return nodemailer.createTransport({
    host,
    port,
    secure: false, // true for 465, false for other ports
    auth: {
      user,
      pass,
    },
  });
}

export interface SendEmailParams {
  to: string;
  from: string;
  subject: string;
  text: string;
  html?: string;
  attachments?: Array<{
    filename: string;
    content: Buffer;
    contentType?: string;
  }>;
}

/**
 * Send an email via Brevo SMTP
 * @param params Email parameters
 * @returns Message info from nodemailer
 */
export async function sendEmail(params: SendEmailParams) {
  // Check if TEST_MODE is enabled
  if (process.env.TEST_MODE === "true") {
    console.log("[TEST_MODE] Skipping actual email send:", {
      to: params.to,
      from: params.from,
      subject: params.subject,
      hasAttachments: !!params.attachments?.length,
    });
    return { messageId: "test-mode-message-id", accepted: [params.to] };
  }

  const transporter = createBrevoTransporter();

  try {
    const info = await transporter.sendMail(params);
    console.log("Email sent successfully:", {
      messageId: info.messageId,
      to: params.to,
      subject: params.subject,
    });
    return info;
  } catch (error) {
    console.error("Failed to send email:", error);
    throw error;
  }
}

/**
 * Send an email with EPUB attachment (commonly used for Kindle delivery)
 */
export async function sendEmailWithAttachment(params: SendEmailParams) {
  return sendEmail(params);
}
