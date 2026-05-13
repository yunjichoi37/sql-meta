def get_solution_components(client, solution_unique_name):
    """
    특정 솔루션에 포함된 테이블 목록과 컬럼 ID 목록을 함께 추출합니다.
    """
    print(f"[{solution_unique_name}] 솔루션 구성 요소를 조회합니다...")

    # 1. 솔루션 ID 조회
    sol_endpoint = f"/api/data/v9.2/solutions?$select=solutionid&$filter=uniquename eq '{solution_unique_name}'"
    sol_resp = client.get(sol_endpoint)
    
    if not sol_resp.get("value"):
        print("해당 이름의 솔루션을 찾을 수 없습니다.")
        return [], []
        
    solution_id = sol_resp["value"][0]["solutionid"]

    # 2. 테이블(Entity) 객체 ID 조회 (componenttype eq 1)
    entity_comp_endpoint = f"/api/data/v9.2/solutioncomponents?$select=objectid&$filter=_solutionid_value eq '{solution_id}' and componenttype eq 1"
    entity_resp = client.get(entity_comp_endpoint)
    entity_ids = [comp["objectid"] for comp in entity_resp.get("value", [])]

    # 3. 컬럼(Attribute) 객체 ID 조회 (componenttype eq 2)
    attr_comp_endpoint = f"/api/data/v9.2/solutioncomponents?$select=objectid&$filter=_solutionid_value eq '{solution_id}' and componenttype eq 2"
    attr_resp = client.get(attr_comp_endpoint)
    column_ids = [comp["objectid"] for comp in attr_resp.get("value", [])]

    # 4. 엔터티 메타데이터 매핑 (테이블 LogicalName 추출)
    meta_endpoint = "/api/data/v9.2/EntityDefinitions?$select=MetadataId,LogicalName"
    meta_resp = client.get(meta_endpoint)
    
    solution_tables = []
    for entity in meta_resp.get("value", []):
        if entity["MetadataId"] in entity_ids:
            solution_tables.append(entity["LogicalName"])
            
    return solution_tables, column_ids