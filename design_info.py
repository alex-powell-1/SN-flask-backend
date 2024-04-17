import json
import os
import sys
import time
from datetime import datetime

import pandas
import pika
import requests
from docxtpl import DocxTemplate

from setup import creds, email_engine, sms_engine
from setup import log_engine

test_mode = False


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='design_info')

    def callback(ch, method, properties, body):
        json_body = json.loads(body.decode())
        first_name = json_body['first_name']
        last_name = json_body['last_name']
        email = json_body['email']
        phone = sms_engine.format_phone(json_body['phone'], mode='counterpoint')
        timeline = json_body['timeline']
        interested_in = json_body['interested_in']
        street = json_body['street']
        city = json_body['city']
        state = json_body['state'] if json_body['state'] != 'State' else ""
        zip_code = json_body['zip_code']
        comments = json_body['comments']
        # Concat the address
        address = f"{street}, {city}, {state}, {zip_code}"

        # Concatenate user interests (for text and spreadsheet use)
        interests = ""
        if interested_in is not None:
            for x in interested_in:
                interests += x
                if len(interested_in) > 1:
                    interests += ", "
            if len(interested_in) > 1:
                # remove last trailing characters (", ")
                interests = interests[:-2]

        # Log Details
        # establish time for consistent logging
        now = datetime.now()

        design_lead_data = [[str(now)[:-7], first_name, last_name, email, phone, interested_in, timeline,
                             street, city, state, zip_code, comments]]
        df = pandas.DataFrame(design_lead_data,
                              columns=["date", "first_name", "last_name", "email", "phone", "interested_in", "timeline",
                                       "street", "city", "state", "zip_code", "comments"])
        log_engine.write_log(df, creds.lead_log)

        # Send text notification To sales team manager
        if not test_mode:
            try:
                sms_engine.design_text(first_name, last_name, phone, interests, timeline, address, comments)
            except Exception as err:
                error_type = "sms"
                error_data = [[str(now)[:-7], error_type, err]]
                df = pandas.DataFrame(error_data, columns=["date", "error_type", "message"])
                log_engine.write_log(df, f"{creds.lead_error_log}/error_{now.strftime("%m_%d_%y_%H_%M_%S")}.csv")
                print(err)

        # Send email to client
        try:
            email_engine.design_email(first_name, email)
        except Exception as err:
            error_type = "email"
            error_data = [[str(now)[:-7], error_type, err]]
            df = pandas.DataFrame(error_data, columns=["date", "error_type", "message"])
            log_engine.write_log(df, f"{creds.lead_error_log}/error_{now.strftime("%m_%d_%y_%H_%M_%S")}.csv")
            print(err)

        # Print lead details for in-store use

        # Create the Word document
        try:
            doc = DocxTemplate("./templates/lead_template.docx")

            context = {
                # Product Details
                'date': now.strftime("%m/%d/%Y %H:%M %p"),
                'name': first_name + " " + last_name,
                'email': email,
                'phone': phone,
                'interested_in': interested_in,
                'timeline': timeline,
                'address': address,
                'comments': comments
            }

            doc.render(context)
            ticket_name = f"lead_{now.strftime("%m_%d_%y_%H_%M_%S")}.docx"
            # Save the rendered file for printing
            doc.save(f"./{ticket_name}")
            # Print the file to default printer
            if not test_mode:
                os.startfile(ticket_name, "print")
            # Delay while print job executes
            time.sleep(4)
            # Delete the unneeded Word document
            # os.close causing crash of printing
            # os.close(1)
            os.remove(ticket_name)
        except Exception as err:
            error_type = "lead_ticket"
            error_data = [[str(now)[:-7], error_type, err]]
            df = pandas.DataFrame(error_data, columns=["date", "error_type", "message"])
            log_engine.write_log(df, f"{creds.lead_error_log}/error_{now.strftime("%m_%d_%y_%H_%M_%S")}.csv")

        # Upload to sheety API for spreadsheet use

        sheety_post_body = {
            "sheet1": {
                "date": str(now),
                "first": first_name,
                "last": last_name,
                "phone": phone,
                "email": email,
                "interested": interests,
                "timeline": timeline,
                "street": street,
                "city": city,
                "state": state,
                "zip": zip_code,
                "comments": comments
            }
        }
        try:
            # Try block stands to decouple our implementation from API changes that might impact app.
            requests.post(url=creds.sheety_design_url, headers=creds.sheety_header, json=sheety_post_body)
        except Exception as err:
            error_type = "spreadsheet"
            error_data = [[str(now)[:-7], error_type, err]]
            df = pandas.DataFrame(error_data, columns=["date", "error_type", "message"])
            log_engine.write_log(df, f"{creds.lead_error_log}/error_{now.strftime("%m_%d_%y_%H_%M_%S")}.csv")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue='design_info', on_message_callback=callback)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
