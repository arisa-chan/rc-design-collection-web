import air
import beam
import column
import slab
import footing  # <-- Added the new footing import
from shared import expressive_layout

# Initialize the Air App
app = air.Air()

# Register the module routes directly to our app
beam.setup_beam_routes(app)
column.setup_column_routes(app)
slab.setup_slab_routes(app)
footing.setup_footing_routes(app)  # <-- Registered the footing routes here

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
                        air.P("v0.8 beta.", style="margin-bottom: 24px;"),
                        air.A("Launch", href="/beam", class_="button", style="width: 100%; box-sizing: border-box;"),
                        class_="card"
                    ),

                    # Column Designer Card (Active)
                    air.Div(
                        air.H3("RC Column Designer"),
                        air.P("v0.8 beta.", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Launch", href="/column", class_="button", style="width: 100%; box-sizing: border-box;"),
                        class_="card"
                    ),

                    # Slab Designer Card (Active)
                    air.Div(
                        air.H3("RC Slab Designer"),
                        air.P("v0.4 alpha. Expect bugs, wrong results and/or missing features. Refinements ongoing.", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Launch", href="/slab", class_="button", style="width: 100%; box-sizing: border-box;"),
                        class_="card"
                    ),

                    # Footing Designer Card (Now Active!)
                    air.Div(
                        air.H3("RC Isolated Footing Designer"),
                        air.P("v0.1 developer preview. Expect bugs, wrong results and/or missing features. Refinements ongoing.", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Launch", href="/footing", class_="button", style="width: 100%; box-sizing: border-box;"),
                        class_="card"
                    ),

                    class_="grid-2"
                )
            )
        )
    )