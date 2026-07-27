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
from datetime import date

import pydeck as pdk
import streamlit as st

from src.agent.router import handle_agent_query
from src.graph.runner import run_full_compliance_check

CATEGORY_ORDER = ["sunlight_setback", "heritage", "military"]
CATEGORY_LABEL = {
    "sunlight_setback": "☀ 일조권 사선제한",
    "heritage": "🏛 국가유산 경관보호",
    "military": "🪖 군사시설 비행안전구역",
}

# 검색 전 지도에 보여줄 기본 위치 (성남 서울공항 비행안전구역 인근 데모 좌표)
DEFAULT_MAP_X = 127.125000
DEFAULT_MAP_Y = 37.126000

ACCENT = "#3987e5"  # dataviz 스킬 카테고리 슬롯1(blue, dark) — 관제센터 주조색
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"
MUTED = "#898781"

st.set_page_config(page_title="ZeCret — Height Compliance Control Center", page_icon="🛰", layout="wide")

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

st.sidebar.markdown('<div class="zc-panel-title">▌ Control Panel</div>', unsafe_allow_html=True)
with st.sidebar.form("search_form"):
    plan_x_plain = st.number_input(
        "경도 (X)", value=None, format="%.6f", placeholder="예: 127.125000"
    )
    plan_y_plain = st.number_input(
        "위도 (Y)", value=None, format="%.6f", placeholder="예: 37.126000"
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
        st.session_state.report = run_full_compliance_check(*search_inputs)
        st.session_state.chat_history = []  # 새 건물을 검색하면 이전 대화는 비운다

report = st.session_state.report
searched_inputs = st.session_state.searched_inputs
map_x = searched_inputs[0] if searched_inputs else DEFAULT_MAP_X
map_y = searched_inputs[1] if searched_inputs else DEFAULT_MAP_Y

total_count = len(report) if report is not None else 0
violation_count = sum(1 for item in report if item.exceeds_limit) if report else 0
ok_count = total_count - violation_count

s1, s2, s3 = st.columns(3)
for col, label, value, color in (
    (s1, "판정 항목", total_count, "#e6e6e6"),
    (s2, "위반", violation_count, STATUS_CRITICAL),
    (s3, "적합", ok_count, STATUS_GOOD),
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
    # 지명 라벨이 있는 배경지도는 확대/축소 단계에 따라 영문/한글이 뒤섞여 보이는 문제가 있어,
    # 라벨이 아예 없는 스타일(dark_no_labels)을 써서 언어 혼용 자체를 없앤다.
    marker_layer = pdk.Layer(
        "ScatterplotLayer",
        data=[{"lat": map_y, "lon": map_x}],
        get_position="[lon, lat]",
        get_fill_color=[57, 135, 229, 220],
        get_radius=40,
        radius_min_pixels=8,
        radius_max_pixels=40,
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[marker_layer],
            initial_view_state=pdk.ViewState(latitude=map_y, longitude=map_x, zoom=13),
            map_style="dark_no_labels",
        )
    )
    if searched_inputs is None:
        st.caption("검색 전 기본 위치입니다. 좌측에서 검색하면 계획 건물 위치로 갱신됩니다.")
    st.caption("인접 국가유산/군사시설의 위치는 지도에 표시하지 않습니다.")

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
                st.markdown(
                    f'<div class="zc-row"><span class="zc-row-name">{item.facility_name}</span>'
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
