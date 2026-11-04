#!/usr/bin/env python3
"""Lấy kết quả Mega 6/45 và Power 6/55 từ vietlott.vn, lưu vào data/<game>.json.

Chạy: pip install requests beautifulsoup4 && python scripts/scrape.py
"""
import json, re, sys, datetime as dt
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE = "https://vietlott.vn"
GAMES = {
    "645": dict(page="/vi/trung-thuong/ket-qua-trung-thuong/645",
                web="Game645CompareWebPart", n=6),
    "655": dict(page="/vi/trung-thuong/ket-qua-trung-thuong/655",
                web="Game655CompareWebPart", n=6),
}
YEAR = dt.date.today().year
UA = {"User-Agent": "Mozilla/5.0 (compatible; vietlott-stats/1.0)"}
OUT = Path(__file__).resolve().parent.parent / "data"

def parse_rows(html):
    """Trả về danh sách kỳ quay từ HTML bảng kết quả."""
    soup = BeautifulSoup(html, "html.parser")
    draws = []
    for tr in soup.find_all("tr"):
        text = tr.get_text(" ", strip=True)
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
        balls = [int(s.get_text(strip=True)) for s in tr.select(".bong_tron")
                 if s.get_text(strip=True).isdigit()]
        if not m or len(balls) < 6:
            continue
        d, mo, y = m.groups()
        idm = re.search(r"#?(\d{4,6})\b", text.replace(m.group(0), ""))
        draws.append(dict(date=f"{y}-{mo}-{d}", id=idm.group(1) if idm else "",
                          numbers=sorted(balls[:6]),
                          bonus=balls[6] if len(balls) > 6 else None))
    return draws

def fetch_game(code, cfg):
    s = requests.Session(); s.headers.update(UA)
    page = s.get(BASE + cfg["page"], timeout=30); page.raise_for_status()
    # Trang kết quả nạp bảng qua AjaxPro; lấy "Key" nhúng trong trang.
    key = re.search(r'["\']?Key["\']?\s*[:=]\s*["\']([0-9a-f]{16,})["\']', page.text)
    all_draws = parse_rows(page.text)
    if key:
        url = f"{BASE}/ajaxpro/Vietlott.PlugIn.WebParts.{cfg['web']},Vietlott.PlugIn.WebParts.ashx"
        for idx in range(0, 40):
            body = {"ORenderInfo": {"SiteId": "main.frontend.vi", "SiteAlias": "main.vi",
                    "UserSessionId": "", "SiteLang": "vi", "IsPageDesign": False,
                    "ExtraParam1": "", "ExtraParam2": "", "ExtraParam3": "",
                    "SiteURL": "", "WebPage": None, "SiteName": "Vietlott",
                    "OrgPageAlias": None, "PageAlias": None, "RefKey": None,
                    "FullPageAlias": None},
                    "Key": key.group(1), "GameDrawId": "",
                    "ArrayNumbers": [[""] * cfg["n"]], "CheckMulti": False, "PageIndex": idx}
            r = s.post(url, json=body, timeout=30,
                       headers={"X-AjaxPro-Method": "ServerSideDrawResult",
                                "Referer": BASE + cfg["page"]})
            if r.status_code != 200: break
            html = (r.json().get("value") or {}).get("HtmlContent", "")
            rows = parse_rows(html)
            if not rows: break
            all_draws += rows
            if min(d["date"] for d in rows) < f"{YEAR}-01-01": break
    return all_draws

def main():
    OUT.mkdir(exist_ok=True)
    ok = False
    for code, cfg in GAMES.items():
        f = OUT / f"{code}.json"
        old = json.loads(f.read_text())["draws"] if f.exists() else []
        try:
            new = fetch_game(code, cfg)
        except Exception as e:
            print(f"[{code}] lỗi: {e}", file=sys.stderr); continue
        merged = {d["date"] + d["id"]: d for d in old + new}
        draws = sorted(merged.values(), key=lambda d: d["date"], reverse=True)
        f.write_text(json.dumps(dict(updated=dt.datetime.utcnow().isoformat() + "Z",
                                     source=BASE + cfg["page"], draws=draws),
                                ensure_ascii=False, indent=1))
        print(f"[{code}] {len(new)} kỳ mới lấy, tổng {len(draws)}")
        ok = ok or bool(new)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
