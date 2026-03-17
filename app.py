"""
공모전 정보 웹 서비스
- Flask 웹 서버
- APScheduler: 매일 오전 8시 자동 스크래핑
"""

import os
import threading
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db
import scraper

app = Flask(__name__)


# ─── 스케줄러 설정 ────────────────────────────────────────────
def scheduled_scrape():
    print(f"[스케줄러] 스크래핑 시작: {datetime.now()}")
    try:
        results = scraper.run_all_scrapers()
        added = db.upsert_contests(results)
        db.log_scrape(len(results), added, "success")
        print(f"[스케줄러] 완료: {len(results)}건 수집, {added}건 신규")
    except Exception as e:
        db.log_scrape(0, 0, f"error: {e}")
        print(f"[스케줄러] 오류: {e}")


scheduler = BackgroundScheduler(timezone="Asia/Seoul")
scheduler.add_job(
    scheduled_scrape,
    CronTrigger(hour=8, minute=0, timezone="Asia/Seoul"),
    id="daily_scrape",
    replace_existing=True,
)


# ─── 라우트 ───────────────────────────────────────────────────
@app.route("/")
def index():
    page = int(request.args.get("page", 1))
    keyword = request.args.get("q", "").strip()
    source = request.args.get("source", "").strip()
    category = request.args.get("category", "").strip()

    data = db.get_contests(
        page=page, per_page=20,
        source=source or None,
        keyword=keyword or None,
        category=category or None,
    )
    sources = db.get_sources()
    last_scrape = db.get_last_scrape()

    return render_template(
        "index.html",
        data=data,
        sources=sources,
        last_scrape=last_scrape,
        keyword=keyword,
        selected_source=source,
        selected_category=category,
    )


@app.route("/api/contests")
def api_contests():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    keyword = request.args.get("q", "").strip() or None
    source = request.args.get("source", "").strip() or None
    category = request.args.get("category", "").strip() or None

    data = db.get_contests(page=page, per_page=per_page,
                           source=source, keyword=keyword, category=category)
    return jsonify(data)


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """수동 스크래핑 트리거 (백그라운드)"""
    def _run():
        scheduled_scrape()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"status": "started", "message": "스크래핑이 백그라운드에서 시작되었습니다."})


@app.route("/api/status")
def api_status():
    last = db.get_last_scrape()
    next_run = None
    job = scheduler.get_job("daily_scrape")
    if job and job.next_run_time:
        next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({
        "last_scrape": last,
        "next_run": next_run,
        "scheduler_running": scheduler.running,
    })


# ─── 앱 시작 ─────────────────────────────────────────────────
def create_app():
    db.init_db()

    with db.get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM contests").fetchone()[0]

    if count == 0:
        print("[초기화] DB가 비어있어 첫 스크래핑을 시작합니다...")
        t = threading.Thread(target=scheduled_scrape, daemon=True)
        t.start()

    scheduler.start()
    print("[스케줄러] 매일 오전 8시(KST) 자동 갱신 설정 완료")
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=False)


# Gunicorn/Render 진입점
application = create_app()
