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
import numpy as np  # noqa: E402
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


def wma(s, n):
    w = np.arange(1, n + 1)
    return s.rolling(n).apply(lambda x: (x * w).sum() / w.sum(), raw=True)


def hma(s, n=21):
    """Moyenne mobile de Hull : donne la tendance (pente), pas un signal d'entrée."""
    return wma(2 * wma(s, n // 2) - wma(s, n), int(np.sqrt(n)))


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

    print(f"{sym} ({y})  dernier {last:.2f}  à {m15.index[-1]:%d/%m %H:%M} (La Réunion, données retardées)")
    print(f"ATR M15 {a15:.2f}  ATR H1 {ah1:.2f}")

    # 1. TENDANCE : pente de la HMA 21 (la structure HH/HL sert de contexte)
    print("\n1. TENDANCE (pente HMA 21 ; structure en contexte)")
    names = {1: "HH + HL", -1: "LH + LL", 0: "mixte"}
    st, slope = {}, {}
    for lab, df, n in (("Daily", d1.iloc[:-1], 3), ("H4", h4, 3), ("H1", h1, 4)):
        tr, ev, hs, ls, labels = structure(df, n)
        st[lab] = (tr, hs, ls, labels)
        h = hma(df.close, 21)
        slope[lab] = 1 if h.iloc[-1] > h.iloc[-2] else -1
        print(f"  {lab:6s} HMA 21 {'monte  ' if slope[lab] > 0 else 'descend'}  prix {'au-dessus' if df.close.iloc[-1] > h.iloc[-1] else 'sous'} ({h.iloc[-1]:.2f})"
              f"  structure {names[tr]}  {ev}")
    trend = slope["H1"] if slope["H1"] == slope["H4"] else 0
    ttxt = {1: "HAUSSIÈRE (H4 et H1 d'accord)", -1: "BAISSIÈRE (H4 et H1 d'accord)",
            0: f"MIXTE (H4 {'monte' if slope['H4'] > 0 else 'descend'}, H1 {'monte' if slope['H1'] > 0 else 'descend'})"}[trend]
    print(f"  => tendance {ttxt}. Testé sur l'or : trader contre la pente HMA H1 a perdu (-0,17 R par trade).")

    # niveaux de la journée
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

    # 2. OÙ EST LE PRIX : range de travail H1 (dernier sommet et dernier creux), premium ou discount
    _, hs, ls, _ = st["H1"]
    rh, rl = hs[-1][1], ls[-1][1]
    rh, rl = max(rh, cur.high.max()), min(rl, cur.low.min())
    pos = (last - rl) / (rh - rl) if rh > rl else 0.5
    zone = "PREMIUM (cher)" if pos > 0.55 else "DISCOUNT (bon marché)" if pos < 0.45 else "ÉQUILIBRE"
    print(f"\n2. OÙ EST LE PRIX\n  Range de travail H1 {rl:.2f} - {rh:.2f}, équilibre {(rh + rl) / 2:.2f} : prix à {pos*100:.0f} % => {zone}")
    if mo:
        print(f"  {'Au-dessus' if last > mo else 'Sous'} l'ouverture de minuit {mo:.2f}")
    p20h, p20l = d1.high.iloc[-21:-1].max(), d1.low.iloc[-21:-1].min()
    print(f"  Plage de 20 jours {p20l:.2f} - {p20h:.2f} : {(last - p20l) / (p20h - p20l) * 100:.0f} %")

    # 3. PHASE : accumulation, retracement, expansion, distribution (H1, 12 dernières bougies)
    c = h1.close
    w = c.iloc[-13:]
    move = w.iloc[-1] - w.iloc[0]
    er = abs(move) / w.diff().abs().sum()
    rng = (h1.high.iloc[-12:].max() - h1.low.iloc[-12:].min()) / ah1
    prior = c.iloc[-13] - c.iloc[-37]
    last6 = c.iloc[-1] - c.iloc[-7]
    if er >= 0.5 and abs(move) >= 2 * ah1:
        phase = f"EXPANSION {'haussière' if move > 0 else 'baissière'}"
        pnote = "ne pas courir après le prix : attendre le retracement"
    elif trend and np.sign(last6) == -trend and 0.25 <= ((rh - last) if trend > 0 else (last - rl)) / (rh - rl) <= 0.85:
        phase = "RETRACEMENT " + ("d'une hausse" if trend > 0 else "d'une baisse")
        pnote = f"zone d'entrée dans le sens de la tendance quand le prix est en {'discount' if trend > 0 else 'premium'}"
    elif er < 0.35 and rng <= 4:
        if prior < 0 or pos < 0.5:
            phase, pnote = "ACCUMULATION (range après une baisse)", "attendre la sortie du range (Wyckoff : plutôt par le haut, non testé) ou le balayage du bas"
        else:
            phase, pnote = "DISTRIBUTION (range après une hausse)", "attendre la sortie du range (Wyckoff : plutôt par le bas, non testé) ou le balayage du haut"
    else:
        phase, pnote = "TRANSITION (pas de phase nette)", "réduire la taille ou attendre"
    print(f"\n3. PHASE : {phase}\n  efficacité du mouvement {er:.2f}, amplitude {rng:.1f} ATR H1 sur 12 h ; {pnote}")

    # 4. LIQUIDITÉ : sommets et creux non pris (stops au-dessus et en dessous), sommets ou creux égaux
    print("\n4. LIQUIDITÉ")
    swh = [s for s in swings(h1.iloc[-120:], 3) if s[2] == "H"]
    swl = [s for s in swings(h1.iloc[-120:], 3) if s[2] == "L"]
    pools = {"Veille haut": prev.high, "Veille bas": prev.low}
    if len(asia):
        pools.update({"Asie haut": asia.high.max(), "Asie bas": asia.low.min()})
    if len(lon):
        pools.update({"Londres haut": lon.high.max(), "Londres bas": lon.low.min()})
    for t, px, k in swh + swl:
        after = h1[h1.index > t]
        taken = (after.high.max() > px) if k == "H" else (after.low.min() < px)
        if not taken:
            pools[f"Swing H1 {'haut' if k == 'H' else 'bas'} {t:%d/%m %Hh} non pris"] = px
    for grp, k in ((swh, "hauts"), (swl, "bas")):
        for (t1, p1, _), (t2, p2, _) in zip(grp, grp[1:]):
            after = h1[h1.index > t2]
            untaken = after.high.max() <= max(p1, p2) if k == "hauts" else after.low.min() >= min(p1, p2)
            if abs(p1 - p2) <= 0.15 * ah1 and untaken:
                pools[f"{k.capitalize()} égaux {t1:%d/%m %Hh}-{t2:%d/%m %Hh}"] = max(p1, p2) if k == "hauts" else min(p1, p2)
    is_hi = lambda n: "haut" in n.lower()
    bsl = sorted([(n, p) for n, p in pools.items() if p > last and is_hi(n)], key=lambda x: x[1])
    ssl = sorted([(n, p) for n, p in pools.items() if p < last and not is_hi(n)], key=lambda x: -x[1])
    today_hi, today_lo = cur.high.max(), cur.low.min()
    for n, p in pools.items():
        if "Veille" in n and ((p == prev.high and today_hi > p) or (p == prev.low and today_lo < p)):
            print(f"  déjà prise aujourd'hui : {n} {p:.2f}")
    print("  Au-dessus (liquidité acheteuse, stops des vendeurs) : " + ", ".join(f"{p:.2f} {n}" for n, p in bsl[:4]))
    print("  En dessous (liquidité vendeuse, stops des acheteurs) : " + ", ".join(f"{p:.2f} {n}" for n, p in ssl[:4]))
    draw_on = (bsl[0] if trend > 0 and bsl else ssl[0] if trend < 0 and ssl else None)
    if draw_on:
        print(f"  Cible probable dans le sens de la tendance : {draw_on[1]:.2f} ({draw_on[0]})")
    bias = trend

    # niveaux pour les setups : liquidité + ouverture de minuit + jour
    lv = dict(pools)
    lv.update({"Jour haut": today_hi, "Jour bas": today_lo})
    if mo:
        lv["Ouverture minuit NY"] = mo
    merged = []
    for name, px in sorted(lv.items(), key=lambda x: x[1]):
        if merged and px - merged[-1][1] < 0.3 * a15:
            merged[-1] = (merged[-1][0] + " + " + name, (merged[-1][1] + px) / 2)
        else:
            merged.append((name, px))
    above = [x for x in merged if x[1] > last + 0.2 * a15]
    below = [x for x in merged if x[1] < last - 0.2 * a15][::-1]

    # 5. Setups : seulement dans le sens de la tendance HMA ; mieux placés en discount (achat) ou premium (vente)
    cand = []
    sbuf = max(1.5 * a15, MIN_STOP_TICKS.get(sym, 10) * tick)

    def add(kind, side, entry, stop, targets, cond):
        risk = abs(entry - stop)
        for j, (tname, tg) in enumerate(targets):
            rr = abs(tg - entry) / risk
            if rr >= 1.5:
                if j:
                    cond += " ; obstacles avant l'objectif : " + ", ".join(f"{x[1]:.2f}" for x in targets[:j]) + " (sortie partielle possible)"
                d = 1 if side == "long" else -1
                epos = (entry - rl) / (rh - rl) if rh > rl else 0.5
                sc = (2 if d == bias else 0) + (1 if rr >= 2 else 0) + (1 if (d > 0 and epos < 0.5) or (d < 0 and epos > 0.5) else 0)
                sc += 1 if "RETRACEMENT" in phase and d == bias else 0
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
    against = [c for c in cand if bias and (1 if c[2] == "long" else -1) != bias]
    cand = [c for c in cand if c not in against]
    cand.sort(key=lambda c: (-c[0], -c[7]))
    print("\n5. SETUPS DANS LE SENS DE LA TENDANCE (fenêtre 17h20-19h30 ; entrée seulement après la confirmation)")
    for k, (sc, kind, side, e, s, t, tname, rr, cond) in enumerate(cand, 1):
        br, size, verdict = run_plan(sym, side, e, s, t, a)
        print(f"{k}. {kind} {'ACHAT' if side == 'long' else 'VENTE'}  score {sc}  entrée {e:.2f}  stop {s:.2f}  objectif {t:.2f} ({tname})  R {rr:.1f}")
        print(f"   Condition : {cond}")
        print(f"   {br} | {size}")
        print(f"   {verdict}")
    if not cand:
        print("  aucun setup avec un rendement/risque d'au moins 1,5 : attendre")
    if against:
        print("  Écartés car contre la tendance HMA : " + ", ".join(f"{c[1]} {'achat' if c[2] == 'long' else 'vente'} {c[3]:.2f}" for c in against))

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
