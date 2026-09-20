# -*- coding: utf-8 -*-
"""一键刷新群报数 token：
启动 mitmdump -> 开系统代理 -> 等小程序流量里的 Authorization -> 验证 -> gh 更新 secret -> 恢复代理。
配套桌面 bat：打卡token一键刷新.bat（双击运行本文件）。
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import winreg

import requests

BASE = r"C:\Users\26246\.zcode\workspace\default\qunbaoshu-checkin"
TOKEN_FILE = BASE + r"\fresh_token.txt"
ADDON = BASE + r"\mitm_token_grab.py"
REPO = "zy1003-deg/qunbaoshu-checkin"
PROXY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/144.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) "
      "NetType/WIFI MiniProgramEnv/Windows")


def log(msg):
    print(msg, flush=True)


def clash_up(port=7897):
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def read_proxy():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROXY_KEY) as k:
        server = winreg.QueryValueEx(k, "ProxyServer")[0]
        enable = winreg.QueryValueEx(k, "ProxyEnable")[0]
    return server, enable


def write_proxy(server, enable):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROXY_KEY, 0, winreg.SET_VALUE) as k:
        winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ, server)
        winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, enable)
    import ctypes
    internet = ctypes.windll.Wininet
    internet.InternetSetOptionW(0, 39, 0, 0)  # SETTINGS_CHANGED
    internet.InternetSetOptionW(0, 37, 0, 0)  # REFRESH


def validate(token):
    r = requests.get(
        "https://form.qun100.com/v1/1889970208846901248/form_data/last",
        headers={"Authorization": token, "User-Agent": UA},
        timeout=15, verify=True,
        proxies={"http": None, "https": None},
    )
    return r.status_code == 200 and r.json().get("code") == 0


def main():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

    saved_server, saved_enable = read_proxy()
    args = [shutil.which("mitmdump") or "mitmdump", "-p", "8080", "-s", ADDON]
    if clash_up():
        args += ["--mode", "upstream:http://127.0.0.1:7897"]
        log("[*] Clash 在线，抓包流量链式经过 Clash")
    else:
        log("[*] Clash 离线，直连抓包")

    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    write_proxy("127.0.0.1:8080", 1)
    log("[*] 代理已开。现在请：打开电脑微信 -> 打开「群报数」小程序任意页面（打卡页即可）")
    log("[*] 若小程序窗口原本开着，先关掉重新打开。等待捕获 token...")

    token = None
    for _ in range(60):  # 最多等 5 分钟
        time.sleep(5)
        if proc.poll() is not None:
            break
        if os.path.exists(TOKEN_FILE):
            token = open(TOKEN_FILE).read().strip()
            if token:
                break

    write_proxy(saved_server, saved_enable)
    proc.terminate()
    log(f"[*] 代理已恢复为原状（{saved_server}, enable={saved_enable}）")

    if not token:
        log("[!] 5 分钟内没抓到 token。确认微信里真的打开了群报数页面后重试。")
        return 1

    log(f"[*] 捕获到 token: {token[:12]}...，验证中")
    if not validate(token):
        log("[!] token 验证失败（接口未返回成功），请重新打开一次小程序再试。")
        return 1
    log("[*] 验证通过")

    # 更新本地 secrets.local.json
    with open(BASE + r"\secrets.local.json", "w", encoding="utf-8") as f:
        json.dump({"qbs_token": token}, f, ensure_ascii=False, indent=2)

    # 更新 GitHub secret
    gh = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
    r = subprocess.run([gh, "secret", "set", "QBS_TOKEN", "-R", REPO, "--body", token],
                       capture_output=True, text=True)
    if r.returncode != 0:
        log(f"[!] gh 更新 secret 失败: {r.stderr.strip()}")
        log("[!] token 已存本地 fresh_token.txt / secrets.local.json，可手动更新 secret")
        return 1

    log("[OK] token 已验证并同步到 GitHub Secrets，明天 20:00 起自动打卡用新 token。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
