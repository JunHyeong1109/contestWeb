"""
공모전 스크래퍼
- 콘테스트코리아 (contestkorea.com) ← 공모전/대외활동, SSR 안정적
- 링커리어 (api.linkareer.com)      ← GraphQL API
"""

import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

TIMEOUT = 15
BASE_CK = "https://www.contestkorea.com"


def _get(url, **kwargs):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"[GET] {url[:60]} -> {e}")
        return None


def _parse_ck_list(soup: BeautifulSoup, source_name: str) -> list[dict]:
    """콘테스트코리아 .list_wrap li 항목을 파싱하여 반환"""
    results = []
    items = [li for li in soup.select(".list_wrap li")
             if li.select_one('a[href*="view.php"]')]

    for li in items:
        a_tag = li.select_one('a[href*="view.php"]')
        if not a_tag:
            continue

        href = a_tag.get("href", "")
        if href.startswith("http"):
            link = href
        elif href.startswith("/"):
            link = BASE_CK + href
        else:
            link = BASE_CK + "/sub/" + href

        title_tag = li.select_one("span.txt")
        title = title_tag.get_text(strip=True) if title_tag else a_tag.get_text(strip=True)
        if not title:
            continue

        category = ""
        cat_tag = li.select_one("span.category")
        if cat_tag:
            category = cat_tag.get_text(strip=True)

        host = ""
        host_tag = li.select_one("ul.host li.icon_1")
        if host_tag:
            raw = host_tag.get_text(strip=True)
            host = raw.replace("주최", "").replace(".", "").strip()

        deadline = ""
        step1 = li.select_one("span.step-1")
        if step1:
            text = step1.get_text(strip=True)
            if "~" in text:
                deadline = text.split("~")[-1].strip()
            else:
                deadline = text.replace("접수", "").strip()

        thumb = ""
        img = li.select_one("img[src]")
        if img:
            src = img.get("src", "")
            if src and not src.endswith(".gif") and not src.endswith(".png"):
                thumb = src if src.startswith("http") else BASE_CK + src

        results.append({
            "title": title,
            "url": link,
            "source": source_name,
            "category": category,
            "deadline": deadline,
            "host": host,
            "prize": "",
            "thumbnail": thumb,
        })

    return results


# ─────────────────────────────────────────────────────────────
# 1. 콘테스트코리아 - 공모전 (int_gbn=1)
# ─────────────────────────────────────────────────────────────
def scrape_contestkorea_contest(pages: int = 5) -> list[dict]:
    results = []
    for page in range(1, pages + 1):
        url = (
            f"{BASE_CK}/sub/list.php"
            f"?displayrow=20&int_gbn=1&Txt_sGn=1&Txt_key=all&page={page}"
        )
        resp = _get(url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        items = _parse_ck_list(soup, "콘테스트코리아")
        if not items:
            break
        results.extend(items)
        time.sleep(0.6)

    print(f"[콘테스트코리아-공모전] {len(results)}건 수집")
    return results


# ─────────────────────────────────────────────────────────────
# 2. 콘테스트코리아 - 대외활동 (int_gbn=2)
# ─────────────────────────────────────────────────────────────
def scrape_contestkorea_activity(pages: int = 3) -> list[dict]:
    results = []
    for page in range(1, pages + 1):
        url = (
            f"{BASE_CK}/sub/list.php"
            f"?displayrow=20&int_gbn=2&Txt_sGn=1&Txt_key=all&page={page}"
        )
        resp = _get(url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        items = _parse_ck_list(soup, "콘테스트코리아-대외활동")
        if not items:
            break
        results.extend(items)
        time.sleep(0.6)

    print(f"[콘테스트코리아-대외활동] {len(results)}건 수집")
    return results


# ─────────────────────────────────────────────────────────────
# 3. 링커리어 - GraphQL API
#    activityTypeID=3 → 공모전, =1 → 대외활동
# ─────────────────────────────────────────────────────────────
def _linkareer_fetch(type_id: int, source_name: str) -> list[dict]:
    api_url = "https://api.linkareer.com/graphql"
    headers = {
        **HEADERS,
        "Content-Type": "application/json",
        "Origin": "https://linkareer.com",
        "Referer": "https://linkareer.com/",
    }
    query = """
    query($filterBy: ActivityFilter, $orderBy: ActivityOrder) {
        activities(filterBy: $filterBy, orderBy: $orderBy) {
            totalCount
            nodes {
                id
                title
                organizationName
                deadlineStatus
                activityType { name }
                posterImage { url }
            }
        }
    }
    """
    variables = {
        "filterBy": {"activityTypeID": type_id},
        "orderBy": {"field": "CREATED_AT", "direction": "DESC"},
    }
    try:
        resp = requests.post(
            api_url,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=TIMEOUT,
        )
        data = resp.json()
        if "errors" in data:
            print(f"[{source_name}] GraphQL 오류: {data['errors'][0]['message']}")
            return []

        nodes = data.get("data", {}).get("activities", {}).get("nodes", [])
        results = []
        for node in nodes:
            # REJECTED(마감/반려) 제외
            if node.get("deadlineStatus") in ("REJECTED", "CLOSED"):
                continue

            link = f"https://linkareer.com/activity/{node.get('id', '')}"
            thumb = ""
            poster = node.get("posterImage") or {}
            if poster.get("url"):
                thumb = poster["url"]

            results.append({
                "title": node.get("title", ""),
                "url": link,
                "source": source_name,
                "category": (node.get("activityType") or {}).get("name", ""),
                "deadline": "",
                "host": node.get("organizationName", ""),
                "prize": "",
                "thumbnail": thumb,
            })
        return results

    except Exception as e:
        print(f"[{source_name}] 오류: {e}")
        return []


def scrape_linkareer() -> list[dict]:
    results = []
    # 공모전 (typeID=3)
    results.extend(_linkareer_fetch(3, "링커리어-공모전"))
    time.sleep(0.5)
    # 대외활동 (typeID=1)
    results.extend(_linkareer_fetch(1, "링커리어-대외활동"))

    # URL 중복 제거
    seen, deduped = set(), []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            deduped.append(r)

    print(f"[링커리어] {len(deduped)}건 수집")
    return deduped


# ─────────────────────────────────────────────────────────────
# 통합 실행
# ─────────────────────────────────────────────────────────────
def run_all_scrapers() -> list[dict]:
    all_results = []
    scrapers = [
        ("콘테스트코리아-공모전", scrape_contestkorea_contest),
        ("콘테스트코리아-대외활동", scrape_contestkorea_activity),
        ("링커리어", scrape_linkareer),
    ]
    for name, fn in scrapers:
        try:
            data = fn()
            all_results.extend(data)
        except Exception as e:
            print(f"[{name}] 스크래퍼 오류: {e}")

    print(f"[전체] 총 {len(all_results)}건 수집 완료")
    return all_results


if __name__ == "__main__":
    results = run_all_scrapers()
    for r in results[:5]:
        print(r["source"], "|", r["title"][:40], "|", r["deadline"])
