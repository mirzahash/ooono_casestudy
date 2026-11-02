"""Fetch API pages with bounded retries and local resume checkpoints.

Called by run_pipeline.py and ingest.py; no direct CLI or Snowflake writes.
Return extraction metadata while saving response bytes under data/.
Failures retain saved pages; tokens are not written to checkpoints."""

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


# Get the current date and time in UTC.
def utc_now():
    """Return the current timezone-aware UTC timestamp as an ISO string."""
    return datetime.now(timezone.utc).isoformat()


# Calculate a file checksum so we can detect changes to its contents.
def sha256(path):
    """Return a file's SHA-256 hexadecimal checksum, reading in 1 MiB chunks."""
    digest = hashlib.sha256()
    # The context manager closes the file even on failure. iter(callable, sentinel)
    # reads chunks until b"" signals EOF, keeping checksum memory use bounded.
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# Save JSON through a temporary file so readers do not see a partial write.
def atomic_json(path, value):
    """Serialize value to JSON and replace path after the write completes."""
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    # Rename a sibling temporary file only after serialization completes. A failed
    # write leaves the previous checkpoint intact; parent directories are caller-owned.
    temp.replace(path)


class EventsAPI:
    """A reusable HTTP session with lazy OAuth authentication and saved pagination."""
    # Load API settings and prepare a reusable HTTP connection session.
    def __init__(self):
        """Load project-local settings and create an unauthenticated requests session."""
        # Locate .env relative to this module, not the notebook or shell working directory.
        # Loading configuration here keeps importing shared helpers free of network calls.
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.session = requests.Session()
        self.authenticated = False

    # Get an access token so we can request API data.
    def authenticate(self):
        """Obtain a client-credentials token and store it on the session headers."""
        credentials = {"grant_type": "client_credentials", "client_id": os.getenv("OOONO_CLIENT_ID"),
                       "client_secret": os.getenv("OOONO_CLIENT_SECRET")}
        if not credentials["client_id"] or not credentials["client_secret"]:
            raise ValueError("Configure the API credentials locally")
        response = self.session.post(f"{BASE_URL}/oauth/token", data=credentials, timeout=(10, 60))
        if response.status_code != 200:
            raise RuntimeError(f"API authentication HTTP {response.status_code}; body hidden")
        self.session.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        self.authenticated = True

    # Request one API page and retry certain temporary failures.
    def get(self, endpoint, params):
        """Return a successful Response for endpoint and query params, or raise."""
        if not self.authenticated:
            self.authenticate()
        renewed = False
        # Bound retries so a broken source does not loop forever. Token renewal consumes
        # an attempt too; authentication POST failures are not retried by this block.
        for attempt in range(4):
            try:
                response = self.session.get(f"{BASE_URL}/v1/{endpoint}", params=params, timeout=(10, 60))
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 3:
                    raise RuntimeError("API request failed; resumable pages retained") from None
                # Exponential backoff slows repeated failures; jitter reduces synchronized
                # retries by clients that encountered the same outage.
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

    # Download all pages, saving progress so an interrupted extraction can resume.
    def extract(self, endpoint, directory, received_since=None, max_pages=2000):
        """Fetch/resume endpoint pages and return the complete checkpoint.

        Validate saved hashes and request scope before reuse. Follow next_cursor,
        not page length; users reject received_since. Corrupt pages, repeated
        cursors or max_pages stop extraction. Resume requires a valid API cursor."""
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
        # Trust a resume only after rechecking every previously checkpointed page. This
        # is file-integrity verification, not revalidation against the live API.
        for page in state["pages"]:
            if sha256(directory / page["file"]) != page["sha256"]:
                raise ValueError("Previously saved API page checksum mismatch")
        while not state["complete"] and len(state["pages"]) < max_pages:
            # A requested size is not proof of returned size. Completion below depends on
            # next_cursor, so server-capped or short pages do not truncate the extraction.
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
            # Publish page metadata only after the response file is safely replaced. A crash
            # before checkpoint replacement may refetch the page rather than skip it.
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
            raise RuntimeError("Page guard reached; extraction is incomplete and cannot load")
        return state
