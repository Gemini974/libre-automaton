#!/usr/bin/env python3
"""topstep-trader: sessions, plan (long or short), sizing and risk gate for
micro futures on a Topstep account. Standard library only, no network.

  python3 plan.py sessions [--date 2026-11-18]
  python3 plan.py plan --symbol MBT --side short --or-high 64300 --or-low 64000 --entry 63950
  python3 plan.py plan --symbol MGC --side short --entry 3795 --stop 3808 --target 3725
"""
import argparse
import math
import sys
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("Indian/Reunion")
NY = ZoneInfo("America/New_York")
CHI = ZoneInfo("America/Chicago")
LON = ZoneInfo("Europe/London")
TOK = ZoneInfo("Asia/Tokyo")

# symbol: (tick size, $ per tick)
SPECS = {
    "MNQ": (0.25, 0.50), "MES": (0.25, 1.25), "MYM": (1.0, 0.50), "M2K": (0.10, 0.50),
    "MGC": (0.10, 1.00), "SIL": (0.005, 5.00), "MCL": (0.01, 1.00), "M6E": (0.0001, 1.25),
    "MBT": (5.0, 0.50), "MET": (0.50, 0.05),
    "NQ": (0.25, 5.00), "ES": (0.25, 12.50), "GC": (0.10, 10.00), "CL": (0.01, 10.00),
}

# name, zone, open, opening-range minutes
SESSIONS = [
    ("Asie (Tokyo)", TOK, time(9, 0), 15),
    ("Londres", LON, time(8, 0), 15),
    ("Or COMEX", NY, time(8, 20), 15),
    ("Pétrole NYMEX", NY, time(9, 0), 15),
    ("New York (actions)", NY, time(9, 30), 15),
]


def local(d, zone, t):
    return datetime.combine(d, t, zone).astimezone(LOCAL)


def cmd_sessions(a):
    d = date.fromisoformat(a.date) if a.date else datetime.now(LOCAL).date()
    print(f"Sessions du {d} en heure de La Réunion (UTC+4)")
    globex = local(d - timedelta(days=1), CHI, time(17, 0))
    flat = local(d, CHI, time(15, 10))
    print(f"  Réouverture CME Globex : {globex:%a %H:%M}")
    for name, zone, t, m in SESSIONS:
        o = local(d, zone, t)
        print(f"  {name:20s} ouverture {o:%H:%M}  range d'ouverture {o:%H:%M}-{o + timedelta(minutes=m):%H:%M}")
    print(f"  Topstep : à plat avant {flat:%H:%M} (15:10 Chicago), pause CME {local(d, CHI, time(16, 0)):%H:%M}-{local(d, CHI, time(17, 0)):%H:%M}")


def rnd(x, tick, up):
    n = x / tick
    return (math.ceil(n - 1e-9) if up else math.floor(n + 1e-9)) * tick


def cmd_plan(a):
    sym = a.symbol.upper()
    if sym not in SPECS:
        sys.exit(f"Symbole inconnu {sym}. Connus : {', '.join(SPECS)}")
    tick, tv = SPECS[sym]
    short = a.side == "short"
    sgn = -1 if short else 1
    entry = a.entry
    if entry is None:
        if a.or_high is None or a.or_low is None:
            sys.exit("Donne --entry, ou le range d'ouverture (--or-high et --or-low).")
        entry = a.or_low if short else a.or_high
    if a.stop is not None:
        stop, rule = a.stop, "ton prix"
    elif a.or_high is not None and a.or_low is not None:
        stop, rule = (a.or_high + a.or_low) / 2, "milieu du range d'ouverture"
    else:
        sys.exit("Donne --stop, ou le range d'ouverture pour un stop au milieu.")
    stop = rnd(stop, tick, up=short)  # stop pushed away from the entry
    risk_pts = (stop - entry) * -sgn
    blocks, warns = [], []
    if risk_pts <= 0:
        sys.exit(f"REFUSÉ : le stop {stop} est du mauvais côté de l'entrée {entry} pour un {a.side}.")
    ticks = round(risk_pts / tick)
    if ticks < a.min_ticks:
        blocks.append(f"stop trop serré ({ticks} ticks < {a.min_ticks}) : le bruit normal le touchera")
    if a.target is not None:
        target = a.target
    else:
        target = entry + sgn * a.r * risk_pts
    target = rnd(target, tick, up=not short)
    reward_pts = (target - entry) * sgn
    if reward_pts <= 0:
        sys.exit("REFUSÉ : l'objectif est du mauvais côté de l'entrée.")
    rr = reward_pts / risk_pts
    risk_1 = ticks * tv
    qty = min(a.max_contracts, int(a.max_risk // risk_1))
    if qty < 1:
        blocks.append(f"1 contrat risque {risk_1:.2f} $ > risque max {a.max_risk:.2f} $")
        qty = 0
    risk_total = qty * risk_1
    reward_total = qty * round(reward_pts / tick) * tv
    remaining = a.daily_limit + a.day_pnl
    if rr < a.min_rr:
        blocks.append(f"rendement/risque {rr:.2f} < minimum {a.min_rr}")
    if risk_total > remaining:
        blocks.append(f"risque {risk_total:.2f} $ > marge du jour {remaining:.2f} $")
    if a.max_trades and a.trades_today >= a.max_trades:
        blocks.append(f"déjà {a.trades_today} trades aujourd'hui (max {a.max_trades})")
    if a.day_pnl + reward_total > a.consistency_cap:
        warns.append(f"si l'objectif est touché, la journée dépasse {a.consistency_cap:.0f} $ (règle de régularité) : sors une partie plus tôt")
    now = datetime.now(LOCAL) if not a.now else datetime.fromisoformat(a.now).replace(tzinfo=LOCAL)
    flat = local(now.date(), CHI, time(15, 10))
    if a.news:
        nh, nm = map(int, a.news.split(":"))
        nt = now.replace(hour=nh, minute=nm, second=0, microsecond=0)
        if nt - timedelta(minutes=15) <= now <= nt + timedelta(minutes=15):
            blocks.append(f"fenêtre d'annonce {a.news} ±15 min : pas d'entrée")
        elif now < nt:
            warns.append(f"annonce à {a.news} : à plat ou stop au point d'entrée à {(nt - timedelta(minutes=15)):%H:%M}")
    if flat - timedelta(minutes=20) <= now <= flat:
        blocks.append(f"trop près de la clôture forcée Topstep ({flat:%H:%M})")

    side_fr = "VENTE" if short else "ACHAT"
    print(f"{sym} {side_fr}  tick {tick} = {tv:.2f} $")
    print(f"  Entrée   {entry}")
    print(f"  Stop     {stop}  ({rule}) : {ticks} ticks, {risk_1:.2f} $/contrat")
    print(f"  Objectif {target}  ({round(reward_pts / tick)} ticks) : rendement/risque {rr:.2f}")
    print(f"  Taille   {qty} contrat(s) : risque {risk_total:.2f} $, gain visé {reward_total:.2f} $")
    print(f"  Bracket  stop {ticks} ticks, objectif {round(reward_pts / tick)} ticks")
    print(f"  Journée  {a.day_pnl:+.2f} $, marge restante {remaining:.2f} $, à plat avant {flat:%H:%M}")
    for w in warns:
        print(f"  ! {w}")
    if blocks:
        print("BLOCK : " + " ; ".join(blocks))
        return 1
    print("PASS : les règles sont respectées. Ce n'est pas une recommandation.")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sessions")
    s.add_argument("--date")
    q = sub.add_parser("plan")
    q.add_argument("--symbol", required=True)
    q.add_argument("--side", choices=["long", "short"], required=True)
    q.add_argument("--entry", type=float)
    q.add_argument("--stop", type=float)
    q.add_argument("--target", type=float)
    q.add_argument("--or-high", type=float)
    q.add_argument("--or-low", type=float)
    q.add_argument("--r", type=float, default=2.0, help="objectif en multiple du risque (2R)")
    q.add_argument("--max-risk", type=float, default=80.0)
    q.add_argument("--max-contracts", type=int, default=5)
    q.add_argument("--min-ticks", type=int, default=10)
    q.add_argument("--min-rr", type=float, default=1.5)
    q.add_argument("--day-pnl", type=float, default=0.0)
    q.add_argument("--daily-limit", type=float, default=1000.0, help="limite journalière Topstep (DLL)")
    q.add_argument("--trades-today", type=int, default=0)
    q.add_argument("--max-trades", type=int, default=0, help="0 = pas de limite (Topstep n'en impose pas)")
    q.add_argument("--consistency-cap", type=float, default=1400.0)
    q.add_argument("--news", help="heure d'une annonce, HH:MM heure de La Réunion")
    q.add_argument("--now", help="AAAA-MM-JJTHH:MM heure de La Réunion (tests)")
    a = p.parse_args()
    if a.cmd == "sessions":
        cmd_sessions(a)
        return 0
    return cmd_plan(a)


if __name__ == "__main__":
    sys.exit(main())
