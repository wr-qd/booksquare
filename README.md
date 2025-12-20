# 多平台书籍评论分析系统（雾林书札）

把“找书、看评价、收进书架、沉浸阅读、记录感想、每天被温柔地推荐一本”串成一个闭环。

这是一个开箱可跑的全栈项目：

- 前端：Vue 3 + Vite + Vue Router + Axios
- 后端：Flask + SQLAlchemy（自动建表）
- 数据库：默认 SQLite（开箱即用），也支持切换 MySQL
- 阅读：支持 TXT/EPUB 导入与站内阅读（含阅读进度、字号/背景调节）
- 多源内容：豆瓣书籍信息与短评（抓取）、微博搜索（可选 Playwright）、B站专栏书评（搜索+详情+图片代理）

---

## 你能用它做什么

### 1) 搜索与发现：

- 书名/关键词搜索：直接从豆瓣搜索返回结果卡片（带封面、作者、评分）
- 高级搜索：选择“类型 + 描述”，系统会从描述里提取情绪/氛围关键词，再去豆瓣组合检索
- 搜索缓存：对同一关键词做 sessionStorage 缓存，二次进入几乎秒开

### 2) 书籍详情页：

- 基础信息：书名、作者、豆瓣评分、标签、简介（可展开/收起）
- 一键喜欢：加入/移除书架（同一个按钮，状态明确）
- 读书日志：在详情页直接写感想，自动进入个人时间线
- 评论词云：从豆瓣短评提取中文分词，后端即时生成 PNG（无额外重依赖）

### 3) 书评来源切换：

- 豆瓣短评：分页加载更多
- 微博：按书名搜索相关内容（可选 Playwright；支持保存登录态以提升可用性）
- B站：搜索图文专栏书评，支持进入“详情页”并代理图片避免防盗链/404

### 4) 书架：你的“阅读中控台”

- 书架列表：展示你喜欢的书（含封面、作者、评分）
- 继续阅读：如果你已导入/下载过该书资源，直接一键续读
- 上传并阅读：对书架上的书直接导入 TXT/EPUB 并立即进入阅读器
- 我的感想：在书架里打开“随笔/收藏句子”时间线面板，并支持逐条删除

### 5) 自定义书籍：

- 创建自建书：填写书名/作者/简介，封面支持上传（自动压测格式、避免乱七八糟的扩展名）
- 自动加入书架：创建即上架，立刻可导入并阅读

### 6) 阅读器：

- TXT/EPUB 站内阅读
- 进度同步：
	- TXT 保存 scrollY
	- EPUB 保存 CFI（epubjs 的定位标识）
- 字号调节：A+/A-，并持久化保存
- 背景调节：
	- 默认背景
	- 纯色背景
	- 渐变背景
	- 上传图片做背景
	- 遮罩强度可调（让文字更清晰）
- 划线交互：TXT 模式支持选中文本后弹出操作
	- 加入随笔
	- 收藏句子

### 7) 个人信息页：把你的阅读记录变成“时间线”

- 展示账号信息（用户名、邮箱、注册时间）
- 读书日记鱼骨时间线：最新在前
- 支持按书籍筛选、支持删除某条日记

### 8) 每日推荐：每天最多 2 次

- 首页自动生成今日推荐（基于你的书架）
- 支持刷新，但每日有次数上限

---

## 技术实现亮点

- 后端采用 Flask Blueprint 分模块：auth/books/me/reader/recommendations/custom-books
- 统一 JWT Bearer 鉴权：前端 Axios 拦截器自动带 token
- SQLite 默认路径固定为 server/instance/book_review.db，避免“启动目录不同导致连错库”
- 阅读资源存储隔离：按 user_id 存到 server/instance/reader_assets/<user_id>/
- 安全策略：
	- 图片代理/封面代理做了域名限制
	- Gutenberg 下载做 allowlist，避免变成任意下载器

---

## 目录速览

- client/：前端工程（Vue 3 + Vite）
- server/：后端工程（Flask API + SQLAlchemy 模型）
- scripts/：一键启动与分平台脚本
- docs/：设计/分析文档
- examples/：示例 payload 与独立脚本

---

## 快速开始

### 1) 克隆项目

```bash
git clone <your-repo-url> book-review-system
cd book-review-system
```

### 2) 一条命令启动前后端

- Windows（PowerShell）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

如仍出现中文乱码，建议在同一窗口先执行 `chcp 65001`，或使用 Windows Terminal 运行上述命令。

- macOS/Linux

```bash
bash scripts/dev.sh
```

启动成功后：

- 后端：http://127.0.0.1:5000
- 前端：http://127.0.0.1:3000

---

## 手动启动（更适合开发调试）

### 后端

```bash
python -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 可选：配置环境变量
copy .env.example .env            # macOS/Linux: cp .env.example .env

python server/app.py
```

说明：默认 SQLite 会在首次启动时自动创建表，不需要额外执行初始化脚本。

健康检查：

- /api/health
- /api/debug/routes

### 前端

```bash
cd client
npm install
npm run dev
```

前端开发环境通过 Vite proxy 自动把 /api 转发到 http://127.0.0.1:5000。

---

## 配置说明（.env）

你可以把 .env 放在仓库根目录或 server/.env。

- SECRET_KEY：Flask session 等用途（生产环境务必修改）
- JWT_SECRET_KEY：JWT 签名密钥（生产环境务必修改）
- DATABASE_URL：数据库连接串
	- 默认：SQLite（无需配置）
	- MySQL 示例：

```env
DATABASE_URL=mysql+mysqlconnector://root:<password>@localhost:3306/book_review_system
```

邮件（可选，用于验证码邮件）：

- MAIL_SERVER / MAIL_PORT / MAIL_USE_TLS
- MAIL_USERNAME / MAIL_PASSWORD

前端（可选）：

- VITE_API_BASE：生产环境前后端不同域名时，指定后端 base
- VITE_BG_IMAGE_URL：替换全局背景图（示例：放一张图到可访问的 URL）

---

## 可选能力（按需开启）

### 1) Playwright（豆瓣/微博“打开浏览器登录”、微博搜索）

某些能力需要 Playwright（比如打开浏览器让你手动登录并保存 cookies，以提升抓取可用性）。默认 requirements.txt 不强制安装它。

安装方式：

```bash
pip install playwright
playwright install chromium
```

### 2) 第三方登录态文件位置（本地保存，不建议提交）

- server/instance/douban_cookies.json
- server/instance/weibo_cookies.json

---

## API 速览（前端实际在用的接口）

鉴权：

- POST /api/auth/register
- POST /api/auth/login
- GET  /api/auth/profile

书籍与多源内容：

- GET  /api/books/search?q=...&limit=50
- POST /api/books/advanced-search
- GET  /api/books/<book_id>
- GET  /api/books/<book_id>/comments?page=1&limit=20
- GET  /api/books/<book_id>/wordcloud
- GET  /api/books/douban/status | POST /api/books/douban/login | POST /api/books/douban/logout
- GET  /api/books/weibo/status | POST /api/books/weibo/login | POST /api/books/weibo/logout | GET /api/books/weibo/search
- GET  /api/books/bilibili/search | GET /api/books/bilibili/article | GET /api/books/bilibili/image

书架与个人数据（需要 Bearer token）：

- GET/POST/DELETE /api/me/bookshelf
- GET/POST/DELETE /api/me/reading-logs
- GET/POST/DELETE /api/me/notes

阅读器（需要 Bearer token）：

- GET  /api/reader/sources?book_id=...
- POST /api/reader/download
- POST /api/reader/upload
- GET  /api/reader/assets?book_id=...
- GET/POST /api/reader/assets/<asset_id>/progress
- GET  /api/reader/assets/<asset_id>/file

每日推荐（需要 Bearer token）：

- GET  /api/recommendations/today
- POST /api/recommendations/refresh

自定义书籍（需要 Bearer token）：

- POST /api/custom-books
- GET  /api/custom-books/<id>
- GET  /api/custom-books/cover/<filename>（展示封面不要求登录）

---

## 常见问题（非常常见，但也非常好解决）

### 1) 首页“每日推荐”显示 401/未授权

每日推荐接口需要登录 token。请先注册/登录，确认浏览器 localStorage 里有 token，再刷新首页。

### 2) 豆瓣搜索/详情偶尔失败（403/风控页）

这是豆瓣的反爬策略导致的。通常更换网络、降低频率、或者使用“豆瓣登录（可选 Playwright）”会更稳定。

### 3) Windows 运行脚本中文乱码

优先使用 Windows Terminal + PowerShell。必要时先执行 `chcp 65001` 再运行一键脚本。

---

## 启动脚本位置

- 一键启动：scripts/dev.ps1、scripts/dev.sh
- Windows 分步：scripts/windows/start_backend.bat、scripts/windows/start_frontend.bat
- macOS/Linux 分步：scripts/unix/start_backend.sh、scripts/unix/start_frontend.sh

---

## 示例与调试文件

- examples/payloads/：用于接口测试的示例请求体（JSON）
- examples/scripts/：独立示例脚本（不影响主服务运行）

---

## 备注（关于 MySQL 初始化脚本）

database/init.py 与 database/schema.sql 更偏向“旧版示例/演示数据”的 MySQL 初始化方式。

当前主服务使用 SQLAlchemy 的模型自动建表（server/app.py 启动时 db.create_all），所以：

- 默认 SQLite：直接启动即可，不需要 init.py
- 切换 MySQL：配置好 DATABASE_URL 后直接启动后端即可（同样会自动建表）

