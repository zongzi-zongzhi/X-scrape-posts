# insforge-x-leads

只读采集 X 公开帖子，并将符合 InsForge 目标画像的建联线索同步到飞书多维表。

## 解决的问题

InsForge 需要稳定发现正在用 AI 工具做 App、网站、SaaS、MVP 或独立开发项目，但卡在后端、数据库、登录、权限、RLS、Auth、API Key、Vercel 部署、环境变量、数据保存等环节的人。这个项目把 X 公开帖子采集、语言过滤、规则筛选、去重、飞书 dry-run 和安全写入串成可复用自动化。

## 核心功能

- 只读搜索 X 公开帖子，不执行点赞、评论、转发、私信或发布。
- 支持 fixture、官方 X API、twscrape、Scweet、twikit 作为采集 provider。
- 按简中、繁中、英语、日语、韩语分语言配置规则。
- 严格过滤教程、课程、社群、招聘、资讯、热榜、开源项目推荐和 InsForge 自己人相关内容。
- 读取飞书表字段、已有帖子链接 / post id、“状态=不需要回”样本后再 dry-run。
- dry-run 通过且满足每日数量规则后才 append。
- 保留 raw JSONL、候选 JSON、Markdown、运行日志、同步报告和日报。

## 当前 Demo 能力

当前可运行 demo 是本地命令行自动化：

1. 读取配置和本地凭据引用。
2. 只读抓取 X 公开搜索结果。
3. 过滤并生成候选线索。
4. 检查飞书表结构和重复记录。
5. 在满足规则时追加新记录。

## 安全边界

- 不保存或打印真实 `auth_token`、`ct0`、Bearer Token、API Secret。
- 真实配置只允许放在本地 `.env`、`secrets/` 或本机 provider 数据库中。
- `.env`、`secrets/`、`outputs/`、本地数据库和 seen state 不应提交到 GitHub。
- 自动写入字段仅限：`发布时间`、`帖子名字`、`帖子链接`、`匹配关键词`。
- 人工字段必须留空：`状态`、`评论`、`后续帖主回复`、`回复情况`、`二次评论`、`其他`。

## 数量规则

每日每种语言入库数量：

- 最少：10 条
- 最多：25 条

程序会将同步上限限制为 25 条；如果 fresh 记录少于 10 条，会在 sync report 中写入 `blocked_reason` 并阻止 append。不得为了凑数量放宽语言、InsForge、自家内容、教程、课程、招聘、社群、热榜、日报等硬性排除规则。

## 安装

```powershell
cd D:\GitHub\insforge-x-leads
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

也可以新建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，只填写本地真实值，不要提交 `.env`。

关键配置：

```text
X_PROVIDER=fixture
X_BEARER_TOKEN=
TWSCRAPE_ACCOUNTS_DB=
SCWEET_COOKIES_FILE=
SCWEET_AUTH_TOKEN=
TWIKIT_COOKIES_PATH=
LARK_CLI_PROFILE=feishu-other-org
LARK_BASE_APP_TOKEN=
```

## 运行

环境检查：

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

默认 fixture dry-run：

```powershell
.\.venv\Scripts\python.exe scripts\run_daily_x_crawl.py
```

简中 / 繁中每日自动化：

```powershell
$env:LARK_CLI_PROFILE="feishu-other-org"
.\.venv\Scripts\python.exe scripts\run_daily_zh_x_leads.py --append --commit-local-state
```

英语 / 日语 / 韩语：

```powershell
$env:LARK_CLI_PROFILE="feishu-other-org"
.\.venv\Scripts\python.exe scripts\run_multilang_x_leads.py --append --commit-local-state
```

## 输出

每次运行会生成：

- `outputs/<lang>/run-*/raw_posts.jsonl`
- `outputs/<lang>/run-*/leads.json`
- `outputs/<lang>/run-*/leads.md`
- `outputs/<lang>/run-*/run_log.json`
- `outputs/lark-sync-*/sync_report.json`
- `outputs/daily-*/*daily_report.json`

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## 项目结构

详见 [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)。

## 技术架构

详见 [docs/TECH_ARCHITECTURE.md](docs/TECH_ARCHITECTURE.md)。

## PRD

详见 [docs/PRD.md](docs/PRD.md)。

## 已知限制

- X 搜索 provider 依赖本地可用凭据、Cookie、会话数据库或官方 API token。
- 单账号搜索存在限流，twscrape 可能出现 `SearchTimeline` queue locked。
- 飞书写入依赖本地 lark-cli 授权。
- 规则筛选仍可能出现误判，发现误入库必须删除飞书记录、撤回本地 seen key，并补充排除规则。

## 许可证

MIT。详见 [LICENSE](LICENSE)。
