from __future__ import annotations

from pathlib import Path

import pytest

from app import app


def call(path: str) -> tuple[str, dict[str, str], str]:
    """The app's answer to a GET of `path`: status, headers, body."""
    said: dict = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        said["status"], said["headers"] = status, dict(headers)

    body = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": path}, start_response)).decode()
    return said["status"], said["headers"], body


@pytest.fixture(autouse=True)
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


def test_the_home_page_answers() -> None:
    status, headers, body = call("/")
    assert status == "200 OK" and headers["Content-Type"].startswith("text/html") and "<h1>Hello</h1>" in body


def test_health_answers_ok() -> None:
    assert call("/health")[0] == "200 OK"


def test_an_unknown_path_is_not_found() -> None:
    assert call("/nope")[0] == "404 Not Found"
