"""OpenAPI 停更時改用證交所網站（2026-10 OpenAPI 停在 10/22 好幾天，網站股價跟著停）"""

import datetime as dt

import fetch_twse

OPENAPI_ROWS = [{"Code": "2330", "Name": "台積電", "TradeValue": "71537000000", "ClosingPrice": "2385.00",
                 "Change": "-35.0000", "Date": "1151022"}]
FIELDS = ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價",
          "漲跌(+/-)", "漲跌價差", "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量", "本益比"]


def mi_index(close, sign):
    row = ["2330", "台積電 ", "30,000,000", "90,000", "72,450,000,000", "2,400.00", "2,425.00", "2,390.00",
           close, f"<p style= color:red>{sign}</p>", "15.00", "", "", "", "", "28.10"]
    return {"stat": "OK", "tables": [{"title": "每日收盤行情", "fields": FIELDS, "data": [row]}]}


def fake_get(site):
    """site：{YYYYMMDD: MI_INDEX 回應}；沒列出的日期當作休市"""
    calls = []

    def get(url):
        calls.append(url)
        if "STOCK_DAY_ALL" in url:
            return OPENAPI_ROWS
        if "MI_INDEX" in url:
            return site.get(url.rsplit("date=", 1)[1], {"stat": "很抱歉，沒有符合條件的資料!"})
        raise AssertionError(url)
    return get, calls


def test_uses_site_when_openapi_is_stale(monkeypatch):
    get, _ = fake_get({"20261027": mi_index("2,410.00", "-")})
    monkeypatch.setattr(fetch_twse, "get", get)
    monkeypatch.setattr(fetch_twse.time, "sleep", lambda s: None)
    rows, asof, from_site = fetch_twse.latest_day_all(today=dt.date(2026, 10, 27))
    assert from_site and asof == dt.date(2026, 10, 27)
    r = rows[0]
    assert (r["Code"], r["Name"], r["ClosingPrice"], r["Change"], r["Date"]) == ("2330", "台積電", "2410.00", "-15.00", "1151027")
    assert fetch_twse.num(r["TradeValue"]) == 72450000000


def test_walks_back_past_holidays_and_before_close(monkeypatch):
    # 今天還沒收盤（網站沒資料），往回找到前一個交易日
    get, calls = fake_get({"20261026": mi_index("2,425.00", "+")})
    monkeypatch.setattr(fetch_twse, "get", get)
    monkeypatch.setattr(fetch_twse.time, "sleep", lambda s: None)
    rows, asof, _ = fetch_twse.latest_day_all(today=dt.date(2026, 10, 27))
    assert asof == dt.date(2026, 10, 26) and rows[0]["Change"] == "15.00"


def test_keeps_openapi_when_it_is_current(monkeypatch):
    get, calls = fake_get({})
    monkeypatch.setattr(fetch_twse, "get", get)
    rows, asof, from_site = fetch_twse.latest_day_all(today=dt.date(2026, 10, 22))
    assert not from_site and asof == dt.date(2026, 10, 22) and rows is OPENAPI_ROWS
    assert not any("MI_INDEX" in u for u in calls)


def test_keeps_openapi_when_site_has_nothing_newer(monkeypatch):
    get, _ = fake_get({})
    monkeypatch.setattr(fetch_twse, "get", get)
    monkeypatch.setattr(fetch_twse.time, "sleep", lambda s: None)
    rows, asof, from_site = fetch_twse.latest_day_all(today=dt.date(2026, 10, 25))
    assert not from_site and asof == dt.date(2026, 10, 22)


def test_site_bwibbu_matches_openapi_keys(monkeypatch):
    resp = {"stat": "OK", "fields": ["證券代號", "證券名稱", "收盤價", "殖利率(%)", "股利年度", "本益比", "股價淨值比", "財報年/季"],
            "data": [["2330", "台積電", "2410.00", "0.91", "114", "27.90", "9.70", "115/2"]]}
    monkeypatch.setattr(fetch_twse, "get", lambda url: resp)
    bw = fetch_twse.site_bwibbu(dt.date(2026, 10, 27))
    assert bw == {"2330": {"PEratio": "27.90", "DividendYield": "0.91", "PBratio": "9.70"}}
