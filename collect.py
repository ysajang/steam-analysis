#!/usr/bin/env python3
"""
Steam Analysis - 실데이터 수집기
SteamSpy(상위 1000) + 개별 태그/장르 + Steam Store 출시일을 수집해 data/games.json 생성.

특징:
- rate limit 안전마진 (SteamSpy 개별 1.2s, Store 1.5s 간격)
- 재시도(지수 백오프) + 429 대응
- 중단 재개: enrich 캐시(data/_enrich_cache.json)에 개별 결과를 즉시 굳혀
  중간에 끊겨도 다시 실행하면 남은 것만 이어서 수집
- 최종 산출물 data/games.json 은 대시보드가 읽는 단일 파일

사용:
  python collect.py                # 상위 1000개 전량 수집
  python collect.py --limit 50     # 테스트용 상위 50개만
  python collect.py --skip-store   # Store 출시일 생략(SteamSpy만, 빠름)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

# ---- 경로 ----
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
GAMES_JSON = os.path.join(DATA_DIR, "games.json")
ENRICH_CACHE = os.path.join(DATA_DIR, "_enrich_cache.json")

# ---- 설정 ----
STEAMSPY_ALL = "https://steamspy.com/api.php?request=all&page=0"
STEAMSPY_DETAIL = "https://steamspy.com/api.php?request=appdetails&appid={appid}"
STORE_DETAIL = (
    "https://store.steampowered.com/api/appdetails"
    "?appids={appid}&filters=basic,release_date,genres,price_overview"
)
HEADERS = {"User-Agent": "personal-steam-analysis/1.0"}

STEAMSPY_INTERVAL = 1.2   # 초. SteamSpy 개별 호출 간격(초당 1회 권장 대비 안전마진)
STORE_INTERVAL = 1.5      # 초. Store API는 더 보수적으로
MAX_RETRIES = 4
TIMEOUT = 25


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_json(url, retries=MAX_RETRIES):
    """지수 백오프 재시도 + 429 처리. 실패 시 None."""
    backoff = 2.0
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                wait = backoff * attempt
                log(f"  429 rate limited, {wait:.0f}s 대기 후 재시도 ({attempt}/{retries})")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == retries:
                log(f"  실패(최종): {e}")
                return None
            wait = backoff * attempt
            log(f"  오류 {e} → {wait:.0f}s 후 재시도 ({attempt}/{retries})")
            time.sleep(wait)
    return None


def parse_owners(owners_str):
    """'100,000 .. 200,000' → 중간값 정수. 소유자 추정치."""
    try:
        lo, hi = owners_str.replace(",", "").split("..")
        return (int(lo.strip()) + int(hi.strip())) // 2
    except Exception:
        return 0


def to_quarter(date_str):
    """'Sep 17, 2020' → '2020-Q3'. 파싱 실패 시 None."""
    if not date_str:
        return None
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%b %Y", "%Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
        except ValueError:
            continue
    return None


def load_cache():
    if os.path.exists(ENRICH_CACHE):
        with open(ENRICH_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(ENRICH_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def collect(limit=None, skip_store=False):
    os.makedirs(DATA_DIR, exist_ok=True)

    # 1) SteamSpy 상위 1000 (소유자순)
    log("SteamSpy 상위 목록 수집 중...")
    top = fetch_json(STEAMSPY_ALL)
    if not top:
        log("치명적: 상위 목록 수집 실패. 종료.")
        sys.exit(1)

    appids = list(top.keys())
    if limit:
        appids = appids[:limit]
    log(f"대상 게임 수: {len(appids)}")

    cache = load_cache()
    log(f"기존 캐시: {len(cache)}개 (재개 가능)")

    total = len(appids)
    for i, appid in enumerate(appids, 1):
        if appid in cache and cache[appid].get("_complete"):
            continue

        base = top[appid]
        entry = cache.get(appid, {})

        # 2) SteamSpy 개별: 태그 + 장르
        if "tags" not in entry:
            detail = fetch_json(STEAMSPY_DETAIL.format(appid=appid))
            time.sleep(STEAMSPY_INTERVAL)
            if detail:
                entry["tags"] = detail.get("tags", {}) or {}
                entry["genre"] = detail.get("genre", "") or ""
            else:
                entry["tags"] = {}
                entry["genre"] = ""

        # 3) Steam Store: 출시일 + type + is_free
        if not skip_store and "release_quarter" not in entry:
            store = fetch_json(STORE_DETAIL.format(appid=appid))
            time.sleep(STORE_INTERVAL)
            rel_date = None
            gtype = "game"
            is_free = base.get("price") == "0"
            if store and store.get(appid, {}).get("success"):
                sd = store[appid]["data"]
                rel_date = (sd.get("release_date") or {}).get("date")
                gtype = sd.get("type", "game")
                is_free = sd.get("is_free", is_free)
            entry["release_date"] = rel_date
            entry["release_quarter"] = to_quarter(rel_date)
            entry["type"] = gtype
            entry["is_free"] = is_free

        entry["_complete"] = True if (skip_store or "release_quarter" in entry) else False
        cache[appid] = entry

        # 즉시 굳히기(중단 대비) — 20개마다 디스크 flush
        if i % 20 == 0 or i == total:
            save_cache(cache)
            pct = i / total * 100
            log(f"진행 {i}/{total} ({pct:.0f}%)")

    save_cache(cache)

    # 4) 최종 병합 → games.json
    log("최종 병합 중...")
    games = []
    for appid in appids:
        base = top[appid]
        enr = cache.get(appid, {})
        tags = enr.get("tags", {})
        games.append({
            "appid": int(appid),
            "name": base.get("name"),
            "developer": base.get("developer", ""),
            "publisher": base.get("publisher", ""),
            "positive": base.get("positive", 0),
            "negative": base.get("negative", 0),
            "owners_mid": parse_owners(base.get("owners", "0 .. 0")),
            "owners_raw": base.get("owners", ""),
            "price_cents": int(base.get("price") or 0),
            "ccu": base.get("ccu", 0),
            "genre": enr.get("genre", ""),
            "tags": tags,
            "top_tag": max(tags, key=tags.get) if tags else None,
            "release_date": enr.get("release_date"),
            "release_quarter": enr.get("release_quarter"),
            "type": enr.get("type", "game"),
            "is_free": enr.get("is_free", base.get("price") == "0"),
        })

    payload = {
        "schema": "steam-analysis.v1",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "count": len(games),
        "source": "SteamSpy + Steam Store API",
        "games": games,
    }
    with open(GAMES_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    log(f"완료 → {GAMES_JSON} ({len(games)}개)")
    quarters = sorted({g["release_quarter"] for g in games if g["release_quarter"]})
    log(f"출시 분기 커버리지: {len(quarters)}개 분기 ({quarters[0] if quarters else '-'} ~ {quarters[-1] if quarters else '-'})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="상위 N개만 수집(테스트용)")
    ap.add_argument("--skip-store", action="store_true", help="Store 출시일 생략(빠름)")
    args = ap.parse_args()
    collect(limit=args.limit, skip_store=args.skip_store)
