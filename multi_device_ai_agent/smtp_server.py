import smtpd
import asyncore
import logging
import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv  # Load dotenv

# Load environment variables from .env
load_dotenv()

logging.basicConfig(level=logging.INFO)

# Retrieve SMTP settings from .env
SMTP_RELAY_SERVER = os.getenv("SMTP_RELAY_SERVER", "smtp.gmail.com")
SMTP_RELAY_PORT = int(os.getenv("SMTP_RELAY_PORT", 587))
SMTP_RELAY_USERNAME = os.getenv("SMTP_RELAY_USERNAME", "your-email@gmail.com")
SMTP_RELAY_PASSWORD = os.getenv("SMTP_RELAY_PASSWORD", "your-app-password")


class SMTPServer(smtpd.SMTPServer):
    """A simple SMTP server for relaying emails."""

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        logging.info(f"📨 Received email from {mailfrom} to {rcpttos}")
        logging.info(f"📄 Email Data:\n{data.decode()}")

        # Relay email via external SMTP provider
        try:
            msg = EmailMessage()
            msg.set_content(data.decode())
            msg["Subject"] = "Relayed Email"
            msg["From"] = SMTP_RELAY_USERNAME
            msg["To"] = ", ".join(rcpttos)

            with smtplib.SMTP(SMTP_RELAY_SERVER, SMTP_RELAY_PORT) as server:
                server.starttls()  # Secure connection
                server.login(SMTP_RELAY_USERNAME, SMTP_RELAY_PASSWORD)  # Authenticate
                server.send_message(msg)

            logging.info(f"✅ Email successfully relayed to {rcpttos}")

        except Exception as e:
            logging.error(f"❌ Email relaying failed: {str(e)}")

        return

if __name__ == "__main__":
    logging.info("🚀 Starting local SMTP server on port 1025...")
    server = SMTPServer(('0.0.0.0', 1025), None)

    try:
        asyncore.loop()  # Keep server running
    except KeyboardInterrupt:
        logging.info("🛑 Shutting down SMTP server...")
