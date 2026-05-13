import os
import json

def get_label(data_dict, key):
    """다국어 레이블(한글 표시 이름 등)을 안전하게 추출하기 위한 헬퍼 함수"""
    if data_dict and data_dict.get(key) and data_dict[key].get("UserLocalizedLabel"):
        return data_dict[key]["UserLocalizedLabel"].get("Label", "")
    return ""

def extract_metadata(client, tables, output_dir="../metadata/tables"):
    """
    주어진 테이블 목록의 메타데이터(컬럼 정보 등)를 추출하여 JSON 파일로 저장합니다.
    """
    os.makedirs(output_dir, exist_ok=True)
    print("메타데이터 추출을 시작합니다...")
    
    for table in tables:
        print(f"[{table}] 메타데이터 추출 중...")
        
        # 1. 엔터티 기본 정보 조회
        entity_endpoint = f"/api/data/v9.2/EntityDefinitions(LogicalName='{table}')?$select=DisplayName,Description"
        try:
            entity_resp = client.get(entity_endpoint)
        except Exception as e:
            print(f"[{table}] 기본 정보 조회 실패: {e}")
            continue
        
        table_display_name = get_label(entity_resp, "DisplayName") or table
        table_description = get_label(entity_resp, "Description") or f"{table_display_name} 테이블"

        # 2. 엔터티 컬럼 목록 조회
        attr_endpoint = f"/api/data/v9.2/EntityDefinitions(LogicalName='{table}')/Attributes?$select=LogicalName,DisplayName,AttributeType&$filter=IsValidForRead eq true"
        try:
            attr_resp = client.get(attr_endpoint)
        except Exception as e:
            print(f"[{table}] 컬럼 정보 조회 실패: {e}")
            continue
        
        attributes = attr_resp.get("value", [])
        columns_meta = {}
        
        for attr in attributes:
            col_logical = attr.get("LogicalName")
            col_display = get_label(attr, "DisplayName")
            col_type = attr.get("AttributeType", "")
            
            desc_str = col_display if col_display else col_logical
            if col_type:
                desc_str += f" ({col_type})"
                
            columns_meta[col_logical] = desc_str

        # 3. JSON 구조 조립
        meta_json = {
            "summary": table_display_name,
            "description": table_description,
            "columns": columns_meta,
            "common_filters": "",
            "notes": ""
        }

        # 4. JSON 파일로 저장
        file_path = os.path.join(output_dir, f"{table}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(meta_json, f, ensure_ascii=False, indent=2)
            
    print("모든 메타데이터 추출 및 저장이 완료되었습니다.")