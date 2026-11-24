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
OR_START = {"MGC": (8, 20), "GC": (8, 20), "MCL": (9, 0), "CL": (9, 0)}  # heure NY ; sinon 9h30


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

    # lecture des dernières bougies (anatomie d'abord, figure ensuite)
    from candles import describe, patterns
    print("\nBOUGIES (la dernière peut être en cours)")
    for lab, df in (("H1", h1), ("M15", m15)):
        dd, sens = patterns(df[["open", "high", "low", "close"]])
        for t, r in dd.tail(2).iterrows():
            figs = [k for k in sens if r[k]]
            print(f"  {lab:3s} {t:%d/%m %H:%M}  {describe(r)}" + (f"  [{', '.join(figs)}]" if figs else ""))

    # 5. SETUPS DE BASE (cassure + retest d'un niveau, range d'ouverture), puis les 4 étapes en confirmation
    cand = []
    sbuf = max(1.5 * a15, MIN_STOP_TICKS.get(sym, 10) * tick)
    hh, mm = OR_START.get(sym, (9, 30))
    _, m5 = bars(sym, "5m", 2)
    t5 = m5.index.tz_convert(NY)
    end = time(hh, mm + 15) if mm + 15 < 60 else time(hh + 1, mm - 45)
    orb = m5[(t5.date == t5[-1].date()) & (t5.time >= time(hh, mm)) & (t5.time < end)]
    or_txt = f"{(pd.Timestamp('2000-01-01 ' + f'{hh}:{mm:02d}').tz_localize(NY).tz_convert(m15.index.tz)):%Hh%M}"

    def confirm(side):
        d = 1 if side == "long" else -1
        lines = []
        if trend == d:
            t_ok = "ok"
            lines.append("✅ 1. tendance HMA H1 + H4 dans le sens du trade")
        elif trend == 0:
            t_ok = "mixte"
            lines.append("⚠️ 1. tendance mixte (H1 et H4 en désaccord) : au test, pas d'avantage")
        else:
            t_ok = "contre"
            lines.append("❌ 1. contre la tendance HMA : au test, perdant (-0,13 à -0,41 R par trade)")
        lines.append(f"ℹ️ 2. prix en {zone.split(' ')[0].lower()} du range H1 (information : non filtrant au test)")
        ph_ok = True
        lines.append(f"ℹ️ 3. phase {phase.split(' ')[0].lower()} (information : pas d'effet mesuré au test)")
        return t_ok, ph_ok, lines

    def add(kind, side, entry, stop, targets, cond):
        risk = abs(entry - stop)
        for j, (tname, tg) in enumerate(targets):
            rr = abs(tg - entry) / risk
            if rr < 1.5:
                continue
            if j:
                cond += " ; obstacles avant l'objectif : " + ", ".join(f"{x[1]:.2f}" for x in targets[:j]) + " (sortie partielle possible)"
            t_ok, ph_ok, lines = confirm(side)
            lines.append(f"✅ 4. objectif sur la liquidité : {tg:.2f} ({tname}), {rr:.1f} R")
            verdict = {"contre": "À ÉVITER", "mixte": "ATTENDRE que H1 et H4 s'accordent"}.get(t_ok) or \
                "CONFIRMÉ (tendance)"
            rank = 0 if verdict.startswith("CONFIRMÉ") else 2 if t_ok == "mixte" else 3
            cand.append((rank, kind, side, round(entry / tick) * tick, round(stop / tick) * tick,
                         round(tg / tick) * tick, tname, rr, cond, lines, verdict))
            return

    check = (f"checklist sur la bougie H1 de cassure : clôture franche, corps > {ah1:.2f} (1 ATR H1), volume >= 2x la moyenne, "
             "RSI > 65 pour un achat ou < 35 pour une vente, heure 17h-19h30 ou 13h")
    if len(orb) >= 3:
        oh, ol = orb.high.max(), orb.low.min()
        print(f"\n  Range d'ouverture {or_txt} (15 min) : {ol:.2f} - {oh:.2f}")
        add("Range d'ouverture", "long", oh, min((oh + ol) / 2, oh - sbuf),
            [x for x in above if x[1] > oh], f"clôture M5 ou M15 au-dessus de {oh:.2f} ; {check}")
        add("Range d'ouverture", "short", ol, max((oh + ol) / 2, ol + sbuf), [x for x in below if x[1] < ol],
            f"clôture M5 ou M15 sous {ol:.2f} ; {check}")
    else:
        print(f"\n  Range d'ouverture : se forme à {or_txt} (15 min), relancer l'analyse ensuite")
    for lvl in above[:2]:
        add("Cassure + retest", "long", lvl[1], lvl[1] - sbuf, [x for x in above if x[1] > lvl[1]],
            f"clôture H1 au-dessus de {lvl[1]:.2f} ({lvl[0]}), puis retour sur le niveau ; {check}")
    for lvl in below[:2]:
        add("Cassure + retest", "short", lvl[1], lvl[1] + sbuf, [x for x in below if x[1] < lvl[1]],
            f"clôture H1 sous {lvl[1]:.2f} ({lvl[0]}), puis retour sur le niveau ; {check}")
    cand.sort(key=lambda c: (c[0], 0 if c[1].startswith("Cassure") else 1, -c[7]))
    print("\n5. SETUPS DE BASE + CONFIRMATION PAR LES 4 ÉTAPES (entrée seulement après la condition)")
    shown = 0
    for (rank, kind, side, e, s, t, tname, rr, cond, lines, verdict) in cand:
        if rank >= 3:
            continue
        shown += 1
        br, size, pv = run_plan(sym, side, e, s, t, a)
        print(f"{shown}. {kind} {'ACHAT' if side == 'long' else 'VENTE'} : {verdict}")
        print(f"   entrée {e:.2f}  stop {s:.2f}  objectif {t:.2f}  ({br.replace('Bracket  ', 'bracket ')})")
        print(f"   Condition : {cond}")
        for ln in lines:
            print(f"   {ln}")
        print(f"   {size} | {pv}")
    if not shown:
        print("  aucun setup confirmé : attendre")
    bad = [c for c in cand if c[0] >= 3]
    if bad:
        print("  À éviter (contre la tendance HMA) : " + ", ".join(f"{c[1]} {'achat' if c[2] == 'long' else 'vente'} {c[3]:.2f}" for c in bad))
    cand = [c for c in cand if c[0] < 3]

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
