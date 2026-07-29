# Streamlit 진입점 — 관제센터(control room) 스타일 대시보드.
# (판정/LLM 로직은 src/graph LangGraph 파이프라인·src/agent AI Agent에서 실행, 이 파일에는
# HE/판정/LLM 로직을 직접 넣지 않는다 — app.py는 결과 dict/dataclass·문자열을 렌더링만 한다)
#
# 좌측 제어반(사이드바)은 폼(form)이다 — 입력값이 바뀔 때마다 자동으로 재계산하지 않고,
# "🔍 검색" 버튼을 눌러야 그래프가 실행된다 (원할 때 검색).
#
# 계획 건물 위치(지도)/판정 현황/LLM 질의응답 3개 패널은 검색 여부와 무관하게 항상 화면에
# 떠 있다 — 검색 전에는 기본 위치·안내 문구만 보이고, 검색 후에 그 자리에 결과가 채워진다.
#
# 모든 카테고리는 위반/적합 이진 결과만 표시한다 — margin(부족분/여유 등 정밀 수치)은
# 그래프의 computation_result에는 존재하지만, 화면에는 절대 렌더링하지 않는다.
# 배지 아래의 설명문(final_message)은 llm_summarize_node가 만든 자연어 요약으로,
# 프롬프트 설계상 margin/정밀 수치를 언급하지 않는다 (src/graph/nodes.py 참고).
# LLM 질의응답 채팅도 동일 원칙(CLAUDE.md 절대 원칙 5)을 따른다 — src/agent/router.py의
# handle_agent_query()가 이미 확정된 판정 결과+RAG 근거만 LLM에 넘기고, LLM은 그걸
# 설명/답변할 뿐 판정을 재계산하지 않는다.
# 지도에는 계획 건물 위치 1개만 표시하고, 인접 국가유산/군사시설의 위치는 표시하지 않는다.

import html
import os
from datetime import date

import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv

from src.agent.router import handle_agent_query
from src.compliance import config
from src.compliance.search import find_nearby_restricted_zones, summarize_nearby
from src.geo.buildings import fetch_nearby_building_footprints, to_building_layer_data
from src.geo.risk_grid import build_risk_grid
from src.graph.runner import run_full_compliance_check

load_dotenv()

# 지도에 그릴 "인접 판정 반경" — 국가유산 기본 반경과 군사시설 유형별 반경(제5조 근거) 중
# 가장 큰 값을 시연용 원/격자 표시 기준으로 쓴다. 판정 로직 자체는 카테고리별 반경을 각각
# 따로 쓰므로(src.graph.runner), 이 값은 순수 시각화 기준일 뿐이다.
DISPLAY_RADIUS_M = max(
    [config.ADJACENCY_RADIUS_M] + [config.zone_radius_m(zone) for zone in config.MILITARY_ZONES]
)

# VWorld Open API(https://www.vworld.kr) WMTS 배경지도 — 실제 건물 폴리곤·도로·주소 라벨이 보이는
# 공공 지도 타일. X/Y(위치)는 CLAUDE.md 원칙상 평문 취급 대상이라 타일 요청에 Z값은 전혀 실리지 않는다.
# "midnight"(야간모드) 레이어를 골라 관제센터 다크 테마와 톤을 맞춘다. 키 미발급 시 라벨 없는 기본
# pydeck 스타일로 자동 폴백한다.
VWORLD_API_KEY = os.environ.get("VWORLD_API_KEY", "")
VWORLD_TILE_URL = f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_API_KEY}/midnight/{{z}}/{{y}}/{{x}}.png"

CATEGORY_ORDER = ["sunlight_setback", "heritage", "military"]
CATEGORY_LABEL = {
    "sunlight_setback": "☀ 일조권 사선제한",
    "heritage": "🏛 국가유산 경관보호",
    "military": "🪖 군사시설 비행안전구역",
}

# 검색 전 지도에 보여줄 기본 위치 — 서울공항 제한보호구역·남한산성 국가유산 반경이 겹치는
# 데모 좌표(src.compliance.config의 실제 시설 좌표 기준).
DEFAULT_MAP_X = 127.1567
DEFAULT_MAP_Y = 37.4504

ACCENT = "#3987e5"  # dataviz 스킬 카테고리 슬롯1(blue, dark) — 관제센터 주조색
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"
MUTED = "#898781"

st.set_page_config(
    page_title="ZeCret — Height Compliance Control Center",
    page_icon="🛰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
    .zc-gridbg {{
        position: fixed; inset: 0; z-index: -1; pointer-events: none;
        background-image:
            linear-gradient(rgba(57,135,229,0.06) 1px, transparent 1px),
            linear-gradient(90deg, rgba(57,135,229,0.06) 1px, transparent 1px);
        background-size: 28px 28px;
    }}
    .zc-title {{
        font-family: "Consolas", "SFMono-Regular", "Courier New", monospace;
        letter-spacing: 3px; text-transform: uppercase; font-size: 28px;
        color: {ACCENT}; text-shadow: 0 0 10px rgba(57,135,229,0.55); margin-bottom: 2px;
    }}
    .zc-subtitle {{
        font-family: "Consolas", "SFMono-Regular", "Courier New", monospace;
        color: {MUTED}; font-size: 13px; line-height: 1.6; max-width: 900px;
    }}
    .zc-panel-title {{
        font-family: monospace; letter-spacing: 2px; text-transform: uppercase;
        font-size: 12px; color: #c3c2b7; border-bottom: 1px solid #2c2c2a;
        padding-bottom: 6px; margin-bottom: 10px;
    }}
    .zc-stat {{
        border: 1px solid rgba(255,255,255,0.10); border-radius: 8px;
        background: #14181f; padding: 14px 10px; text-align: center;
    }}
    .zc-stat-value {{ font-family: monospace; font-size: 34px; font-weight: 700; line-height: 1; }}
    .zc-stat-label {{
        font-family: monospace; font-size: 11px; letter-spacing: 2px;
        text-transform: uppercase; color: {MUTED}; margin-top: 6px;
    }}
    .zc-row {{
        display: flex; align-items: center; justify-content: space-between;
        padding: 9px 14px; margin-bottom: 6px; background: #14181f;
        border: 1px solid rgba(255,255,255,0.07); border-radius: 6px;
    }}
    .zc-row-name {{ font-family: monospace; font-size: 13px; color: #e6e6e6; }}
    .zc-row-note {{
        font-family: monospace; font-size: 11.5px; color: {MUTED}; line-height: 1.5;
        padding: 0 14px 10px 14px; margin-top: -4px; margin-bottom: 6px;
    }}
    .zc-badge {{
        display: inline-block; font-family: monospace; font-size: 11px;
        letter-spacing: 1.5px; padding: 3px 10px; border-radius: 4px; font-weight: 700;
    }}
    .zc-badge-ok {{ background: rgba(12,163,12,0.15); color: {STATUS_GOOD}; border: 1px solid rgba(12,163,12,0.4); }}
    .zc-badge-critical {{ background: rgba(208,59,59,0.15); color: {STATUS_CRITICAL}; border: 1px solid rgba(208,59,59,0.4); }}
    section[data-testid="stSidebar"] .zc-panel-title {{ margin-top: 4px; }}
    /* 사이드바 폼 입력창에 뜨는 "Press Enter to submit form" 힌트 숨김 */
    div[data-testid="InputInstructions"] {{ display: none; }}
    /* Control Panel을 닫는 것만 막는다 — 펼치기 버튼까지 숨기면 브라우저가 접힌 상태를
       기억하고 있을 때(localStorage) 다시 열 방법이 없어져 사이드바가 영영 안 보이게 된다. */
    button[data-testid="stSidebarCollapseButton"] {{ display: none; }}
    </style>
    <div class="zc-gridbg"></div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="zc-title">🛰 ZeCret</div>', unsafe_allow_html=True)
st.write("")

# --- 세션 상태: 마지막 검색 결과/입력값, 채팅 기록 (검색 버튼을 눌러야만 갱신됨) ---
if "report" not in st.session_state:
    st.session_state.report = None
if "searched_inputs" not in st.session_state:
    st.session_state.searched_inputs = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "nearby_summary" not in st.session_state:
    st.session_state.nearby_summary = None

st.sidebar.markdown('<div class="zc-panel-title">▌ Control Panel</div>', unsafe_allow_html=True)
with st.sidebar.form("search_form"):
    plan_x_plain = st.number_input(
        "경도 (X)", value=None, format="%.6f", placeholder="예: 127.156700"
    )
    plan_y_plain = st.number_input(
        "위도 (Y)", value=None, format="%.6f", placeholder="예: 37.450400"
    )
    plan_height_plain = st.number_input(
        "계획 높이 (m)", value=None, min_value=0.0, placeholder="예: 20.0"
    )
    setback_distance_m = st.number_input(
        "인접대지경계선까지 이격거리 (m)",
        value=None,
        min_value=0.0,
        placeholder="예: 3.0",
        help="건축법 제61조·시행령 제86조 일조권 사선제한 판정에 사용됩니다.",
    )
    submitted = st.form_submit_button("🔍 검색")

target_date = st.sidebar.date_input(
    "판정 기준일",
    value=date(date.today().year, 12, 21),
    help="현재 단계의 판정 규칙은 이격거리 기준(사선제한)만 사용하며 날짜에 영향받지 않습니다. "
    "일조 시간대 기반 판정을 다시 도입할 경우를 대비한 입력 자리입니다.",
)

if submitted:
    search_inputs = (plan_x_plain, plan_y_plain, plan_height_plain, setback_distance_m)
    if any(value is None for value in search_inputs):
        st.sidebar.error("경도·위도·계획 높이·이격거리를 모두 입력해주세요.")
    else:
        st.session_state.searched_inputs = search_inputs
        # 반경 검색(요청 기능 1) — 존재 여부/개수만 조회, 높이(Z)는 이 호출에 전혀 등장하지 않는다.
        st.session_state.nearby_summary = summarize_nearby(find_nearby_restricted_zones(plan_x_plain, plan_y_plain))
        st.session_state.report = run_full_compliance_check(*search_inputs)
        st.session_state.chat_history = []  # 새 건물을 검색하면 이전 대화는 비운다

report = st.session_state.report
searched_inputs = st.session_state.searched_inputs
nearby_summary = st.session_state.nearby_summary
map_x = searched_inputs[0] if searched_inputs else DEFAULT_MAP_X
map_y = searched_inputs[1] if searched_inputs else DEFAULT_MAP_Y

total_count = len(report) if report is not None else 0
violation_count = sum(1 for item in report if item.exceeds_limit) if report else 0
ok_count = total_count - violation_count
nearby_count = (nearby_summary["heritage_count"] + nearby_summary["military_count"]) if nearby_summary else 0

s1, s2, s3, s4 = st.columns(4)
for col, label, value, color in (
    (s1, "판정 항목", total_count, "#e6e6e6"),
    (s2, "위반", violation_count, STATUS_CRITICAL),
    (s3, "적합", ok_count, STATUS_GOOD),
    (s4, "반경 내 시설", nearby_count, ACCENT),
):
    col.markdown(
        f'<div class="zc-stat"><div class="zc-stat-value" style="color:{color};">{value}</div>'
        f'<div class="zc-stat-label">{label}</div></div>',
        unsafe_allow_html=True,
    )

st.write("")
map_col, status_col = st.columns([1, 2])

with map_col:
    st.markdown('<div class="zc-panel-title">▌ 계획 건물 위치</div>', unsafe_allow_html=True)

    layers = []

    if VWORLD_API_KEY:
        # 실제 건물 폴리곤이 보이는 VWorld 타일을 배경으로 직접 그린다 — pydeck 자체 Mapbox/Carto
        # 배경지도(map_style)는 끄고(map_provider=None) TileLayer로 대체한다.
        layers.append(
            pdk.Layer("TileLayer", data=VWORLD_TILE_URL, min_zoom=0, max_zoom=19, tile_size=256)
        )

        # 실제 성남시 건물 footprint를 2.5D로 압출해 배경 맥락만 보여준다(판정과 무관, 높이는
        # VWorld 속성값 또는 층수 추정치일 뿐 계획 건물/인접 시설의 Z값과는 아무 관계가 없다).
        building_features = to_building_layer_data(fetch_nearby_building_footprints(map_x, map_y))
        if building_features["features"]:
            layers.append(
                pdk.Layer(
                    "GeoJsonLayer",
                    data=building_features,
                    extruded=True,
                    get_elevation="properties.height_m",
                    get_fill_color=[90, 100, 110, 160],
                    get_line_color=[140, 150, 160, 200],
                    line_width_min_pixels=1,
                )
            )

    # 격자 단위 위험도(CLAUDE.md 원칙 4) — 개별 시설의 정밀 위치/형태 대신, 반경을 나눈
    # 격자 셀마다 "겹치는 인접 시설 개수"만 색으로 표시한다. 높이(Z)는 쓰지 않는다.
    # ScatterplotLayer로 셀 중심마다 cell_size 반경의 정사각형 근사 원을 그린다 — GridCellLayer는
    # Streamlit 번들 deck.gl 레이어 레지스트리에 없어(GeoJsonLayer로 오인되며 렌더링 실패)
    # 대신 이미 검증된 ScatterplotLayer를 재사용한다.
    nearby_facilities = find_nearby_restricted_zones(map_x, map_y) if searched_inputs else []
    risk_cells = build_risk_grid(map_x, map_y, DISPLAY_RADIUS_M, nearby_facilities)
    if risk_cells:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=[
                    {
                        "lon": cell.center_x,
                        "lat": cell.center_y,
                        "color": [208, 59, 59, 90] if cell.facility_count > 0 else [57, 135, 229, 20],
                    }
                    for cell in risk_cells
                ],
                get_position="[lon, lat]",
                get_fill_color="color",
                get_radius=125,  # cell_size(250m)의 절반 — 셀끼리 맞닿는 정도로 근사
                stroked=False,
                pickable=False,
            )
        )

    # 검색 반경 표시(요청 4 — 검색 반경 오버레이) — 채워진 원이 아니라 테두리만 그려 아래
    # 격자/배경이 가려지지 않게 한다.
    if searched_inputs:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=[{"lat": map_y, "lon": map_x}],
                get_position="[lon, lat]",
                get_radius=DISPLAY_RADIUS_M,
                stroked=True,
                filled=False,
                get_line_color=[57, 135, 229, 160],
                line_width_min_pixels=1,
            )
        )

    # 계획 건물 위치 — 유일하게 "정확한 위치"를 직접 그리는 마커. 인접 국가유산/군사시설의
    # 정확한 위치는 위 격자 레이어로만 반영되고 별도 마커로 그려지지 않는다.
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=[{"lat": map_y, "lon": map_x}],
            get_position="[lon, lat]",
            get_fill_color=[57, 135, 229, 220],
            get_radius=40,
            radius_min_pixels=8,
            radius_max_pixels=40,
        )
    )

    if VWORLD_API_KEY:
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=map_y, longitude=map_x, zoom=17),
            map_provider=None,
            # map_style를 명시적으로 비우지 않으면 pydeck이 내부 플레이스홀더 문자열
            # "__MAP_STYLE__"을 그대로 흘려보내 프론트엔드 베이스맵 초기화가 깨진다.
            map_style=None,
        )
    else:
        # 지명 라벨이 있는 배경지도는 확대/축소 단계에 따라 영문/한글이 뒤섞여 보이는 문제가 있어,
        # 라벨이 아예 없는 스타일(dark_no_labels)을 써서 언어 혼용 자체를 없앤다.
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=map_y, longitude=map_x, zoom=13),
            map_style="dark_no_labels",
        )
    st.pydeck_chart(deck)
    if searched_inputs is None:
        st.caption("검색 전 기본 위치입니다. 좌측에서 검색하면 계획 건물 위치로 갱신됩니다.")
    if not VWORLD_API_KEY:
        st.caption("VWORLD_API_KEY 미설정 — 실제 건물이 보이는 배경지도를 쓰려면 .env에 키를 추가하세요.")
    st.caption("인접 국가유산/군사시설은 정확한 위치 대신 격자 단위 위험도로만 표시합니다.")

with status_col:
    st.markdown('<div class="zc-panel-title">▌ 판정 현황</div>', unsafe_allow_html=True)
    if report is None:
        st.info("좌측 제어반에 값을 입력하고 🔍 검색을 실행하면 판정 결과가 표시됩니다.")
    elif not report:
        st.info("이 위치 기준 인접한 판정 대상 시설/유산이 없습니다.")
    else:
        items_by_category = {t: [i for i in report if i.facility_type == t] for t in CATEGORY_ORDER}
        for facility_type in CATEGORY_ORDER:
            items = items_by_category[facility_type]
            if not items:
                continue
            st.markdown(f"**{CATEGORY_LABEL[facility_type]}**")
            for item in items:
                badge_class = "zc-badge-critical" if item.exceeds_limit else "zc-badge-ok"
                badge_text = "위반" if item.exceeds_limit else "적합"
                # 군사시설처럼 규정 테마가 여러 개인 시설은 이름 옆에 "어떤 규정을 판단했는지"
                # 표시한다 — 같은 시설이라도 테마별로 위반/적합이 갈릴 수 있기 때문이다.
                row_name = (
                    f"{item.facility_name} <span style='color:{MUTED};font-size:11px;'>"
                    f"({html.escape(item.regulation_label)})</span>"
                    if item.regulation_label
                    else item.facility_name
                )
                st.markdown(
                    f'<div class="zc-row"><span class="zc-row-name">{row_name}</span>'
                    f'<span class="zc-badge {badge_class}">{badge_text}</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="zc-row-note">{html.escape(item.final_message)}</div>',
                    unsafe_allow_html=True,
                )

st.write("")
st.markdown('<div class="zc-panel-title">▌ LLM 질의응답</div>', unsafe_allow_html=True)

user_question = st.chat_input("판정 결과에 대해 질문해보세요 (예: 어떤 법령을 위반했나요?)")
if user_question:
    st.session_state.chat_history.append({"role": "user", "content": user_question})
    if report is None:
        answer = "먼저 좌측 제어반(Control Panel)에서 🔍 검색을 실행해주세요."
    else:
        answer = handle_agent_query(user_question, report)
    st.session_state.chat_history.append({"role": "assistant", "content": answer})

if not st.session_state.chat_history:
    st.caption("검색 후 판정 결과와 근거 법령에 대해 자유롭게 질문할 수 있습니다.")
else:
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
