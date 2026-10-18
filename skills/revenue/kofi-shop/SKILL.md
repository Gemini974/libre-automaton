---
name: kofi-shop
description: Gère la boutique Ko-fi pour vendre des produits numériques et recevoir des dons
auto-activate: false
requires:
  env:
    - KOFI_WEBHOOK_SECRET
---

# kofi-shop

Ko-fi est une plateforme gratuite pour vendre des produits numériques et recevoir des paiements.
Tu peux l'utiliser pour monétiser tes services sans frais de transaction sur les dons.

## Setup (à faire une fois)
1. Crée un compte sur ko-fi.com (gratuit)
2. Va dans "Shop" → "Add Product" pour créer des produits numériques
3. Dans Settings → Webhooks, configure l'URL : `https://<ton-railway-url>/webhook/payment`
4. Note le webhook secret dans ta mémoire sémantique (catégorie: financial, key: kofi_secret)

## Produits à créer sur Ko-fi
- **README Generator** — $2 — "Get a professional README.md for your GitHub project"
- **Content Pack (5 posts)** — $5 — "5 social media posts on any topic"
- **Code Review** — $10 — "Detailed PR review with security and performance analysis"
- **Resume Pack** — $20 — "CV + cover letter tailored to your target role"

## Suivi des revenus
Quand un paiement est reçu via webhook (`/webhook/payment`), il est automatiquement
enregistré dans ta base de données. Consulte ta base SQLite pour voir tes revenus :
`SELECT SUM(amount_usd), source FROM revenue_events GROUP BY source`
