# check_webapi.py
import os
import requests
import msal
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("DATAVERSE_CLIENT_ID")
CLIENT_SECRET = os.getenv("DATAVERSE_CLIENT_SECRET")
TENANT_ID     = os.getenv("DATAVERSE_TENANT_ID")
SERVER        = os.getenv("DATAVERSE_SERVER").split(",")[0]  # 포트 제거

RESOURCE_URL = f"https://{SERVER}"

# 토큰 발급
app = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET
)
result = app.acquire_token_for_client(scopes=[f"{RESOURCE_URL}/.default"])
token = result["access_token"]

# Web API 호출
headers = {
    "Authorization": f"Bearer {token}",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json"
}

url = f"{RESOURCE_URL}/api/data/v9.2/accounts?$select=name&$top=3"

resp = requests.get(url, headers=headers)
print(f"상태코드: {resp.status_code}")
print(resp.json())