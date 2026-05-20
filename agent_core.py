# agent_core.py
"""
백엔드 핵심 로직:
  - DB 연결 및 SQL 실행 (execute_sql_query tool)
  - CSV 저장
  - LLM / Agent 생성 및 실행
  - 메타데이터 로딩 위임 (metadata_loader)
  - 모듈 레벨 싱글톤으로 LLM 객체 1회 생성 → 성능 유지
"""

import os
import csv
import glob
import struct
import warnings
from datetime import datetime
from pathlib import Path

import pyodbc
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from metadata_loader import get_relevant_tables, load_table_metadata, load_relationships
from filtered_setting.client import DataverseClient

warnings.filterwarnings("ignore")
load_dotenv()

DATAVERSE_SERVER = os.getenv("DATAVERSE_SERVER")
DATAVERSE_DATABASE = os.getenv("DATAVERSE_DATABASE")
DATAVERSE_CLIENT_ID = os.getenv("DATAVERSE_CLIENT_ID")
DATAVERSE_CLIENT_SECRET = os.getenv("DATAVERSE_CLIENT_SECRET")
DATAVERSE_TENANT_ID = os.getenv("DATAVERSE_TENANT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MAX_ROWS_IN_CONTEXT = 100       # 이 이하면 텍스트로 반환
OUTPUT_DIR = "query_outputs"    # CSV 저장 폴더
last_query_results = {"data": None}  # tool과 run_sql_agent가 공유하는 전역 상태

AGENT_PREFIX = """You are a SQL expert connected to a Dataverse database via TDS endpoint.

Rules:
1. Always use standard T-SQL syntax.
2. Use the 'execute_sql_query' tool to fetch data.
3. Always verify column names with the provided metadata below before writing a query.
4. Only use the available tables and columns. Never assume or invent names.
5. Do NOT use markdown code blocks inside the tool input, pass the raw string.
6. Report query results as facts. Do NOT add disclaimers or caveats.
7. If the result shows only a preview, inform the user that the full data will be saved as a CSV file automatically.

Metadata Format:
- col_name(Type) | Label | VirtualColumn | Description
- Type에 * 표시된 컬럼은 VirtualColumn으로 한글 텍스트 조회 가능
- 예: statuscode(Picklist*) | 상태코드 | statuscodename → SELECT statuscodename 사용

Dataverse Common Columns (available in ALL tables):
- statecode(State*) | 활성여부 | statecodename | 0=활성 1=비활성
- statuscode(Picklist*) | 상태코드 | statuscodename
- createdon(DateTime) | 생성일
- modifiedon(DateTime) | 수정일
- ownerid(Owner*) | 담당자 | owneridname
"""


def get_extracted_tables() -> list[str]:
    table_files = glob.glob("filtered_metadata/tables/*.json")
    return [Path(f).stem for f in table_files]

ALL_TABLES: list[str] = get_extracted_tables()


# LLM singleton
_llm: ChatGroq | None = None
def get_llm() -> ChatGroq:
    """LLM 객체를 싱글톤으로 반환한다."""
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
            # model="openai/gpt-oss-120b",
            temperature=0,
        )
    return _llm


@tool
def execute_sql_query(sql_query: str) -> str:
    """
    Dataverse TDS 엔드포인트에 T-SQL 쿼리를 실행하고 결과를 반환한다.
    결과가 100행 이하면 텍스트로 반환하고, 100행 초과면 CSV 파일로 저장 후 경로와 미리보기를 반환한다. 
    (CSV는 답변 완성 후 자동 저장)
    """
    try:
        # 1. Client 및 토큰 발급
        client = DataverseClient()
        token = client.get_access_token()

        # 2. 토큰을 ODBC용 Byte Struct로 변환
        token_bytes = token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
        SQL_COPT_SS_ACCESS_TOKEN = 1256 # ODBC 토큰 주입 옵션 번호

        # 3. 연결
        conn_str = (
            f"Driver={{ODBC Driver 17 for SQL Server}};"
            f"Server={DATAVERSE_SERVER};"
            f"Database={DATAVERSE_DATABASE};"
            f"Encrypt=yes;"
        )

        conn = pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}, autocommit=True) # DB 연결시 토큰 주입
        cursor = conn.cursor() # cursor 객체 생성
        cursor.execute(sql_query) # cursor가 DB에서 쿼리를 실행시킨다. 실행 후 cursor는 결과 집합의 첫 번째 행을 가리키게 된다.

        if cursor.description is None:
            conn.close()
            return "실행 완료 (반환된 데이터 없음)"

        columns = [col[0] for col in cursor.description] # cursor의 metadata인 description에서 컬럼 이름을 추출한다.
        rows = cursor.fetchall() # fetch + all: 남은 데이터를 모두 가져온다.
        results = [dict(zip(columns, row)) for row in rows]
        conn.close()

        # 4. 행 수에 따라 분기
        if len(results) <= MAX_ROWS_IN_CONTEXT:
            # 100행 이하: 텍스트로 전달, 전역 초기화
            last_query_results["data"] = None
            return str(results)
 
        # 100행 초과: 전역에 보관, 미리보기만 LLM에 전달
        last_query_results["data"] = results
        preview = results[:5]
        return (
            f"쿼리 결과: 총 {len(results)}행 (데이터가 많아 상위 5행만 표시)\n"
            f"{preview}"
        )

    except Exception as e:
        return f"SQL 실행 에러: {e}\n이 에러를 바탕으로 쿼리를 수정해서 다시 시도하세요."


def save_csv_if_needed() -> str | None:
    """last_query_results에 데이터가 있으면 CSV로 저장하고 경로 반환"""
    data = last_query_results.get("data")
    if not data:
        return None
 
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"result_{timestamp}.csv")
 
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
 
    last_query_results["data"] = None  # 다음 질문을 위해 초기화
    return csv_path


def build_agent_executor(dynamic_prefix: str) -> AgentExecutor:
    """주어진 시스템 프롬프트로 AgentExecutor를 생성한다."""
    llm   = get_llm()
    tools = [execute_sql_query] # 추후 tool 추가 가능(차트 그리기 등)
 
    prompt = ChatPromptTemplate.from_messages([
        ("system", dynamic_prefix), # 테이블 메타데이터
        ("human", "{input}"), # 질문
        MessagesPlaceholder("agent_scratchpad"), # 쿼리 결과가 동적으로 저장될 곳
    ])
 
    agent = create_tool_calling_agent(llm, tools, prompt) # 어떤 tool을 호출하여 무엇을 할지 판단하는 객체 생성
    return AgentExecutor( # 에이전트의 생각을 행동으로 실행해주는 시스템
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )

import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

def load_metadata_for_query(user_input: str) -> tuple[list[str], str, str]:
    """
    사용자 질문에서 관련 테이블을 찾고 메타데이터를 로드한다.
    Returns: (relevant_tables, table_meta, rel_meta)
    """
    llm = get_llm()
    relevant_tables = get_relevant_tables(user_input, llm, ALL_TABLES)
    table_meta = load_table_metadata(relevant_tables)
    rel_meta = load_relationships(relevant_tables)

    print(f"[TOKEN] table_meta: {count_tokens(table_meta)}")
    print(f"[TOKEN] rel_meta:   {count_tokens(rel_meta)}")
    return relevant_tables, table_meta, rel_meta


def run_query(user_input: str, callbacks: list | None = None,) -> dict:
    """
    사용자 질문 하나를 처리하고 결과 dict를 반환한다.
 
    반환 형식:
    {
        "answer":             str,
        "csv_path":           str | None,
        "relevant_tables":    list[str],
        "table_meta":         str,
        "rel_meta":           str,
        "intermediate_steps": list,
        "error":              str | None,   # 에러 시에만 존재
    }
    """
    relevant_tables, table_meta, rel_meta = load_metadata_for_query(user_input)
 
    dynamic_prefix = AGENT_PREFIX
    if table_meta:
        dynamic_prefix += f"\n\n{table_meta}"
    if rel_meta:
        dynamic_prefix += f"\n\n{rel_meta}"
    print(table_meta)
    print(rel_meta)
 
    agent_executor = build_agent_executor(dynamic_prefix) # agent 생성
 
    invoke_config = {}
    if callbacks: # callback은 agent가 어떤 일을 하고 있는지 실시간으로 보여주는 용도. app.py에서 StreamlitCallbackHandler가 전달된다.
        invoke_config["callbacks"] = callbacks
 
    try:
        response           = agent_executor.invoke({"input": user_input}, invoke_config)
        answer             = response["output"]
        intermediate_steps = response.get("intermediate_steps", [])
        csv_path           = save_csv_if_needed()
 
        return {
            "answer":             answer,
            "csv_path":           csv_path,
            "relevant_tables":    relevant_tables,
            "table_meta":         table_meta,
            "rel_meta":           rel_meta,
            "intermediate_steps": intermediate_steps,
        }
 
    except Exception as e:
        last_query_results["data"] = None   # 에러 시에도 버퍼 초기화
        return {
            "answer":             "",
            "csv_path":           None,
            "relevant_tables":    relevant_tables,
            "table_meta":         table_meta,
            "rel_meta":           rel_meta,
            "intermediate_steps": [],
            "error":              str(e),
        }