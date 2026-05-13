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

# 분석할 대상 테이블 목록
ALL_TABLES = [
    "new_ordersales", "new_po", "new_podetail", "new_serial", "new_web", 
    "new_q1", "new_notice", "new_part", "systemuser", "cr78e_status", 
    "new_q112", "new_safeinspection", "appointment", "new_q3", 
    "new_q1024", "new_weeklyreport"
]

relationships_list = []

print("테이블 간의 관계를 분석 중입니다...")

for table in ALL_TABLES:
    # 해당 테이블이 가지고 있는 외래 키(Lookup) 정보인 N:1 관계 목록을 가져옵니다.
    rel_url = f"{RESOURCE_URL}/api/data/v9.2/EntityDefinitions(LogicalName='{table}')/ManyToOneRelationships?$select=ReferencingEntity,ReferencingAttribute,ReferencedEntity,ReferencedAttribute,SchemaName"
    
    resp = requests.get(rel_url, headers=headers)
    if resp.status_code != 200:
        print(f"[{table}] 조회 실패: {resp.status_code}")
        continue
        
    relationships = resp.json().get("value", [])
    
    for rel in relationships:
        from_table = rel.get("ReferencingEntity")
        to_table = rel.get("ReferencedEntity")
        
        # 우리가 지정한 ALL_TABLES 목록 안에 있는 테이블끼리의 관계만 필터링합니다.
        if to_table in ALL_TABLES:
            from_col = rel.get("ReferencingAttribute")
            to_col = rel.get("ReferencedAttribute")
            schema_name = rel.get("SchemaName")
            
            # Dataverse의 Lookup은 값이 비어있을 수 있으므로 기본적으로 LEFT JOIN을 추천하는 노트를 작성합니다.
            note = f"LEFT JOIN 추천 (Dataverse N:1 관계 - {schema_name})"
            
            rel_info = {
                "from_table": from_table,
                "from_col": from_col,
                "to_table": to_table,
                "to_col": to_col,
                "note": note
            }
            relationships_list.append(rel_info)

# 결과를 metadata 디렉토리에 relationships.json으로 저장합니다.
os.makedirs("metadata", exist_ok=True)
output_file = "metadata/relationships.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(relationships_list, f, ensure_ascii=False, indent=2)

print(f"총 {len(relationships_list)}개의 관계를 찾아서 {output_file}에 저장했습니다!")