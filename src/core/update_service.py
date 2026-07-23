"""Check for updates via GitHub Releases API."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class UpdateInfo:
    version: str
    url: str
    notes: str


def parse_version(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(p) for p in parts) if parts else (0,)


def is_newer(current: str, latest: str) -> bool:
    return parse_version(latest) > parse_version(current)


def check_github_release(repo: str, current_version: str) -> UpdateInfo | None:
    repo = repo.strip().strip("/")
    if not repo or "/" not in repo:
        return None

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        response = requests.get(
            url,
            timeout=12,
            headers={"Accept": "application/vnd.github+json"},
        )
        if response.status_code != 200:
            logger.info("Update check failed: HTTP %s", response.status_code)
            return None
        data = response.json()
        tag = (data.get("tag_name") or "").lstrip("v")
        if not tag or not is_newer(current_version, tag):
            return None
        return UpdateInfo(
            version=tag,
            url=data.get("html_url") or f"https://github.com/{repo}/releases/latest",
            notes=(data.get("body") or "")[:500],
        )
    except Exception as exc:
        logger.warning("Update check error: %s", exc)
        return None
