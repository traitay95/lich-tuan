import json
import base64
import requests
import smtplib
import pandas as pd
import streamlit as st
from datetime import datetime, time, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================================================
# ⚙️ CẤU HÌNH CƠ BẢN & MÚI GIỜ
# =========================================================
# Định nghĩa múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

GITHUB_USER = st.secrets.get("GITHUB_USER", "traitay95")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "lich-tuan")
BRANCH = st.secrets.get("BRANCH", "main")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "")
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", "")

# =========================================================
# 🛠️ CÁC HÀM TƯƠNG TÁC GITHUB REST API
# =========================================================
BASE_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def load_data_from_github(filename, default_data):
    """Đọc file JSON từ GitHub."""
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
        else:
            st.error(f"Lỗi đọc {filename} ({res.status_code}): {res.text}")
    except Exception as e:
        st.error(f"Lỗi kết nối GitHub khi đọc dữ liệu: {e}")
    return default_data, None

def save_data_to_github(filename, data, sha=None, commit_msg="Update data"):
    """Ghi dữ liệu lên GitHub Repo."""
    url = f"{BASE_URL}/{filename}"
    content_str = json.dumps(data, ensure_ascii=False, indent=2)
    encoded_content = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": commit_msg,
        "content": encoded_content,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha
        
    try:
        res = requests.put(url, json=payload, headers=HEADERS, timeout=5)
        if res.status_code in [200, 201]:
            st.cache_data.clear()
            return True
        else:
            st.error(f"Lỗi ghi dữ liệu ({res.status_code}): {res.text}")
    except Exception as e:
        st.error(f"Lỗi kết nối GitHub: {e}")
    return False

# =========================================================
# 🧹 HÀM TỰ ĐỘNG XÓA LỊCH THÁNG TRƯỚC
# =========================================================
def auto_clean_old_schedules(schedules, sha):
    """Tự động loại bỏ các lịch từ tháng trước trở về trước."""
    now = datetime.now(VN_TZ).replace(tzinfo=None)
    first_day_of_current_month = datetime(now.year, now.month, 1).date()
    
    cleaned_schedules = []
    has_changed = False

    for task in schedules:
        try:
            task_date = datetime.strptime(task["ngay"], "%Y-%m-%d").date()
            if task_date >= first_day_of_current_month:
                cleaned_schedules.append(task)
            else:
                has_changed = True
        except Exception:
            cleaned_schedules.append(task)

    if has_changed:
        save_data_to_github("schedules.json", cleaned_schedules, sha, "Auto clean old schedules from last month")
        return cleaned_schedules
    return schedules

# =========================================================
# 🔄 TẢI VÀ TỰ ĐỘNG DỌN DẸP DỮ LIỆU
# =========================================================
schedules_data, schedules_sha = load_data_from_github("schedules.json", [])
staffs_data, staffs_sha = load_data_from_github("staffs.json", [])

schedules_data = auto_clean_old_schedules(schedules_data, schedules_sha)
staff_names = [s["name"] for s in staffs_data if "name" in s]

# =========================================================
# 🎨 HÀM XÁC ĐỊNH MÀU SẮC THEO THỜI GIAN CÒN LẠI
# =========================================================
def get_task_highlight_status(task_date_str, task_time_str, task_status=""):
    """
    Trả về màu sắc và thông báo dựa trên thời gian còn lại (chuẩn múi giờ Việt Nam UTC+7):
    - Đỏ: Còn từ 0 đến 2 tiếng (chưa hoàn thành / hủy)
    - Vàng: Còn từ 2 đến 24 tiếng
    """
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
# 🖥️ GIAO DIỆN STREAMLIT
# =========================================================
st.set_page_config(page_title="Lịch Làm Việc Phòng Kế Hoạch", layout="wide", page_icon="📅")
st.title("📅 Quản Lý Lịch Làm Việc - Phòng Kế Hoạch")

# --- POP-UP CHỈNH SỬA ---
@st.dialog("✏️ Chỉnh Sửa Lịch Làm Việc")
def edit_schedule_dialog(task_idx, task, staff_options):
    with st.form("form_edit_schedule"):
        edit_title = st.text_input("Nội dung công việc / Cuộc họp (*)", value=task.get("title", ""))
        
        if staff_options:
            default_index = staff_options.index(task.get("nguoi_phu_trach")) if task.get("nguoi_phu_trach") in staff_options else 0
            edit_nguoi_phu_trach = st.selectbox("Người phụ trách (*)", options=staff_options, index=default_index)
        else:
            edit_nguoi_phu_trach = st.text_input("Người phụ trách (*)", value=task.get("nguoi_phu_trach", ""))

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

        edit_ghi_chu = st.text_area("Địa điểm / Ghi chú / Thành phần", value=task.get("ghi_chu", ""))

        status_list = ["Dự kiến", "Chính thức", "Hoàn thành", "Hủy"]
        curr_status_idx = status_list.index(task.get("trang_thai")) if task.get("trang_thai") in status_list else 0
        edit_trang_thai = st.selectbox("Trạng thái", status_list, index=curr_status_idx)

        btn_update = st.form_submit_button("💾 Cập Nhật Lịch Hẹn")

        if btn_update:
            if not edit_title or not edit_nguoi_phu_trach:
                st.error("Vui lòng điền nội dung và người phụ trách!")
            elif edit_gio_bat_dau >= edit_gio_ket_thuc:
                st.error("Giờ kết thúc phải sau giờ bắt đầu!")
            else:
                schedules_data[task_idx] = {
                    "id": task["id"],
                    "title": edit_title,
                    "nguoi_phu_trach": edit_nguoi_phu_trach,
                    "ngay": edit_ngay_lam.strftime("%Y-%m-%d"),
                    "gio_bat_dau": edit_gio_bat_dau.strftime("%H:%M"),
                    "gio_ket_thuc": edit_gio_ket_thuc.strftime("%H:%M"),
                    "ghi_chu": edit_ghi_chu,
                    "trang_thai": edit_trang_thai,
                    "email_sent": False
                }
                if save_data_to_github("schedules.json", schedules_data, schedules_sha, f"Update task {task['id']}"):
                    st.success("Đã cập nhật lịch thành công!")
                    st.rerun()

# --- SIDEBAR THÊM LỊCH ---
st.sidebar.header("📝 Đăng ký lịch làm việc")
with st.sidebar.form("form_dangkylich", clear_on_submit=True):
    title = st.text_input("Nội dung công việc / Cuộc họp (*)")
    
    if staff_names:
        nguoi_phu_trach = st.selectbox("Người phụ trách (*)", options=staff_names)
    else:
        nguoi_phu_trach = st.text_input("Người phụ trách (*)")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        ngay_lam = st.date_input("Ngày thực hiện", datetime.now(VN_TZ).date())
    with col_d2:
        gio_bat_dau = st.time_input("Giờ bắt đầu", time(8, 0))
        gio_ket_thuc = st.time_input("Giờ kết thúc", time(9, 0))

    ghi_chu = st.text_area("Địa điểm / Ghi chú / Thành phần")
    trang_thai = st.selectbox("Trạng thái", ["Dự kiến", "Chính thức", "Hoàn thành", "Hủy"])

    submitted = st.form_submit_button("💾 Lưu Lịch Hẹn")

    if submitted:
        if not title or not nguoi_phu_trach:
            st.sidebar.error("Vui lòng điền nội dung và người phụ trách!")
        elif gio_bat_dau >= gio_ket_thuc:
            st.sidebar.error("Giờ kết thúc phải sau giờ bắt đầu!")
        else:
            new_task = {
                "id": f"task_{int(datetime.now().timestamp())}",
                "title": title,
                "nguoi_phu_trach": nguoi_phu_trach,
                "ngay": ngay_lam.strftime("%Y-%m-%d"),
                "gio_bat_dau": gio_bat_dau.strftime("%H:%M"),
                "gio_ket_thuc": gio_ket_thuc.strftime("%H:%M"),
                "ghi_chu": ghi_chu,
                "trang_thai": trang_thai,
                "email_sent": False
            }
            schedules_data.append(new_task)
            if save_data_to_github("schedules.json", schedules_data, schedules_sha, f"Add task {new_task['id']}"):
                st.sidebar.success("Thêm lịch thành công!")
                st.rerun()

# --- TAB GIAO DIỆN CHÍNH ---
tab1, tab2, tab3 = st.tabs(["📆 Lịch Theo Tuần", "📋 Danh Sách Chi Tiết", "⚙️ Cài Đặt Nhân Sự"])

with tab1:
    col_w1, col_w2 = st.columns([1, 2])
    with col_w1:
        picked_date = st.date_input("🗓️ Chọn ngày xem lịch:", value=datetime.now(VN_TZ).date())
        start_of_week = picked_date - timedelta(days=picked_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        st.info(f"📌 **Tuần:** {start_of_week.strftime('%d/%m/%Y')} - {end_of_week.strftime('%d/%m/%Y')}")

    week_days = [start_of_week + timedelta(days=i) for i in range(7)]
    day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    cols = st.columns(7)

    today_date = datetime.now(VN_TZ).date()

    for i, col in enumerate(cols):
        current_day = week_days[i]
        day_str = current_day.strftime("%Y-%m-%d")
        with col:
            st.markdown(f"### {'🔵' if current_day == today_date else '🗓️'} {day_names[i]}")
            st.caption(current_day.strftime("%d/%m/%Y"))
            st.divider()

            day_tasks = [t for t in schedules_data if t.get("ngay") == day_str]
            day_tasks = sorted(day_tasks, key=lambda x: x.get("gio_bat_dau", ""))

            if day_tasks:
                for task in day_tasks:
                    bg_color, text_color, badge = get_task_highlight_status(
                        task.get("ngay"),
                        task.get("gio_bat_dau"),
                        task.get("trang_thai")
                    )
                    
                    if bg_color:
                        st.markdown(
                            f"""
                            <div style="background-color: {bg_color}; color: {text_color}; padding: 8px; border-radius: 6px; margin-bottom: 8px; border: 1px solid {text_color};">
                                <b>{badge}</b><br>
                                ⏰ <b>{task['gio_bat_dau']} - {task['gio_ket_thuc']}</b><br>
                                <b>{task['title']}</b><br>
                                👤 <small>{task['nguoi_phu_trach']}</small>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                    else:
                        with st.container(border=True):
                            st.markdown(f"⏰ **{task['gio_bat_dau']} - {task['gio_ket_thuc']}**")
                            st.markdown(f"**{task['title']}**")
                            st.caption(f"👤 {task['nguoi_phu_trach']}")
                    
                    if st.button("✏️ Sửa", key=f"btn_edit_t1_{task['id']}"):
                        edit_schedule_dialog(schedules_data.index(task), task, staff_names)
            else:
                st.caption("_Không có lịch_")

with tab2:
    st.subheader("📋 Danh Sách Lịch Chi Tiết")
    st.markdown("**Chú thích cảnh báo:** 🔴 *Còn < 2 tiếng* | 🟡 *Còn < 24 tiếng*")

    if schedules_data:
        # Sắp xếp lịch mới nhất lên đầu
        sorted_schedules = sorted(schedules_data, key=lambda x: (x.get("ngay", ""), x.get("gio_bat_dau", "")), reverse=True)

        # Tiêu đề bảng
        h1, h2, h3, h4, h5, h6, h7 = st.columns([1.2, 1.2, 2.5, 1.5, 1.2, 1.8, 1.2])
        h1.write("**Ngày**")
        h2.write("**Thời gian**")
        h3.write("**Nội dung**")
        h4.write("**Phụ trách**")
        h5.write("**Trạng thái**")
        h6.write("**Ghi chú**")
        h7.write("**Thao tác**")
        st.divider()

        # Hiển thị từng dòng cùng với Nút Sửa & Xóa
        for task in sorted_schedules:
            c1, c2, c3, c4, c5, c6, c7 = st.columns([1.2, 1.2, 2.5, 1.5, 1.2, 1.8, 1.2])
            
            # Tính màu tô nổi bật nếu sắp tới giờ
            bg_color, text_color, badge = get_task_highlight_status(
                task.get("ngay"), task.get("gio_bat_dau"), task.get("trang_thai")
            )

            c1.write(task.get("ngay", ""))
            c2.write(f"{task.get('gio_bat_dau', '')} - {task.get('gio_ket_thuc', '')}")
            
            # Nếu còn ít thời gian thì gắn badge màu đỏ/vàng
            title_text = f"{badge} {task.get('title', '')}" if badge else task.get("title", "")
            c3.write(title_text)
            c4.write(task.get("nguoi_phu_trach", ""))
            c5.write(task.get("trang_thai", ""))
            c6.write(task.get("ghi_chu", ""))

            # Cột Thao tác chứa Nút Sửa & Nút Xóa
            with c7:
                col_btn_edit, col_btn_del = st.columns(2)
                
                # NÚT SỬA
                if col_btn_edit.button("✏️", key=f"btn_edit_t2_{task['id']}", help="Chỉnh sửa lịch hẹn"):
                    task_real_idx = schedules_data.index(task)
                    edit_schedule_dialog(task_real_idx, task, staff_names)

                # NÚT XÓA
                if col_btn_del.button("🗑️", key=f"btn_del_t2_{task['id']}", help="Xóa lịch hẹn"):
                    updated_schedules = [t for t in schedules_data if t["id"] != task["id"]]
                    if save_data_to_github("schedules.json", updated_schedules, schedules_sha, f"Delete task {task['id']}"):
                        st.toast("Đã xóa lịch thành công!")
                        st.rerun()

            st.markdown("<hr style='margin: 4px 0px; border: 0.5px solid #eee;'>", unsafe_allow_html=True)
    else:
        st.info("Chưa có lịch hẹn nào.")

with tab3:
    st.subheader("⚙️ Danh Sách Người Phụ Trách")
    col_a, col_l = st.columns([1, 2])
    with col_a:
        with st.form("form_staff"):
            s_name = st.text_input("Họ và Tên (*)")
            s_pos = st.text_input("Chức vụ")
            s_email = st.text_input("Email")
            s_phone = st.text_input("SĐT")
            if st.form_submit_button("💾 Thêm Nhân Sự"):
                if s_name:
                    staffs_data.append({"id": f"s_{int(datetime.now().timestamp())}", "name": s_name, "position": s_pos, "email": s_email, "phone": s_phone})
                    if save_data_to_github("staffs.json", staffs_data, staffs_sha, "Add staff"):
                        st.success("Đã thêm!")
                        st.rerun()
    with col_l:
        if staffs_data:
            st.dataframe(pd.DataFrame(staffs_data)[["name", "position", "email", "phone"]], use_container_width=True)
