# check_auth.py
import os
import msal
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("DATAVERSE_CLIENT_ID")
CLIENT_SECRET = os.getenv("DATAVERSE_CLIENT_SECRET")
SERVER        = os.getenv("DATAVERSE_SERVER")  # makinokr.crm21.dynamics.com,5558

# 테넌트 ID 없으면 일단 organizations으로 시도
TENANT_ID = os.getenv("DATAVERSE_TENANT_ID", "organizations")

# Dataverse 리소스 URL (포트 빼고 도메인만)
resource_url = f"https://{SERVER.split(',')[0]}"

app = msal.ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}"
)

result = app.acquire_token_for_client(
    scopes=[f"{resource_url}/.default"]
)

if "access_token" in result:
    print("토큰 발급 성공: Client ID/Secret 유효함")
    print(f"- 토큰 타입: {result.get('token_type')}")
    print(f"- 만료(초): {result.get('expires_in')}")
elif "error" in result:
    print(f"인증 실패: {result.get('error')}")
    print(f"- 상세: {result.get('error_description')}")