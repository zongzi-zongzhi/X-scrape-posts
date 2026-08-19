# Project Structure

```text
insforge-x-leads/
  README.md
  CHANGELOG.md
  LICENSE
  SECURITY.md
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  .env.example
  .gitignore
  .github/
    ISSUE_TEMPLATE/
      bug_report.md
      feature_request.md
    workflows/
      ci.yml
    pull_request_template.md
  config/
  data/
  docs/
  fixtures/
  scripts/
  src/
  tests/
```

## 根目录

| 路径 | 作用 |
|---|---|
| `README.md` | 项目介绍、安装、配置、运行、测试和限制说明。 |
| `CHANGELOG.md` | 面向用户的版本变更记录。 |
| `LICENSE` | 开源许可证。 |
| `SECURITY.md` | 安全边界和漏洞报告方式。 |
| `CONTRIBUTING.md` | 本地开发、测试和 PR 要求。 |
| `CODE_OF_CONDUCT.md` | 贡献者行为规范。 |
| `.env.example` | 环境变量模板，只包含占位符。 |
| `.gitignore` | 忽略本地凭据、输出、缓存和数据库。 |
| `requirements.txt` | Python 依赖版本。 |

## `config/`

| 文件 | 作用 |
|---|---|
| `x_lead_crawl.zh_cn.json` | 简中搜索、过滤、语言和输出配置。 |
| `x_lead_crawl.zh_tw.json` | 繁中搜索、过滤、语言和输出配置。 |
| `x_lead_crawl.en.json` | 英语配置。 |
| `x_lead_crawl.ja.json` | 日语配置。 |
| `x_lead_crawl.ko.json` | 韩语配置。 |
| `lark_x_tables.json` | 飞书 base 与多语言 table id。 |
| `no_reply_profile.json` | 动态排除画像。 |

## `src/insforge_x_leads/`

| 文件 | 作用 |
|---|---|
| `models.py` | `XPost` 和 `LeadCandidate` 数据模型。 |
| `config.py` | 配置读取、路径解析、只读约束检查。 |
| `filtering.py` | 语言过滤、关键词过滤、画像组匹配和评分。 |
| `dedupe.py` | 本地去重 key 生成和 seen state 读写。 |
| `outputs.py` | 运行目录、JSON、JSONL、Markdown 和 pointer 输出。 |
| `profile.py` | no-reply profile 加载。 |
| `runner.py` | 单次抓取主流程。 |
| `providers/` | X 只读 provider 适配器。 |

## `scripts/`

| 文件 | 作用 |
|---|---|
| `run_daily_x_crawl.py` | 单配置抓取入口。 |
| `run_daily_zh_x_leads.py` | 简中 / 繁中每日抓取和飞书同步。 |
| `run_multilang_x_leads.py` | 英语 / 日语 / 韩语抓取和飞书同步。 |
| `sync_lark_x_table_cli.py` | 飞书字段读取、重复检查、数量门禁和 append。 |
| `refilter_raw_x_posts.py` | 从已保存 raw 重新过滤，不请求 X。 |
| `check_env.py` | 环境和依赖检查。 |
| `setup_*` | 本地凭据或飞书表初始化辅助脚本。 |

## `data/`

本地状态目录。包含 provider 数据库、seen state 和 no-reply 样本。该目录中的真实状态文件不应提交。

## `outputs/`

运行产物目录。包含 raw、leads、log、sync report 和 daily report。该目录不应提交到 GitHub。

## `tests/`

单元测试目录。最小验证入口：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
