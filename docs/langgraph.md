# LangGraph 그래프 구조

아래 Mermaid는 손으로 그린 것이 아니라, 실제 컴파일된 LangGraph 인스턴스에서
`graph.get_graph().draw_mermaid()`로 직접 추출한 것이다(코드와 다이어그램이 어긋날 수
없다). 추출 방법:

```bash
python -c "
from src.graph.build import build_compliance_graph
from src.graph.runner import _MILITARY_SUBGRAPH, _PLAIN_SUBGRAPH
print(build_compliance_graph().get_graph().draw_mermaid())
print(_MILITARY_SUBGRAPH.get_graph().draw_mermaid())
print(_PLAIN_SUBGRAPH.get_graph().draw_mermaid())
"
```

## 1. 레퍼런스/테스트 그래프 — `src/graph/build.py`

`tests/test_graph_end_to_end.py`용 단일-진입 그래프. 계획 건물 1건당 시설 1건만
판정하는 구조라 `search_zone_node`가 반경 내 시설을 우선순위(군사시설 → 국가유산 →
일조권)로 하나만 골라 그 이후 경로를 조건부 분기한다.

```mermaid
graph TD;
	__start__([<p>__start__</p>]):::first
	search_zone(search_zone)
	he_compute(he_compute)
	authority_verify(authority_verify)
	plain_compute(plain_compute)
	rag_check(rag_check)
	llm_summarize(llm_summarize)
	__end__([<p>__end__</p>]):::last
	__start__ --> search_zone;
	authority_verify --> rag_check;
	he_compute --> authority_verify;
	plain_compute --> rag_check;
	rag_check --> llm_summarize;
	search_zone -. &nbsp;military&nbsp; .-> he_compute;
	search_zone -. &nbsp;plain&nbsp; .-> plain_compute;
	llm_summarize --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

## 2. 실제 서비스 경로 — `src/graph/runner.py`

Streamlit 앱(`app.py`)이 실제로 쓰는 경로. `search_zone_node`를 거치지 않고, 두 서브
그래프(`_MILITARY_SUBGRAPH`/`_PLAIN_SUBGRAPH`)를 `run_full_compliance_check()`가
직접 여러 번 호출한다 — 한 건물이 여러 카테고리·여러 규정 테마를 동시에 위반할 수
있어야 하기 때문이다(아래 "오케스트레이션" 절 참고).

### 2-1. `_MILITARY_SUBGRAPH` (HE 경로)

```mermaid
graph TD;
	__start__([<p>__start__</p>]):::first
	he_compute(he_compute)
	authority_verify(authority_verify)
	rag_check(rag_check)
	llm_summarize(llm_summarize)
	__end__([<p>__end__</p>]):::last
	__start__ --> he_compute;
	authority_verify --> rag_check;
	he_compute --> authority_verify;
	rag_check --> llm_summarize;
	llm_summarize --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

### 2-2. `_PLAIN_SUBGRAPH` (평문 경로 — 일조권/국가유산)

```mermaid
graph TD;
	__start__([<p>__start__</p>]):::first
	plain_compute(plain_compute)
	rag_check(rag_check)
	llm_summarize(llm_summarize)
	__end__([<p>__end__</p>]):::last
	__start__ --> plain_compute;
	plain_compute --> rag_check;
	rag_check --> llm_summarize;
	llm_summarize --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

## 3. 통합 뷰 — 실제로 도는 전체 흐름을 한 장으로

위 1·2번은 각각 "레퍼런스 그래프 1장" / "서브그래프 내부 노드 2장"으로 쪼개져 있어서,
그것만 보면 "그럼 한 건물이 일조권+국가유산+군사시설을 동시에 위반하는 건 실제로
어떻게 처리되는가"가 한눈에 안 들어온다는 지적이 있었다. 아래는 `src/graph/runner.py::run_full_compliance_check`가
실제로 실행하는 오케스트레이션(몇 번 반복하는가)과 서브그래프 내부 노드 시퀀스를
**하나의 다이어그램**으로 합친 것이다 — 발표에서는 1·2번 대신 이 다이어그램 하나만
보여줘도 된다.

```mermaid
flowchart TD
    IN["입력: 위치(X,Y) · 계획높이 · 이격거리"]

    IN --> S1["일조권 사선제한<br/>(항상 1건)"]
    IN --> S2{"반경 내 국가유산?<br/>ADJACENCY_RADIUS_M"}
    IN --> S3{"반경 내 군사시설?<br/>zone_radius_m(zone_subtype)<br/>군사기지법 제5조 근거"}

    S2 -- "있는 시설마다 반복" --> S2A["국가유산 N건"]
    S3 -- "있는 시설 × regulation_theme마다 반복<br/>(예: 서울공항 protect_zone 제9조 / flight_safety 제10조)" --> S3A["군사시설 M건 × 테마"]

    subgraph PLAIN["_PLAIN_SUBGRAPH — 평문 경로 (일조권·국가유산 공용)"]
        direction LR
        P1(plain_compute) --> P2(rag_check) --> P3(llm_summarize)
    end

    subgraph MIL["_MILITARY_SUBGRAPH — HE 경로 (군사시설 전용)"]
        direction LR
        M1["he_compute<br/>(CKKS 암호문−평문 뺄셈)"] --> M2["authority_verify<br/>(HSM 자리, 부호만 복호화)"] --> M3(rag_check) --> M4(llm_summarize)
    end

    S1 --> PLAIN
    S2A --> PLAIN
    S3A --> MIL

    PLAIN --> OUT["List[CategoryResult]<br/>(exceeds_limit, margin|None, final_message …)"]
    MIL --> OUT

    OUT --> APP["app.py 렌더링<br/>(배지 + 지도 격자 + 채팅)"]
```

- `search_zone_node`는 이 경로에 아예 등장하지 않는다 — "시설 1건만 골라서 분기"하는
  레퍼런스 그래프(1번)와 달리, `runner.py`는 카테고리별로 **후보 시설을 전부 순회하며
  서브그래프를 여러 번 직접 `invoke()`한다**. 그래서 한 건물이 세 카테고리를 동시에
  위반해도 각각 독립된 `CategoryResult`로 리스트에 쌓인다.
- 군사시설은 시설 1건이라도 규정 테마(현재 서울공항은 `protect_zone`/`flight_safety`
  2개)마다 `_MILITARY_SUBGRAPH`를 독립적으로 한 번씩 실행한다 — 같은 시설이라도
  테마별로 위반/적합이 갈릴 수 있기 때문이다.
- HE 경로만 `authority_verify`(HSM 부호 검증)를 거치고, 평문 경로(일조권/국가유산)는
  `plain_compute` 결과를 바로 `rag_check`로 넘긴다 — CLAUDE.md 절대 원칙 1대로 diff
  암호문은 서비스 내부 어디서도 복호화하지 않는다.
