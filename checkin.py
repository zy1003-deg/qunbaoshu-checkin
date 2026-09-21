# -*- coding: utf-8 -*-
"""群报数「每日签到打卡」自动提交脚本（GitHub Actions / 本地通用）。

流程：
  1. GET /v1/{FORM_ID}/form_data/last —— currNormalSize >= 1 则今天已打卡，成功退出
  2. GET /v1/form/{FORM_ID}/profile —— 取最新 formVersion（老师改表单后版本会涨，必须现拉）
  3. POST /v1/{FORM_ID}/form_data —— 提交姓名(名单) + 是否请假=否 + 定位(固定坐标)
  4. 回查 currNormalSize 确认生效；失败重试 3 次并 PushPlus 推送到微信

提交窗口：每日 20:00–22:30（服务端校验），Actions 定在北京时间 20:10 / 20:40。
"""
import datetime
import json
import os
import sys
import time

import requests

BASE = "https://form.qun100.com"
FORM_ID = "1889970208846901248"

NAME_CID = "1889970209849339904"          # 姓名（名单题，value = "姓名 组号"）
NAME_VALUE = "张江楠202330142156 5"
CHOICE_CID = "1889971696492388352"        # 是否请假
NO_OPTION_CID = "1889971696496582659"     # 选项「否」
LOCATION_CID = "1889971696496582660"      # 当前位置（选「否」后显示）
LOCATION_VALUE = {
    "address": "湖南省长沙市岳麓区西苑路",
    "title": "岳麓区湖南师范大学(桃花坪校区)",
    "location": {"type": "Point", "coordinates": [112.92599690755209, 28.168426649305555]},
    "specifiedAddress": "岳麓区湖南师范大学(桃花坪校区)",
    "setupLongitude": 112.926094,
    "setupLatitude": 28.168562,
    "setupAddress": "",
}
SHOW_QUESTIONS = [NAME_CID, CHOICE_CID, LOCATION_CID]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/144.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) "
        "NetType/WIFI MiniProgramEnv/Windows"
    ),
    "Referer": "https://servicewechat.com/wxfc4ef6d539d03373/346/page-frame.html",
    "Content-Type": "application/json",
}

HERE = os.path.dirname(os.path.abspath(__file__))


def log(msg):
    print(f"[{datetime.datetime.now():%F %T}] {msg}")


def load_token():
    tok = os.environ.get("QBS_TOKEN")
    if tok:
        return tok.strip()
    path = os.path.join(HERE, "secrets.local.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))["qbs_token"].strip()
    raise SystemExit("QBS_TOKEN 未设置（环境变量或 secrets.local.json）")


def api(token):
    h = dict(HEADERS)
    h["Authorization"] = token
    return h


def checked_in_today(token):
    r = requests.get(f"{BASE}/v1/{FORM_ID}/form_data/last", headers=api(token), timeout=20)
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(f"form_data/last 异常: {d}")
    data = d.get("data") or {}
    return (data.get("currNormalSize") or 0) >= 1, data.get("cycleId")


def current_form_version(token):
    r = requests.get(f"{BASE}/v1/form/{FORM_ID}/profile", headers=api(token), timeout=20)
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(f"profile 异常: {d}")
    return d["data"]["version"]


def token_valid(token):
    """token 是否仍有效（用一次只读请求探测）。"""
    try:
        r = requests.get(f"{BASE}/v1/{FORM_ID}/form_data/last",
                         headers=api(token), timeout=20,
                         proxies={"http": None, "https": None})
        return r.status_code == 200 and r.json().get("code") == 0
    except Exception:
        return False


def submit(token):
    version = current_form_version(token)
    body = {
        "fid": "",
        "subscribe": {},
        "catalogs": [
            {"cid": NAME_CID, "type": "WORD", "value": NAME_VALUE},
            {"cid": CHOICE_CID, "type": "CHOICE",
             "value": [{"cid": NO_OPTION_CID, "customValue": ""}]},
            {"cid": LOCATION_CID, "type": "LOCATION", "value": LOCATION_VALUE},
        ],
        "showQuestions": list(SHOW_QUESTIONS),
        "examUsedTime": None,
        "formVersion": version,
    }
    log(f"提交中 (formVersion={version})")
    r = requests.post(f"{BASE}/v1/{FORM_ID}/form_data",
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers=api(token), timeout=20)
    try:
        d = r.json()
    except ValueError:
        raise RuntimeError(f"提交响应非 JSON: HTTP {r.status_code} {r.text[:200]}")
    if d.get("code") != 0:
        # 13396 = 表单被发布人修改(版本变了)；下一轮重拉 version 再试
        raise RuntimeError(f"提交被拒绝: HTTP {r.status_code} "
                           f"code={d.get('code')} {str(d.get('message'))[:150]}")
    log(f"提交成功: {json.dumps(d.get('data') or {}, ensure_ascii=False)[:200]}")
    return d


def notify(title, content):
    """QQ 邮箱 SMTP 推送（给自己发信；未配置则跳过）。"""
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    if not user or not pwd:
        path = os.path.join(HERE, "secrets.local.json")
        if os.path.exists(path):
            d = json.load(open(path, encoding="utf-8"))
            user, pwd = d.get("smtp_user"), d.get("smtp_pass")
    if not user or not pwd:
        print("(未配置 SMTP，跳过推送)")
        return
    import smtplib
    from email.header import Header
    from email.mime.text import MIMEText

    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = user
    msg["To"] = user
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15) as s:
            s.login(user, pwd)
            s.sendmail(user, [user], msg.as_string())
        print(f"已发送提醒邮件到 {user}")
    except Exception as e:
        print(f"邮件发送失败: {e}")


def main():
    token = load_token()
    for attempt in range(1, 4):
        try:
            done, cycle = checked_in_today(token)
            log(f"cycle={cycle} checked_in={done}")
            if done:
                log("今天已完成打卡，跳过提交")
                return 0
            submit(token)
            time.sleep(3)
            done, _ = checked_in_today(token)
            if done:
                log("打卡成功，回查确认 ✓")
                notify("打卡成功（自动提交）",
                       "今天的签到打卡已由脚本自动提交并回查确认。此邮件仅在脚本实际提交的日子发送。")
                return 0
            raise RuntimeError("提交后校验未通过（currNormalSize 仍为 0）")
        except Exception as e:
            log(f"第 {attempt} 次尝试失败: {e}")
            if attempt < 3:
                time.sleep(30)
    notify("打卡失败，请手动补卡", "自动打卡连续 3 次失败（今天 22:30 前务必手动打卡）。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
