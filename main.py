import json
import time
import urllib.parse
from datetime import datetime

import bleach
import flask
import pandas
import pika
import requests
from flask import request, jsonify, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from jinja2 import Template
from jsonschema import validate, ValidationError
from twilio.twiml.messaging_response import MessagingResponse
from waitress import serve

from setup import creds, email_engine, sms_engine, authorization
from setup import query_engine
from setup import log_engine

app = flask.Flask(__name__)

limiter = Limiter(get_remote_address, app=app)

CORS(app)

# When False, app is served by Waitress
dev = False


# Error handling functions
@app.errorhandler(ValidationError)
def handle_validation_error(e):
    # Return a JSON response with a message indicating that the input data is invalid
    return jsonify({"error": "Invalid input data", "message": str(e)}), 400


@app.errorhandler(Exception)
def handle_exception(e):
    # Return a JSON response with a generic error message
    print(str(e), file=creds.flask_error_log)
    return jsonify({"error": "An error occurred", "message": str(e)}), 500


@app.route("/design", methods=["POST"])
@limiter.limit("20/minute")  # 10 requests per minute
def get_service_information():
    """Route for information request about company service. Sends JSON to RabbitMQ for asynchronous processing."""
    data = request.json
    # # Validate the input data
    try:
        validate(instance=data, schema=creds.design_schema)
    except ValidationError as e:
        abort(400, description=e.message)
    else:
        payload = json.dumps(data)
        connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))

        channel = connection.channel()

        channel.queue_declare(queue="design_info", durable=True)

        channel.basic_publish(
            exchange="",
            routing_key="design_info",
            body=payload,
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
        )
        connection.close()

        return "Your information has been received. Please check your email for more information from our team."


@app.route("/stock_notify", methods=["POST"])
@limiter.limit("20/minute")  # 10 requests per minute
def stock_notification():
    """Get contact and product information from user who wants notification of when
    a product comes back into stock."""
    data = request.json
    # Sanitize the input data
    sanitized_data = {k: bleach.clean(v) for k, v in data.items()}

    # Validate the input data
    try:
        validate(instance=sanitized_data, schema=creds.stock_notification_schema)
    except ValidationError as e:
        abort(400, description=e.message)
    else:
        email = sanitized_data.get("email")
        item_no = sanitized_data.get("sku")
        try:
            df = pandas.read_csv(creds.stock_notification_log)
        except FileNotFoundError:
            pass
        else:
            entries = df.to_dict("records")
            for x in entries:
                if x["email"] == email and str(x["item_no"]) == item_no:
                    return (
                        "This email address is already on file for this item. We will send you an email "
                        "when it comes back in stock. Please contact our office at "
                        "<a href='tel:8288740679'>(828) 874-0679</a> if you need an alternative "
                        "item. Thank you!"
                    ), 400

        stock_notification_data = [[str(datetime.now())[:-7], email, item_no]]
        df = pandas.DataFrame(
            stock_notification_data, columns=["date", "email", str("item_no")]
        )
        log_engine.write_log(df, creds.stock_notification_log)
        return "Your submission was received."


@app.route("/newsletter", methods=["POST"])
@limiter.limit("20 per minute")  # 20 requests per minute
def newsletter_signup():
    """Route for website pop-up. Offers user a coupon and adds their information to a csv."""
    data = request.json
    print(data)

    # Sanitize the input data
    sanitized_data = {k: bleach.clean(v) for k, v in data.items()}
    print(sanitized_data)
    # Validate the input data
    try:
        validate(instance=sanitized_data, schema=creds.newsletter_schema)
    except ValidationError as e:
        abort(400, description=e.message)
    else:
        email = data.get("email")
        try:
            df = pandas.read_csv(creds.newsletter_log)
        except FileNotFoundError:
            print("Coupon File Not Found")
        else:
            entries = df.to_dict("records")
            for x in entries:
                if x["email"] == email:
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
            "company_reviews": creds.company_reviews,
        }

        email_content = jinja_template.render(email_data)

        email_engine.send_html_email(
            from_name=creds.company_name,
            from_address=creds.gmail_user,
            recipients_list=recipient,
            subject=f"Welcome to {creds.company_name}! Coupon Inside!",
            content=email_content,
            mode="related",
            logo=True,
            attachment=False,
        )

        newsletter_data = [[str(datetime.now())[:-7], email]]
        df = pandas.DataFrame(newsletter_data, columns=["date", "email"])
        log_engine.write_log(df, creds.newsletter_log)
        return "OK", 200


@app.route("/sms", methods=["POST"])
@limiter.limit("40/minute")  # 10 requests per minute
def incoming_sms():
    """Webhook route for incoming SMS/MMS messages to be used with client messenger application.
    Saves all incoming SMS/MMS messages to share drive csv file."""
    raw_data = request.get_data()
    print(raw_data)
    # Decode
    string_code = raw_data.decode("utf-8")
    # Parse to dictionary
    msg = urllib.parse.parse_qs(string_code)

    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    from_phone = msg["From"][0]
    to_phone = msg["To"][0]
    if "Body" in msg:
        body = msg["Body"][0]
    else:
        body = ""

    # Unsubscribe user from SMS marketing
    if body.lower() in [
        "stop",
        "unsubscribe",
        "stop please",
        "please stop",
        "cancel",
        "opt out",
        "remove me",
    ]:
        sms_engine.unsubscribe_from_sms(from_phone)
        # Return Response to Twilio
        resp = MessagingResponse()
        return str(resp)

    else:
        # Get MEDIA URL for MMS Messages
        if int(msg["NumMedia"][0]) > 0:
            media_url = ""

            for i in range(int(msg["NumMedia"][0])):
                media_key_index = f"MediaUrl{i}"
                url = msg[media_key_index][0]
                if i < (int(msg["NumMedia"][0]) - 1):
                    # Add separator per front-end request.
                    media_url += url + ";;;"
                else:
                    media_url += url
        else:
            media_url = "No Media"

        # Get Customer Name and Category from SQL
        full_name, category = sms_engine.lookup_customer_data(
            sms_engine.format_phone(from_phone, mode="counterpoint")
        )

        log_data = [
            [date, to_phone, from_phone, body, full_name, category.title(), media_url]
        ]

        # Write dataframe to CSV file
        df = pandas.DataFrame(
            log_data,
            columns=[
                "date",
                "to_phone",
                "from_phone",
                "body",
                "name",
                "category",
                "media",
            ],
        )
        log_engine.write_log(df, creds.incoming_sms_log)

        # Return Response to Twilio
        resp = MessagingResponse()
        return str(resp)


@app.route("/bc", methods=["POST"])
@limiter.limit("20/minute")  # 10 requests per minute
def bc_orders():
    """Webhook route for incoming orders. Sends to RabbitMQ queue for asynchronous processing"""
    response_data = request.get_json()
    print(response_data)
    order_id = response_data["data"]["id"]

    # Add order to SQL Database. Datestamp and status are added by default.
    query = f"INSERT INTO SN_ORDERS (ORDER_ID) VALUES ({order_id})"
    db = query_engine.QueryEngine()
    insert_res = db.query_db(query, commit=True)
    if insert_res.status_code != 200:
        print(f"Error inserting order {order_id} into SQL Database")

    # Send order to RabbitMQ for asynchronous processing
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="bc_orders", durable=True)

    channel.basic_publish(
        exchange="",
        routing_key="bc_orders",
        body=str(order_id),
        properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
    )
    connection.close()

    return jsonify({"success": True}), 200


@app.route("/token", methods=["POST"])
@limiter.limit("10/minute")  # 10 requests per minute
def get_token():
    password = request.args.get("password")

    if password.lower() == creds.commercial_availability_pw:
        session = authorization.Session(password)
        authorization.SESSIONS.append(session)
        return jsonify({"token": session.token, "expires": session.expires}), 200

    return jsonify({"error": "Invalid username or password"}), 401


@app.route("/commercialAvailability", methods=["POST"])
@limiter.limit("10/minute")  # 10 requests per minute
def get_commercial_availability():
    token = request.args.get("token")

    session = next((s for s in authorization.SESSIONS if s.token == token), None)

    if not session or session.expires < time.time():
        authorization.SESSIONS = [s for s in authorization.SESSIONS if s.token != token]
        return jsonify({"error": "Invalid token"}), 401

    response = requests.get(creds.commercial_availability_url)
    if response.status_code == 200:
        return jsonify({"data": response.text}), 200
    else:
        return jsonify({"error": "Error fetching data"}), 500


@app.route("/availability", methods=["POST"])
@limiter.limit("10/minute")  # 10 requests per minute
def get_availability():
    response = requests.get(creds.retail_availability_url)
    if response.status_code == 200:
        return jsonify({"data": response.text}), 200
    else:
        return jsonify({"error": "Error fetching data"}), 500


@app.route("/health", methods=["GET"])
@limiter.limit("10/minute")  # 10 requests per minute
def health_check():
    return jsonify({"status": "Server is running"}), 200


if __name__ == "__main__":
    if dev:
        app.run(debug=True, port=creds.flask_port)
    else:
        print("Flask Server Running")
        serve(app, host="localhost", port=creds.flask_port)
