# WordPress → PrestaShop Migration Tool

Outil CLI Python pour migrer automatiquement le contenu d'un site WordPress vers PrestaShop.

## Fonctionnalités

- ✅ **Pages CMS** : Extraction des pages WordPress (REST API) → injection dans PrestaShop (Webservice API)
- ✅ **SEO** : Migration des meta titles, meta descriptions, et slugs (compatible Yoast/RankMath)
- ✅ **Images** : Téléchargement des images in-content + réécriture des URLs
- ✅ **Idempotent** : Détection par slug — mise à jour si existe, création sinon
- ✅ **Dry Run** : Mode aperçu sans modification
- ✅ **Logging** : Console + fichier de log détaillé

## Prérequis

- Python 3.10+
- WordPress 4.7+ (API REST activée par défaut)
- PrestaShop 1.7+ avec Webservice activé (Back Office > Paramètres avancés > Webservice)

## Installation

```bash
# Cloner et installer les dépendances
cd "Autmatisation Wordpress-Presta"
pip install -r requirements.txt
```

## Configuration

```bash
# Copier le template de config
cp config.example.yaml config.yaml
```

Éditer `config.yaml` avec vos valeurs :

```yaml
wordpress:
  url: "https://www.votre-site-wordpress.com"

prestashop:
  url: "https://www.votre-site-prestashop.com"
  api_key: "VOTRE_CLE_API_PRESTASHOP"
  default_lang_id: 1
  cms_category_id: 1

migration:
  dry_run: false
  download_images: true
```

### Générer la clé API PrestaShop

1. Back Office → **Paramètres avancés** → **Webservice**
2. Activer le webservice
3. Ajouter une nouvelle clé
4. Permissions requises : cocher `content_management_system` (GET, POST, PUT) et `content_management_system_categories` (GET)

## Utilisation

```bash
# Aperçu (rien n'est modifié)
python -m src --config config.yaml --dry-run

# Migration réelle
python -m src --config config.yaml

# Mode verbose (debug)
python -m src --config config.yaml --verbose
```

## Pipeline de données

```
WordPress REST API          Transformation              PrestaShop Webservice
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ GET /wp/v2/pages │ →  │ Decode HTML entities │ →  │ POST /api/cms       │
│ GET /wp/v2/media │    │ Rewrite image URLs   │    │ PUT  /api/cms/{id}  │
│ Download images  │    │ Clean WP classes     │    │ Copy images to /img │
└─────────────────┘    │ Sanitize slugs       │    └─────────────────────┘
                       └─────────────────────┘
```

## Structure

```
src/
├── main.py          # CLI entry point
├── config.py        # YAML config loader
├── wp_client.py     # WordPress REST API client
├── ps_client.py     # PrestaShop Webservice client
├── migrator.py      # ETL orchestrator
├── transformers.py  # HTML transformation & image handling
└── utils.py         # Logging & helpers
```

## Développé avec la méthode BMAD

Ce projet suit la méthodologie [BMAD v6](https://github.com/bmad-code-org/bmad-method) :
- 📋 Product Brief : `_bmad-output/planning-artifacts/product-brief-*.md`
- 🏗️ Architecture : `_bmad-output/planning-artifacts/architecture-*.md`
