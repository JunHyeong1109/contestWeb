"""스크래퍼 실행 후 결과를 docs/data/contests.json으로 저장"""

import json
import os
from datetime import datetime, timezone, timedelta
from scraper import run_all_scrapers

KST_OFFSET = timedelta(hours=9)


def main():
    results = run_all_scrapers()
    updated_at = (datetime.now(timezone.utc) + KST_OFFSET).strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs("docs/data", exist_ok=True)

    data = {
        "updated_at": updated_at,
        "count": len(results),
        "contests": results,
    }

    with open("docs/data/contests.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[완료] {len(results)}건 → docs/data/contests.json 저장 ({updated_at} KST)")


if __name__ == "__main__":
    main()
