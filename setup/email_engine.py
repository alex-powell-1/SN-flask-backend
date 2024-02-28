from email.encoders import encode_base64
from setup import creds
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr


def send_html_email(from_name, from_address, recipients_list, subject, content):
    # Dictionary of recipients in creds
    for k, v in recipients_list.items():
        to_name = k
        to_address = v

        msg = MIMEMultipart('related')
        msg['From'] = formataddr((from_name, from_address))
        msg['To'] = formataddr((to_name, to_address))
        msg["Subject"] = subject

        msg_html = MIMEText(content, _subtype='html')

        msg.attach(msg_html)

        with open(f"./{creds.pdf_attachment}", 'rb') as file:
            pdf = file.read()
            attached_file = MIMEApplication(pdf, _subtype='pdf', _encoder=encode_base64)
            attached_file.add_header('content-disposition', 'attachment', filename=f"{creds.pdf_attachment}")

        msg.attach(attached_file)

        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.ehlo()
            connection.starttls()
            connection.ehlo()
            connection.login(user=creds.gmail_user, password=creds.gmail_pw)
            connection.sendmail(from_address, to_address, msg.as_string().encode('utf-8'))
            connection.quit()
