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

def get_tables_from_solution(solution_unique_name):
    print(f"[{solution_unique_name}] 솔루션에서 테이블 목록을 조회합니다...")

    # 1. 솔루션 ID 조회
    sol_url = f"{RESOURCE_URL}/api/data/v9.2/solutions?$select=solutionid&$filter=uniquename eq '{solution_unique_name}'"
    sol_resp = requests.get(sol_url, headers=headers).json()
    
    if not sol_resp.get("value"):
        print("해당 이름의 솔루션을 찾을 수 없습니다.")
        return []
        
    solution_id = sol_resp["value"][0]["solutionid"]

    # 2. 해당 솔루션에 포함된 컴포넌트 중 '테이블(엔터티)' 객체 ID 조회 (componenttype eq 1)
    comp_url = f"{RESOURCE_URL}/api/data/v9.2/solutioncomponents?$select=objectid&$filter=_solutionid_value eq '{solution_id}' and componenttype eq 1"
    comp_resp = requests.get(comp_url, headers=headers).json()
    
    entity_ids = [comp["objectid"] for comp in comp_resp.get("value", [])]
    
    if not entity_ids:
        print("솔루션 내에 테이블이 없습니다.")
        return []

    # 3. 전체 엔터티 메타데이터를 가져와서 ID와 LogicalName 매핑
    # (API 호출을 줄이기 위해 전체를 한 번에 가져와서 파이썬 내에서 필터링하는 것이 빠릅니다)
    meta_url = f"{RESOURCE_URL}/api/data/v9.2/EntityDefinitions?$select=MetadataId,LogicalName"
    meta_resp = requests.get(meta_url, headers=headers).json()
    
    all_entities = meta_resp.get("value", [])
    
    # 솔루션에 포함된 objectid와 메타데이터의 MetadataId를 대조하여 LogicalName 추출
    solution_tables = []
    for entity in all_entities:
        if entity["MetadataId"] in entity_ids:
            solution_tables.append(entity["LogicalName"])
            
    return solution_tables

# 'Default' 솔루션(Common Data Services Default Solution)에 있는 테이블 목록 가져오기
# 다른 솔루션을 원하시면 Power Apps 화면에서 솔루션의 "고유 이름(Name)"을 확인해서 넣으시면 됩니다.
ALL_TABLES = get_tables_from_solution("Cr2b787")

print(f"추출된 테이블 개수: {len(ALL_TABLES)}개")
print(f"{ALL_TABLES}\n")

# ---------------------------------------------------------
# 이후에는 이전에 작성했던 메타데이터 추출(columns)이나 
# 관계 추출(relationships) 반복문 코드를 그대로 이어서 붙여넣으시면 됩니다.
# for table in ALL_TABLES:
#     ...
# ---------------------------------------------------------