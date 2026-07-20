"""최근 3년 Co-op 샘플의 승자(10만+) vs 실패군 속성 비교
입력: analysis/out_Co-op.json  출력: analysis/out_coop_attrs.json"""
import urllib.request, json, time, os

MONTHS = {m: i+1 for i, m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])}

def parse_ym(s):
    y = m = None
    for tok in s.replace(",", " ").split():
        if tok.isdigit() and len(tok) == 4: y = int(tok)
        if tok[:3] in MONTHS: m = MONTHS[tok[:3]]
    return y, m

def owners_mid(s):
    try:
        lo, hi = [int(x.replace(",", "")) for x in s.split(" .. ")]
        return (lo+hi)//2
    except Exception:
        return 0

def get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(4*(i+1))
    return None

def main():
    state = json.load(open("analysis/out_Co-op.json"))
    outpath = "analysis/out_coop_attrs.json"
    attrs = json.load(open(outpath)) if os.path.exists(outpath) else {}

    # 최근 3년 유료 코옵 샘플 재구성
    cat = get("https://steamspy.com/api.php?request=tag&tag=Co-op")
    recent_ids = []
    for appid, info in state["lookups"].items():
        if not info or info.get("coming") or info.get("type") != "game":
            continue
        y, m = parse_ym(info.get("date", ""))
        if y and (y, m or 12) >= (2023, 7) and appid in cat:
            recent_ids.append(appid)
    print(f"recent ids: {len(recent_ids)}", flush=True)

    for i, appid in enumerate(recent_ids):
        if appid in attrs:
            continue
        ss = get(f"https://steamspy.com/api.php?request=appdetails&appid={appid}")
        time.sleep(1.1)
        st = get(f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=categories,genres,price_overview")
        time.sleep(1.1)
        cats = []
        if st and st.get(str(appid), {}).get("success"):
            d = st[str(appid)]["data"]
            cats = [c["description"] for c in d.get("categories", [])]
        attrs[appid] = {
            "name": (ss or {}).get("name", ""),
            "owners": owners_mid((ss or {}).get("owners", "0")),
            "price": int((ss or {}).get("price") or 0)/100,
            "tags": list(((ss or {}).get("tags") or {}).keys())[:12],
            "categories": cats,
            "reviews": ((ss or {}).get("positive", 0) or 0) + ((ss or {}).get("negative", 0) or 0),
        }
        if i % 10 == 0:
            json.dump(attrs, open(outpath, "w"))
            print(f"  {i}/{len(recent_ids)}", flush=True)
    json.dump(attrs, open(outpath, "w"), indent=1)

    win = {k: v for k, v in attrs.items() if v["owners"] >= 100000}
    lose = {k: v for k, v in attrs.items() if v["owners"] < 100000}
    def freq(group, field):
        from collections import Counter
        c = Counter()
        for v in group.values():
            c.update(set(v[field]))
        n = max(len(group), 1)
        return {k: round(100*x/n, 1) for k, x in c.most_common(25)}
    report = {
        "n_win": len(win), "n_lose": len(lose),
        "win_price_list": sorted(v["price"] for v in win.values()),
        "lose_price_median": sorted(v["price"] for v in lose.values())[len(lose)//2] if lose else None,
        "win_tags_pct": freq(win, "tags"), "lose_tags_pct": freq(lose, "tags"),
        "win_cats_pct": freq(win, "categories"), "lose_cats_pct": freq(lose, "categories"),
        "winners": [{"name": v["name"], "price": v["price"], "owners": v["owners"],
                     "tags": v["tags"][:6]} for v in sorted(win.values(), key=lambda x: -x["owners"])],
    }
    json.dump(report, open("analysis/out_coop_report.json", "w"), indent=1)
    print(json.dumps(report, indent=1, ensure_ascii=False))

if __name__ == "__main__":
    main()
