def get_tables_from_solution(client, solution_unique_name):
    """
    특정 솔루션에 포함된 테이블(Entity)의 LogicalName 목록을 추출합니다.
    
    Args:
        client (DataverseClient): API 통신을 위한 클라이언트 객체
        solution_unique_name (str): Dataverse 솔루션의 고유 이름
        
    Returns:
        list: 테이블의 LogicalName 문자열이 담긴 리스트
    """
    print(f"[{solution_unique_name}] 솔루션에서 테이블 목록을 조회합니다...")

    # 1. 솔루션 ID 조회
    sol_endpoint = f"/api/data/v9.2/solutions?$select=solutionid&$filter=uniquename eq '{solution_unique_name}'"
    sol_resp = client.get(sol_endpoint)
    
    if not sol_resp.get("value"):
        print("해당 이름의 솔루션을 찾을 수 없습니다.")
        return []
        
    solution_id = sol_resp["value"][0]["solutionid"]

    # 2. 해당 솔루션에 포함된 컴포넌트 중 '테이블(엔터티)' 객체 ID 조회 (componenttype eq 1)
    comp_endpoint = f"/api/data/v9.2/solutioncomponents?$select=objectid&$filter=_solutionid_value eq '{solution_id}' and componenttype eq 1"
    comp_resp = client.get(comp_endpoint)
    
    entity_ids = [comp["objectid"] for comp in comp_resp.get("value", [])]
    
    if not entity_ids:
        print("솔루션 내에 테이블이 없습니다.")
        return []

    # 3. 전체 엔터티 메타데이터를 가져와서 ID와 LogicalName 매핑
    meta_endpoint = "/api/data/v9.2/EntityDefinitions?$select=MetadataId,LogicalName"
    meta_resp = client.get(meta_endpoint)
    
    all_entities = meta_resp.get("value", [])
    
    # 솔루션에 포함된 objectid와 메타데이터의 MetadataId를 대조하여 LogicalName 추출
    solution_tables = []
    for entity in all_entities:
        if entity["MetadataId"] in entity_ids:
            solution_tables.append(entity["LogicalName"])
            
    return solution_tables