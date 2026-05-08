from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

DATA_FILE = Path("shared_data.json")
TASK_STATUSES = ["예정", "진행", "완료"]
CALENDAR_CATEGORIES = ["회의", "외근", "휴무", "특이사항", "일정"]
MEMBER_COLORS = ["#dbeafe", "#dcfce7", "#fef3c7", "#fee2e2", "#ede9fe", "#cffafe"]

DEFAULT_DATA = {
    "previous_total_progress": 58,
    "members": [
        {"id": "kim", "name": "김민수M", "role": "PM"},
        {"id": "hong", "name": "홍길동M", "role": "개발"},
        {"id": "lee", "name": "이서연M", "role": "디자인"},
        {"id": "park", "name": "박지훈M", "role": "QA"},
    ],
    "tasks": [
        {
            "id": "task-001",
            "title": "오픈 보고",
            "owner_id": "hong",
            "status": "진행",
            "priority": "P1",
            "due_date": "2026-05-08",
            "progress": 80,
        },
        {
            "id": "task-002",
            "title": "고객사 주간 리뷰",
            "owner_id": "kim",
            "status": "예정",
            "priority": "P1",
            "due_date": "2026-05-09",
            "progress": 20,
        },
        {
            "id": "task-003",
            "title": "대시보드 와이어프레임",
            "owner_id": "lee",
            "status": "완료",
            "priority": "P2",
            "due_date": "2026-05-06",
            "progress": 100,
        },
        {
            "id": "task-004",
            "title": "회귀 테스트",
            "owner_id": "park",
            "status": "진행",
            "priority": "P2",
            "due_date": "2026-05-07",
            "progress": 65,
        },
    ],
    "calendar": [
        {
            "id": "cal-001",
            "owner_id": "kim",
            "date": "2026-05-08",
            "category": "회의",
            "title": "주간 리더 회의",
        },
        {
            "id": "cal-002",
            "owner_id": "hong",
            "date": "2026-05-08",
            "category": "외근",
            "title": "고객사 현장 지원",
        },
        {
            "id": "cal-003",
            "owner_id": "lee",
            "date": "2026-05-11",
            "category": "휴무",
            "title": "오전 반차",
        },
        {
            "id": "cal-004",
            "owner_id": "park",
            "date": "2026-05-12",
            "category": "특이사항",
            "title": "배포 검증 집중일",
        },
    ],
    "logs": [
        {
            "id": "log-001",
            "timestamp": "2026-05-08T08:50:00",
            "message": "홍길동M이 '오픈 보고' 과제의 진척률을 80%로 수정했습니다.",
        }
    ],
}


def load_data() -> dict:
    if not DATA_FILE.exists():
        save_data(DEFAULT_DATA)
        return deepcopy(DEFAULT_DATA)
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_log(data: dict, message: str) -> None:
    data.setdefault("logs", []).insert(
        0,
        {
            "id": f"log-{uuid4().hex[:8]}",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "message": message,
        },
    )
    data["logs"] = data["logs"][:30]


def member_lookup(data: dict) -> dict[str, str]:
    return {member["id"]: member["name"] for member in data["members"]}


def calculate_total_progress(tasks: list[dict]) -> int:
    if not tasks:
        return 0
    completed = sum(1 for task in tasks if task["status"] == "완료")
    return round((completed / len(tasks)) * 100)


def this_week_range(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def build_task_frame(data: dict) -> pd.DataFrame:
    members = member_lookup(data)
    rows = []
    for task in data["tasks"]:
        rows.append(
            {
                "과제": task["title"],
                "담당자": members.get(task["owner_id"], "미지정"),
                "상태": task["status"],
                "우선순위": task["priority"],
                "마감일": task["due_date"],
                "진척률": f"{task['progress']}%",
            }
        )
    return pd.DataFrame(rows)


def render_top_metrics(data: dict) -> None:
    today = date.today()
    week_start, week_end = this_week_range(today)
    tasks = data["tasks"]
    total_progress = calculate_total_progress(tasks)
    delta = total_progress - int(data.get("previous_total_progress", 0))

    p1_this_week = [
        task
        for task in tasks
        if task["priority"] == "P1" and week_start <= date.fromisoformat(task["due_date"]) <= week_end
    ]
    p1_completed = sum(1 for task in p1_this_week if task["status"] == "완료")

    active_absences = [
        item
        for item in data["calendar"]
        if item["category"] in ["외근", "휴무"] and date.fromisoformat(item["date"]) == today
    ]
    names = member_lookup(data)
    absence_names = ", ".join(names.get(item["owner_id"], "미지정") for item in active_absences) or "없음"

    col1, col2, col3 = st.columns(3)
    col1.metric("전체 과제 수행률", f"{total_progress}%", f"{delta:+d}%p vs 전주")
    col2.metric("금주 P1 마일스톤", f"{p1_completed}/{len(p1_this_week)} 완료", "긴급 과제 기준")
    col3.metric("금일 외근/휴무", f"{len(active_absences)}명", absence_names)


def render_calendar(data: dict) -> None:
    st.subheader("🗓️ 통합 팀 캘린더")
    selected_categories = st.multiselect(
        "카테고리 필터",
        CALENDAR_CATEGORIES,
        default=CALENDAR_CATEGORIES,
        help="회의, 외근, 휴무, 특이사항만 골라 주간 일정을 빠르게 확인합니다.",
    )
    today = date.today()
    week_start, week_end = this_week_range(today)
    week_days = [week_start + timedelta(days=index) for index in range(7)]
    members = member_lookup(data)
    member_color = {
        member["id"]: MEMBER_COLORS[index % len(MEMBER_COLORS)]
        for index, member in enumerate(data["members"])
    }

    rows = []
    for member in data["members"]:
        row = {"담당자": member["name"]}
        for day in week_days:
            events = [
                event
                for event in data["calendar"]
                if event["owner_id"] == member["id"]
                and event["category"] in selected_categories
                and date.fromisoformat(event["date"]) == day
            ]
            row[day.strftime("%m/%d(%a)")] = "\n".join(
                f"{event['category']} · {event['title']}" for event in events
            )
        rows.append(row)

    frame = pd.DataFrame(rows)

    def style_calendar(row: pd.Series) -> list[str]:
        owner_id = next((member_id for member_id, name in members.items() if name == row["담당자"]), "")
        color = member_color.get(owner_id, "#f8fafc")
        styles = [f"background-color: {color}; white-space: pre-wrap" for _ in row.index]
        styles[0] = f"background-color: {color}; font-weight: 700"
        return styles

    st.dataframe(frame.style.apply(style_calendar, axis=1), use_container_width=True, hide_index=True)


def render_workload(data: dict) -> None:
    st.subheader("📊 담당자별 진척도 비교")
    members = member_lookup(data)
    chart_rows = []
    today = date.today()
    overdue_by_owner: dict[str, int] = {}

    for member in data["members"]:
        owned = [task for task in data["tasks"] if task["owner_id"] == member["id"]]
        chart_rows.append(
            {
                "담당자": member["name"],
                "완료": sum(1 for task in owned if task["status"] == "완료"),
                "진행": sum(1 for task in owned if task["status"] == "진행"),
                "예정": sum(1 for task in owned if task["status"] == "예정"),
            }
        )
        overdue_by_owner[member["id"]] = sum(
            1 for task in owned if task["status"] != "완료" and date.fromisoformat(task["due_date"]) < today
        )

    chart_frame = pd.DataFrame(chart_rows).set_index("담당자")
    st.bar_chart(chart_frame)

    worst_owner_id, worst_count = max(
        overdue_by_owner.items(), key=lambda item: item[1], default=("", 0)
    )
    if worst_count > 0:
        st.warning(
            f"⚠️ 병목 주의: {members.get(worst_owner_id, '미지정')} "
            f"담당자가 지연 과제 {worst_count}건으로 가장 많습니다."
        )
    else:
        st.success("현재 마감일이 지난 미완료 과제가 없습니다.")

    with st.expander("전체 과제 상세 보기", expanded=False):
        st.dataframe(build_task_frame(data), use_container_width=True, hide_index=True)


def render_recent_updates(data: dict) -> None:
    st.subheader("🕒 실시간 업무 로그")
    for log in data.get("logs", [])[:10]:
        timestamp = datetime.fromisoformat(log["timestamp"])
        elapsed = datetime.now() - timestamp
        minutes = max(0, int(elapsed.total_seconds() // 60))
        when = "방금 전" if minutes == 0 else f"{minutes}분 전"
        st.caption(f"{when} · {timestamp:%Y-%m-%d %H:%M}")
        st.write(log["message"])


def render_dashboard(data: dict) -> None:
    st.header("🏢 마스터 대시보드")
    render_top_metrics(data)
    st.divider()
    render_calendar(data)
    st.divider()
    render_workload(data)
    st.divider()
    render_recent_updates(data)


def render_member_tab(data: dict, member: dict) -> None:
    st.subheader(f"{member['name']} 개인 업무/일정")
    member_tasks = [task for task in data["tasks"] if task["owner_id"] == member["id"]]

    st.markdown("#### 내 과제 업데이트")
    for task in member_tasks:
        with st.form(f"task-{task['id']}"):
            st.write(f"**{task['title']}** · {task['priority']} · 마감 {task['due_date']}")
            status = st.selectbox("상태", TASK_STATUSES, index=TASK_STATUSES.index(task["status"]), key=f"status-{task['id']}")
            progress = st.slider("진척률", 0, 100, int(task["progress"]), step=5, key=f"progress-{task['id']}")
            submitted = st.form_submit_button("과제 저장")
            if submitted:
                task["status"] = status
                task["progress"] = 100 if status == "완료" else progress
                add_log(
                    data,
                    f"{member['name']}이 '{task['title']}' 과제의 상태를 "
                    f"{task['status']}, 진척률을 {task['progress']}%로 수정했습니다.",
                )
                save_data(data)
                st.success("과제가 저장되었습니다. 대시보드 지표에 즉시 반영됩니다.")
                st.rerun()

    st.markdown("#### 일정 추가")
    with st.form(f"calendar-{member['id']}"):
        event_date = st.date_input("일자", value=date.today(), key=f"event-date-{member['id']}")
        category = st.selectbox("카테고리", CALENDAR_CATEGORIES, key=f"event-category-{member['id']}")
        title = st.text_input("일정 내용", key=f"event-title-{member['id']}")
        submitted = st.form_submit_button("일정 추가")
        if submitted and title.strip():
            data["calendar"].append(
                {
                    "id": f"cal-{uuid4().hex[:8]}",
                    "owner_id": member["id"],
                    "date": event_date.isoformat(),
                    "category": category,
                    "title": title.strip(),
                }
            )
            add_log(
                data,
                f"{member['name']}이 {event_date:%Y-%m-%d} "
                f"'{title.strip()}' 일정을 추가했습니다.",
            )
            save_data(data)
            st.success("일정이 저장되었습니다. 통합 팀 캘린더에 즉시 반영됩니다.")
            st.rerun()


def render_deployment_info() -> None:
    st.sidebar.info(
        "서버 PC에서 `streamlit run app.py --server.address 0.0.0.0`로 실행한 뒤 "
        "터미널의 Network URL을 팀원들에게 공유하세요. 모든 접속자는 `shared_data.json`을 함께 사용합니다."
    )


def main() -> None:
    st.set_page_config(page_title="팀 마스터 대시보드", page_icon="🏢", layout="wide")
    data = load_data()
    st.title("팀 협업 마스터 대시보드")
    st.caption("전사 성과, 주간 캘린더, 담당자별 병목, 실시간 로그를 한 화면에서 확인합니다.")
    render_deployment_info()

    tabs = st.tabs(["마스터 대시보드"] + [member["name"] for member in data["members"]])
    with tabs[0]:
        render_dashboard(data)
    for tab, member in zip(tabs[1:], data["members"]):
        with tab:
            render_member_tab(data, member)


if __name__ == "__main__":
    main()
