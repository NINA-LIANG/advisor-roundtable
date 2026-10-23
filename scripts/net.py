"""共用的網路請求：連不上、逾時或伺服器 5xx／429 時，等 2、4、8 秒再試，最多 4 次。

證交所、櫃買中心的 API 盤後偶爾很慢，一次失敗就放棄會少一天資料。
4xx（網址錯、被拒）重試也沒用，直接丟出。
"""

import sys
import time
import urllib.error
import urllib.request

WAITS = (2, 4, 8)
UA = "Mozilla/5.0 (compatible; advisor-roundtable; +https://github.com/NINA-LIANG/advisor-roundtable)"


def fetch(url, data=None, headers=None, timeout=60, waits=WAITS):
    """回傳回應內容（bytes）；最後一次仍失敗就把例外丟給呼叫端"""
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    for i, wait in enumerate((*waits, None), 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if wait is None or (e.code < 500 and e.code != 429):
                raise
            err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if wait is None:
                raise
            err = e
        print(f"retry {i}/{len(waits)}：{url[:90]}（{err}），{wait} 秒後再試", file=sys.stderr)
        time.sleep(wait)
