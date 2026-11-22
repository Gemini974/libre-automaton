#!/usr/bin/env python3
"""topstep-trader geopolitics, shipping and event odds from free public APIs (no key).
Standard library only.

  python3 geo.py news ["Iran OR Hormuz"]   # GDELT: news volume 14 days + latest headlines (default: watchlist)
  python3 geo.py ships                      # IMF PortWatch: daily transits through the main chokepoints
  python3 geo.py odds                       # Polymarket: odds on the Fed, wars, Bitcoin, tariffs, oil
  python3 geo.py decrees                    # Federal Register: latest presidential documents (tariffs, sanctions)
  python3 geo.py quakes                     # USGS: M6+ earthquakes this week
  python3 geo.py all

Hosts: api.gdeltproject.org, services9.arcgis.com, gamma-api.polymarket.com,
www.federalregister.gov, earthquake.usgs.gov.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("Indian/Reunion")
UA = {"User-Agent": "Mozilla/5.0 (topstep-trader)"}
WATCH = [  # (label, GDELT query, assets it moves)
    ("Iran / Hormuz", "(Iran OR Hormuz OR \"Persian Gulf\")", "pétrole, or, dollar, risque global"),
    ("Droits de douane / Chine", "(tariff OR tariffs) (China OR Trump)", "indices, cuivre, yuan, BTC"),
    ("Russie / Ukraine", "(Russia Ukraine) (attack OR ceasefire OR sanctions)", "pétrole, gaz, euro, blé"),
    ("Fed / inflation", "(\"Federal Reserve\" OR Warsh) (rate OR inflation)", "tout, surtout BTC, or, indices"),
    ("Taïwan", "Taiwan (China OR strait) (military OR blockade)", "Nasdaq, semi-conducteurs, risque global"),
]
CHOKE = ["Strait of Hormuz", "Bab el-Mandeb Strait", "Suez Canal", "Panama Canal", "Malacca Strait",
         "Taiwan Strait", "Bosporus Strait", "Cape of Good Hope"]
ODDS_KW = ["fed ", "rate", "iran", "israel", "war", "ceasefire", "china", "taiwan", "tariff", "russia", "ukraine",
           "bitcoin", "recession", "oil", "hormuz", "gold", "shutdown"]


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def safe(fn):
    def run(*a, **k):
        try:
            fn(*a, **k)
        except Exception as e:
            print(f"  [indisponible : {type(e).__name__} {str(e)[:80]}]")
    return run


def gdelt(mode, query, extra=""):
    q = urllib.parse.quote(f"{query} sourcelang:english")
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}&mode={mode}&format=json{extra}"
    for attempt in range(3):
        time.sleep(6 + 20 * attempt)  # GDELT allows about one request every 5 seconds
        try:
            return get(url)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 2:
                raise


@safe
def news(a):
    topics = [(a.query, a.query, "")] if getattr(a, "query", None) else WATCH
    print("ACTUALITÉ GÉOPOLITIQUE  [GDELT, articles par jour sur 14 jours]")
    for label, q, assets in topics:
        tl = gdelt("timelinevolraw", q, "&timespan=14d")["timeline"][0]["data"]
        vals = [x["value"] for x in tl]
        if not vals:
            continue
        base = sum(vals[:-3]) / max(1, len(vals) - 3)
        recent = max(vals[-3:])
        flag = "🔴 FORT" if recent > 2 * base else "🟠 en hausse" if recent > 1.3 * base else "⚪ normal"
        print(f"  {label:26s} {flag:12s} dernier pic {recent} articles/jour, moyenne {base:.0f}. Touche : {assets}")
        arts = gdelt("artlist", q, "&timespan=24h&maxrecords=3&sort=datedesc").get("articles", [])
        for x in arts[:3]:
            print(f"      {x['seendate'][6:8]}/{x['seendate'][4:6]} {x['domain']}: {x['title'][:95]}")


@safe
def ships(_a=None):
    print("TRAFIC MARITIME AUX DÉTROITS  [IMF PortWatch, transits par jour]")
    base = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"
    for name in CHOKE:
        q = urllib.parse.urlencode({"where": f"portname='{name}'", "outFields": "date,n_total,n_tanker",
                                    "orderByFields": "date DESC", "resultRecordCount": 60, "f": "json"})
        rows = [f["attributes"] for f in get(f"{base}?{q}")["features"]]
        if not rows:
            continue
        last7 = rows[:7]
        prev = rows[7:60]
        avg = lambda r, k: sum(x[k] or 0 for x in r) / max(1, len(r))
        t7, tp = avg(last7, "n_total"), avg(prev, "n_total")
        k7, kp = avg(last7, "n_tanker"), avg(prev, "n_tanker")
        chg = 100 * (t7 / tp - 1) if tp else 0
        flag = "🔴" if chg < -30 else "🟠" if chg < -10 else "⚪"
        print(f"  {flag} {name:22s} {t7:6.1f} navires/j (7 j), {chg:+5.0f} % vs 2 mois. Pétroliers {k7:.1f}/j (avant {kp:.1f}). Dernière donnée {rows[0]['date']}")


@safe
def odds(_a=None):
    print("PROBABILITÉS DE MARCHÉ  [Polymarket, marchés les plus actifs]")
    ms = get("https://gamma-api.polymarket.com/markets?closed=false&order=volume24hr&ascending=false&limit=150")
    n = 0
    for m in ms:
        q = m.get("question", "")
        if not any(k in q.lower() for k in ODDS_KW):
            continue
        try:
            yes = float(json.loads(m.get("outcomePrices", "[]"))[0])
        except Exception:
            continue
        print(f"  {100 * yes:5.1f} %  {q[:100]}")
        n += 1
        if n >= 18:
            break


@safe
def decrees(_a=None):
    print("DÉCISIONS DE LA MAISON-BLANCHE  [Federal Register, documents présidentiels]")
    r = get("https://www.federalregister.gov/api/v1/documents.json?per_page=10&order=newest&conditions%5Btype%5D%5B%5D=PRESDOCU")
    for x in r.get("results", []):
        print(f"  {x['publication_date']} {x['title'][:110]}")
    r = get("https://www.federalregister.gov/api/v1/documents.json?per_page=5&order=newest&conditions%5Bterm%5D=tariff")
    print("  Derniers textes contenant « tariff » :")
    for x in r.get("results", []):
        print(f"    {x['publication_date']} {x['title'][:105]}")


@safe
def quakes(_a=None):
    print("SÉISMES M6+ DE LA SEMAINE  [USGS]")
    u = get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson")["features"]
    big = [x["properties"] for x in u if x["properties"]["mag"] >= 6]
    for p in big:
        t = datetime.fromtimestamp(p["time"] / 1000, LOCAL)
        print(f"  M{p['mag']:.1f} {t:%d/%m %Hh} {p['place']}")
    if not big:
        print("  Aucun.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("news")
    n.add_argument("query", nargs="?")
    for c in ("ships", "odds", "decrees", "quakes", "all"):
        sub.add_parser(c)
    a = p.parse_args()
    print(f"Relevé du {datetime.now(LOCAL):%d/%m %H:%M} (La Réunion)")
    fns = {"news": news, "ships": ships, "odds": odds, "decrees": decrees, "quakes": quakes}
    if a.cmd == "all":
        a.query = None
        for fn in (news, ships, odds, decrees, quakes):
            fn(a)
            print()
    else:
        fns[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
