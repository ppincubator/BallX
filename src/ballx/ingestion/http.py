"""Bounded provider downloads through inherited network policy; no credential-bearing URLs."""

import hashlib
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ALLOWED_HOSTS = {"cricsheet.org", "power.larc.nasa.gov", "opendatacommons.org"}


def checked_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Downloads require an approved HTTPS provider without URL credentials")
    return url


def download(
    url: str,
    destination: Path,
    *,
    max_bytes: int = 50 * 1024 * 1024,
    expected_sha256: str | None = None,
    client: httpx.Client | None = None,
) -> str:
    checked_url(url)
    owns_client = client is None
    client = client or httpx.Client(
        verify=ssl.create_default_context(),
        timeout=30,
        follow_redirects=False,
        headers={"User-Agent": "BallX-GPID/0.2 bounded research sample"},
    )
    try:
        for attempt in range(3):
            try:
                with client.stream("GET", url) as response:
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                        try:
                            delay = float(response.headers.get("Retry-After", 0.5 * 2**attempt))
                        except ValueError:
                            delay = 0.5 * 2**attempt
                        time.sleep(max(0, min(delay, 10)))
                        continue
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError(
                                "Provider response exceeds the configured download bound"
                            )
                        chunks.append(chunk)
                    payload = b"".join(chunks)
                digest = hashlib.sha256(payload).hexdigest()
                if expected_sha256 and digest != expected_sha256:
                    raise ValueError("Downloaded bytes differ from the pinned source snapshot")
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                temporary.write_bytes(payload)
                temporary.replace(destination)
                return digest
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == 2:
                    raise
                time.sleep(0.5 * 2**attempt)
        raise RuntimeError("Provider request exhausted retries")
    finally:
        if owns_client:
            client.close()
