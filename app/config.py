"""Load and validate the targets managed by the worker."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class TargetConfig:
    slug: str
    name: str
    url: str
    interval_seconds: int = 60
    timeout_seconds: float = 5.0


def load_targets(path: str | Path | None = None) -> list[TargetConfig]:
    path = Path(path or os.getenv("TARGETS_FILE", "config/targets.json"))
    content = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(content, list):
        raise ValueError("Target configuration must be a JSON list")

    targets = []
    seen = set()
    for item in content:
        target = TargetConfig(**item)
        parsed = urlsplit(target.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Invalid URL for {target.slug}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", target.slug):
            raise ValueError(f"Invalid slug: {target.slug}")
        if target.slug in seen:
            raise ValueError(f"Duplicate slug: {target.slug}")
        if not 5 <= target.interval_seconds <= 86400:
            raise ValueError(f"Invalid interval for {target.slug}")
        if not 0 < target.timeout_seconds <= 30:
            raise ValueError(f"Invalid timeout for {target.slug}")
        seen.add(target.slug)
        targets.append(target)
    return targets
