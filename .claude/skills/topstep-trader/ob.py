#!/usr/bin/env python3
"""Méthode d'entrée de l'utilisateur : order block + FVG, sinon retest du dernier point cassé.

Vente (achat en miroir) :
1. Cassure de structure (BOS) : une bougie clôture sous le dernier creux confirmé.
2. Order block (OB) : la dernière bougie haussière avant la jambe de baisse qui a cassé.
   Zone = de l'ouverture (bas du corps) au plus haut de cette bougie.
3. FVG : un déséquilibre baissier dans la jambe (plus haut d'une bougie sous le plus bas de
   l'avant-dernière). OB valable seulement s'il y a un FVG et si le prix n'est pas revenu dans l'OB.
4. Entrée au retour dans l'OB (ligne proximale = bas du corps), stop au-dessus de l'OB.
5. Sans OB + FVG valable : entrée au retest du dernier creux cassé, stop au-dessus du dernier
   sommet avant la cassure.

  /opt/openbb/bin/python ob.py MGC --tf 15m
"""
import argparse
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402


def swings(h, lo, n=2):
    sh, sl = [], []
    for i in range(n, len(h) - n):
        if h[i] == h[i - n:i + n + 1].max():
            sh.append(i)
        if lo[i] == lo[i - n:i + n + 1].min():
            sl.append(i)
    return sh, sl


def find_setups(df, side, n=2, lookback=120, upto=None, keep_touched=False, ob_only=False):
    """Zones valables à la bougie `upto` (incluse), sans regarder après.
    side = -1 vente, +1 achat. Renvoie une liste de dicts triés du plus récent au plus ancien."""
    o, h, lo, c = (df[k].values for k in ("open", "high", "low", "close"))
    end = len(df) - 1 if upto is None else upto
    start = max(0, end - lookback)
    sh, sl = swings(h[:end + 1], lo[:end + 1], n)
    pivots = sl if side < 0 else sh          # points dont la cassure fait un BOS
    opp = sh if side < 0 else sl             # points opposés (pour le stop du retest)
    out = []
    for p in pivots:
        if p < start:
            continue
        lvl = lo[p] if side < 0 else h[p]
        conf = p + n                          # le point n'est connu que n bougies plus tard
        k = next((j for j in range(conf, end + 1) if (c[j] < lvl if side < 0 else c[j] > lvl)), None)
        if k is None:
            continue
        # jambe de cassure : du dernier point opposé avant k jusqu'à k
        prev_opp = [q for q in opp if q < k and q + n <= k]
        leg0 = prev_opp[-1] if prev_opp else max(start, k - 10)
        # order block : dernière bougie de couleur opposée avant la jambe (dans la jambe ou juste avant)
        ob = None
        for j in range(k, max(leg0 - 3, start) - 1, -1):
            if (c[j] > o[j]) if side < 0 else (c[j] < o[j]):
                ob = j
                break
        fvg = None
        if ob is not None:
            for j in range(ob + 2, k + 1):
                if side < 0 and h[j] < lo[j - 2]:
                    fvg = (h[j], lo[j - 2])
                    break
                if side > 0 and lo[j] > h[j - 2]:
                    fvg = (h[j - 2], lo[j])
                    break
        after = slice(k + 1, end + 1)
        if ob_only:  # tous les order blocks, avec ou sans FVG (pour comparer)
            if ob is not None:
                out.append(dict(kind="Order block + FVG" if fvg else "Order block sans FVG", t=df.index[ob], bos=df.index[k],
                                entry=o[ob], far=h[ob] if side < 0 else lo[ob], fvg=fvg, level=lvl, k=k))
            continue
        if ob is not None and fvg is not None:
            # règle 1 : order block + FVG ; entrée au retour dans l'OB. Un OB déjà touché a été joué.
            prox = o[ob]                       # bas du corps (vente) / haut du corps (achat)
            dist = h[ob] if side < 0 else lo[ob]
            touched = (h[after] >= prox).any() if side < 0 else (lo[after] <= prox).any()
            if keep_touched or not touched:
                out.append(dict(kind="Order block + FVG", t=df.index[ob], bos=df.index[k], entry=prox, far=dist,
                                fvg=fvg, level=lvl, k=k))
            continue
        # règle 2 : pas de FVG -> retest du point cassé, s'il n'a pas encore été retesté
        touched = (h[after] >= lvl).any() if side < 0 else (lo[after] <= lvl).any()
        if (keep_touched or not touched) and prev_opp:
            out.append(dict(kind="Retest du point cassé", t=df.index[p], bos=df.index[k], entry=lvl,
                            far=h[prev_opp[-1]] if side < 0 else lo[prev_opp[-1]], fvg=None, level=lvl, k=k))
    seen, uniq = set(), []
    if not keep_touched:  # seulement le dernier point récemment cassé (la cassure la plus récente)
        out = [x for x in out if x["k"] == max(y["k"] for y in out)] if out else out
    for x in sorted(out, key=lambda x: -x["k"]):
        key = (x["kind"], x["t"])
        if key not in seen:
            seen.add(key)
            uniq.append(x)
    return uniq


RULES = {  # règles testées (zones M15, entrée M5, 60 jours) ; défaut = or
    "or": {"kinds": ("Order block + FVG", "Retest du point cassé"),
           "confirm": {"Order block + FVG": ("CHoCH M5", "rejet M5"), "Retest du point cassé": ("rejet M5", "avalement M5")}},
    "crypto": {"kinds": ("Retest du point cassé",), "confirm": {"Retest du point cassé": ("rejet M5", "fin de repli M5")}},
}


def live_setups(m15, m5, side, group="or", buf=0.0, now=None):
    """Zone M15 la plus récente selon les règles, et son état en M5 :
    attente (prix pas encore revenu), dans la zone (attendre la confirmation), CONFIRMÉE, invalidée, expirée."""
    import pandas as pd
    rule = RULES.get(group, RULES["or"])
    zones = [z for z in find_setups(m15, side, lookback=200, keep_touched=True) if z["kind"] in rule["kinds"]]
    if not zones:
        return []
    out = []
    for kind in rule["kinds"]:
        zk = [z for z in zones if z["kind"] == kind]
        if not zk:
            continue
        z = max(zk, key=lambda x: x["k"])
        t_ready = m15.index[z["k"]] + pd.Timedelta(minutes=15)
        prox, far = z["entry"], z["far"]
        stop_zone = far + buf if side < 0 else far - buf
        x = m5[m5.index >= t_ready]
        if len(x) > 1:
            x = x.iloc[:-1]  # la dernière bougie M5 peut être en cours
        O, H, Lo, C = (x[c].values for c in ("open", "high", "low", "close"))
        hit = np.where((H >= prox) if side < 0 else (Lo <= prox))[0]
        st = dict(z, stop=stop_zone, status="attente", confirm=rule["confirm"][kind], trig=None, t_trig=None, choch=None)
        if len(hit):
            j = hit[0]
            st["t_touch"] = x.index[j]
            ext = H[j] if side < 0 else Lo[j]
            base = Lo[max(j - 3, 0):j + 1].min() if side < 0 else H[max(j - 3, 0):j + 1].max()
            st["choch"] = base
            st["status"] = "dans la zone"
            for m in range(j, min(j + 12, len(x))):
                if (C[m] > stop_zone) if side < 0 else (C[m] < stop_zone):
                    st["status"] = "invalidée"
                    break
                ext = max(ext, H[m]) if side < 0 else min(ext, Lo[m])
                rng = H[m] - Lo[m] or 1e-9
                touched = (H[m] >= prox) if side < 0 else (Lo[m] <= prox)
                rej = (C[m] < prox and (H[m] - max(O[m], C[m])) / rng >= .4) if side < 0 else \
                      (C[m] > prox and (min(O[m], C[m]) - Lo[m]) / rng >= .4)
                lvl = (Lo[max(j - 3, 0):m].min() if side < 0 else H[max(j - 3, 0):m].max()) if m > j else None
                if "CHoCH M5" in st["confirm"] and m > j and ((C[m] < lvl) if side < 0 else (C[m] > lvl)):
                    st.update(status="CONFIRMÉE", trig="CHoCH M5", t_trig=x.index[m], entry=C[m],
                              stop=ext + buf if side < 0 else ext - buf)
                    break
                if "rejet M5" in st["confirm"] and touched and rej:
                    st.update(status="CONFIRMÉE", trig="rejet M5", t_trig=x.index[m], entry=C[m])
                    break
                # déclencheurs repris de stolgo (testés dans nos zones M15)
                if "avalement M5" in st["confirm"] and m > 0 and (
                        (C[m-1] > O[m-1] and C[m] < O[m] and O[m] >= C[m-1] and C[m] <= O[m-1]) if side < 0 else
                        (C[m-1] < O[m-1] and C[m] > O[m] and O[m] <= C[m-1] and C[m] >= O[m-1])):
                    st.update(status="CONFIRMÉE", trig="avalement M5", t_trig=x.index[m], entry=C[m])
                    break
                if "fin de repli M5" in st["confirm"] and m >= 3 and all(
                        (C[q] > O[q]) if side < 0 else (C[q] < O[q]) for q in (m-3, m-2, m-1)) and \
                        ((C[m] < O[m]) if side < 0 else (C[m] > O[m])):
                    st.update(status="CONFIRMÉE", trig="fin de repli M5", t_trig=x.index[m], entry=C[m])
                    break
            else:
                if len(x) - j > 12:
                    st["status"] = "expirée (pas de confirmation en 1 h)"
        out.append(st)
    return out


def main():
    from market import atr, bars
    from bias import daily_bias
    from plan import SPECS
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("symbol")
    p.add_argument("--tf", default="15m")
    a = p.parse_args()
    sym = a.symbol.upper()
    tick = SPECS[sym][0]
    _, d1 = bars(sym, "1d", 200)
    b, *_ , btxt = daily_bias(sym, d1)
    _, df = bars(sym, a.tf, 10 if a.tf in ("5m", "15m") else 40)
    last = df.close.iloc[-1]
    at = atr(df)
    print(f"{sym} {a.tf} dernier {last:.2f} ; biais du jour : {btxt}")
    sides = [b] if b else [-1, 1]
    for side in sides:
        for s in find_setups(df, side)[:3]:
            buf = 0.1 * at
            stop = s["far"] + buf if side < 0 else s["far"] - buf
            risk = abs(stop - s["entry"])
            tgt = s["entry"] - 2 * risk if side < 0 else s["entry"] + 2 * risk
            fv = f" ; FVG {s['fvg'][0]:.2f}-{s['fvg'][1]:.2f}" if s["fvg"] else ""
            print(f"  {'VENTE' if side < 0 else 'ACHAT'} {s['kind']} (bougie {s['t']:%d/%m %H:%M}, cassure {s['bos']:%H:%M}{fv})")
            print(f"     entrée {s['entry']:.2f} ({(s['entry'] - last) / tick:+.0f} ticks du prix)  stop {stop:.2f}  objectif 2R {tgt:.2f}"
                  f"  = {risk / tick:.0f} / {2 * risk / tick:.0f} ticks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
