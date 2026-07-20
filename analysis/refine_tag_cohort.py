"""SteamSpy tag 카탈로그를 유료+최근출시로 정제해 도달률 재계산 (샘플링 기반)
사용: python analysis/refine_tag_cohort.py --tag Co-op --sample 350
출력: analysis/out_<tag>.json
"""
import urllib.request, urllib.parse, json, time, random, argparse, os, sys

def fetch_tag(tag):
    url = "https://steamspy.com/api.php?request=tag&tag=" + urllib.parse.quote(tag)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())

def owners_mid(s):
    try:
        lo, hi = [int(x.replace(",", "")) for x in s.split(" .. ")]
        return (lo + hi) // 2
    except Exception:
        return 0

def store_release(appid, retries=3):
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=release_date,basic"
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read())
            e = d.get(str(appid), {})
            if not e.get("success"):
                return None
            data = e.get("data", {})
            rd = data.get("release_date", {})
            return {"date": rd.get("date", ""), "coming": rd.get("coming_soon", False),
                    "type": data.get("type", "")}
        except Exception:
            time.sleep(5 * (i + 1))
    return None

def parse_year(datestr):
    for tok in datestr.replace(",", " ").split():
        if tok.isdigit() and len(tok) == 4:
            return int(tok)
    return None

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

def parse_ym(datestr):
    y = parse_year(datestr)
    m = None
    for tok in datestr.replace(",", " ").split():
        if tok[:3] in MONTHS:
            m = MONTHS[tok[:3]]
    return y, m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--sample", type=int, default=300)
    ap.add_argument("--since", default="2023-07")  # YYYY-MM
    args = ap.parse_args()
    sy, sm = map(int, args.since.split("-"))

    outpath = f"analysis/out_{args.tag.replace(' ', '_')}.json"
    state = json.load(open(outpath)) if os.path.exists(outpath) else {"lookups": {}}

    cat = fetch_tag(args.tag)
    paid = {k: v for k, v in cat.items() if (v.get("price") or "0") not in ("0", "", None)}
    print(f"[{args.tag}] catalog={len(cat)} paid={len(paid)}", flush=True)

    random.seed(42)
    ids = sorted(paid.keys())
    sample = random.sample(ids, min(args.sample, len(ids)))

    for i, appid in enumerate(sample):
        if appid in state["lookups"]:
            continue
        info = store_release(appid)
        state["lookups"][appid] = info
        if i % 25 == 0:
            json.dump(state, open(outpath, "w"))
            print(f"  {i}/{len(sample)}", flush=True)
        time.sleep(1.6)  # store API rate limit 보수적 준수
    json.dump(state, open(outpath, "w"))

    # 집계
    recent, older, unknown = [], [], 0
    for appid in sample:
        info = state["lookups"].get(appid)
        if not info or info.get("coming") or info.get("type") != "game":
            unknown += 1
            continue
        y, m = parse_ym(info.get("date", ""))
        if not y:
            unknown += 1
            continue
        om = owners_mid(paid[appid].get("owners", "0"))
        rec = (y, m or 12) >= (sy, sm)
        (recent if rec else older).append(om)

    def stats(xs):
        if not xs:
            return {}
        xs = sorted(xs)
        n = len(xs)
        return {"n": n, "median": xs[n // 2],
                "ge100k": round(100 * sum(1 for x in xs if x >= 100000) / n, 1),
                "ge1m": round(100 * sum(1 for x in xs if x >= 1000000) / n, 1)}

    result = {"tag": args.tag, "catalog": len(cat), "paid": len(paid),
              "sampled": len(sample), "unknown": unknown,
              "recent_since": args.since,
              "recent": stats(recent), "older": stats(older)}
    state["result"] = result
    json.dump(state, open(outpath, "w"), indent=1)
    print(json.dumps(result, indent=1))

if __name__ == "__main__":
    main()
