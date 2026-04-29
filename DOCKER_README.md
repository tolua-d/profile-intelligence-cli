# Insighta CLI - Docker Setup

This document describes how to run the Insighta CLI in Docker.

## Prerequisites

- Docker
- Docker Compose (optional, for orchestration)

## Quick Start

### 1. Build the CLI Docker Image

```bash
docker build -t insighta_cli:latest .
```

### 2. Run CLI Commands

```bash
# Get help
docker run --rm insighta_cli:latest --help

# List profiles (requires API running and INSIGHTA_API_URL set)
docker run --rm \
  -e INSIGHTA_API_URL=http://localhost:8000 \
  insighta_cli:latest profiles list

# Create a profile
docker run --rm \
  -e INSIGHTA_API_URL=http://localhost:8000 \
  insighta_cli:latest profiles create --name "John Doe"
```

## Environment Variables

- `INSIGHTA_API_URL` - API endpoint (default: `http://api:8000`)
- `GITHUB_CLIENT_ID` - GitHub OAuth client ID (required for login)

```bash
docker run --rm \
  -e INSIGHTA_API_URL=http://localhost:8000 \
  -e GITHUB_CLIENT_ID=your_client_id \
  insighta_cli:latest login
```

## Credentials Persistence

To persist credentials between runs, mount the credentials directory:

```bash
docker run --rm \
  -v ~/.insighta:/root/.insighta \
  -e INSIGHTA_API_URL=http://localhost:8000 \
  insighta_cli:latest whoami
```

## Using with Docker Compose

### Standalone CLI Compose

```bash
# Start with API reference
docker-compose up -d

# Run a command
docker-compose run --rm cli profiles list

# Stop
docker-compose down
```

### From Root Docker Compose

If using the root-level docker-compose.yml:

```bash
cd ..

# Run CLI with all services
docker-compose --profile cli run --rm cli profiles list

# Or start CLI interactively
docker-compose --profile cli run --rm -it cli
```

## Interactive Mode

```bash
# Start interactive session
docker run -it --rm \
  -v ~/.insighta:/root/.insighta \
  -e INSIGHTA_API_URL=http://localhost:8000 \
  insighta_cli:latest

# Then run commands like:
# > insighta login
# > insighta profiles list
# > insighta profiles get <id>
```

## Network Access

When running with other services in docker-compose:

- Access API at `http://api:8000` (from within container network)
- Access web at `http://web:3000` (if needed)

## Common Commands

```bash
# Show help
docker run --rm insighta_cli:latest --help

# List all profiles
docker run --rm -e INSIGHTA_API_URL=http://localhost:8000 \
  insighta_cli:latest profiles list --limit 20

# Search profiles
docker run --rm -e INSIGHTA_API_URL=http://localhost:8000 \
  insighta_cli:latest profiles search "female adults"

# Export to CSV
docker run --rm -e INSIGHTA_API_URL=http://localhost:8000 \
  -v $(pwd):/tmp \
  insighta_cli:latest profiles export --format csv

# Show current user
docker run --rm -e INSIGHTA_API_URL=http://localhost:8000 \
  -v ~/.insighta:/root/.insighta \
  insighta_cli:latest whoami
```

## Volumes

- `~/.insighta:/root/.insighta` - Credentials storage
- `./:/app` - Project directory (for development)

## Development

### Rebuild After Changes

```bash
docker build -t insighta_cli:latest .
```

### Mount Source for Development

```bash
docker run -it --rm \
  -v $(pwd):/app \
  -v ~/.insighta:/root/.insighta \
  -e INSIGHTA_API_URL=http://localhost:8000 \
  insighta_cli:latest bash
```

## Troubleshooting

### "Connection refused" to API

Make sure the API is running and the `INSIGHTA_API_URL` is correct:

```bash
# If running with docker-compose
docker-compose logs api

# If running standalone API
docker ps | grep api
```

### Credentials Not Found

Create the `.insighta` directory and mount it:

```bash
mkdir -p ~/.insighta
docker run --rm -v ~/.insighta:/root/.insighta insighta_cli:latest login
```

### "Command not found"

Make sure the image is built:

```bash
docker images | grep insighta_cli
docker build -t insighta_cli:latest .
```

## Docker Image Details

- **Base Image**: `python:3.11-slim`
- **Workdir**: `/app`
- **Entrypoint**: `python -m insighta_cli.main`
- **Default CMD**: `--help`

## Size Optimization

The image uses `python:3.11-slim` to minimize size. Current size is typically under 300MB.

To see actual size:

```bash
docker images insighta_cli:latest
```
