# Development Log

## 2026-08-18

### Completed

- Added `src/insforge_x_leads/rules_doc.py` to parse `D:\zhishiku-010204\InsForge_X线索抓取规则.md` at runtime.
- Updated `scripts/run_daily_zh_x_leads.py` and `scripts/run_multilang_x_leads.py` so Feishu base token, CLI profile, table ids, daily minimum, and daily maximum come from the Markdown rules document.
- Added `--rules-doc` to daily orchestration scripts.
- Added tests for Markdown rules parsing and the below-minimum append gate.
- Read `D:\GitHub\readme.md` and applied its GitHub project creation protocol to this project.
- Added required project documents:
  - `docs/PRD.md`
  - `docs/TECH_ARCHITECTURE.md`
  - `docs/PROJECT_STRUCTURE.md`
  - `CHANGELOG.md`
  - `docs/DEV_LOG.md`
- Added repository health files:
  - `LICENSE`
  - `SECURITY.md`
  - `CONTRIBUTING.md`
  - `CODE_OF_CONDUCT.md`
  - `.github/` issue, PR, Dependabot, and CI files
- Updated README and `.gitignore`.
- Modified `scripts/sync_lark_x_table_cli.py` to support `--min-count`.
- Modified daily language runners to use minimum 10 and maximum 25 records per language.

### Why

The existing project had working automation but did not fully meet the project-management and repository-health requirements in the GitHub protocol. It also allowed append with very small fresh counts, which conflicted with the user-defined daily quantity rule and increased the chance of low-quality writes.

### Modules Changed

- `src/insforge_x_leads/rules_doc.py`
- Documentation and repository metadata.
- `scripts/sync_lark_x_table_cli.py`
- `scripts/run_daily_zh_x_leads.py`
- `scripts/run_multilang_x_leads.py`

### Related PRD Requirements

- FR-005: Feishu dry-run.
- FR-006: Quantity gate.
- FR-008: Audit outputs.

### Remaining Issues

- The current automation does not yet implement automatic supplemental crawling when fresh count is below 10. It blocks append and reports the reason. Supplemental query expansion should be implemented as a separate controlled change.
- Some older test fixture strings display mojibake in PowerShell, but tests should still be validated in UTF-8 Python.

### Next Steps

- Add supplemental crawl strategy for below-minimum cases.
- Add tests for `sync_lark_x_table_cli.py --min-count`.
- Add a manual review queue if false positives remain costly.
