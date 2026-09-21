import streamlit as st
from supabase import create_client, Client
from datetime import datetime, time, timedelta
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler

# ---------------------------------------------------------
# 1. Cấu hình trang Streamlit (BẮT BUỘC ĐẶT ĐẦU TIÊN)
# ---------------------------------------------------------
st.set_page_config(page_title="Hệ Thống Lịch Phòng Kế Hoạch", layout="wide", page_icon="📅")

# ---------------------------------------------------------
# Cấu hình Supabase & SMTP Email
# ---------------------------------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://rsxjvquijelfylkevgwt.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzeGp2cXVpamVsZnlsa2V2Z3d0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4OTk4NTAyNSwiZXhwIjoyMTA1NTYxMDI1fQ.MAQXQnW7FtyixOSE2mtMtSMOA_RMwGvPzs4YcsvQohQ")

SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "traitay95@gmail.com")
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", "wtgm paga vpze bfzm")

# ---------------------------------------------------------
# 2. Khởi tạo kết nối Supabase
# ---------------------------------------------------------
@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# ---------------------------------------------------------
# 3. Các hàm lấy dữ liệu An Toàn
# ---------------------------------------------------------
@st.cache_data(ttl=30, show_spinner=False)
def fetch_schedules():
    try:
        response = supabase.table("schedules").select("*").order("gio_bat_dau", desc=False).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[ERROR] Fetch schedules failed: {e}")
        return []

@st.cache_data(ttl=30, show_spinner=False)
def fetch_staffs():
    try:
        response = supabase.table("staffs").select("*").order("name", desc=False).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[ERROR] Fetch staffs failed: {e}")
        return []

# ---------------------------------------------------------
# 4. Gửi Email thông báo qua SMTP
# ---------------------------------------------------------
def send_email_reminder(to_email, staff_name, task_title, task_time_str, note):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Hệ thống Lịch PKH <{SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = f"⏰ [NHẮC LỊCH] Công việc sắp diễn ra trong 2 tiếng: {task_title}"

        body = f"""Chào {staff_name},

Hệ thống xin thông báo bạn có lịch công tác/cuộc họp sắp diễn ra trong 2 tiếng tới:

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
        print(f"[ERROR] Gửi email thất bại: {e}")
        return False

# ---------------------------------------------------------
# 5. Background Task: Quét lịch & Nhắc nhở Email
# ---------------------------------------------------------
def check_and_send_reminders():
    try:
        now = datetime.now()
        two_hours_later = now + timedelta(hours=2)

        schedules_res = supabase.table("schedules").select("*").eq("email_sent", False).execute()
        staffs_res = supabase.table("staffs").select("*").execute()

        staffs_dict = {s["name"]: s["email"] for s in staffs_res.data if "name" in s and "email" in s}

        for data in schedules_res.data:
            try:
                task_datetime_str = f"{data['ngay']} {data['gio_bat_dau']}"
                task_datetime = datetime.strptime(task_datetime_str, "%Y-%m-%d %H:%M:%S" if len(str(data['gio_bat_dau'])) == 8 else "%Y-%m-%d %H:%M")

                if now <= task_datetime <= two_hours_later:
                    staff_name = data.get("nguoi_phu_trach")
                    user_email = staffs_dict.get(staff_name)

                    if user_email:
                        success = send_email_reminder(
                            to_email=user_email,
                            staff_name=staff_name,
                            task_title=data.get("title"),
                            task_time_str=f"{data['gio_bat_dau']} ngày {data['ngay']}",
                            note=data.get("ghi_chu", "")
                        )

                        if success:
                            supabase.table("schedules").update({"email_sent": True}).eq("id", data["id"]).execute()
            except Exception as ex:
                print(f"[ERROR] Lỗi xử lý item {data.get('id')}: {ex}")
    except Exception as e:
        print(f"[ERROR] Background Task Error: {e}")

@st.cache_resource
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_send_reminders, 'interval', minutes=5)
    scheduler.start()
    return scheduler

scheduler = start_scheduler()

# ---------------------------------------------------------
# 6. Giao Diện Chính Application
# ---------------------------------------------------------
st.title("📅 Quản Lý & Sắp Lịch Làm Việc - Phòng Kế Hoạch")

list_staffs = fetch_staffs()
staff_names = [s["name"] for s in list_staffs if "name" in s]

# Pop-up Chỉnh sửa Lịch
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
            curr_date = datetime.strptime(str(task.get("ngay")), "%Y-%m-%d").date()
        except Exception:
            curr_date = datetime.now().date()

        try:
            t_start_str = str(task.get("gio_bat_dau"))[:5]
            t_end_str = str(task.get("gio_ket_thuc"))[:5]
            curr_start = datetime.strptime(t_start_str, "%H:%M").time()
            curr_end = datetime.strptime(t_end_str, "%H:%M").time()
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
                    "gio_bat_dau": edit_gio_bat_dau.strftime("%H:%M:%S"), # Định dạng chuẩn ISO 8601
                    "gio_ket_thuc": edit_gio_ket_thuc.strftime("%H:%M:%S"), # Định dạng chuẩn ISO 8601
                    "ghi_chu": edit_ghi_chu,
                    "trang_thai": edit_trang_thai,
                    "email_sent": False
                }
                supabase.table("schedules").update(updated_data).eq("id", task["id"]).execute()
                st.cache_data.clear()
                st.success("Đã cập nhật lịch thành công!")
                st.rerun()

# Sidebar Form Đăng ký
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
            data = {
                "title": title,
                "nguoi_phu_trach": nguoi_phu_trach,
                "ngay": ngay_lam.strftime("%Y-%m-%d"),
                "gio_bat_dau": gio_bat_dau.strftime("%H:%M:%S"), # Định dạng chuẩn ISO 8601
                "gio_ket_thuc": gio_ket_thuc.strftime("%H:%M:%S"), # Định dạng chuẩn ISO 8601
                "ghi_chu": ghi_chu,
                "trang_thai": trang_thai,
                "email_sent": False
            }
            supabase.table("schedules").insert(data).execute()
            st.cache_data.clear()
            st.sidebar.success("Đã thêm lịch hẹn thành công!")
            st.rerun()

# Lấy dữ liệu Lịch hẹn
list_schedules = fetch_schedules()
df_all = pd.DataFrame(list_schedules) if list_schedules else pd.DataFrame()

# Tabs giao diện
tab1, tab2, tab3 = st.tabs([
    "📆 Bảng Lịch Theo Tuần",
    "📋 Danh Sách Chi Tiết & Quản Lý",
    "⚙️ Cài Đặt Người Phụ Trách"
])

# TAB 1: BẢNG LỊCH THEO TUẦN
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
                df_all['ngay_str'] = df_all['ngay'].astype(str)
                day_tasks = df_all[df_all["ngay_str"] == day_str]
                if not day_tasks.empty:
                    for _, task in day_tasks.iterrows():
                        badge = "🔴" if task['trang_thai'] == 'Hủy' else ("🟢" if task['trang_thai'] == 'Chính thức' else "🟡")
                        with st.container(border=True):
                            st.markdown(f"⏰ **{str(task['gio_bat_dau'])[:5]} - {str(task['gio_ket_thuc'])[:5]}**")
                            st.markdown(f"**{task['title']}**")
                            st.caption(f"👤 {task['nguoi_phu_trach']}")
                            st.caption(f"Trạng thái: {badge} {task['trang_thai']}")

                            if task.get('ghi_chu'):
                                st.caption(f"📌 {task['ghi_chu']}")

                            if st.button("✏️ Sửa", key=f"btn_edit_{task['id']}"):
                                edit_schedule_dialog(task, staff_names)
                else:
                    st.caption("_Không có lịch_")
            else:
                st.caption("_Không có lịch_")

# TAB 2: DANH SÁCH CHI TIẾT
with tab2:
    if not df_all.empty:
        df_sorted = df_all.sort_values(by=["ngay", "gio_bat_dau"], ascending=[False, False]).copy()
        df_display = df_sorted[["ngay", "gio_bat_dau", "gio_ket_thuc", "title", "nguoi_phu_trach", "trang_thai", "ghi_chu"]].copy()
        df_display.columns = ["Ngày", "Từ", "Đến", "Tên công việc", "Phụ trách", "Trạng thái", "Ghi chú"]

        def colorize_rows(row):
            try:
                task_dt = datetime.strptime(f"{row['Ngày']} {str(row['Từ'])[:5]}", "%Y-%m-%d %H:%M")
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
                format_func=lambda x: f"[{x['ngay']} | {str(x['gio_bat_dau'])[:5]}] {x['title']} - ({x['nguoi_phu_trach']})"
            )
        with col_act:
            st.write(" ")
            st.write(" ")
            if st.button("🗑️ Xóa lịch hẹn", type="primary"):
                supabase.table("schedules").delete().eq("id", selected_task["id"]).execute()
                st.cache_data.clear()
                st.toast(f"Đã xóa thành công lịch: {selected_task['title']}")
                st.rerun()
    else:
        st.info("Chưa có dữ liệu lịch hẹn.")

# TAB 3: QUẢN LÝ NGƯỜI PHỤ TRÁCH
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
                        "phone": staff_phone
                    }
                    supabase.table("staffs").insert(staff_data).execute()
                    st.cache_data.clear()
                    st.success(f"Đã thêm người phụ trách: {staff_name}")
                    st.rerun()

    with col_list:
        st.markdown("##### 📜 Danh Sách Người Phụ Trách Hiện Tại")
        staffs_full = list_staffs

        if staffs_full:
            df_staffs = pd.DataFrame(staffs_full)
            df_staffs_display = df_staffs[["name", "position", "email", "phone"]].copy()
            df_staffs_display.columns = ["Họ và Tên", "Chức vụ", "Email", "Số điện thoại"]

            st.dataframe(df_staffs_display, use_container_width=True)
            st.divider()

            col_s_del, col_b_del = st.columns([2, 1])
            with col_s_del:
                selected_staff_del = st.selectbox(
                    "Chọn người phụ trách cần xóa:",
                    options=staffs_full,
                    format_func=lambda x: f"{x['name']} ({x.get('position', 'N/A')})"
                )
            with col_b_del:
                st.write(" ")
                st.write(" ")
                if st.button("🗑️ Xóa người phụ trách", type="primary"):
                    supabase.table("staffs").delete().eq("id", selected_staff_del["id"]).execute()
                    st.cache_data.clear()
                    st.toast(f"Đã xóa: {selected_staff_del['name']}")
                    st.rerun()
        else:
            st.info("Chưa có thông tin người phụ trách nào.")
