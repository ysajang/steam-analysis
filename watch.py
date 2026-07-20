#!/usr/bin/env python3
"""
워치리스트 수집기 — SteamSpy 사각지대 우회
data/watchlist.json 에 등록된 appid를 Steam 공식 API로 직접 조회해
data/watchlist_data.json 을 생성/갱신한다.

소스 (전부 공식·무키):
- CCU:    ISteamUserStats/GetNumberOfCurrentPlayers  (실시간 동접)
- 리뷰:   store.steampowered.com/appreviews          (총 리뷰·긍정률 = 판매 대리지표)
- 상세:   store.steampowered.com/api/appdetails      (이름·가격·출시일·장르)

이력: 실행할 때마다 history 배열에 (시각, CCU, 리뷰수) 1줄 추가 → 리뷰 증가속도 추적.

사용:
  python watch.py                 # 워치리스트 전체 갱신
  python watch.py --add 4704690   # appid 추가 후 갱신
  python watch.py --remove 559650 # appid 제거
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
WATCHLIST = os.path.join(DATA_DIR, "watchlist.json")
WATCH_DATA = os.path.join(DATA_DIR, "watchlist_data.json")

CCU_API = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"
REVIEWS_API = "https://store.steampowered.com/appreviews/{appid}?json=1&language=all&purchase_type=all&num_per_page=0"
DETAILS_API = "https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic,release_date,genres,price_overview"
HEADERS = {"User-Agent": "personal-steam-analysis/1.0"}
INTERVAL = 1.5
TIMEOUT = 20
MAX_RETRIES = 3


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_json(url):
    backoff = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(backoff * attempt)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == MAX_RETRIES:
                log(f"  실패: {e}")
                return None
            time.sleep(backoff * attempt)
    return None


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def to_quarter(date_str):
    if not date_str:
        return None
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%b %Y", "%Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
        except ValueError:
            continue
    return None


def collect_one(appid, prev_entry):
    """appid 하나를 공식 API 3종으로 조회. 이력은 prev에서 이어받는다."""
    entry = {"appid": appid, "history": (prev_entry or {}).get("history", [])}

    ccu = fetch_json(CCU_API.format(appid=appid))
    time.sleep(INTERVAL)
    entry["ccu"] = (ccu or {}).get("response", {}).get("player_count", 0)

    rev = fetch_json(REVIEWS_API.format(appid=appid))
    time.sleep(INTERVAL)
    qs = (rev or {}).get("query_summary", {}) or {}
    entry["total_reviews"] = qs.get("total_reviews", 0)
    entry["positive"] = qs.get("total_positive", 0)
    entry["negative"] = qs.get("total_negative", 0)
    entry["review_score_desc"] = qs.get("review_score_desc", "")

    det = fetch_json(DETAILS_API.format(appid=appid))
    time.sleep(INTERVAL)
    d = ((det or {}).get(str(appid)) or {})
    if d.get("success"):
        sd = d["data"]
        entry["name"] = sd.get("name", f"appid {appid}")
        entry["is_free"] = sd.get("is_free", False)
        po = sd.get("price_overview") or {}
        entry["price_cents"] = po.get("final", 0)
        rel = (sd.get("release_date") or {}).get("date")
        entry["release_date"] = rel
        entry["release_quarter"] = to_quarter(rel)
        entry["genres"] = [g["description"] for g in sd.get("genres", [])]
    else:
        # 상세 실패 시 이전 값 유지
        for k in ("name", "is_free", "price_cents", "release_date", "release_quarter", "genres"):
            entry[k] = (prev_entry or {}).get(k)
        entry["name"] = entry["name"] or f"appid {appid}"

    entry["history"].append({
        "at": datetime.now(timezone.utc).isoformat(),
        "ccu": entry["ccu"],
        "total_reviews": entry["total_reviews"],
    })
    entry["history"] = entry["history"][-200:]  # 이력 상한
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", type=int, help="워치리스트에 appid 추가")
    ap.add_argument("--remove", type=int, help="워치리스트에서 appid 제거")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    wl = load_json(WATCHLIST, {"appids": []})

    if args.add and args.add not in wl["appids"]:
        wl["appids"].append(args.add)
        save_json(WATCHLIST, wl)
        log(f"추가: {args.add}")
    if args.remove and args.remove in wl["appids"]:
        wl["appids"].remove(args.remove)
        save_json(WATCHLIST, wl)
        log(f"제거: {args.remove}")
        if not args.add:
            # 제거만 하고 데이터 파일에서도 삭제
            data = load_json(WATCH_DATA, {"entries": []})
            data["entries"] = [e for e in data["entries"] if e["appid"] != args.remove]
            save_json(WATCH_DATA, data)

    if not wl["appids"]:
        log("워치리스트 비어있음 → data/watchlist.json 에 appids 추가")
        sys.exit(0)

    prev = {e["appid"]: e for e in load_json(WATCH_DATA, {"entries": []}).get("entries", [])}
    entries = []
    for appid in wl["appids"]:
        log(f"조회: {appid}")
        e = collect_one(appid, prev.get(appid))
        log(f"  {e['name']} | CCU {e['ccu']:,} | 리뷰 {e['total_reviews']:,} ({e['review_score_desc']})")
        entries.append(e)

    save_json(WATCH_DATA, {
        "schema": "steam-analysis.watchlist.v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    })
    log(f"완료 → {WATCH_DATA} ({len(entries)}개)")


if __name__ == "__main__":
    main()
