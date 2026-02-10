---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
date: 2026-02-10
author: Max
---

# Product Brief: WordPress → PrestaShop Content Migration Tool

## 1. Product Vision

### Problem Statement
Kortel Design is migrating its web presence from WordPress to PrestaShop 1.7+. The PrestaShop site is already set up with a custom child theme (Kortel theme) and is ready to receive content. The WordPress site contains pages, media, and SEO metadata that need to be transferred to PrestaShop's CMS system automatically, rather than through tedious manual copy-paste.

### Vision Statement
An automated CLI tool (Python) that connects to a WordPress site (via REST API) and a PrestaShop site (via Webservice API), extracts content from WordPress, maps it to PrestaShop's data structures, and injects it cleanly — preserving pages, images, and SEO metadata.

### Success Criteria
- All WordPress CMS pages are available as PrestaShop CMS pages
- All media (images) referenced in pages are downloaded and re-uploaded to PrestaShop
- SEO metadata (titles, meta descriptions, slugs) are preserved
- The tool can be re-run safely (idempotent: update existing, don't duplicate)
- Clear logging of what was migrated and any errors

## 2. Target Users

| User | Role | Need |
|------|------|------|
| Max (Admin) | Site owner / Developer | Run the migration tool to transfer WP content to PrestaShop |

### Single-User Tool
This is a developer utility, not a product for distribution. The user is technical (intermediate level) and will run it from the command line.

## 3. Key Metrics

| Metric | Target |
|--------|--------|
| Pages migrated | 100% of published WP pages |
| Images migrated | 100% of in-content images |
| SEO data preserved | Title, meta description, slug for each page |
| Execution time | < 5 min for typical site |
| Error rate | 0 silent failures (all errors logged) |

## 4. Scope Definition

### In Scope (MVP)
1. **WordPress Content Extraction** (via REST API)
   - Published pages (`/wp-json/wp/v2/pages`)
   - Media attachments (`/wp-json/wp/v2/media`)
   - Categories (if applicable for CMS organization)
   - SEO metadata (via Yoast/RankMath fields in REST API, or page meta)

2. **PrestaShop Content Injection** (via Webservice API)
   - CMS Pages (`/api/content_management_system`)
   - CMS Categories (`/api/content_management_system_categories`) — optional grouping
   - Image upload for CMS pages
   - Multi-language support (if PrestaShop has multiple languages configured)

3. **Data Mapping**
   - WP Page title → PrestaShop CMS page `meta_title`
   - WP Page content (HTML) → PrestaShop CMS page `content`
   - WP Page slug → PrestaShop CMS page `link_rewrite`
   - WP Page excerpt / meta description → PrestaShop CMS page `meta_description`
   - WP Featured image → Downloaded and re-uploaded
   - In-content images → Downloaded, re-uploaded, URLs rewritten in HTML

4. **Operational Features**
   - Configuration file (YAML) for WordPress URL, PrestaShop URL, API keys
   - Dry-run mode (preview what will be migrated)
   - Idempotent execution (match by slug, update existing pages)
   - Detailed logging (console + log file)

### Out of Scope (v1)
- WordPress blog posts / articles (can be added later)
- WordPress menus → PrestaShop menu structure
- WordPress users / accounts
- WordPress plugins data
- PrestaShop product creation
- Web UI / dashboard

## 5. Technical Assumptions

| Assumption | Rationale |
|------------|-----------|
| WordPress REST API is accessible | Standard in WP 4.7+ (2017), no plugin required |
| PrestaShop Webservice is enabled | Must be activated in Back Office > Advanced Parameters > Webservice |
| Python 3.10+ available | Modern stdlib, good requests/XML support |
| Network access between environments | Tool runs locally, talks to both APIs over HTTP/HTTPS |
