# run_sql_dynamic.py
import os
import warnings
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_groq import ChatGroq

from metadata_loader import get_relevant_tables, load_table_metadata, load_relationships

warnings.filterwarnings("ignore")
load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

AGENT_PREFIX = """You are a SQL expert connected to a real production database.

                Rules:
                1. Always call list_tables first before writing any query.
                2. Only use the available tables. Never assume or invent table/column names.
                3. Always verify column names with sql_db_schema before writing a query.
                4. Report query results as facts. Do NOT add disclaimers or caveats.
                5. The query results ARE the actual data.
                6. Use the metadata context below to understand column meanings and join conditions.

                Output Format:
                1. Format the final query results as a CSV string (comma-separated).
                2. Do not create Markdown tables or use extra padding spaces.
                3. Include column headers in the first line of the CSV output.
                """

ALL_TABLES = [
    "customer", "sales_transaction", "product", "transaction_product",
    "store", "inventory", "vendor", "customer_email", "customer_phone", "product_supply"
]


def run_sql_agent():
    required_vars = ["MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB", "GROQ_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"환경변수 누락: {missing}")

    db_uri = f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}@{MYSQL_HOST}/{MYSQL_DB}"
    engine = create_engine(db_uri)

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile", # 얘가 정답 맞힘. 근데 토큰이 없음 ㅠㅠ
        # model_name="llama-3.1-8b-instant", # 약간 덜 떨어짐
        # model_name="openai/gpt-oss-120b", # 오 좀 더 똑똑한듯? 토큰 아끼자
        temperature=0
    )

    while True:
        user_input = input("질문: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("채팅 종료")
            break
        if not user_input:
            continue

        # 2단계: summary 기반 테이블 선택
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

        # 5단계: SQL 연결
        # db = SQLDatabase.from_uri(db_uri, include_tables=relevant_tables)
        db = SQLDatabase(engine=engine, include_tables=relevant_tables)

        # 6단계: Agent 실행
        agent_executor = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="tool-calling",
            verbose=True,
            prefix=dynamic_prefix,
            agent_executor_kwargs={"handle_parsing_errors": True},
        )

        try:
            print("\n[Agent 추론 시작]")
            response = agent_executor.invoke({"input": user_input})
            print(f"\n답변:\n{response['output']}\n")
            print("-" * 60)
        except Exception as e:
            print(f"\n에러: {e}\n")


if __name__ == "__main__":
    run_sql_agent()