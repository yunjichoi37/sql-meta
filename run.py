# run.py
import os
import struct
import warnings
import pyodbc
import requests
import glob
from pathlib import Path
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from metadata_loader import get_relevant_tables, load_table_metadata, load_relationships

warnings.filterwarnings("ignore")
load_dotenv()

DATAVERSE_SERVER = os.getenv("DATAVERSE_SERVER")
DATAVERSE_DATABASE = os.getenv("DATAVERSE_DATABASE")
DATAVERSE_CLIENT_ID = os.getenv("DATAVERSE_CLIENT_ID")
DATAVERSE_CLIENT_SECRET = os.getenv("DATAVERSE_CLIENT_SECRET")
DATAVERSE_TENANT_ID = os.getenv("DATAVERSE_TENANT_ID") # 토큰 발급용
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def get_dataverse_token() -> str:
    """OData 때 썼던 확실한 방식으로 Azure AD 토큰을 직접 발급받음"""
    server_domain = DATAVERSE_SERVER.split(",")[0] # 포트 번호 분리
    token_url = f"https://login.microsoftonline.com/{DATAVERSE_TENANT_ID}/oauth2/v2.0/token"
    token_data = {
        "client_id": DATAVERSE_CLIENT_ID,
        "client_secret": DATAVERSE_CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": f"https://{server_domain}/.default"
    }

    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    return response.json().get("access_token")


@tool
def execute_sql_query(sql_query: str) -> str:
    """
    Dataverse TDS 엔드포인트에 T-SQL 쿼리를 직접 실행하고 결과를 반환합니다.
    """
    try:
        # 1. 토큰 발급
        token = get_dataverse_token()
        
        # 2. ODBC가 알아먹을 수 있게 토큰을 Byte Struct로 변환 (마법의 주문)
        token_bytes = token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
        SQL_COPT_SS_ACCESS_TOKEN = 1256  # ODBC 토큰 주입 옵션 번호

        # 3. ID/PWD 없이 토큰만 들고 들어감
        conn_str = (
            f"Driver={{ODBC Driver 17 for SQL Server}};"
            f"Server={DATAVERSE_SERVER};"
            f"Database={DATAVERSE_DATABASE};"
            f"Encrypt=yes;"
        )
        
        # 연결 시 attrs_before 파라미터로 토큰 강제 주입
        conn = pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}, autocommit=True)
        cursor = conn.cursor()
        
        cursor.execute(sql_query)
        
        if cursor.description is None:
            return "실행 완료 (반환된 데이터 없음)"
            
        columns = [column[0] for column in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
            
        conn.close()
        return str(results)
    except Exception as e:
        return f"SQL 실행 에러: {e}\n이 에러를 바탕으로 쿼리를 수정해서 다시 시도하세요."


AGENT_PREFIX = """You are a SQL expert connected to a Dataverse database via TDS endpoint.

                Rules:
                1. Always use standard T-SQL syntax.
                2. Use the 'execute_sql_query' tool to fetch data.
                3. Always verify column names with the provided metadata below before writing a query.
                4. Only use the available tables and columns. Never assume or invent names.
                5. Do NOT use markdown code blocks inside the tool input, pass the raw string.
                6. Report query results as facts. Do NOT add disclaimers or caveats.
                """

def get_extracted_tables():
    table_files = glob.glob("filtered_metadata/tables/*.json")
    return [Path(f).stem for f in table_files]

ALL_TABLES = get_extracted_tables()

def run_sql_agent():
    required_vars = ["DATAVERSE_SERVER", "DATAVERSE_DATABASE", "DATAVERSE_CLIENT_ID", "DATAVERSE_CLIENT_SECRET", "DATAVERSE_TENANT_ID", "GROQ_API_KEY"]
    
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"환경변수 누락: {missing}")

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        # model_name="llama-3.3-70b-versatile",
        model="openai/gpt-oss-120b",
        temperature=0
    )

    tools = [execute_sql_query]

    while True:
        user_input = input("질문: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("채팅 종료")
            break
        if not user_input:
            continue

        relevant_tables = get_relevant_tables(user_input, llm, ALL_TABLES)
        print(f"\n[선택된 테이블] {relevant_tables}")

        if not relevant_tables:
            print("관련 테이블을 찾지 못했습니다.")
            continue

        table_meta = load_table_metadata(relevant_tables)
        rel_meta = load_relationships(relevant_tables)

        dynamic_prefix = AGENT_PREFIX
        if table_meta:
            dynamic_prefix += f"\n\n{table_meta}"
        if rel_meta:
            dynamic_prefix += f"\n\n{rel_meta}"

        prompt = ChatPromptTemplate.from_messages([
            ("system", dynamic_prefix),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True, 
            handle_parsing_errors=True
        )

        try:
            print("\n[Agent 추론 시작]")
            response = agent_executor.invoke({"input": user_input})
            print(f"\n답변:\n{response['output']}\n")
            print("-" * 60)
        except Exception as e:
            print(f"\n시스템 에러: {e}\n")

if __name__ == "__main__":
    run_sql_agent()