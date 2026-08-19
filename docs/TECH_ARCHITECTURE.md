# Technical Architecture

## 1. 总体架构

项目是本地 CLI 自动化，分为采集、过滤、去重、同步和审计输出五层。

```text
Config + .env
  -> X Provider
  -> Filtering / Language Rules / No-reply Profile
  -> Local Dedupe
  -> Files under outputs/
  -> Feishu dry-run
  -> Feishu append if safe
  -> Daily report
```

## 2. 模块拆分

| 模块 | 路径 | 职责 |
|---|---|---|
| 配置层 | `config/` | 保存语言、关键词、排除词、表格和画像配置。 |
| Provider 层 | `src/insforge_x_leads/providers/` | 封装 fixture、X API、twscrape、Scweet、twikit 的只读搜索。 |
| 过滤层 | `src/insforge_x_leads/filtering.py` | 语言脚本检查、关键词筛选、画像组匹配和评分。 |
| 去重层 | `src/insforge_x_leads/dedupe.py` | 基于 URL、post id、作者与正文 hash 去重。 |
| 运行层 | `src/insforge_x_leads/runner.py` | 单语言采集、过滤、输出和 pointer 更新。 |
| 同步层 | `scripts/sync_lark_x_table_cli.py` | 通过 lark-cli 读取飞书表并 dry-run / append。 |
| 编排层 | `scripts/run_daily_zh_x_leads.py`、`scripts/run_multilang_x_leads.py` | 多表、多语言调度、日期窗口和日报生成。 |
| 验证层 | `tests/` | 单元测试和最小回归入口。 |

## 3. 技术栈

- Python 3
- 标准库 `argparse`、`json`、`subprocess`、`pathlib`
- `requests` 用于官方 X API provider
- `PyYAML` 用于 YAML 配置兼容
- `twscrape`、`Scweet`、`twikit` 作为可选 X provider
- lark-cli 作为飞书多维表访问方式

## 4. 数据流

1. 脚本读取 `.env` 和目标 config。
2. Provider 按查询词抓取 X 公开帖子。
3. 过滤层执行语言、排除词、画像组和评分。
4. 去重层读取 `data/seen_posts_*.json`。
5. runner 写出 raw、leads、Markdown 和 run log。
6. sync 脚本读取飞书字段和已有记录。
7. sync 脚本执行数量门禁、重复检查和 dry-run。
8. 满足条件才 append。
9. 编排脚本生成 daily report。

## 5. 输入输出格式

输入：

- 配置文件：JSON 或 YAML。
- X provider 凭据引用：环境变量或本地路径。
- 飞书配置：base token、table id、CLI profile。

输出：

- `raw_posts.jsonl`：每行一个 `XPost`。
- `leads.json`：结构化候选数组。
- `leads.md`：人工阅读报告。
- `run_log.json`：筛选和拒绝原因。
- `sync_report.json`：飞书字段、重复、数量门禁和 append 状态。
- `daily_report.json`：多语言汇总。

## 6. 授权与凭据

- X 官方 API 使用 `X_BEARER_TOKEN`。
- twscrape 使用 `TWSCRAPE_ACCOUNTS_DB` 指向本地账号数据库。
- Scweet 使用 `SCWEET_COOKIES_FILE` 或 `SCWEET_AUTH_TOKEN`。
- twikit 使用 `TWIKIT_COOKIES_PATH`。
- 飞书使用本地 `LARK_CLI_PROFILE`。

真实凭据不得写入 README、测试、示例或提交记录。

## 7. 错误处理

- Provider 缺配置时抛出明确错误。
- lark-cli 非 0 退出时抛出 CLI 输出。
- 飞书字段缺失时 `blocked_reason=target table missing required fields`。
- fresh 少于每日最小数量时 `blocked_reason=fresh_count below required minimum`。
- 输出 JSON 解析失败时保留子进程输出前 500 字符用于排查。

## 8. 扩展点

- 增加新语言：新增 config、seen state、表配置和编排入口。
- 增加 provider：实现 `ReadOnlyProvider.search_public_posts`。
- 增加质量规则：优先放入语言 config 的 `exclude_keywords` 和 `required_groups`。
- 增加人工审核：可在 append 前引入 review queue，但不能绕过 dry-run。
