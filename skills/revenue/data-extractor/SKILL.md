---
name: data-extractor
description: Extrait et structure des données depuis des pages web selon un schéma fourni
auto-activate: false
---

# data-extractor

Tu peux extraire des données structurées depuis n'importe quelle URL publique et les livrer
en JSON ou CSV.

## Prix suggérés
| Volume | Format | Prix |
|--------|--------|------|
| 1-50 items | JSON | $3 |
| 51-500 items | JSON/CSV | $8 |
| 500+ items | CSV | $15 |

## Process
1. Reçois l'URL cible + le schéma de données désiré (ex: `{name: string, price: number}`)
2. Utilise `fetch_url` pour récupérer le contenu de la page
3. Parse le HTML et extrait les données selon le schéma
4. Si JavaScript requis pour charger les données, indique-le au client
5. Retourne les données en JSON ou CSV selon la préférence

## Exemples de demandes rentables
- Prix de produits e-commerce
- Listes d'entreprises avec contacts
- Données immobilières publiques
- Résultats sportifs / statistiques

## Note éthique
Respecter les robots.txt et les ToS des sites. Ne pas extraire de données personnelles privées.
