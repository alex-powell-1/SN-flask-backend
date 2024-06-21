from setup.creds import SERVER, DATABASE, USERNAME, PASSWORD, cp_api_key
import pyodbc
from pyodbc import ProgrammingError, Error
import requests
import json
from setup import creds
import time


class QueryEngine:
    def __init__(self):
        self.__SERVER = SERVER
        self.__DATABASE = DATABASE
        self.__USERNAME = USERNAME
        self.__PASSWORD = PASSWORD

    def query_db(self, query, commit=False):
        """Runs Query Against SQL Database. Use Commit Kwarg for updating database"""
        connection = pyodbc.connect(
            f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.__SERVER};PORT=1433;DATABASE={self.__DATABASE};"
            f"UID={self.__USERNAME};PWD={self.__PASSWORD};TrustServerCertificate=yes;timeout=3"
        )
        connection.setdecoding(pyodbc.SQL_CHAR, encoding="latin1")
        connection.setencoding("latin1")

        cursor = connection.cursor()
        if commit:
            try:
                cursor.execute(query)
                connection.commit()
            except ProgrammingError as e:
                sql_data = {"code": f"{e.args[0]}", "message": f"{e.args[1]}"}
            except Error as e:
                if e.args[0] == "40001":
                    print("Deadlock Detected. Retrying Query")
                    time.sleep(1)
                    cursor.execute(query)
                    connection.commit()
                else:
                    sql_data = {"code": f"{e.args[0]}", "message": f"{e.args[1]}"}
            else:
                sql_data = {"code": 200, "message": "Query Successful"}
        else:
            try:
                sql_data = cursor.execute(query).fetchall()
            except ProgrammingError as e:
                sql_data = {"code": f"{e.args[0]}", "message": f"{e.args[1]}"}

        cursor.close()
        connection.close()
        return sql_data if sql_data else None

    def lookup_customer_by_email(self, email_address):
        query = f"""
        SELECT TOP 1 CUST_NO
        FROM AR_CUST
        WHERE EMAIL_ADRS_1 = '{email_address}' or EMAIL_ADRS_2 = '{email_address}'
        """
        response = self.query_db(query)
        if response is not None:
            return response[0][0]

    def lookup_customer_by_phone(self, phone_number):
        query = f"""
        SELECT TOP 1 CUST_NO
        FROM AR_CUST
        WHERE PHONE_1 = '{phone_number}' or MBL_PHONE_1 = '{phone_number}'
        """
        response = self.query_db(query)
        if response is not None:
            return response[0][0]

    def is_customer(self, email_address, phone_number):
        """Checks to see if an email or phone number belongs to a current customer"""
        return (
            self.lookup_customer_by_email(email_address) is not None
            or self.lookup_customer_by_phone(phone_number) is not None
        )


def add_new_customer(
    first_name,
    last_name,
    phone_number,
    email_address,
    street_address,
    city,
    state,
    zip_code,
):
    db = QueryEngine()
    if not db.is_customer(email_address=email_address, phone_number=phone_number):
        url = f"{creds.cp_api_server}/CUSTOMER/"
        headers = {
            "Authorization": f"Basic {creds.cp_api_user}",
            "APIKey": cp_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "Workgroup": "1",
            "AR_CUST": {
                "FST_NAM": first_name,
                "LST_NAM": last_name,
                "STR_ID": "1",
                "EMAIL_ADRS_1": email_address,
                "PHONE_1": phone_number,
                "ADRS_1": street_address,
                "CITY": city,
                "STATE": state,
                "ZIP_COD": zip_code,
            },
        }

        response = requests.post(url, headers=headers, verify=False, json=payload)
        data = response.json()
        pretty = response.content
        pretty = json.loads(pretty)
        pretty = json.dumps(pretty, indent=4)
        print(pretty)
    else:
        print("Already a Customer")


def get_document_id(ticket_number):
    query = f"""
    SELECT DOC_ID
    FROM PS_TKT_HIST
    WHERE TKT_NO = '{ticket_number}'
    """
    db = QueryEngine()
    response = db.query_db(query)
    if response is not None:
        return response[0][0]


def add_ticket_notes(ticket_number, note_id, note):
    document_id = get_document_id(ticket_number)
    document_id = "103301725573"
    url = f"{creds.cp_api_server}/Document/{document_id}/Note"

    headers = {
        "Authorization": f"Basic {creds.cp_api_user}",
        "APIKey": cp_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "PS_DOC_NOTE": {
            "NOTE": r"{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0\\fnil\\fcharset0 Arial;}}\n\\viewkind4\\uc1\\pard\\lang1033\\fs16 Adding a note to an existing customer!\\par\n\\par\\par\n}"
        }
    }
    response = requests.post(url, headers=headers, verify=False, json=payload)
    data = response.json()
    pretty = response.content
    pretty = json.loads(pretty)
    pretty = json.dumps(pretty, indent=4)
    print(pretty)
