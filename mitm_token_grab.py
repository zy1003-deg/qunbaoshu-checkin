# -*- coding: utf-8 -*-
"""mitmproxy addon: 捕获 form.qun100.com 请求头里的 Authorization token 写入文件。"""

TOKEN_FILE = r"C:\Users\26246\.zcode\workspace\default\qunbaoshu-checkin\fresh_token.txt"


def response(flow):
    try:
        if "qun100.com" not in flow.request.pretty_host:
            return
        tok = flow.request.headers.get("authorization", "")
        if len(tok) > 30 and " " not in tok:
            with open(TOKEN_FILE, "w") as f:
                f.write(tok)
    except Exception:
        pass
