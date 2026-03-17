"""
공모전 스크래퍼 (IT/컴퓨터공학 관련만 수집)
- 콘테스트코리아: IT 카테고리 전용 URL
"""

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# IT/컴퓨터공학 관련 키워드 (제목·카테고리·주최에 하나라도 포함되면 통과)
IT_KEYWORDS = [
    "IT", "SW", "AI", "소프트웨어", "프로그래밍", "코딩", "개발",
    "컴퓨터", "알고리즘", "데이터", "빅데이터", "클라우드", "인공지능",
    "머신러닝", "딥러닝", "웹", "앱", "모바일", "보안", "사이버",
    "해킹", "블록체인", "IoT", "핀테크", "디지털", "스마트", "게임",
    "네트워크", "데이터베이스", "임베디드", "로봇", "자율주행",
    "메타버스", "AR", "VR", "챗봇", "자연어", "컴퓨터공학", "정보보안",
    "정보통신", "전산", "ICT",
]


def _is_it_related(item: dict) -> bool:
    """IT/CS 관련 여부를 제목·카테고리·주최 텍스트로 판단"""
    target = " ".join([
        item.get("title", ""),
        item.get("category", ""),
        item.get("host", ""),
    ]).upper()
    return any(kw.upper() in target for kw in IT_KEYWORDS)


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
# 1. 콘테스트코리아 - IT 공모전 (Txt_bcode=030310001: 학문·과학·IT)
# ─────────────────────────────────────────────────────────────
def _fetch_page(url: str) -> list[dict]:
    resp = _get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    return _parse_ck_list(soup, "콘테스트코리아")


def scrape_contestkorea_contest(pages: int = 5) -> list[dict]:
    urls_template = [
        f"{BASE_CK}/sub/list.php?displayrow=20&int_gbn=1&Txt_bcode=030310001&page={{page}}",
        f"{BASE_CK}/sub/list.php?displayrow=20&int_gbn=1&Txt_sGn=1&Txt_key=all&Txt_word=IT&page={{page}}",
        f"{BASE_CK}/sub/list.php?displayrow=20&int_gbn=1&Txt_sGn=1&Txt_key=all&Txt_word=SW&page={{page}}",
        f"{BASE_CK}/sub/list.php?displayrow=20&int_gbn=1&Txt_sGn=1&Txt_key=all&Txt_word=AI&page={{page}}",
        f"{BASE_CK}/sub/list.php?displayrow=20&int_gbn=1&Txt_sGn=1&Txt_key=all&Txt_word=%EC%86%8C%ED%94%84%ED%8A%B8%EC%9B%A8%EC%96%B4&page={{page}}",
    ]
    all_urls = [
        tmpl.format(page=page)
        for tmpl in urls_template
        for page in range(1, pages + 1)
    ]

    seen_urls = set()
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_page, url): url for url in all_urls}
        for future in as_completed(futures):
            for item in future.result():
                if item["url"] not in seen_urls and _is_it_related(item):
                    seen_urls.add(item["url"])
                    results.append(item)

    print(f"[콘테스트코리아-공모전] {len(results)}건 수집 (IT 필터 적용)")
    return results


# ─────────────────────────────────────────────────────────────
# 통합 실행
# ─────────────────────────────────────────────────────────────
def run_all_scrapers() -> list[dict]:
    all_results = []
    scrapers = [
        ("콘테스트코리아-공모전", scrape_contestkorea_contest),
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
