import json
from pathlib import Path
from langchain_core.messages import HumanMessage

METADATA_DIR = Path("metadata/tables")
RELATIONSHIPS_PATH = Path("metadata/relationships.json")


def get_relevant_tables(user_question: str, llm, all_tables: list) -> list:
    # 2단계: 각 테이블의 summary(한 줄 설명)만 보고 필요한 테이블 선택
    # 메타 파일 없으면 테이블명만으로 fallback
    
    table_summaries = []
    for table in all_tables:
        json_path = METADATA_DIR / f"{table}.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            summary = meta.get("summary", "설명 없음")
        else:
            summary = "(메타데이터 없음)"
        table_summaries.append(f"- {table}: {summary}")

    prompt = f"""아래는 데이터베이스 테이블 목록과 각 테이블의 간단한 설명입니다.
    
            {chr(10).join(table_summaries)}

            사용자 질문: {user_question}

            이 질문에 답하려면 어떤 테이블이 필요한가요?
            테이블 이름만 쉼표로 구분해서 답하세요. 다른 말은 하지 마세요.
            예시: sales_transaction, product, customer"""

    response = llm.invoke([HumanMessage(content=prompt)])
    selected = [t.strip() for t in response.content.split(",")]
    return [t for t in selected if t in all_tables]


def load_table_metadata(relevant_tables: list) -> str:
    # 3단계: 선택된 테이블의 세부 메타(columns, notes 등) 로드
    
    if not relevant_tables:
        return ""

    lines = ["[테이블 메타데이터]"]

    for table in relevant_tables:
        json_path = METADATA_DIR / f"{table}.json"
        if not json_path.exists():
            lines.append(f"\n## {table}\n  (메타데이터 파일 없음)")
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        lines.append(f"\n## {table}")
        lines.append(f"설명: {meta.get('description', meta.get('summary', ''))}")

        if "columns" in meta:
            lines.append("컬럼:")
            for col, desc in meta["columns"].items():
                lines.append(f"  - {col}: {desc}")

        if "common_filters" in meta:
            lines.append(f"기본 필터 조건: {meta['common_filters']}")

        if "notes" in meta:
            lines.append(f"주의사항: {meta['notes']}")

    return "\n".join(lines)


def load_relationships(relevant_tables: list) -> str:
    # 3단계: 선택된 테이블 간 관계(조인) 로드
    
    if not RELATIONSHIPS_PATH.exists() or not relevant_tables:
        return ""

    with open(RELATIONSHIPS_PATH, "r", encoding="utf-8") as f:
        all_rels = json.load(f)

    filtered = [
        r for r in all_rels
        if r.get("from_table") in relevant_tables or r.get("to_table") in relevant_tables
    ]

    if not filtered:
        return ""

    lines = ["[테이블 관계 / 조인 힌트]"]
    for r in filtered:
        note = f" ({r['note']})" if r.get("note") else ""
        lines.append(f"  - {r['from_table']}.{r['from_col']} → {r['to_table']}.{r['to_col']}{note}")

    return "\n".join(lines)