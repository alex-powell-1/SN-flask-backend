from setup.creds import *
import pyodbc


class QueryEngine:
    def __init__(self):
        self.__SERVER = SERVER
        self.__DATABASE = DATABASE
        self.__USERNAME = USERNAME
        self.__PASSWORD = PASSWORD

    def query_db(self, query, commit=False):
        """Runs Query Against SQL Database. Use Commit Kwarg for updating database"""
        connection = pyodbc.connect(
            f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.__SERVER};PORT=1433;DATABASE={self.__DATABASE};'
            f'UID={self.__USERNAME};PWD={self.__PASSWORD};TrustServerCertificate=yes;timeout=3')
        cursor = connection.cursor()
        if commit:
            sql_data = cursor.execute(query)
            connection.commit()
        else:
            sql_data = cursor.execute(query).fetchall()
        cursor.close()
        connection.close()
        if sql_data:
            return sql_data
        else:
            return

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
        return (self.lookup_customer_by_email(email_address) is not None or
                self.lookup_customer_by_phone(phone_number) is not None)

    def add_new_customer(self, customer_number, first_name, last_name, phone_number,
                         email_address, street_address, city, state, zip_code):
        query = """
        INSERT INTO AR_CUST (CUST_NO, NAM, NAM_UPR, FST_NAM, FST_NAM_UPR, LST_NAM, LST_NAM_UPR,
        CUST_TYP, ADRS_1, CITY, STATE, ZIP_COD, PHONE_1, EMAIL_ADRS_1, PROMPT_NAM_ADRS, 
        SLS_REP, CATEG_COD, STR_ID, TAX_COD, ALLOW_AR_CHRG, ALLOW_TKTS, NO_CR_LIM, 
        """
        pass


db = QueryEngine()
