import smtplib
import os
from email.mime.text import MIMEText
from langchain.tools import Tool  # ✅ Import Tool

# Environment variables for SMTP server
SMTP_SERVER = os.getenv("SMTP_SERVER", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", 1025))

def send_email(recipient, subject, message):
    """Send an email using the local SMTP server."""
    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = "ai-agent@example.com"
        msg["To"] = recipient

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail("ai-agent@example.com", [recipient], msg.as_string())

        print(f"✅ Email successfully sent to {recipient}")
        return {"status": "success", "message": f"Email sent to {recipient}"}
    
    except Exception as e:
        print(f"❌ Email sending failed: {str(e)}")
        return {"status": "error", "error": str(e)}

# ✅ Define the `send_email_tool` for LangChain
send_email_tool = Tool(
    name="Email Agent",
    func=lambda input_data: send_email(
        recipient=input_data.get("recipient", ""),
        subject=input_data.get("subject", ""),
        message=input_data.get("message", "")
    ),
    description="Send an email with 'recipient', 'subject', and 'message'."
)

print("📧 Email Agent initialized and ready to send emails.")
