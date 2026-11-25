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
# OpenBB est installé dans /opt/openbb par le script de l'environnement ; sinon :
# python3 -m venv /opt/openbb && /opt/openbb/bin/pip install openbb-core openbb-yfinance openbb-equity openbb-crypto matplotlib
# Lancer market.py avec /opt/openbb/bin/python (crypto.py, geo.py, av.py et plan.py tournent avec python3).
python3 "${CLAUDE_SKILL_DIR}/market.py" levels MBT                   # dernier, haut/bas du jour, de la veille, 5 jours, ATR 15m
python3 "${CLAUDE_SKILL_DIR}/market.py" orb MNQ --session ny         # range d'ouverture + déclenchement, commande plan.py prête
python3 "${CLAUDE_SKILL_DIR}/market.py" spread                       # écart MBT - BTC spot
python3 "${CLAUDE_SKILL_DIR}/scan.py"                                 # scanner : quels contrats trader aujourd'hui selon la méthode
python3 "${CLAUDE_SKILL_DIR}/bias.py" MGC                             # biais du jour : EMA 20/50 Daily + accord fondamental
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" MGC --side short --entry 3601 --stop 3615 --target 3566 --at 20:30   # chances du plan
python3 "${CLAUDE_SKILL_DIR}/structure.py" MGC --chart /tmp/mgc.png  # tendance, position, phase, liquidité, bougies, setups confirmés + PNG
python3 "${CLAUDE_SKILL_DIR}/candles.py" MGC                         # lecture des 6 dernières bougies M15 et H1, figures, Heikin-Ashi
python3 "${CLAUDE_SKILL_DIR}/ticks.py" volume MGC --chart /tmp/v.png   # bougies d'activité (même nombre de contrats), proches des bougies en ticks
python3 "${CLAUDE_SKILL_DIR}/ticks.py" fetch --hours 12 && python3 "${CLAUDE_SKILL_DIR}/ticks.py" bars --n 500   # ticks Dukascopy (or au comptant)
```

python3 "${CLAUDE_SKILL_DIR}/market.py" macro                       # taux 10 et 5 ans, dollar, VIX, yen, ZN
```

Contexte crypto et positionnement (API publiques gratuites, sans clé, bibliothèque
standard seulement) :

```bash
python3 "${CLAUDE_SKILL_DIR}/crypto.py" all          # tout ce qui suit, d'un coup
python3 "${CLAUDE_SKILL_DIR}/crypto.py" market       # capitalisation totale, volume, dominance du BTC (Coinpaprika)
python3 "${CLAUDE_SKILL_DIR}/crypto.py" onchain      # stablecoins (DefiLlama), difficulté, puissance, frais (Mempool)
python3 "${CLAUDE_SKILL_DIR}/crypto.py" derivs btc   # financement, positions ouvertes, amas de liquidations, murs d'ordres (Swiftedge)
                                                     # aussi : eth, gold, us500, us100, oil, silver
python3 "${CLAUDE_SKILL_DIR}/crypto.py" sentiment    # Fear & Greed, liquidations 24 h, comptes acheteurs/vendeurs (MarginPad)
python3 "${CLAUDE_SKILL_DIR}/crypto.py" flows        # achats et ventes des ETF et entreprises, 7 jours (CorpStacking)
```

Sentiment des actualités et macro américaine (Alpha Vantage, clé gratuite, 25
requêtes par jour, réponses gardées 6 h en cache) :

```bash
python3 "${CLAUDE_SKILL_DIR}/av.py" news btc     # sentiment des dernières actualités sur le BTC (aussi : eth, macro, energy, fx)
python3 "${CLAUDE_SKILL_DIR}/av.py" macro        # inflation, taux de la Fed, taux 2 et 10 ans, chômage (5 requêtes)
```

La clé se lit dans la variable ALPHAVANTAGE_API_KEY, que l'utilisateur ajoute
lui-même dans les réglages de l'environnement. Ne jamais la demander dans la
conversation. Sans clé, le script le dit et s'arrête.

Géopolitique, trafic maritime et probabilités d'événements (API publiques, sans clé) :

```bash
python3 "${CLAUDE_SKILL_DIR}/geo.py" all             # tout ce qui suit
python3 "${CLAUDE_SKILL_DIR}/geo.py" news            # GDELT : volume d'actualité Iran/Hormuz, droits de douane, Russie, Fed, Taïwan + titres
python3 "${CLAUDE_SKILL_DIR}/geo.py" news "Venezuela oil"   # n'importe quel sujet
python3 "${CLAUDE_SKILL_DIR}/geo.py" ships           # IMF PortWatch : transits par jour à Hormuz, Bab el-Mandeb, Suez, Panama, Malacca…
python3 "${CLAUDE_SKILL_DIR}/geo.py" odds            # Polymarket : probabilités Fed, guerres, Bitcoin, droits de douane
python3 "${CLAUDE_SKILL_DIR}/geo.py" decrees         # Federal Register : décisions présidentielles, textes sur les droits de douane
python3 "${CLAUDE_SKILL_DIR}/geo.py" quakes          # USGS : séismes M6+ de la semaine
```

GDELT limite à une requête toutes les 5 secondes et peut refuser (HTTP 429)
pendant un moment : réessayer plus tard. PortWatch a quelques jours de retard.
Lire un volume d'actualité en forte hausse ou un détroit en chute comme un
risque d'écart de prix sur les actifs touchés (pétrole, or, dollar, indices).

Comment s'en servir : les amas de liquidations et les murs d'ordres servent
d'aimants et de résistances pour placer entrées et objectifs ; un financement
négatif avec beaucoup de vendeurs au-dessus du prix annonce un risque de
rachat brutal ; des stablecoins en baisse et des ventes d'ETF confirment un
biais vendeur de fond. Citer la source de chaque chiffre : ce sont des données
de tiers, parfois sur d'autres plateformes que le CME.

Réseau requis : query1.finance.yahoo.com, query2.finance.yahoo.com,
fc.yahoo.com ; pour crypto.py : api.coinpaprika.com, stablecoins.llama.fi, mempool.space,
swiftedge.uk, marginpad.io, www.corpstacking.com ; pour geo.py :
api.gdeltproject.org, services9.arcgis.com, gamma-api.polymarket.com,
www.federalregister.gov, earthquake.usgs.gov ; pour av.py : www.alphavantage.co. Sessions : `asia`, `london`, `comex`, `nymex`, `ny`. Si
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
2. **Biais.** Lancer `structure.py` (voir « Structure et biais daily »).
   Unité haute (Daily, H4, H1) : tendance, triangle ou range, niveaux
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

## Checklist : vraie ou fausse cassure

Étude sur l'or (GC, bougies H1, 2 ans, 993 cassures des plus hauts et plus
bas de la veille, de l'Asie et de Londres). Vraie = le prix va à 2 ATR H1
au-delà du niveau ; fausse = une bougie reclôture de l'autre côté. Sans
filtre : 54 % de vraies. Résultats sur le passé, non validés hors
échantillon ; sur M15, juger la bougie H1 complète.

1. **Clôture franche** au-delà du niveau. Une clôture à moins de 0,25 ATR
   du niveau n'est vraie que 27 % du temps (au-delà de 1 ATR : 87 %).
2. **Corps plus grand que l'ATR H1**, clôture dans le quart extrême de la
   bougie. Corps sous 0,6 ATR ou clôture en mèche : 37 % de vraies.
3. **Volume au moins 2 fois la moyenne 20** (62 % de vraies ; sous 0,8 fois :
   36 %).
4. **RSI au-dessus de 65** dans le sens de la cassure (sous 35 pour une
   vente). RSI sous 55 dans le sens : 34 %.
5. **Heure (La Réunion)** : 17h à 19h30 (56 à 62 %) ou 13h (65 %). Éviter
   14h (35 %), 16h (44 %) et 20h à 21h (32 à 38 %).
6. **Stop à 1,5 à 2 ATR**, objectif connu, plan passé par `plan.py`.
7. **Sortie au temps** : 60 % des fausses cassures échouent dans les 2
   heures, et la moitié des vraies atteignent leur objectif dès la première.
   Sans progrès après 2 bougies H1, sortir ou resserrer.

Combinaisons : corps > 1 ATR + volume > 2 fois : 70 % ; avec RSI > 65 :
76 % ; avec la clôture dans le quart extrême : 78 %. Sans les points 2, 3
et 4, la cassure est fausse environ 6 fois sur 10 : attendre plutôt le
retour sous le niveau pour jouer l'autre sens.

Ne discriminent presque pas : la tendance H4 (55 % avec, 52 % contre), le
nombre de touches du niveau, la compression avant la cassure, le jour de
la semaine.

## Chaîne complète : day-trader-skill + notre méthode

Dans l'ordre, pour chaque séance (scanner → actualités → entrée → sortie →
machine à remonter le temps → taille et risque → alertes) :

| Étape day-trader-skill | Ici | Ce qui change pour la méthode |
|---|---|---|
| trader-scanner | `scan.py` | contrats Topstep classés par biais du jour (technique + fondamental), HMA H1/H4 d'accord, risque d'un stop de 1 ATR M15 sous le risque max, volume relatif ; écarte les autres avec la raison |
| trader-news | `av.py`, `geo.py`, `crypto.py`, `market.py macro`, recherche web | fondamental et calendrier : pas d'entrée 15 min avant ou après une annonce majeure |
| trader-entry | `structure.py` (setup n° 1) | range d'ouverture 15 min, première clôture M15 au-delà dans le sens du biais ; signale un signal déjà passé |
| trader-exit | `structure.py` + `plan.py` | stop 1 ATR M15 (130 ticks min. sur MBT), objectif 2R ou liquidité, sortie à 1h |
| trader-timemachine | `timemachine.py` (lancé par `structure.py` sur les 2 meilleurs setups) | 10 000 fins de séance tirées des bougies 5 min des 60 derniers jours + historique réel du même plan, sortie à 1h |
| trader-budget + trader-risk | `plan.py` | taille en ticks, DLL 1 000 $, plafond de gain 1 400 $, clôture 1h10, annonces |
| trader-alerts | alertes TradingView sur entrée, stop, objectif ; analyses programmées | rappel 23h30 : plus d'entrée ; 1h00 : à plat |

## Entrée de l'utilisateur : zones M15, entrée M5 (`ob.py`, setup n° 1 de `structure.py`)

Règles retenues après backtest (zones M15, entrée M5, 60 jours, sens du biais, stop
minimum or 100 ticks / BTC 130, objectif 2R) :
- **Or** : order block + FVG M15, entrée sur **CHoCH M5** (+0,91 R, 10 trades) ou
  **rejet M5** (+0,58 R) ; sans FVG, retest du point cassé + **rejet M5** (+0,25 R).
- **BTC / Ether** : **retest du point cassé + rejet M5** (+0,39 R, 54 % gagnants, 61
  trades) ; l'order block + FVG a perdu sur le BTC (-0,14 R).
- Rejet M5 = mèche dans la zone (40 % de la bougie ou plus) et clôture du bon côté ;
  CHoCH M5 = clôture M5 au-delà du creux (ou sommet) des 3 bougies précédant l'entrée
  dans la zone, stop au-delà de l'extrême atteint. Confirmation dans l'heure qui suit
  l'entrée dans la zone, sinon zone expirée ; clôture au-delà de la zone = invalidée.
- `structure.py` donne l'état en direct : attente du retour, prix dans la zone
  (niveau du CHoCH), CONFIRMÉE (entrée à la clôture), déjà joué (avec le résultat).

### Règles de base

1. **Order block + FVG dans le sens du biais.** Après une cassure de structure en M15
   (clôture au-delà du dernier creux ou sommet), l'order block est la dernière bougie
   de couleur opposée avant la jambe qui a cassé ; la jambe doit contenir un FVG.
   **On entre quand le prix revient dans l'order block** (ordre limite sur le bord du
   corps), stop juste au-delà de l'OB, objectif 2R. Un OB déjà touché a été joué.
2. **S'il n'y a pas de FVG : entrée sur le retest du dernier point bas (ou haut)
   récemment cassé**, stop au-delà du dernier sommet (ou creux) avant la cassure.
Seulement la cassure la plus récente, seulement dans le sens du biais du jour.
Stop minimum : or 100 ticks, BTC 130 ticks (sans lui, les stops d'OB sont trop serrés).
Backtest (M15, 60 jours, sens du biais, stop minimum, 2R, sortie 1h) : or OB + FVG +0,58 R
par trade, 57 % gagnants, 28 trades (t = 2,1), contre le biais -0,34 R ; or retest +0,03 R ;
BTC les deux règles +0,16 R (190 trades, t = 2,0). Perdant : M5 (or -0,30 R, BTC -0,34 R),
retest contre le biais (-0,28 R), BTC en H1 (-0,12 R). Échantillons courts : à confirmer.

## Méthode du jour : biais Daily + entrée M15 / M5 (`structure.py`, section 0 et setup n° 1)

1. **Biais technique** : EMA 20 Daily au-dessus de l'EMA 50 Daily = achats
   seulement ; en dessous = ventes seulement (jours terminés).
2. **Accord avec le fondamental (règle de l'utilisateur)** : or = dollar
   DXY, taux US 10 ans (en baisse = haussier or), VIX au-dessus de sa
   moyenne 50 jours (haussier or) ; BTC = Nasdaq (en hausse = haussier),
   dollar (en baisse = haussier), VIX sous sa moyenne (haussier). Vote à la
   majorité. Technique et fondamental en désaccord = pas de trade. Plus le
   calendrier du jour : pas d'entrée 15 min avant ou après une annonce
   majeure (`av.py`, `geo.py`, `crypto.py`, `market.py macro`).
3. **Entrée** : range d'ouverture de 15 min (or 17h20-17h35, pétrole
   18h-18h15, BTC et indices 18h30-18h45) ; première bougie M15 qui clôture
   au-delà du range dans le sens du biais ; stop 1 ATR M15 ; objectif 2R ou
   sortie à 1h (au plus tard 1h10). Si le signal est déjà passé, ne pas
   courir après. Les autres setups (cassure + retest, range borne à borne)
   ne se prennent que dans le sens du biais du jour.

Tests : avec le biais EMA 20/50, le range d'ouverture M15 sur l'or a donné
+0,36 R par trade en moyenne (+0,89 R tenu jusqu'à la fin de séance, 30
trades, 60 jours), contre -0,58 R pris contre le biais. Sur toutes les
entrées testées, l'or a fait +0,11 R avec le biais et -0,27 R contre (M15).
La pente HMA 21 Daily est un mauvais biais (-0,09 R) : la HMA sert en H1 et
H4. Les filtres fondamentaux de tendance (dollar, taux, VIX, Nasdaq) n'ont
pas amélioré le biais sur 26 ans (or) et 9 ans (BTC) : l'accord fondamental
est appliqué parce que l'utilisateur le demande, il réduit le nombre de
trades sans gain prouvé. Échantillons courts en M15 (60 jours) : à valider
sur le journal de trades.

## Structure et biais daily (`structure.py`)

L'outil suit la méthode d'analyse de l'utilisateur, dans cet ordre. Il décrit
le marché, il ne prédit pas la direction.

1. **Tendance** : pente de la HMA 21 en Daily, H4 et H1 (la HMA donne
   uniquement la tendance, pas l'entrée). Tendance retenue quand H4 et H1
   sont d'accord, sinon mixte. Structure HH/HL ou LH/LL et dernière cassure
   (BOS, CHoCH) en contexte. Testé sur l'or : les setups contre la pente HMA
   H1 ont perdu -0,17 R par trade, ils sont écartés.
2. **Où est le prix** : range de travail H1 (dernier sommet, dernier creux),
   premium au-dessus de 55 %, discount sous 45 %, équilibre entre les deux ;
   côté de l'ouverture de minuit ; position dans la plage de 20 jours.
3. **Phase** (H1, 12 dernières bougies) : expansion (mouvement efficace d'au
   moins 2 ATR), retracement (contre la tendance, entre 25 et 85 % de la
   jambe), accumulation (range après une baisse) ou distribution (range après
   une hausse), sinon transition. En expansion : ne pas courir après le prix.
4. **Liquidité** (règle de l'utilisateur : on trade avec ou sans liquidité ; le prix
   va dans le sens qu'il a choisi. La liquidité sert d'objectif quand elle existe,
   sinon l'objectif est 2R ; un niveau proche est un obstacle, jamais un refus) :
   sommets et creux H1 non pris, sommets ou creux égaux,
   veille, Asie (3h-9h), Londres (11h-14h) ; au-dessus = stops des vendeurs,
   en dessous = stops des acheteurs ; ce qui a déjà été pris aujourd'hui ;
   cible probable dans le sens de la tendance.
5. **Setups de base, confirmés par les étapes 1 à 4.** Le setup reste le
   premier setup de la méthode : cassure d'un niveau en clôture (checklist
   des cassures) puis retour sur le niveau, ou range d'ouverture de la
   session (or 17h20, pétrole 18h, sinon 18h30). Stop à 1,5 ATR M15 au-delà
   du niveau (130 ticks minimum sur MBT), ou milieu du range d'ouverture.
   Chaque setup reçoit :
   - étape 1 tendance : ✅ dans le sens, ⚠️ mixte (attendre), ❌ contre (à éviter) ;
   - étape 2 position : information seulement ;
   - étape 3 phase : information seulement ;
   - étape 4 liquidité : objectif sur la liquidité suivante, au moins 1,5R.
   Verdict : CONFIRMÉ (tendance), ATTENDRE (tendance mixte) ou À ÉVITER
   (contre la tendance). Chaque setup passe par
   `plan.py` (risque max 160 $ par défaut). `--chart` : PNG M15.

**Backtest de la méthode (or, H1, 2 ans, 1 trade par jour, 17h-21h, risque
160 $ max, sans biais d'anticipation)** :
- Le seul résultat solide est l'interdit : **contre la pente HMA H1**, l'ordre
  limite sur retest perd -0,41 R par trade (t = -3,3) et le rejet -0,17 R.
- Dans le sens de la HMA : retest en ordre limite +0,07 R, retest confirmé
  (entrée à la clôture) 0,00 R, rejet -0,08 R. Aucun avantage démontré.
- Range d'ouverture, London Breakout, Dual Thrust : environ 0 R.
- Premium ou discount, phase, figures de bougies : pas d'effet mesurable.
- Une première version du test entrait sur le niveau seulement quand la
  bougie reclôturait du bon côté (biais d'anticipation) et donnait +0,65 R :
  ce chiffre est faux, ne pas le citer.

## Lecture des bougies (`candles.py`)

**Règle de l'utilisateur : une bougie ne se lit que sur un support ou une
résistance, jamais ailleurs.** `structure.py` n'affiche la lecture que pour
les bougies qui touchent un niveau.

Lire l'anatomie avant le nom de la figure :
1. **Couleur et taille** par rapport à l'ATR (grande au-dessus de 1,3 ATR).
2. **Corps** en % de la bougie : au-dessus de 85 % = marubozu (conviction),
   sous 10 % = doji (indécision).
3. **Mèches** : une mèche de 40 % ou plus de la bougie = rejet de ce côté.
4. **Clôture** : dans le quart haut = acheteurs en contrôle, quart bas =
   vendeurs, entre les deux = indécision. Une mèche au-delà d'un niveau ne
   compte pas, seule la clôture compte.
5. **Contexte** : tendance des 5 bougies précédentes (un marteau n'existe
   qu'après une baisse, un pendu qu'après une hausse), niveau touché, sens de
   la HMA.
6. **Figures** reconnues sans regarder la bougie suivante : doji, libellule,
   pierre tombale, marteau, pendu, étoile filante, marteau inversé,
   marubozu, toupie, avalement, harami, pénétrante, nuage noir, pinces,
   inside et outside bar, étoile du matin et du soir, trois soldats, trois
   corbeaux.
7. **Heikin-Ashi** (bougies lissées) : trois bougies de même couleur sans
   mèche contraire = tendance nette.

**Ce que dit le test sur l'or (H1, 2 ans, 4 heures après la figure)** : aucune
figure seule ne donne d'avantage fiable (toutes avec |t| < 2). Les figures de
retournement contre la tendance échouent (étoile filante, pendu, avalement
baissier contre la HMA : -0,2 à -0,3 ATR). Dans le sens de la tendance, la
plupart font un peu mieux qu'une bougie quelconque (+0,2 à +0,4 ATR contre
+0,1). Une bougie de confirmation plus nette (clôture extrême, longue mèche
de rejet) n'a pas amélioré les entrées sur niveau. Les bougies servent à
lire qui contrôle et à ne pas entrer contre, pas à prédire.

## Lire le prix en ticks

Toutes les distances se donnent en ticks, comme TopstepX : ATR, hauteur d'un
range, distance du prix à chaque niveau, taille d'une bougie et de ses
mèches, stop et objectif (MGC : 1 tick = 0,10 $ de prix = 1 $ ; MBT : 1 tick
= 5 $ de prix = 0,50 $). `structure.py` et `candles.py` affichent les ticks.

Graphiques en ticks : seulement si l'utilisateur le demande. **Par défaut,
l'analyse se fait en bougies de temps (M15, H1, H4, Daily).** Outils :
- `ticks.py volume` : bougies d'activité, chacune se ferme quand le même
  nombre de contrats a été échangé (volume 1 minute du contrat standard
  sur Yahoo, 7 jours, retard d'environ 10 minutes). Le plus proche des
  bougies en ticks du CME qu'on puisse obtenir gratuitement, à la minute
  près. Bougie courte = marché actif.
- `ticks.py fetch` puis `bars` : vrais ticks de l'or au comptant
  (Dukascopy, hôte datafeed.dukascopy.com). Ce sont des changements de
  cotation, pas les transactions du CME. Le serveur limite très fortement
  le débit et peut refuser toutes les demandes (erreur 503) : dans ce cas
  utiliser `volume`.
- Sur une capture TopstepX en ticks (500T, 1000T), l'axe du temps n'est pas
  régulier : lire la structure et les bougies, pas les heures.

## Range borne à borne

Règles de l'utilisateur : dans un range, vendre la borne haute et acheter la
borne basse sur une bougie de rejet SUR la borne ; à la 3e ou 4e touche, la
mèche qui dépasse la borne puis clôture dedans est souvent la prise de
liquidité avant le mouvement inverse.

`structure.py` repère le range sur les 36 dernières bougies M15 et H1
(hauteur 3 à 8 ATR, déplacement net sous 35 % de la hauteur, au moins 2
touches de chaque côté), compte les touches, signale un balayage sur la
dernière bougie, et propose l'entrée sur la borne (stop au-delà de la borne,
objectif milieu ou borne opposée). Tendance mixte = normal dans un range.

**Test (or et BTC, H1 2 ans et M15 60 jours, entrée à la clôture de la bougie
sur la borne, stop au-delà de la mèche)** :
- Une bougie de rejet sur la borne fait mieux qu'une entrée sans regarder la
  bougie sur l'or H1 (-0,13 R contre -0,27 R ; objectif milieu +0,01 R contre
  -0,17 R), pas sur le BTC. Aucune version n'est gagnante de façon fiable.
- Or M15 (60 jours) vers la borne opposée : +0,34 R avec bougie de rejet
  (50 trades, non significatif).
- BTC M15 : nettement perdant (-0,47 à -0,65 R) avec un stop juste au-delà de
  la mèche : sur le BTC, un stop serré sur une borne se fait prendre.
- 3e ou 4e touche : le balayage n'a pas fait mieux que les autres touches
  (or H1 +0,01 R, BTC H1 -0,15 R, or M15 -0,26 R) ; après la 3e touche le prix
  casse la borne plus souvent qu'il ne rejoint la borne opposée (38 % contre
  24 % sur l'or H1). Exception à surveiller : or M15 4e touche, borne opposée
  d'abord dans 50 % des cas (14 cas seulement).

## Dépôt je-suis-tm/quant-trading (testé sur l'or H1)

MACD, Awesome Oscillator, Heikin-Ashi, Parabolic SAR : comme filtre de
tendance, ils donnent des résultats proches de la HMA 21 (aucun ne la bat
nettement). London Breakout et Dual Thrust : environ 0 R. Le script Shooting
Star du dépôt regarde la bougie suivante pour valider le signal (biais
d'anticipation) : la version de `candles.py` ne le fait pas.

**Lire une capture de l'utilisateur** : calibrer l'échelle avec deux prix de
l'axe (pixels par point) avant de lire un niveau ; repérer les derniers
sommets et creux, les nommer HH/HL/LH/LL ; dire si la dernière bougie a
cassé une structure (clôture, pas mèche) ; placer ses zones et lignes ; puis
comparer avec `structure.py` et signaler les écarts. Le biais reste le même
dans toute la réponse.

**Ce qui a été testé (or, 2 ans)** : le côté de l'ouverture de minuit à 17h
donne le bon sens de 17h à 1h dans environ 55 % des cas (t = +3). Ne
fonctionnent pas sur l'or : Londres qui fait l'extrême du jour (6 %),
« acheter en discount » IPDA, les FVG (pas mieux qu'une zone au hasard), le
retour à l'équilibre des plages 20/40/60 jours, le range d'ouverture seul
(-0,02 R par trade). Les modèles d'IA de prévision (Kronos, Chronos-Bolt,
Chronos-2) ne prédisent pas la direction : ne pas les utiliser pour cela.

## Règles du compte (celles de Topstep uniquement)

- Limite journalière (DLL) : **1 000 $** (`--daily-limit`, défaut 1000).
- Perte maximale (MLL) : **2 000 $ suiveuse** sur le meilleur solde de fin
  de journée, bloquée à 50 000 $. Vérifier le plancher dans ACCOUNT.
- Règle de régularité : la meilleure journée doit rester sous ~50 % du
  profit total (vérifier le pourcentage du Combine). `--consistency-cap`
  avertit seulement.
- Aucune limite de nombre de trades : `--max-trades` vaut 0 par défaut.
  L'utilisateur peut s'en fixer une s'il le souhaite.
- Le risque par trade (`--max-risk`, défaut 80 $) est un réglage de taille,
  pas une règle Topstep : l'utilisateur le choisit.
- Conseils (pas des règles) : ne pas cumuler des actifs corrélés (BTC, or,
  euro, Nasdaq), pas de trade de revanche après une perte.

## Ce qu'il ne fait jamais

Il ne passe aucun ordre, ne promet aucun gain, n'élargit jamais un stop,
n'entre pas sur une bougie qui n'a pas clôturé et ne lit pas une capture
floue comme un prix exact : il le dit et demande la valeur.

Éducation et outils, pas un conseil en investissement. Un PASS vérifie des
règles, ce n'est pas une recommandation.
