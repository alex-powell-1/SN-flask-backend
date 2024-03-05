import flask
from flask import request
from waitress import serve
from setup import creds, email_engine, sms_engine
import pandas
from datetime import datetime
from flask_cors import CORS
from jinja2 import Template
from flask import Response
from twilio.twiml.messaging_response import MessagingResponse

app = flask.Flask(__name__)
CORS(app)

dev = False


def send_email(first_name, email):
    """Send PDF attachment to customer"""
    recipient = {first_name: email}
    with open("./templates/email_body.html", "r") as file:
        template_str = file.read()

    jinja_template = Template(template_str)

    email_data = {
        "title": creds.email_subject,
        "greeting": f"Hi {first_name},",
        "service": creds.service,
        "company": creds.company_name,
        "list_items": creds.list_items,
        "signature_name":creds.signature_name,
        "signature_title": creds.signature_title,
        "company_phone": creds.company_phone,
        "company_url": creds.company_url,
        "company_reviews": creds.company_reviews
    }

    email_content = jinja_template.render(email_data)

    email_engine.send_html_email(from_name=creds.company_name,
                                 from_address=creds.gmail_user,
                                 recipients_list=recipient,
                                 subject=creds.email_subject,
                                 content=email_content)


def send_text(first_name, last_name, phone, interested_in, timeline):
    """Send text message to sales team mangers for customer followup"""
    name = f"{first_name} {last_name}".title()
    message = (f"{name} just requested a phone follow-up about {creds.service}.\n"
               f"Interested in: {interested_in}\n"
               f"Timeline: {timeline}\n"
               f"Phone: {sms_engine.format_phone(phone, mode='clickable')}")
    sms = sms_engine.SMSEngine()
    for k, v in creds.lead_recipient.items():
        sms.send_text(name=name,
                      to_phone=sms_engine.format_phone(v, prefix=True),
                      message=message,
                      log_location=creds.sms_log,
                      create_log=True)


@app.route('/design', methods=["POST"])
def get_service_information():
    data = request.json
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone = data.get('phone')
    timeline = data.get('timeline')
    interested_in = data.get('interested_in')

    interests = ""
    if interested_in is not None:
        for x in interested_in:
            interests += x
            if len(interested_in) > 1:
                interests += ", "

    send_email(first_name, email)
    send_text(first_name, last_name, phone, interests, timeline)

    design_lead_data = [[str(datetime.now())[:-7], first_name, last_name, email, phone, interested_in, timeline]]
    df = pandas.DataFrame(design_lead_data, columns=["date", "first_name", "last_name", "email", "phone", "interested_in", "timeline"])

    # Looks for file. If it has been deleted, it will recreate.
    try:
        pandas.read_csv(creds.lead_log)
    except FileNotFoundError:
        df.to_csv(creds.lead_log, mode='a', header=True, index=False)
    else:
        df.to_csv(creds.lead_log, mode='a', header=False, index=False)

    finally:
        print(f"{creds.service} request for information received!".capitalize())

    return "Your information has been received. Please check your email for more information from our team."


@app.route('/stock_notify', methods=['POST'])
def stock_notification():
    """get contact and product information from user who wants notification of when
    a product comes back into stock"""
    data = request.json
    email = data.get('email')
    item_no = data.get('sku')
    stock_notification_data = [[str(datetime.now())[:-7], email, item_no]]
    df = pandas.DataFrame(stock_notification_data, columns=["date", "email", "item_no"])
    # Looks for file. If it has been deleted, it will recreate.
    try:
        pandas.read_csv(creds.stock_notification_log)
    except FileNotFoundError:
        df.to_csv(creds.stock_notification_log, mode='a', header=True, index=False)
    else:
        df.to_csv(creds.stock_notification_log, mode='a', header=False, index=False)

    finally:
        return "Your submission was received."


@app.route('/newsletter', methods=['POST'])
def newsletter_signup():
    email = request.form.get('email')
    newsletter_data = [[str(datetime.now())[:-7], email]]
    df = pandas.DataFrame(newsletter_data, columns=["date", "email"])
    # Looks for file. If it has been deleted, it will recreate.
    try:
        pandas.read_csv(creds.newsletter_log)
    except FileNotFoundError:
        df.to_csv(creds.newsletter_log, mode='a', header=True, index=False)
    else:
        df.to_csv(creds.newsletter_log, mode='a', header=False, index=False)

    finally:
        return "OK", 200


@app.route('/sms', methods=['POST'])
def incoming_sms():
    data = request.json
    print(data)
    return "OK", 200


if __name__ == '__main__':
    if dev:
        app.run(debug=True, port=9999)
    else:
        print("Flask Server Running")
        serve(app, host='localhost', port=9999)

