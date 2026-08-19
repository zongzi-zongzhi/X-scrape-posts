# Security Policy

## Supported Versions

The current `main` branch is the only supported development line until formal releases are introduced.

## Secret Handling

Do not commit:

- `.env`
- X cookies
- X Bearer Tokens
- `auth_token`
- `ct0`
- Feishu tokens
- lark-cli session files
- provider account databases
- raw outputs containing real user data

Use `.env.example` for variable names and placeholders only.

## Reporting Security Issues

Open a private report with the maintainer or contact the repository owner directly. Do not file public issues containing secrets, tokens, cookies, private links, or real user data.

## Data Handling

The project stores local crawl outputs under `outputs/` and local state under `data/`. These directories are ignored by Git and should not be published unless explicitly scrubbed.
