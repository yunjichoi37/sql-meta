# run.py
import os
import warnings
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq

from metadata_loader import get_relevant_tables, load_table_metadata, load_relationships
from dataverse_tool import query_dataverse

warnings.filterwarnings("ignore")
load_dotenv()

DATAVERSE_SERVER = os.getenv("DATAVERSE_SERVER")
DATAVERSE_CLIENT_ID = os.getenv("DATAVERSE_CLIENT_ID")
DATAVERSE_CLIENT_SECRET = os.getenv("DATAVERSE_CLIENT_SECRET")
DATAVERSE_TENANT_ID = os.getenv("DATAVERSE_TENANT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# SQL 대신 OData를 작성하도록 프롬프트 전면 수정
AGENT_PREFIX = """You are a Dataverse OData expert connected to a real production environment.

                Rules:
                1. DO NOT write SQL. You must write OData queries for Dataverse Web API.
                2. Use the provided 'query_dataverse' tool to fetch data.
                3. Always verify column names with the metadata below before writing a query.
                4. Dataverse Web API usually requires plural Entity Set Names for endpoints (e.g., 'account' -> 'accounts', 'opportunity' -> 'opportunities').
                5. Pass ONLY the relative OData query string to the tool (e.g., 'accounts?$select=name,address1_city&$filter=address1_city eq 'Seoul'&$top=10').
                6. Report query results as facts. Do NOT add disclaimers or caveats.
                
                Output Format:
                Format the final query results as a clean list or CSV style based on user request.
                """

ALL_TABLES = [
    "account",      # 거래처
    "contact",      # 연락처
    "lead",         # 잠재 고객
    "opportunity",  # 영업 기회
    "incident",     # 서비스 케이스
    "systemuser",   # 내부 직원
    "task",         # 활동/작업
    "quote",        # 견적
    "salesorder",   # 주문
    "invoice"       # 송장
]

def run_odata_agent():
    required_vars = ["DATAVERSE_SERVER", "DATAVERSE_CLIENT_ID", "DATAVERSE_CLIENT_SECRET", "DATAVERSE_TENANT_ID", "GROQ_API_KEY"]

    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"환경변수 누락: {missing}")

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )

    tools = [query_dataverse]

    while True:
        user_input = input("질문: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("채팅 종료")
            break
        if not user_input:
            continue

        # 2단계: summary 기반 테이블 선택 (메타데이터 파일명과 매칭을 위해 원본 리스트 사용)
        relevant_tables = get_relevant_tables(user_input, llm, ALL_TABLES)
        print(f"\n[선택된 테이블] {relevant_tables}")

        if not relevant_tables:
            print("관련 테이블을 찾지 못했습니다.")
            continue

        # 3단계: 세부 메타 + 관계 로드
        table_meta = load_table_metadata(relevant_tables)
        print(f"\n{table_meta}")
        
        rel_meta = load_relationships(relevant_tables)
        if rel_meta:
            print(f"\n{rel_meta}")

        # 4단계: prefix에 메타 주입
        dynamic_prefix = AGENT_PREFIX
        if table_meta:
            dynamic_prefix += f"\n\n{table_meta}"
        if rel_meta:
            dynamic_prefix += f"\n\n{rel_meta}"

        # 5단계: Agent 프롬프트 및 Executor 설정
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
            print(f"\n에러: {e}\n")

if __name__ == "__main__":
    run_odata_agent()