# 시스템 아키텍처

## 컴포넌트 다이어그램

```mermaid
flowchart TB
    subgraph Client["사용자 (민간 건축사업자)"]
        Browser[브라우저]
    end

    subgraph App["app.py — Streamlit UI"]
        Sidebar[입력 폼: X·Y·계획높이·이격거리]
        StatTiles["stat tile: 판정항목/위반/적합/반경 내 시설"]
        MapView["지도(pydeck): 계획 건물 마커 + 격자 위험도<br/>+ 검색 반경 원 + 2.5D 건물 배경(VWorld)"]
        StatusPanel["판정 현황 패널(카테고리·규정 테마별 위반/적합 배지)"]
        Chat["LLM 질의응답 채팅"]
    end

    subgraph Compliance["src/compliance — 판정 로직·데이터"]
        Config["config.py<br/>HERITAGE_SITES / MILITARY_ZONES<br/>ZONE_RADIUS_BY_SUBTYPE(군사기지법 제5조)"]
        Search["search.py<br/>find_nearby_restricted_zones()"]
        Rules["rules.py<br/>evaluate_height_compliance()"]
    end

    subgraph Graph["src/graph — LangGraph 판정 파이프라인"]
        Runner["runner.py<br/>run_full_compliance_check()"]
        MilSub["_MILITARY_SUBGRAPH<br/>he_compute→authority_verify→rag_check→llm_summarize"]
        PlainSub["_PLAIN_SUBGRAPH<br/>plain_compute→rag_check→llm_summarize"]
        Tracing["tracing.py — Langfuse span (redact)"]
    end

    subgraph HE["src/he — CKKS (TenSEAL)"]
        Encryption["encryption.py<br/>compute_diff_ciphertext()<br/>(공개 컨텍스트, 비밀키 없음)"]
    end

    subgraph DataStores["데이터 저장소 (역할별 4개 분리)"]
        StructDB[("src/db<br/>구조화 기준값 DB<br/>(facility_id, regulation_theme) PK")]
        CipherCache[("src/db/ciphertext_cache.db<br/>암호문 캐시(opaque bytes만)")]
        RagDB[("src/rag — ChromaDB<br/>법령 조문 청크(근거 인용 전용)")]
        LangfuseStore[("Langfuse<br/>redact된 span만 기록")]
    end

    subgraph Authority["관리기관 역할 (오프라인/Mock)"]
        GenScript["scripts/generate_mock_ciphertexts.py<br/>(facility_id, regulation_theme)별 Z값 암호화"]
        SecretCtx[("scripts/keys/<br/>비밀키 컨텍스트 — 서비스 코드는 import 안 함")]
        Verify["scripts/mock_authority_verify.py<br/>verify_diff() — 부호(초과 여부)만 반환"]
    end

    subgraph Agent["src/agent — AI Agent"]
        Tools["tools.py<br/>tool_check_height_compliance<br/>tool_search_nearby_restricted_zones<br/>tool_get_violation_citations"]
        Router["router.py<br/>handle_agent_query()<br/>실제 tool-calling(CLOVA Studio) → 단발 LLM → 규칙 폴백"]
    end

    subgraph External["외부 API"]
        LLMApi["CLOVA Studio (HyperCLOVA X) API"]
        VWorldApi["VWorld WMTS 타일 + 건물통합정보(WFS)"]
    end

    Browser --> Sidebar
    Sidebar --> Runner
    StatTiles -.-> Search
    MapView -.-> Search
    MapView -.-> VWorldApi
    Runner --> MilSub
    Runner --> PlainSub
    Runner --> Config
    MilSub --> Encryption
    Encryption --> HEPublicCtx["src/he/public_context.bin(공개 컨텍스트)"]
    MilSub --> Verify
    Verify --> SecretCtx
    GenScript --> CipherCache
    GenScript --> SecretCtx
    Config --> CipherCache
    MilSub -.tracing.-> Tracing
    PlainSub -.tracing.-> Tracing
    Tracing --> LangfuseStore
    MilSub --> StructDB
    PlainSub --> StructDB
    MilSub --> RagDB
    PlainSub --> RagDB
    Runner --> StatusPanel
    StatusPanel --> Browser
    Chat --> Router
    Router --> Tools
    Tools --> Runner
    Tools --> RagDB
    Router --> LLMApi
    Search --> Config
```

## 계층별 책임 요약

| 계층 | 책임 | 하지 않는 것 |
|---|---|---|
| `app.py` | 입력 폼, 결과 렌더링, 지도(마커+격자+반경 원+2.5D 배경) | HE 연산, 판정 로직 직접 구현 |
| `src/compliance` | 시설 데이터(실 성남시 좌표) + 반경 검색 + 3개 판정 공식 | 암호문 복호화 |
| `src/graph` | LangGraph 오케스트레이션, 노드별 트레이싱 | UI 렌더링 |
| `src/he` | CKKS 암호문-평문 뺄셈(공개 컨텍스트만) | 복호화(비밀키 없음) |
| `src/db` | facility_id/regulation_theme 기반 정확 대조용 저장소 2종(구조화 DB, 암호문 캐시) | 벡터 유사도 검색 |
| `src/rag` | 법령 조문 근거 인용(벡터 검색) | 판정 자체 |
| `src/agent` | function-calling 기반 채팅, 실제 판정 결과만 요약 | 판정 재계산(그래프 재실행) |
| `scripts/` (관리기관 역할) | 비밀키 보유, Z값 암호화, 부호만 반환 | 서비스 코드에서 import됨 |

## 신뢰 경계(Trust boundary)

- **서비스(app.py, src/) 프로세스는 비밀키를 어디에도 갖지 않는다.** 비밀키는 `scripts/keys/`에만 있고, 이 파일들을 로드하는 코드는 `scripts/generate_mock_ciphertexts.py`·`scripts/mock_authority_verify.py` 두 개뿐이며 둘 다 관리기관 역할을 흉내내는 오프라인 스크립트다.
- 서비스가 실제로 수행하는 유일한 암호 연산은 `compute_diff_ciphertext()`(암호문-평문 뺄셈)이고, 그 결과(diff 암호문)는 절대 서비스 내부에서 복호화되지 않는다.
