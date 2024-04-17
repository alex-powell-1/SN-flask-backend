import os
import sys
from datetime import datetime
from email import utils

import pandas
import pika
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage

from setup import barcode_engine
from setup import creds, product_engine, log_engine
from setup.order_engine import Order, utc_to_local


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='bc_orders')

    def callback(ch, method, properties, body):
        now = datetime.now()
        order_id = body.decode()
        # Create order object
        try:
            order = Order(order_id)
            # Filter out DECLINED payments
            if order.payment_status != 'declined' or order.payment_status != "":
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

        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue='bc_orders', on_message_callback=callback)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
