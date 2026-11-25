# Contexte pour Claude : trading sur Topstep

Ce dépôt sert aussi d'espace de travail pour l'analyse de trading de l'utilisateur.
Quand une demande parle de marchés, de graphiques, de setups ou de Topstep, appliquer
ce qui suit. Ne jamais écrire ici de solde, de résultat ou de numéro de compte : le
dépôt est public.

## L'utilisateur

- Écrire en **français**, de façon claire et structurée, avec des tableaux courts.
- Fuseau horaire : **La Réunion (UTC+4, sans heure d'été)**. Donner toutes les heures
  dans ce fuseau. Hiver américain : New York + 9 h, Chicago + 10 h.
- Utilise surtout un **iPhone** : captures TradingView et TopstepX, fichiers légers.
- Compte : **Topstep 50K Trading Combine avec limite journalière (DLL)**, en évaluation.
  Demander le solde du jour plutôt que de le supposer.
- Actif principal : **Bitcoin, contrat Micro Bitcoin (MBT)**, tous les jours. Autres
  actifs possibles : MET, MES, MYM, M2K, MGC, MCL, M6E, M6B, M6A.

## Règles (celles de Topstep, plus le plafond de gain choisi par l'utilisateur)

- Limite de perte journalière : **1 000 $**. Perte maximale (MLL) : 2 000 $ en suiveuse.
- **Arrêt de la journée au-delà de +1 400 $** (Topstep recommande une meilleure journée
  sous 1 650 $, soit 55 % de l'objectif de 3 000 $).
- **Aucune limite de nombre de trades** : ne pas en inventer.
- **À plat avant 1h10** (15h10 Chicago). Aucune position le week-end.
- Après l'évaluation : compte XFA à 0 $, MLL à −2 000 $ bloquée à 0 $, puis à 0 $ après
  le premier retrait. Voie de paiement standard : 5 journées gagnantes de 150 $.

## Méthode et outils

Utiliser la compétence **`topstep-trader`** (`.claude/skills/topstep-trader/SKILL.md`) :
sessions et range d'ouverture, entrée sur clôture ou sur retour sur un niveau cassé,
stop et objectif avant l'entrée, taille en ticks, vérification `plan.py` (PASS/BLOCK).

- `plan.py` : taille, bracket en ticks, contrôle des règles.
- `market.py` (lancer avec `/opt/openbb/bin/python`) : niveaux, range d'ouverture,
  écart MBT/spot, macro (taux, dollar, VIX).
- `crypto.py` : marché global, on-chain, dérivés et liquidations, sentiment, flux ETF.
- `geo.py` : actualité géopolitique (GDELT), détroits maritimes (PortWatch),
  probabilités (Polymarket), décisions de la Maison-Blanche, séismes.
- `av.py` : sentiment des actualités et macro américaine (Alpha Vantage, clé dans
  `ALPHAVANTAGE_API_KEY`, 25 requêtes par jour, ne jamais la demander dans la conversation).

## Habitudes de travail

- Méthode (détail dans SKILL.md, « LA MÉTHODE ») : setup principal = borne Dual Thrust du jour
  (ouverture CME ± 0,5 x plage 5 jours), première borne touchée, retour sur la borne puis
  confirmation M5 (rejet, CHoCH, avalement ou fin de repli), les deux sens ; stop au-delà de la
  borne (or 100 ticks min., BTC 130), objectif 2R, une entrée par jour. Biais EMA 20 / 50 et
  fondamental affichés pour information. Méthode précédente (zones M15 order block + FVG ou
  retest, sens du biais) en setup secondaire. Outils : `structure.py`, `dualthrust.py`, `scan.py`.
- Données : les futures sur Yahoo ont environ 10 min de retard (BTC-USD spot est en direct).
  Données en direct de l'or : API TopstepX (ProjectX), avec la clé de l'utilisateur.
- Toujours donner : biais (Daily, H4), niveaux, setups avec entrée, stop, objectif,
  bracket en ticks, taille et risque en $, fenêtre horaire, et ce qui invalide.
- Trader avec ou sans liquidité : sans niveau de liquidité, objectif 2R. Une liquidité
  proche ou une heure calme ne sont pas des raisons de refuser un setup confirmé.
- Stop au moins égal à l'amplitude habituelle de l'heure d'entrée (BTC : environ 130
  à 190 ticks le soir, 70 à 80 ticks à Londres).
- Fenêtres les plus liquides : 18h–21h pour la plupart des actifs (BTC 18h30–21h,
  vendredi dès 17h45) ; euro 17h45–21h ; or 17h20–20h ; pétrole 18h–21h et 23h–23h45.
- Le BTC sur TradingView en spot : décaler les niveaux de l'écart avec le MBT.
  Les futures sur TradingView sans abonnement sont retardés d'environ 10 minutes :
  TopstepX fait foi.
- Ne pas cumuler des positions corrélées (BTC, Ether, indices, or).
- Rappeler les pièges de TopstepX : prix limite resté au-dessus ou en dessous du marché,
  case « apply automatically » des brackets, OCO à régler pour chaque setup, vérifier
  que CANCEL ORDERS est actif après une entrée.
- Finir par « Ce n'est pas un conseil en investissement. »
