#!/usr/bin/env python3
"""Setup principal : borne Dual Thrust (dépôt je-suis-tm/quant-trading) + confirmation M5 de l'utilisateur.

1. Journée CME (ouverture 18h NY = 3h La Réunion). Plage des 5 journées précédentes :
   max(plus haut 5 j - plus bas des clôtures 5 j, plus haute clôture 5 j - plus bas 5 j).
2. Bornes = ouverture du jour +/- 0,5 x plage. Seule la PREMIÈRE borne touchée compte (achat si
   borne haute, vente si borne basse). Une bougie qui touche les deux bornes : pas de trade.
3. Attendre le RETOUR du prix sur la borne cassée, puis la première confirmation M5 dans le
   sens de la cassure, dans l'heure (12 bougies) : rejet, CHoCH, avalement ou fin de repli.
4. Entrée à la clôture de la bougie de confirmation, stop au-delà de la borne (or 100 ticks
   minimum, BTC 130 ; CHoCH : au-delà de l'extrême), objectif 2R, à plat à 16h NY (1h La Réunion).
   Les deux sens, sans filtre de biais : au test, le biais Daily n'améliorait pas ce setup.

Backtest (une entrée par jour, frais inclus) : or 2006-2019 +0,05 R (t 2,0), or 2020-2026
+0,15 R (t 2,9), BTC 2020-2026 +0,07 R (t 1,5, 7 années positives sur 7). Données spot.

  /opt/openbb/bin/python dualthrust.py MGC
"""
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

MIN_STOP_TICKS = {"MGC": 100, "MBT": 130, "MET": 130}  # stops minimum testés
TESTED = ("MGC", "MBT")
END = 16 * 60  # 16h NY


def live_dt(m5, tick, min_stop):
    """m5 : bougies 5 min (index avec fuseau), au moins 6 journées CME. Renvoie l'état du jour."""
    x = m5[["open", "high", "low", "close"]].copy()
    ny = x.index.tz_convert("America/New_York")
    x["cd"] = (ny + pd.Timedelta(hours=6)).date
    x["hm"] = ny.hour * 60 + ny.minute
    if len(x) > 1:
        x = x.iloc[:-1]  # la dernière bougie peut être en cours
    days = sorted(set(x.cd))
    if len(days) < 6:
        return None
    d1 = x.groupby("cd").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    prev = d1.loc[days[-6:-1]]
    rng = max(prev.high.max() - prev.close.min(), prev.close.max() - prev.low.min())
    g = x[x.cd == days[-1]]
    O, H, L, C, hm = (g[k].values for k in ("open", "high", "low", "close", "hm"))
    live = (hm < END) | (hm >= 18 * 60)
    up, lo = O[0] + 0.5 * rng, O[0] - 0.5 * rng
    st = dict(up=up, lo=lo, rng=rng, open=O[0], day=days[-1], status="attente", side=0)
    i = next((k for k in range(len(g)) if live[k] and (H[k] >= up or L[k] <= lo)), None)
    if i is None:
        return st
    if H[i] >= up and L[i] <= lo:
        st["status"] = "les deux bornes touchées dans la même bougie : pas de trade aujourd'hui"
        return st
    side = 1 if H[i] >= up else -1
    lvl = up if side > 0 else lo
    st.update(side=side, level=lvl, t_break=g.index[i], status="cassée")
    j = next((k for k in range(i + 1, len(g)) if live[k] and ((L[k] <= lvl) if side > 0 else (H[k] >= lvl))), None)
    if j is None:
        return st
    st.update(t_retest=g.index[j], status="retour sur la borne")
    stop_zone = lvl - side * min_stop
    ext = L[j] if side > 0 else H[j]
    for m in range(j, min(j + 12, len(g))):
        if not live[m]:
            break
        if (C[m] < stop_zone) if side > 0 else (C[m] > stop_zone):
            st["status"] = "invalidée (clôture au-delà du stop de zone)"
            return st
        ext = min(ext, L[m]) if side > 0 else max(ext, H[m])
        rngm = H[m] - L[m] or 1e-9
        touched = (L[m] <= lvl) if side > 0 else (H[m] >= lvl)
        trig, stp = None, stop_zone
        if touched and ((C[m] > lvl and (min(O[m], C[m]) - L[m]) / rngm >= .4) if side > 0 else
                        (C[m] < lvl and (H[m] - max(O[m], C[m])) / rngm >= .4)):
            trig = "rejet M5"
        elif m > j and ((C[m] > H[max(j - 3, 0):m].max()) if side > 0 else (C[m] < L[max(j - 3, 0):m].min())):
            trig, stp = "CHoCH M5", ext
        elif m > 0 and ((C[m-1] < O[m-1] and C[m] > O[m] and O[m] <= C[m-1] and C[m] >= O[m-1]) if side > 0 else
                        (C[m-1] > O[m-1] and C[m] < O[m] and O[m] >= C[m-1] and C[m] <= O[m-1])):
            trig = "avalement M5"
        elif m >= 3 and all((C[q] < O[q]) if side > 0 else (C[q] > O[q]) for q in (m-3, m-2, m-1)) and \
                ((C[m] > O[m]) if side > 0 else (C[m] < O[m])):
            trig = "fin de repli M5"
        if trig:
            e = C[m]
            if abs(e - stp) < min_stop:
                stp = e - side * min_stop
            tg = e + side * 2 * abs(e - stp)
            st.update(status="CONFIRMÉE", trig=trig, t_trig=g.index[m], entry=e, stop=stp, target=tg)
            res = "toujours en cours"
            for k in range(m + 1, len(g)):
                if not live[k]:
                    res = "clôturé à 1h00"
                    break
                if (L[k] <= stp) if side > 0 else (H[k] >= stp):
                    res = "stop touché"
                    break
                if (H[k] >= tg) if side > 0 else (L[k] <= tg):
                    res = "objectif 2R atteint"
                    break
            st["result"] = res
            return st
    if len(g) - j > 12:
        st["status"] = "expirée (pas de confirmation M5 dans l'heure)"
    else:
        st["status"] = "retour sur la borne : attendre la confirmation M5"
    return st


def main():
    from market import atr, bars
    from plan import SPECS
    sym = sys.argv[1].upper()
    tick = SPECS[sym][0]
    _, m5 = bars(sym, "5m", 10)
    mn = MIN_STOP_TICKS.get(sym, 0) * tick or atr(m5.resample("15min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna())
    st = live_dt(m5, tick, mn)
    if st is None:
        print("pas assez de données (6 journées CME)")
        return 1
    print(f"{sym} journée CME du {st['day']} : ouverture {st['open']:.2f}, plage 5 j {st['rng']:.2f}")
    print(f"  borne haute {st['up']:.2f}  borne basse {st['lo']:.2f}  état : {st['status']}")
    if st.get("trig"):
        print(f"  {st['trig']} à {st['t_trig']:%H:%M} : entrée {st['entry']:.2f} stop {st['stop']:.2f} objectif {st['target']:.2f} ({st['result']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
