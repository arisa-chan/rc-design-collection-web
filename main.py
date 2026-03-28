import air
import beam
import column
from shared import expressive_layout

# Initialize the Air App
app = air.Air()

# Register the Beam module routes directly to our app
beam.setup_beam_routes(app)
column.setup_column_routes(app)

@app.page
def index(request: air.Request):
    """
    Central dashboard for the ACI 318M-25 Structural Suite.
    Designed for infinite scalability as new modules are created.
    """
    return expressive_layout(
        air.Header(
            air.H1("ACI 318M-25 Design Collection"),
            air.P("Design RC members anytime, anywhere.", class_="subtitle"),
            class_="hero-header"
        ),
        air.Main(
            air.Div(
                air.H2("Available Modules"),
                air.Div(
                    # Beam Designer Card (Active)
                    air.Div(
                        air.H3("RC Beam Designer"),
                        air.P("Current release: v1.0", style="margin-bottom: 24px;"),
                        air.A("Launch", href="/beam", class_="button", style="width: 100%; box-sizing: border-box;"),
                        class_="card"
                    ),
                    
                    # Column Designer Card (Placeholder for future)
                    air.Div(
                        air.H3("RC Column Designer"),
                        air.P("Current release: v0.1 (alpha). Please expect bugs, wrong results, and/or missing features. Refinements ongoing.", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Launch", href="/column", class_="button", style="width: 100%; box-sizing: border-box;"),
                        class_="card"
                    ),
                    
                    # Slab Designer Card (Placeholder for future)
                    air.Div(
                        air.H3("RC Slab Designer", style="color: var(--text-muted);"),
                        air.P("Still cooking...", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Coming Soon", href="#", class_="button secondary", style="width: 100%; box-sizing: border-box; pointer-events: none; opacity: 0.5;"),
                        class_="card",
                        style="background: #f9fafb; border-color: #e5e7eb;"
                    ),
                    
                    # Footing Designer Card (Placeholder for future)
                    air.Div(
                        air.H3("RC Isolated Footing Designer", style="color: var(--text-muted);"),
                        air.P("Still cooking...", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Coming Soon", href="#", class_="button secondary", style="width: 100%; box-sizing: border-box; pointer-events: none; opacity: 0.5;"),
                        class_="card",
                        style="background: #f9fafb; border-color: #e5e7eb;"
                    ),
                    
                    class_="grid-2"
                )
            )
        )
    )