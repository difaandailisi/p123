#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P123 — 123 云盘（123pan）命令行客户端与库。

实测验证过的接口（详见 references/）：
  - GET  /file/list/new            列目录 / 搜索
  - POST /file/upload_request       新建文件夹(type=1) / 上传预检(秒传)
  - POST /file/delete               删除（移入回收站，返回 7301 视为成功）
  - GET  /file/download/traffic/check  下载流量预检（常返回 isBlocked=true）
  - GET  /user/info                 账号信息
  - POST /share/save                转存他人分享
  - GET  /share/traffic-info        分享流量余额

鉴权：Authorization: Bearer <token>，token 取自登录后的 localStorage.authorToken。
可选头 platform=web, app-version=3；loginuuid 经实测非必需。

仅用于本人已授权账号的自动化操作，不破解任何官方限制。
"""
import argparse
import hashlib
import json
import os
import sys
import time

import requests

API = "https://api.123278.com/b/api"
WEB = "https://yun.123pan.cn/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

STATE_FILE = os.path.expanduser("~/.p123/state.json")


# --------------------------------------------------------------------------- #
# 会话加载
# --------------------------------------------------------------------------- #
def load_token(state_file=STATE_FILE):
    """从 Playwright 保存的 storage_state 里取出 Bearer token。"""
    if not os.path.exists(state_file):
        raise SystemExit(f"未找到登录态：{state_file}\n请先运行 login_qr.py 扫码登录。")
    data = json.load(open(state_file, encoding="utf-8"))

    def clean(v):
        # storage_state 偶尔把 localStorage 值包成 JSON 字符串（带首尾引号）
        return v.strip().strip('"').strip("'") if v else v

    tok = None
    # 优先从 localStorage 读 authorToken（取最长且像 JWT 的值）
    cands = []
    for item in data.get("origins", []):
        for kv in item.get("localStorage", []):
            if kv.get("name") == "authorToken":
                cands.append(clean(kv.get("value")))
        for c in item.get("cookies", []):
            if c.get("name") == "authorToken" and not tok:
                tok = clean(c.get("value"))
    if not tok:
        for c in data.get("cookies", []):
            if c.get("name") in ("authorToken", "sso-token"):
                cands.append(clean(c.get("value")))
    cands = [c for c in cands if c]
    if cands:
        tok = max(cands, key=len)  # JWT 通常最长
    if not tok:
        raise SystemExit("登录态中没有 authorToken，请重新扫码登录。")
    return tok


def load_cookies(state_file=STATE_FILE):
    """返回 {name: value} 形式的 cookie 字典（供浏览器/直连使用）。"""
    data = json.load(open(state_file, encoding="utf-8"))
    return {c["name"]: c["value"] for c in data.get("cookies", [])}


# --------------------------------------------------------------------------- #
# 客户端
# --------------------------------------------------------------------------- #
class P123:
    def __init__(self, state_file=STATE_FILE):
        self.token = load_token(state_file)
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {self.token}",
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Origin": WEB,
            "Referer": WEB,
            "platform": "web",
            "app-version": "3",
        })

    @staticmethod
    def _j(r):
        try:
            return r.json()
        except Exception:
            return {"code": r.status_code, "text": r.text[:300]}

    def _request(self, method, path, params=None, payload=None):
        url = f"{API}{path}"
        last = None
        for attempt in range(4):  # 应对机房网络偶发的 SSL 断连
            try:
                if method == "GET":
                    return self._j(self.s.get(url, params=params, timeout=30))
                return self._j(self.s.post(url, json=payload or {}, params=params, timeout=30))
            except requests.exceptions.SSLError as e:
                last = e
                time.sleep(1.5 * (attempt + 1))
        return {"code": -1, "message": f"请求失败(SSL): {last}"}

    def _get(self, path, **params):
        return self._request("GET", path, params=params)

    def _post(self, path, payload=None):
        return self._request("POST", path, payload=payload)

    # ---- 账号 / 列表 ---- #
    def user_info(self):
        return self._get("/user/info")

    def ls(self, parent=0, limit=100, search=""):
        """列出 parent 目录下条目；search 非空则按文件名搜索。"""
        out, nxt, page = [], "0", 1
        while True:
            d = self._get("/file/list/new", driveId=0, limit=limit, next=nxt,
                          orderBy="update_time", orderDirection="desc",
                          parentFileId=parent, trashed="false", SearchData=search,
                          Page=page, OnlyLookAbnormalFile=0, event="homeListFile",
                          operateType=1, inDirectSpace="false", fileCategory=0,
                          isSearchOrder="false")
            if d.get("code") != 0:
                return d
            info = d["data"]
            out += info.get("InfoList", [])
            nxt = str(info.get("Next", "-1"))
            if nxt in ("-1", "", "0") or len(out) >= info.get("Total", 0):
                break
            page += 1
            if page > 50:
                break
        return {"code": 0, "Total": len(out), "InfoList": out}

    def stat(self, file_id):
        return self._post("/file/info", {"fileIdList": [file_id]})

    def mkdir(self, name, parent=0):
        """新建文件夹。真实 FileId 在 data.Info.FileId。"""
        return self._post("/file/upload_request", {
            "driveId": 0, "etag": "", "fileName": name, "parentFileId": parent,
            "size": 0, "type": 1, "duplicate": 2, "RequestSource": None,
        })

    def delete(self, file_id):
        """删除（移入回收站）。返回 7301 也视为成功。"""
        d = self._post("/file/delete", {"fileId": file_id})
        if d.get("code") in (0, 7301):
            d = dict(d, code=0)
        return d

    # ---- 上传 / 秒传 ---- #
    @staticmethod
    def md5_of(path):
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def upload_request(self, name, size, etag, parent=0, ftype=0, duplicate=2):
        """上传预检 / 新建。返回 Reuse=true 表示服务器已有相同 MD5，可直接挂载（秒传）。"""
        return self._post("/file/upload_request", {
            "driveId": 0, "etag": etag, "fileName": name, "parentFileId": parent,
            "size": size, "type": ftype, "duplicate": duplicate, "RequestSource": None,
        })

    def instant_upload(self, path, parent=0):
        """尝试秒传：计算 MD5 后请求 upload_request。命中 Reuse 则真文件已挂上，0 字节。"""
        etag = self.md5_of(path)
        size = os.path.getsize(path)
        name = os.path.basename(path)
        d = self.upload_request(name, size, etag, parent=parent)
        info = (d.get("data") or {}).get("Info") or {}
        fid = info.get("FileId") or (d.get("data") or {}).get("FileId") or 0
        return {
            "code": d.get("code"),
            "reuse": bool((d.get("data") or {}).get("Reuse")),
            "file_id": fid,
            "name": name,
            "etag": etag,
            "raw": d,
        }

    # ---- 下载预检 / 分享 ---- #
    def download_traffic_check(self, file_id):
        return self._post("/file/download/traffic/check", {"fids": [file_id]})

    def share_save(self, share_key, file_ids=None, parent=0, pwd=""):
        """转存他人分享到自己网盘。"""
        return self._post("/share/save", {
            "shareKey": share_key, "sharePwd": pwd,
            "fileIdList": file_ids or [], "parentFileId": parent,
        })

    def share_traffic_info(self):
        return self._get("/share/traffic-info")


# --------------------------------------------------------------------------- #
# 浏览器上传（秒传未命中时走 Web UI，可处理覆盖对话框）
# --------------------------------------------------------------------------- #
def browser_upload(path, parent=0, state_file=STATE_FILE):
    """用 Playwright 驱动 Web 上传。适合大文件或秒传未命中的情况。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("browser_upload 需要 playwright：pip3 install playwright && playwright install chromium")
    name = os.path.basename(path)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        ctx = b.new_context(storage_state=state_file, viewport={"width": 1400, "height": 900},
                            user_agent=UA, locale="zh-CN")
        pg = ctx.new_page()
        pg.goto(WEB, wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(3500)
        try:
            pg.click("text=上传", timeout=6000)
        except Exception:
            pass
        pg.wait_for_timeout(1200)
        inputs = pg.query_selector_all("input[type=file]")
        if not inputs:
            b.close()
            return {"ok": False, "msg": "未找到文件输入框"}
        inputs[1].set_input_files(path) if len(inputs) > 1 else inputs[0].set_input_files(path)
        # 处理“同名文件”覆盖对话框
        for _ in range(30):
            pg.wait_for_timeout(1000)
            try:
                btn = pg.get_by_role("button", name="覆盖").first
                if btn.count() and btn.is_visible():
                    btn.click()
                    break
            except Exception:
                pass
        pg.wait_for_timeout(8000)
        b.close()
    return {"ok": True, "msg": f"{name} 已提交上传（请到网盘确认）"}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _fmt(items):
    def mb(n):
        n = int(n or 0)
        return f"{n/1048576:.1f}MB" if n > 1048576 else f"{n/1024:.0f}KB"
    # 保留接口返回顺序（搜索时接口把精确匹配放最前，不要重排破坏相关性）
    for it in items:
        t = "DIR " if it.get("Type") == 1 else "FILE"
        print(f"{t} {str(it.get('FileId')):<12} {mb(it.get('Size', 0)):>9}  {it.get('FileName')}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="p123", description="123 云盘命令行客户端")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami", help="打印账号信息")
    p_ls = sub.add_parser("ls", help="列目录")
    p_ls.add_argument("parent", nargs="?", default=0, type=int, help="父目录 FileId，默认根目录")
    p_se = sub.add_parser("search", help="按文件名搜索")
    p_se.add_argument("keyword", help="关键词")
    p_mk = sub.add_parser("mkdir", help="新建文件夹")
    p_mk.add_argument("name", help="文件夹名")
    p_mk.add_argument("parent", nargs="?", default=0, type=int)
    p_rm = sub.add_parser("rm", help="删除（进回收站）")
    p_rm.add_argument("file_id", type=int)
    p_up = sub.add_parser("upload", help="上传（秒传优先，否则浏览器上传）")
    p_up.add_argument("path", help="本地文件路径")
    p_up.add_argument("parent", nargs="?", default=0, type=int)
    p_up.add_argument("--force-browser", action="store_true", help="强制走浏览器上传")
    p_dl = sub.add_parser("dlcheck", help="下载流量预检（看是否被 VIP 限制）")
    p_dl.add_argument("file_id", type=int)

    args = ap.parse_args(argv)
    c = P123()

    if args.cmd == "whoami":
        d = c.user_info()
        print(json.dumps(d, ensure_ascii=False, indent=2)[:1500])
    elif args.cmd == "ls":
        d = c.ls(args.parent)
        if d.get("code") != 0:
            print("失败：", d); return 1
        print(f"共 {d['Total']} 项：")
        _fmt(d["InfoList"])
    elif args.cmd == "search":
        d = c.ls(0, search=args.keyword)
        if d.get("code") != 0:
            print("失败：", d); return 1
        print(f"匹配 {d['Total']} 项：")
        _fmt(d["InfoList"])
    elif args.cmd == "mkdir":
        d = c.mkdir(args.name, args.parent)
        if d.get("code") != 0:
            print("失败：", d); return 1
        info = (d.get("data") or {}).get("Info") or {}
        print(f"已建文件夹：{args.name}  FileId={info.get('FileId')}")
    elif args.cmd == "rm":
        d = c.delete(args.file_id)
        if d.get("code") != 0:
            print("失败：", d); return 1
        print(f"已删除 FileId={args.file_id}（移入回收站，可恢复）")
    elif args.cmd == "upload":
        if args.force_browser:
            print(browser_upload(args.path, args.parent))
        else:
            r = c.instant_upload(args.path, args.parent)
            if r["reuse"]:
                print(f"✅ 秒传成功（0 字节）：{r['name']}  FileId={r['file_id']}  MD5={r['etag']}")
            else:
                print(f"⚠️ 未命中秒传，改为浏览器上传：{r['name']}")
                print(browser_upload(args.path, args.parent))
    elif args.cmd == "dlcheck":
        d = c.download_traffic_check(args.file_id)
        print(json.dumps(d, ensure_ascii=False, indent=2)[:800])
        data = (d.get("data") or {})
        if data.get("isBlocked"):
            print("\n❌ 该账号下载被官方限制（isBlocked=true），需开 VIP 或用官方客户端下载。本技能不绕过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
