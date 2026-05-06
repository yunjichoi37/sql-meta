# test_connection.py
import pyodbc, os
from dotenv import load_dotenv
load_dotenv()

conn_str = (
    f"Driver={{ODBC Driver 17 for SQL Server}};"
    f"Server={os.getenv('DATAVERSE_SERVER')};"
    f"Database={os.getenv('DATAVERSE_DATABASE')};"
    f"UID={os.getenv('DATAVERSE_CLIENT_ID')};"
    f"PWD={os.getenv('DATAVERSE_CLIENT_SECRET')};"
    f"Authentication=ActiveDirectoryServicePrincipal;"
)

conn = pyodbc.connect(conn_str)
print("연결 완료")
conn.close()