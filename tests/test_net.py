import io
import urllib.error

import pytest

import net


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake(monkeypatch, outcomes):
    calls, waits = [], []
    monkeypatch.setattr(net.time, "sleep", waits.append)

    def urlopen(req, timeout):
        calls.append(req.full_url)
        o = outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return Resp(o)

    monkeypatch.setattr(net.urllib.request, "urlopen", urlopen)
    return calls, waits


def http(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


def test_retries_until_success(monkeypatch):
    calls, waits = fake(monkeypatch, [urllib.error.URLError("down"), http(503), b"ok"])
    assert net.fetch("https://x") == b"ok"
    assert len(calls) == 3 and waits == [2, 4]


def test_gives_up_after_last_wait(monkeypatch):
    calls, waits = fake(monkeypatch, [TimeoutError()] * 4)
    with pytest.raises(TimeoutError):
        net.fetch("https://x")
    assert len(calls) == 4 and waits == [2, 4, 8]


def test_client_error_is_not_retried(monkeypatch):
    calls, waits = fake(monkeypatch, [http(404)])
    with pytest.raises(urllib.error.HTTPError):
        net.fetch("https://x")
    assert len(calls) == 1 and waits == []


def test_rate_limit_is_retried(monkeypatch):
    calls, _ = fake(monkeypatch, [http(429), b"ok"])
    assert net.fetch("https://x") == b"ok" and len(calls) == 2


def test_retries_when_download_is_cut_off(monkeypatch):
    # 2026-10-27 起每日更新的上市櫃清單都因為 ISIN 頁下載到一半被切斷而沒更新
    import http.client
    calls, waits = fake(monkeypatch, [http.client.IncompleteRead(b"x" * 10, 100), b"full"])
    assert net.fetch("https://x") == b"full"
    assert len(calls) == 2 and waits == [2]
