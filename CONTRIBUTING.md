# Contributing

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` for local-only configuration. Never commit `.env`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Pull Request Checklist

- Update tests for behavior changes.
- Update README or docs if commands, configuration, outputs, or safety boundaries change.
- Update `CHANGELOG.md`.
- Do not commit secrets, cookies, provider DBs, raw outputs, or seen state.
- Preserve the X read-only contract.

## Coding Guidelines

- Keep provider operations read-only.
- Prefer explicit JSON reports over console-only output.
- Keep human-only Feishu fields blank.
- Fail with clear `blocked_reason` when a write should not proceed.
