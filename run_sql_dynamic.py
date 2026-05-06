# run_sql_dynamic.py
import os
import warnings
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

warnings.filterwarnings("ignore")
load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def get_relevant_tables(user_question: str, llm, all_tables: list) -> list:
    """질문을 보고 필요한 테이블만 골라내는 함수"""
    prompt = f"""Given this database tables: {', '.join(all_tables)}
    
                User question: {user_question}

                Which tables are needed to answer this question?
                Reply with ONLY a comma-separated list of table names, nothing else.
                Example: sales_transaction, product, customer"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    selected = [t.strip() for t in response.content.split(',')]
    valid = [t for t in selected if t in all_tables] # 실제 존재하는 테이블만 필터링
    
    return valid

def run_sql_agent():
    # 환경변수 누락 체크
    required_vars = ["MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB", "GROQ_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"환경변수 누락: {missing}")
    
    # 테이블 이름 미리 정의 (일단 하드코딩)
    all_tables = [
        "customer", "sales_transaction", "product", "transaction_product",
        "store", "inventory", "vendor", "customer_email", "customer_phone", "product_supply"
    ]
    
    db_uri = f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}@{MYSQL_HOST}/{MYSQL_DB}"
    engine = create_engine(db_uri) # DB engine(connection pool) 생성
    
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        # model_name="llama-3.3-70b-versatile", # 얘가 정답 맞힘. 근데 토큰이 없음 ㅠㅠ
        # model_name="llama-3.1-8b-instant", # 약간 덜 떨어짐
        model_name="openai/gpt-oss-120b", # 오 좀 더 똑똑한듯? 토큰 아끼자
        temperature=0
    )

    AGENT_PREFIX = """You are a SQL expert connected to a real production database.
            
                    Rules:
                    1. Always call list_tables first before writing any query.
                    2. Only use the available tables. Never assume or invent table/column names.
                    3. Always verify column names with sql_db_schema before writing a query.
                    4. Report query results as facts. Do NOT add disclaimers or caveats.
                    5. The query results ARE the actual data.
                
                    Output Format:
                    1. Format the final query results as a CSV string (comma-separated).
                    2. Do not create Markdown tables or use extra padding spaces.
                    3. Include column headers in the first line of the CSV output."""

    while True:
        user_input = input("질문: ")
        if user_input.lower() in ['exit', 'quit', 'ㄷ턋']:
            print("채팅 종료")
            break
        if not user_input.strip():
            continue

        # 1단계: 필요한 테이블만 선택
        relevant_tables = get_relevant_tables(user_input, llm, all_tables)
        print(f"1. 선택된 테이블: {relevant_tables}")

        # 2단계: 미리 만들어둔 engine을 재사용하여 객체 생성
        db = SQLDatabase(engine=engine, include_tables=relevant_tables)

        # 3단계: Agent 실행
        agent_executor = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="tool-calling",
            verbose=True,
            agent_executor_kwargs={"handle_parsing_errors": True},
            prefix=AGENT_PREFIX
        )

        try:
            print("2. SQL Agent 추론 시작")
            response = agent_executor.invoke({"input": user_input})
            print(f"\n답변: {response['output']}\n")
            print("-" * 60)
        except Exception as e:
            print(f"\n에러: {e}\n")

# 캐시 기능은 일단 고민...
# cache_key = tuple(sorted(relevant_tables))
# if cache_key not in db_cache:
#     db_cache[cache_key] = SQLDatabase(engine, include_tables=relevant_tables)
# db = db_cache[cache_key]

if __name__ == "__main__":
    run_sql_agent()