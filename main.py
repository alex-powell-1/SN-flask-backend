import flask
from flask import request
from waitress import serve
from setup import creds, email_engine, sms_engine, product_engine
import pandas
from flask_cors import CORS
from jinja2 import Template
import urllib.parse
from datetime import datetime
from twilio.twiml.messaging_response import MessagingResponse
from setup.query_engine import QueryEngine
from setup.order_engine import Order, utc_to_local
import code128
import os
import json
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from email import utils

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
        "signature_name": creds.signature_name,
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
                                 content=email_content,
                                 mode='mixed',
                                 logo=False,
                                 attachment=True)


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
    """Route for information request about company service. Sends user an email with PDF attachment
    and personalized details."""

    data = request.json
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone = data.get('phone')
    timeline = data.get('timeline')
    interested_in = data.get('interested_in')

    if phone != "":
        interests = ""
        if interested_in is not None:
            for x in interested_in:
                interests += x
                if len(interested_in) > 1:
                    interests += ", "
        send_text(first_name, last_name, phone, interests, timeline)

    send_email(first_name, email)

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
    """Get contact and product information from user who wants notification of when
    a product comes back into stock."""
    data = request.json
    email = data.get('email')
    item_no = data.get('sku')
    try:
        df = pandas.read_csv(creds.stock_notification_log)
    except FileNotFoundError:
        pass
    else:
        entries = df.to_dict("records")
        for x in entries:
            if x['email'] == email and str(x['item_no']) == item_no:
                print(f"{email} is already on file for this item")
                return ("This email address is already on file for this item. We will send you an email "
                        "when it comes back in stock. Please contact our office at <a href='tel:8288740679'>(828) 874-0679</a> if you need an alternative "
                        "item. Thank you!"), 400

    stock_notification_data = [[str(datetime.now())[:-7], email, item_no]]
    df = pandas.DataFrame(stock_notification_data, columns=["date", "email", str("item_no")])
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
    """Route for website pop-up. Offers user a coupon and adds their information to a csv.
    NOTES: ADD check for email already on file!"""
    data = request.json
    email = data.get('email')
    try:
        df = pandas.read_csv(creds.newsletter_log)
    except FileNotFoundError:
        print("Coupon File Not Found")
    else:
        entries = df.to_dict("records")
        for x in entries:
            if x['email'] == email:
                print(f"{email} is already on file")
                return "This email address is already on file.", 400

    recipient = {"": email}
    with open("./templates/new10.html", "r") as file:
        template_str = file.read()

    jinja_template = Template(template_str)

    email_data = {
        "title": f"Welcome to {creds.company_name}",
        "greeting": f"Hi!",
        "service": creds.service,
        "coupon": "NEW10",
        "company": creds.company_name,
        "list_items": creds.list_items,
        "signature_name": creds.signature_name,
        "signature_title": creds.signature_title,
        "company_phone": creds.company_phone,
        "company_url": creds.company_url,
        "company_reviews": creds.company_reviews
    }

    email_content = jinja_template.render(email_data)

    email_engine.send_html_email(from_name=creds.company_name,
                                 from_address=creds.gmail_user,
                                 recipients_list=recipient,
                                 subject=f"Welcome to {creds.company_name}! Coupon Inside!",
                                 content=email_content,
                                 mode='related',
                                 logo=True,
                                 attachment=False)

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
    """Route for incoming SMS messages to be used with client messenger application.
    Saves all incoming SMS/MMS messages to share drive csv file."""
    raw_data = request.get_data()
    # Decode
    string_code = raw_data.decode('utf-8')
    # Parse to dictionary
    msg = urllib.parse.parse_qs(string_code)

    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    from_phone = msg['From'][0]
    to_phone = msg['To'][0]
    body = msg['Body'][0]

    # Get MEDIA URL for MMS Messages
    if int(msg['NumMedia'][0]) > 0:
        media = msg['MediaUrl0'][0]
        media_url = media[0:8] + creds.twilio_account_sid + ":" + creds.twilio_auth_token + "@" + media[8:]
    else:
        media_url = "No Media"

    # Get Customer Name and Category from SQL
    db = QueryEngine()

    query = f"""
    SELECT FST_NAM, LST_NAM, CATEG_COD
    FROM AR_CUST
    WHERE PHONE_1 = '{sms_engine.format_phone(from_phone, mode="counterpoint")}'
    """
    response = db.query_db(query)

    if response is not None:
        first_name = response[0][0]
        last_name = response[0][1]
        full_name = first_name + " " + last_name
        category = response[0][2]

    # For people with no phone in our database
    else:
        full_name = "Unknown"
        category = "Unknown"

    log_data = [[date, to_phone, from_phone, body, full_name, category.title(), media_url]]
    # Write dataframe to CSV file
    df = pandas.DataFrame(log_data, columns=["date", "to_phone", "from_phone", "body", "name", "category", "media"])
    # Look for existing CSV file
    try:
        pandas.read_csv(creds.incoming_sms_log)
    except FileNotFoundError:
        sms_engine.write_all_twilio_messages_to_share()
        df.to_csv(creds.incoming_sms_log, mode='a', header=False, index=False)
    else:
        df.to_csv(creds.incoming_sms_log, mode='a', header=False, index=False)

    # Return Response to Twilio
    resp = MessagingResponse()
    return str(resp)


@app.route('/bc', methods=['POST'])
def bc_orders():
    response_data = request.get_json()
    order_id = response_data['data']['id']
    order = Order(order_id)
    if order.payment_status != 'declined':
        bc_date = order.date_created
        dt_date = utils.parsedate_to_datetime(bc_date)
        date = utc_to_local(dt_date).strftime("%m/%d/%Y")
        time = utc_to_local(dt_date).strftime("%I:%M:%S %p")
        number_of_items = order.items_total
        ticket_notes = order.customer_message
        products = order.order_products
        product_list = []
        for x in products:
            item = product_engine.Product(x['sku'])
            product_details = {'sku': item.item_no,
                               'name': item.descr,
                               'qty': x['quantity']
                               }
            product_list.append(product_details)
        # Create Barcode
        code128.image(order_id).save("barcode.png")  # with PIL present
        with open("barcode.svg", "w") as f:
            f.write(code128.svg(order_id))

        # Print the document
        doc = DocxTemplate("./template.docx")
        barcode = InlineImage(doc, './barcode.png', height=Mm(15))  # width is in millimetres
        context = {
            'order_number': order_id,
            'company_name': creds.company_name,
            'co_address': creds.company_address,
            'co_phone': creds.company_phone,
            'cb_name': order.billing_first_name + " " + order.billing_last_name,
            'cb_phone': order.billing_phone,
            'cb_email': order.billing_email,
            'cb_street': order.billing_street_address,
            # 'cb_street_2': order.billing_street_2,
            'cb_city': order.billing_city,
            'cb_state': order.billing_state,
            'cb_zip': order.billing_zip,
            'cs_name': order.shipping_first_name + " " + order.shipping_last_name,
            'cs_phone': order.shipping_phone,
            'cs_email': order.shipping_email,
            'cs_street': order.shipping_street_address,
            'shipping_method': order.shipping_method,
            # 'cs_street_2': order.shipping_street_2,
            'cs_city': order.shipping_city,
            'cs_state': order.shipping_state,
            'cs_zip': order.shipping_zip,
            'order_date': date,
            'order_time': time,
            'order_subtotal': float(order.subtotal_inc_tax),
            'order_shipping': float(order.shipping_cost_inc_tax),
            'order_total': float(order.total_inc_tax),
            'number_of_items': number_of_items,
            'ticket_notes': ticket_notes,
            'products': product_list,
            'coupon_code': order.order_coupons['code'],
            'coupon_discount': float(order.coupon_discount),
            'loyalty': float(order.store_credit_amount),
            'gc_amount': float(order.gift_certificate_amount),
            'barcode': barcode
        }
        doc.render(context)
        ticket_name = f"ticket_{order_id}_{datetime.now().strftime("%m_%d_%y_%H_%M_%S")}.docx"
        file_path = creds.ticket_location + ticket_name
        doc.save(file_path)
        os.startfile(file_path, "print")

    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


if __name__ == '__main__':
    if dev:
        app.run(debug=True, port=9999)
    else:
        print("Flask Server Running")
        serve(app, host='localhost', port=9999)
