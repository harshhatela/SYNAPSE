import os
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
from mailjet_rest import Client as MailjetClient
import telepot

class NotificationAgent:
    """Agent for sending notifications via SMS, Email, and Telegram."""
    def __init__(self):
        load_dotenv()
        self.my_phone = os.getenv("MY_PHONE_NUMBER")
        self.my_email = os.getenv("MY_EMAIL")
        self.my_telegram_id = os.getenv("TELEGRAM_CHAT_ID")
        self.twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.mailjet_client = MailjetClient(auth=(os.getenv("MAILJET_API_KEY"), os.getenv("MAILJET_SECRET_KEY")), version='v3.1')
        self.mailjet_sender = os.getenv("MAILJET_SENDER_EMAIL")
        self.telegram_bot = telepot.Bot(os.getenv("TELEGRAM_BOT_TOKEN"))

    def notify_by_sms(self, message: str) -> str:
        """Sends an SMS notification to your pre-configured phone number."""
        try:
            self.twilio_client.messages.create(body=message, from_=self.twilio_number, to=self.my_phone)
            return "SMS notification sent."
        except Exception as e: return f"Error sending SMS: {e}"

    def notify_by_email(self, subject: str, body: str) -> str:
        """Sends an email notification to your pre-configured email address."""
        data = {'Messages': [{"From": {"Email": self.mailjet_sender, "Name": "SYNAPSE Agent"}, "To": [{"Email": self.my_email}], "Subject": subject, "TextPart": body}]}
        try:
            self.mailjet_client.send.create(data=data)
            return "Email notification sent."
        except Exception as e: return f"Error sending email: {e}"

    def notify_by_telegram(self, message: str) -> str:
        """Sends a Telegram notification to your pre-configured chat."""
        try:
            self.telegram_bot.sendMessage(self.my_telegram_id, message)
            return "Telegram notification sent."
        except Exception as e: return f"Error sending Telegram message: {e}"