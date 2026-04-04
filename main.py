import air
import beam
import column
import slab
import footing
from shared import blueprint_layout

app = air.Air()

beam.setup_beam_routes(app)
column.setup_column_routes(app)
slab.setup_slab_routes(app)
footing.setup_footing_routes(app)

@app.page
def index(request: air.Request):
    return blueprint_layout(
        air.Div(
            air.H1("ACI 318M-25 Design Collection"),
            air.P("Design RC members anytime, anywhere.", class_="subtitle"),
            class_="hero-header"
        ),
        air.Main(
            air.Div(
                air.H2("Available Modules"),
                air.Div(
                    air.Div(
                        air.H3("RC Beam Designer"),
                        air.P("v0.8 beta.", style="margin-bottom: 20px; color: var(--text-secondary);"),
                        air.A("Launch", href="/beam", class_="button"),
                        class_="module-card"
                    ),
                    air.Div(
                        air.H3("RC Column Designer"),
                        air.P("v0.8 beta.", style="color: var(--text-muted); margin-bottom: 20px;"),
                        air.A("Launch", href="/column", class_="button"),
                        class_="module-card"
                    ),
                    air.Div(
                        air.H3("RC Slab Designer"),
                        air.P("v0.8 beta.", style="color: var(--text-muted); margin-bottom: 20px;"),
                        air.A("Launch", href="/slab", class_="button"),
                        class_="module-card"
                    ),
                    air.Div(
                        air.H3("RC Isolated Footing Designer"),
                        air.P("v0.8 beta.", style="color: var(--text-muted); margin-bottom: 20px;"),
                        air.A("Launch", href="/footing", class_="button"),
                        class_="module-card"
                    ),
                    class_="dashboard-grid"
                )
            )
        )
    )
