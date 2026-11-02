---
display_name: P123 · 123云盘助手
display_name_en: P123 · 123Pan Helper
description_zh: 123 云盘（123pan）自动化助手：扫码登录、列目录、搜索、新建/删除、上传（秒传优先）、转存分享，并如实报告下载与会员限制。仅走官方网页会话与官方接口，不破解登录/付费/限速/风控/DRM。
description_en: 123Pan (123云盘) automation helper: QR login, list/search, mkdir/delete, upload (instant-transfer first), save shares, and honest reporting of download/VIP limits. Uses only official web sessions and APIs; no cracking of login/pay/rate-limit/DRM.
name: p123
slug: p123
displayName: P123 · 123云盘助手
version: 1.0.0
platforms: [linux, macos, windows]
author: difaandailisi
license: CC-BY-SA-4.0
description: 123 云盘自动化助手。支持扫码登录（绕过阿里云滑块）、列目录、搜索、新建文件夹、删除（进回收站）、上传（命中 MD5 秒传、否则走浏览器上传）、转存他人分享；如实报告下载被 VIP 限制与分享流量不足。依赖 Playwright（扫码与上传）与 requests（纯接口调用）。
usage: 需要操作 123 云盘时使用。先 `python3 scripts/login_qr.py` 让用户扫码登录（保存到 ~/.p123/state.json），再用 `python3 scripts/p123.py ls|search|mkdir|rm|whoami|upload` 管理文件。下载受限时如实告知用户开 VIP 或用官方客户端。不破解任何官方限制。
metadata:
  version: "1.0.0"
i18n:
  en: README.en.md
  zh: README.md
locale: zh-CN
locales: [zh-CN, en-US]
---

# P123 · 123 云盘助手

面向 123 云盘（123pan，域名 `123pan.com` / `123684.com` / `123865.com` / `123912.com`）的轻量自动化技能。
它把"在机房/服务器无头环境下怎么真正用上 123 云盘"的踩坑经验固化成可复用工具。

## 它能做什么 / 不能做什么

| 能力 | 状态 | 说明 |
|---|---|---|
| 扫码登录（QR） | ✅ 实测可用 | 绕开手机号登录的阿里云滑块验证 |
| 列目录 / 搜索 | ✅ 实测可用 | 纯官方接口，无需浏览器 |
| 新建文件夹 / 删除 | ✅ 实测可用 | 删除是移入回收站（可恢复） |
| 上传（秒传优先） | ✅ 实测可用 | 命中 MD5 秒传零字节；否则走浏览器上传 |
| 转存他人分享 | ⚠️ 接口已定位 | 依赖分享密钥，按官方接口调用 |
| 下载到自己机器 | ❌ 受官方限制 | Web 端 `isBlocked` 需开 VIP；如实告知，不绕过 |
| 生成分享链接 | ⚠️ 能生成 | 但对方"提取"需分享流量包（账号默认 0） |

核心原则：**只走官方网页会话、官方接口和用户主动确认的操作；不破解、不伪造登录态、不绕过验证码/风控/会员/付费/DRM。官方不给直链时安全失败并如实报告。**

## 快速开始

```bash
# 1) 安装依赖
pip3 install requests playwright
playwright install chromium

# 2) 扫码登录（会弹出二维码图片，手机 123 云盘 App 扫码确认）
python3 scripts/login_qr.py
# 登录态默认保存在 ~/.p123/state.json

# 3) 查看账号与根目录
python3 scripts/p123.py whoami
python3 scripts/p123.py ls

# 4) 搜索 / 建目录 / 删文件
python3 scripts/p123.py search "android-studio"
python3 scripts/p123.py mkdir "软件安装包"
python3 scripts/p123.py rm <FileId>

# 5) 上传（秒传优先，命中则 0 字节；否则浏览器上传）
python3 scripts/p123.py upload ./android-studio-rabbit2-windows.exe
```

## 关键结论（来自实测）

1. **登录页真实域名是 `user.123pan.cn`，不是 `www.123pan.com`**（`www` 下登录接口反复 404）。扫码登录走 `https://user.123pan.cn/centerlogin`。
2. **手机号登录在无头环境会被阿里云滑块（拖动验证）挡住**——模拟拖拽不被认可。优先用扫码。
3. **API 基地址 `https://api.123278.com/b/api`**；鉴权用 `Authorization: Bearer <token>`，token 取自登录后的 `localStorage.authorToken`；附带 `platform: web`、`app-version: 3` 头。
4. **上传走 `POST /file/upload_request`**：服务端按 `etag`（文件 MD5）判断，若已存在同 MD5 文件则返回 `Reuse: true` 直接挂载（**秒传，零字节**）。新建文件夹同样走此接口，`type: 1`，真实 FileId 在 `data.Info.FileId`。
5. **下载在 Web 端默认被拦截**：`POST /file/download/traffic/check` 返回 `isBlocked: true`，即使剩余流量充足也需开 VIP。这是官方策略，本技能不绕过；建议在手机/桌面官方客户端下载，或开会员。

> 详细接口字段、踩坑与示例见 `references/` 各文档。

## 目录

```
p123/
├── SKILL.md                 本文件
├── README.md                中文介绍
├── LICENSE                  CC BY-SA 4.0
├── scripts/
│   ├── login_qr.py          扫码登录（Playwright）
│   └── p123.py              客户端库 + CLI
└── references/
    ├── 01-登录与扫码.md
    ├── 02-文件管理.md
    ├── 03-上传与秒传.md
    ├── 04-下载与会员限制.md
    └── 05-接口与字段速查.md
```

## 隐私与安全提醒

- 登录态（`state.json`）等同账号权限，**视为密码保管**；用完可在 123 云盘「设置 → 设备管理」踢掉陌生登录。
- 不要在对话里明文发送网盘密码（本次调试曾用过，建议改密）。
- 本技能仅自用/授权场景；下载内容合法性由用户负责。
