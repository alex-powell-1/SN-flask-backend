This flask application handles realtime http requests and incoming data from webhooks to ngrok server for: 
- Marketing lead generation form (with RabbitMQ async queue consumer)
- Requests to join newsletter
- Requests to subscribe to stock notification emails for specific e-commerce items (with Jinja templating email response)
- Twilio webhooks for incoming SMS/MMS messages
- BigCommerce webhooks for realtime printing of invoices in retail store location (with RabbitMQ async queue consumer)
