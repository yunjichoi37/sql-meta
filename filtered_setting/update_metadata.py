import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from client import DataverseClient
from extractors.solution import get_solution_components
from extractors.metadata import extract_metadata
from extractors.relationships import extract_relationships

def main():
    print("=== Dataverse 메타데이터 추출 파이프라인 시작 ===")
    
    try:
        client = DataverseClient()
        print("Dataverse API 클라이언트 연결 성공.")
    except Exception as e:
        print(f"클라이언트 연결 실패: {e}")
        return

    TARGET_SOLUTION = "Cr2b787"
    
    # 변경점: 테이블 목록과 솔루션에 속한 컬럼 ID 목록을 함께 받아옵니다.
    tables, solution_column_ids = get_solution_components(client, TARGET_SOLUTION)
    
    if not tables:
        print("추출할 테이블이 없어 프로세스를 종료합니다.")
        return
        
    print(f"\n총 {len(tables)}개의 테이블과 {len(solution_column_ids)}개의 명시적 컬럼을 대상으로 작업을 진행합니다.")

    metadata_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "filtered_metadata", "tables")
    
    # 변경점: valid_column_ids 파라미터로 명시적 컬럼 ID 리스트를 넘겨줍니다.
    extract_metadata(client, tables, valid_column_ids=solution_column_ids, output_dir=metadata_dir)

    relationships_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "filtered_metadata", "relationships.json")
    extract_relationships(client, tables, output_file=relationships_file)
    
    print("\n=== Dataverse 메타데이터 추출 파이프라인 완료 ===")

if __name__ == "__main__":
    main()