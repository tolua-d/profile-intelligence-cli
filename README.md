# Insighta CLI (Stage 3)

## Install

```bash
pip install .
```

Or for development:

```bash
pip install -e .
```

Then from any directory:

```bash
python -m insighta_cli.main --help
```

Or if installed with entry point:

```bash
insighta --help
```

## Environment

- `INSIGHTA_API_URL` (default: `http://localhost:8000`)
- `GITHUB_CLIENT_ID` (required for `insighta login`)

## Credentials

Stored at `~/.insighta/credentials.json`.

## Commands

- `insighta login`
- `insighta logout`
- `insighta whoami`
- `insighta profiles list [filters...]`
- `insighta profiles get <id>`
- `insighta profiles search "query"`
- `insighta profiles create --name "Harriet Tubman"`
- `insighta profiles export --format csv [filters...]`
