import streamlit as st
import pandas as pd
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client

# ========== 页面配置 ==========
st.set_page_config(page_title="BMRQ 音乐奖赏问卷", layout="centered")
st.title("🎵 BMRQ 音乐奖赏敏感性问卷")
st.write("请对每个陈述选择您同意程度, 提交后会显示总分与判定结果, 并自动将结果保存到数据库。")

# ========== Supabase 连接 ==========
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== 邮件发送函数 ==========
def send_email_notification(name, total):
    """发送结果通知到研究者邮箱"""
    from_email = "2281273608@qq.com"
    to_email = "2281273608@qq.com"
    password = st.secrets["EMAIL_APP_PASSWORD"]

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
        st.success("📩 邮件通知已发送！")
    except Exception as e:
        st.warning(f"⚠️ 邮件发送失败: {e}")

# ========== 被试编号工具（从 Supabase 或 CSV 获取） ==========
def get_next_sid(table_name="bmrq_results"):
    """根据 Supabase 记录数获取下一个 SID"""
    try:
        data = supabase.table(table_name).select("sid").execute()
        if data.data:
            return max([int(x["sid"]) for x in data.data]) + 1
        else:
            return 1
    except Exception:
        return 1

# ========== 问卷题目 ==========
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
reverse_items = {2, 5}
choices = ["完全不同意", "不同意", "不确定", "同意", "完全同意"]


next_sid = get_next_sid()

st.caption(f"📊 已收集：{next_sid - 1} 份 | 本次编号：S{next_sid:03d}")

with st.form("bmrq_form", clear_on_submit=False):
    name = st.text_input("您的姓名：")
    responses = []

    for i, q in enumerate(questions):
        box = st.container(border=True)
        with box:
            st.markdown(f"**{i + 1}. {q}**")
            val = st.radio("", options=choices, key=f"q{i}", index=None, label_visibility="collapsed")
        if val:
            score = choices.index(val) + 1
            if (i + 1) in reverse_items:
                score = 6 - score
            responses.append(score)
        else:
            responses.append(None)

    submitted = st.form_submit_button("提交问卷并查看结果")

# ========== 结果处理 ==========
if submitted:
    if any(v is None for v in responses):
        st.warning("⚠️ 还有题目未作答，请完成后再提交。")
    else:
        total = int(sum(responses))
        st.subheader(f"总分：{total} / 100")

        if total > 65:
            st.success("🎉 结果：音乐奖赏敏感性正常")
        else:
            st.error("⚠️ 分数 ≤ 65，提示奖赏敏感性较低")

        assigned_name = name.strip() if name else f"S{next_sid:03d}"
        row = {
            "timestamp": datetime.utcnow().isoformat(),
            "sid": next_sid,
            "subject_code": f"S{next_sid:03d}",
            "name": assigned_name,
            "total": total
        }

        # 写入 Supabase

        supabase.table("bmrq_results").insert(row).execute()
        st.success("✅ 数据已保存到 Supabase！")


        # 邮件通知
        send_email_notification(assigned_name, total)
