# check_tables.py
import os
import requests
import msal
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("DATAVERSE_CLIENT_ID")
CLIENT_SECRET = os.getenv("DATAVERSE_CLIENT_SECRET")
TENANT_ID     = os.getenv("DATAVERSE_TENANT_ID")
SERVER        = os.getenv("DATAVERSE_SERVER").split(",")[0]
RESOURCE_URL  = f"https://{SERVER}"

app = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET
)
result = app.acquire_token_for_client(scopes=[f"{RESOURCE_URL}/.default"])
token = result["access_token"]

headers = {
    "Authorization": f"Bearer {token}",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json"
}

# 사용 가능한 엔티티 목록
url = f"{RESOURCE_URL}/api/data/v9.2/EntityDefinitions?$select=LogicalName,DisplayName"
resp = requests.get(url, headers=headers)

entities = resp.json().get("value", [])

# 결과를 txt 파일로 저장
with open("entities_list.txt", "w", encoding="utf-8") as f:
    for e in entities:
        logical_name = e.get("LogicalName", "")
        display = e.get("DisplayName", {}).get("UserLocalizedLabel", {})
        label = display.get("Label", "") if display else ""
        
        # 파일에 쓰기 (정렬 포함)
        f.write(f"{logical_name:<40} {label}\n")

print("저장이 완료되었습니다: entities_list.txt")