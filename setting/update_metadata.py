import sys
import os

# 현재 폴더(setting)를 시스템 경로에 추가하여 모듈을 쉽게 찾을 수 있도록 합니다.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from client import DataverseClient
from extractors.solution import get_tables_from_solution
from extractors.metadata import extract_metadata
from extractors.relationships import extract_relationships

def main():
    print("=== Dataverse 메타데이터 추출 파이프라인 시작 ===")
    
    # 1. API 클라이언트 초기화 (자동으로 토큰 발급 완료)
    try:
        client = DataverseClient()
        print("Dataverse API 클라이언트 연결 성공.")
    except Exception as e:
        print(f"클라이언트 연결 실패: {e}")
        return

    # 2. 대상 솔루션 설정 및 테이블 목록 조회
    TARGET_SOLUTION = "Cr2b787"  # 필요에 따라 다른 솔루션 이름으로 변경 가능
    tables = get_tables_from_solution(client, TARGET_SOLUTION)
    
    if not tables:
        print("추출할 테이블이 없어 프로세스를 종료합니다.")
        return
        
    print(f"\n총 {len(tables)}개의 테이블을 대상으로 작업을 진행합니다.")
    print(f"대상 테이블: {tables}\n")

    # 3. 메타데이터(컬럼 정보) 추출 및 저장
    # 챗봇 본체(최상위 폴더)의 metadata/tables 디렉토리에 저장하도록 경로 지정
    metadata_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "metadata", "tables")
    extract_metadata(client, tables, output_dir=metadata_dir)

    # 4. 테이블 간 N:1 관계 정보 추출 및 저장
    # 챗봇 본체의 metadata/relationships.json 으로 저장
    relationships_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "metadata", "relationships.json")
    extract_relationships(client, tables, output_file=relationships_file)
    
    print("\n=== Dataverse 메타데이터 추출 파이프라인 완료 ===")

if __name__ == "__main__":
    main()