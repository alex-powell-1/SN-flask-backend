# Flask Application Documentation

## Overview
This Flask application provides several API endpoints for different functionalities including handling incoming orders, sending information to RabbitMQ for asynchronous processing, handling incoming SMS/MMS messages, and more.

## API Endpoints

### 1. `/design` (POST)
This endpoint is used to get information about the company service. It sends the received JSON data to a RabbitMQ queue for asynchronous processing.

### 2. `/stock_notify` (POST)
This endpoint is used to get contact and product information from a user who wants notification of when a product comes back into stock.

### 3. `/newsletter` (POST)
This endpoint is used for website pop-up. It offers the user a coupon and adds their information to a CSV file.

### 4. `/sms` (POST)
This endpoint is a webhook route for incoming SMS/MMS messages to be used with a client messenger application. It saves all incoming SMS/MMS messages to a shared drive CSV file.

### 5. `/bc` (POST)
This endpoint is a webhook route for incoming orders. It sends the order ID to a RabbitMQ queue for asynchronous processing.

### 6. `/token` (POST)
This endpoint is used to get a token for a session. The password is passed as a query parameter.

### 7. `/commercialAvailability` (POST)
This endpoint is used to get commercial availability data. A token is passed as a query parameter for authorization.

### 8. `/availability` (POST)
This endpoint is used to get retail availability data.

## Running the Application
The application can be run in development mode by setting the `dev` variable to `True`. In this mode, the application is served by Flask's built-in server. If `dev` is `False`, the application is served by the Waitress WSGI server.

## Recent Improvements

1. **Input Validation**: The application now uses JSON Schema to validate the incoming data in the routes. This helps to ensure that the data is in the expected format and can help to prevent issues such as injection attacks.

2. **Rate Limiting**: The application now uses Flask-Limiter to limit the number of requests that can be made to the endpoints per minute. This can help to protect against brute-force attacks or denial-of-service attacks.

3. **Data Sanitization**: The application now uses the `bleach` library to sanitize the input data. This can help to prevent security threats like Cross-Site Scripting (XSS) or Command Injection attacks.

4. **Error Handling**: The application now has error handling functions in place to handle `ValidationError` and `Exception`. This can prevent any sensitive information leakage through error messages.

## Testing
The application has a `test_mode` variable. When `True`, it disables SMS text and automatic printing in the office.

Please note that this is a high-level overview of the application. For a detailed understanding, you should refer to the code and comments in the `main.py` file.