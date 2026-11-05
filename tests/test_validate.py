import datetime as dt
import json
import shutil
from pathlib import Path

import pytest

from validate_data import validate

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo(tmp_path):
    """複製一份目前的資料與知識庫，讓測試可以任意弄壞"""
    for d in ("data", "knowledge"):
        shutil.copytree(ROOT / d, tmp_path / d, ignore=shutil.ignore_patterns("raw", "status.json", "chunks"))
    return tmp_path


def edit(path, fn):
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def asof(repo):
    return dt.date.fromisoformat(json.loads((repo / "data" / "tw.json").read_text(encoding="utf-8"))["asof"])


def test_current_data_passes(repo):
    # 只擋「錯誤」（會停止發佈的問題）。「警告」例如央行利率來源 15 天沒更新，是外部資料的狀況，
    # 已經顯示在資料狀態頁並由每日更新開 Issue 通知；放在這裡會讓每個 PR 的 CI 都變紅，蓋過真正的程式錯誤。
    errors, warnings, status = validate(repo, today=asof(repo) + dt.timedelta(days=1))
    assert errors == [] and status["ok"], errors
    assert len(status["datasets"]) == 7
    assert all(d["state"] in ("ok", "warn") for d in status["datasets"]), [d["state"] for d in status["datasets"]]


def test_empty_stock_list_blocks_publish(repo):
    edit(repo / "data" / "tw.json", lambda d: d.update(stocks=[]))
    errors, _, status = validate(repo, today=asof(repo))
    assert any("個股只有 0 檔" in e for e in errors) and not status["ok"]


def test_bad_price_blocks_publish(repo):
    edit(repo / "data" / "tw.json", lambda d: d["stocks"][0].update(p=0))
    errors, _, _ = validate(repo, today=asof(repo))
    assert any("收盤價不合理" in e for e in errors)


def test_broken_json_blocks_publish(repo):
    (repo / "data" / "rates.json").write_text("{oops", encoding="utf-8")
    errors, _, status = validate(repo, today=asof(repo))
    assert errors and status["datasets"][3]["state"] == "error"


def test_missing_advisor_field_blocks_publish(repo):
    edit(repo / "knowledge" / "advisors.zh.json", lambda d: d["value"].pop("blind"))
    errors, _, _ = validate(repo, today=asof(repo))
    assert any("value.blind" in e for e in errors)


def test_stale_data_only_warns(repo):
    errors, warnings, status = validate(repo, today=asof(repo) + dt.timedelta(days=30))
    assert errors == [] and any("天沒更新" in w for w in warnings)
    assert status["datasets"][0]["state"] == "warn"


def test_failed_fetch_step_warns(repo):
    _, warnings, status = validate(repo, today=asof(repo), steps={"twse": {"outcome": "failure"}})
    assert any("抓取失敗" in w for w in warnings) and status["steps"] == {"twse": "failure"}
