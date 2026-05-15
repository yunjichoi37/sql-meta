import os
import streamlit as st
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler

# 기존 모듈 및 Tool 임포트 (run.py에 있던 함수들을 그대로 가져옵니다)
from run import (
    execute_sql_query, 
    save_csv_if_needed, 
    ALL_TABLES, 
    AGENT_PREFIX, 
    GROQ_API_KEY
)
from metadata_loader import get_relevant_tables, load_table_metadata, load_relationships

st.set_page_config(page_title="Makino Dataverse SQL Agent", layout="wide")
st.title("Makino Dataverse SQL Agent")

# 세션 상태 초기화 (채팅 기록 저장용)
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "안녕하세요! 데이터베이스에 대해 무엇이든 물어보세요."}]

# 이전 채팅 기록 출력 (토글 복원 포함)
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        # 1. 메타데이터 토글 복원
        if msg.get("relevant_tables"):
            with st.expander(f"선택된 테이블 ({', '.join(msg['relevant_tables'])})", expanded=False):
                if msg.get("table_meta"):
                    st.markdown(msg["table_meta"])
                if msg.get("rel_meta"):
                    st.markdown("---")
                    st.markdown(msg["rel_meta"])
        
        # 2. Agent 사고 흐름 토글 복원
        if msg.get("intermediate_steps"):
            with st.expander("Agent 사고 흐름", expanded=False):
                for action, observation in msg["intermediate_steps"]:
                    st.markdown(f"**Tool:** {action.tool}")
                    st.markdown(f"**Input:** {action.tool_input}")
                    st.markdown(f"**Observation:** {observation}")
                    st.markdown("---")

        # 3. 메시지 내용 출력
        st.write(msg["content"])
        
        # 4. 이전 대화에 CSV 결과가 있었다면 렌더링
        if msg.get("csv_path"):
            df = pd.read_csv(msg["csv_path"])
            st.dataframe(df)

# LLM 및 툴 셋업
@st.cache_resource
def get_agent_executor():
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )
    tools = [execute_sql_query]
    return llm, tools

llm, tools = get_agent_executor()

# 사용자 입력 처리
if user_input := st.chat_input("질문을 입력하세요..."):
    # 사용자 메시지 화면에 표시 및 저장
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        # 1. 관련 테이블 검색 및 메타데이터 로드
        with st.spinner("관련 테이블과 메타데이터를 검색 중입니다..."):
            relevant_tables = get_relevant_tables(user_input, llm, ALL_TABLES)
            table_meta = load_table_metadata(relevant_tables)
            rel_meta = load_relationships(relevant_tables)

        # 2. 메타데이터 토글(Expander) UI 생성
        if relevant_tables:
            with st.expander(f"선택된 테이블 ({', '.join(relevant_tables)})", expanded=False):
                if table_meta:
                    st.markdown(table_meta)
                if rel_meta:
                    st.markdown("---")
                    st.markdown(rel_meta)
        else:
            st.info("관련 테이블을 찾지 못했습니다.")

        # 3. Agent 프롬프트 구성
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
        
        # return_intermediate_steps=True 추가: 사고 과정을 반환받기 위함
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True, 
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )

        # 4. Agent 사고 흐름 표시 콜백 설정
        st_callback = StreamlitCallbackHandler(st.container(), expand_new_thoughts=True)

        try:
            # Agent 실행
            response = agent_executor.invoke(
                {"input": user_input},
                {"callbacks": [st_callback]}
            )
            answer = response["output"]
            intermediate_steps = response.get("intermediate_steps", [])
            st.write(answer.replace('\n', '  \n'))

            # 5. CSV 결과가 있다면 화면에 렌더링
            csv_path = save_csv_if_needed()
            if csv_path:
                st.success(f"데이터가 많아 CSV 파일로 저장되었습니다: `{csv_path}`")
                df = pd.read_csv(csv_path)
                st.dataframe(df)
                
            # 상태에 메타데이터 및 사고 과정과 함께 저장
            st.session_state["messages"].append({
                "role": "assistant", 
                "content": answer,
                "csv_path": csv_path,
                "relevant_tables": relevant_tables,
                "table_meta": table_meta,
                "rel_meta": rel_meta,
                "intermediate_steps": intermediate_steps
            })

        except Exception as e:
            st.error(f"시스템 에러 발생: {e}")