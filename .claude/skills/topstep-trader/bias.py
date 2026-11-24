#!/usr/bin/env python3
"""Biais du jour d'un contrat : technique (EMA 20 / EMA 50 Daily) et fondamental (vote à la majorité).
Technique et fondamental en désaccord = pas de trade (règle de l'utilisateur).

  /opt/openbb/bin/python bias.py MGC
"""
import sys
import warnings

warnings.filterwarnings("ignore")

from market import bars  # noqa: E402

# indicateur Yahoo, signe (+1 : sa hausse est haussière pour le contrat), libellé
FUND = {
    "or": [("DX-Y.NYB", -1, "Dollar (DXY)"), ("^TNX", -1, "Taux US 10 ans"), ("^VIX", 1, "VIX")],
    "crypto": [("NQ=F", 1, "Nasdaq"), ("DX-Y.NYB", -1, "Dollar (DXY)"), ("^VIX", -1, "VIX")],
    "indices": [("^VIX", -1, "VIX"), ("^TNX", -1, "Taux US 10 ans"), ("DX-Y.NYB", -1, "Dollar (DXY)")],
    "petrole": [("DX-Y.NYB", -1, "Dollar (DXY)"), ("ES=F", 1, "S&P 500 (demande)"), ("^VIX", -1, "VIX")],
    "devises": [("DX-Y.NYB", -1, "Dollar (DXY)"), ("^TNX", -1, "Taux US 10 ans"), ("^VIX", -1, "VIX")],
}
GROUP = {"MGC": "or", "GC": "or", "SIL": "or", "MBT": "crypto", "MET": "crypto", "BTC": "crypto",
         "MES": "indices", "MNQ": "indices", "MYM": "indices", "M2K": "indices",
         "MCL": "petrole", "CL": "petrole", "M6E": "devises", "M6B": "devises", "M6A": "devises"}


_CACHE = {}


def _fund_bars(ysym):
    if ysym not in _CACHE:
        _CACHE[ysym] = bars(ysym, "1d", 120)[1]
    return _CACHE[ysym]


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def daily_bias(sym, d1=None, verbose=False):
    """Renvoie (biais : +1, -1 ou 0, technique, fondamental, lignes de texte)."""
    if d1 is None:
        _, d1 = bars(sym, "1d", 200)
    dc = d1.close.iloc[:-1]
    e20, e50 = ema(dc, 20).iloc[-1], ema(dc, 50).iloc[-1]
    tech = 1 if e20 > e50 else -1
    lines = [f"Technique : EMA 20 Daily {e20:.4g} {'>' if tech > 0 else '<'} EMA 50 Daily {e50:.4g} => {'HAUSSIER' if tech > 0 else 'BAISSIER'}"]
    votes = []
    for ysym, sign, lab in FUND[GROUP.get(sym, "indices")]:
        try:
            fd = _fund_bars(ysym)
            fc = fd.close.iloc[:-1]
            if ysym == "^VIX":
                up = fc.iloc[-1] > fc.rolling(50).mean().iloc[-1]
                txt = f"{fc.iloc[-1]:.1f} {'au-dessus' if up else 'sous'} sa moyenne 50 j"
            else:
                up = ema(fc, 20).iloc[-1] > ema(fc, 50).iloc[-1]
                txt = f"{'en hausse' if up else 'en baisse'} (EMA 20 {'>' if up else '<'} EMA 50)"
            v = sign * (1 if up else -1)
            votes.append(v)
            lines.append(f"Fondamental : {lab:18s} {txt} => {'haussier' if v > 0 else 'baissier'} pour {sym}")
        except Exception as ex:
            lines.append(f"Fondamental : {lab} indisponible ({ex.__class__.__name__})")
    s = sum(votes)
    fund = 1 if s > 0 else -1 if s < 0 else 0
    if fund == 0:
        b, txt = 0, "PAS DE TRADE : fondamental partagé"
    elif fund == tech:
        b, txt = tech, ("ACHATS SEULEMENT" if tech > 0 else "VENTES SEULEMENT") + " (technique et fondamental d'accord)"
    else:
        b, txt = 0, "PAS DE TRADE : technique et fondamental en désaccord"
    lines.append(f"=> {txt}")
    if verbose:
        print("\n".join("  " + x for x in lines))
    return b, tech, fund, lines, txt


if __name__ == "__main__":
    daily_bias(sys.argv[1].upper(), verbose=True)
