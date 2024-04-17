import json
import os
import time
import urllib.parse
from datetime import datetime
from email import utils
import pika
import sys

import flask
import pandas
import requests
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from flask import request
from flask_cors import CORS
from jinja2 import Template
from twilio.twiml.messaging_response import MessagingResponse
from waitress import serve

from setup import barcode_engine
from setup import creds, email_engine, sms_engine, product_engine
from setup import log_engine
from setup.order_engine import Order, utc_to_local

app = flask.Flask(__name__)
CORS(app)

# When False, app is served by Waitress
dev = False

# When True, disables sms text and automatic printing in office
test_mode = False


@app.route('/design', methods=["POST"])
def get_service_information():
    """Route for information request about company service. Sends JSON to RabbitMQ for processing."""
    data = request.json
    payload = json.dumps(data)
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='design_info')
    channel.basic_publish(exchange='',
                          routing_key='design_info',
                          body=payload)
    connection.close()

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
                return ("This email address is already on file for this item. We will send you an email "
                        "when it comes back in stock. Please contact our office at "
                        "<a href='tel:8288740679'>(828) 874-0679</a> if you need an alternative "
                        "item. Thank you!"), 400

    stock_notification_data = [[str(datetime.now())[:-7], email, item_no]]
    df = pandas.DataFrame(stock_notification_data, columns=["date", "email", str("item_no")])
    log_engine.write_log(df, creds.stock_notification_log)
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
    log_engine.write_log(df, creds.newsletter_log)
    return "OK", 200


@app.route('/sms', methods=['POST'])
def incoming_sms():
    """Webhook route for incoming SMS/MMS messages to be used with client messenger application.
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
    full_name, category = sms_engine.lookup_customer_data(sms_engine.format_phone(from_phone, mode="counterpoint"))

    log_data = [[date, to_phone, from_phone, body, full_name, category.title(), media_url]]

    # Write dataframe to CSV file
    df = pandas.DataFrame(log_data, columns=["date", "to_phone", "from_phone", "body", "name", "category", "media"])
    log_engine.write_log(df, creds.incoming_sms_log)

    # Return Response to Twilio
    resp = MessagingResponse()
    return str(resp)


@app.route('/bc', methods=['POST'])
def bc_orders():
    """Webhook route for incoming orders. Renders pick/loading ticket. Automatically prints"""
    response_data = request.get_json()
    order_id = response_data['data']['id']
    now = datetime.now()
    # Create order object
    try:
        order = Order(order_id)
        # Filter out DECLINED payments
        if order.payment_status != 'declined' and order.payment_status != "":
            bc_date = order.date_created
            # Format Date and Time
            dt_date = utils.parsedate_to_datetime(bc_date)
            date = utc_to_local(dt_date).strftime("%m/%d/%Y")  # ex. 04/24/2024
            time = utc_to_local(dt_date).strftime("%I:%M:%S %p")  # ex. 02:34:24 PM
            products = order.order_products
            product_list = []
            gift_card_only = True
            for x in products:
                if x['type'] == 'physical':
                    gift_card_only = False
                item = product_engine.Product(x['sku'])
                product_details = {'sku': item.item_no,
                                   'name': item.descr,
                                   'qty': x['quantity'],
                                   'base_price': x['base_price'],
                                   'base_total': x['base_total']
                                   }
                product_list.append(product_details)

            # FILTER OUT GIFT CARDS (NO PHYSICAL PRODUCTS)
            if not gift_card_only:
                # Create Barcode
                barcode_filename = 'barcode'
                barcode_engine.generate_barcode(data=order_id, filename=barcode_filename)
                # Create the Word document
                doc = DocxTemplate("./templates/ticket_template.docx")
                barcode = InlineImage(doc, f'./{barcode_filename}.png', height=Mm(15))  # width in mm
                context = {
                    # Company Details
                    'company_name': creds.company_name,
                    'co_address': creds.company_address,
                    'co_phone': creds.company_phone,
                    # Order Details
                    'order_number': order_id,
                    'order_date': date,
                    'order_time': time,
                    'order_subtotal': float(order.subtotal_inc_tax),
                    'order_shipping': float(order.shipping_cost_inc_tax),
                    'order_total': float(order.total_inc_tax),
                    # Customer Billing
                    'cb_name': order.billing_first_name + " " + order.billing_last_name,
                    'cb_phone': order.billing_phone,
                    'cb_email': order.billing_email,
                    'cb_street': order.billing_street_address,
                    'cb_city': order.billing_city,
                    'cb_state': order.billing_state,
                    'cb_zip': order.billing_zip,
                    # Customer Shipping
                    'shipping_method': order.shipping_method,
                    'cs_name': order.shipping_first_name + " " + order.shipping_last_name,
                    'cs_phone': order.shipping_phone,
                    'cs_email': order.shipping_email,
                    'cs_street': order.shipping_street_address,
                    'cs_city': order.shipping_city,
                    'cs_state': order.shipping_state,
                    'cs_zip': order.shipping_zip,
                    # Product Details
                    'number_of_items': order.items_total,
                    'ticket_notes': order.customer_message,
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
                # Print the file to default printer
                os.startfile(file_path, "print")
                # Delete barcode files
                os.remove(f"./{barcode_filename}.png")
                os.remove(f"./{order_id}.svg")
    except Exception as err:
        error_type = "general catch"
        error_data = [[str(now)[:-7], error_type, err]]
        df = pandas.DataFrame(error_data, columns=["date", "error_type", "message"])
        log_engine.write_log(df, f"{creds.lead_error_log}/general_error_{now.strftime("%m_%d_%y_%H_%M_%S")}.csv")
        print(err)

    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


if __name__ == '__main__':
    if dev:
        app.run(debug=True, port=9999)
    else:
        print("Flask Server Running")
        serve(app, host='localhost', port=9999)
