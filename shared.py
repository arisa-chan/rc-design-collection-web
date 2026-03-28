import air

EXPRESSIVE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');

:root {
    --primary: #db2777; --secondary: #2563eb; --success: #16A34A;
    --warning: #D97706; --danger: #DC2626; --surface: #FFFFFF;
    --background: #fdf2f8; --text: #111827; --text-muted: #4b5563;
    --radius-md: 12px; --radius-pill: 9999px;
}

body {
    font-family: 'IBM Plex Mono', monospace; background-color: var(--background);
    color: var(--text); margin: 0; padding: 32px; line-height: 1.6; font-size: 16px;
}

h1, h2, h3, h4 { font-weight: 700; margin-top: 0; color: var(--text); }
h1 { font-size: 40px; margin-bottom: 8px; letter-spacing: -1px; }
h2 { font-size: 30px; margin-bottom: 24px; color: var(--primary); }
h3 { font-size: 22px; margin-bottom: 16px; color: var(--secondary); border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;}
h4 { font-size: 18px; margin-bottom: 12px; margin-top: 24px; color: var(--text); }
p.subtitle { font-size: 18px; color: var(--text-muted); margin-bottom: 32px; }

.container { max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; min-height: 95vh; }
.main-content { flex: 1; }

.card {
    background: var(--surface); border-radius: var(--radius-md); padding: 32px;
    box-shadow: 0 10px 40px -10px rgba(219, 39, 119, 0.15); margin-bottom: 32px;
    border: 1px solid rgba(219, 39, 119, 0.1);
}

.grid-2 { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 24px; }
.grid-2 > div { width: calc(50% - 12px); box-sizing: border-box; }
.grid-3 { display: flex; flex-wrap: wrap; justify-content: space-between; }
.grid-3 > div { width: 31%; box-sizing: border-box; margin-bottom: 16px; }

.section-box { background: #f9fafb; padding: 24px; border-radius: 8px; border: 1px solid #e5e7eb; box-sizing: border-box; }
.form-group { margin-bottom: 16px; width: 100%;}
label { font-weight: 600; display: block; margin-bottom: 6px; font-size: 14px; color: var(--secondary); }

input[type="number"], input[type="text"], input[type="date"], select {
    font-family: 'IBM Plex Mono', monospace; font-size: 15px; padding: 10px 14px;
    border: 2px solid #e5e7eb; border-radius: var(--radius-md); background: var(--surface);
    color: var(--text); width: 100%; box-sizing: border-box; transition: all 0.2s ease;
}

button, a.button {
    font-family: 'IBM Plex Mono', monospace; font-size: 16px; font-weight: 700;
    background-color: var(--primary); color: white; padding: 16px 32px;
    border: none; border-radius: var(--radius-pill); cursor: pointer;
    display: inline-block; text-decoration: none; text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
button:hover, a.button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(219, 39, 119, 0.4); }
button:active, a.button:active { transform: translateY(1px); box-shadow: 0 2px 10px rgba(219, 39, 119, 0.3); }

a.button.secondary { background-color: var(--surface); color: var(--secondary); border: 2px solid var(--secondary); }
a.button.secondary:hover { background-color: #eff6ff; box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.2); }

ul { list-style-type: none; padding-left: 0; margin-top: 8px; }
li { margin-bottom: 8px; font-size: 14px; padding: 10px; background: #ffffff; border-radius: 6px; border: 1px solid #f3f4f6; display: flex; justify-content: space-between; align-items: center; }
.data-value { font-weight: 700; color: var(--primary); font-size: 15px; text-align: right;}
.notes-list li { display: block; background: #fffbeb; border-color: #fef3c7; color: #92400e; }

table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; text-align: left; }
th, td { padding: 10px 16px; border-bottom: 1px solid #e5e7eb; }
th { color: var(--secondary); font-weight: 700; background: #eff6ff; text-transform: uppercase; font-size: 12px;}
.metric-card { background: #fdf2f8; border: 2px solid #fbcfe8; padding: 24px; border-radius: 12px; text-align: center; }
.metric-card.blue { background: #eff6ff; border-color: #bfdbfe; }
.metric-card.green { background: #f0fdf4; border-color: #bbf7d0; }
.metric-value { font-size: 32px; font-weight: 700; color: var(--text); margin: 8px 0; }
.metric-label { font-size: 14px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; }

/* ---------------- HEADER TYPOGRAPHY & SPACING ---------------- */
.hero-header { text-align: center; padding: 80px 20px 60px; }
.hero-header h1 { font-size: 56px; letter-spacing: -2px; margin-bottom: 16px; }
.hero-header .subtitle { font-size: 22px; max-width: 700px; margin: 0 auto; line-height: 1.5; }

.module-header { text-align: center; padding: 24px 0 32px; position: relative; border-bottom: 2px dashed #e5e7eb; margin-bottom: 32px; }
.module-header h1 { font-size: 36px; margin-bottom: 8px; }
.module-header .subtitle { margin-bottom: 0; }
.back-link { position: absolute; left: 0; top: 50%; transform: translateY(-50%); font-weight: 600; color: var(--text-muted); text-decoration: none; transition: color 0.2s; display: flex; align-items: center; gap: 8px;}
.back-link:hover { color: var(--primary); }
@media (max-width: 900px) {
    .back-link { position: static; display: inline-block; margin-bottom: 16px; transform: none; }
}

/* ---------------- FOOTER STYLES ---------------- */
.site-footer { text-align: center; margin-top: 48px; padding-top: 32px; padding-bottom: 16px; border-top: 1px solid #e5e7eb; color: var(--text-muted); font-size: 14px; }
.social-links { display: flex; justify-content: center; gap: 24px; margin-top: 16px; }
.social-link { color: var(--text-muted); transition: color 0.2s ease; display: flex; align-items: center; justify-content: center; }
.social-link:hover { color: var(--primary); }

.icon-github { 
    display: inline-block; width: 24px; height: 24px; background-color: currentColor;
    -webkit-mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>') no-repeat center;
    mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>') no-repeat center;
}
.icon-facebook {
    display: inline-block; width: 24px; height: 24px; background-color: currentColor;
    -webkit-mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M9 8h-3v4h3v12h5v-12h3.642l.358-4h-4v-1.667c0-.955.192-1.333 1.115-1.333h2.885v-5h-3.808c-3.596 0-5.192 1.583-5.192 4.615v3.385z"/></svg>') no-repeat center;
    mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M9 8h-3v4h3v12h5v-12h3.642l.358-4h-4v-1.667c0-.955.192-1.333 1.115-1.333h2.885v-5h-3.808c-3.596 0-5.192 1.583-5.192 4.615v3.385z"/></svg>') no-repeat center;
}
.icon-linkedin {
    display: inline-block; width: 24px; height: 24px; background-color: currentColor;
    -webkit-mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M4.98 3.5c0 1.381-1.11 2.5-2.48 2.5s-2.48-1.119-2.48-2.5c0-1.38 1.11-2.5 2.48-2.5s2.48 1.12 2.48 2.5zm.02 4.5h-5v16h5v-16zm7.982 0h-4.968v16h4.969v-8.399c0-4.67 6.029-5.052 6.029 0v8.399h4.988v-10.131c0-7.88-8.922-7.593-11.018-3.714v-2.155z"/></svg>') no-repeat center;
    mask: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M4.98 3.5c0 1.381-1.11 2.5-2.48 2.5s-2.48-1.119-2.48-2.5c0-1.38 1.11-2.5 2.48-2.5s2.48 1.12 2.48 2.5zm.02 4.5h-5v16h5v-16zm7.982 0h-4.968v16h4.969v-8.399c0-4.67 6.029-5.052 6.029 0v8.399h4.988v-10.131c0-7.88-8.922-7.593-11.018-3.714v-2.155z"/></svg>') no-repeat center;
}

@media print {
    body { background: #FFFFFF; padding: 0; margin: 0; }
    .card { border: none; padding: 0; margin-bottom: 40px; page-break-inside: avoid; box-shadow: none; }
    .section-box, .metric-card { page-break-inside: avoid; }
    .no-print { display: none !important; }
    .page-break { page-break-before: always; }
    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; color-adjust: exact !important; }
    
    /* Ensure print headers format nicely */
    .hero-header { padding: 20px 0; }
    .module-header { padding: 20px 0; border-bottom: 2px solid #000;}
}
"""

def expressive_layout(*content):
    """Wraps all application pages in the Expressive Design System, including the site footer."""
    return air.Html(
        air.Head(air.Title("ACI 318M-25 Designer"), air.Style(EXPRESSIVE_CSS)),
        air.Body(
            air.Div(
                air.Div(*content, class_="main-content"),
                air.Div(
                    air.P("(c) 2026 by Jaydee Lucero • written in Python 3.14 • powered by Air web framework", style="margin-bottom: 12px;"),
                    air.Div(
                        air.A(air.Div(class_="icon-github"), href="https://github.com/arisa-chan/rc-design-collection-web", target="_blank", title="Project Repository", class_="social-link"),
                        air.A(air.Div(class_="icon-facebook"), href="https://www.facebook.com/jaydee.lucero", target="_blank", title="Facebook Page", class_="social-link"),
                        air.A(air.Div(class_="icon-linkedin"), href="https://www.linkedin.com/in/jaydee-lucero-977070200/", target="_blank", title="LinkedIn Profile", class_="social-link"),
                        air.A(air.Div(class_="icon-github"), href="https://github.com/arisa-chan", target="_blank", title="GitHub Profile", class_="social-link"),
                        class_="social-links"
                    ),
                    class_="site-footer no-print"
                ),
                class_="container"
            )
        )
    )