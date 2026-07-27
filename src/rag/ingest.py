# 법령 조문(건축법·문화재보호법·군사기지법 등) 청크를 임베딩해 RAG 벡터DB(ChromaDB)에 색인한다.
#
# 이 모듈이 만드는 데이터는 "판정에 관여하지 않는 근거 인용 전용"이다 — 실제 위반/적합
# 판정은 src.compliance.rules / src.graph의 판정 노드가 전담하고, 여기서 색인한 조문은
# llm_summarize_node가 "왜 이 기준이 적용되는지"를 설명할 때만 인용한다.
#
# facility_id는 src.db(Phase 1 구조화 기준값 DB)와 동일한 값을 써서 두 저장소가 같은 키로
# 연결된다. superseded_by가 채워진(빈 문자열이 아닌) 청크는 구버전이며 검색에서 제외한다
# — chromadb 메타데이터는 None을 지원하지 않으므로 "미대체(최신본)"는 빈 문자열로 표현한다.
#
# 실 고시 원문(PDF/HWP) 연동 전이라, 조문 텍스트는 공개된 법령 조문을 데모용으로 재구성한
# 것으로 대체한다 (군사시설 관련 조문은 고도제한 수치 자체가 비공개라는 사실만 서술하고,
# 수치는 절대 포함하지 않는다 — CLAUDE.md 절대 원칙 1).

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import chromadb

CHROMA_PERSIST_DIR = str(Path(__file__).parent / "chroma_store")
COLLECTION_NAME = "legal_citations"


@dataclass
class LegalChunk:
    """법령 조문 청크 1건 — facility_id로 src.db 구조화 기준값 DB와 연결된다."""

    chunk_id: str
    text: str
    facility_id: str
    regulation_type: str  # "sunlight_setback" | "heritage" | "military"
    effective_date: str
    superseded_by: str  # ""면 최신본, 아니면 이 값이 가리키는 chunk_id가 최신본


def load_legal_documents(source_dir: Optional[str] = None) -> List[LegalChunk]:
    """법령 조문 청크 목록을 반환한다.

    source_dir는 실 고시 원문 문서 연동 시 사용할 자리이며, 현재는 사용하지 않는다
    (원문이 없어 조문 텍스트로 대체 — 이번 작업 지시 참고).
    """
    return [
        LegalChunk(
            chunk_id="sunlight_setback_building_act_61_v1",
            text=(
                "[구버전, 1999.05.01. 시행] 건축법 제61조(일조 등의 확보를 위한 건축물의 높이 제한) "
                "및 시행령 제86조: 전용주거지역·일반주거지역 안에서 건축하는 건축물의 높이 9미터 "
                "이하인 부분은 정북방향 인접 대지경계선으로부터 1.5미터 이상을 띄어야 하고, "
                "9미터를 초과하는 부분은 그 건축물 각 부분 높이의 2분의 1 이상을 띄어야 한다."
            ),
            facility_id="sunlight_setback_general",
            regulation_type="sunlight_setback",
            effective_date="1999-05-01",
            superseded_by="sunlight_setback_building_act_61_v2",
        ),
        LegalChunk(
            chunk_id="sunlight_setback_building_act_61_v2",
            text=(
                "건축법 제61조(일조 등의 확보를 위한 건축물의 높이 제한) 및 시행령 제86조 "
                "(2016.02.01. 개정): 전용주거지역·일반주거지역에서 건축물 높이 9미터 이하 부분은 "
                "정북방향 인접 대지경계선으로부터 1.5미터 이상, 9미터를 초과하는 부분은 해당 "
                "높이의 2분의 1 이상을 띄어야 한다. 이 기준에 미달하면 일조권 사선제한 위반이다."
            ),
            facility_id="sunlight_setback_general",
            regulation_type="sunlight_setback",
            effective_date="2016-02-01",
            superseded_by="",
        ),
        LegalChunk(
            chunk_id="heritage_namhansanseong_v1",
            text=(
                "문화재보호법 제13조(역사문화환경 보존지역의 보호) 및 남한산성 역사문화환경 "
                "보존지역 고시: 지정된 국가유산 역사문화환경보존지역 안에서 신축하는 건축물은 "
                "유산별로 개별 고시된 허용 높이를 초과할 수 없다. 남한산성 역사문화환경보존지역의 "
                "허용 높이는 문화재청 고시로 개별 지정되며, 초과 시 경관 훼손을 이유로 건축 허가가 "
                "제한된다."
            ),
            facility_id="heritage_namhansanseong",
            regulation_type="heritage",
            effective_date="2019-06-01",
            superseded_by="",
        ),
        LegalChunk(
            chunk_id="military_seongnam_airport_v1",
            text=(
                "군사기지 및 군사시설 보호법 제10조(비행안전구역에서의 행위 제한) 및 관계 중앙행정 "
                "기관 고시: 비행안전구역 안에서는 항공기 이착륙 안전을 위해 시설물의 높이가 "
                "제한되며, 그 구체적인 고도제한 수치는 군사보안상 비공개다. 신축 건축물은 "
                "관계 기관의 사전 협의·확인 없이 이 높이제한을 초과해서는 안 된다."
            ),
            facility_id="military_seongnam_airport",
            regulation_type="military",
            effective_date="2020-01-01",
            superseded_by="",
        ),
    ]


def embed_and_index(chunks: List[LegalChunk], persist_directory: str = CHROMA_PERSIST_DIR) -> None:
    """청크를 임베딩해 ChromaDB 컬렉션에 저장한다 (chunk_id 기준 upsert라 재실행해도 안전)."""
    client = chromadb.PersistentClient(path=persist_directory)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    collection.upsert(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "facility_id": c.facility_id,
                "regulation_type": c.regulation_type,
                "effective_date": c.effective_date,
                "superseded_by": c.superseded_by,
            }
            for c in chunks
        ],
    )


def ensure_indexed(persist_directory: str = CHROMA_PERSIST_DIR) -> None:
    """컬렉션이 비어 있을 때만 색인한다 — qa.py가 조회 전에 호출하는 idempotent 진입점."""
    client = chromadb.PersistentClient(path=persist_directory)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    if collection.count() == 0:
        embed_and_index(load_legal_documents(), persist_directory)
