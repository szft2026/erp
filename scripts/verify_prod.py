#!/usr/bin/env python3
"""线上验收：重建后跑一遍，确认新镜像 + 核心功能。

用法：
    python3 verify_prod.py
    BASE=https://xxx ERP_USER=admin ERP_PWD=xxx python3 verify_prod.py

注意：**绝对不要**用 `?act=del` 去探测后门是否还在。
在旧镜像上那一条请求就是后门本身，会直接删掉 mysql_model.php 让全站 500。
新镜像是否上线，用下面的行为特征判断即可。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

BASE = (os.environ.get("BASE") or "https://erp.prod.page").rstrip("/") + "/index.php"
USER = os.environ.get("ERP_USER", "admin")
PWD = os.environ.get("ERP_PWD", "admin888")

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(path, data=None, raw=False):
    try:
        r = op.open(urllib.request.Request(f"{BASE}/{path}",
                                           data=urllib.parse.urlencode(data or {}).encode()), timeout=45)
        body = r.read()
        return r.status, (body if raw else body.decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, (body if raw else body.decode("utf-8", "ignore"))
    except Exception as e:
        return 0, str(e)


results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def login():
    st, h = call("login")
    if st != 200:
        return False, f"登录页 HTTP {st}"
    m = re.search(r'token:\s*"([a-f0-9]+)"', h)
    if not m:
        return False, "登录页没有 token"
    _, r = call("login", {"username": USER, "userpwd": PWD, "token": m.group(1), "ispwd": 0})
    return r.strip() == "1", r[:60]


ok, detail = login()
check("登录", ok, detail)
if not ok:
    print("\n登录失败，后续跳过（服务未就绪或账号变更）")
    sys.exit(1)

# 1 新镜像特征一：invSaleList 返回真实数据，且没有授权威胁文案
st, body = call("scm/invSa/invSaleList?transType=150601")
try:
    d = json.loads(body)
    msg = str(d.get("msg") or "")
    rows = (d.get("data") or {}).get("rows")
    licensed_nag = ("尚未授权" in msg) or ("清空您的数据库" in msg)
    check("invSaleList 返回真实数据（无授权威胁文案）",
          st == 200 and d.get("status") == 200 and not licensed_nag and isinstance(rows, list),
          f"rows={0 if rows is None else len(rows)} msg={msg[:24]}")
except Exception:
    check("invSaleList 返回真实数据（无授权威胁文案）", False, body[:60])

# 2 新镜像特征二：两个曾经 500 的接口
st, _ = call("scm/invSa/log")
check("scm/invSa/log 不再 500", st == 200, f"HTTP {st}")
st, body = call("scm/pdImport/index")
check("scm/pdImport/index 不再 500", st == 200 and "Fatal error" not in body, f"HTTP {st}")

# 3 核心读接口
st, body = call("basedata/contact/index?type=10", {"page": 1, "rows": 1})
check("客户列表", st == 200 and '"status":200' in body, f"HTTP {st}")
st, body = call("scm/invSa/saleList", {"transType": 150601, "page": 1, "rows": 1})
check("销售单列表", st == 200 and '"status":200' in body, f"HTTP {st}")

# 4 打印
st, pdf = call("scm/invSa/toPdf?id=124", raw=True)
check("销售单打印 PDF", st == 200 and pdf[:4] == b"%PDF", f"{len(pdf)}B")

# 5 错误兜底
st, body = call("basedata/contact/update", {"name": "ZZPROBE", "number": "ZZPROBE", "cCategory": "21"})
check("contact/update 缺 id 返回 JSON 而非 500", st == 200 and '"status":-1' in body, f"HTTP {st}")

failed = [r for r in results if not r[1]]
print("\n" + ("全部通过" if not failed else f"失败 {len(failed)} 项"))
sys.exit(0 if not failed else 2)
