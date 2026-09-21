import json
import base64
import requests
import smtplib
import pandas as pd
import streamlit as st
from datetime import datetime, time, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================================================
# ⚙️ CẤU HÌNH CÔNG KHAI - KHÔNG CẦN BẢO MẬT
# =========================================================
# Thay 'username' và 'app-lich-pkh' bằng tên GitHub & Repo của bạn
GITHUB_USER = "traitay95"
GITHUB_REPO = "lich-tuan"
BRANCH = "main"

# Cấu hình Email gửi thông báo
SENDER_EMAIL = "traitay95@gmail.com"
SENDER_PASSWORD = "wtgm paga vpze bfzm"

# =========================================================
# 🛠️ CÁC HÀM TƯƠNG TÁC GITHUB REST API (KHÔNG DÙNG TOKEN)
# =========================================================
BASE_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"

def load_data_from_github(filename, default_data):
    """Đọc file JSON công khai từ GitHub."""
    url = f"{BASE_URL}/{filename}?ref={BRANCH}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            content = res.json()
            decoded_bytes = base64.b64decode(content["content"])
            data = json.loads(decoded_bytes.decode('utf-8'))
            return data, content["sha"]
        elif res.status_code == 404:
            # File chưa có -> Khởi tạo
            save_data_to_github(filename, default_data, sha=None, commit_msg=f"Init {filename}")
            return default_data, None
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu từ GitHub: {e}")
    return default_data, None

def save_data_to_github(filename, data, sha=None, commit_msg="Update data"):
    """Ghi dữ liệu thẳng lên GitHub Repo mà không cần bảo mật/token."""
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
        res = requests.put(url, json=payload, timeout=5)
        if res.status_code in [200, 201]:
            st.cache_data.clear()
            return True
        else:
            st.error(f"Lỗi ghi dữ liệu ({res.status_code}): {res.text}")
    except Exception as e:
        st.error(f"Lỗi kết nối GitHub: {e}")
    return False

# Load dữ liệu công khai từ Repo
schedules_data, schedules_sha = load_data_from_github("schedules.json", [])
staffs_data, staffs_sha = load_data_from_github("staffs.json", [])

staff_names = [s["name"] for s in staffs_data if "name" in s]

# =========================================================
# 📧 HÀM GỬI EMAIL
# =========================================================
def send_email_reminder(to_email, staff_name, task_title, task_time_str, note):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Hệ thống Lịch PKH <{SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = f"⏰ [NHẮC LỊCH] Công việc sắp diễn ra: {task_title}"

        body = f"""
        Chào {staff_name},

        Hệ thống xin thông báo bạn có lịch công tác/cuộc họp sắp diễn ra:

        📌 Nội dung: {task_title}
        🕒 Thời gian: {task_time_str}
        📝 Ghi chú / Địa điểm: {note if note else 'Không có'}

        Vui lòng chuẩn bị và tham gia đúng giờ!
        ---
        Phòng Kế Hoạch
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Lỗi gửi email: {e}")
        return False

# =========================================================
# 🖥️ GIAO DIỆN STREAMLIT
# =========================================================
st.set_page_config(page_title="Lịch Làm Việc Phòng Kế Hoạch", layout="wide", page_icon="📅")
st.title("📅 Quản Lý Lịch Làm Việc - Phòng Kế Hoạch")
st.caption(f"🚀 Data trực tiếp từ Repo: `{GITHUB_USER}/{GITHUB_REPO}` (Nhánh `{BRANCH}`)")

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
            curr_date = datetime.now().date()
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
        ngay_lam = st.date_input("Ngày thực hiện", datetime.now())
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
df_all = pd.DataFrame(schedules_data) if schedules_data else pd.DataFrame()
tab1, tab2, tab3 = st.tabs(["📆 Lịch Theo Tuần", "📋 Danh Sách Chi Tiết", "⚙️ Cài Đặt Nhân Sự"])

with tab1:
    col_w1, col_w2 = st.columns([1, 2])
    with col_w1:
        picked_date = st.date_input("🗓️ Chọn ngày xem lịch:", value=datetime.now().date())
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
            st.markdown(f"### {'🔵' if current_day == datetime.now().date() else '🗓️'} {day_names[i]}")
            st.caption(current_day.strftime("%d/%m/%Y"))
            st.divider()

            day_tasks = [t for t in schedules_data if t.get("ngay") == day_str]
            if day_tasks:
                for task in day_tasks:
                    with st.container(border=True):
                        st.markdown(f"⏰ **{task['gio_bat_dau']} - {task['gio_ket_thuc']}**")
                        st.markdown(f"**{task['title']}**")
                        st.caption(f"👤 {task['nguoi_phu_trach']}")
                        if st.button("✏️ Sửa", key=f"btn_edit_{task['id']}"):
                            edit_schedule_dialog(schedules_data.index(task), task, staff_names)
            else:
                st.caption("_Không có lịch_")

with tab2:
    if not df_all.empty:
        df_sorted = df_all.sort_values(by=["ngay", "gio_bat_dau"], ascending=[False, False])
        st.dataframe(df_sorted[["ngay", "gio_bat_dau", "gio_ket_thuc", "title", "nguoi_phu_trach", "trang_thai", "ghi_chu"]], use_container_width=True)
        
        st.divider()
        col_s, col_b = st.columns([3, 1])
        with col_s:
            selected_del = st.selectbox("Chọn lịch để xóa:", options=schedules_data, format_func=lambda x: f"[{x['ngay']}] {x['title']}")
        with col_b:
            st.write(" ")
            st.write(" ")
            if st.button("🗑️ Xóa Lịch", type="primary"):
                updated_schedules = [t for t in schedules_data if t["id"] != selected_del["id"]]
                if save_data_to_github("schedules.json", updated_schedules, schedules_sha, "Delete task"):
                    st.toast("Đã xóa thành công!")
                    st.rerun()
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
