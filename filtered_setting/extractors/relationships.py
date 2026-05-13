import os
import json

def extract_relationships(client, tables, output_file="../filtered_metadata/relationships.json"):
    """
    주어진 테이블 목록 간의 N:1 관계를 추출하여 JSON 파일로 저장합니다.
    """
    print("테이블 간의 관계를 분석 중입니다...")
    relationships_list = []

    for table in tables:
        rel_endpoint = f"/api/data/v9.2/EntityDefinitions(LogicalName='{table}')/ManyToOneRelationships?$select=ReferencingEntity,ReferencingAttribute,ReferencedEntity,ReferencedAttribute,SchemaName"
        
        try:
            resp = client.get(rel_endpoint)
        except Exception as e:
            print(f"[{table}] 관계 조회 실패: {e}")
            continue
            
        relationships = resp.get("value", [])
        
        for rel in relationships:
            from_table = rel.get("ReferencingEntity")
            to_table = rel.get("ReferencedEntity")
            
            # 분석 대상 테이블 간의 관계만 필터링
            if to_table in tables:
                from_col = rel.get("ReferencingAttribute")
                to_col = rel.get("ReferencedAttribute")
                schema_name = rel.get("SchemaName")
                
                note = f"LEFT JOIN 추천 (Dataverse N:1 관계 - {schema_name})"
                
                rel_info = {
                    "from_table": from_table,
                    "from_col": from_col,
                    "to_table": to_table,
                    "to_col": to_col,
                    "note": note
                }
                relationships_list.append(rel_info)

    # 결과를 상위 디렉토리의 metadata 폴더에 저장합니다.
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(relationships_list, f, ensure_ascii=False, indent=2)

    print(f"총 {len(relationships_list)}개의 관계를 찾아서 {output_file}에 저장했습니다.")