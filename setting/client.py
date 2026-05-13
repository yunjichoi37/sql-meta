import os
import requests
import msal
from dotenv import load_dotenv

class DataverseClient:
    def __init__(self):
        # 환경 변수 로드
        load_dotenv()

        self.client_id = os.getenv("DATAVERSE_CLIENT_ID")
        self.client_secret = os.getenv("DATAVERSE_CLIENT_SECRET")
        self.tenant_id = os.getenv("DATAVERSE_TENANT_ID")
        
        server_env = os.getenv("DATAVERSE_SERVER")
        if not server_env:
            raise ValueError("DATAVERSE_SERVER 환경 변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            
        self.server = server_env.split(",")[0]
        self.resource_url = f"https://{self.server}"

        # 인스턴스 생성 시 자동으로 토큰을 발급받아 헤더를 구성합니다.
        self.headers = self._generate_headers()

    def _generate_headers(self):
        """MSAL을 사용하여 Access Token을 발급받고 API 요청용 헤더를 반환합니다."""
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret
        )
        
        result = app.acquire_token_for_client(scopes=[f"{self.resource_url}/.default"])
        
        if "access_token" not in result:
            error_msg = result.get('error_description', '알 수 없는 오류 발생')
            raise Exception(f"Dataverse 토큰 발급 실패: {error_msg}")
            
        token = result["access_token"]
        
        return {
            "Authorization": f"Bearer {token}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json"
        }

    def get(self, endpoint):
        """
        Dataverse Web API에 GET 요청을 보내고 JSON 결과를 반환합니다.
        
        Args:
            endpoint (str): API 엔드포인트 경로 (예: '/api/data/v9.2/solutions')
            
        Returns:
            dict: API 응답 JSON 데이터
        """
        url = f"{self.resource_url}{endpoint}"
        response = requests.get(url, headers=self.headers)
        
        # HTTP 에러(4xx, 5xx) 발생 시 예외를 발생시켜 디버깅을 용이하게 합니다.
        response.raise_for_status() 
        
        return response.json()