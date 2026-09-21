import streamlit as st
import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore
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
# Cấu hình Email SMTP & Firebase Credentials
# ---------------------------------------------------------
SENDER_EMAIL = "traitay95@gmail.com"
SENDER_PASSWORD = "wtgm paga vpze bfzm"

FIREBASE_CREDENTIALS = {
  "type": "service_account",
  "project_id": "lichtuan-2b316",
  "private_key_id": "79ea12471bfabef4ec591741e3042836ad51ac96",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDz5FERafP3/x9c\n0MbX92XgZvffjweTOfCi58x+Y07/e5rvao+Ikm1LauaNrJ3uWWLQX8XJF18BJmBV\nT2uJq58x7q9zQFQoVZbhg7amzPFP+5DFk7UiJkPDPNNejMVotHEuutMLCrTdSfv5\nf8QNI4c/8CtCz6/hIzvJTTZEkMWWGds2Z+kx6JbkO+0Wewvpkq3UUswD6vQS79mN\njz/atpKehQEe6i6qACcNtQZFzn+Aq+rrF18V9KyT/iPts3XGcIw3Bvbzv8kTDsd4\nptBzkgtJGnpFaZBzu5u/1TytXkQMNqK5U9JGewse2VVYVSFXQIN0JbXoqph03yAD\n7IUMbXpHAgMBAAECggEAcu7RVUd89Q2BFhg83GF13P4pKW0ZwMO5JsvdjmH2RGdX\naCPraAy4/KVv6KvD8SKmclPvvQgKeVxAYXN/1ezOpJU6kTFrd2Z+J+AOHyTNQ0fl\nvXYSEfm+TS9I3HGyRdlizQa1laqB+RZ4a+dN2HM5tWPUvzNoSsxzzDVasY0Xz9eL\n8BTcdlm5LcZFdXEpXqbTKoLkdEINw0TGCYyXQryQ+9NS7F92DxIBnO2o1M7y+QCx\nc6qVcPdHtCo3BB7xBle4Phq+7qzbw8owRavWj0r5P0FxcRRsTgLSzf/CTMbHEVk/\nFu+eD58/Gkmsk+rfXKaLmGRbn8HB2Q8o0tfq+XChwQKBgQD+KYgI0lRJcCuMvFoN\nTyhIl2u7VYOLGfsY7igPm2GYN/+uO54Da5FHeK0LRN4JDEZGB6VTvNAxD4IDWwuW\n/x8Mp+0tVMNyXn4FE4o0hT/sauJsdjZv5kAo/RlO1V/2YJvwxt7/Zh0MDT9Kme74\nv3wwB7NCGXSp9tym/2mSEzQeyQKBgQD1p8Y1ff+qqPPvQhobndQ/oKcl+YPw3oro\nF7SiivaEoD5QNGlLDY9k4SGHiGr6JunZ5wasykQTLd1ZLzyiF4RwKMnnyBFwZWe2\nGFqcCaD+uJjuUrck6LxUFZIM1yfRAGHlChuGhhJYHSq2YX/k00RGK36FahsHTY9W\nni9Y0YoIjwKBgAJaoh7qy8sOVejsyay74fSiKmZGyXwdVn0Jn6ddWg8N3blgZftE\nIMlXrcqf7aqJyZDWe0qGQitiKGMdkcLpRAFbANBdq53AkEw9vRb1cP0glE5K3gA1\nUrzOc1COm1/tzyPww5n7+SLmcIKhYFw/ccgEGj3vfGwilDKbxP+MW/w5AoGBANA7\nXG/Bk3QVbVlVng3k1qLsymMNQ8Ns0TB1z7+srdS0hL21/78ICpIHqEVb5NqRG8+C\n3wyfE99yFFxiBzKbXr84RBX+aJHu01/u+vejzd29mp0Cbo6R3fokor3Rr8WhXlop\nHDYG9gvNBYS91wyf7RLSEZiD3c9t9mAFDLtsO2aPAoGBAKKAUbKzQrjkU44nskWG\nZeLQc/oD3u81vIuZGeaFQ6QUuh6L1AT7Qnchtk/rOPwmL9InezM2zN+l3Ud3RuzA\njFrSl8bBXnhBL776Ixt1W4T0HND/y2c9m6YcEDPFeABkAqVfSK8yg8sifPvthA8C\nlGVpZs3EIF/onAHG7uM8D38i\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-fbsvc@lichtuan-2b316.iam.gserviceaccount.com",
  "client_id": "112928288504526035507",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40lichtuan-2b316.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

# ---------------------------------------------------------
# 2. Khởi tạo Firestore bằng REST Transport (Khắc phục treo Streamlit Cloud)
# ---------------------------------------------------------
@st.cache_resource
from google.oauth2 import service_account

# ---------------------------------------------------------
# 2. Khởi tạo Firestore bằng REST Transport (Sửa lỗi TypeError)
# ---------------------------------------------------------
@st.cache_resource
def init_firestore():
    cred_dict = dict(FIREBASE_CREDENTIALS)
    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
    
    # 1. Khởi tạo Firebase Admin SDK (nếu chưa khởi tạo)
    if not firebase_admin._apps:
        cred_admin = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred_admin)
    
    # 2. Khởi tạo Google Cloud Service Account Credentials chuẩn cho Firestore Client
    scoped_credentials = service_account.Credentials.from_service_account_info(cred_dict)
    
    # 3. Ép dùng transport='rest' để tránh kẹt socket/gRPC trên Streamlit Cloud
    return firestore.Client(
        project=cred_dict["project_id"],
        credentials=scoped_credentials,
        transport="rest"
    )

db = init_firestore()

# ---------------------------------------------------------
# 3. Các hàm lấy dữ liệu An Toàn (Timeout 10s)
# ---------------------------------------------------------
@st.cache_data(ttl=30, show_spinner=False)
def fetch_schedules():
    try:
        query = db.collection("schedules").order_by("gio_bat_dau", direction=firestore.Query.ASCENDING)
        docs = query.get(timeout=10)
        list_schedules = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            list_schedules.append(d)
        return list_schedules
    except Exception as e:
        print(f"[ERROR] Fetch schedules failed: {e}")
        return []

@st.cache_data(ttl=30, show_spinner=False)
def fetch_staffs():
    try:
        query = db.collection("staffs").order_by("name", direction=firestore.Query.ASCENDING)
        docs = query.get(timeout=10)
        staffs = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            staffs.append(d)
        return staffs
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

        # Đọc trực tiếp Firestore bằng REST, không qua Streamlit Cache
        docs = db.collection("schedules").where("email_sent", "==", False).get(timeout=10)
        staff_docs = db.collection("staffs").get(timeout=10)
        
        staffs_dict = {}
        for s in staff_docs:
            sd = s.to_dict()
            if "name" in sd and "email" in sd:
                staffs_dict[sd["name"]] = sd["email"]

        for doc in docs:
            data = doc.to_dict()
            try:
                task_datetime_str = f"{data['ngay']} {data['gio_bat_dau']}"
                task_datetime = datetime.strptime(task_datetime_str, "%Y-%m-%d %H:%M")

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
                            db.collection("schedules").document(doc.id).update({"email_sent": True})
            except Exception as ex:
                print(f"[ERROR] Lỗi xử lý item {doc.id}: {ex}")
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
                "gio_bat_dau": gio_bat_dau.strftime("%H:%M"),
                "gio_ket_thuc": gio_ket_thuc.strftime("%H:%M"),
                "ghi_chu": ghi_chu,
                "trang_thai": trang_thai,
                "email_sent": False,
                "created_at": datetime.now()
            }
            db.collection("schedules").add(data)
            st.cache_data.clear()
            st.sidebar.success("Đã thêm lịch hẹn thành công!")
            st.rerun()

# Lấy dữ liệu Lịch hẹn đã Cache
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
                day_tasks = df_all[df_all["ngay"] == day_str]
                if not day_tasks.empty:
                    for _, task in day_tasks.iterrows():
                        badge = "🔴" if task['trang_thai'] == 'Hủy' else ("🟢" if task['trang_thai'] == 'Chính thức' else "🟡")
                        with st.container(border=True):
                            st.markdown(f"⏰ **{task['gio_bat_dau']} - {task['gio_ket_thuc']}**")
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
                format_func=lambda x: f"[{x['ngay']} | {x['gio_bat_dau']}] {x['title']} - ({x['nguoi_phu_trach']})"
            )
        with col_act:
            st.write(" ")
            st.write(" ")
            if st.button("🗑️ Xóa lịch hẹn", type="primary"):
                db.collection("schedules").document(selected_task["id"]).delete()
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
                        "phone": staff_phone,
                        "created_at": datetime.now()
                    }
                    db.collection("staffs").add(staff_data)
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
                    db.collection("staffs").document(selected_staff_del["id"]).delete()
                    st.cache_data.clear()
                    st.toast(f"Đã xóa: {selected_staff_del['name']}")
                    st.rerun()
        else:
            st.info("Chưa có thông tin người phụ trách nào.")
