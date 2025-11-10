import streamlit as st
import pandas as pd
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== 新增：Google Sheets =====
import gspread
from google.oauth2.service_account import Credentials

# ---------------- 页面配置 ----------------
st.set_page_config(page_title="BMRQ 音乐奖赏问卷", layout="centered")
st.title("🎵 BMRQ 音乐奖赏敏感性问卷")
st.write("请对每个陈述选择您同意程度（1=完全不同意，5=完全同意）。提交后会显示总分与判定结果，并自动将结果保存。")


# ---------------- Google Sheets 工具 ----------------
def get_gsheet_client():
    """
    读取 st.secrets 中的 Google Service Account 信息并返回 gspread 客户端。
    如果未配置（本地调试），返回 None。
    """
    try:
        sa_info = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception:
        return None


def get_or_create_worksheet(client, sheet_key, ws_title="BMRQ_Responses"):
    """
    打开（或创建）工作表，并确保表头存在。
    返回 worksheet 对象。
    """
    sh = client.open_by_key(sheet_key)
    try:
        ws = sh.worksheet(ws_title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=ws_title, rows=2000, cols=40)

    # 表头
    header = (
        ["timestamp", "sid", "subject_code", "name"]
        + [f"Q{i}" for i in range(1, 21)]
        + ["total"]
    )
    values = ws.get_all_values()
    if not values:
        ws.append_row(header)
    else:
        # 若首行不是表头则补齐
        if values[0][:len(header)] != header:
            ws.insert_row(header, 1)
    return ws


def get_next_sid_from_sheet(ws):
    """
    根据 Google Sheet 里已有的响应数，给出下一个被试编号（S001…）。
    规则：现有有效数据行数（去掉表头）+ 1。
    """
    # 只取第1列，减少 IO
    col1 = ws.col_values(1)
    existing = max(0, len(col1) - 1)  # 去掉表头
    return existing + 1


def append_row_to_sheet(ws, row_dict):
    """
    将结果以行的形式写入 Google Sheet。
    row_dict 的列顺序与表头一致。
    """
    ordered = (
        [row_dict["timestamp"], row_dict["sid"], row_dict["subject_code"], row_dict["name"]]
        + [row_dict[f"Q{i}"] for i in range(1, 21)]
        + [row_dict["total"]]
    )
    ws.append_row(ordered, value_input_option="USER_ENTERED")


# ---------------- 邮件发送函数 ----------------
def send_email_notification(name, total):
    """发送问卷结果通知邮件到研究者邮箱（可选）"""
    from_email = "2281273608@qq.com"
    to_email = "2281273608@qq.com"
    password = os.getenv("EMAIL_APP_PASSWORD") or st.secrets.get("EMAIL_APP_PASSWORD")

    if not password:
        st.info("ℹ️ 未配置 EMAIL_APP_PASSWORD，已跳过邮件发送。")
        return

    subject = "🎵 BMRQ问卷结果通知"
    result_text = "✅ 正常 (≥65分)" if total > 65 else "⚠️ 较低 (≤65分)"
    body = (
        f"受试者: {name or '匿名'}\n"
        f"总分: {total}\n"
        f"结果: {result_text}\n\n"
        f"提交时间: {datetime.utcnow().isoformat()}"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
        st.success("📩 邮件已发送到研究者邮箱。")
    except Exception as e:
        st.warning(f"⚠️ 邮件发送失败: {e}")


# ---------------- 被试编号（CSV 兜底） ----------------
def get_next_sid_csv(csv_path="results/bmrq_results.csv"):
    if not os.path.exists(csv_path):
        return 1
    try:
        df = pd.read_csv(csv_path)
        if "sid" in df.columns and pd.api.types.is_numeric_dtype(df["sid"]):
            current_max = int(df["sid"].max()) if len(df) else 0
            return current_max + 1
        else:
            return len(df) + 1
    except Exception:
        return 1


# ---------------- 问卷题目与计分 ----------------
questions = [
    "当我与他人分享音乐时，我会感觉与那个人有一种特别的联系。",
    "在空闲时间我几乎不听音乐。",
    "我喜欢聆听富含情感的音乐。",
    "当我独处时，音乐会陪伴我。",
    "我不喜欢跳舞，即使配上我喜欢的音乐也不喜欢。",
    "音乐让我与他人更加亲近。",
    "我会主动了解我喜欢的音乐资讯。",
    "听到某些音乐作品时我会产生强烈情感。",
    "音乐能让我平静、放松。",
    "音乐经常让我想跳舞。",
    "我总是在寻找新的音乐。",
    "当我听到特别喜欢的旋律时，会眼眶湿润甚至落泪。",
    "我喜欢与他人一起唱歌或合奏。",
    "音乐有助于让我放松解压。",
    "听到喜欢的音乐时我会情不自禁地哼唱或跟唱。",
    "在音乐会中，我会感到与演奏者和观众彼此相连。",
    "我会在音乐及相关物品上花费不少钱。",
    "听到喜欢的旋律时，我有时会起鸡皮疙瘩。",
    "音乐能安慰我。",
    "听到非常喜欢的曲子时，我会情不自禁地随着节拍打拍或摆动。"
]
# 反向计分题（题号从1开始）
reverse_items = {2, 5}
choices = ["完全不同意", "不同意", "不确定", "同意", "完全同意"]

# ---------------- Google Sheet 客户端/表 ----------------
csv_path = "results/bmrq_results.csv"
os.makedirs("results", exist_ok=True)

gs_client = get_gsheet_client()
sheet_key = st.secrets.get("SHEET_KEY")  # 只需填 spreadsheet 的 key
ws = None
if gs_client and sheet_key:
    try:
        ws = get_or_create_worksheet(gs_client, sheet_key, ws_title="BMRQ_Responses")
    except Exception as e:
        st.warning(f"⚠️ 无法连接 Google Sheets：{e}（将写入本地 CSV）")
        ws = None

# 用 Sheet 计数优先，其次用 CSV
if ws:
    next_sid = get_next_sid_from_sheet(ws)
else:
    next_sid = get_next_sid_csv(csv_path)

st.caption(f"📊 已收集：{next_sid - 1} 份 | 本次自动编号：S{next_sid:03d}")

# ---------------- 表单 ----------------
with st.form("bmrq_form", clear_on_submit=False):
    name = st.text_input("您的姓名：")
    responses = []

    for i, q in enumerate(questions):
        box = st.container(border=True)
        with box:
            st.markdown(f"**{i + 1}. {q}**")
            val = st.radio(
                label="",
                options=choices,
                key=f"q{i}",
                index=None,
                label_visibility="collapsed",
            )

        if val:
            score = choices.index(val) + 1
            if (i + 1) in reverse_items:
                score = 6 - score
            responses.append(score)
        else:
            responses.append(None)

    # 美化
    st.markdown("""
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] {
      background-color: #eaf4f8 !important;
      border: 2px solid #225560 !important;
      border-radius: 12px !important;
      padding: 16px 20px !important;
      margin-bottom: 18px !important;
      box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

    submitted = st.form_submit_button("提交问卷并查看结果")

# ---------------- 提交逻辑 ----------------
if submitted:
    if any(v is None for v in responses):
        st.warning("还有题目未作答哦～请完成全部题目再提交。")
    else:
        total = int(sum(responses))
        st.subheader(f"总分：{total} / 100")

        if total > 65:
            st.success("🎉 结果：通过（音乐奖赏敏感性正常）")
        else:
            st.error("⚠️ 结果：分数≤65，提示奖赏敏感性较低")

        assigned_name = name.strip() if name else f"S{next_sid:03d}"
        row = {
            "timestamp": datetime.utcnow().isoformat(),
            "sid": next_sid,
            "subject_code": f"S{next_sid:03d}",
            "name": assigned_name,
            **{f"Q{i + 1}": s for i, s in enumerate(responses)},
            "total": total,
        }

        # 1) 优先写 Google Sheets
        wrote_to_sheet = False
        if ws:
            try:
                append_row_to_sheet(ws, row)
                wrote_to_sheet = True
                st.success("✅ 已保存到 Google Sheets。")
            except Exception as e:
                st.warning(f"⚠️ 写入 Google Sheets 失败：{e}（将写入本地 CSV）")

        # 2) 兜底写 CSV
        if not wrote_to_sheet:
            df = pd.DataFrame([row])
            header = not os.path.exists(csv_path)
            df.to_csv(csv_path, mode="a", header=header, index=False)
            st.success("✅ 已保存到本地 CSV（results/bmrq_results.csv）。")

        # 可选：邮件通知
        send_email_notification(assigned_name, total)
