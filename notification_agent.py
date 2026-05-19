import os
import logging
from tool_schemas import TelegramOutput, EmailOutput, SMSOutput

logger = logging.getLogger(__name__)


class NotificationAgent:
    """Agent for sending notifications via SMS, Email, and Telegram.

    Clients are lazily constructed so a missing provider credential disables
    only that channel rather than crashing backend startup.
    """

    def __init__(self):
        self.my_phone = os.getenv("MY_PHONE_NUMBER")
        self.my_email = os.getenv("MY_EMAIL")
        self.my_telegram_id = os.getenv("TELEGRAM_CHAT_ID")
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.mailjet_sender = os.getenv("MAILJET_SENDER_EMAIL")
        self._twilio = None
        self._mailjet = None
        self._telegram = None

    def _get_twilio(self):
        if self._twilio is not None:
            return self._twilio
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        if not (sid and token):
            return None
        from twilio.rest import Client as TwilioClient
        self._twilio = TwilioClient(sid, token)
        return self._twilio

    def _get_mailjet(self):
        if self._mailjet is not None:
            return self._mailjet
        key = os.getenv("MAILJET_API_KEY")
        secret = os.getenv("MAILJET_SECRET_KEY")
        if not (key and secret):
            return None
        from mailjet_rest import Client as MailjetClient
        self._mailjet = MailjetClient(auth=(key, secret), version="v3.1")
        return self._mailjet

    def _get_telegram(self):
        if self._telegram is not None:
            return self._telegram
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            return None
        import telepot
        self._telegram = telepot.Bot(token)
        return self._telegram

    def notify_by_sms(self, message: str) -> str:
        client = self._get_twilio()
        if client is None or not self.twilio_number or not self.my_phone:
            return SMSOutput(
                success=False, summary="SMS not configured",
                error="Twilio credentials or phone numbers missing",
            ).model_dump_json()
        try:
            msg = client.messages.create(
                body=message, from_=self.twilio_number, to=self.my_phone
            )
            return SMSOutput(success=True, summary="SMS sent", message_sid=msg.sid).model_dump_json()
        except Exception as e:
            return SMSOutput(success=False, summary="SMS failed", error=str(e)).model_dump_json()

    def notify_by_email(self, subject: str, body: str) -> str:
        client = self._get_mailjet()
        if client is None or not self.mailjet_sender or not self.my_email:
            return EmailOutput(
                success=False, summary="Email not configured",
                error="Mailjet credentials or addresses missing",
            ).model_dump_json()
        data = {"Messages": [{"From": {"Email": self.mailjet_sender, "Name": "SYNAPSE Agent"},
                              "To": [{"Email": self.my_email}], "Subject": subject, "TextPart": body}]}
        try:
            result = client.send.create(data=data)
            return EmailOutput(success=True, summary="Email sent",
                               message_id=str(result.status_code)).model_dump_json()
        except Exception as e:
            return EmailOutput(success=False, summary="Email failed", error=str(e)).model_dump_json()

    def notify_by_telegram(self, message: str) -> str:
        bot = self._get_telegram()
        if bot is None or not self.my_telegram_id:
            return TelegramOutput(
                success=False, summary="Telegram not configured",
                error="TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing",
            ).model_dump_json()
        try:
            result = bot.sendMessage(self.my_telegram_id, message)
            return TelegramOutput(success=True, summary="Telegram message sent",
                                  message_id=result.get("message_id")).model_dump_json()
        except Exception as e:
            return TelegramOutput(success=False, summary="Telegram failed", error=str(e)).model_dump_json()
