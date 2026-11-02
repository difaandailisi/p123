#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
login_qr.py — 123 云盘扫码登录。

为什么不用手机号登录：123 云盘手机号登录在无头/自动化环境会被「阿里云滑块」
（拖动验证）拦截，模拟拖拽不被认可。扫码登录走 https://user.123pan.cn/centerlogin，
稳定可用。

用法：
    python3 login_qr.py [--out 二维码图片路径] [--state 登录态保存路径]

默认：
    - 二维码图片保存到当前目录下的 123云盘登录二维码.png（中文名，方便识别）
    - 登录态保存到 ~/.p123/state.json（p123.py 默认读取此处）

登录成功后把二维码展示给用户，用户用「123 云盘 App」或「微信」扫，
手机点确认后即可。脚本最长等待 15 分钟。
"""
import argparse
import json
import os
import time

from playwright.sync_api import sync_playwright

LOGIN_PAGE = "https://user.123pan.cn/centerlogin"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
STATE_DEFAULT = os.path.expanduser("~/.p123/state.json")
QR_DEFAULT = os.path.join(os.getcwd(), "123云盘登录二维码.png")


def log(*a):
    print("[login]", *a, flush=True)


def find_qr(pg):
    """定位页面里的二维码元素（img/canvas，近似正方形）。"""
    best = None
    for el in pg.query_selector_all("img, canvas"):
        try:
            bb = el.bounding_box()
            if not bb:
                continue
            w, h = bb["width"], bb["height"]
            if 120 < w < 420 and abs(w - h) < 30:
                if best is None or w > best[0]:
                    best = (w, bb)
        except Exception:
            continue
    return best[1] if best else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=QR_DEFAULT, help="二维码图片保存路径")
    ap.add_argument("--state", default=STATE_DEFAULT, help="登录态（storage_state）保存路径")
    ap.add_argument("--timeout", type=int, default=900, help="最长等待秒数，默认 900")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.state)), exist_ok=True)

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 1280, "height": 900},
                            user_agent=UA, locale="zh-CN", device_scale_factor=2)
        pg = ctx.new_page()
        pg.goto(LOGIN_PAGE, wait_until="networkidle", timeout=45000)
        pg.wait_for_timeout(3000)

        qr = find_qr(pg)
        if qr:
            pad = 24
            clip = {"x": max(qr["x"] - pad, 0), "y": max(qr["y"] - pad, 0),
                    "width": qr["width"] + pad * 2, "height": qr["height"] + pad * 2}
            pg.screenshot(path=args.out, clip=clip)
        else:
            log("未定位到二维码元素，改截左栏")
            pg.screenshot(path=args.out, clip={"x": 180, "y": 300, "width": 400, "height": 400})
        log(f"二维码已保存：{args.out}  （请手机 123 云盘 App / 微信扫码）")

        # 轮询登录态
        deadline = time.time() + args.timeout
        logged = False
        while time.time() < deadline:
            pg.wait_for_timeout(2000)
            url = pg.url
            cks = ctx.cookies()
            names = {c["name"] for c in cks}
            if "centerlogin" not in url:
                logged = True
            elif {"authorToken", "sso-token"} & names:
                logged = True
            if logged:
                ctx.storage_state(path=args.state)
                pg.screenshot(path=os.path.join(os.path.dirname(args.out) or ".", "123云盘登录成功.png"))
                log(f"✅ 登录成功，登录态已保存：{args.state}")
                break
        else:
            log("⏰ 超时未登录。二维码可能已失效，请重新运行本脚本。")
        b.close()
        if not logged:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
