import air
import beam
from shared import expressive_layout

# Initialize the Air App
app = air.Air()

# Register the Beam module routes directly to our app
beam.setup_beam_routes(app)

@app.page
def index(request: air.Request):
    """
    Central dashboard for the ACI 318M-25 Structural Suite.
    Designed for infinite scalability as new modules are created.
    """
    return expressive_layout(
        air.Header(
            air.H1("ACI 318M-25 Design Suite"),
            air.P("Select a structural module below to begin engineering analysis and QTO generation.", class_="subtitle"),
            class_="hero-header"
        ),
        air.Main(
            air.Div(
                air.H2("Available Modules"),
                air.Div(
                    # Beam Designer Card (Active)
                    air.Div(
                        air.H3("RC Beam Designer"),
                        air.P("Continuous beam analysis including flexure, combined shear-torsion, serviceability checks, and detailed quantity takeoffs.", style="margin-bottom: 24px;"),
                        air.A("Launch Designer →", href="/beam", class_="button", style="width: 100%; box-sizing: border-box;"),
                        class_="card"
                    ),
                    
                    # Column Designer Card (Placeholder for future)
                    air.Div(
                        air.H3("RC Column Designer", style="color: var(--text-muted);"),
                        air.P("Advanced P-M interaction diagrams and biaxial shear capacity design.", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Coming Soon", href="#", class_="button secondary", style="width: 100%; box-sizing: border-box; pointer-events: none; opacity: 0.5;"),
                        class_="card",
                        style="background: #f9fafb; border-color: #e5e7eb;"
                    ),
                    
                    # Slab Designer Card (Placeholder for future)
                    air.Div(
                        air.H3("RC Slab Designer", style="color: var(--text-muted);"),
                        air.P("One-way and two-way flat slab systems with complex punching shear validation.", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Coming Soon", href="#", class_="button secondary", style="width: 100%; box-sizing: border-box; pointer-events: none; opacity: 0.5;"),
                        class_="card",
                        style="background: #f9fafb; border-color: #e5e7eb;"
                    ),
                    
                    # Footing Designer Card (Placeholder for future)
                    air.Div(
                        air.H3("Isolated Footings", style="color: var(--text-muted);"),
                        air.P("Bearing pressure validation, one-way shear, and two-way punching shear checks.", style="color: var(--text-muted); margin-bottom: 24px;"),
                        air.A("Coming Soon", href="#", class_="button secondary", style="width: 100%; box-sizing: border-box; pointer-events: none; opacity: 0.5;"),
                        class_="card",
                        style="background: #f9fafb; border-color: #e5e7eb;"
                    ),
                    
                    class_="grid-2"
                )
            )
        )
    )