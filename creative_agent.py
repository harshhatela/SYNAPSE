import os
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
from mailjet_rest import Client as MailjetClient
import telepot
from linux_agent import LinuxTool

class CreativeTool:
    def __init__(self):
        load_dotenv()
        # Twilio
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.twilio_client = TwilioClient(self.twilio_sid, self.twilio_token)
        
        # Mailjet
        self.mailjet_key = os.getenv("MAILJET_API_KEY")
        self.mailjet_secret = os.getenv("MAILJET_API_SECRET")
        self.mailjet_sender = os.getenv("MAILJET_SENDER_EMAIL")
        self.mailjet_client = MailjetClient(auth=(self.mailjet_key, self.mailjet_secret), version='v3.1')
        
        # Telegram
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.telegram_bot = telepot.Bot(self.telegram_token)
        
        # For creating files on the server
        self.linux_tool = LinuxTool()

    def send_sms(self, to_number: str, body: str) -> str:
        """Sends an SMS to a specified phone number using Twilio."""
        try:
            message = self.twilio_client.messages.create(body=body, from_=self.twilio_number, to=to_number)
            return f"SMS sent successfully to {to_number}. SID: {message.sid}"
        except Exception as e:
            return f"Error sending SMS: {e}"

    def send_email(self, to_email: str, subject: str, body: str) -> str:
        """Sends an email to a specified recipient using Mailjet."""
        data = {
          'Messages': [
            {
              "From": {"Email": self.mailjet_sender, "Name": "SYNAPSE Agent"},
              "To": [{"Email": to_email}],
              "Subject": subject,
              "TextPart": body
            }
          ]
        }
        try:
            result = self.mailjet_client.send.create(data=data)
            if result.status_code == 200:
                return f"Email sent successfully to {to_email}."
            else:
                return f"Failed to send email: {result.json()}"
        except Exception as e:
            return f"Error sending email: {e}"

    def send_telegram_message(self, message: str) -> str:
        """Sends a message to the pre-configured Telegram chat."""
        try:
            self.telegram_bot.sendMessage(self.telegram_chat_id, message)
            return "Telegram message sent successfully."
        except Exception as e:
            return f"Error sending Telegram message: {e}"

    def create_streamlit_app(self, python_code: str, file_path: str) -> str:
        """Creates a Python file on the remote server with the given Streamlit code."""
        # Use the LinuxTool to write the file via SSH
        command = f"echo '{python_code}' > {file_path}"
        return self.linux_tool.run(command)