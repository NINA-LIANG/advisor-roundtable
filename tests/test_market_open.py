import datetime as dt

from market_open import closed_days, is_open, to_date

ROWS = [
    {"Name": "中華民國開國紀念日", "Date": "1150101", "Weekday": "四", "Description": "依規定放假1日。"},
    {"Name": "國曆新年開始交易", "Date": "1150102", "Weekday": "五", "Description": ""},
    {"Name": "農曆春節前最後交易日", "Date": "1150211", "Weekday": "三", "Description": ""},
    {"Name": "國慶日", "Date": "115/10/09", "Weekday": "五", "Description": "補假"},
]


def test_date_formats():
    assert to_date("1150101") == dt.date(2026, 1, 1)
    assert to_date("115/10/09") == dt.date(2026, 10, 9)
    assert to_date("20261009") == dt.date(2026, 10, 9)
    assert to_date("") is None


def test_trading_days_in_list_are_not_holidays():
    closed = closed_days(ROWS)
    assert closed == {dt.date(2026, 1, 1), dt.date(2026, 10, 9)}


def test_is_open():
    closed = closed_days(ROWS)
    assert not is_open(dt.date(2026, 1, 1), closed)
    assert is_open(dt.date(2026, 1, 2), closed)
    assert not is_open(dt.date(2026, 10, 24), closed)  # 星期六
    assert is_open(dt.date(2026, 10, 23), closed)


def test_trade_day_survives_late_schedule():
    """GitHub 排程延後到隔天凌晨，仍算前一個交易日（10/30 星期五曾被誤判成週末）"""
    from market_open import TPE, trade_day
    assert trade_day(dt.datetime(2026, 10, 30, 18, 47, tzinfo=TPE)) == dt.date(2026, 10, 30)
    assert trade_day(dt.datetime(2026, 10, 31, 0, 46, tzinfo=TPE)) == dt.date(2026, 10, 30)
    assert trade_day(dt.datetime(2026, 11, 4, 4, 27, tzinfo=TPE)) == dt.date(2026, 11, 3)
    assert trade_day(dt.datetime(2026, 10, 30, 10, 47, tzinfo=dt.timezone.utc)) == dt.date(2026, 10, 30)


def test_backup_schedule_skips_when_already_updated(tmp_path):
    import json
    from market_open import already_done
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "tw.json").write_text(json.dumps({"asof": "2026-11-03"}), encoding="utf-8")
    assert already_done(dt.date(2026, 11, 3), tmp_path)
    assert not already_done(dt.date(2026, 11, 4), tmp_path)
    assert not already_done(dt.date(2026, 11, 4), tmp_path / "missing")
