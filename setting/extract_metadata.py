import os
import json
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

ALL_TABLES = [
    "account", "contact", "lead", "opportunity",
    "incident", "systemuser", "task", "quote",
    "salesorder", "invoice"
]

# JSON 파일을 저장할 디렉토리 생성
os.makedirs("metadata/tables", exist_ok=True)

# 다국어 레이블(한글 표시 이름 등)을 안전하게 추출하기 위한 헬퍼 함수
def get_label(data_dict, key):
    if data_dict and data_dict.get(key) and data_dict[key].get("UserLocalizedLabel"):
        return data_dict[key]["UserLocalizedLabel"].get("Label", "")
    return ""

for table in ALL_TABLES:
    print(f"[{table}] 메타데이터 추출 중...")
    
    # 1. 엔터티 기본 정보 조회 (테이블 설명, 표시 이름 등)
    entity_url = f"{RESOURCE_URL}/api/data/v9.2/EntityDefinitions(LogicalName='{table}')?$select=DisplayName,Description"
    entity_resp = requests.get(entity_url, headers=headers).json()
    
    table_display_name = get_label(entity_resp, "DisplayName") or table
    table_description = get_label(entity_resp, "Description") or f"{table_display_name} 테이블"

    # 2. 엔터티 컬럼(Attribute) 목록 조회
    # IsValidForRead eq true 조건을 주어 실제로 읽을 수 있는 컬럼만 필터링합니다.
    attr_url = f"{RESOURCE_URL}/api/data/v9.2/EntityDefinitions(LogicalName='{table}')/Attributes?$select=LogicalName,DisplayName,AttributeType&$filter=IsValidForRead eq true"
    attr_resp = requests.get(attr_url, headers=headers).json()
    
    attributes = attr_resp.get("value", [])
    columns_meta = {}
    
    for attr in attributes:
        col_logical = attr.get("LogicalName")
        col_display = get_label(attr, "DisplayName")
        col_type = attr.get("AttributeType", "")
        
        # 컬럼 설명 텍스트 구성 (예: "거래처 이름 (String)")
        desc_str = col_display if col_display else col_logical
        if col_type:
            desc_str += f" ({col_type})"
            
        columns_meta[col_logical] = desc_str

    # 3. 요청하신 JSON 구조 조립
    meta_json = {
        "summary": table_display_name,
        "description": table_description,
        "columns": columns_meta,
        "common_filters": "",
        "notes": ""
    }

    # 4. JSON 파일로 저장
    file_path = f"metadata/tables/{table}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(meta_json, f, ensure_ascii=False, indent=2)
        
print("모든 메타데이터 추출 및 저장이 완료되었습니다.")