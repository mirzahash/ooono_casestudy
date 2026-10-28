"""Small checkpointed API extractor. Frozen pages retain whole response bodies."""

import hashlib
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_URL = "https://qw7ytrkpd3swtndax6c4a73oua0mcrky.lambda-url.eu-west-1.on.aws"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.replace(path)


class EventsAPI:
    def __init__(self):
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.session = requests.Session()
        self.authenticated = False

    def authenticate(self):
        credentials = {"grant_type": "client_credentials", "client_id": os.getenv("OOONO_CLIENT_ID"),
                       "client_secret": os.getenv("OOONO_CLIENT_SECRET")}
        if not credentials["client_id"] or not credentials["client_secret"]:
            raise ValueError("Configure the API credentials locally")
        response = self.session.post(f"{BASE_URL}/oauth/token", data=credentials, timeout=(10, 60))
        if response.status_code != 200:
            raise RuntimeError(f"API authentication HTTP {response.status_code}; body hidden")
        self.session.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        self.authenticated = True

    def get(self, endpoint, params):
        if not self.authenticated:
            self.authenticate()
        renewed = False
        for attempt in range(4):
            try:
                response = self.session.get(f"{BASE_URL}/v1/{endpoint}", params=params, timeout=(10, 60))
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 3:
                    raise RuntimeError("API request failed; resumable pages retained") from None
                time.sleep(2 ** attempt + random.random())
                continue
            if response.status_code == 401 and not renewed:
                self.authenticate()
                renewed = True
                continue
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 3:
                retry_after = response.headers.get("Retry-After", "")
                time.sleep(float(retry_after) if retry_after.isdigit() else 2 ** attempt + random.random())
                continue
            if response.status_code != 200:
                raise RuntimeError(f"API HTTP {response.status_code}; response body hidden")
            return response
        raise RuntimeError("API retry budget exhausted")

    def extract(self, endpoint, directory, received_since=None, max_pages=2000):
        if endpoint not in {"drives", "warnings", "users"}:
            raise ValueError("Unsupported endpoint")
        if endpoint == "users" and received_since:
            raise ValueError("Users have no documented incremental receipt filter")
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        state_path = directory / "checkpoint.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {
            "endpoint": endpoint, "received_since": received_since, "started_at": utc_now(),
            "next_cursor": None, "seen_cursors": [], "pages": [], "complete": False,
        }
        if state["endpoint"] != endpoint or state["received_since"] != received_since:
            raise ValueError("Checkpoint request scope differs; use a new extraction directory")
        for page in state["pages"]:
            if sha256(directory / page["file"]) != page["sha256"]:
                raise ValueError("Previously saved API page checksum mismatch")
        while not state["complete"] and len(state["pages"]) < max_pages:
            params = {"limit": 1000}
            if received_since:
                params["received_since"] = received_since
            if state["next_cursor"]:
                params["cursor"] = state["next_cursor"]
            started_at = utc_now()
            response = self.get(endpoint, params)
            finished_at = utc_now()
            payload = response.json()
            if not isinstance(payload.get("data"), list) or "next_cursor" not in payload:
                raise ValueError("Unexpected API envelope")
            cursor = payload["next_cursor"]
            if cursor and cursor in state["seen_cursors"]:
                raise ValueError("Repeated cursor; extraction stopped")
            name = f"page_{len(state['pages']):05d}.json"
            page_path = directory / name
            # Response JSON bytes, not reserialized: preserve the whole original envelope.
            temporary = page_path.with_suffix(".tmp")
            temporary.write_bytes(response.content)
            temporary.replace(page_path)
            state["pages"].append({"file": name, "rows": len(payload["data"]),
                                   "sha256": sha256(page_path), "started_at": started_at,
                                   "finished_at": finished_at})
            state["next_cursor"] = cursor
            if cursor:
                state["seen_cursors"].append(cursor)
            state["complete"] = not bool(cursor)
            state["finished_at"] = finished_at
            atomic_json(state_path, state)
        if not state["complete"]:
            raise RuntimeError("Page guard reached; snapshot is incomplete and cannot load")
        return state
