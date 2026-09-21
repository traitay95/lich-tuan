import json
import base64
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, time, timedelta, timezone

# =========================================================
# ⚙️ CẤU HÌNH & MÚI GIỜ
# =========================================================
VN_TZ = timezone(timedelta(hours=7))

GITHUB_USER = st.secrets.get("GITHUB_USER", "traitay95")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "lich-tuan")
BRANCH = st.secrets.get("BRANCH", "main")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

BASE_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

st.set_page_config(page_title="Lịch Làm Việc Phòng Kế Hoạch", layout="wide", page_icon="📅")

# =========================================================
# 🛠️ HÀM KẾT NỐI GITHUB REST API
# =========================================================
def load_data_from_github(filename, default_data):
    url = f"{BASE_URL}/{filename}?ref={BRANCH}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            content = res.json()
            decoded_bytes = base64.b64decode(content["content"])
            data = json.loads(decoded_bytes.decode('utf-8'))
            return data, content["sha"]
        elif res.status_code == 404:
            save_data_to_github(filename, default_data, sha=None, commit_msg=f"Init {filename}")
            return default_data, None
    except Exception as e:
        st.error(f"Lỗi đọc {filename}: {e}")
    return default_data, None

def save_data_to_github(filename, data, sha=None, commit_msg="Update data"):
    url = f"{BASE_URL}/{filename}"
    content_str = json.dumps(data, ensure_ascii=False, indent=2)
    encoded_content = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
    payload = {"message": commit_msg, "content": encoded_content, "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    try:
        res = requests.put(url, json=payload, headers=HEADERS, timeout=5)
        if res.status_code in [200, 201]:
            st.cache_data.clear()
            return True
    except Exception as e:
        st.error(f"Lỗi ghi {filename}: {e}")
    return False

# Load dữ liệu
schedules_data, schedules_sha = load_data_from_github("schedules.json", [])
staffs_data, staffs_sha = load_data_from_github("staffs.json", [])
staff_names = [s["name"] for s in staffs_data if "name" in s]

# =========================================================
# 🎛️ KHỞI TẠO STATE ĐIỀU HƯỚNG VÀ HIGHLIGHT
# =========================================================
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "tab1"
if "selected_task_id" not in st.session_state:
    st.session_state["selected_task_id"] = None
if "selected_date" not in st.session_state:
    st.session_state["selected_date"] = datetime.now(VN_TZ).date()

# =========================================================
# 🎨 HÀM XÁC ĐỊNH MÀU NỔI BẬT
# =========================================================
def get_task_highlight_status(task_date_str, task_time_str, task_status=""):
    if task_status in ["Hoàn thành", "Hủy"]:
        return None, None, None
    try:
        task_datetime = datetime.strptime(f"{task_date_str} {task_time_str}", "%Y-%m-%d %H:%M")
        now = datetime.now(VN_TZ).replace(tzinfo=None)
        diff = (task_datetime - now).total_seconds()
        if 0 <= diff <= 2 * 3600:
            return "#FFD2D2", "#D8000C", "🔴 Còn < 2 tiếng"
        elif 2 * 3600 < diff <= 24 * 3600:
            return "#FFF3CD", "#856404", "🟡 Còn < 24 tiếng"
    except Exception:
        pass
    return None, None, None

# =========================================================
# ✏️ DIALOG SỬA CÔNG VIỆC
# =========================================================
@st.dialog("✏️ Chỉnh Sửa Lịch Làm Việc")
def edit_schedule_dialog(task_idx, task, staff_options):
    with st.form("form_edit_schedule"):
        edit_title = st.text_input("Nội dung công việc / Cuộc họp (*)", value=task.get("title", ""))
        
        default_index = staff_options.index(task.get("nguoi_phu_trach")) if task.get("nguoi_phu_trach") in staff_options else 0
        edit_nguoi_phu_trach = st.selectbox("Người phụ trách (*)", options=staff_options or [task.get("nguoi_phu_trach", "")], index=default_index)

        try:
            curr_date = datetime.strptime(task.get("ngay"), "%Y-%m-%d").date()
            curr_start = datetime.strptime(task.get("gio_bat_dau"), "%H:%M").time()
            curr_end = datetime.strptime(task.get("gio_ket_thuc"), "%H:%M").time()
        except Exception:
            curr_date = datetime.now(VN_TZ).date()
            curr_start, curr_end = time(8, 0), time(9, 0)

        col1, col2 = st.columns(2)
        with col1:
            edit_ngay_lam = st.date_input("Ngày thực hiện", value=curr_date)
        with col2:
            edit_gio_bat_dau = st.time_input("Giờ bắt đầu", value=curr_start)
            edit_gio_ket_thuc = st.time_input("Giờ kết thúc", value=curr_end)

        edit_ghi_chu = st.text_area("Địa điểm / Ghi chú", value=task.get("ghi_chu", ""))
        status_list = ["Dự kiến", "Chính thức", "Hoàn thành", "Hủy"]
        curr_status_idx = status_list.index(task.get("trang_thai")) if task.get("trang_thai") in status_list else 0
        edit_trang_thai = st.selectbox("Trạng thái", status_list, index=curr_status_idx)

        if st.form_submit_button("💾 Cập Nhật Lịch Hẹn"):
            schedules_data[task_idx] = {
                "id": task["id"],
                "title": edit_title,
                "nguoi_phu_trach": edit_nguoi_phu_trach,
                "ngay": edit_ngay_lam.strftime("%Y-%m-%d"),
                "gio_bat_dau": edit_gio_bat_dau.strftime("%H:%M"),
                "gio_ket_thuc": edit_gio_ket_thuc.strftime("%H:%M"),
                "ghi_chu": edit_ghi_chu,
                "trang_thai": edit_trang_thai,
            }
            if save_data_to_github("schedules.json", schedules_data, schedules_sha, f"Update task {task['id']}"):
                st.success("Đã cập nhật!")
                st.rerun()

# =========================================================
# 🖥️ GIAO DIỆN CHÍNH STREAMLIT
# =========================================================
st.title("📅 Quản Lý Lịch Làm Việc - Phòng Kế Hoạch")

# Sidebar thêm lịch
with st.sidebar.form("form_dangkylich", clear_on_submit=True):
    st.header("📝 Đăng ký lịch làm việc")
    title = st.text_input("Nội dung công việc (*)")
    nguoi_phu_trach = st.selectbox("Người phụ trách (*)", options=staff_names if staff_names else ["Khác"])
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        ngay_lam = st.date_input("Ngày thực hiện", datetime.now(VN_TZ).date())
    with col_d2:
        gio_bat_dau = st.time_input("Giờ bắt đầu", time(8, 0))
        gio_ket_thuc = st.time_input("Giờ kết thúc", time(9, 0))
    ghi_chu = st.text_area("Ghi chú")
    trang_thai = st.selectbox("Trạng thái", ["Dự kiến", "Chính thức", "Hoàn thành", "Hủy"])

    if st.form_submit_button("💾 Lưu Lịch Hẹn"):
        new_task = {
            "id": f"task_{int(datetime.now().timestamp())}",
            "title": title,
            "nguoi_phu_trach": nguoi_phu_trach,
            "ngay": ngay_lam.strftime("%Y-%m-%d"),
            "gio_bat_dau": gio_bat_dau.strftime("%H:%M"),
            "gio_ket_thuc": gio_ket_thuc.strftime("%H:%M"),
            "ghi_chu": ghi_chu,
            "trang_thai": trang_thai
        }
        schedules_data.append(new_task)
        save_data_to_github("schedules.json", schedules_data, schedules_sha, "Add task")
        st.rerun()

# TAB NAVIGATION DÙNG RADIO / TABS CỦA STREAMLIT
tabs = ["📆 Lịch Theo Tuần", "📋 Danh Sách Chi Tiết"]
selected_tab = st.radio("Chuyển Tab View:", tabs, horizontal=True, index=0 if st.session_state["active_tab"] == "tab1" else 1)

# =========================================================
# TAB 1: LỊCH THEO TUẦN
# =========================================================
if selected_tab == "📆 Lịch Theo Tuần":
    st.session_state["active_tab"] = "tab1"
    
    col_w1, col_w2 = st.columns([1, 2])
    with col_w1:
        # Tự động lấy ngày đã chọn từ state nếu người dùng bấm từ Tab Danh sách
        picked_date = st.date_input("🗓️ Chọn ngày xem lịch:", value=st.session_state["selected_date"])
        st.session_state["selected_date"] = picked_date
        
        start_of_week = picked_date - timedelta(days=picked_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        st.info(f"📌 **Tuần:** {start_of_week.strftime('%d/%m/%Y')} - {end_of_week.strftime('%d/%m/%Y')}")

    week_days = [start_of_week + timedelta(days=i) for i in range(7)]
    day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    cols = st.columns(7)

    for i, col in enumerate(cols):
        current_day = week_days[i]
        day_str = current_day.strftime("%Y-%m-%d")
        with col:
            is_selected_day = (current_day == st.session_state["selected_date"])
            st.markdown(f"### {'🎯' if is_selected_day else '🗓️'} {day_names[i]}")
            st.caption(current_day.strftime("%d/%m/%Y"))
            st.divider()

            day_tasks = [t for t in schedules_data if t.get("ngay") == day_str]
            day_tasks = sorted(day_tasks, key=lambda x: x.get("gio_bat_dau", ""))

            if day_tasks:
                for task in day_tasks:
                    # Đánh dấu viền/màu nổi bật nếu công việc này được chọn từ Danh Sách
                    is_focused = (task["id"] == st.session_state.get("selected_task_id"))
                    
                    bg_color, text_color, badge = get_task_highlight_status(
                        task.get("ngay"), task.get("gio_bat_dau"), task.get("trang_thai")
                    )

                    border_style = "3px solid #0056b3" if is_focused else f"1px solid {text_color if text_color else '#ccc'}"
                    box_bg = "#E8F0FE" if is_focused else (bg_color if bg_color else "#FFFFFF")

                    st.markdown(
                        f"""
                        <div style="background-color: {box_bg}; padding: 8px; border-radius: 6px; margin-bottom: 8px; border: {border_style};">
                            {'<b>' + badge + '</b><br>' if badge else ''}
                            {'<b>🎯 Đang chọn</b><br>' if is_focused else ''}
                            ⏰ <b>{task['gio_bat_dau']} - {task['gio_ket_thuc']}</b><br>
                            <b>{task['title']}</b><br>
                            👤 <small>{task['nguoi_phu_trach']}</small>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    if st.button("✏️ Sửa", key=f"btn_edit_w_{task['id']}"):
                        edit_schedule_dialog(schedules_data.index(task), task, staff_names)
            else:
                st.caption("_Không có lịch_")

# =========================================================
# TAB 2: DANH SÁCH CHI TIẾT
# =========================================================
else:
    st.session_state["active_tab"] = "tab2"
    st.subheader("📋 Danh Sách Lịch Chi Tiết")
    st.caption("💡 **Mẹo:** Bấm nút **🎯 Xem Lịch Tuần** trên bất kỳ dòng nào để nhảy ngay đến tuần và highlight công việc đó.")

    if schedules_data:
        # Tạo bảng tương tác hiển thị từng dòng với đầy đủ nút Sửa & Trỏ đến Lịch Tuần
        df_all = pd.DataFrame(schedules_data)
        df_sorted = df_all.sort_values(by=["ngay", "gio_bat_dau"], ascending=[False, False])

        # Header bảng
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6, h_col7 = st.columns([1.2, 1, 2.5, 1.5, 1, 1, 1])
        h_col1.write("**Ngày**")
        h_col2.write("**Giờ**")
        h_col3.write("**Nội dung**")
        h_col4.write("**Phụ trách**")
        h_col5.write("**Trạng thái**")
        h_col6.write("**Xem Lịch**")
        h_col7.write("**Thao tác**")
        st.divider()

        for idx, row in df_sorted.iterrows():
            c1, c2, c3, c4, c5, c6, c7 = st.columns([1.2, 1, 2.5, 1.5, 1, 1, 1])
            
            c1.write(row["ngay"])
            c2.write(f"{row['gio_bat_dau']} - {row['gio_ket_thuc']}")
            c3.write(row["title"])
            c4.write(row["nguoi_phu_trach"])
            c5.write(row["trang_thai"])

            # NÚT 1: Nhảy sang Lịch Tuần & Highlight đúng lịch
            if c6.button("🎯 Xem", key=f"btn_focus_{row['id']}"):
                st.session_state["selected_task_id"] = row["id"]
                st.session_state["selected_date"] = datetime.strptime(row["ngay"], "%Y-%m-%d").date()
                st.session_state["active_tab"] = "tab1"
                st.rerun()

            # NÚT 2: Sửa trực tiếp ngay trong danh sách chi tiết
            if c7.button("✏️ Sửa", key=f"btn_edit_l_{row['id']}"):
                task_obj = row.to_dict()
                task_real_idx = next(i for i, t in enumerate(schedules_data) if t["id"] == row["id"])
                edit_schedule_dialog(task_real_idx, task_obj, staff_names)
            
            st.markdown("<hr style='margin: 4px 0px; border: 0.5px solid #eee;'>", unsafe_allow_html=True)
    else:
        st.info("Chưa có dữ liệu lịch làm việc.")
