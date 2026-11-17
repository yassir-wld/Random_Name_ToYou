import json

import pytest

from app.config import load_targets


def test_load_valid_targets(tmp_path):
    config = tmp_path / "targets.json"
    config.write_text(
        json.dumps([{"slug": "web", "name": "Website", "url": "https://example.org"}]),
        encoding="utf-8",
    )
    assert load_targets(config)[0].interval_seconds == 60


@pytest.mark.parametrize("url", ["file:///etc/passwd", "", "javascript:alert(1)"])
def test_reject_invalid_target_url(tmp_path, url):
    config = tmp_path / "targets.json"
    config.write_text(
        json.dumps([{"slug": "web", "name": "Website", "url": url}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_targets(config)


def test_duplicate_target_slug_is_rejected(tmp_path):
    config = tmp_path / "targets.json"
    item = {"slug": "web", "name": "Website", "url": "https://example.org"}
    config.write_text(json.dumps([item, item]), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_targets(config)
