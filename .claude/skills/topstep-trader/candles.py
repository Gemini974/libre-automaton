#!/usr/bin/env python3
"""topstep-trader : lecture des bougies japonaises.

Décrit chaque bougie (corps, mèches, clôture, taille par rapport à l'ATR, qui
contrôle), reconnaît les figures à 1, 2 et 3 bougies sans regarder la bougie
suivante, et donne le contexte (tendance des 5 bougies précédentes). Ajoute la
lecture Heikin-Ashi (bougies lissées) pour la tendance.

  /opt/openbb/bin/python candles.py MGC              # 6 dernières bougies M15 et H1
  /opt/openbb/bin/python candles.py MBT --tf 1h --n 10
"""
import argparse
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def anatomy(df, n_atr=14):
    """Colonnes de base : corps, mèches, position de clôture, taille en ATR."""
    d = df.copy()
    rng = (d.high - d.low).replace(0, np.nan)
    d["body"] = (d.close - d.open).abs()
    d["dir"] = np.sign(d.close - d.open)
    d["upw"] = d.high - d[["open", "close"]].max(axis=1)
    d["low_w"] = d[["open", "close"]].min(axis=1) - d.low
    d["body_pct"] = d.body / rng
    d["clo"] = (d.close - d.low) / rng  # 0 = clôture au plus bas, 1 = au plus haut
    tr = pd.concat([d.high - d.low, (d.high - d.close.shift()).abs(), (d.low - d.close.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.rolling(n_atr).mean().shift()
    d["size"] = (d.high - d.low) / d.atr
    d["trend5"] = np.sign(d.close.shift(1) - d.close.shift(6))  # tendance des 5 bougies AVANT
    return d


def patterns(df):
    """Figures reconnues sur chaque bougie, avec le sens attendu (+1 haussier, -1 baissier, 0 indécision)."""
    d = anatomy(df)
    o, h, lo, c = d.open, d.high, d.low, d.close
    p1 = d.shift(1)
    p2 = d.shift(2)
    small = d.body_pct <= 0.1
    big = (d.body_pct >= 0.85) & (d.size >= 1.0)
    out = {
        # une bougie
        "Doji": (small & (d.upw > 0) & (d.low_w > 0) & (d.upw / (d.low_w + 1e-9)).between(0.33, 3), 0),
        "Doji libellule": (small & (d.low_w >= 2 * d.upw) & (d.clo >= 0.8), 1),
        "Doji pierre tombale": (small & (d.upw >= 2 * d.low_w) & (d.clo <= 0.2), -1),
        "Marteau": ((d.body_pct.between(0.1, 0.35)) & (d.low_w >= 2 * d.body) & (d.upw <= d.body) & (d.trend5 < 0), 1),
        "Pendu": ((d.body_pct.between(0.1, 0.35)) & (d.low_w >= 2 * d.body) & (d.upw <= d.body) & (d.trend5 > 0), -1),
        "Étoile filante": ((d.body_pct.between(0.1, 0.35)) & (d.upw >= 2 * d.body) & (d.low_w <= d.body) & (d.trend5 > 0), -1),
        "Marteau inversé": ((d.body_pct.between(0.1, 0.35)) & (d.upw >= 2 * d.body) & (d.low_w <= d.body) & (d.trend5 < 0), 1),
        "Marubozu haussier": (big & (d.dir > 0), 1),
        "Marubozu baissier": (big & (d.dir < 0), -1),
        "Toupie": ((d.body_pct.between(0.1, 0.3)) & (d.upw > d.body) & (d.low_w > d.body), 0),
        # deux bougies
        "Avalement haussier": ((p1.dir < 0) & (d.dir > 0) & (o <= p1.close) & (c >= p1.open) & (d.body > p1.body), 1),
        "Avalement baissier": ((p1.dir > 0) & (d.dir < 0) & (o >= p1.close) & (c <= p1.open) & (d.body > p1.body), -1),
        "Harami haussier": ((p1.dir < 0) & (p1.body_pct >= 0.6) & (d.dir > 0) & (o > p1.close) & (c < p1.open) & (d.body < 0.5 * p1.body), 1),
        "Harami baissier": ((p1.dir > 0) & (p1.body_pct >= 0.6) & (d.dir < 0) & (o < p1.close) & (c > p1.open) & (d.body < 0.5 * p1.body), -1),
        "Pénétrante": ((p1.dir < 0) & (p1.body_pct >= 0.6) & (d.dir > 0) & (o <= p1.low) & (c > (p1.open + p1.close) / 2) & (c < p1.open), 1),
        "Couverture en nuage noir": ((p1.dir > 0) & (p1.body_pct >= 0.6) & (d.dir < 0) & (o >= p1.high) & (c < (p1.open + p1.close) / 2) & (c > p1.open), -1),
        "Pinces basses": (((lo - p1.low).abs() <= 0.05 * d.atr) & (p1.dir < 0) & (d.dir > 0), 1),
        "Pinces hautes": (((h - p1.high).abs() <= 0.05 * d.atr) & (p1.dir > 0) & (d.dir < 0), -1),
        "Inside bar": ((h < p1.high) & (lo > p1.low), 0),
        "Outside bar haussière": ((h > p1.high) & (lo < p1.low) & (d.clo >= 0.75), 1),
        "Outside bar baissière": ((h > p1.high) & (lo < p1.low) & (d.clo <= 0.25), -1),
        # trois bougies
        "Étoile du matin": ((p2.dir < 0) & (p2.body_pct >= 0.6) & (p1.body_pct <= 0.3) & (d.dir > 0) & (c > (p2.open + p2.close) / 2), 1),
        "Étoile du soir": ((p2.dir > 0) & (p2.body_pct >= 0.6) & (p1.body_pct <= 0.3) & (d.dir < 0) & (c < (p2.open + p2.close) / 2), -1),
        "Trois soldats blancs": ((d.dir > 0) & (p1.dir > 0) & (p2.dir > 0) & (c > p1.close) & (p1.close > p2.close)
                                 & (d.body_pct >= 0.6) & (p1.body_pct >= 0.6) & (p2.body_pct >= 0.6), 1),
        "Trois corbeaux noirs": ((d.dir < 0) & (p1.dir < 0) & (p2.dir < 0) & (c < p1.close) & (p1.close < p2.close)
                                 & (d.body_pct >= 0.6) & (p1.body_pct >= 0.6) & (p2.body_pct >= 0.6), -1),
    }
    for name, (mask, _) in out.items():
        d[name] = mask.fillna(False)
    return d, {k: v[1] for k, v in out.items()}


def heikin_ashi(df):
    """Bougies Heikin-Ashi (méthode du dépôt je-suis-tm/quant-trading)."""
    ha = pd.DataFrame(index=df.index)
    ha["close"] = (df.open + df.high + df.low + df.close) / 4
    op = [df.open.iloc[0]]
    for i in range(1, len(df)):
        op.append((op[-1] + ha.close.iloc[i - 1]) / 2)
    ha["open"] = op
    ha["high"] = pd.concat([ha.open, ha.close, df.high], axis=1).max(axis=1)
    ha["low"] = pd.concat([ha.open, ha.close, df.low], axis=1).min(axis=1)
    return ha


def describe(row, tick=None):
    """Une phrase sur la bougie : couleur, taille, corps, mèches (en ticks si tick est donné), clôture, qui contrôle."""
    if np.isnan(row.atr) or row.high == row.low:
        return "données insuffisantes"
    col = "verte" if row.dir > 0 else "rouge" if row.dir < 0 else "neutre"
    tk = (lambda x: f"{int(round(x / tick))} t") if tick else (lambda x: f"{x:.2f}")
    size = "grande" if row["size"] >= 1.3 else "petite" if row["size"] <= 0.6 else "moyenne"
    body = f"corps {row.body_pct*100:.0f} % ({tk(row.body)}), mèche haute {tk(row.upw)}, mèche basse {tk(row.low_w)}"
    wick = []
    rng = row.high - row.low
    if row.upw / rng >= 0.4:
        wick.append("longue mèche haute (vendeurs ont rejeté le haut)")
    if row.low_w / rng >= 0.4:
        wick.append("longue mèche basse (acheteurs ont rejeté le bas)")
    clo = row.clo
    ctrl = ("acheteurs en contrôle" if clo >= 0.75 else "vendeurs en contrôle" if clo <= 0.25 else "indécision")
    return f"{col}, {size} ({tk(row.high - row.low)} = {row['size']:.1f} ATR), {body}, clôture à {clo*100:.0f} % de la bougie : {ctrl}" + \
        (" ; " + ", ".join(wick) if wick else "")


def main():
    from market import bars
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("symbol")
    p.add_argument("--tf", nargs="*", default=["15m", "1h"])
    p.add_argument("--n", type=int, default=6)
    a = p.parse_args()
    from plan import SPECS
    tick = SPECS.get(a.symbol.upper(), (None, 0))[0]
    for tf in a.tf:
        _, df = bars(a.symbol.upper(), tf, 5 if tf in ("5m", "15m") else 30)
        d, sens = patterns(df)
        ha = heikin_ashi(df)
        print(f"\n{a.symbol.upper()} {tf} : {a.n} dernières bougies (heure de La Réunion ; la dernière peut être en cours)")
        for t, r in d.tail(a.n).iterrows():
            figs = [f"{k} ({'haussier' if sens[k] > 0 else 'baissier' if sens[k] < 0 else 'indécision'})" for k in sens if r[k]]
            print(f"  {t:%d/%m %H:%M}  O {r.open:.2f} H {r.high:.2f} B {r.low:.2f} C {r.close:.2f}  {describe(r, tick)}")
            if figs:
                print(f"               figure : {', '.join(figs)}")
        last = ha.tail(3)
        up = (last.close > last.open).sum()
        nowick = ((last.close > last.open) & (last.low >= last.open)).sum() + ((last.close < last.open) & (last.high <= last.open)).sum()
        print(f"  Heikin-Ashi : {up}/3 vertes sur les 3 dernières, {nowick} sans mèche contraire "
              f"({'tendance nette' if nowick >= 2 else 'tendance faible ou retournement possible'})")


if __name__ == "__main__":
    sys.exit(main())
