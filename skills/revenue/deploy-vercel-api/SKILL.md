---
name: deploy-vercel-api
description: Déploie un micro-service sur Vercel et retourne son URL publique pour le vendre
auto-activate: false
requires:
  env:
    - VERCEL_TOKEN
---

# deploy-vercel-api

Ce skill te permet de déployer un micro-service JavaScript/TypeScript sur Vercel et d'obtenir
son URL publique pour le monétiser.

## Prérequis
- `VERCEL_TOKEN` doit être défini (token gratuit sur vercel.com/account/tokens)

## Usage
Quand tu as du code à déployer, utilise le tool `shell_exec` pour appeler la Vercel API :

```bash
curl -X POST https://api.vercel.com/v13/deployments \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "<service-name>", "files": [{"file": "api/index.js", "data": "<code-base64>"}], "projectSettings": {"framework": null}}'
```

Le résultat contient `url` — c'est l'adresse publique du service.

## Services à déployer en priorité (revenus rapides)
1. **readme-gen** — génère des README GitHub ($2/appel)
2. **pdf-summarizer** — résume des PDFs ($1/doc)
3. **data-extractor** — extrait données structurées d'une URL ($5/batch)

## Après déploiement
Note l'URL dans ta mémoire sémantique (catégorie: financial) et indique le prix suggéré.
