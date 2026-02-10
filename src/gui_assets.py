"""
Single-page HTML/CSS/JS frontend for the migration GUI.
Embedded as a Python string to avoid external files.
"""


def get_html() -> str:
    return '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WP → PrestaShop Migration</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ── Reset & Base ──────────────────────────────────────────── */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
:root {
    --bg-deep: #0a0a1a;
    --bg-card: rgba(18, 18, 42, 0.85);
    --bg-card-hover: rgba(25, 25, 55, 0.95);
    --bg-input: rgba(30, 30, 65, 0.9);
    --border: rgba(100, 100, 180, 0.15);
    --border-active: rgba(102, 126, 234, 0.5);
    --accent: #667eea;
    --accent2: #764ba2;
    --cyan: #4fc3f7;
    --magenta: #ce93d8;
    --green: #66bb6a;
    --orange: #ffa726;
    --red: #ef5350;
    --text: #e0e0e0;
    --text-dim: #888;
    --text-muted: #555;
    --radius: 12px;
    --radius-sm: 8px;
    --glass: blur(20px);
}
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg-deep);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
    overflow-x: hidden;
}
body::before {
    content: '';
    position: fixed;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle at 30% 20%, rgba(102,126,234,0.08) 0%, transparent 50%),
                radial-gradient(circle at 70% 80%, rgba(118,75,162,0.06) 0%, transparent 50%);
    z-index: -1;
    animation: bgPulse 20s ease-in-out infinite;
}
@keyframes bgPulse {
    0%, 100% { transform: translate(0, 0) rotate(0deg); }
    50% { transform: translate(-2%, -1%) rotate(1deg); }
}

/* ── Layout ────────────────────────────────────────────────── */
.app { max-width: 1400px; margin: 0 auto; padding: 20px; }
.header {
    text-align: center; padding: 30px 0 20px;
}
.header h1 {
    font-size: 2.2em; font-weight: 700;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px;
}
.header .subtitle { color: var(--text-dim); font-size: 0.95em; }

/* ── Tabs ──────────────────────────────────────────────────── */
.tabs {
    display: flex; gap: 4px; margin: 20px 0;
    background: var(--bg-card);
    backdrop-filter: var(--glass);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    padding: 4px;
    overflow-x: auto;
}
.tab-btn {
    flex: 1; padding: 12px 20px; border: none; background: transparent;
    color: var(--text-dim); font-family: inherit; font-size: 0.9em;
    font-weight: 500; cursor: pointer; border-radius: var(--radius-sm);
    transition: all 0.3s ease; white-space: nowrap;
}
.tab-btn:hover { color: var(--text); background: rgba(102,126,234,0.1); }
.tab-btn.active {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: white; font-weight: 600;
    box-shadow: 0 4px 15px rgba(102,126,234,0.3);
}
.tab-content { display: none; animation: fadeIn 0.3s ease; }
.tab-content.active { display: block; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* ── Cards ─────────────────────────────────────────────────── */
.card {
    background: var(--bg-card);
    backdrop-filter: var(--glass);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 20px;
    transition: border-color 0.3s;
}
.card:hover { border-color: var(--border-active); }
.card h2 {
    font-size: 1.2em; font-weight: 600; margin-bottom: 16px;
    display: flex; align-items: center; gap: 8px;
}
.card h2 .icon { font-size: 1.2em; }

/* ── Form elements ─────────────────────────────────────────── */
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: 0.85em; font-weight: 500; color: var(--text-dim); }
.form-group input, .form-group select {
    padding: 10px 14px; background: var(--bg-input); border: 1px solid var(--border);
    border-radius: var(--radius-sm); color: var(--text); font-family: inherit;
    font-size: 0.9em; transition: border-color 0.3s, box-shadow 0.3s;
    outline: none;
}
.form-group input:focus, .form-group select:focus {
    border-color: var(--accent); box-shadow: 0 0 0 3px rgba(102,126,234,0.15);
}
.form-group input::placeholder { color: var(--text-muted); }

/* ── Buttons ───────────────────────────────────────────────── */
.btn {
    padding: 10px 20px; border: none; border-radius: var(--radius-sm);
    font-family: inherit; font-size: 0.9em; font-weight: 500;
    cursor: pointer; display: inline-flex; align-items: center; gap: 8px;
    transition: all 0.3s ease; position: relative; overflow: hidden;
}
.btn::after {
    content: ''; position: absolute; top: 50%; left: 50%;
    width: 0; height: 0; border-radius: 50%;
    background: rgba(255,255,255,0.2);
    transition: width 0.4s, height 0.4s, top 0.4s, left 0.4s;
}
.btn:active::after { width: 200px; height: 200px; top: -60px; left: -60px; }
.btn-primary {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: white;
    box-shadow: 0 4px 15px rgba(102,126,234,0.25);
}
.btn-primary:hover { box-shadow: 0 6px 20px rgba(102,126,234,0.4); transform: translateY(-1px); }
.btn-secondary { background: var(--bg-input); color: var(--text); border: 1px solid var(--border); }
.btn-secondary:hover { border-color: var(--accent); }
.btn-success { background: linear-gradient(135deg, #43a047, #2e7d32); color: white; }
.btn-success:hover { box-shadow: 0 4px 15px rgba(67,160,71,0.3); }
.btn-danger { background: linear-gradient(135deg, var(--red), #c62828); color: white; }
.btn-danger:hover { box-shadow: 0 4px 15px rgba(239,83,80,0.3); }
.btn-sm { padding: 6px 12px; font-size: 0.8em; }
.btn-group { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }

/* ── Stats bar ─────────────────────────────────────────────── */
.stats-bar {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px; margin: 16px 0;
}
.stat-box {
    background: var(--bg-input); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 16px; text-align: center;
    transition: all 0.3s;
}
.stat-box:hover { border-color: var(--accent); transform: translateY(-2px); }
.stat-value { font-size: 2em; font-weight: 700; }
.stat-label { font-size: 0.75em; color: var(--text-dim); margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }
.stat-cms .stat-value { color: var(--cyan); }
.stat-product .stat-value { color: var(--magenta); }
.stat-skip .stat-value { color: var(--text-muted); }
.stat-total .stat-value { color: var(--accent); }

/* ── Filter toolbar ────────────────────────────────────────── */
.toolbar {
    display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
    margin: 16px 0; padding: 12px 16px;
    background: var(--bg-input); border-radius: var(--radius-sm);
    border: 1px solid var(--border);
}
.toolbar .search-input {
    flex: 1; min-width: 200px; padding: 8px 12px;
    background: rgba(0,0,0,0.2); border: 1px solid var(--border);
    border-radius: 20px; color: var(--text); font-family: inherit;
    font-size: 0.85em; outline: none;
}
.toolbar .search-input:focus { border-color: var(--accent); }
.filter-pill {
    padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
    background: transparent; color: var(--text-dim); font-family: inherit;
    font-size: 0.8em; cursor: pointer; transition: all 0.2s;
}
.filter-pill:hover { border-color: var(--accent); color: var(--text); }
.filter-pill.active { background: var(--accent); color: white; border-color: var(--accent); }
.filter-pill.pill-cms.active { background: #0277bd; border-color: #0277bd; }
.filter-pill.pill-product.active { background: #7b1fa2; border-color: #7b1fa2; }
.filter-pill.pill-skip.active { background: #455a64; border-color: #455a64; }

/* ── Pages table ───────────────────────────────────────────── */
.pages-table { width: 100%; border-collapse: separate; border-spacing: 0; }
.pages-table thead th {
    position: sticky; top: 0; z-index: 10;
    background: rgba(15,15,35,0.95); backdrop-filter: var(--glass);
    padding: 12px 14px; text-align: left; font-size: 0.8em;
    font-weight: 600; text-transform: uppercase; letter-spacing: 1px;
    color: var(--accent); border-bottom: 1px solid var(--border);
}
.pages-table tbody tr {
    transition: background 0.2s; cursor: pointer;
}
.pages-table tbody tr:hover { background: rgba(102,126,234,0.06); }
.pages-table tbody td {
    padding: 10px 14px; border-bottom: 1px solid rgba(100,100,180,0.06);
    font-size: 0.88em; vertical-align: middle;
}
.pages-table .col-check { width: 40px; text-align: center; }
.pages-table .col-target { width: 120px; }
.pages-table .col-slug { max-width: 220px; }
.pages-table .col-title { max-width: 280px; }
.pages-table .col-size, .pages-table .col-img, .pages-table .col-seo { width: 70px; text-align: center; }

.slug-text { color: var(--cyan); font-family: 'JetBrains Mono', monospace; font-size: 0.85em; }

/* Type badges */
.type-badge {
    padding: 2px 8px; border-radius: 10px; font-size: 0.75em;
    font-weight: 600; letter-spacing: 0.5px; display: inline-block;
}
.type-badge.type-page { background: rgba(102,126,234,0.15); color: var(--accent); }
.type-badge.type-post { background: rgba(255,167,38,0.15); color: var(--orange); }
.category-tag {
    padding: 1px 6px; border-radius: 6px; font-size: 0.7em;
    background: rgba(79,195,247,0.1); color: var(--cyan); margin-left: 4px;
}

/* Target selector in table */
.target-select {
    padding: 4px 8px; border-radius: 6px; border: none;
    font-family: inherit; font-size: 0.85em; cursor: pointer;
    outline: none; font-weight: 500;
}
.target-select.target-cms { background: #0d2137; color: var(--cyan); }
.target-select.target-product { background: #2a0d37; color: var(--magenta); }
.target-select.target-skip { background: #1a1a1a; color: var(--text-muted); }

/* ── Page detail panel ─────────────────────────────────────── */
.detail-panel {
    position: fixed; top: 0; right: -450px; width: 440px; height: 100vh;
    background: rgba(12,12,30,0.97); backdrop-filter: var(--glass);
    border-left: 1px solid var(--border); z-index: 100;
    transition: right 0.3s ease; overflow-y: auto; padding: 24px;
}
.detail-panel.open { right: 0; box-shadow: -10px 0 40px rgba(0,0,0,0.5); }
.detail-close {
    position: absolute; top: 16px; right: 16px;
    width: 32px; height: 32px; border-radius: 50%;
    border: 1px solid var(--border); background: var(--bg-input);
    color: var(--text); cursor: pointer; font-size: 1.2em;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s;
}
.detail-close:hover { border-color: var(--red); color: var(--red); }
.detail-panel h3 { font-size: 1.3em; margin-bottom: 16px; padding-right: 40px; }
.detail-meta { display: grid; grid-template-columns: 120px 1fr; gap: 8px; font-size: 0.88em; }
.detail-meta dt { color: var(--accent); font-weight: 500; }
.detail-meta dd { color: var(--text-dim); word-break: break-word; }
.detail-preview {
    margin-top: 16px; padding: 14px;
    background: rgba(0,0,0,0.3); border-radius: var(--radius-sm);
    font-size: 0.85em; color: var(--text-dim); line-height: 1.7;
}
.detail-thumbs { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.detail-thumbs img {
    width: 100px; height: 70px; object-fit: cover;
    border-radius: 6px; border: 1px solid var(--border);
}

/* ── Migration log ─────────────────────────────────────────── */
.log-terminal {
    background: #0a0a14; border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 16px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.8em; line-height: 1.8; max-height: 500px;
    overflow-y: auto; color: #a0a0c0;
}
.log-terminal .log-success { color: var(--green); }
.log-terminal .log-error { color: var(--red); }
.log-terminal .log-warning { color: var(--orange); }
.log-terminal .log-info { color: var(--cyan); }

/* ── Progress bar ──────────────────────────────────────────── */
.progress-container {
    background: var(--bg-input); border-radius: 20px;
    height: 24px; overflow: hidden; border: 1px solid var(--border);
    margin: 16px 0; position: relative;
}
.progress-bar {
    height: 100%; border-radius: 20px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    transition: width 0.5s ease;
    position: relative; overflow: hidden;
}
.progress-bar::after {
    content: ''; position: absolute; top: 0; left: -200%;
    width: 200%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    animation: progressShine 2s infinite;
}
@keyframes progressShine { to { left: 200%; } }
.progress-text {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    font-size: 0.75em; font-weight: 600; color: white;
    text-shadow: 0 1px 3px rgba(0,0,0,0.5);
}

/* ── Connection status indicators ───────────────────────────── */
.status-dot {
    width: 10px; height: 10px; border-radius: 50%;
    display: inline-block; margin-right: 6px;
}
.status-dot.ok { background: var(--green); box-shadow: 0 0 6px var(--green); }
.status-dot.fail { background: var(--red); box-shadow: 0 0 6px var(--red); }
.status-dot.pending { background: var(--orange); animation: pulse 1.5s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* ── Toast notifications ───────────────────────────────────── */
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 200; }
.toast {
    background: var(--bg-card); backdrop-filter: var(--glass);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 14px 20px; margin-bottom: 8px; min-width: 280px;
    font-size: 0.9em; animation: slideIn 0.3s ease;
    box-shadow: 0 8px 30px rgba(0,0,0,0.3);
}
.toast.success { border-left: 3px solid var(--green); }
.toast.error { border-left: 3px solid var(--red); }
.toast.info { border-left: 3px solid var(--accent); }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } }

/* ── Checkbox styling ──────────────────────────────────────── */
.custom-check {
    width: 18px; height: 18px; border-radius: 4px;
    border: 2px solid var(--border); background: transparent;
    cursor: pointer; appearance: none; -webkit-appearance: none;
    transition: all 0.2s; position: relative;
}
.custom-check:checked {
    background: var(--accent); border-color: var(--accent);
}
.custom-check:checked::after {
    content: '✓'; position: absolute; top: -1px; left: 2px;
    color: white; font-size: 12px; font-weight: 700;
}

/* ── Responsive ────────────────────────────────────────────── */
@media (max-width: 768px) {
    .app { padding: 12px; }
    .header h1 { font-size: 1.5em; }
    .form-grid { grid-template-columns: 1fr; }
    .detail-panel { width: 100%; right: -100%; }
    .tabs { flex-wrap: nowrap; overflow-x: auto; }
}

/* ── Loading spinner ───────────────────────────────────────── */
.spinner {
    width: 20px; height: 20px; border: 2px solid var(--border);
    border-top-color: var(--accent); border-radius: 50%;
    animation: spin 0.8s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
    text-align: center; padding: 60px 20px; color: var(--text-dim);
}
.empty-state .icon { font-size: 3em; margin-bottom: 12px; }
.empty-state p { max-width: 400px; margin: 0 auto; }

/* ── Modal overlay ─────────────────────────────────────── */
.modal-overlay {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
    z-index: 300; display: flex; align-items: center;
    justify-content: center; opacity: 0; pointer-events: none;
    transition: opacity 0.25s ease;
}
.modal-overlay.show { opacity: 1; pointer-events: auto; }
.modal-box {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 28px; width: 480px;
    max-width: 90vw; box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    transform: translateY(20px); transition: transform 0.25s ease;
}
.modal-overlay.show .modal-box { transform: translateY(0); }
.modal-box h3 {
    font-size: 1.2em; font-weight: 600; margin-bottom: 16px;
    display: flex; align-items: center; gap: 8px;
}
.modal-box .separator {
    height: 1px; background: var(--border); margin: 16px 0;
}
.detail-edit-group {
    margin-top: 14px; padding: 14px;
    background: rgba(0,0,0,0.2); border-radius: var(--radius-sm);
    border: 1px solid var(--border);
}
.detail-edit-group h4 {
    font-size: 0.85em; font-weight: 600; color: var(--accent);
    margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;
}
.detail-edit-row {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.detail-edit-row label {
    font-size: 0.82em; color: var(--text-dim); min-width: 110px;
}
.detail-edit-row input, .detail-edit-row select {
    flex: 1; padding: 6px 10px; background: var(--bg-input);
    border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); font-family: inherit; font-size: 0.85em;
    outline: none;
}
.detail-edit-row input:focus, .detail-edit-row select:focus {
    border-color: var(--accent);
}
</style>
</head>
<body>
<div class="app">
    <div class="header">
        <h1>🚀 WordPress → PrestaShop</h1>
        <p class="subtitle">Outil de migration de contenu</p>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('config')">⚙️ Configuration</button>
        <button class="tab-btn" onclick="switchTab('scanner')">🔍 Scanner & Router</button>
        <button class="tab-btn" onclick="switchTab('migration')">🚀 Migration</button>
        <button class="tab-btn" onclick="switchTab('results')">📊 Résultats</button>
    </div>

    <!-- ═══════════ CONFIG TAB ═══════════ -->
    <div id="tab-config" class="tab-content active">
        <div class="card">
            <h2><span class="icon">🌐</span> WordPress</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>URL du site</label>
                    <input type="url" id="cfg-wp-url" placeholder="https://www.example.com" />
                </div>
                <div class="form-group">
                    <label>Utilisateur (optionnel)</label>
                    <input type="text" id="cfg-wp-user" placeholder="admin" />
                </div>
                <div class="form-group">
                    <label>App password (optionnel)</label>
                    <input type="password" id="cfg-wp-pass" placeholder="xxxx xxxx xxxx" />
                </div>
            </div>
        </div>

        <div class="card">
            <h2><span class="icon">🛒</span> PrestaShop</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>URL de la boutique</label>
                    <input type="url" id="cfg-ps-url" placeholder="https://shop.example.com" />
                </div>
                <div class="form-group">
                    <label>Clé API Webservice</label>
                    <input type="password" id="cfg-ps-key" placeholder="ABCDEF1234567890" />
                </div>
                <div class="form-group">
                    <label>Langue par défaut (ID)</label>
                    <input type="number" id="cfg-ps-lang" value="1" min="1" />
                </div>
                <div class="form-group">
                    <label>Catégorie CMS (ID)</label>
                    <input type="number" id="cfg-ps-cat" value="1" min="1" />
                </div>
            </div>
        </div>

        <div class="card">
            <h2><span class="icon">⚙️</span> Options de migration</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="cfg-dry-run" checked class="custom-check" style="vertical-align:middle" />
                        Mode test (dry-run) — aucune modification
                    </label>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="cfg-images" checked class="custom-check" style="vertical-align:middle" />
                        Télécharger les images
                    </label>
                </div>
                <div class="form-group">
                    <label>Répertoire images cible (local)</label>
                    <input type="text" id="cfg-img-dir" placeholder="/var/www/prestashop/img/cms/" />
                </div>

                <h3 style="margin-top:20px; color:var(--primary)">📡 Upload FTP des images</h3>
                <div class="form-group">
                    <label>Hôte FTP</label>
                    <input type="text" id="cfg-ftp-host" placeholder="shop.korteldesign.com" />
                </div>
                <div class="form-group">
                    <label>Utilisateur FTP</label>
                    <input type="text" id="cfg-ftp-user" placeholder="user@domain.com" />
                </div>
                <div class="form-group">
                    <label>Mot de passe FTP</label>
                    <input type="password" id="cfg-ftp-pass" />
                </div>
                <div class="form-group">
                    <label>Chemin distant</label>
                    <input type="text" id="cfg-ftp-path" value="/img/cms" placeholder="/img/cms" />
                </div>
            </div>
        </div>

        <div class="btn-group">
            <button class="btn btn-primary" onclick="saveConfig()">💾 Sauvegarder la configuration</button>
            <button class="btn btn-secondary" onclick="testConnection()">🔌 Tester les connexions</button>
        </div>

        <div id="connection-status" class="card" style="margin-top:16px; display:none">
            <h2><span class="icon">🔌</span> État des connexions</h2>
            <div style="display:flex; gap:24px">
                <div><span id="wp-status-dot" class="status-dot pending"></span> WordPress: <span id="wp-status-text">test...</span></div>
                <div><span id="ps-status-dot" class="status-dot pending"></span> PrestaShop: <span id="ps-status-text">test...</span></div>
            </div>
        </div>
    </div>

    <!-- ═══════════ SCANNER TAB ═══════════ -->
    <div id="tab-scanner" class="tab-content">
        <div class="card">
            <h2><span class="icon">🔍</span> Scanner les pages WordPress</h2>
            <div style="display:flex; gap:12px; align-items:flex-end">
                <div class="form-group" style="flex:1">
                    <label>URL WordPress</label>
                    <input type="url" id="scan-url" placeholder="https://www.korteldesign.com" />
                </div>
                <button class="btn btn-primary" onclick="scanWordPress()" id="btn-scan">🔍 Scanner</button>
            </div>
        </div>

        <div id="scan-results" style="display:none">
            <div class="stats-bar">
                <div class="stat-box stat-total"><div class="stat-value" id="stat-total">0</div><div class="stat-label">Total</div></div>
                <div class="stat-box"><div class="stat-value" id="stat-pages" style="color:var(--accent)">0</div><div class="stat-label">Pages</div></div>
                <div class="stat-box"><div class="stat-value" id="stat-posts" style="color:var(--orange)">0</div><div class="stat-label">Articles</div></div>
                <div class="stat-box stat-cms"><div class="stat-value" id="stat-cms">0</div><div class="stat-label">→ CMS</div></div>
                <div class="stat-box stat-product"><div class="stat-value" id="stat-product">0</div><div class="stat-label">→ Produits</div></div>
                <div class="stat-box stat-skip"><div class="stat-value" id="stat-skip">0</div><div class="stat-label">→ Ignorées</div></div>
            </div>

            <div class="toolbar">
                <input type="text" class="search-input" id="search-pages" placeholder="🔎 Rechercher..." oninput="filterPages()" />
                <button class="filter-pill active" data-filter="all" onclick="setFilter('all', this)">Tout</button>
                <button class="filter-pill pill-cms" data-filter="cms" onclick="setFilter('cms', this)">📄 CMS</button>
                <button class="filter-pill pill-product" data-filter="product" onclick="setFilter('product', this)">🏷️ Produits</button>
                <button class="filter-pill pill-skip" data-filter="skip" onclick="setFilter('skip', this)">⏭️ Ignorées</button>
                <span style="border-left:1px solid var(--border); height:20px; margin:0 4px"></span>
                <button class="filter-pill" data-filter="type-page" onclick="setFilter('type-page', this)">📃 Pages</button>
                <button class="filter-pill" data-filter="type-post" onclick="setFilter('type-post', this)">📝 Articles</button>
                <span style="flex:1"></span>
                <button class="btn btn-sm btn-secondary" onclick="bulkAction('cms')">📄 Sélection → CMS</button>
                <button class="btn btn-sm btn-secondary" onclick="bulkAction('product')">🏷️ Sélection → Produit</button>
                <button class="btn btn-sm btn-secondary" onclick="bulkAction('skip')">⏭️ Sélection → Ignorer</button>
                <button class="btn btn-sm btn-secondary" onclick="autoCateg()">🤖 Auto</button>
            </div>

            <div style="overflow-x:auto; max-height:65vh; overflow-y:auto; border-radius:var(--radius-sm); border:1px solid var(--border)">
                <table class="pages-table">
                    <thead>
                        <tr>
                            <th class="col-check"><input type="checkbox" class="custom-check" id="check-all" onchange="toggleAll(this)" /></th>
                            <th class="col-target">Destination</th>
                            <th class="col-slug">Slug</th>
                            <th class="col-title">Titre</th>
                            <th class="col-size" style="width:55px">Type</th>
                            <th class="col-size">Taille</th>
                            <th class="col-img">Img</th>
                            <th class="col-seo">SEO</th>
                        </tr>
                    </thead>
                    <tbody id="pages-body"></tbody>
                </table>
            </div>
        </div>

        <div id="scan-empty" class="empty-state">
            <div class="icon">🌐</div>
            <p>Entrez l'URL WordPress et cliquez sur <strong>Scanner</strong> pour voir toutes les pages et articles disponibles.</p>
        </div>
    </div>

    <!-- ═══════════ MIGRATION TAB ═══════════ -->
    <div id="tab-migration" class="tab-content">
        <div class="card">
            <h2><span class="icon">🚀</span> Lancer la migration</h2>
            <div class="stats-bar" id="mig-stats">
                <div class="stat-box stat-cms"><div class="stat-value" id="mig-cms">0</div><div class="stat-label">Pages CMS</div></div>
                <div class="stat-box stat-product"><div class="stat-value" id="mig-product">0</div><div class="stat-label">Produits</div></div>
                <div class="stat-box stat-skip"><div class="stat-value" id="mig-skip">0</div><div class="stat-label">Ignorées</div></div>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="startMigration(true)" id="btn-dry">🔍 Dry Run (test)</button>
                <button class="btn btn-success" onclick="startMigration(false)" id="btn-live">🚀 Migration LIVE</button>
                <button class="btn btn-secondary" onclick="saveMappingOnly()">💾 Sauvegarder le mapping</button>
            </div>
        </div>

        <div id="mig-progress-card" class="card" style="display:none">
            <h2><span class="icon">⏳</span> Progression</h2>
            <div class="progress-container">
                <div class="progress-bar" id="mig-bar" style="width:0%"></div>
                <div class="progress-text" id="mig-bar-text">0%</div>
            </div>
            <div class="log-terminal" id="mig-log"></div>
        </div>
    </div>

    <!-- ═══════════ RESULTS TAB ═══════════ -->
    <div id="tab-results" class="tab-content">
        <div id="results-empty" class="empty-state">
            <div class="icon">📊</div>
            <p>Lancez une migration pour voir les résultats ici.</p>
        </div>
        <div id="results-content" style="display:none">
            <div class="card">
                <h2><span class="icon">✅</span> Résultats de la migration</h2>
                <div class="stats-bar" id="results-stats"></div>
            </div>
            <div class="card">
                <h2><span class="icon">📋</span> Journal complet</h2>
                <div class="log-terminal" id="results-log"></div>
            </div>
        </div>
    </div>
</div>

<!-- Detail side panel -->
<div class="detail-panel" id="detail-panel">
    <button class="detail-close" onclick="closeDetail()">✕</button>
    <h3 id="detail-title"></h3>
    <dl class="detail-meta" id="detail-meta"></dl>
    <div class="detail-preview" id="detail-preview"></div>
    <div class="detail-thumbs" id="detail-thumbs"></div>
</div>

<!-- Toasts -->
<div class="toast-container" id="toasts"></div>

<!-- Bulk action modal -->
<div class="modal-overlay" id="bulk-modal" onclick="if(event.target===this)closeBulkModal()">
    <div class="modal-box">
        <h3 id="modal-title">Configuration</h3>
        <div id="modal-body"></div>
        <div class="separator"></div>
        <div class="btn-group" style="justify-content:flex-end">
            <button class="btn btn-secondary" onclick="closeBulkModal()">Annuler</button>
            <button class="btn btn-primary" id="modal-confirm" onclick="confirmBulkModal()">Appliquer</button>
        </div>
    </div>
</div>

<script>
// ── State ────────────────────────────────────────────────────
let pages = [];
let currentFilter = 'all';
let migrationPollInterval = null;

// ── API helpers ──────────────────────────────────────────────
async function api(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(path, opts);
    return resp.json();
}

// ── Toast notifications ──────────────────────────────────────
function toast(msg, type = 'info') {
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    document.getElementById('toasts').appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

// ── Tabs ─────────────────────────────────────────────────────
function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`[onclick="switchTab('${name}')"]`).classList.add('active');
    document.getElementById('tab-' + name).classList.add('active');

    if (name === 'migration') updateMigStats();
    if (name === 'scanner' && !document.getElementById('scan-url').value) {
        const wpUrl = document.getElementById('cfg-wp-url').value;
        if (wpUrl) document.getElementById('scan-url').value = wpUrl;
    }
}

// ── Config ───────────────────────────────────────────────────
async function loadConfig() {
    const cfg = await api('GET', '/api/config');
    if (cfg.wordpress) {
        document.getElementById('cfg-wp-url').value = cfg.wordpress.url || '';
        document.getElementById('cfg-wp-user').value = cfg.wordpress.username || '';
        document.getElementById('cfg-wp-pass').value = cfg.wordpress.app_password || '';
    }
    if (cfg.prestashop) {
        document.getElementById('cfg-ps-url').value = cfg.prestashop.url || '';
        document.getElementById('cfg-ps-key').value = cfg.prestashop.api_key || '';
        document.getElementById('cfg-ps-lang').value = cfg.prestashop.default_lang_id || 1;
        document.getElementById('cfg-ps-cat').value = cfg.prestashop.cms_category_id || 1;
    }
    if (cfg.migration) {
        document.getElementById('cfg-dry-run').checked = cfg.migration.dry_run !== false;
        document.getElementById('cfg-images').checked = cfg.migration.download_images !== false;
        document.getElementById('cfg-img-dir').value = cfg.migration.image_target_dir || '';
        document.getElementById('cfg-ftp-host').value = cfg.migration.ftp_host || '';
        document.getElementById('cfg-ftp-user').value = cfg.migration.ftp_user || '';
        document.getElementById('cfg-ftp-pass').value = cfg.migration.ftp_password || '';
        document.getElementById('cfg-ftp-path').value = cfg.migration.ftp_remote_path || '/img/cms';
    }
}

async function saveConfig() {
    const cfg = {
        wordpress: {
            url: document.getElementById('cfg-wp-url').value,
            username: document.getElementById('cfg-wp-user').value,
            app_password: document.getElementById('cfg-wp-pass').value,
        },
        prestashop: {
            url: document.getElementById('cfg-ps-url').value,
            api_key: document.getElementById('cfg-ps-key').value,
            default_lang_id: parseInt(document.getElementById('cfg-ps-lang').value) || 1,
            cms_category_id: parseInt(document.getElementById('cfg-ps-cat').value) || 1,
        },
        migration: {
            dry_run: document.getElementById('cfg-dry-run').checked,
            download_images: document.getElementById('cfg-images').checked,
            image_target_dir: document.getElementById('cfg-img-dir').value,
            ftp_host: document.getElementById('cfg-ftp-host').value,
            ftp_user: document.getElementById('cfg-ftp-user').value,
            ftp_password: document.getElementById('cfg-ftp-pass').value,
            ftp_remote_path: document.getElementById('cfg-ftp-path').value,
            log_file: 'migration.log',
        }
    };
    await api('POST', '/api/config', cfg);
    toast('Configuration sauvegardée ✅', 'success');
}

async function testConnection() {
    document.getElementById('connection-status').style.display = 'block';
    document.getElementById('wp-status-dot').className = 'status-dot pending';
    document.getElementById('ps-status-dot').className = 'status-dot pending';
    document.getElementById('wp-status-text').textContent = 'test...';
    document.getElementById('ps-status-text').textContent = 'test...';

    const result = await api('POST', '/api/test-connection', {
        wp_url: document.getElementById('cfg-wp-url').value,
        ps_url: document.getElementById('cfg-ps-url').value,
        ps_key: document.getElementById('cfg-ps-key').value,
    });

    document.getElementById('wp-status-dot').className = 'status-dot ' + (result.wordpress ? 'ok' : 'fail');
    document.getElementById('wp-status-text').textContent = result.wordpress ? '✅ Connecté' : '❌ ' + (result.wp_error || 'Échec');
    document.getElementById('ps-status-dot').className = 'status-dot ' + (result.prestashop ? 'ok' : 'fail');
    document.getElementById('ps-status-text').textContent = result.prestashop ? '✅ Connecté' : '❌ ' + (result.ps_error || 'Échec');
}

// ── Scanner ──────────────────────────────────────────────────
async function scanWordPress() {
    const url = document.getElementById('scan-url').value.trim();
    if (!url) { toast('URL WordPress requise', 'error'); return; }

    const btn = document.getElementById('btn-scan');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Scan en cours...';

    try {
        const result = await api('POST', '/api/scan', { url });
        if (result.error) { toast(result.error, 'error'); return; }

        toast(`${result.total} pages trouvées`, 'success');
        await loadPages();
        document.getElementById('scan-results').style.display = 'block';
        document.getElementById('scan-empty').style.display = 'none';
    } catch (e) {
        toast('Erreur: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '🔍 Scanner';
    }
}

async function loadPages() {
    pages = await api('GET', '/api/pages');
    updateStats();
    renderPages();
}

function updateStats() {
    const cms = pages.filter(p => p.target === 'cms').length;
    const product = pages.filter(p => p.target === 'product').length;
    const skip = pages.filter(p => p.target === 'skip').length;
    const pageCount = pages.filter(p => p.wp_type === 'page').length;
    const postCount = pages.filter(p => p.wp_type === 'post').length;

    document.getElementById('stat-total').textContent = pages.length;
    document.getElementById('stat-pages').textContent = pageCount;
    document.getElementById('stat-posts').textContent = postCount;
    document.getElementById('stat-cms').textContent = cms;
    document.getElementById('stat-product').textContent = product;
    document.getElementById('stat-skip').textContent = skip;
}

function renderPages() {
    const tbody = document.getElementById('pages-body');
    const search = document.getElementById('search-pages').value.toLowerCase();

    const filtered = pages.filter(p => {
        if (currentFilter === 'type-page' && p.wp_type !== 'page') return false;
        if (currentFilter === 'type-post' && p.wp_type !== 'post') return false;
        if (['cms','product','skip'].includes(currentFilter) && p.target !== currentFilter) return false;
        if (search && !p.slug.includes(search) && !p.title.toLowerCase().includes(search)) return false;
        return true;
    });

    tbody.innerHTML = filtered.map((p, i) => {
        const selectClass = 'target-select target-' + p.target;
        const typeBadge = p.wp_type === 'post'
            ? '<span class="type-badge type-post">Article</span>'
            : '<span class="type-badge type-page">Page</span>';
        const cats = (p.category_names || []).map(c => `<span class="category-tag">${escHtml(c)}</span>`).join('');
        return `<tr onclick="showDetail('${p.slug}')" data-slug="${p.slug}">
            <td class="col-check" onclick="event.stopPropagation()">
                <input type="checkbox" class="custom-check page-check" data-slug="${p.slug}" />
            </td>
            <td class="col-target" onclick="event.stopPropagation()">
                <select class="${selectClass}" onchange="changeTarget('${p.slug}', this.value, this)"
                    data-slug="${p.slug}">
                    <option value="cms" ${p.target==='cms'?'selected':''}>📄 CMS</option>
                    <option value="product" ${p.target==='product'?'selected':''}>🏷️ Produit</option>
                    <option value="skip" ${p.target==='skip'?'selected':''}>⏭️ Ignorer</option>
                </select>
            </td>
            <td class="col-slug"><span class="slug-text">${p.slug}</span></td>
            <td class="col-title">${escHtml(p.title)}${cats}</td>
            <td class="col-size">${typeBadge}</td>
            <td class="col-size">${p.content_size}</td>
            <td class="col-img">${p.image_count}</td>
            <td class="col-seo">${p.has_seo ? '✅' : '❌'}</td>
        </tr>`;
    }).join('');
}

function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

async function changeTarget(slug, target, selectEl) {
    await api('POST', '/api/pages/route', { slug, target });
    const p = pages.find(x => x.slug === slug);
    if (p) p.target = target;
    selectEl.className = 'target-select target-' + target;
    updateStats();
    toast(`${slug} → ${targetLabel(target)}`, 'success');
}

function filterPages() { renderPages(); }
function setFilter(f, btn) {
    currentFilter = f;
    document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderPages();
}

function toggleAll(el) {
    document.querySelectorAll('.page-check').forEach(cb => cb.checked = el.checked);
}

async function bulkAction(target) {
    const slugs = Array.from(document.querySelectorAll('.page-check:checked'))
        .map(cb => cb.dataset.slug);
    if (!slugs.length) { toast('Sélectionnez des pages d\\'abord', 'error'); return; }
    openBulkModal(target, slugs);
}

let pendingBulk = { target: '', slugs: [] };

function openBulkModal(target, slugs) {
    pendingBulk = { target, slugs };
    const modal = document.getElementById('bulk-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    const count = slugs.length;

    if (target === 'cms') {
        title.innerHTML = `📄 ${count} élément(s) → CMS`;
        body.innerHTML = `
            <p style="font-size:0.9em;color:var(--text-dim);margin-bottom:12px">
                Choisissez la catégorie CMS de destination dans PrestaShop.
            </p>
            <div class="detail-edit-row">
                <label>Catégorie CMS (ID)</label>
                <input type="number" id="modal-cms-cat" value="1" min="1" placeholder="ID catégorie" />
            </div>
        `;
    } else if (target === 'product') {
        title.innerHTML = `🏷️ ${count} élément(s) → Produit`;
        body.innerHTML = `
            <p style="font-size:0.9em;color:var(--text-dim);margin-bottom:12px">
                Comment faire correspondre ces pages aux produits PrestaShop ?
            </p>
            <div class="detail-edit-row">
                <label>Mode de match</label>
                <select id="modal-match-by">
                    <option value="name">Par nom du produit</option>
                    <option value="reference">Par référence produit</option>
                </select>
            </div>
        `;
    } else {
        title.innerHTML = `⏭️ ${count} élément(s) → Ignorer`;
        body.innerHTML = `
            <p style="font-size:0.9em;color:var(--text-dim)">
                Ces ${count} éléments seront ignorés lors de la migration.
            </p>
        `;
    }
    modal.classList.add('show');
}

function closeBulkModal() {
    document.getElementById('bulk-modal').classList.remove('show');
}

async function confirmBulkModal() {
    const { target, slugs } = pendingBulk;
    let options = {};

    if (target === 'cms') {
        const catId = parseInt(document.getElementById('modal-cms-cat').value) || 1;
        options = { cms_category_id: catId };
    } else if (target === 'product') {
        options = { match_by: document.getElementById('modal-match-by').value };
    }

    await api('POST', '/api/pages/bulk-route', { slugs, target, options });
    slugs.forEach(slug => {
        const p = pages.find(x => x.slug === slug);
        if (p) {
            p.target = target;
            p.options = { ...(p.options || {}), ...options };
        }
    });
    updateStats();
    renderPages();
    closeBulkModal();
    toast(`${slugs.length} éléments → ${targetLabel(target)}`, 'success');
}

async function autoCateg() {
    const result = await api('POST', '/api/pages/auto-categorize');
    await loadPages();
    toast(`🤖 Auto: ${result.cms || 0} CMS, ${result.product || 0} Produits, ${result.skip || 0} Ignorées`, 'success');
}

// ── Detail panel ─────────────────────────────────────────────
function showDetail(slug) {
    const p = pages.find(x => x.slug === slug);
    if (!p) return;

    // Remove previous edit section if any
    const oldEdit = document.getElementById('detail-edit-section');
    if (oldEdit) oldEdit.remove();

    document.getElementById('detail-title').textContent = p.title;
    document.getElementById('detail-meta').innerHTML = `
        <dt>Slug</dt><dd><code>${p.slug}</code></dd>
        <dt>Type</dt><dd>${p.wp_type === 'post' ? '📝 Article' : '📃 Page'}</dd>
        <dt>Destination</dt><dd>${targetLabel(p.target)}</dd>
        <dt>WP ID</dt><dd>${p.wp_id}</dd>
        ${(p.category_names || []).length ? '<dt>Catégories</dt><dd>' + p.category_names.join(', ') + '</dd>' : ''}
        <dt>Taille</dt><dd>${p.content_size}</dd>
        <dt>Images</dt><dd>${p.image_count}</dd>
        <dt>SEO</dt><dd>${p.has_seo ? '✅ Oui' : '❌ Non'}</dd>
        <dt>Meta Title</dt><dd>${escHtml(p.meta_title || 'N/A')}</dd>
        <dt>Meta Desc</dt><dd>${escHtml(p.meta_description || 'N/A')}</dd>
        <dt>Modifié</dt><dd>${p.modified || 'N/A'}</dd>
        ${p.warnings.length ? '<dt>Alertes</dt><dd>⚠️ ' + p.warnings.join(', ') + '</dd>' : ''}
    `;

    // Editable options section
    const opts = p.options || {};
    let editHtml = '<div class="detail-edit-group">';
    editHtml += '<h4>⚙️ Options de destination</h4>';

    editHtml += `
        <div class="detail-edit-row">
            <label>Destination</label>
            <select id="detail-target" onchange="detailChangeTarget('${p.slug}', this.value)">
                <option value="cms" ${p.target==='cms'?'selected':''}>📄 Page CMS</option>
                <option value="product" ${p.target==='product'?'selected':''}>🏷️ Produit</option>
                <option value="skip" ${p.target==='skip'?'selected':''}>⏭️ Ignorer</option>
            </select>
        </div>
    `;

    if (p.target === 'cms') {
        editHtml += `
            <div class="detail-edit-row">
                <label>Catégorie CMS</label>
                <input type="number" id="detail-cms-cat" value="${opts.cms_category_id || ''}" min="1"
                    placeholder="ID (défaut: config)" />
            </div>
        `;
    } else if (p.target === 'product') {
        editHtml += `
            <div class="detail-edit-row">
                <label>Produit ID</label>
                <input type="number" id="detail-product-id" value="${opts.product_id || ''}" min="1"
                    placeholder="ID direct (optionnel)" />
            </div>
            <div class="detail-edit-row">
                <label>Référence</label>
                <input type="text" id="detail-product-ref" value="${opts.product_reference || ''}"
                    placeholder="REF produit (optionnel)" />
            </div>
            <div class="detail-edit-row">
                <label>Mode match</label>
                <select id="detail-match-by">
                    <option value="name" ${(opts.match_by||'name')==='name'?'selected':''}>Par nom</option>
                    <option value="reference" ${opts.match_by==='reference'?'selected':''}>Par référence</option>
                </select>
            </div>
        `;
    }

    editHtml += `
        <div style="margin-top:10px">
            <button class="btn btn-sm btn-primary" onclick="saveDetailOptions('${p.slug}')">Sauvegarder</button>
        </div>
    </div>`;

    // Insert after meta
    document.getElementById('detail-meta').insertAdjacentHTML('afterend',
        '<div id="detail-edit-section">' + editHtml + '</div>');
    document.getElementById('detail-preview').textContent = p.content_preview || '(vide)';
    document.getElementById('detail-thumbs').innerHTML = (p.image_urls || [])
        .map(url => `<img src="${url}" onerror="this.style.display='none'" loading="lazy">`).join('');

    document.getElementById('detail-panel').classList.add('open');
}

function closeDetail() {
    document.getElementById('detail-panel').classList.remove('open');
}

function targetLabel(t) {
    return { cms: '📄 Page CMS', product: '🏷️ Produit', skip: '⏭️ Ignoré' }[t] || t;
}

async function detailChangeTarget(slug, target) {
    await api('POST', '/api/pages/route', { slug, target });
    const p = pages.find(x => x.slug === slug);
    if (p) p.target = target;
    updateStats();
    renderPages();
    // Re-open detail to refresh the options section
    showDetail(slug);
}

async function saveDetailOptions(slug) {
    const p = pages.find(x => x.slug === slug);
    if (!p) return;
    let options = {};

    if (p.target === 'cms') {
        const catEl = document.getElementById('detail-cms-cat');
        if (catEl && catEl.value) options.cms_category_id = parseInt(catEl.value);
    } else if (p.target === 'product') {
        const pidEl = document.getElementById('detail-product-id');
        const refEl = document.getElementById('detail-product-ref');
        const matchEl = document.getElementById('detail-match-by');
        if (pidEl && pidEl.value) options.product_id = parseInt(pidEl.value);
        if (refEl && refEl.value) options.product_reference = refEl.value;
        if (matchEl) options.match_by = matchEl.value;
    }

    await api('POST', '/api/pages/options', { slug, options });
    p.options = { ...(p.options || {}), ...options };
    toast('Options sauvegardées pour ' + p.title, 'success');
}

// ── Migration ────────────────────────────────────────────────
function updateMigStats() {
    const cms = pages.filter(p => p.target === 'cms').length;
    const product = pages.filter(p => p.target === 'product').length;
    const skip = pages.filter(p => p.target === 'skip').length;
    document.getElementById('mig-cms').textContent = cms;
    document.getElementById('mig-product').textContent = product;
    document.getElementById('mig-skip').textContent = skip;
}

async function startMigration(dryRun) {
    if (!pages.length) { toast('Scannez d\\'abord les pages WordPress', 'error'); return; }

    if (!dryRun && !confirm('⚠️ Lancer la migration LIVE ?\\nCela modifiera votre boutique PrestaShop.')) return;

    await saveConfig();

    document.getElementById('mig-progress-card').style.display = 'block';
    document.getElementById('btn-dry').disabled = true;
    document.getElementById('btn-live').disabled = true;

    const result = await api('POST', '/api/migrate', { dry_run: dryRun });
    if (result.error) {
        toast(result.error, 'error');
        document.getElementById('btn-dry').disabled = false;
        document.getElementById('btn-live').disabled = false;
        document.getElementById('mig-progress-card').style.display = 'none';
        return;
    }

    toast(dryRun ? '🔍 Dry run lancé' : '🚀 Migration lancée', 'info');
    pollMigrationStatus();
}

function pollMigrationStatus() {
    if (migrationPollInterval) clearInterval(migrationPollInterval);
    migrationPollInterval = setInterval(async () => {
        const data = await api('GET', '/api/migrate/status');
        const prog = data.progress;

        // Update progress bar
        const pct = prog.total > 0 ? Math.round((prog.current / prog.total) * 100) : 0;
        document.getElementById('mig-bar').style.width = pct + '%';
        document.getElementById('mig-bar-text').textContent = `${prog.current}/${prog.total} (${pct}%)`;

        // Update log
        const logEl = document.getElementById('mig-log');
        logEl.innerHTML = data.log.map(line => {
            let cls = '';
            if (line.includes('✅')) cls = 'log-success';
            else if (line.includes('❌')) cls = 'log-error';
            else if (line.includes('⚠️')) cls = 'log-warning';
            else if (line.includes('━') || line.includes('═')) cls = 'log-info';
            return `<div class="${cls}">${escHtml(line)}</div>`;
        }).join('');
        logEl.scrollTop = logEl.scrollHeight;

        if (!data.running) {
            clearInterval(migrationPollInterval);
            document.getElementById('btn-dry').disabled = false;
            document.getElementById('btn-live').disabled = false;

            if (prog.status === 'done') {
                toast('✅ Migration terminée !', 'success');
                showResults(data, prog.stats);
            } else if (prog.status === 'error') {
                toast('❌ Erreur: ' + (prog.error || ''), 'error');
            }
        }
    }, 1000);
}

function showResults(data, stats) {
    document.getElementById('results-empty').style.display = 'none';
    document.getElementById('results-content').style.display = 'block';

    const statsEl = document.getElementById('results-stats');
    if (stats) {
        statsEl.innerHTML = `
            <div class="stat-box stat-cms"><div class="stat-value">${stats.cms_migrated || 0}</div><div class="stat-label">CMS Migrées</div></div>
            <div class="stat-box stat-product"><div class="stat-value">${stats.product_updated || 0}</div><div class="stat-label">Produits MAJ</div></div>
            <div class="stat-box stat-skip"><div class="stat-value">${stats.skipped || 0}</div><div class="stat-label">Ignorées</div></div>
            <div class="stat-box"><div class="stat-value" style="color:var(--red)">${stats.failed || 0}</div><div class="stat-label">Échecs</div></div>
            <div class="stat-box"><div class="stat-value" style="color:var(--orange)">${stats.images || 0}</div><div class="stat-label">Images</div></div>
        `;
    }

    document.getElementById('results-log').innerHTML = data.log
        .map(line => {
            let cls = '';
            if (line.includes('✅')) cls = 'log-success';
            else if (line.includes('❌')) cls = 'log-error';
            else if (line.includes('⚠️')) cls = 'log-warning';
            return `<div class="${cls}">${escHtml(line)}</div>`;
        }).join('');

    switchTab('results');
}

async function saveMappingOnly() {
    await saveConfig();
    const result = await api('POST', '/api/save-mapping');
    toast('Mapping sauvegardé dans config.yaml ✅', 'success');
}

// ── Keyboard shortcuts ───────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDetail();
});

// ── Init ─────────────────────────────────────────────────────
loadConfig();
</script>
</body>
</html>'''
