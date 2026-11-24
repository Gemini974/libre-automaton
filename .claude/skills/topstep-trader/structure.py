#!/usr/bin/env python3
"""topstep-trader : biais daily et structure du prix, puis setups classés.

Ne prédit pas la direction. Décrit la structure (sommets et creux, cassures de
structure), le biais Daily / H4 / H1, les niveaux de liquidité, puis propose les
setups les mieux placés et les passe par plan.py (PASS / BLOCK).

  /opt/openbb/bin/python structure.py MGC
  /opt/openbb/bin/python structure.py MBT --chart /chemin/mbt.png --day-pnl 120
"""
import argparse
import subprocess
import sys
import warnings
from datetime import time
from pathlib import Path

warnings.filterwarnings("ignore")
import pandas as pd  # noqa: E402

from market import NY, atr, bars  # noqa: E402
from plan import SPECS  # noqa: E402

HERE = Path(__file__).resolve().parent
MIN_STOP_TICKS = {"MBT": 130, "MET": 130}  # amplitude habituelle du soir (CLAUDE.md)


def swings(df, n):
    """Sommets et creux confirmés : plus haut (plus bas) des n bougies de chaque côté."""
    out = []
    h, lo = df.high.values, df.low.values
    for i in range(n, len(df) - n):
        if h[i] == max(h[i - n:i + n + 1]):
            out.append((df.index[i], h[i], "H"))
        if lo[i] == min(lo[i - n:i + n + 1]):
            out.append((df.index[i], lo[i], "L"))
    return out


def structure(df, n):
    """Tendance par sommets et creux, et dernière cassure de structure (BOS ou CHoCH)."""
    sw = swings(df, n)
    hs = [s for s in sw if s[2] == "H"][-3:]
    ls = [s for s in sw if s[2] == "L"][-3:]
    labels = []
    for grp, up, dn in ((hs, "HH", "LH"), (ls, "HL", "LL")):
        for a, b in zip(grp, grp[1:]):
            labels.append((b[0], b[1], up if b[1] > a[1] else dn))
    trend = 0
    if len(hs) >= 2 and len(ls) >= 2:
        hh, hl = hs[-1][1] > hs[-2][1], ls[-1][1] > ls[-2][1]
        trend = 1 if hh and hl else -1 if not hh and not hl else 0
    last = df.close.iloc[-1]
    event = ""
    if hs and last > hs[-1][1]:
        event = ("BOS haussier" if trend >= 0 else "CHoCH haussier") + f" (clôture au-dessus de {hs[-1][1]:.2f})"
    elif ls and last < ls[-1][1]:
        event = ("BOS baissier" if trend <= 0 else "CHoCH baissier") + f" (clôture sous {ls[-1][1]:.2f})"
    return trend, event, hs, ls, labels


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def window(df, a, b):
    """Bougies entre a et b heure de New York (a > b : passe minuit)."""
    t = df.index.tz_convert(NY).time
    m = (t >= a) | (t < b) if a > b else (t >= a) & (t < b)
    return df[m]


def run_plan(sym, side, entry, stop, target, a):
    cmd = ["python3", str(HERE / "plan.py"), "plan", "--symbol", sym, "--side", side, "--entry", f"{entry}",
           "--stop", f"{stop}", "--target", f"{target}", "--max-risk", f"{a.max_risk}", "--day-pnl", f"{a.day_pnl}"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip().splitlines()
    br = next((x.strip() for x in out if x.strip().startswith("Bracket")), "")
    size = next((x.strip() for x in out if x.strip().startswith("Taille")), "")
    verdict = next((x for x in out if x.startswith(("PASS", "BLOCK"))), "?")
    return br, size, verdict


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("symbol")
    p.add_argument("--chart", help="fichier PNG du graphique annoté (M15, 2 jours)")
    p.add_argument("--max-risk", type=float, default=160.0, help="risque max par trade en $ (choix de l'utilisateur)")
    p.add_argument("--day-pnl", type=float, default=0.0)
    a = p.parse_args()
    sym = a.symbol.upper()
    tick = SPECS.get(sym, (0.01, 1))[0]
    y, d1 = bars(sym, "1d", 200)
    _, h1 = bars(sym, "1h", 40)
    _, m15 = bars(sym, "15m", 5)
    h4 = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    last = m15.close.iloc[-1]
    a15, ah1 = atr(m15), atr(h1)

    # 1. Structure par unité de temps
    print(f"{sym} ({y})  dernier {last:.2f}  à {m15.index[-1]:%d/%m %H:%M} (La Réunion, données retardées)")
    print(f"ATR M15 {a15:.2f}  ATR H1 {ah1:.2f}\n\nSTRUCTURE")
    score, reasons = 0, []
    names = {1: "haussière (HH + HL)", -1: "baissière (LH + LL)", 0: "range / mixte"}
    st = {}
    for lab, df, n in (("Daily", d1.iloc[:-1], 3), ("H4", h4, 3), ("H1", h1, 4)):
        tr, ev, hs, ls, labels = structure(df, n)
        st[lab] = (tr, hs, ls, labels)
        e20, e50 = ema(df.close, 20).iloc[-1], ema(df.close, 50).iloc[-1]
        side = "au-dessus" if df.close.iloc[-1] > e20 > e50 else "sous" if df.close.iloc[-1] < e20 < e50 else "entre"
        sh = f"{hs[-1][1]:.2f}" if hs else "-"
        sl = f"{ls[-1][1]:.2f}" if ls else "-"
        print(f"  {lab:6s} {names[tr]:22s} dernier sommet {sh}  dernier creux {sl}  prix {side} EMA20/50  {ev}")
        if lab in ("Daily", "H4"):
            score += tr + (1 if side == "au-dessus" else -1 if side == "sous" else 0)
            reasons.append(f"{lab} {names[tr]}, prix {side} EMA20/50")

    # 2. Niveaux de liquidité
    nyt = m15.index.tz_convert(NY)
    cday = (nyt + pd.Timedelta(hours=6)).date  # journée CME : 18h NY la veille -> 17h
    cur = m15[cday == cday[-1]]
    hd = (h1.index.tz_convert(NY) + pd.Timedelta(hours=6)).date  # veille calculée sur les bougies H1
    pv = h1[hd == sorted(set(d for d, w in zip(hd, h1.index.tz_convert(NY).weekday) if d < cday[-1] and w < 5))[-1]]
    prev = pd.Series({"high": pv.high.max(), "low": pv.low.min(), "close": pv.close.iloc[-1]})
    asia = window(cur, time(18), time(0))
    lon = window(cur, time(2), time(5))
    mo_bar = window(cur, time(0), time(0, 15))
    mo = mo_bar.open.iloc[0] if len(mo_bar) else None
    lv = {"Veille haut": prev.high, "Veille bas": prev.low, "Veille clôture": prev.close,
          "Jour haut": cur.high.max(), "Jour bas": cur.low.min(),
          "20 j haut": d1.high.iloc[-21:-1].max(), "20 j bas": d1.low.iloc[-21:-1].min()}
    if len(asia):
        lv.update({"Asie haut": asia.high.max(), "Asie bas": asia.low.min()})
    if len(lon):
        lv.update({"Londres haut": lon.high.max(), "Londres bas": lon.low.min()})
    if mo:
        lv["Ouverture minuit NY"] = mo
    for t, px, kind in st["H1"][1][-2:] + st["H1"][2][-2:]:
        lv[f"Swing H1 {'haut' if kind == 'H' else 'bas'} {t:%d/%m %Hh}"] = px
    # fusion des niveaux proches (moins de 0,3 ATR M15)
    merged = []
    for name, px in sorted(lv.items(), key=lambda x: x[1]):
        if merged and px - merged[-1][1] < 0.3 * a15:
            merged[-1] = (merged[-1][0] + " + " + name, (merged[-1][1] + px) / 2)
        else:
            merged.append((name, px))
    above = [x for x in merged if x[1] > last + 0.2 * a15]
    below = [x for x in merged if x[1] < last - 0.2 * a15][::-1]
    print("\nNIVEAUX (du plus haut au plus bas)")
    for name, px in merged[::-1]:
        mark = "  <- prix" if abs(px - last) <= 0.2 * a15 else ""
        print(f"  {px:10.2f}  {name}{mark}")

    # 3. Biais
    if mo:
        moside = 1 if last > mo else -1
        reasons.append(f"prix {'au-dessus de' if moside > 0 else 'sous'} l'ouverture de minuit ({mo:.2f}), repère testé : 55 % sur 2 ans")
        score += moside
    pos = (last - lv["20 j bas"]) / (lv["20 j haut"] - lv["20 j bas"])
    bias = 1 if score >= 2 else -1 if score <= -2 else 0
    btxt = {1: "ACHAT prioritaire", -1: "VENTE prioritaire", 0: "NEUTRE : jouer les bornes du range"}[bias]
    print(f"\nBIAIS DU JOUR : {btxt}  (score {score:+d} sur ±5)")
    for r in reasons:
        print(f"  - {r}")
    print(f"  - position dans la plage de 20 jours : {pos*100:.0f} % (information, pas un signal)")

    # 4. Setups : retour sur niveau et cassure-retest, stop >= 1,5 ATR M15
    cand = []
    sbuf = max(1.5 * a15, MIN_STOP_TICKS.get(sym, 10) * tick)

    def add(kind, side, entry, stop, targets, cond):
        risk = abs(entry - stop)
        for j, (tname, tg) in enumerate(targets):
            rr = abs(tg - entry) / risk
            if rr >= 1.5:
                if j:
                    cond += " ; obstacles avant l'objectif : " + ", ".join(f"{x[1]:.2f}" for x in targets[:j]) + " (sortie partielle possible)"
                sc = (2 if side == ("long" if bias > 0 else "short" if bias < 0 else "") else 0) + (1 if rr >= 2 else 0)
                if bias == 0 and kind.startswith("Rejet"):
                    sc += 1
                cand.append((sc, kind, side, round(entry / tick) * tick, round(stop / tick) * tick,
                             round(tg / tick) * tick, tname, rr, cond))
                return

    if below:
        s1 = below[0]
        add("Rejet sur support", "long", s1[1], s1[1] - sbuf, above[:4],
            f"bougie M15 de rejet sur {s1[1]:.2f} ({s1[0]}) : mèche basse, clôture au-dessus")
    if above:
        r1 = above[0]
        add("Rejet sur résistance", "short", r1[1], r1[1] + sbuf, below[:4],
            f"bougie M15 de rejet sur {r1[1]:.2f} ({r1[0]}) : mèche haute, clôture en dessous")
        add("Cassure-retest", "long", r1[1], r1[1] - sbuf, above[1:4],
            f"clôture H1 au-dessus de {r1[1]:.2f} conforme à la checklist (corps, volume, RSI), puis retour sur le niveau")
    if below:
        add("Cassure-retest", "short", s1[1], s1[1] + sbuf, below[1:4],
            f"clôture H1 sous {s1[1]:.2f} conforme à la checklist, puis retour sur le niveau")
    cand.sort(key=lambda c: (-c[0], -c[7]))
    print("\nSETUPS CLASSÉS (fenêtre 17h20-19h30 ; entrée seulement après la confirmation)")
    for k, (sc, kind, side, e, s, t, tname, rr, cond) in enumerate(cand, 1):
        br, size, verdict = run_plan(sym, side, e, s, t, a)
        print(f"{k}. {kind} {'ACHAT' if side == 'long' else 'VENTE'}  score {sc}  entrée {e:.2f}  stop {s:.2f}  objectif {t:.2f} ({tname})  R {rr:.1f}")
        print(f"   Condition : {cond}")
        print(f"   {br} | {size}")
        print(f"   {verdict}")
    if not cand:
        print("  aucun setup avec un rendement/risque d'au moins 1,5 : attendre")

    if a.chart:
        draw(a.chart, sym, m15, merged, st["H1"][3], cand, last)
        print(f"\nGraphique : {a.chart}")


def draw(path, sym, m15, levels, labels, cand, last):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    df = m15[m15.index >= m15.index[-1] - pd.Timedelta(hours=36)]
    x = range(len(df))
    fig, ax = plt.subplots(figsize=(7, 9), dpi=150)
    fig.patch.set_facecolor("#131722")
    ax.set_facecolor("#131722")
    for i, (_, r) in zip(x, df.iterrows()):
        c = "#26a69a" if r.close >= r.open else "#ef5350"
        ax.plot([i, i], [r.low, r.high], color=c, lw=0.8)
        ax.add_patch(plt.Rectangle((i - 0.35, min(r.open, r.close)), 0.7, max(abs(r.close - r.open), 1e-9), color=c))
    lo, hi = df.low.min(), df.high.max()
    pad = (hi - lo) * 0.08
    for name, px in levels:
        if lo - pad <= px <= hi + pad:
            col = "#f0b90b" if "minuit" in name else "#5b8def"
            ax.axhline(px, color=col, lw=0.8, ls="--")
            ax.text(len(df) + 13, px, f"{px:.2f} {name[:26]}", color=col, fontsize=6, va="bottom")
    for t, px, lab in labels:
        if t >= df.index[0]:
            i = df.index.get_indexer([t], method="nearest")[0]
            ax.text(i, px, lab, color="white", fontsize=7, ha="center", va="bottom" if lab in ("HH", "LH") else "top")
    for k, (sc, kind, side, e, s, tg, *_ ) in enumerate(cand[:2], 1):
        x0 = len(df) + 1 + (k - 1) * 5
        ax.add_patch(plt.Rectangle((x0, min(e, s)), 3, abs(e - s), color="#ef5350", alpha=0.35))
        ax.add_patch(plt.Rectangle((x0, min(e, tg)), 3, abs(tg - e), color="#26a69a", alpha=0.35))
        ax.text(x0 + 1.5, max(e, tg, s), f"{k} {'A' if side == 'long' else 'V'}", color="white", fontsize=8, ha="center", va="bottom")
    ax.axhline(last, color="white", lw=0.5)
    ax.set_xlim(-1, len(df) + 45)
    ax.set_ylim(lo - pad, hi + pad)
    step = max(1, len(df) // 6)
    ax.set_xticks(list(x)[::step])
    ax.set_xticklabels([t.strftime("%d %Hh") for t in df.index[::step]], color="#aaa", fontsize=7)
    ax.tick_params(colors="#aaa", labelsize=7)
    ax.set_title(f"{sym} M15 – structure et niveaux (La Réunion)", color="white", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    sys.exit(main())
