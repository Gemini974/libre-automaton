#!/usr/bin/env python3
"""Machine à remonter le temps (adaptée de trader-timemachine, day-trader-skill) pour un plan Topstep.

Avant de risquer un dollar : 10 000 fins de séance simulées à partir des bougies 5 min des
60 derniers jours (même heure de la journée, ± 2 bougies), plus l'historique réel du même plan
(stop et objectif en ATR) sur chaque séance passée. Sortie forcée à 16h NY (1h La Réunion).

  /opt/openbb/bin/python timemachine.py MGC --side short --entry 3601 --stop 3615 --target 3566.3
  /opt/openbb/bin/python timemachine.py MBT --side long --entry 60500 --stop 59850 --target 61800 --at 19:00
"""
import argparse
import random
import sys
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from market import NY, atr, bars  # noqa: E402
from plan import LOCAL  # noqa: E402

END = 16 * 60  # 16h00 New York


def verdict(pt, ps, rr):
    hit = pt + ps
    if hit < 1e-9:
        return "aucun côté touché : tout se joue à la clôture"
    need = 1 / (1 + rr)
    got = pt / hit
    gap = (got - need) * 100
    side = "l'objectif" if gap > 0 else "le stop"
    if abs(gap) < 5:
        return f"proche de l'équilibre (il faut {need*100:.0f} % des cas touchés côté objectif, obtenu {got*100:.0f} %)"
    if abs(gap) < 15:
        return f"penche vers {side} (il faut {need*100:.0f} %, obtenu {got*100:.0f} %)"
    return f"nettement vers {side} (il faut {need*100:.0f} %, obtenu {got*100:.0f} %)"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("symbol")
    p.add_argument("--side", choices=["long", "short"], required=True)
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--target", type=float, required=True)
    p.add_argument("--at", help="heure d'entrée HH:MM La Réunion (défaut : maintenant)")
    p.add_argument("--replays", type=int, default=10000)
    p.add_argument("--seed", type=int, default=19)
    a = p.parse_args()
    sym = a.symbol.upper()
    side = 1 if a.side == "long" else -1
    _, m5 = bars(sym, "5m", 59)
    m5 = m5.copy()
    m5.index = m5.index.tz_convert(NY)
    m5["hm"] = m5.index.hour * 60 + m5.index.minute
    m5["cd"] = (m5.index + pd.Timedelta(hours=6)).date
    now = datetime.now(LOCAL)
    if a.at:
        h, mi = map(int, a.at.split(":"))
        now = now.replace(hour=h, minute=mi)
    t0 = now.astimezone(NY)
    start = (t0.hour * 60 + t0.minute) // 5 * 5
    if not (start < END or start >= 18 * 60):
        print("Heure d'entrée hors séance (16h-18h NY = 1h-3h La Réunion)")
        return 1
    risk = abs(a.entry - a.stop)
    rr = abs(a.target - a.entry) / risk
    a5 = atr(m5.iloc[-200:])
    ks, kt = risk / a5, abs(a.target - a.entry) / a5
    # pool : rapports open/high/low/close sur la clôture précédente, par heure de la journée
    pc = m5.close.shift()
    ratios = np.c_[m5.open / pc, m5.high / pc, m5.low / pc, m5.close / pc]
    same = (m5.cd.values == np.roll(m5.cd.values, 1))
    ok = same & ~np.isnan(ratios).any(1)
    hm = m5.hm.values
    steps = []
    t = start
    while True:
        steps.append(t)
        t = (t + 5) % 1440
        if t == END:
            break
    rng = random.Random(a.seed)
    pools = {}
    for s in set(steps):
        idx = np.where(ok & (np.abs(((hm - s + 720) % 1440) - 720) <= 10))[0]
        pools[s] = idx
    res = {"t": 0, "s": 0, "n": 0}
    Rs = []
    for _ in range(a.replays):
        px = a.entry
        out = None
        for s in steps:
            pool = pools[s]
            if not len(pool):
                continue
            o, hh, ll, cc = ratios[pool[rng.randrange(len(pool))]]
            hi, lo, px_new = px * hh, px * ll, px * cc
            if (lo <= a.stop) if side > 0 else (hi >= a.stop):
                out = "s"
                break
            if (hi >= a.target) if side > 0 else (lo <= a.target):
                out = "t"
                break
            px = px_new
        if out == "t":
            res["t"] += 1
            Rs.append(rr)
        elif out == "s":
            res["s"] += 1
            Rs.append(-1)
        else:
            res["n"] += 1
            Rs.append((px - a.entry) * side / risk)
    n = a.replays
    pt, ps, pn = res["t"] / n, res["s"] / n, res["n"] / n
    print(f"{sym} {'ACHAT' if side > 0 else 'VENTE'} entrée {a.entry} stop {a.stop} objectif {a.target} ({rr:.1f} R), "
          f"entrée vers {now:%H:%M} La Réunion, sortie forcée 1h00")
    print(f"Simulation ({n} fins de séance tirées des bougies 5 min des 60 derniers jours, graine {a.seed}) :")
    print(f"  objectif d'abord {pt*100:.1f} %   stop d'abord {ps*100:.1f} %   ni l'un ni l'autre à 1h00 {pn*100:.1f} %   R moyen {np.mean(Rs):+.2f}")
    print(f"  Verdict : {verdict(pt, ps, rr)}")
    if pn > .4:
        print("  Plus de 40 % des cas finissent sans toucher : le prix de 1h00 décide.")
    # historique réel : même heure, même stop et objectif en ATR 5 min du jour
    tr = pd.concat([m5.high - m5.low, (m5.high - pc).abs(), (m5.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    hist = []
    for cd, g in m5.groupby("cd"):
        if cd >= t0.date():
            continue
        e_rows = g[g.hm == start]
        if e_rows.empty:
            continue
        i0 = m5.index.get_loc(e_rows.index[0])
        e = m5.open.iloc[i0]
        at_ = tr.iloc[i0 - 1]
        if np.isnan(at_):
            continue
        st, tg = e - side * ks * at_, e + side * kt * at_
        r = None
        for j in range(i0, len(m5)):
            if m5.cd.iloc[j] != cd or m5.hm.iloc[j] == END:
                r = (m5.close.iloc[j - 1] - e) * side / (ks * at_)
                break
            if (m5.low.iloc[j] <= st) if side > 0 else (m5.high.iloc[j] >= st):
                r = -1
                break
            if (m5.high.iloc[j] >= tg) if side > 0 else (m5.low.iloc[j] <= tg):
                r = rr
                break
        if r is not None:
            hist.append(r)
    if hist:
        h = np.array(hist)
        print(f"Historique réel du même plan (stop {ks:.1f} ATR 5 min, objectif {kt:.1f} ATR, même heure) sur {len(h)} séances :")
        print(f"  objectif {np.mean(h == rr)*100:.0f} %   stop {np.mean(h == -1)*100:.0f} %   autre {np.mean((h != rr) & (h != -1))*100:.0f} %   R moyen {h.mean():+.2f}")
    print("C'est une simulation tirée des 60 derniers jours, pas une prévision.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
