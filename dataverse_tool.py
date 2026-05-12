# dataverse_tool.py
import os
import requests
from langchain.tools import tool

def get_dataverse_token() -> str:
    tenant_id = os.getenv("DATAVERSE_TENANT_ID")
    client_id = os.getenv("DATAVERSE_CLIENT_ID")
    client_secret = os.getenv("DATAVERSE_CLIENT_SECRET")
    server = os.getenv("DATAVERSE_SERVER") # 예: orgname.crm.dynamics.com

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": f"https://{server}/.default"
    }

    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    return response.json().get("access_token")

@tool
def query_dataverse(odata_query: str) -> str:
    """
    Dataverse Web API에 OData 쿼리를 실행하고 JSON 결과를 반환합니다.
    입력값은 반드시 엔드포인트에 붙일 상대 경로(예: accounts?$select=name&$top=5)여야 합니다.
    """
    server = os.getenv("DATAVERSE_SERVER")
    try:
        token = get_dataverse_token()
    except Exception as e:
        return f"토큰 발급 실패: {e}"

    headers = {
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json"
    }

    base_url = f"https://{server}/api/data/v9.2/"
    
    # 쿼리 문자열 앞의 슬래시 제거
    if odata_query.startswith("/"):
        odata_query = odata_query[1:]
        
    full_url = base_url + odata_query

    try:
        response = requests.get(full_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # 토큰 절약을 위해 실제 데이터 배열만 반환
        if "value" in data:
            return str(data["value"])
        return str(data)
    except Exception as e:
        return f"OData 쿼리 실행 에러: {e}"