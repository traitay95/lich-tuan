import streamlit as st

# ---------------------------------------------------------
# Cấu hình Trang Streamlit (PHẢI ĐẶT DÒNG ĐẦU TIÊN)
# ---------------------------------------------------------
st.set_page_config(page_title="Hệ Thống Lịch Phòng Kế Hoạch", layout="wide", page_icon="📅")

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, time, timedelta
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# ---------------------------------------------------------
# Cấu hình Email SMTP
# ---------------------------------------------------------
SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "")
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", "")

# ---------------------------------------------------------
# 1. Khởi tạo kết nối Firebase
# ---------------------------------------------------------
if not firebase_admin._apps:
    cred = None
    # Lần lượt kiểm tra các khóa trong Streamlit Secrets
    if "gcp_service_account" in st.secrets:
        key_dict = dict(st.secrets["gcp_service_account"])
        cred = credentials.Certificate(key_dict)
    elif "textkey" in st.secrets:
        key_dict = dict(st.secrets["textkey"])
        cred = credentials.Certificate(key_dict)
    else:
        try:
            cred = credentials.Certificate("firebase_key.json")
        except Exception as e:
            st.error("Không tìm thấy tệp hoặc cấu hình khóa Firebase bí mật!")

    if cred:
        firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------------------------------------------------
# 2. Hàm gửi Email qua SMTP
# ---------------------------------------------------------
def send_email_reminder(to_email, staff_name, task_title, task_time_str, note):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Chưa cấu hình SENDER_EMAIL hoặc SENDER_PASSWORD trong Secrets.")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Hệ thống Lịch PKH <{SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = f"⏰ [NHẮC LỊCH] Công việc sắp diễn ra trong 2 tiếng: {task_title}"

        body = f"""
Chào {staff_name},

Hệ thống xin thông báo bạn có lịch công tác/cuộc họp sắp diễn ra trong 2 tiếng tới:

📌 Nội dung: {task_title}
🕒 Thời gian: {task_time_str}
📝 Ghi chú / Địa điểm: {note if note else 'Không có'}

Vui lòng chuẩn bị và tham gia đúng giờ!
---
Phòng Kế Hoạch
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Lỗi gửi email: {e}")
        return False

# ---------------------------------------------------------
# 3. Task ngầm: Quét Firestore và gửi mail trước 2 tiếng
# ---------------------------------------------------------
def check_and_send_reminders():
    now = datetime.now()
    two_hours_later = now + timedelta(hours=2)

    try:
        schedules_ref = db.collection("schedules").where("email_sent", "==", False)
        docs = schedules_ref.stream()

        staffs_stream = db.collection("staffs").stream()
        staffs_dict = {}
        for s in staffs_stream:
            sd = s.to_dict()
            if "name" in sd and "email" in sd:
                staffs_dict[sd["name"]] = sd["email"]

        for doc in docs:
            data = doc.to_dict()
            try:
                if not data.get('ngay') or not data.get('gio_bat_dau'):
                    continue
                
                task_datetime_str = f"{data['ngay']} {data['gio_bat_dau']}"
                task_datetime = datetime.strptime(task_datetime_str, "%Y-%m-%d %H:%M")

                if now <= task_datetime <= two_hours_later:
                    staff_name = data.get("nguoi_phu_trach")
                    user_email = staffs_dict.get(staff_name)

                    if user_email:
                        success = send_email_reminder(
                            to_email=user_email,
                            staff_name=staff_name,
                            task_title=data.get("title", "Công việc"),
                            task_time_str=f"{data['gio_bat_dau']} ngày {data['ngay']}",
                            note=data.get("ghi_chu", "")
                        )

                        if success:
                            db.collection("schedules").document(doc.id).update({"email_sent": True})
                            print(f"Đã gửi email nhắc lịch cho {staff_name} ({user_email})")
            except Exception as e:
                print(f"Lỗi xử lý lịch {doc.id}: {e}")
    except Exception as ex:
        print(f"Lỗi khi thực hiện quét dữ liệu nhắc lịch: {ex}")

# ---------------------------------------------------------
# 4. Khởi chạy Background Scheduler
# ---------------------------------------------------------
@st.cache_resource
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_send_reminders, 'interval', minutes=5)
    scheduler.start()
    return scheduler

scheduler = start_scheduler()
atexit.register(lambda: scheduler.shutdown(wait=False))

st.title("📅 Quản Lý & Sắp Lịch Làm Việc - Phòng Kế Hoạch")

# ---------------------------------------------------------
# 5. Lấy danh sách Người phụ trách từ Firebase
# ---------------------------------------------------------
staffs_ref = db.collection("staffs").order_by("name", direction=firestore.Query.ASCENDING)
staff_docs = staffs_ref.stream()
list_staffs = [doc.to_dict() for doc in staff_docs]
staff_names = [s["name"] for s in list_staffs if "name" in s]

# ---------------------------------------------------------
# 6. POP-UP CHỈNH SỬA LỊCH HẸN (ST.DIALOG)
# ---------------------------------------------------------
@st.dialog("✏️ Chỉnh Sửa Lịch Làm Việc")
def edit_schedule_dialog(task, staff_options):
    with st.form("form_edit_schedule"):
        edit_title = st.text_input("Nội dung công việc / Cuộc họp (*)", value=task.get("title", ""))

        if staff_options:
            default_index = staff_options.index(task.get("nguoi_phu_trach")) if task.get("nguoi_phu_trach") in staff_options else 0
            edit_nguoi_phu_trach = st.selectbox("Người phụ trách (*)", options=staff_options, index=default_index)
        else:
            edit_nguoi_phu_trach = st.text_input("Người phụ trách (*)", value=task.get("nguoi_phu_trach", ""))

        try:
            curr_date = datetime.strptime(task.get("ngay"), "%Y-%m-%d").date()
        except Exception:
            curr_date = datetime.now().date()

        try:
            curr_start = datetime.strptime(task.get("gio_bat_dau"), "%H:%M").time()
            curr_end = datetime.strptime(task.get("gio_ket_thuc"), "%H:%M").time()
        except Exception:
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
                updated_data = {
                    "title": edit_title,
                    "nguoi_phu_trach": edit_nguoi_phu_trach,
                    "ngay": edit_ngay_lam.strftime("%Y-%m-%d"),
                    "gio_bat_dau": edit_gio_bat_dau.strftime("%H:%M"),
                    "gio_ket_thuc": edit_gio_ket_thuc.strftime("%H:%M"),
                    "ghi_chu": edit_ghi_chu,
                    "trang_thai": edit_trang_thai,
                    "email_sent": False
                }
                db.collection("schedules").document(task["id"]).update(updated_data)
                st.success("Đã cập nhật lịch thành công!")
                st.rerun()

# ---------------------------------------------------------
# 7. Thanh bên (Sidebar) - Form Đăng ký
# ---------------------------------------------------------
st.sidebar.header("📝 Đăng ký lịch làm việc")

with st.sidebar.form("form_dangkylich", clear_on_submit=True):
    title = st.text_input("Nội dung công việc / Cuộc họp (*)")

    if staff_names:
        nguoi_phu_trach = st.selectbox("Người phụ trách (*)", options=staff_names)
    else:
        nguoi_phu_trach = st.text_input("Người phụ trách (*)", help="Chưa có danh sách, nhập tay hoặc sang tab Cài đặt để thêm")

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
            data = {
                "title": title,
                "nguoi_phu_trach": nguoi_phu_trach,
                "ngay": ngay_lam.strftime("%Y-%m-%d"),
                "gio_bat_dau": gio_bat_dau.strftime("%H:%M"),
                "gio_ket_thuc": gio_ket_thuc.strftime("%H:%M"),
                "ghi_chu": ghi_chu,
                "trang_thai": trang_thai,
                "email_sent": False,
                "created_at": firestore.SERVER_TIMESTAMP
            }
            db.collection("schedules").add(data)
            st.sidebar.success("Đã thêm lịch hẹn thành công!")
            st.rerun()

# ---------------------------------------------------------
# 8. Lấy danh sách Lịch làm việc từ Firebase
# ---------------------------------------------------------
schedules_ref = db.collection("schedules").order_by("gio_bat_dau", direction=firestore.Query.ASCENDING)
docs = schedules_ref.stream()

list_schedules = []
for doc in docs:
    d = doc.to_dict()
    d["id"] = doc.id
    list_schedules.append(d)

df_all = pd.DataFrame(list_schedules) if list_schedules else pd.DataFrame()

# ---------------------------------------------------------
# 9. Giao diện chính: Các Tab tính năng
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📆 Bảng Lịch Theo Tuần",
    "📋 Danh Sách Chi Tiết & Quản Lý",
    "⚙️ Cài Đặt Người Phụ Trách"
])

# =========================================================
# TAB 1: BẢNG LỊCH THEO TUẦN
# =========================================================
with tab1:
    col_w1, col_w2 = st.columns([1, 2])

    with col_w1:
        picked_date = st.date_input("🗓️ Chọn ngày bất kỳ để xem lịch tuần:", value=datetime.now().date())

        start_of_week = picked_date - timedelta(days=picked_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        week_num = start_of_week.isocalendar()[1]

        st.info(f"📌 **Tuần {week_num} (Năm {start_of_week.year}):** Từ **{start_of_week.strftime('%d/%m/%Y')}** đến **{end_of_week.strftime('%d/%m/%Y')}**")

    week_days = [start_of_week + timedelta(days=i) for i in range(7)]
    day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]

    cols = st.columns(7)

    for i, col in enumerate(cols):
        current_day = week_days[i]
        day_str = current_day.strftime("%Y-%m-%d")

        with col:
            is_today = current_day == datetime.now().date()
            header_icon = "🔵" if is_today else "🗓️"
            st.markdown(f"### {header_icon} {day_names[i]}")
            st.caption(current_day.strftime("%d/%m/%Y"))
            st.divider()

            if not df_all.empty and "ngay" in df_all.columns:
                day_tasks = df_all[df_all["ngay"] == day_str]

                if not day_tasks.empty:
                    for _, task in day_tasks.iterrows():
                        badge = "🔴" if task.get('trang_thai') == 'Hủy' else (
                            "🟢" if task.get('trang_thai') == 'Chính thức' else "🟡")

                        with st.container(border=True):
                            st.markdown(f"⏰ **{task.get('gio_bat_dau', '')} - {task.get('gio_ket_thuc', '')}**")
                            st.markdown(f"**{task.get('title', '')}**")
                            st.caption(f"👤 {task.get('nguoi_phu_trach', '')}")
                            st.caption(f"Trạng thái: {badge} {task.get('trang_thai', '')}")

                            if task.get('ghi_chu'):
                                st.caption(f"📌 {task['ghi_chu']}")

                            if st.button("✏️ Sửa", key=f"btn_edit_{task['id']}"):
                                edit_schedule_dialog(task, staff_names)
                else:
                    st.caption("_Không có lịch_")
            else:
                st.caption("_Không có lịch_")

# =========================================================
# TAB 2: DANH SÁCH CHI TIẾT
# =========================================================
with tab2:
    if not df_all.empty and "ngay" in df_all.columns:
        df_sorted = df_all.sort_values(by=["ngay", "gio_bat_dau"], ascending=[False, False]).copy()

        # Đảm bảo các cột tồn tại trước khi lọc
        req_cols = ["ngay", "gio_bat_dau", "gio_ket_thuc", "title", "nguoi_phu_trach", "trang_thai", "ghi_chu"]
        for col_name in req_cols:
            if col_name not in df_sorted.columns:
                df_sorted[col_name] = ""

        df_display = df_sorted[req_cols].copy()
        df_display.columns = ["Ngày", "Từ", "Đến", "Tên công việc", "Phụ trách", "Trạng thái", "Ghi chú"]

        def colorize_rows(row):
            try:
                task_dt = datetime.strptime(f"{row['Ngày']} {row['Từ']}", "%Y-%m-%d %H:%M")
                time_diff = task_dt - datetime.now()
                status = row['Trạng thái']

                if timedelta(hours=0) <= time_diff <= timedelta(hours=4) and status != 'Hoàn thành':
                    style_str = 'background-color: #ffcccc; color: #900000; font-weight: bold;'
                elif timedelta(hours=4) < time_diff <= timedelta(hours=24) and status != 'Hoàn thành':
                    style_str = 'background-color: #fff2cc; color: #856404; font-weight: bold;'
                else:
                    style_str = 'background-color: #e6f2ff; color: #004085;'
            except Exception:
                style_str = 'background-color: #e6f2ff; color: #004085;'

            return [style_str] * len(row)

        st.markdown("💡 **Chú thích màu:** <span style='background-color:#ffcccc; color:#900; padding:3px 8px; border-radius:3px; font-weight:bold;'>🔴 Dưới 4h</span> &nbsp; <span style='background-color:#fff2cc; color:#856404; padding:3px 8px; border-radius:3px; font-weight:bold;'>🟡 Dưới 24h</span> &nbsp; <span style='background-color:#e6f2ff; color:#004085; padding:3px 8px; border-radius:3px; font-weight:bold;'>🔵 Bình thường</span>", unsafe_allow_html=True)
        st.write("")

        st.dataframe(df_display.style.apply(colorize_rows, axis=1), use_container_width=True)

        st.divider()
        st.subheader("⚙️ Thao tác xóa / quản lý lịch")

        col_sel, col_act = st.columns([3, 1])
        with col_sel:
            sorted_schedules = df_sorted.to_dict('records')
            selected_task = st.selectbox(
                "Chọn lịch cần xóa:",
                options=sorted_schedules,
                format_func=lambda x: f"[{x.get('ngay', '')} | {x.get('gio_bat_dau', '')}] {x.get('title', '')} - ({x.get('nguoi_phu_trach', '')})"
            )
        with col_act:
            st.write(" ")
            st.write(" ")
            if st.button("🗑️ Xóa lịch hẹn", type="primary"):
                if selected_task:
                    db.collection("schedules").document(selected_task["id"]).delete()
                    st.toast(f"Đã xóa thành công lịch: {selected_task.get('title', '')}")
                    st.rerun()
    else:
        st.info("Chưa có dữ liệu lịch hẹn.")

# =========================================================
# TAB 3: CÀI ĐẶT NGƯỜI PHỤ TRÁCH (STAFF MANAGEMENT)
# =========================================================
with tab3:
    st.subheader("⚙️ Quản Lý Danh Sách Người Phụ Trách")

    col_add, col_list = st.columns([1, 2])

    with col_add:
        st.markdown("##### ➕ Thêm Người Phụ Trách Mới")
        with st.form("form_add_staff", clear_on_submit=True):
            staff_name = st.text_input("Họ và Tên (*)")
            staff_position = st.text_input("Vị trí / Chức vụ")
            staff_email = st.text_input("Email")
            staff_phone = st.text_input("Số điện thoại")

            submit_staff = st.form_submit_button("💾 Lưu Thông Tin")

            if submit_staff:
                if not staff_name:
                    st.error("Vui lòng nhập Họ và Tên!")
                else:
                    staff_data = {
                        "name": staff_name,
                        "position": staff_position,
                        "email": staff_email,
                        "phone": staff_phone,
                        "created_at": firestore.SERVER_TIMESTAMP
                    }
                    db.collection("staffs").add(staff_data)
                    st.success(f"Đã thêm người phụ trách: {staff_name}")
                    st.rerun()

    with col_list:
        st.markdown("##### 📜 Danh Sách Người Phụ Trách Hiện Tại")

        staffs_stream = db.collection("staffs").order_by("name").stream()
        staffs_full = []
        for doc in staffs_stream:
            sd = doc.to_dict()
            sd["id"] = doc.id
            staffs_full.append(sd)

        if staffs_full:
            df_staffs = pd.DataFrame(staffs_full)
            
            # Đảm bảo đủ các cột hiển thị
            for col_name in ["name", "position", "email", "phone"]:
                if col_name not in df_staffs.columns:
                    df_staffs[col_name] = ""

            df_staffs_display = df_staffs[["name", "position", "email", "phone"]].copy()
            df_staffs_display.columns = ["Họ và Tên", "Chức vụ", "Email", "Số điện thoại"]

            st.dataframe(df_staffs_display, use_container_width=True)

            st.divider()
            col_s_del, col_b_del = st.columns([2, 1])
            with col_s_del:
                selected_staff_del = st.selectbox(
                    "Chọn người phụ trách cần xóa:",
                    options=staffs_full,
                    format_func=lambda x: f"{x.get('name', '')} ({x.get('position', 'N/A')})"
                )
            with col_b_del:
                st.write(" ")
                st.write(" ")
                if st.button("🗑️ Xóa người phụ trách", type="primary"):
                    if selected_staff_del:
                        db.collection("staffs").document(selected_staff_del["id"]).delete()
                        st.toast(f"Đã xóa: {selected_staff_del.get('name', '')}")
                        st.rerun()
        else:
            st.info("Chưa có thông tin người phụ trách nào.")
