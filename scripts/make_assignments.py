"""產生受試者編號與實驗連結（封閉招募用：課堂、實驗室、你自己發連結）。

用法：python scripts/make_assignments.py 120 > experiment-private/pids.csv
每 8 人一個區塊、區塊內四組各 2 人隨機排列（置換區塊隨機化），依報名順序發連結，任何時候四組人數最多差 2。
組別不寫在連結上：實驗頁用 condition_of(編號) 從編號本身算出組別（web/study.template.html 的 condOf 是同一個算法），
所以這份清單不必放上網站；它含有分組資訊，請存在 experiment-private/（已在 .gitignore），不要提交到公開 repo。
"""

import csv
import random
import sys

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉容易看錯的 I、O、0、1
CONDITIONS = 4
BLOCK = 8
URL = "https://nina-liang.github.io/advisor-roundtable/study.html?pid="


def condition_of(pid):
    """FNV-1a 32 位元雜湊取 4 的餘數：0 單一理專、1 只顯示共識、2 完整圓桌、3 自己調權重"""
    h = 0x811C9DC5
    for b in pid.strip().upper().encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h % CONDITIONS


def generate(n, seed=None):
    rnd = random.Random(seed)
    rows, seen = [], set()
    while len(rows) < n:
        block = [c for c in range(CONDITIONS) for _ in range(BLOCK // CONDITIONS)]
        rnd.shuffle(block)
        for cond in block[:n - len(rows)]:
            while True:
                pid = "".join(rnd.choice(ALPHABET) for _ in range(6))
                if pid not in seen and condition_of(pid) == cond:
                    break
            seen.add(pid)
            rows.append((pid, cond))
    return rows


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    w = csv.writer(sys.stdout)
    w.writerow(["order", "pid", "condition", "link"])
    for k, (pid, cond) in enumerate(generate(n), 1):
        w.writerow([k, pid, cond + 1, URL + pid])


if __name__ == "__main__":
    main()
