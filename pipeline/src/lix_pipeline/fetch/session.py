"""Shared HTTP session with retries."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "uk-liveability-index/0.1 (+https://github.com/MysterionRise/uk-liveability-index)"


def make_session() -> requests.Session:
    """HTTP session that retries transient failures with exponential backoff."""
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = USER_AGENT
    return session
