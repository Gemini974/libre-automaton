---
name: topstep-trader
description: >-
  Day trading de micro futures sur un compte Topstep (évaluation 50K avec
  limite journalière), à l'achat ET à la vente, sur toutes les sessions
  (Asie, Londres, COMEX, NYMEX, New York), en heure de La Réunion. Adapté du
  pack day-trader-skill (scanner, news, entry, exit, timemachine, budget,
  risk, alerts) : même méthode, étendue aux futures et aux ventes. Lit les
  captures de graphique de l'utilisateur, construit le range d'ouverture,
  attend une clôture de bougie hors du range, place le stop et l'objectif
  AVANT l'entrée, calcule la taille en ticks et passe le plan par une porte
  de risque (PASS ou BLOCK). Utiliser quand l'utilisateur dit "setup du
  jour", "analyse le BTC / l'or / le Nasdaq", "où est mon stop", "combien de
  contrats", "je peux prendre ce trade", "plan de la session", ou envoie une
  capture TradingView ou TopstepX.
argument-hint: "[symbole] [long|short] [session]"
---

# topstep-trader

Un trade, une méthode, dans cet ordre : session, actualités, range,
entrée, sortie, taille, risque, alertes. Rien n'est passé sur le compte :
c'est l'utilisateur qui clique. Le day trading fait perdre de l'argent à la
plupart des gens, et un plan propre n'y change rien.

`${CLAUDE_SKILL_DIR}` est le dossier de ce SKILL.md.

```bash
python3 "${CLAUDE_SKILL_DIR}/plan.py" sessions                       # horaires du jour, heure de La Réunion
python3 "${CLAUDE_SKILL_DIR}/plan.py" plan --symbol MBT --side short \
    --or-high 64300 --or-low 64000 --day-pnl -91 --news 23:00          # stop au milieu du range, objectif 2R
python3 "${CLAUDE_SKILL_DIR}/plan.py" plan --symbol MGC --side short \
    --entry 3795 --stop 3808 --target 3725                             # niveaux donnés par l'utilisateur
```

Données de marché avec OpenBB (fournisseur yfinance, gratuit, futures
retardés de 10 à 20 minutes ; TopstepX reste la référence pour les ordres) :

```bash
pip install openbb-core openbb-yfinance openbb-equity openbb-crypto   # une fois par machine
python3 "${CLAUDE_SKILL_DIR}/market.py" levels MBT                   # dernier, haut/bas du jour, de la veille, 5 jours, ATR 15m
python3 "${CLAUDE_SKILL_DIR}/market.py" orb MNQ --session ny         # range d'ouverture + déclenchement, commande plan.py prête
python3 "${CLAUDE_SKILL_DIR}/market.py" spread                       # écart MBT - BTC spot
```

Réseau requis : query1.finance.yahoo.com, query2.finance.yahoo.com,
fc.yahoo.com. Sessions : `asia`, `london`, `comex`, `nymex`, `ny`. Si
OpenBB ou le réseau manque, revenir aux captures de l'utilisateur.

Autres options de plan.py : `--r 1.5`, `--max-risk 80`, `--max-contracts 5`,
`--min-rr 1.5`, `--min-ticks 10`, `--daily-limit 250`, `--trades-today 1`,
`--max-trades 2`, `--consistency-cap 1400`, `--now 2026-11-18T18:50`.

## Contrats connus (tick, valeur du tick)

| MNQ 0,25 / 0,50 $ | MES 0,25 / 1,25 $ | MYM 1 / 0,50 $ | M2K 0,10 / 0,50 $ |
|---|---|---|---|
| **MGC 0,10 / 1 $** | SIL 0,005 / 5 $ | MCL 0,01 / 1 $ | M6E 0,0001 / 1,25 $ |
| **MBT 5 / 0,50 $** | MET 0,50 / 0,05 $ | NQ, ES, GC, CL (contrats standards) | |

BTC1! sur TradingView cote comme le MBT. Si l'utilisateur envoie BTC/USDT
(spot), mesurer l'écart avec le MBT au même instant et décaler les niveaux.

## Les sessions (`plan.py sessions` calcule les heures, heure d'été comprise)

| session | heure de La Réunion (hiver US) | range d'ouverture | actifs |
|---|---|---|---|
| Réouverture Globex | 03:00 | — | tout |
| Asie | 04:00 | 04:00-04:15 | MBT, MGC, M6E |
| Londres | 12:00 | 12:00-12:15 | MGC, M6E, MBT |
| Or COMEX | 17:20 | 17:20-17:35 | MGC, SIL |
| Pétrole NYMEX | 18:00 | 18:00-18:15 | MCL |
| New York | 18:30 | 18:30-18:45 | MNQ, MES, MBT |
| Topstep à plat | **avant 01:10** | — | tout |

## Étapes

1. **Session et actualités.** Lancer `plan.py sessions`. Chercher les
   annonces du jour (calendrier économique, Fed, résultats, géopolitique).
   Pas d'entrée de 15 minutes avant à 15 minutes après une annonce
   majeure (`--news HH:MM` bloque cette fenêtre). À plat ou stop au point
   d'entrée 15 minutes avant.
2. **Biais.** Unité haute (H4 ou H1) : tendance, triangle ou range, niveaux
   clés, RSI. Fondamentaux en une ligne. Le biais dit quel côté est
   prioritaire, il n'interdit pas l'autre.
3. **Range d'ouverture.** Plus haut et plus bas des 15 premières minutes de
   la session (`market.py orb`). Le milieu sert de stop. `market.py levels`
   donne les niveaux de la veille et l'ATR : un stop sous ~1 ATR 15m est
   trop serré.
4. **Entrée.** La première bougie de 5 minutes (ou 15 minutes) qui CLÔTURE
   au-dessus du haut (achat) ou sous le bas (vente). Une mèche ne compte
   pas. Variante sur un niveau : cassure d'une ligne ou d'un support, puis
   retour sur ce niveau et rejet ; entrée en ordre limite sur le niveau.
   Un signal de plus d'une bougie de retard est un autre trade.
   Confirmer sur l'unité au-dessus (H1) : si elle contredit, réduire la
   taille ou passer.
5. **Sortie, avant d'entrer.** Stop au milieu du range (ou au-dessus du
   dernier sommet pour une vente, sous le dernier creux pour un achat).
   Objectif 2R par défaut, ou le prochain niveau si plus proche. Refuser
   un stop trop serré pour le bruit (moins de 10 ticks, 30 sur le MBT).
6. **Probabilités.** Sans données en direct, dire franchement qu'une
   cassure d'ouverture est souvent proche du pile ou face, et que les
   fausses cassures sont fréquentes autour des annonces.
7. **Taille et risque.** `plan.py plan` : contrats = risque max ÷ risque
   d'un contrat, puis PASS ou BLOCK (rendement/risque, marge du jour, nombre
   de trades, fenêtre d'annonce, clôture forcée, règle de régularité). Un
   BLOCK ne se discute pas.
8. **Exécution par l'utilisateur.** Donner le bracket en ticks (c'est ce que
   TopstepX affiche), le type d'ordre (LMT pour un retour sur niveau, STP
   pour une cassure), la quantité, et ce qu'il faut vérifier après : les
   lignes de stop et d'objectif visibles, CANCEL ORDERS actif, la case
   "apply automatically" décochée après le trade.
9. **Gestion et alertes.** Stop au point d'entrée (B/E) au premier
   objectif ou à 1R. Alertes TradingView sur l'entrée, le stop et
   l'objectif. Annuler les ordres non exécutés avant l'annonce ou avant
   00:30. À plat avant 01:10.

## Règles du compte (à ajuster si l'utilisateur les change)

- Limite journalière Topstep 1 000 $ ; limite personnelle **−250 $ par
  jour** ; perte maximale 2 000 $ (suiveuse).
- **2 trades par jour**, risque **70 à 120 $** par trade.
- Règle de régularité : arrêter la journée au-delà d'environ +1 400 $.
- Un seul trade à la fois sur des actifs corrélés (BTC, or, euro et Nasdaq
  réagissent tous au dollar et à la Fed).
- Après une perte : pas de trade de revanche. Après deux erreurs de
  manipulation : arrêter la journée.

## Ce qu'il ne fait jamais

Il ne passe aucun ordre, ne promet aucun gain, n'élargit jamais un stop,
n'entre pas sur une bougie qui n'a pas clôturé et ne lit pas une capture
floue comme un prix exact : il le dit et demande la valeur.

Éducation et outils, pas un conseil en investissement. Un PASS vérifie des
règles, ce n'est pas une recommandation.
