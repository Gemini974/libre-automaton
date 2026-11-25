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


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


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
    tk = lambda x: int(round(x / tick))  # distance en ticks (ce que TopstepX affiche)
    dt_ = lambda px: f"{'+' if px >= last else '-'}{tk(abs(px - last))} ticks"
    print(f"Tick {tick} = {SPECS.get(sym, (0, 0))[1]:.2f} $ ; ATR M15 {a15:.2f} ({tk(a15)} ticks)  ATR H1 {ah1:.2f} ({tk(ah1)} ticks)")

    # 0. BIAIS DU JOUR = technique (EMA 20 / EMA 50 Daily, jours terminés) ET fondamental d'accord (bias.py)
    from bias import daily_bias
    print("\n0. BIAIS DU JOUR")
    day_bias, tech, fund, blines, btxt = daily_bias(sym, d1)
    for ln in blines:
        print("  " + ln)
    crypto = sym in ("MBT", "MET", "BTC")
    print("  Test sur 26 ans (or) et 9 ans (BTC) : les filtres fondamentaux de tendance n'ont pas amélioré le biais ;"
          " la règle d'accord est celle de l'utilisateur. Vérifier aussi le calendrier du jour (av.py macro, geo.py news,"
          + (" crypto.py flows" if crypto else " market.py macro") + ") : pas d'entrée 15 min avant ou après une annonce majeure.")

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
    print(f"\n2. OÙ EST LE PRIX\n  Range de travail H1 {rl:.2f} - {rh:.2f} ({tk(rh - rl)} ticks), équilibre {(rh + rl) / 2:.2f} ({dt_((rh + rl) / 2)}) : prix à {pos*100:.0f} % => {zone}")
    print(f"  Haut du range {dt_(rh)}, bas du range {dt_(rl)}")
    if mo:
        print(f"  {'Au-dessus' if last > mo else 'Sous'} l'ouverture de minuit {mo:.2f} ({dt_(mo)})")
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
    print("  Au-dessus (liquidité acheteuse, stops des vendeurs) : " + ", ".join(f"{p:.2f} {n} ({dt_(p)})" for n, p in bsl[:4]))
    print("  En dessous (liquidité vendeuse, stops des acheteurs) : " + ", ".join(f"{p:.2f} {n} ({dt_(p)})" for n, p in ssl[:4]))
    draw_on = (bsl[0] if trend > 0 and bsl else ssl[0] if trend < 0 and ssl else None)
    if draw_on:
        print(f"  Cible probable dans le sens de la tendance : {draw_on[1]:.2f} ({draw_on[0]}, {dt_(draw_on[1])})")

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

    # bougies : lues SEULEMENT quand elles touchent un support ou une résistance (règle de l'utilisateur)
    from candles import describe, patterns
    lvl_px = [px for _, px in merged]
    print("\nBOUGIES SUR NIVEAU (une bougie n'est lue que sur un support ou une résistance)")
    seen = False
    for lab, df, at in (("H1", h1, ah1), ("M15", m15, a15)):
        dd, sens = patterns(df[["open", "high", "low", "close"]])
        for t, r in dd.tail(3).iterrows():
            hit = [px for px in lvl_px if r.low - 0.1 * at <= px <= r.high + 0.1 * at]
            if not hit:
                continue
            seen = True
            figs = [k for k in sens if r[k]]
            print(f"  {lab:3s} {t:%d/%m %H:%M} sur {', '.join(f'{x:.2f}' for x in hit)} : {describe(r, tick)}" + (f"  [{', '.join(figs)}]" if figs else ""))
    if not seen:
        print("  aucune des dernières bougies n'est sur un niveau : pas de lecture")

    # RANGE : bornes, nombre de touches, balayage de liquidité (M15 et H1, 36 bougies)
    ranges = []
    print("\nRANGE (36 dernières bougies)")
    for lab, df, at in (("M15", m15, a15), ("H1", h1, ah1)):
        w = df.iloc[-37:-1]
        hi_r, lo_r = w.high.max(), w.low.min()
        hgt = hi_r - lo_r
        eff = abs(w.close.iloc[-1] - w.close.iloc[0]) / hgt if hgt else 1
        if not (3 * at <= hgt <= 8 * at and eff < 0.35):
            print(f"  {lab} : pas de range net (hauteur {tk(hgt)} ticks = {hgt / at:.1f} ATR, déplacement net {eff*100:.0f} % de la hauteur)")
            continue

        def touches(mask):
            idx = np.where(mask)[0]
            return (1 + sum(1 for i in range(1, len(idx)) if idx[i] - idx[i - 1] > 3)) if len(idx) else 0
        nt_h = touches(w.high.values >= hi_r - 0.1 * hgt)
        nt_l = touches(w.low.values <= lo_r + 0.1 * hgt)
        if nt_h < 2 or nt_l < 2:
            print(f"  {lab} : bornes {lo_r:.2f} - {hi_r:.2f} pas encore confirmées ({nt_h} touche(s) en haut, {nt_l} en bas ; il en faut 2 de chaque côté)")
            continue
        cur_b = df.iloc[-1]
        sw = ("balayage du HAUT (mèche au-dessus, clôture dedans)" if cur_b.high > hi_r and cur_b.close < hi_r else
              "balayage du BAS (mèche en dessous, clôture dedans)" if cur_b.low < lo_r and cur_b.close > lo_r else "")
        print(f"  {lab} : borne haute {hi_r:.2f} ({nt_h} touches, {dt_(hi_r)})  borne basse {lo_r:.2f} ({nt_l} touches, {dt_(lo_r)})  hauteur {tk(hgt)} ticks"
              + (f"\n        dernière bougie : {sw}" if sw else ""))
        ranges.append((lab, hi_r, lo_r, nt_h, nt_l, at))

    # 5. SETUPS DE BASE (cassure + retest d'un niveau, range d'ouverture), puis les 4 étapes en confirmation
    cand = []
    sbuf = max(1.5 * a15, MIN_STOP_TICKS.get(sym, 10) * tick)
    hh, mm = OR_START.get(sym, (9, 30))
    _, m5 = bars(sym, "5m", 2)
    t5 = m5.index.tz_convert(NY)
    end = time(hh, mm + 15) if mm + 15 < 60 else time(hh + 1, mm - 45)
    cd5 = (t5 + pd.Timedelta(hours=6)).date  # journée CME (la séance commence à 18h NY = 3h La Réunion)
    orb = m5[(cd5 == cd5[-1]) & (t5.time >= time(hh, mm)) & (t5.time < end)]
    or_txt = f"{(pd.Timestamp('2000-01-01 ' + f'{hh}:{mm:02d}').tz_localize(NY).tz_convert(m15.index.tz)):%Hh%M}"

    def confirm(side):
        d = 1 if side == "long" else -1
        lines = []
        if day_bias == d:
            lines.append("✅ 0. dans le sens du biais du jour (technique + fondamental)")
        elif day_bias == 0:
            lines.append(f"❌ 0. {btxt.lower()}")
        else:
            lines.append("❌ 0. contre le biais du jour")
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

    d_ = lambda sd: 1 if sd == "long" else -1

    def add(kind, side, entry, stop, targets, cond):
        risk = abs(entry - stop)
        # le prix va où il a décidé d'aller, avec ou sans liquidité : sans niveau à 1,5R ou plus,
        # l'objectif devient 2R (les niveaux proches restent signalés comme obstacles)
        dd = 1 if side == "long" else -1
        if not any(abs(tg - entry) / risk >= 1.5 for _, tg in targets):
            targets = list(targets) + [("2R, sans liquidité visible", entry + dd * 2 * risk)]
        for j, (tname, tg) in enumerate(targets):
            rr = abs(tg - entry) / risk
            if rr < 1.5:
                continue
            if j:
                cond += " ; obstacles avant l'objectif : " + ", ".join(f"{x[1]:.2f}" for x in targets[:j]) + " (sortie partielle possible)"
            t_ok, ph_ok, lines = confirm(side)
            lines.append(f"{'ℹ️' if 'sans liquidité' in tname else '✅'} 4. objectif : {tg:.2f} ({tname}), {rr:.1f} R")
            if day_bias != d_(side):
                cand.append((3, kind, side, round(entry / tick) * tick, round(stop / tick) * tick,
                             round(tg / tick) * tick, tname, rr, cond, lines, "À ÉVITER (biais du jour)"))
                return
            if kind.startswith(("Order block", "Retest du point")):
                if "CONFIRMÉE" in cond:
                    lines.append("🟢 confirmation M5 obtenue")
                lines.append("ℹ️ testé (zones M15, entrée M5, 60 j, avec le biais) : or OB + FVG CHoCH M5 +0,91 R (10 trades), rejet M5"
                             " +0,58 R, retest + rejet M5 +0,25 R ; BTC retest + rejet M5 +0,39 R (61 trades) ; contre le biais perdant")
                v = "CONFIRMÉ (votre méthode)" + ("" if t_ok == "ok" else " ; HMA H1/H4 pas alignée")
                cand.append((-2 if kind.startswith("Order") else -1, kind, side, round(entry / tick) * tick, round(stop / tick) * tick,
                             round(tg / tick) * tick, tname, rr, cond, lines, v))
                return
            if kind.startswith("Range d'ouverture M15"):
                lines.append("ℹ️ méthode testée (or, 60 jours) : avec le biais +0,36 à +0,89 R par trade, contre -0,58 R")
                v = "CONFIRMÉ (méthode)" + ("" if t_ok == "ok" else " ; HMA H1/H4 pas alignée")
                cand.append((-1, kind, side, round(entry / tick) * tick, round(stop / tick) * tick,
                             round(tg / tick) * tick, tname, rr, cond, lines, v))
                return
            if "borne à borne" in kind and t_ok == "mixte":
                lines[0] = "ℹ️ 1. tendance mixte : normal dans un range"
                lines.append("⚠️ range borne à borne : pas d'avantage mesuré au test (or et BTC, H1 et M15)")
                cand.append((1, kind, side, round(entry / tick) * tick, round(stop / tick) * tick,
                             round(tg / tick) * tick, tname, rr, cond, lines, "POSSIBLE (non prouvé au test)"))
                return
            verdict = {"contre": "À ÉVITER", "mixte": "ATTENDRE que H1 et H4 s'accordent"}.get(t_ok) or \
                "CONFIRMÉ (tendance)"
            rank = 0 if verdict.startswith("CONFIRMÉ") else 2 if t_ok == "mixte" else 3
            cand.append((rank, kind, side, round(entry / tick) * tick, round(stop / tick) * tick,
                         round(tg / tick) * tick, tname, rr, cond, lines, verdict))
            return

    check = (f"checklist sur la bougie H1 de cassure : clôture franche, corps > {tk(ah1)} ticks (1 ATR H1), volume >= 2x la moyenne, "
             "RSI > 65 pour un achat ou < 35 pour une vente, heure 17h-19h30 ou 13h")
    if len(orb) >= 3:
        oh, ol = orb.high.max(), orb.low.min()
        print(f"\n  Range d'ouverture {or_txt} (15 min) : {ol:.2f} - {oh:.2f} ({tk(oh - ol)} ticks ; haut {dt_(oh)}, bas {dt_(ol)})")
        r15 = max(a15, MIN_STOP_TICKS.get(sym, 10) * tick)
        or_end = orb.index[-1] + pd.Timedelta(minutes=5)
        aft = m15[(m15.index >= or_end.floor("15min")) & (m15.index.date == orb.index[-1].date())]
        aft = aft.iloc[:-1] if len(aft) else aft  # la dernière bougie M15 peut être en cours
        done_sides = set()
        for nm, cond_, sd in (("au-dessus du haut", aft.close > oh, "long"), ("sous le bas", aft.close < ol, "short")):
            if cond_.any():
                done_sides.add(sd)
                t0 = aft.index[cond_.values.argmax()]
                print(f"  Déjà déclenché : première clôture M15 {nm} à {t0 + pd.Timedelta(minutes=15):%H:%M} ({aft.close[t0]:.2f}). "
                      "Si le trade n'a pas été pris, ne pas courir après : attendre le retour sur le niveau ou passer.")
        if "long" not in done_sides:
          add("Range d'ouverture M15", "long", oh, oh - r15, [("2R", oh + 2 * r15)] + [x for x in above if x[1] > oh + 1.5 * r15],
            f"PREMIÈRE bougie M15 qui clôture au-dessus de {oh:.2f} après {or_txt} + 15 min ; entrée à cette clôture, stop 1 ATR M15 ;"
            " objectif 2R ou tenir jusqu'à 1h (au plus tard 1h10)")
        if "short" not in done_sides:
          add("Range d'ouverture M15", "short", ol, ol + r15, [("2R", ol - 2 * r15)] + [x for x in below if x[1] < ol - 1.5 * r15],
            f"PREMIÈRE bougie M15 qui clôture sous {ol:.2f} après {or_txt} + 15 min ; entrée à cette clôture, stop 1 ATR M15 ;"
            " objectif 2R ou tenir jusqu'à 1h (au plus tard 1h10)")
    else:
        print(f"\n  Range d'ouverture : se forme à {or_txt} (15 min), relancer l'analyse ensuite (setup principal de la méthode)")
    for lvl in above[:2]:
        add("Cassure + retest", "long", lvl[1], lvl[1] - sbuf, [x for x in above if x[1] > lvl[1]],
            f"clôture H1 au-dessus de {lvl[1]:.2f} ({lvl[0]}), puis retour sur le niveau ; {check}")
    for lvl in below[:2]:
        add("Cassure + retest", "short", lvl[1], lvl[1] + sbuf, [x for x in below if x[1] < lvl[1]],
            f"clôture H1 sous {lvl[1]:.2f} ({lvl[0]}), puis retour sur le niveau ; {check}")
    # MÉTHODE DE L'UTILISATEUR : zones M15 (order block + FVG, sinon retest du point cassé), entrée sur M5
    # or : OB + FVG -> CHoCH M5 ou rejet M5 ; retest -> rejet M5.  BTC / Ether : retest -> rejet M5 (OB + FVG perdant au test)
    from ob import live_setups
    grp = "crypto" if sym in ("MBT", "MET") else "or"
    mn = {"MGC": 100, "MBT": 130, "MET": 130}.get(sym, 0) * tick  # stop minimum testé
    for sd_ in ([day_bias] if day_bias else [-1, 1]):
        sdn = "short" if sd_ < 0 else "long"
        for z in live_setups(m15, m5, sd_, grp, buf=0.1 * a15):
            if z["status"].startswith(("invalidée", "expirée")):
                print(f"  Zone {z['kind']} M15 ({z['entry']:.2f}) : {z['status']}")
                continue
            stp = z["stop"]
            if abs(stp - z["entry"]) < mn:
                stp = z["entry"] - sd_ * mn
            rk_ = abs(z["entry"] - stp)
            if z["status"] == "CONFIRMÉE" and m5.index[-1] - z["t_trig"] > pd.Timedelta(minutes=10):
                tg_ = z["entry"] + sd_ * 2 * rk_
                after = m5[m5.index > z["t_trig"]]
                hs = after.index[(after.high >= stp) if sd_ < 0 else (after.low <= stp)]
                ht = after.index[(after.low <= tg_) if sd_ < 0 else (after.high >= tg_)]
                res = ("objectif 2R atteint" if len(ht) and (not len(hs) or ht[0] < hs[0]) else
                       "stop touché" if len(hs) else "toujours en cours")
                print(f"  Déjà joué : {z['kind']} M15 confirmé par {z['trig']} à {z['t_trig'] + pd.Timedelta(minutes=5):%H:%M}, "
                      f"entrée {z['entry']:.2f}, stop {stp:.2f}, objectif {tg_:.2f} : {res}. Ne pas courir après.")
                continue
            fv = f", FVG {z['fvg'][0]:.2f}-{z['fvg'][1]:.2f}" if z["fvg"] else ""
            conf = " ou ".join(z["confirm"])
            if z["status"] == "CONFIRMÉE":
                etat = (f"CONFIRMÉE par {z['trig']} à {z['t_trig'] + pd.Timedelta(minutes=5):%H:%M} : entrée à la clôture {z['entry']:.2f}"
                        " (si le signal date de plus d'une bougie M5, c'est un autre trade : ne pas courir après)")
            elif z["status"] == "dans la zone":
                lv = z["choch"]
                etat = (f"prix DANS la zone depuis {z['t_touch']:%H:%M} : attendre la confirmation M5 ({conf})"
                        + (f" ; CHoCH = clôture M5 {'sous' if sd_ < 0 else 'au-dessus de'} {lv:.2f}" if "CHoCH M5" in z["confirm"] else ""))
            else:
                etat = f"attendre le retour du prix dans la zone, puis la confirmation M5 ({conf})"
            add(f"{z['kind']} M15 → entrée M5", sdn, z["entry"], stp, [("2R", z["entry"] + sd_ * 2 * rk_)],
                f"zone M15 (bougie {z['t']:%d/%m %H:%M}, cassure à {z['bos']:%H:%M}{fv}) ; {etat} ; stop au-delà de la zone"
                f" (minimum {mn / tick:.0f} ticks), objectif 2R")

    # range borne à borne : vente sur la borne haute, achat sur la borne basse, après une bougie de rejet sur la borne
    for lab, hi_r, lo_r, nt_h, nt_l, at in ranges[:1]:
        buf = max(0.25 * at, MIN_STOP_TICKS.get(sym, 10) * tick)
        mid = (hi_r + lo_r) / 2
        for side, b, n in (("short", hi_r, nt_h + 1), ("long", lo_r, nt_l + 1)):
            st_ = b + buf + 0.1 * (hi_r - lo_r) if side == "short" else b - buf - 0.1 * (hi_r - lo_r)
            tgts = [("milieu du range", mid), ("borne opposée", lo_r if side == "short" else hi_r)]
            note = (f" ; touche n° {n} : si la mèche dépasse la borne puis clôture dedans, c'est un balayage de liquidité"
                    if n >= 3 else "")
            add(f"Range {lab} borne à borne", side, b, st_, tgts,
                f"bougie {lab} de rejet SUR la borne {b:.2f} (mèche {'haute' if side == 'short' else 'basse'}, clôture dans le range){note}")
    cand.sort(key=lambda c: (c[0], 0 if c[1].startswith(("Order", "Retest du point")) else 1 if c[1].startswith("Cassure") else 2, -c[7]))
    print("\n5. SETUPS : biais du jour d'abord, puis les 4 étapes en confirmation (entrée seulement après la condition)")
    shown = 0
    for (rank, kind, side, e, s, t, tname, rr, cond, lines, verdict) in cand:
        if rank >= 3:
            continue
        shown += 1
        br, size, pv = run_plan(sym, side, e, s, t, a)
        print(f"{shown}. {kind} {'ACHAT' if side == 'long' else 'VENTE'} : {verdict}")
        print(f"   entrée {e:.2f} ({dt_(e)} du prix)  stop {s:.2f}  objectif {t:.2f}  ({br.replace('Bracket  ', 'bracket ')})")
        print(f"   Condition : {cond}")
        for ln in lines:
            print(f"   {ln}")
        print(f"   {size} | {pv}")
        if verdict.startswith("CONFIRMÉ") and shown <= 2:
            tm = subprocess.run(["/opt/openbb/bin/python", str(HERE / "timemachine.py"), sym, "--side", side, "--entry", f"{e}",
                                 "--stop", f"{s}", "--target", f"{t}", "--replays", "3000"], capture_output=True, text=True).stdout
            odds = [x.strip() for x in tm.splitlines() if x.strip().startswith(("objectif d'abord", "Verdict"))]
            if odds:
                print("   Machine à remonter le temps : " + " | ".join(odds))
    if not shown:
        print("  aucun setup confirmé : attendre")
    bad = [c for c in cand if c[0] >= 3]
    if bad:
        print("  À éviter (contre le biais du jour ou la tendance HMA) : " + ", ".join(f"{c[1]} {'achat' if c[2] == 'long' else 'vente'} {c[3]:.2f}" for c in bad))
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
