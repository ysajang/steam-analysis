# Steam 시장 분석 — 개인 콕핏

SteamSpy 상위 1000 + 출시분기 회고 + Steam 공식 API 워치리스트.
개인 판단용 로컬 도구. 서버·인터넷 없이 `dashboard.html` 더블클릭으로 열림.

## 구조

```
collect.py           SteamSpy 상위 1000 + 태그/장르 + 출시일 수집 → data/games.json (~45분)
snapshot.py          분기 스냅샷 축적 → data/snapshots/YYYY-Qn.json
watch.py             워치리스트 조회 (Steam 공식 API, SteamSpy 사각지대 우회) → data/watchlist_data.json
build_dashboard.py   위 데이터 전부 주입한 완전 독립 dashboard.html 생성
data/watchlist.json  추적할 appid 목록 (수동 편집 가능)
```

## 최초 셋업

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 운영 루틴 (분기마다 1회)

```bash
source .venv/bin/activate
python collect.py           # 상위 1000 재수집 (~45분, 중단돼도 재실행하면 이어짐)
python snapshot.py          # 분기 스냅샷 굳히기
python watch.py             # 워치리스트 갱신 (~10초, 자주 돌려도 됨 — 리뷰 증가속도 추적용)
python build_dashboard.py   # dashboard.html 재생성
```

## 워치리스트 관리

```bash
python watch.py --add 4704690     # appid 추가 (Steam 상점 URL의 숫자)
python watch.py --remove 559650   # 제거
```

## 데이터 소스와 한계

- SteamSpy `all`: 소유자순 상위 1000 스냅샷. **과거 순위 소급 불가, 최신 바이럴 신작 누락 가능**(사각지대)
- Steam Store `appdetails`: 출시일·장르·가격 (공식)
- Steam 공식 CCU·appreviews: 워치리스트 전용, 실시간·정확
- 판매 추정 = 리뷰수 × 30~50 (업계 관례, 대략치)

## 유의

- `dashboard.html`은 생성물 — git 미추적, 데이터에서 언제든 재생성
- `data/games.json`·`data/snapshots/`는 자산 — 커밋해서 이력 보존
- SteamSpy rate limit 준수 코드 내장(1.2s 간격) — 수집 병렬화 금지
