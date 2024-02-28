from setup import creds
from twilio.rest import Client
from datetime import datetime
from twilio.base.exceptions import TwilioRestException
import pandas

class SMSEngine:
    def __init__(self):
        self.phone = creds.twilio_phone_number
        self.sid = creds.twilio_account_sid
        self.token = creds.twilio_auth_token

    def send_text(self, name, to_phone, message, log_location, create_log=True, test_mode=False):
        twilio_response = ""
        if test_mode:
            print(f"Sending test sms text to {name}: {message}")
            twilio_response = "Test Mode"
        if not test_mode:
            # for SMS Messages
            client = Client(self.sid, self.token)
            try:
                twilio_message = client.messages.create(
                    from_=self.phone,
                    to=to_phone,
                    body=message)

            except TwilioRestException as err:
                if str(err)[-22:] == "is not a mobile number":
                    twilio_response = "landline"
            else:
                twilio_response = twilio_message.sid
                print(twilio_message.to, twilio_message.body)

        if create_log:
            create_sms_log(name, to_phone, message, twilio_response, log_location=log_location)


def create_sms_log(name, phone, sent_message, response, log_location):
    """ Creates a log file on share server. Logs date, phone, message, and twilio response"""
    log_message = sent_message
    log_data = [[str(datetime.now())[:-7], name, format_phone(phone, mode="Counterpoint"),
                 log_message.strip().replace("\n", ""), response]]
    df = pandas.DataFrame(log_data, columns=["date", "name", "to_phone", "body", "response"])
    # Looks for file. If it has been deleted, it will recreate.

    try:
        pandas.read_csv(log_location)
    except FileNotFoundError:
        df.to_csv(log_location, mode='a', header=True, index=False)
    else:
        df.to_csv(log_location, mode='a', header=False, index=False)


def format_phone(phone_number, mode="Twilio", prefix=False):
    """Cleanses input data and returns masked phone for either Twilio or Counterpoint configuration"""
    phone_number_as_string = str(phone_number)
    # Strip away extra symbols
    formatted_phone = phone_number_as_string.replace(" ", "")  # Remove Spaces
    formatted_phone = formatted_phone.replace("-", "")  # Remove Hyphens
    formatted_phone = formatted_phone.replace("(", "")  # Remove Open Parenthesis
    formatted_phone = formatted_phone.replace(")", "")  # Remove Close Parenthesis
    formatted_phone = formatted_phone.replace("+1", "")  # Remove +1
    formatted_phone = formatted_phone[-10:]  # Get last 10 characters
    if mode == "clickable":
        # Masking ###-###-####
        clickable_phone = "(" + formatted_phone[0:3] + ") " + formatted_phone[3:6] + "-" + formatted_phone[6:10]
        return clickable_phone
    else:
        if prefix:
            formatted_phone = "+1" + formatted_phone
        return formatted_phone
