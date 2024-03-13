from setup import creds
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.utils import formataddr


def send_html_email(from_name, from_address, recipients_list, subject, content, mode, logo=True, attachment=True):
    # Dictionary of recipients in creds
    for k, v in recipients_list.items():
        to_name = k
        to_address = v

        msg = MIMEMultipart(mode)
        msg['From'] = formataddr((from_name, from_address))
        msg['To'] = formataddr((to_name, to_address))
        msg["Subject"] = subject

        msg_html = MIMEText(content, _subtype='html')

        msg.attach(msg_html)

        if logo:
            with open(creds.logo, 'rb') as logo_file:
                logo = logo_file.read()
                msg_logo = MIMEImage(logo, 'jpg')
                msg_logo.add_header('Content-ID', '<image1>')
                msg_logo.add_header('Content-Disposition', 'inline', filename='Logo.jpg')
                msg.attach(msg_logo)

        if attachment:
            with open(f"./{creds.pdf_attachment}", 'rb') as file:
                pdf = file.read()

                attached_file = MIMEApplication(_data=pdf,
                                                _subtype='pdf')

                attached_file.add_header(_name='content-disposition',
                                         _value='attachment',
                                         filename=f"{creds.pdf_attachment}")
                msg.attach(attached_file)

        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.ehlo()
            connection.starttls()
            connection.ehlo()
            connection.login(user=creds.gmail_user, password=creds.gmail_pw)
            connection.sendmail(from_address, to_address, msg.as_string().encode('utf-8'))
            connection.quit()
