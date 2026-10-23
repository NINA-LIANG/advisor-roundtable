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
