# 🔐 ZeCret — 신축 건물 높이 컴플라이언스 사전검토 서비스

> 민간 건축사업자가 신축을 계획할 때, 인접한 국가유산·군사시설 등 공개제한구역의 높이제한 기준 대비 자기 건물이 위반인지 사전 검토하는 서비스입니다. 군사시설(비행안전구역) 높이제한 기준값은 비공개 대상이라, 실제 CKKS 동형암호(TenSEAL)로 암호화된 상태를 유지한 채 초과 여부만 반환합니다 — 서비스는 비밀키를 보유하지 않으며, 복호화는 관리기관 HSM 역할을 대신하는 오프라인 스크립트에서만 일어납니다.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![AWS](https://img.shields.io/badge/Deploy-AWS-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](#license)

---

## 📌 프로젝트 개요

민간 건축사업자가 건물을 신축하려 할 때, 인접한 국가유산 역사문화환경보존지역이나 군사시설 비행안전구역의 높이제한 기준을 사전에 검토해야 합니다. 문제는 군사시설 등 공개제한구역의 정확한 고도제한 수치는 안보상 이유로 공개되지 않는다는 점입니다.

본 프로젝트는 이 요구를 만족시키기 위해, 공개제한구역의 높이제한 기준값(Z)은 비공개 상태로 유지하면서도 "이 계획 건물이 그 기준을 위반하는지"라는 판단 결과만 제공하는 서비스를 구현합니다. 일조권·문화재 기준도 내부적으로는 정밀 수치(margin)를 계산하지만, 화면에는 모든 카테고리 공통으로 위반/적합 이진 결과만 노출합니다.

| 항목 | 내용 |
|---|---|
| 개발 기간 | 2주 |
| UI | Streamlit |
| 배포 | AWS EC2 (GitHub Actions CI/CD) |

---

## 🧩 문제 정의

- 군사시설 등 공개제한구역은 관련 규정에 따라 고도 등 정밀 높이제한 정보 공개가 제한됨
- 민간 건축사업자는 그 시설의 정확한 높이제한 기준을 모른 채로도, 자기 건물이 그 기준을 위반하지 않는다는 것을 사전에 확인해야 함
- → **"안보상 비공개"**와 **"민간의 사전 확인 필요성"**이 충돌하는 구조적 문제
- 해법: 높이제한 기준값(Z)을 복호화하지 않고도 비교 연산 자체를 암호화된 상태로 수행하는 동형암호(CKKS) 기술 적용 — 군사시설 카테고리에 실제 TenSEAL 연산으로 구현 완료

---

## 👤 사용자 흐름

```
① 민간 건축사업자가 화면(관제센터형 대시보드)에서 신축 예정 건물 정보
   (위치 X,Y + 계획 높이 + 인접대지경계선 이격거리)를 입력
        │
② 계획 위치 기준 인접한(반경 내) 국가유산·군사시설 참조 데이터를 자동 조회
        │
③ 3개 카테고리(일조권 사선제한 / 국가유산 경관보호 / 군사시설 고도제한)를 각각 독립 판정
        │
④ 군사시설 기준값은 암호문 상태로만 서비스에 존재하며, 서비스는 암호문-평문 동형 뺄셈까지만 수행한다(실제 TenSEAL CKKS 연산). 최종 복호화(부호 비트만)는 서비스가 아니라 비밀키를 보유한 관리기관 HSM 검증 API 역할을 대신하는 오프라인 스크립트(`scripts/mock_authority_verify.py`)에서 수행하고, 서비스는 그 이진 결과만 전달받아 반환한다.
        │
⑤ 일조권·국가유산도 내부적으로는 margin을 계산하지만, 화면에는 모든 카테고리
   공통으로 위반/적합 이진 결과만 표시 — 지도에는 계획 건물 위치 1개만 마커로 표시
```

**입력 데이터 두 갈래**

- **건축사업자 입력** : 신축 예정 건물의 위치(X,Y)·계획 높이·인접대지경계선 이격거리를 화면에서 직접 입력 (모두 평문, 판정 대상)
- **참조 데이터** : 인접 국가유산/군사시설의 위치·높이제한 기준값 — 현재는 하드코딩된 샘플 좌표/값(`src/compliance/config.py`), 실 데이터 연동은 이후 단계

---

## ⚖️ 판정 카테고리 (3종만 자동 판정 대상)

법정 수치 기준이 없는 항목(예: 조망권)은 오판정 리스크가 있어 이번 범위에서 제외했습니다.

| # | 카테고리 | 근거 | 규칙 | margin(내부 계산) | 화면 노출 |
|---|---|---|---|---|---|
| 1 | 일조권 사선제한 | 건축법 제61조, 시행령 제86조 | 높이 9m 이하 → 1.5m 이상 이격 / 9m 초과 → 높이의 1/2 이상 이격 | 실제 수치 | 이진 결과만 |
| 2 | 국가유산 경관보호 | 문화재보호법, 유산별 개별 고시 | 계획 높이가 유산별 허용 높이를 초과하는지 | 실제 수치 | 이진 결과만 |
| 3 | 군사시설 비행안전구역 고도제한 | 군사기지 및 군사시설 보호법 | 계획 높이가 비공개 높이제한 기준값을 초과하는지 | 항상 `None` | 이진 결과만 |

세 카테고리 모두 동일한 반환 스키마를 쓰는 `evaluate_height_compliance(facility_type, plan_height, reference_value) -> dict`(`src/compliance/rules.py`)로 구현되어 있고, 실제 실행은 LangGraph 파이프라인(`src/graph`)의 `plain_compute_node`(일조권/국가유산)·`he_compute_node`+`authority_verify_node`(군사시설) 노드가 담당합니다. Streamlit UI(`app.py`)는 `src/graph/runner.py`의 `run_full_compliance_check()`가 반환한 카테고리별 결과(`CategoryResult`)를 그대로 받아 렌더링만 하며, margin은 1)일조권·2)국가유산 카테고리에서는 데이터 계층(`computation_result`)에 실제 수치가 채워지지만 카테고리와 무관하게 화면에는 전혀 렌더링하지 않고 `exceeds_limit`(위반/적합)만 표시합니다.

---

## ✅ 체크포인트 대응

| 체크포인트 | 적용 방식 |
|---|---|
| ① 암호화 저장 | 군사시설 높이제한 기준값을 `HeightLimitCiphertext`(실제 TenSEAL CKKS 암호문, `src/he/encryption.py`)로 감싸 둠. 암호화는 관리기관 역할의 오프라인 스크립트(`scripts/generate_mock_ciphertexts.py`)가 미리 수행해 암호문 캐시(`src/db/ciphertext_cache.py`)에 저장하고, 서비스는 조회만 함 — 비밀키는 `scripts/keys/`에만 있고 서비스 코드(`src/`, `app.py`)는 이를 import하지 않음. LangGraph 경로에서는 `he_compute_node`(공개 컨텍스트로 실제 동형 뺄셈)와 `authority_verify_node`(`scripts/mock_authority_verify.py` 호출 — 관리기관 HSM 자리)가 이 분리를 그대로 구현함 |
| ② 범위검색 | 계획 위치 기준 반경(`ADJACENCY_RADIUS_M`) 내 인접 국가유산/군사시설만 판정 대상으로 검색 |
| ③ 시각화 대안 | 관제센터형 대시보드에서 모든 카테고리가 위반/적합 이진 결과만 표시 (정밀 수치 UI 요소 자체를 렌더링하지 않음). 지도에는 계획 건물 위치 1개만 마커로 표시하고, 인접 국가유산/군사시설 위치는 지도에 올리지 않음 |
| ④ 토큰 참조값 | `HE:datasetId:buildingIndex` 형식 유틸(`src/tokens.py`)은 보유하고 있으나, 이번 반전된 흐름(고정 참조 데이터 비교)에는 아직 연결되어 있지 않음 — 다음 단계 검토 대상 |

---

## ⚙️ 핵심 기능

- ⚖️ **3종 높이 컴플라이언스 판정** — 일조권 사선제한 / 국가유산 경관보호 / 군사시설 고도제한
- 🔒 **군사시설 기준값 비공개 처리 (실제 TenSEAL CKKS)** — 서비스는 비밀키를 보유하지 않으며 암호문-평문 동형 뺄셈까지만 수행, 최종 복호화(부호 비트)는 관리기관 HSM 역할을 대신하는 오프라인 스크립트(`scripts/mock_authority_verify.py`)에서 수행 후 이진 결과만 전달
- 🔑 **Mock 관리기관 사전 준비** (`scripts/generate_mock_ciphertexts.py`) — CKKS 키 쌍 생성, 샘플 군사시설 Z값을 공개키로 암호화해 암호문 캐시에 저장. 비밀키는 `scripts/keys/`에만 저장되고 서비스 코드는 이를 절대 import하지 않음
- 🔍 **인접 판정 대상 자동 검색** — 계획 위치 기준 반경 내 국가유산/군사시설만 자동 조회
- 🖥️ **관제센터형 대시보드 UI** — 판정 현황 요약(항목 수·위반·적합), 카테고리별 이진 결과 패널, 계획 건물 위치만 표시하는 지도로 구성. 좌측 제어반은 폼(form) 형태라 4개 값을 입력한 뒤 "🔍 검색" 버튼을 눌러야 판정이 실행되며(입력마다 자동 재계산되지 않음), 지도·판정 현황·LLM 질의응답 3개 패널은 검색 여부와 무관하게 항상 화면에 떠 있음(검색 전에는 기본 위치/안내 문구만 표시)
- 🕸️ **LangGraph 판정 파이프라인** (`src/graph`) — 군사시설은 `he_compute_node`(실제 CKKS 동형 뺄셈) → `authority_verify_node`(`scripts/mock_authority_verify.py` 호출), 그 외 카테고리는 `plain_compute_node` → 공통으로 `rag_check_node`(구조화 DB 정확 대조) → `llm_summarize_node`(판정 결과 설명문 생성) 순으로 실행. Streamlit 대시보드(`app.py`)는 `src/graph/runner.py`를 통해 이 그래프를 카테고리별로 직접 실행한 결과만 받아 렌더링함
- 🗄️ **구조화 기준값 DB** (`src/db`, SQLite) — facility_id 기반 정확 쿼리로 판정 결과를 재검증 (벡터 검색 아님), 군사시설 행은 height_limit_m을 조회 결과에 포함하지 않음
- 📚 **RAG 벡터DB 근거 인용** (`src/rag`, ChromaDB) — 건축법·문화재보호법·군사기지법 조문 청크를 facility_id로 정확 조회해 "왜 이 기준이 적용되는지" 근거 문장을 제공. 판정에는 관여하지 않으며, 개정으로 대체된(`superseded_by`) 구버전 조문은 검색에서 제외
- 🗣️ **LLM 판정 설명** (`llm_summarize_node`) — 이미 확정된 판정 결과(bool)와 RAG 근거만으로 설명문을 생성하고, 재판단·임의 수치 언급은 프롬프트로 금지 (CLAUDE.md 절대 원칙 5). API 키 미설정/호출 실패 시 결정론적 템플릿 문구로 자동 대체되어 파이프라인이 항상 끝까지 실행됨
- 🔭 **Langfuse 노드별 트레이싱** (`src/graph/tracing.py`) — 각 노드 실행을 span으로 기록하되, 계획 높이·정확한 좌표·암호문 등은 절대 남기지 않고 `facility_id`/`regulation_type`/`latency_ms`/`exceeds_limit`만 allowlist 방식으로 기록
- 🤖 **AI Agent 채팅** (`src/agent`) — 화면 하단 "LLM 질의응답" 채팅창에서 판정 결과에 대해 자유 질문 가능. `tool_check_height_compliance`(function calling 대상 tool)를 먼저 호출해 실제 판정 결과를 얻고, `handle_agent_query`가 그 결과 + RAG 근거 조문만 LLM에 넘겨 답변을 생성 — LLM이 판정을 다시 계산하는 경로는 없음(CLAUDE.md 절대 원칙 5). LLM 호출 실패/미설정 시에도 판정 결과와 근거 조문을 나열하는 폴백 답변으로 대체됨

---

## 🛠️ 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 언어 | Python 3.10+ |
| UI | Streamlit |
| 동형암호 | **TenSEAL** (CKKS) — 군사시설 카테고리에 실제 적용 완료. `poly_modulus_degree=8192`, `coeff_mod_bit_sizes=[60,40,60]`, `global_scale=2**40`, galois/relinearization key는 생성하지 않음(뺄셈 1회만 필요해 불필요) — 파라미터 선정 근거는 `scripts/generate_mock_ciphertexts.py` 주석 참고 |
| AI Agent | `src/agent` — `tool_check_height_compliance`(tool) → `handle_agent_query`(결과+RAG 근거를 LLM에 전달해 자연어 답변). 화면의 "LLM 질의응답" 채팅창에서 사용 |
| LLM 호출 | `src/graph/llm_client.py`가 Claude/Gemini 공용 호출부 — `ANTHROPIC_API_KEY`가 있으면 Claude(`claude-sonnet-5` 기본값), 없고 `GEMINI_API_KEY`가 있으면 Gemini(`gemini-2.0-flash` 기본값), 둘 다 없거나 호출 실패 시 결정론적 템플릿/근거 나열로 폴백. `llm_summarize_node`와 AI Agent 채팅이 이 모듈을 공유 |
| RAG | ChromaDB(`src/rag`) — 법령 조문 청크를 facility_id로 정확 조회해 근거 인용 전용으로 사용 (판정 비관여), 일반 법령 Q&A는 미구현 |
| 트레이싱 | Langfuse(`src/graph/tracing.py`) — 노드별 span 기록, 민감 필드는 allowlist 방식으로 마스킹 |
| 배포 | 단일 Dockerfile로 패키징한 컨테이너를 AWS EC2에 배포. GitHub Actions(`.github/workflows/ci-cd.yml`)가 테스트→GHCR 이미지 push까지는 항상 수행하고, EC2 시크릿이 등록되면 이어서 자동 배포 — 자세한 내용은 "CI/CD 배포" 절 참고 |
| 오케스트레이션 | LangGraph — `search_zone_node`→(조건부 분기)→`he_compute_node`/`plain_compute_node`→`authority_verify_node`(military만)→`rag_check_node`→`llm_summarize_node` 그래프 구현 완료 (`src/graph/build.py`, 시설 1건 판정용 레퍼런스/테스트 경로). Streamlit 대시보드(`app.py`)는 `src/graph/runner.py`의 `run_full_compliance_check()`를 사용하는데, 이 함수는 search_zone_node 없이 일조권(항상 1건) + 반경 내 국가유산·군사시설(각각 0건 이상)을 모두 열거해 서브그래프를 여러 번 실행 — 건물 1건이 세 카테고리를 동시에 위반해도 전부 표시됨 |
| 구조화 기준값 DB | SQLite (`src/db`) — facility_id·regulation_type·height_limit_m 등 기준값을 저장, rag_check_node의 정확 대조(exact match)에 사용 |

---

## 🗄️ 데이터 소스

| 구분 | 출처 | 비고 |
|---|---|---|
| 신축 예정 건물 (판정 대상) | 화면에서 건축사업자가 직접 입력 | 위치·계획 높이 모두 평문, 별도 저장소 없음 |
| 인접 국가유산 참조 데이터 | `src/compliance/config.py`에 하드코딩 | 샘플 좌표/허용높이(남한산성 역사문화환경보존지역), 실 데이터(문화재청 고시) 연동은 이후 단계 |
| 인접 군사시설 참조 데이터 | `src/compliance/config.py`에 하드코딩 | 샘플 좌표/높이제한(성남 서울공항 비행안전구역), 실 데이터 연동은 이후 단계이며 높이제한 값은 비공개 취급 |
| 구조화 기준값 DB | `src/db`(SQLite, 런타임 생성) | facility_id별 height_limit_m·근거 법령·고시일 등을 저장, LangGraph의 `rag_check_node`가 정확 대조에 사용 (문서 임베딩 기반 벡터 검색인 `src/rag`와는 별개) |
| RAG 벡터DB(근거 조문) | `src/rag`(ChromaDB, 런타임 생성) | 건축법·문화재보호법·군사기지법 조문 청크 + facility_id/regulation_type/effective_date/superseded_by 메타데이터. `llm_summarize_node`가 facility_id로 정확 조회해 설명문 근거로만 사용, 판정에는 관여하지 않음 |
| 암호문 캐시 | `src/db/ciphertext_cache.db`(SQLite, `scripts/generate_mock_ciphertexts.py`로 1회 생성 후 저장소에 커밋된 고정 산출물) | facility_id·`ciphertext_blob`(opaque bytes)·`he_context_version`·`issued_at`·`expires_at`만 저장 — 원본 Z값은 이 테이블에 존재하지 않아 커밋해도 안전 |
| 공개 컨텍스트(evaluation key) | `src/he/public_context.bin`(위와 동일하게 1회 생성 후 커밋) | `src/he/context.py`가 로드해 `he_compute_node`의 동형 뺄셈에 사용. 비밀키는 포함하지 않음 |
| 관리기관 비밀키 | `scripts/keys/authority_secret_context.bin`(`scripts/generate_mock_ciphertexts.py`가 생성) | `scripts/mock_authority_verify.py`만 로드. 서비스 코드(`src/`, `app.py`)는 이 파일을 참조하지 않으며, `.gitignore`/`.dockerignore`에 모두 등록되어 커밋·이미지 어디에도 포함되지 않는다 — EC2에는 scp로 배치 후 `docker run -v`로 마운트(위 CI/CD 배포 절 참고) |

---

## 🚀 시작하기

```bash
# 저장소 클론
git clone <repo-url>
cd zecret

# 의존성 설치
pip install -r requirements.txt

# [필수, 최초 1회] Mock 관리기관 사전 준비 — CKKS 키 쌍 생성 + 군사시설 샘플 Z값 암호화 +
# 암호문 캐시/공개 컨텍스트 저장. 이 스크립트를 실행하기 전에는 app.py/pytest 모두
# config.py의 MILITARY_ZONES를 만드는 시점에 실패한다 (암호문 캐시가 비어 있으므로).
python scripts/generate_mock_ciphertexts.py

# 로컬 실행
streamlit run app.py
```

테스트 실행 (3개 판정 카테고리 스키마 검증, 군사시설 카테고리 정밀 수치 비노출 검증, RAG facility_id 조회, LLM 노드의 판정 불변성, Langfuse span redaction, 실제 TenSEAL 연산 결과가 Phase 5 baseline과 일치하는지 등). `tests/conftest.py`가 세션 시작 시 위 사전 준비 스크립트를 자동으로(이미 되어 있으면 건너뜀) 실행하므로 수동 실행 없이도 바로 돌아간다:

```bash
pytest
```

Phase 7 벤치마크(Mock 평문 연산 대 실제 CKKS 연산 속도 비교, 배치 검증 라운드트립 절감 측정):

```bash
python scripts/benchmark_he.py
```

Docker로 실행 (단일 컨테이너, app.py + src/he·compliance·db·graph·agent·rag·scripts 전체 포함). 암호문 캐시/공개 컨텍스트(`src/db/ciphertext_cache.db`, `src/he/public_context.bin`)는 저장소에 커밋된 고정 산출물이라 별도 준비 없이 바로 빌드된다. 다만 `scripts/keys/`의 비밀키는 `.dockerignore`로 이미지에서 항상 제외되므로, 로컬 실행 시 군사시설(HE) 판정을 테스트하려면 저장소 checkout에 `scripts/keys/authority_secret_context.bin`이 이미 있어야 한다(최초 1회 `python scripts/generate_mock_ciphertexts.py` 실행 시 함께 생성됨):

```bash
docker build -t zecret .
docker run --rm -p 8501:8501 --env-file .env \
  -v "$(pwd)/scripts/keys:/app/scripts/keys:ro" \
  zecret
```

### 환경 변수 (예시)

```
ANTHROPIC_API_KEY=your_anthropic_api_key       # 있으면 Claude 우선 사용
ANTHROPIC_MODEL=claude-sonnet-5
GEMINI_API_KEY=your_gemini_api_key             # ANTHROPIC_API_KEY가 없을 때 대신 사용됨
GEMINI_MODEL=gemini-2.0-flash
# 위 두 키가 모두 없으면 llm_summarize_node/AI Agent 채팅 모두 결정론적 폴백 문구로 동작
LANGFUSE_PUBLIC_KEY=                            # 없으면 노드별 트레이싱이 조용히 비활성화됨
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
VWORLD_API_KEY=your_vworld_api_key             # 없으면 지도가 라벨 없는 기본 dark 스타일로 폴백 (실제 건물 표시 안 됨)
```

> ChromaDB(`src/rag`)는 최초 색인 시 로컬 임베딩 모델(all-MiniLM-L6-v2, ~80MB)을 한 번 내려받습니다 — 최초 실행 시에만 인터넷 연결이 필요하고, 이후에는 로컬 캐시를 사용합니다.

### CI/CD 배포

`.github/workflows/ci-cd.yml` 하나로 CI(test → build)와 CD(deploy)를 함께 관리한다. 대상은 **EC2 단일 인스턴스**(ECS는 채택 안 함 — 클러스터·태스크정의 등 관리형 인프라를 미리 만들어둬야 해서 이 프로젝트 규모에는 과함).

| 잡 | 트리거 | 내용 |
|---|---|---|
| `test` | 모든 push/PR | `pytest -q` 실행. 추가 시크릿 없이 항상 돎 (`tests/conftest.py`가 Mock HE 아티팩트를 자동 준비하고, LLM API 키도 강제로 비워 결정론적 폴백 경로만 탐) |
| `build-and-push` | `main` push | checkout 후 바로 Docker 이미지 빌드 → **GHCR**(`ghcr.io/<repo>`)에 push. 암호문 캐시/공개 컨텍스트는 저장소에 커밋된 고정 산출물을 그대로 쓰며, **CI가 매 빌드마다 새 키쌍을 만들지 않는다** — 그러면 EC2에 미리 배치해 둔 비밀키와 짝이 어긋나 군사시설 판정이 복호화 실패로 깨지기 때문. 키를 실제로 교체하려면 로컬에서 `python scripts/generate_mock_ciphertexts.py --force`를 수동으로 돌려 두 산출물을 재커밋하고, 아래 `scripts/keys/`도 EC2에 새로 scp해야 한다 |
| `deploy` | `build-and-push` 성공 후 | EC2에 SSH 접속해 최신 이미지 pull 후 컨테이너 재시작(`scripts/keys/`를 볼륨으로 마운트). **`EC2_HOST` 시크릿이 없으면 실패가 아니라 스킵**되고, 아래 시크릿을 추가하는 순간 다음 `main` push부터 바로 배포까지 이어짐 |

**서버 생성 후 GitHub 리포지토리 Settings → Secrets and variables → Actions에 추가해야 하는 값**

| 시크릿 | 값 |
|---|---|
| `EC2_HOST` | EC2 퍼블릭 IP 또는 도메인 |
| `EC2_USER` | SSH 접속 계정 (예: `ubuntu`, `ec2-user`) |
| `EC2_SSH_KEY` | 위 계정으로 접속 가능한 SSH 프라이빗 키 전체 내용 |

**EC2 쪽에 미리 준비해둬야 하는 것** (배포 스크립트가 가정하는 조건)

- Docker 설치 및 `${EC2_USER}`가 `docker` 그룹에 속해 있을 것 (매 배포 시 `sudo` 없이 `docker` 명령 실행)
- `ghcr.io/<이 리포지토리>` 패키지가 private이면, EC2가 pull할 때 쓰는 `GITHUB_TOKEN`이 해당 패키지에 대한 read 권한을 갖도록(같은 리포지토리 소유면 기본 설정으로 충분) — 안 되면 패키지를 public으로 전환하거나 별도 PAT로 교체
- `/opt/zecret/.env`에 위 "환경 변수" 절 내용을 실제 값으로 채워 미리 배치 (이미지에는 절대 포함되지 않으므로 서버에 직접 있어야 함)
- `/opt/zecret/keys/authority_secret_context.bin`(관리기관 비밀키)을 미리 배치 — 로컬에서 `python scripts/generate_mock_ciphertexts.py` 실행 시 생성되는 `scripts/keys/` 디렉터리를 그대로 scp해서 올린다. 이 키는 git에도 이미지에도 절대 포함되지 않으므로 EC2에 직접 올리는 것 외엔 전달 방법이 없다:
  ```bash
  scp -r scripts/keys ubuntu@<EC2 퍼블릭 IP>:/opt/zecret/
  ```
  이 파일이 없으면 컨테이너는 뜨지만 군사시설(HE) 카테고리 판정 시 `FileNotFoundError`로 실패한다(`scripts/mock_authority_verify.py`) — 문화재/일조권(평문) 판정에는 영향 없음
- 인바운드 보안그룹에서 8501 포트(또는 앞단 리버스 프록시 포트) 허용

---

## ⚠️ 리스크 및 대응

| 리스크 | 대응 방안 |
|---|---|
| 군사시설 참조 데이터·높이제한 실데이터 부재 | 가상/샘플 데이터로 대체, PoC 목적임을 명시 |
| 동형암호 실연산 도입 시 성능·속도 | 처음에는 더 작은 파라미터(N=4096, scale=2^21)로 시작했으나 노이즈가 ±2mm까지 나타나 파라미터를 키워(N=8192, scale=2^40) 노이즈를 ~1e-9m 수준으로 낮춤 — 부트스트래핑 없이 파라미터 조정만으로 해결 (Phase 7 벤치마크 결과는 아래 참고) |
| CKKS 근사 연산의 경계값 불안정성 | 계획높이가 군사시설 기준값과 완전히(부동소수점 단위로) 같은 극단 케이스는 노이즈가 부호를 임의로 결정할 수 있음 — 파라미터를 더 키우거나 부트스트래핑을 붙여도 근본적으로 해결되지 않는, 근사 연산 자체의 한계. 실사용자는 비공개인 군사시설 기준값을 정확히 알아맞힐 수 없어 실질적 영향은 없다고 판단, 테스트에서도 이 극단 케이스만 의도적으로 제외함 (`tests/test_compliance_rules.py` 참고) |
| 2주 내 다기능 구현 부담 | 판정 로직 3종 + UI 우선 구현 후 HE 실연산·AI Agent·RAG 순차 추가 |
| LLM API 키 부재/장애 시 설명문 생성 중단 | `llm_summarize_node`가 결정론적 템플릿 문구로 자동 대체 — 판정 결과(exceeds_limit) 자체는 이 노드가 절대 바꾸지 않으므로 폴백 상태에서도 파이프라인이 끝까지 실행됨 |
| 법령 원문(고시) 미확보 | 실 고시 원문 연동 전까지 공개 조문을 데모용으로 재구성한 텍스트를 `src/rag`에 색인, 군사시설 조문은 수치 없이 "비공개"라는 사실만 서술 |

---

## 📎 Phase 5 baseline

`docs/baseline_phase5.json`, `docs/baseline_phase5_screenshot.png`에 이번 단계(Mock HE + RAG + LLM 연결) 시점의 전체 파이프라인 출력을 기록해 두었습니다. 이 환경은 `ANTHROPIC_API_KEY`가 없어 `llm_summarize_node`가 템플릿 폴백 문구로 동작한 상태의 baseline입니다 — 실제 키를 넣고 `python scripts/capture_phase5_baseline.py`를 다시 실행하면 LLM이 생성한 문장으로 baseline을 갱신할 수 있습니다. 이후 단계에서 판정 로직/그래프를 바꿀 때 이 baseline과 비교해 회귀를 확인하는 용도입니다.

Phase 6(Mock HE → 실제 TenSEAL CKKS 교체) 이후, 군사시설 카테고리에 대해 이 baseline과 동일한 입력으로 실제 CKKS 파이프라인을 실행해 `exceeds_limit`이 baseline과 정확히 일치함을 `tests/test_he_pipeline.py::test_he_result_matches_phase5_baseline`로 확인했습니다 — Mock에서 실 연산으로 바뀌어도 판정 결과 자체는 달라지지 않았습니다. 실제 CKKS 파이프라인이 반영된 화면은 `docs/phase6_real_tenseal_screenshot.png`에 저장해 두었습니다.

---

## 📊 Phase 7 벤치마크

Mock(평문) 파이프라인과 실제 TenSEAL CKKS 파이프라인의 연산 시간을 `scripts/benchmark_he.py`로 비교 측정했습니다 (`he_compute_node`/`plain_compute_node`를 LangGraph `.invoke()` 없이 직접 호출해 상태 전이 오버헤드를 배제, steady-state 30회 평균 · 이 저장소 개발 환경 기준 참고용 수치). 최신 결과는 `docs/benchmark_phase7.json`에도 저장됩니다.

| 측정 항목 | 결과 |
|---|---|
| `he_compute_node` (steady-state) | 평균 ~6ms / 중앙값 ~4.5ms |
| `he_compute_node` (콜드 스타트, 공개 컨텍스트 최초 로드 포함) | ~340ms (프로세스당 1회성 비용) |
| `plain_compute_node` | 평균 ~0.005ms |
| HE ÷ 평문 속도비 | 약 1,300~5,000배 (실행마다 변동 — CKKS 연산이 수 ms, 평문 연산은 수 μs 이하라 비율 자체가 노이즈에 민감) |
| `authority_verify` 배치 처리 (batch_size=20, 워밍업 후) | in-process 절감 효과 없음 (측정마다 -2~+4% 수준, 노이즈 범위) |

**배치 처리에 대한 솔직한 결론**: `verify_diff_batch()`를 구현하고 개별 `verify_diff()` N회 호출과 비교했지만, 이 저장소의 Mock 구조(같은 프로세스 안에서 함수 호출로 관리기관 검증을 흉내냄)에는 실제 네트워크 왕복(RTT)이 없어 배치 처리 자체의 시간 절감이 나타나지 않았습니다. 워밍업 없이 측정했을 때는 배치 쪽이 59.8% 빨라 보이는 결과가 나왔지만, 이는 컨텍스트 최초 로드에 따른 콜드스타트 아티팩트였음을 순서를 바꿔 재측정해 확인했고, 워밍업 후·반복 평균으로는 유의미한 차이가 사라졌습니다. **실제 배포에서 `authority_verify_node`가 진짜 HSM API 호출로 교체되면, N번의 개별 요청을 1번의 배치 요청으로 묶는 것 자체가 N번의 네트워크 왕복을 1번으로 줄이는 효과를 낼 것으로 예상**하지만, 그 절감은 실제 네트워크 지연이 있는 환경에서만 측정 가능하며 이 PoC에서는 검증하지 못했습니다.

---

## 📄 License

MIT License
