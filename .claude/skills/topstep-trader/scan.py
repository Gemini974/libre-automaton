#!/usr/bin/env python3
"""Scanner du jour (adapté de trader-scanner, day-trader-skill) appliqué à NOTRE méthode, sur les
contrats Topstep : biais du jour (technique + fondamental), tendance HMA H1/H4, risque d'un stop de
1 ATR M15 en $, volume relatif, écart à la veille, état du range d'ouverture. Classe les actifs à
trader aujourd'hui ; les autres sont écartés avec la raison.

  /opt/openbb/bin/python scan.py                      # tous les contrats
  /opt/openbb/bin/python scan.py MGC MBT MNQ --max-risk 160
"""
import argparse
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bias import daily_bias  # noqa: E402
from market import NY, atr, bars  # noqa: E402
from plan import SPECS  # noqa: E402

ALL = ["MBT", "MGC", "MNQ", "MES", "MYM", "M2K", "MCL", "M6E", "M6B", "M6A", "MET"]
OR_START = {"MGC": (8, 20), "MCL": (9, 0), "M6E": (8, 20), "M6B": (8, 20), "M6A": (8, 20)}
MIN_STOP = {"MBT": 130, "MET": 130}


def wma(s, n):
    w = np.arange(1, n + 1)
    return s.rolling(n).apply(lambda x: (x * w).sum() / w.sum(), raw=True)


def hma_slope(c, n=21):
    h = wma(2 * wma(c, n // 2) - wma(c, n), int(np.sqrt(n)))
    return 1 if h.iloc[-1] > h.iloc[-2] else -1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("symbols", nargs="*")
    p.add_argument("--max-risk", type=float, default=160.0)
    a = p.parse_args()
    rows = []
    for sym in (a.symbols or ALL):
        sym = sym.upper()
        try:
            tick, tv = SPECS[sym]
            _, d1 = bars(sym, "1d", 200)
            _, h1 = bars(sym, "1h", 40)
            _, m15 = bars(sym, "15m", 10)
            b, tech, fund, _, btxt = daily_bias(sym, d1)
            h4 = h1.close.resample("4h").last().dropna()
            hs1, hs4 = hma_slope(h1.close), hma_slope(h4)
            trend = hs1 if hs1 == hs4 else 0
            a15 = atr(m15)
            stop_ticks = max(round(a15 / tick), MIN_STOP.get(sym, 10))
            risk = stop_ticks * tv
            t = m15.index.tz_convert(NY)
            cd = (t + pd.Timedelta(hours=6)).date
            today = m15[cd == cd[-1]]
            rvol = np.nan
            if m15.volume.sum() > 0:
                hm = t.hour * 60 + t.minute
                now_hm = hm[-1]
                vol_today = today.volume.sum()
                past = [m15[(cd == d) & ((hm <= now_hm) | (hm >= 18 * 60))].volume.sum() for d in sorted(set(cd))[:-1]]
                rvol = vol_today / np.mean(past) if past and np.mean(past) > 0 else np.nan
            prevc = d1.close.iloc[-2]
            gap_atr = (m15.close.iloc[-1] - prevc) / atr(d1.iloc[:-1])
            hh, mm = OR_START.get(sym, (9, 30))
            tt = today.index.tz_convert(NY)
            orb = today[(tt.hour * 60 + tt.minute >= hh * 60 + mm) & (tt.hour * 60 + tt.minute < hh * 60 + mm + 15)]
            if len(orb):
                oh, ol = orb.high.max(), orb.low.min()
                aft = today[today.index > orb.index[-1]].iloc[:-1]
                up, dn = (aft.close > oh).any(), (aft.close < ol).any()
                ors = ("cassé en haut" if up and not dn else "cassé en bas" if dn and not up else
                       "cassé des deux côtés" if up and dn else "dans le range")
            else:
                ors = "pas encore formé"
            reasons = []
            if b == 0:
                reasons.append(btxt.split(":")[-1].strip())
            elif trend == -b:
                reasons.append("HMA H1/H4 contre le biais")
            if risk > a.max_risk:
                reasons.append(f"stop 1 ATR M15 = {risk:.0f} $ > {a.max_risk:.0f} $")
            score = (2 if b != 0 else 0) + (1 if trend == b and b != 0 else 0) + (1 if rvol == rvol and rvol >= 1.2 else 0)
            rows.append(dict(sym=sym, b=b, trend=trend, risk=risk, ticks=stop_ticks, rvol=rvol, gap=gap_atr, ors=ors,
                             score=score if not reasons else -1, why="; ".join(reasons)))
        except Exception as ex:
            rows.append(dict(sym=sym, b=0, trend=0, risk=np.nan, ticks=0, rvol=np.nan, gap=np.nan, ors="-", score=-2,
                             why=f"données indisponibles ({ex.__class__.__name__})"))
    R = pd.DataFrame(rows).sort_values(["score", "rvol"], ascending=False)
    lab = {1: "ACHATS", -1: "VENTES", 0: "aucun"}
    print("SCANNER DU JOUR (méthode : biais Daily + fondamental, HMA H1/H4, range d'ouverture M15)")
    print(f"{'actif':5s} {'biais':7s} {'HMA':7s} {'stop 1 ATR M15':>16s} {'vol. rel.':>9s} {'écart veille':>12s}  range d'ouverture")
    for r in R.itertuples():
        print(f"{r.sym:5s} {lab[r.b]:7s} {lab[r.trend] if r.trend else 'mixte':7s} {r.ticks:6d} t = {r.risk:5.0f} $ "
              f"{r.rvol:9.2f} {r.gap:+11.2f} ATR  {r.ors}")
    ok = R[R.score >= 0]
    print("\nÀ TRADER AUJOURD'HUI : " + (", ".join(f"{r.sym} ({lab[r.b].lower()})" for r in ok.itertuples()) if len(ok) else "aucun actif ne passe"))
    for r in R[R.score < 0].itertuples():
        print(f"  écarté {r.sym} : {r.why}")
    print("Ne pas cumuler des positions corrélées (BTC, Ether, indices, or). Ensuite : structure.py sur l'actif choisi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
