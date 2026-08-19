# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added

- Added Markdown rules document loading via `src/insforge_x_leads/rules_doc.py`.
- Added `--rules-doc` to daily orchestration scripts so execution reads `D:\zhishiku-010204\InsForge_X线索抓取规则.md` before crawling or syncing.
- Added tests for parsing the Markdown rules document and validating the current knowledge-base rules file.
- Added PRD, technical architecture, project structure, development log, security, contributing, license, code of conduct, issue templates, PR template, and CI workflow.
- Added explicit daily quantity gate support to Feishu sync: append can be blocked when fresh rows are below a configured minimum.

### Changed

- Daily language runners now derive Feishu base token, CLI profile, table ids, minimum count, and maximum count from the Markdown rules document.
- Daily language runners now pass a per-language maximum append limit of 25 and minimum fresh count of 10.
- README now documents runtime, safety boundaries, quantity rules, outputs, tests, and known limits.
- `.gitignore` now excludes generated outputs, local databases, local seen state, logs, secrets, and caches more broadly.

### Fixed

- Reduced risk of low-count accidental append by enforcing the daily quantity rule in `sync_lark_x_table_cli.py`.

### Security

- Documented secret-handling boundaries and GitHub safety files.
