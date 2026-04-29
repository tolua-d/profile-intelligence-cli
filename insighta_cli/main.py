import base64
import hashlib
import json
import os
import secrets
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

import click
import requests
from rich.console import Console
from rich.table import Table

console = Console()
CRED_DIR = Path.home() / ".insighta"
CRED_FILE = CRED_DIR / "credentials.json"
API_VERSION_HEADER = {"X-API-Version": "1"}


def api_url() -> str:
    return os.getenv("INSIGHTA_API_URL", "http://localhost:8000").rstrip("/")


def load_creds() -> dict[str, Any]:
    if not CRED_FILE.exists():
        return {}
    try:
        return json.loads(CRED_FILE.read_text())
    except Exception:
        return {}


def save_creds(data: dict[str, Any]) -> None:
    CRED_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    CRED_FILE.write_text(json.dumps(data, indent=2))
    CRED_FILE.chmod(0o600)


def clear_creds() -> None:
    save_creds({})


def _decode_jwt_exp(token: str) -> int | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        return int(data.get("exp"))
    except Exception:
        return None


def _refresh_tokens(creds: dict[str, Any]) -> dict[str, Any]:
    rt = creds.get("refresh_token")
    if not rt:
        raise click.ClickException("Session expired. Run 'insighta login'.")
    res = requests.post(f"{api_url()}/auth/token/refresh/", json={"refresh": rt}, timeout=20)
    if res.status_code != 200:
        clear_creds()
        raise click.ClickException("Session expired. Run 'insighta login'.")
    body = res.json()
    creds["access_token"] = body["access"]
    creds["refresh_token"] = body["refresh"]
    creds["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_creds(creds)
    return creds


def auth_headers() -> dict[str, str]:
    creds = load_creds()
    at = creds.get("access_token")
    if not at:
        raise click.ClickException("Not logged in. Run 'insighta login'.")

    exp = _decode_jwt_exp(at)
    if exp is not None and exp <= int(datetime.now(timezone.utc).timestamp()) + 15:
        creds = _refresh_tokens(creds)
        at = creds["access_token"]

    return {"Authorization": f"Bearer {at}", **API_VERSION_HEADER}


def call_api(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    req_headers = {**auth_headers(), **headers}
    res = requests.request(method, f"{api_url()}{path}", headers=req_headers, timeout=30, **kwargs)

    if res.status_code == 401:
        creds = _refresh_tokens(load_creds())
        req_headers["Authorization"] = f"Bearer {creds['access_token']}"
        res = requests.request(method, f"{api_url()}{path}", headers=req_headers, timeout=30, **kwargs)

    if res.status_code >= 400:
        try:
            msg = res.json().get("message") or res.json().get("error") or res.text
        except Exception:
            msg = res.text
        raise click.ClickException(f"{res.status_code}: {msg}")
    return res


class CallbackHandler(BaseHTTPRequestHandler):
    result = {"code": None, "state": None, "error": None}

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        CallbackHandler.result["code"] = query.get("code", [None])[0]
        CallbackHandler.result["state"] = query.get("state", [None])[0]
        CallbackHandler.result["error"] = query.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Insighta login complete. Return to terminal.</h2>")

    def log_message(self, *_):
        return


@click.group()
def cli():
    """Insighta Labs+ CLI"""


@cli.command()
def login():
    """Authenticate with GitHub OAuth + PKCE."""
    client_id = os.getenv("GITHUB_CLIENT_ID")
    if not client_id:
        raise click.ClickException("GITHUB_CLIENT_ID is required.")

    state = secrets.token_urlsafe(24)
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")

    server = HTTPServer(("127.0.0.1", 8765), CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    params = {
        "client_id": client_id,
        "redirect_uri": "http://127.0.0.1:8765/callback",
        "scope": "read:user user:email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    console.print("Opening browser for GitHub login...")
    webbrowser.open(auth_url)
    console.print(f"If needed, open manually: {auth_url}")
    thread.join(timeout=180)
    server.server_close()

    if CallbackHandler.result.get("error"):
        raise click.ClickException(f"OAuth failed: {CallbackHandler.result['error']}")
    if CallbackHandler.result.get("state") != state:
        raise click.ClickException("Invalid OAuth state.")
    if not CallbackHandler.result.get("code"):
        raise click.ClickException("OAuth code not received.")

    with console.status("Exchanging code for tokens..."):
        res = requests.post(
            f"{api_url()}/auth/github/token/",
            json={"code": CallbackHandler.result["code"], "code_verifier": verifier},
            timeout=30,
        )
    if res.status_code != 200:
        raise click.ClickException(f"Login failed: {res.text}")

    payload = res.json()
    creds = {
        "access_token": payload["access"],
        "refresh_token": payload["refresh"],
        "user": payload.get("user", {}),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_creds(creds)
    username = creds["user"].get("username", "unknown")
    console.print(f"Logged in as @{username}")


@cli.command()
def logout():
    """Logout and clear credentials."""
    creds = load_creds()
    rt = creds.get("refresh_token")
    if rt:
        try:
            call_api("POST", "/auth/logout/", json={"refresh": rt}, headers={"X-API-Version": "1"})
        except Exception:
            pass
    clear_creds()
    console.print("Logged out")


@cli.command()
def whoami():
    """Show current account."""
    res = call_api("GET", "/auth/me/", headers={"X-API-Version": "1"})
    data = res.json().get("data", {})
    t = Table(title="Account")
    t.add_column("Field")
    t.add_column("Value")
    for k in ["id", "username", "email", "role", "is_active"]:
        t.add_row(k, str(data.get(k)))
    console.print(t)


@cli.group()
def profiles():
    """Profiles operations."""


@profiles.command("list")
@click.option("--gender")
@click.option("--country")
@click.option("--age-group")
@click.option("--min-age", type=int)
@click.option("--max-age", type=int)
@click.option("--min-gender-probability", type=float)
@click.option("--min-country-probability", type=float)
@click.option("--sort-by")
@click.option("--order", type=click.Choice(["asc", "desc"]), default="asc")
@click.option("--page", type=int, default=1)
@click.option("--limit", type=int, default=10)
def list_profiles(gender, country, age_group, min_age, max_age, min_gender_probability, min_country_probability, sort_by, order, page, limit):
    params = {"page": page, "limit": limit}
    if gender:
        params["gender"] = gender
    if country:
        params["country_id"] = country
    if age_group:
        params["age_group"] = age_group
    if min_age is not None:
        params["min_age"] = min_age
    if max_age is not None:
        params["max_age"] = max_age
    if min_gender_probability is not None:
        params["min_gender_probability"] = min_gender_probability
    if min_country_probability is not None:
        params["min_country_probability"] = min_country_probability
    if sort_by:
        params["sort_by"] = sort_by
        params["order_by"] = order

    with console.status("Fetching profiles..."):
        body = call_api("GET", "/api/v2/profiles", params=params).json()

    rows = body.get("data", [])
    table = Table(title=f"Profiles (page {body.get('page')})")
    for col in ["id", "name", "gender", "age", "country_id", "created_at"]:
        table.add_column(col)
    for r in rows:
        table.add_row(str(r.get("id")), str(r.get("name")), str(r.get("gender")), str(r.get("age")), str(r.get("country_id")), str(r.get("created_at")))
    console.print(table)


@profiles.command("get")
@click.argument("profile_id")
def get_profile(profile_id):
    body = call_api("GET", f"/api/v2/profiles/{profile_id}").json()
    data = body.get("data", {})
    t = Table(title="Profile")
    t.add_column("Field")
    t.add_column("Value")
    for k, v in data.items():
        t.add_row(str(k), str(v))
    console.print(t)


@profiles.command("search")
@click.argument("query")
@click.option("--page", type=int, default=1)
@click.option("--limit", type=int, default=10)
def search_profiles(query, page, limit):
    with console.status("Searching profiles..."):
        body = call_api("GET", "/api/v2/profiles/search", params={"q": query, "page": page, "limit": limit}).json()
    table = Table(title="Search Results")
    for col in ["id", "name", "gender", "age", "country_id"]:
        table.add_column(col)
    for r in body.get("data", []):
        table.add_row(str(r.get("id")), str(r.get("name")), str(r.get("gender")), str(r.get("age")), str(r.get("country_id")))
    console.print(table)


@profiles.command("create")
@click.option("--name", required=True)
def create_profile(name):
    with console.status("Creating profile..."):
        body = call_api("POST", "/api/v2/profiles", json={"name": name}).json()
    console.print(f"Created profile: {body.get('data', {}).get('id')}")


@profiles.command("export")
@click.option("--format", "fmt", default="csv", type=click.Choice(["csv"]))
@click.option("--gender")
@click.option("--country")
@click.option("--age-group")
def export_profiles(fmt, gender, country, age_group):
    params = {"format": fmt}
    if gender:
        params["gender"] = gender
    if country:
        params["country_id"] = country
    if age_group:
        params["age_group"] = age_group
    with console.status("Exporting CSV..."):
        res = call_api("GET", "/api/v2/profiles/export/csv", params=params)
    filename = Path.cwd() / f"profiles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filename.write_bytes(res.content)
    console.print(f"Saved {filename}")


if __name__ == "__main__":
    cli()
