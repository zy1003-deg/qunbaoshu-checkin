# -*- coding: utf-8 -*-
"""Parse mitmproxy capture.flows, list all hosts, and dump qunbaoshu API requests in detail."""
import json
import sys
from collections import Counter

from mitmproxy import io as mio

CAPDIR = r"C:\Users\26246\.zcode\workspace\default\qunbaoshu-checkin"


def body_of(msg):
    if not msg.raw_content:
        return None
    try:
        return msg.get_text(strict=False)
    except Exception:
        return msg.raw_content.decode("utf-8", "replace")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else CAPDIR + r"\capture.flows"
    hosts = Counter()
    out = []
    with open(path, "rb") as f:
        try:
            for fl in mio.FlowReader(f).stream():
                req = getattr(fl, "request", None)
                if req is None:
                    continue
                hosts[req.pretty_host] += 1
                if "qun100" not in req.pretty_host:
                    continue
                resp = getattr(fl, "response", None)
                entry = {
                    "url": req.url,
                    "method": req.method,
                    "status": resp.status_code if resp else None,
                    "req_headers": dict(req.headers),
                    "req_body": body_of(req),
                }
                if resp is not None:
                    entry["resp_body"] = body_of(resp)
                out.append(entry)
        except Exception as e:
            print(f"[!] flow stream ended early: {e}")

    print("== host histogram ==")
    for h, n in hosts.most_common():
        print(f"{n:4d}  {h}")
    print(f"\n== {len(out)} qunbaoshu requests ==")
    for e in out:
        print(e["method"], e["status"], e["url"])

    with open(CAPDIR + r"\extracted.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nsaved -> {CAPDIR}\\extracted.json")


if __name__ == "__main__":
    main()
