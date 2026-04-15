import air

BLUEPRINT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

/* ── Dark mode (default) ── */
:root {
    --bg-deep: #020617;
    --bg-surface: #0f172a;
    --bg-card: #1e293b;
    --bg-elevated: #334155;
    --border: #334155;
    --border-light: #475569;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent: #f59e0b;
    --accent-dim: #d97706;
    --accent-glow: rgba(245, 158, 11, 0.15);
    --cyan: #06b6d4;
    --cyan-dim: #0891b2;
    --success: #10b981;
    --danger: #f43f5e;
    --warning: #f59e0b;
    --radius: 3px;
    --radius-lg: 6px;
    --grid-color: rgba(59, 130, 246, 0.04);
    --grid-color-major: rgba(59, 130, 246, 0.08);
    --card-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
    --noise-opacity: 0.03;
}

/* ── Light mode ── */
:root.light-mode {
    --bg-deep: #f8fafc;
    --bg-surface: #ffffff;
    --bg-card: #ffffff;
    --bg-elevated: #f1f5f9;
    --border: #e2e8f0;
    --border-light: #cbd5e1;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --accent: #d97706;
    --accent-dim: #b45309;
    --accent-glow: rgba(217, 119, 6, 0.1);
    --cyan: #0891b2;
    --cyan-dim: #0e7490;
    --success: #059669;
    --danger: #e11d48;
    --warning: #d97706;
    --grid-color: rgba(59, 130, 246, 0.06);
    --grid-color-major: rgba(59, 130, 246, 0.12);
    --card-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    --noise-opacity: 0.015;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'JetBrains Mono', monospace;
    background-color: var(--bg-deep);
    color: var(--text-primary);
    line-height: 1.6;
    font-size: 14px;
    font-weight: 400;
    min-height: 100vh;
    transition: background-color 0.3s ease, color 0.3s ease;
}

/* Blueprint grid background */
body::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image:
        linear-gradient(var(--grid-color) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid-color) 1px, transparent 1px),
        linear-gradient(var(--grid-color-major) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid-color-major) 1px, transparent 1px);
    background-size: 20px 20px, 20px 20px, 100px 100px, 100px 100px;
    pointer-events: none;
    z-index: 0;
}

/* Noise texture overlay */
body::after {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    opacity: var(--noise-opacity);
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 0;
}

.container {
    max-width: 1280px;
    margin: 0 auto;
    padding: 24px 32px 48px;
    position: relative;
    z-index: 1;
}

.main-content { position: relative; }

/* ── Theme Toggle ── */
.theme-toggle {
    position: fixed;
    top: 16px;
    right: 24px;
    z-index: 10000;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 8px 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    transition: all 0.2s;
    user-select: none;
}

.theme-toggle:hover {
    border-color: var(--accent);
    color: var(--accent);
}

.theme-toggle .icon-sun,
.theme-toggle .icon-moon {
    width: 16px;
    height: 16px;
    display: inline-block;
    background-color: currentColor;
    -webkit-mask-size: contain;
    -webkit-mask-repeat: no-repeat;
    -webkit-mask-position: center;
    mask-size: contain;
    mask-repeat: no-repeat;
    mask-position: center;
}

.theme-toggle .icon-sun {
    -webkit-mask-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41L5.99 4.58zm12.37 12.37a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0a.996.996 0 000-1.41l-1.06-1.06zm1.06-10.96a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06zM7.05 18.36a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06z"/></svg>');
    mask-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41L5.99 4.58zm12.37 12.37a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0a.996.996 0 000-1.41l-1.06-1.06zm1.06-10.96a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06zM7.05 18.36a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06z"/></svg>');
}

.theme-toggle .icon-moon {
    -webkit-mask-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z"/></svg>');
    mask-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z"/></svg>');
}

/* ── Typography ── */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Bebas Neue', sans-serif;
    font-weight: 400;
    letter-spacing: 0.06em;
    line-height: 1.05;
}

h1 { font-size: 52px; color: var(--text-primary); }
h2 { font-size: 32px; color: var(--accent); margin-bottom: 16px; }
h3 { font-size: 22px; color: var(--cyan); margin-bottom: 12px; }
h4 { font-size: 18px; color: var(--text-primary); margin-bottom: 8px; }

p.subtitle {
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: var(--text-muted);
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin: 0;
}

/* ── Header ── */
.module-header {
    padding: 64px 0 24px;
    margin-bottom: 32px;
    border-bottom: 1px solid var(--border);
    position: relative;
    padding-left: 0;
}

.module-header::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    width: 60px;
    height: 2px;
    background: var(--accent);
}

.module-header h1 { margin-bottom: 4px; }

.back-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    text-decoration: none;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    transition: color 0.2s;
    margin-bottom: 16px;
}

.back-link::before {
    content: '←';
    font-size: 14px;
    color: var(--accent);
}

.back-link:hover { color: var(--accent); }

/* Badge-style status indicators for DCR and Pass/Fail */
.status-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-family: 'Space Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #ffffff;
    line-height: 1.4;
    word-break: break-word;
}
.status-badge.pass {
    background: linear-gradient(135deg, #16A34A, #15803D);
    box-shadow: 0 2px 8px rgba(22, 163, 74, 0.35);
}
.status-badge.fail {
    background: linear-gradient(135deg, #DC2626, #B91C1C);
    box-shadow: 0 2px 8px rgba(220, 38, 38, 0.35);
}
.status-badge.dcr {
    background: linear-gradient(135deg, #2563EB, #1D4ED8);
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
}
.status-badge.dcr-ok {
    background: linear-gradient(135deg, #16A34A, #15803D);
    box-shadow: 0 2px 8px rgba(22, 163, 74, 0.35);
}
.status-badge.dcr-warn {
    background: linear-gradient(135deg, #D97706, #B45309);
    box-shadow: 0 2px 8px rgba(217, 119, 6, 0.35);
}

/* Hero header for dashboard */
.hero-header {
    text-align: center;
    padding: 80px 20px 48px;
    margin-bottom: 16px;
}

.hero-header h1 {
    font-size: 64px;
    margin-bottom: 12px;
    letter-spacing: 0.04em;
}

.hero-header .subtitle {
    font-size: 14px;
    max-width: 500px;
    margin: 0 auto;
}

@media (max-width: 900px) {
    .container { padding: 16px; }
    h1 { font-size: 36px; }
    .module-header h1 { font-size: 36px; }
    .module-header { padding: 56px 0 24px; }
    .hero-header h1 { font-size: 42px; }
    .hero-header { padding: 60px 16px 32px; }
    .theme-toggle { top: 12px; right: 12px; padding: 6px 10px; font-size: 10px; }
}

/* ── Cards ── */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 24px;
    position: relative;
    box-shadow: var(--card-shadow);
}

/* Corner marks - technical drawing style */
.card::before, .card::after {
    content: '';
    position: absolute;
    width: 10px;
    height: 10px;
    border-color: var(--accent);
    border-style: solid;
    opacity: 0.6;
    pointer-events: none;
}

.card::before {
    top: -1px;
    left: -1px;
    border-width: 1px 0 0 1px;
}

.card::after {
    bottom: -1px;
    right: -1px;
    border-width: 0 1px 1px 0;
}

/* ── Grid layouts ── */
.grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
}

.grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
}

@media (max-width: 768px) {
    .grid-2, .grid-3 { grid-template-columns: 1fr; }
}

/* ── Section boxes ── */
.section-box {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
}

/* ── Forms ── */
.form-group { margin-bottom: 16px; width: 100%; }

label {
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    color: var(--cyan);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    display: block;
    margin-bottom: 6px;
}

input[type="number"],
input[type="text"],
input[type="date"],
select {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--bg-surface);
    color: var(--text-primary);
    width: 100%;
    box-sizing: border-box;
    transition: border-color 0.2s, box-shadow 0.2s, background-color 0.3s;
}

input[type="number"]:focus,
input[type="text"]:focus,
input[type="date"]:focus,
select:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-glow);
}

/* ── Buttons ── */
button, a.button {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 18px;
    letter-spacing: 0.12em;
    background: var(--accent);
    color: var(--bg-deep);
    padding: 12px 32px;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
    display: inline-block;
    text-decoration: none;
    text-align: center;
    transition: all 0.2s;
    font-weight: 400;
}

button:hover, a.button:hover {
    background: var(--accent-dim);
    transform: translateY(-1px);
    box-shadow: 0 4px 16px var(--accent-glow);
}

button:active, a.button:active {
    transform: translateY(0);
}

a.button.secondary {
    background: transparent;
    color: var(--accent);
    border: 1px solid var(--accent);
}

a.button.secondary:hover {
    background: var(--accent-glow);
    box-shadow: none;
}

/* ── Lists ── */
ul {
    list-style: none;
    padding: 0;
    margin: 8px 0 0;
}

li {
    margin-bottom: 4px;
    font-size: 13px;
    padding: 8px 12px;
    background: var(--bg-surface);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
}

.data-value {
    font-family: 'Space Mono', monospace;
    font-weight: 700;
    color: var(--accent);
    font-size: 14px;
    text-align: right;
    flex-shrink: 1;
    min-width: 0;
    word-break: break-word;
    margin-left: 8px;
}

.notes-list li {
    display: block;
    background: var(--accent-glow);
    border-color: rgba(245, 158, 11, 0.15);
    color: var(--text-secondary);
}

/* ── Tables ── */
table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 16px;
    font-size: 13px;
    overflow-x: auto;
    display: block;
}

table thead, table tbody { display: table; width: 100%; table-layout: fixed; }

th, td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    text-align: left;
    word-break: break-word;
}

th {
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    color: var(--cyan);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    background: var(--bg-surface);
}

/* ── Metric cards ── */
.metric-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
}

.metric-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent);
}

.metric-card.blue::before { background: var(--cyan); }
.metric-card.green::before { background: var(--success); }
.metric-card.concrete::before { background: var(--accent); }
.metric-card.formwork::before { background: var(--cyan); }
.metric-card.rebar::before { background: var(--success); }

.metric-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 36px;
    color: var(--text-primary);
    margin: 4px 0;
    letter-spacing: 0.02em;
}

.metric-label {
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
}

/* ── Dashboard module cards ── */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 20px;
    margin-top: 32px;
    align-items: stretch;
}

.module-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    text-decoration: none;
    color: var(--text-primary);
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 260px;
}

.module-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent);
    transform: scaleX(0);
    transform-origin: left;
    transition: transform 0.3s ease;
}

.module-card::after {
    content: '';
    position: absolute;
    bottom: -1px;
    right: -1px;
    width: 10px;
    height: 10px;
    border-color: var(--accent);
    border-style: solid;
    border-width: 0 1px 1px 0;
    opacity: 0;
    transition: opacity 0.25s ease;
}

.module-card:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.module-card:hover::before {
    transform: scaleX(1);
}

.module-card:hover::after {
    opacity: 0.6;
}

.module-card h3 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 26px;
    color: var(--text-primary);
    margin-bottom: 8px;
    letter-spacing: 0.06em;
}

.module-card p {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.5;
}

.module-card .version-tag {
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    color: var(--accent);
    background: var(--accent-glow);
    border: 1px solid rgba(245, 158, 11, 0.2);
    border-radius: var(--radius);
    padding: 2px 8px;
    margin-top: 12px;
    letter-spacing: 0.1em;
}

/* ── Contour selector buttons ── */
.contour-btn {
    transition: all 0.15s !important;
}

.contour-btn:hover {
    background: var(--accent) !important;
    color: var(--bg-deep) !important;
    border-color: var(--accent) !important;
}

/* ── Footer ── */
.site-footer {
    text-align: center;
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 12px;
}

.social-links {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 12px;
}

.social-link {
    color: var(--text-muted);
    transition: color 0.2s;
    display: flex;
    align-items: center;
}

.social-link:hover { color: var(--accent); }

.icon-github {
    display: inline-block;
    width: 20px;
    height: 20px;
    background-color: currentColor;
    -webkit-mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>') no-repeat center;
    mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>') no-repeat center;
}

.icon-facebook {
    display: inline-block;
    width: 20px;
    height: 20px;
    background-color: currentColor;
    -webkit-mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M9 8h-3v4h3v12h5v-12h3.642l.358-4h-4v-1.667c0-.955.192-1.333 1.115-1.333h2.885v-5h-3.808c-3.596 0-5.192 1.583-5.192 4.615v3.385z"/></svg>') no-repeat center;
    mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M9 8h-3v4h3v12h5v-12h3.642l.358-4h-4v-1.667c0-.955.192-1.333 1.115-1.333h2.885v-5h-3.808c-3.596 0-5.192 1.583-5.192 4.615v3.385z"/></svg>') no-repeat center;
}

.icon-linkedin {
    display: inline-block;
    width: 20px;
    height: 20px;
    background-color: currentColor;
    -webkit-mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M4.98 3.5c0 1.381-1.11 2.5-2.48 2.5s-2.48-1.119-2.48-2.5c0-1.38 1.11-2.5 2.48-2.5s2.48 1.12 2.48 2.5zm.02 4.5h-5v16h5v-16zm7.982 0h-4.968v16h4.969v-8.399c0-4.67 6.029-5.052 6.029 0v8.399h4.988v-10.131c0-7.88-8.922-7.593-11.018-3.714v-2.155z"/></svg>') no-repeat center;
    mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M4.98 3.5c0 1.381-1.11 2.5-2.48 2.5s-2.48-1.119-2.48-2.5c0-1.38 1.11-2.5 2.48-2.5s2.48 1.12 2.48 2.5zm.02 4.5h-5v16h5v-16zm7.982 0h-4.968v16h4.969v-8.399c0-4.67 6.029-5.052 6.029 0v8.399h4.988v-10.131c0-7.88-8.922-7.593-11.018-3.714v-2.155z"/></svg>') no-repeat center;
}

/* ── Print styles ── */
@media print {
    body {
        background: #fff;
        color: #000;
        padding: 0;
        margin: 0;
    }

    body::before, body::after { display: none; }

    .theme-toggle { display: none !important; }

    .card {
        border: 1px solid #ddd;
        padding: 0;
        margin-bottom: 32px;
        box-shadow: none;
        background: #fff;
    }

    .card::before, .card::after { display: none; }

    .no-print { display: none !important; }

    .metric-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
    }

    .metric-card::before { display: none; }

    h1, h2, h3, h4 { color: #000; }

    .data-value { color: #000; }

    * {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
        color-adjust: exact !important;
    }
}
"""

THEME_TOGGLE_JS = """
(function() {
    const root = document.documentElement;
    const STORAGE_KEY = 'rc-design-theme';
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'light') {
        root.classList.add('light-mode');
    }

    function updateToggle() {
        const isLight = root.classList.contains('light-mode');
        const btn = document.getElementById('themeToggleBtn');
        if (!btn) return;
        const sun = btn.querySelector('.icon-sun');
        const moon = btn.querySelector('.icon-moon');
        const label = btn.querySelector('.theme-label');
        if (sun) sun.style.display = isLight ? 'inline-block' : 'none';
        if (moon) moon.style.display = isLight ? 'none' : 'inline-block';
        if (label) label.textContent = isLight ? 'Light' : 'Dark';
    }

    document.addEventListener('DOMContentLoaded', function() {
        updateToggle();
        const btn = document.getElementById('themeToggleBtn');
        if (btn) {
            btn.addEventListener('click', function() {
                root.classList.toggle('light-mode');
                localStorage.setItem(STORAGE_KEY, root.classList.contains('light-mode') ? 'light' : 'dark');
                updateToggle();
            });
        }
    });
})();
"""


def blueprint_layout(*content, head_extra=None):
    """Wraps all application pages in the Blueprint Design System with light/dark mode."""
    head_items = [
        air.Title("ACI 318M-25 Designer"),
        air.Style(BLUEPRINT_CSS),
        air.Script(THEME_TOGGLE_JS)
    ]
    if head_extra:
        for item in head_extra:
            if isinstance(item, str):
                head_items.append(air.Raw(item))
            else:
                head_items.append(item)

    return air.Html(
        air.Head(*head_items),
        air.Body(
            air.Div(
                air.Div(
                    air.Button(
                        air.Span(class_="icon-sun", style="display:none;"),
                        air.Span(class_="icon-moon"),
                        air.Span(class_="theme-label", style="margin-left: 4px;"),
                        id="themeToggleBtn",
                        class_="theme-toggle no-print",
                    ),
                    style="position: relative;"
                ),
                air.Div(*content, class_="main-content"),
                air.Div(
                    air.P("© 2026 Jaydee Lucero — Python 3.14 — Air Framework", style="margin-bottom: 8px;"),
                    air.Div(
                        air.A(air.Div(class_="icon-github"), href="https://github.com/arisa-chan/rc-design-collection-web", target="_blank", title="Repository", class_="social-link"),
                        air.A(air.Div(class_="icon-facebook"), href="https://www.facebook.com/jaydee.lucero", target="_blank", title="Facebook", class_="social-link"),
                        air.A(air.Div(class_="icon-linkedin"), href="https://www.linkedin.com/in/jaydee-lucero-977070200/", target="_blank", title="LinkedIn", class_="social-link"),
                        air.A(air.Div(class_="icon-github"), href="https://github.com/arisa-chan", target="_blank", title="GitHub", class_="social-link"),
                        class_="social-links"
                    ),
                    class_="site-footer no-print"
                ),
                class_="container"
            )
        )
    )
