import os
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
from mailjet_rest import Client as MailjetClient
import telepot
from tool_schemas import TelegramOutput, EmailOutput, SMSOutput

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
            msg = self.twilio_client.messages.create(
                body=message, from_=self.twilio_number, to=self.my_phone
            )
            return SMSOutput(success=True, summary="SMS sent", message_sid=msg.sid).model_dump_json()
        except Exception as e:
            return SMSOutput(success=False, summary="SMS failed", error=str(e)).model_dump_json()

    def notify_by_email(self, subject: str, body: str) -> str:
        """Sends an email notification to your pre-configured email address."""
        data = {"Messages": [{"From": {"Email": self.mailjet_sender, "Name": "SYNAPSE Agent"},
                              "To": [{"Email": self.my_email}], "Subject": subject, "TextPart": body}]}
        try:
            result = self.mailjet_client.send.create(data=data)
            return EmailOutput(success=True, summary="Email sent",
                               message_id=str(result.status_code)).model_dump_json()
        except Exception as e:
            return EmailOutput(success=False, summary="Email failed", error=str(e)).model_dump_json()

    def notify_by_telegram(self, message: str) -> str:
        """Sends a Telegram notification to your pre-configured chat."""
        try:
            result = self.telegram_bot.sendMessage(self.my_telegram_id, message)
            return TelegramOutput(success=True, summary="Telegram message sent",
                                  message_id=result.get("message_id")).model_dump_json()
        except Exception as e:
            return TelegramOutput(success=False, summary="Telegram failed", error=str(e)).model_dump_json()