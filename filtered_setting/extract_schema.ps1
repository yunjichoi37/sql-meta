# ===== .env 로드 =====
Get-Content ".env" | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+)=(.+)$") {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}

$tenantId     = $env:DATAVERSE_TENANT_ID
$clientId     = $env:DATAVERSE_CLIENT_ID
$clientSecret = $env:DATAVERSE_CLIENT_SECRET
$orgUrl       = $env:DATAVERSE_ORG_URL

# ===== Step 1: 토큰 발급 =====
$body = @{
    grant_type    = "client_credentials"
    client_id     = $clientId
    client_secret = $clientSecret
    scope         = "$orgUrl/.default"
}
$token = (Invoke-RestMethod "https://login.microsoftonline.com/$tenantId/oauth2/v2.0/token" -Method Post -Body $body).access_token
$headers = @{ "Authorization" = "Bearer $token"; "Accept" = "application/json" }
Write-Host "[SUCCESS] 토큰 발급 완료"

# ===== Step 2: 테이블 목록 =====
$tableNames = @(
    "new_q1", "new_part", "new_call", "new_q112",
    "new_safeinspection", "appointment", "contact",
    "new_q3", "new_q4", "new_ordersales", "new_po",
    "new_serial", "new_seriallist", "new_web"
)

New-Item -ItemType Directory -Force -Path "./filtered_metadata/tables" | Out-Null

# ===== name 힌트를 붙일 타입 목록 =====
# - Picklist / State : 선택 목록 -> 숫자 코드로 저장
# - Lookup / Customer / Owner : 다른 테이블 참조 -> GUID로 저장
# - Boolean : 예/아니오 -> 0/1로 저장
$nameHintTypes = @("Picklist", "State", "Lookup", "Customer", "Owner", "Boolean")

# ===== relationships 수집용 =====
$allRelationships = [System.Collections.Generic.List[object]]::new()

foreach ($tableName in $tableNames) {
    Write-Host ""
    Write-Host "[PROCESS] 처리 중: $tableName"

    # ── 테이블 DisplayName / Description ──
    try {
        $entityMeta  = Invoke-RestMethod "$orgUrl/api/data/v9.2/EntityDefinitions(LogicalName='$tableName')?`$select=LogicalName,DisplayName,Description" -Headers $headers
        $displayName = $entityMeta.DisplayName.UserLocalizedLabel.Label
        $description = $entityMeta.Description.UserLocalizedLabel.Label
    } catch {
        $displayName = $tableName
        $description = ""
    }

    # ── 뷰에서 실제 사용된 컬럼명 추출 ──
    try {
        $views = Invoke-RestMethod "$orgUrl/api/data/v9.2/savedqueries?`$filter=returnedtypecode eq '$tableName'&`$select=name,fetchxml" -Headers $headers
        $usedColumnNames = @()
        foreach ($view in $views.value) {
            try {
                $xml = [xml]$view.fetchxml
                $cols = $xml.fetch.entity.attribute.name
                if ($cols) { $usedColumnNames += $cols }
            } catch {}
        }
        $usedColumnNames = $usedColumnNames | Sort-Object -Unique
        Write-Host "  [INFO] 뷰 수: $($views.value.Count) / 사용 컬럼: $($usedColumnNames.Count)개"
    } catch {
        Write-Host "  [WARN] 뷰 조회 실패: $tableName"
        $usedColumnNames = @()
    }

    # ── 사용된 컬럼의 메타데이터만 조회 ──
    $columns = @{}
    foreach ($colName in $usedColumnNames) {
        try {
            $attrMeta = Invoke-RestMethod "$orgUrl/api/data/v9.2/EntityDefinitions(LogicalName='$tableName')/Attributes(LogicalName='$colName')?`$select=LogicalName,DisplayName,AttributeType,Description" -Headers $headers
            $dn   = $attrMeta.DisplayName.UserLocalizedLabel.Label
            $desc = $attrMeta.Description.UserLocalizedLabel.Label
            $type = $attrMeta.AttributeType

            # 1. Description 처리 (값이 있을 때만 파이프 기호와 함께 조립)
            $descPart = if ($desc) {
                $cleanDesc = $desc.Replace("`r`n", " ").Replace("`n", " ")
                " | Desc: $cleanDesc"
            } else {
                ""
            }

            # 2. name 힌트 (가상 컬럼)
            $nameSuffix = if ($nameHintTypes -contains $type) {
                " | VirtualColumn: ${colName}name (For Korean text display)"
            } else {
                ""
            }

            # 3. 최종 문자열 조립
            $combined = "Label: $dn | Type: $type$descPart$nameSuffix"

            $columns[$colName] = $combined
        } catch {
            $columns[$colName] = "Label: Unknown | Type: Unknown"
        }
    }

    # ── 관계 (앱 테이블 간 연결만) ──
    try {
        $manyToOne = Invoke-RestMethod "$orgUrl/api/data/v9.2/EntityDefinitions(LogicalName='$tableName')/ManyToOneRelationships?`$select=ReferencedEntity,ReferencingEntity,ReferencedAttribute,ReferencingAttribute,SchemaName" -Headers $headers
        $filteredRels = $manyToOne.value | Where-Object { $tableNames -contains $_.ReferencedEntity }
    } catch {
        $filteredRels = @()
    }

    foreach ($rel in $filteredRels) {
        $allRelationships.Add([PSCustomObject]@{
            from_table = $rel.ReferencingEntity
            from_col   = $rel.ReferencingAttribute
            to_table   = $rel.ReferencedEntity
            to_col     = $rel.ReferencedAttribute
            "note"     = "Dataverse N:1 관계 - $($rel.SchemaName) (LEFT JOIN 권장)"
        })
    }

    # ── table.json 저장 ──
    $tableSchema = @{
        summary        = $displayName
        description    = $description
        columns        = $columns
        common_filters = ""
        notes          = ""
    }

    $outputPath = "./filtered_metadata/tables/$tableName.json"
    $tableSchema | ConvertTo-Json -Depth 10 | Out-File $outputPath -Encoding UTF8
    Write-Host "  [SUCCESS] 저장: $outputPath"
}

# ===== relationships.json 저장 =====
$allRelationships | ConvertTo-Json -Depth 5 | Out-File "./filtered_metadata/relationships.json" -Encoding UTF8
Write-Host ""
Write-Host "[SUCCESS] relationships.json 저장 완료 (총 $($allRelationships.Count)개)"
Write-Host "[DONE] 전체 완료! ./filtered_metadata/ 폴더 확인해주세요"