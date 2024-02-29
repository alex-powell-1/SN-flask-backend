import flask
from flask import request
from waitress import serve
from setup import creds, email_engine, sms_engine
import pandas
from datetime import datetime

app = flask.Flask(__name__)
dev = False


def send_email(first_name, email):
    """Send PDF attachment to customer"""
    recipient = {first_name: email}

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

    email_engine.send_html_email(from_name=creds.company_name,
                                 from_address=creds.gmail_user,
                                 recipients_list=recipient,
                                 subject=creds.email_subject,
                                 content=flask.render_template('email_body.html'))


def send_text(first_name, last_name, phone):
    """Send text message to sales team mangers for customer followup"""
    name = f"{first_name} {last_name}".title()
    message = (f"{name} just requested a phone follow-up about {creds.service}.\n"
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
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    send_email(first_name, email)
    send_text(first_name, last_name, phone)
    design_lead_data = [[str(datetime.now())[:-7], first_name, last_name, email, phone]]
    df = pandas.DataFrame(design_lead_data, columns=["date", "first_name", "last_name", "email", "phone"])
    # Looks for file. If it has been deleted, it will recreate.
    try:
        pandas.read_csv(creds.lead_log)
    except FileNotFoundError:
        df.to_csv(creds.lead_log, mode='a', header=True, index=False)
    else:
        df.to_csv(creds.lead_log, mode='a', header=False, index=False)

    finally:
        print(f"{creds.service} request for information received!".capitalize())
        return ("Your request for information has been received. "
                "Please check your email for more information from our team.")


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
        print("Newsletter signup complete!")
        return "Newsletter signup complete!"


if __name__ == '__main__':
    if dev:
        app.run(debug=True, port=9999)
    else:
        print("Flask Server Running")
        serve(app, host='localhost', port=9999)

