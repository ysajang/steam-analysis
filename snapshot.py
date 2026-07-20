#!/usr/bin/env python3
"""
분기 스냅샷 축적기 (해석2: 미래 트렌드)
현재 games.json의 요약을 data/snapshots/YYYY-Qn.json 으로 굳힌다.
분기마다 collect.py 실행 후 이 스크립트를 한 번 돌리면 시계열이 쌓인다.

사용:
  python snapshot.py            # 현재 분기 이름으로 저장 (이미 있으면 거부)
  python snapshot.py --force    # 같은 분기 덮어쓰기
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
GAMES_JSON = os.path.join(ROOT, "data", "games.json")
SNAP_DIR = os.path.join(ROOT, "data", "snapshots")


def current_quarter():
    now = datetime.now(timezone.utc)
    return f"{now.year}-Q{(now.month - 1) // 3 + 1}"


def summarize(games):
    """스냅샷은 요약만 저장 — 장르/태그별 집계 + 상위 게임 지표."""
    genre_owners = {}
    tag_owners = {}
    for g in games:
        owners = g.get("owners_mid", 0)
        for genre in [x.strip() for x in (g.get("genre") or "").split(",") if x.strip()]:
            genre_owners[genre] = genre_owners.get(genre, 0) + owners
        tags = g.get("tags") or {}
        if tags:
            top3 = sorted(tags, key=tags.get, reverse=True)[:3]
            for t in top3:
                tag_owners[t] = tag_owners.get(t, 0) + owners
    top_games = [
        {
            "appid": g["appid"], "name": g["name"],
            "owners_mid": g["owners_mid"], "ccu": g["ccu"],
            "positive": g["positive"], "negative": g["negative"],
        }
        for g in sorted(games, key=lambda x: x.get("owners_mid", 0), reverse=True)[:200]
    ]
    return {"genre_owners": genre_owners, "tag_owners": tag_owners, "top_games": top_games}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="같은 분기 스냅샷 덮어쓰기")
    args = ap.parse_args()

    if not os.path.exists(GAMES_JSON):
        print("games.json 없음 → 먼저 collect.py 실행 필요")
        sys.exit(1)

    with open(GAMES_JSON, "r", encoding="utf-8") as f:
        payload = json.load(f)

    q = current_quarter()
    os.makedirs(SNAP_DIR, exist_ok=True)
    out = os.path.join(SNAP_DIR, f"{q}.json")
    if os.path.exists(out) and not args.force:
        print(f"{q} 스냅샷이 이미 존재. 덮어쓰려면 --force")
        sys.exit(1)

    snap = {
        "schema": "steam-analysis.snapshot.v1",
        "quarter": q,
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "count": payload.get("count", 0),
        **summarize(payload.get("games", [])),
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print(f"저장 → {out}")


if __name__ == "__main__":
    main()
