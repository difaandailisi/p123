# P123 · 123 云盘助手

> 一个把"在无头/服务器环境下怎么真正用上 123 云盘（123pan）"的踩坑经验，固化成可复用工具的 WorkBuddy 技能。

[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

123 云盘是国内的网盘服务（域名 `123pan.com` 系列）。本技能不依赖任何第三方网盘挂载器（如 AList），只走**官方网页会话**与**官方接口**，把登录、列目录、搜索、上传、转存等高频操作自动化，并**如实报告官方下载/会员限制**。

---

## 为什么要有这个技能

做自动化时发现 123 云盘有几个"反直觉"的坑：

1. **登录页真实域名是 `user.123pan.cn`（`.cn`），不是 `www.123pan.com`**——后者登录接口反复 404。
2. **手机号 + 验证码登录会被阿里云滑块拦截**，无头浏览器模拟拖拽过不了风控；只能走**扫码登录**。
3. **API 基地址是 `api.123278.com`，不是 `api.123pan.com`**。
4. **上传支持"秒传"**：算 MD5 预检，服务端已有相同文件则直接挂载，**零字节**完成（适合官方安装包等热门资源）。
5. **Web 端下载被官方策略拦截**：`isBlocked=true` 即使剩余流量充足也要开 VIP。这是官方限制，本技能**不绕过**，只如实告诉你原因和替代方案（用官方客户端下载）。

这些都在 `references/` 里写成了文档。

---

## 功能矩阵

| 能力 | 状态 | 说明 |
|---|---|---|
| 扫码登录（QR） | ✅ 实测可用 | 绕开阿里云滑块 |
| 列目录 / 搜索 | ✅ 实测可用 | 纯官方接口 |
| 新建文件夹 / 删除 | ✅ 实测可用 | 删除进回收站（可恢复） |
| 上传（秒传优先） | ✅ 实测可用 | 命中 MD5 秒传 0 字节；否则浏览器上传 |
| 转存他人分享 | ⚠️ 接口已定位 | 按官方接口调用 |
| 下载到自己机器 | ❌ 官方限制 | Web 端 `isBlocked`，需开 VIP 或用官方客户端 |
| 生成分享链接 | ⚠️ 能生成 | 对方提取需分享流量包（默认 0） |

---

## 快速开始

```bash
# 依赖
pip3 install requests playwright
playwright install chromium

# 1) 扫码登录（生成二维码图片，手机 123 云盘 App / 微信扫码确认）
python3 scripts/login_qr.py
#    登录态默认保存 ~/.p123/state.json

# 2) 账号与文件
python3 scripts/p123.py whoami
python3 scripts/p123.py ls
python3 scripts/p123.py search "android-studio"
python3 scripts/p123.py mkdir "软件安装包"
python3 scripts/p123.py rm <FileId>

# 3) 上传（秒传优先）
python3 scripts/p123.py upload ./android-studio-rabbit2-windows.exe
```

---

## 目录结构

```
p123/
├── SKILL.md                  技能定义（frontmatter + 说明）
├── README.md                 本文件
├── LICENSE                   CC BY-SA 4.0
├── scripts/
│   ├── login_qr.py           扫码登录（Playwright）
│   └── p123.py               客户端库 + CLI
└── references/
    ├── 01-登录与扫码.md
    ├── 02-文件管理.md
    ├── 03-上传与秒传.md
    ├── 04-下载与会员限制.md
    └── 05-接口与字段速查.md
```

---

## 核心接口（速查）

基地址 `https://api.123278.com/b/api`，鉴权 `Authorization: Bearer <authorToken>`。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/user/info` | 账号信息 |
| GET | `/file/list/new` | 列目录 / 搜索（`SearchData`） |
| POST | `/file/upload_request` | 新建文件夹 / 上传秒传预检（`etag`=MD5） |
| POST | `/file/delete` | 删除（→回收站，`code:7301` 成功） |
| POST | `/file/download/traffic/check` | 下载流量预检（`isBlocked`） |
| POST | `/share/save` | 转存他人分享 |
| GET | `/share/traffic-info` | 分享提取流量余额 |

完整字段与坑见 [`references/05-接口与字段速查.md`](references/05-接口与字段速查.md)。

---

## 安全与隐私

- 登录态（`~/.p123/state.json`）**等同账号权限，按密码保管**；用完可在 123 云盘「设置 → 设备管理」踢掉登录。
- **不要在对话里明文发送网盘密码**。
- 本技能仅用于本人已授权账号的自动化；下载内容合法性由用户负责。
- **不破解、不伪造登录态、不绕过验证码/风控/会员/付费/限速/DRM**；官方不给直链时安全失败并如实报告。

---

## 许可

[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。你可以自由使用、修改、再分发，但需要署名并以相同方式共享。
