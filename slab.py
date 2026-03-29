import air
from air import AirField, AirResponse
from pydantic import BaseModel
import math
import json
from datetime import date

# Import the ACI 318M-25 library components
from aci318m25 import MaterialProperties
from aci318m25_complete import ACI318M25MemberLibrary
from aci318m25_slab import (
    ACI318M25SlabDesign, SlabGeometry, SlabLoads, SlabType,
    SupportCondition, LoadPattern
)
from shared import expressive_layout

base_aci_lib = ACI318M25MemberLibrary()


# ----------------------------------------------------------------------
# 1. NATIVE AIR SCHEMA
# ----------------------------------------------------------------------
class SlabDesignModel(BaseModel):
    action: str = AirField(default="view")
    proj_name: str = AirField(default="Typical Floor Slab")
    proj_loc: str = AirField(default="Manila, PH")
    proj_eng: str = AirField(default="Engr. Doe")
    proj_date: str = AirField(default="")

    # Geometry
    length_x: float = AirField(default=5000.0)
    length_y: float = AirField(default=6000.0)
    thickness: float = AirField(default=150.0)
    cover: float = AirField(default=20.0)

    # Type & Support
    slab_type: str = AirField(default="two_way_flat")
    support_condition: str = AirField(default="continuous")

    # Materials
    fc_prime: float = AirField(default=28.0)
    fy: float = AirField(default=420.0)

    # Loads
    dead_load: float = AirField(default=3.6)  # e.g., self-weight
    superimposed_dead: float = AirField(default=1.2)
    live_load: float = AirField(default=4.8)

    # Punching Shear (for Flat plates/slabs)
    check_punching: str = AirField(default="no")
    col_width: float = AirField(default=400.0)
    col_depth: float = AirField(default=400.0)


# ----------------------------------------------------------------------
# 2. UI RENDER HELPERS & QTO
# ----------------------------------------------------------------------
def generate_slab_plan_css(lx, ly, thickness):
    """Generates a top-down view of the slab panel."""
    max_dim = max(lx, ly)
    scale = 240 / max(max_dim, 1)
    draw_w = lx * scale
    draw_h = ly * scale

    return air.Div(
        air.Div(f"Lx = {lx} mm",
                style="text-align: center; font-family: monospace; font-weight: 700; color: #6b7280; margin-bottom: 8px;"),
        air.Div(
            air.Div(f"Ly = {ly} mm",
                    style="position: absolute; left: -85px; top: 50%; transform: translateY(-50%); font-family: monospace; font-weight: 700; color: #6b7280; white-space: nowrap;"),
            air.Div(
                air.Div(
                    style="position: absolute; top: 50%; left: 10%; right: 10%; height: 2px; background: rgba(37, 99, 235, 0.3); border-top: 2px dashed #2563eb;"),
                air.Div(
                    style="position: absolute; left: 50%; top: 10%; bottom: 10%; width: 2px; background: rgba(37, 99, 235, 0.3); border-left: 2px dashed #2563eb;"),
                style=f"position: relative; width: {draw_w}px; height: {draw_h}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px; box-sizing: border-box; margin: 0 auto; box-shadow: inset 0 0 10px rgba(0,0,0,0.05);"
            ),
            style="position: relative; display: inline-block; margin-left: 60px;"
        ),
        air.Div(f"Thickness (t) = {thickness} mm",
                style="text-align: center; font-family: monospace; font-weight: 700; color: #db2777; margin-top: 16px;"),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px 24px; background: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; width: 100%; box-sizing: border-box;"
    )


def calculate_slab_qto(geom: SlabGeometry, res, fy: float):
    """Calculates approximate QTO for the slab panel."""
    lx_m, ly_m, t_m = geom.length_x / 1000.0, geom.length_y / 1000.0, geom.thickness / 1000.0
    vol_concrete = lx_m * ly_m * t_m
    area_formwork = lx_m * ly_m  # Bottom formwork only for flat slabs

    rebar_rows = []
    total_kg = 0.0

    # Helper to get bar weight per meter
    def get_kg_m(bar_str):
        try:
            db = float(bar_str.replace('D', ''))
            return (db ** 2) / 162.0, db
        except:
            return 0.617, 10.0  # Default to D10

    # Main X bars (running along X, distributed along Y)
    if res.reinforcement.main_bars_x and res.reinforcement.main_spacing_x > 0:
        kg_m, db = get_kg_m(res.reinforcement.main_bars_x)
        num_bars_x = math.ceil((geom.length_y) / res.reinforcement.main_spacing_x)
        total_len_x = num_bars_x * lx_m
        weight_x = total_len_x * kg_m
        total_kg += weight_x
        rebar_rows.append(
            air.Tr(air.Td(air.Strong("Main Bottom X")), air.Td(res.reinforcement.main_bars_x), air.Td(f"{num_bars_x}"),
                   air.Td(f"{lx_m:.2f}m"), air.Td(f"~{(total_len_x / 12.0):.1f} x 12m"), air.Td(f"{weight_x:.1f} kg")))

    # Main Y bars (running along Y, distributed along X)
    if res.reinforcement.main_bars_y and res.reinforcement.main_spacing_y > 0:
        kg_m, db = get_kg_m(res.reinforcement.main_bars_y)
        num_bars_y = math.ceil((geom.length_x) / res.reinforcement.main_spacing_y)
        total_len_y = num_bars_y * ly_m
        weight_y = total_len_y * kg_m
        total_kg += weight_y
        rebar_rows.append(
            air.Tr(air.Td(air.Strong("Main Bottom Y")), air.Td(res.reinforcement.main_bars_y), air.Td(f"{num_bars_y}"),
                   air.Td(f"{ly_m:.2f}m"), air.Td(f"~{(total_len_y / 12.0):.1f} x 12m"), air.Td(f"{weight_y:.1f} kg")))

    # Top bars (Approximated over supports, assuming 1/3 span length on each side)
    if res.reinforcement.top_bars and res.reinforcement.top_spacing > 0:
        kg_m, db = get_kg_m(res.reinforcement.top_bars)
        # Approximate: top bars run in both directions around perimeter/supports.
        # This is a highly simplified QTO for a single panel.
        num_bars_top_x = math.ceil((geom.length_y) / res.reinforcement.top_spacing)
        num_bars_top_y = math.ceil((geom.length_x) / res.reinforcement.top_spacing)

        len_top_x = lx_m * 0.33 * 2  # 33% of span on each end
        len_top_y = ly_m * 0.33 * 2

        total_len_top = (num_bars_top_x * len_top_x) + (num_bars_top_y * len_top_y)
        weight_top = total_len_top * kg_m
        total_kg += weight_top
        rebar_rows.append(
            air.Tr(air.Td(air.Strong("Top Bars (Supports)")), air.Td(res.reinforcement.top_bars), air.Td("-"),
                   air.Td("Variable"), air.Td(f"~{(total_len_top / 12.0):.1f} x 12m"), air.Td(f"{weight_top:.1f} kg")))

    return vol_concrete, area_formwork, total_kg, rebar_rows


# ----------------------------------------------------------------------
# 3. MODULE ROUTES
# ----------------------------------------------------------------------
def setup_slab_routes(app):
    @app.get("/slab")
    def slab_index(request: air.Request):
        data = SlabDesignModel()
        saved_inputs = request.cookies.get("slab_inputs")
        if saved_inputs:
            try:
                data = SlabDesignModel(**json.loads(saved_inputs))
            except Exception:
                pass

        if not data.proj_date: data.proj_date = date.today().strftime("%Y-%m-%d")

        csrf_token = getattr(request.state, "csrf_token", request.cookies.get("csrftoken", "dev_fallback_token"))

        js_punching_toggle = "document.getElementById('punching_fields').style.display = this.value === 'yes' ? 'flex' : 'none';"

        return expressive_layout(
            air.Header(
                air.A("← Dashboard", href="/", class_="back-link no-print"),
                air.H1("RC Slab Designer"),
                air.P("in accordance with ACI 318M-25", class_="subtitle"),
                class_="module-header"
            ),
            air.Main(
                air.Form(
                    air.Input(type="hidden", name="csrf_token", value=csrf_token),
                    air.Div(
                        air.H2("Project Information"),
                        air.Div(
                            air.Div(air.Label("Project Name"),
                                    air.Input(type="text", name="proj_name", value=data.proj_name, required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Location"),
                                    air.Input(type="text", name="proj_loc", value=data.proj_loc, required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Structural Engineer"),
                                    air.Input(type="text", name="proj_eng", value=data.proj_eng, required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Date"),
                                    air.Input(type="date", name="proj_date", value=data.proj_date, required=True),
                                    class_="form-group"),
                            class_="grid-2"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Geometry and Materials"),
                        air.Div(
                            air.Div(air.Label("Span Length X (mm)"),
                                    air.Input(type="number", name="length_x", value=str(data.length_x), required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Span Length Y (mm)"),
                                    air.Input(type="number", name="length_y", value=str(data.length_y), required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Slab Thickness (mm)"),
                                    air.Input(type="number", name="thickness", value=str(data.thickness),
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Concrete Cover (mm)"),
                                    air.Input(type="number", name="cover", value=str(data.cover), required=True),
                                    class_="form-group"),

                            air.Div(air.Label("Slab Type"), air.Select(
                                air.Option("One-Way Slab", value="one_way", selected=(data.slab_type == "one_way")),
                                air.Option("Two-Way Flat Slab", value="two_way_flat",
                                           selected=(data.slab_type == "two_way_flat")),
                                air.Option("Two-Way with Beams", value="two_way_with_beams",
                                           selected=(data.slab_type == "two_way_with_beams")),
                                air.Option("Flat Plate", value="flat_plate", selected=(data.slab_type == "flat_plate")),
                                name="slab_type"), class_="form-group"),

                            air.Div(air.Label("Support Condition"), air.Select(
                                air.Option("Simply Supported", value="simply_supported",
                                           selected=(data.support_condition == "simply_supported")),
                                air.Option("Continuous", value="continuous",
                                           selected=(data.support_condition == "continuous")),
                                air.Option("Fixed", value="fixed", selected=(data.support_condition == "fixed")),
                                air.Option("Cantilever", value="cantilever",
                                           selected=(data.support_condition == "cantilever")),
                                name="support_condition"), class_="form-group"),

                            air.Div(air.Label("Concrete strength f'c (MPa)"),
                                    air.Input(type="number", name="fc_prime", value=str(data.fc_prime), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Steel yield strength fy (MPa)"),
                                    air.Input(type="number", name="fy", value=str(data.fy), step="any", required=True),
                                    class_="form-group"),
                            class_="grid-3"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Loads & Punching Shear"),
                        air.Div(
                            air.Div(
                                air.H3("Gravity Loads (kN/m²)"),
                                air.Div(air.Label("Dead Load (e.g. Self-Weight)"),
                                        air.Input(type="number", name="dead_load", value=str(data.dead_load),
                                                  step="any", required=True), class_="form-group"),
                                air.Div(air.Label("Superimposed Dead Load (SDL)"),
                                        air.Input(type="number", name="superimposed_dead",
                                                  value=str(data.superimposed_dead), step="any", required=True),
                                        class_="form-group"),
                                air.Div(air.Label("Live Load (LL)"),
                                        air.Input(type="number", name="live_load", value=str(data.live_load),
                                                  step="any", required=True), class_="form-group"),
                                class_="section-box"
                            ),
                            air.Div(
                                air.H3("Punching Shear Check"),
                                air.Div(air.Label("Check Punching Shear?"), air.Select(
                                    air.Option("No", value="no", selected=(data.check_punching == "no")),
                                    air.Option("Yes", value="yes", selected=(data.check_punching == "yes")),
                                    name="check_punching", onchange=js_punching_toggle
                                ), class_="form-group"),
                                air.Div(
                                    air.Div(air.Label("Column Width (mm)"),
                                            air.Input(type="number", name="col_width", value=str(data.col_width),
                                                      step="any"), class_="form-group"),
                                    air.Div(air.Label("Column Depth (mm)"),
                                            air.Input(type="number", name="col_depth", value=str(data.col_depth),
                                                      step="any"), class_="form-group"),
                                    id="punching_fields",
                                    style=f"display: {'flex' if data.check_punching == 'yes' else 'none'}; gap: 16px;"
                                ),
                                class_="section-box"
                            ),
                            class_="grid-2"
                        ),
                        air.Button("Perform Design", type="submit",
                                   style="width: 100%; font-size: 18px; margin-top: 32px;"),
                        class_="card"
                    ),
                    method="post", action="/slab/design"
                )
            )
        )

    @app.post("/slab/design")
    async def slab_design(request: air.Request):
        form_data = await request.form()
        cookie_data = json.dumps(dict(form_data))

        try:
            data = SlabDesignModel(**form_data)
        except Exception as e:
            return AirResponse(content=str(expressive_layout(
                air.Main(air.Div(air.H2("Validation Failed", style="color: #DC2626;"), air.P(str(e)), class_="card"))
            )), media_type="text/html")

        try:
            engine = ACI318M25SlabDesign()

            # 1. Setup Material Properties
            mat_props = MaterialProperties(
                fc_prime=data.fc_prime, fy=data.fy, fu=data.fy * 1.25,
                fyt=data.fy, fut=data.fy * 1.25, es=200000.0,
                ec=base_aci_lib.aci.get_concrete_modulus(data.fc_prime),
                gamma_c=24.0, description="Custom Slab Material"
            )

            # 2. Setup Geometry
            # Estimate effective depths. Assume main bars in X are outer layer, Y are inner layer. (assuming 12mm bars)
            dx = data.thickness - data.cover - 6.0
            dy = dx - 12.0

            geom = SlabGeometry(
                length_x=data.length_x, length_y=data.length_y,
                thickness=data.thickness, cover=data.cover,
                effective_depth_x=dx, effective_depth_y=dy,
                slab_type=SlabType(data.slab_type),
                support_conditions={'all_edges': SupportCondition(data.support_condition)}
            )

            # 3. Setup Loads
            loads = SlabLoads(
                dead_load=data.dead_load, live_load=data.live_load,
                superimposed_dead=data.superimposed_dead,
                load_pattern=LoadPattern.UNIFORM,
                load_factors={'D': 1.2, 'L': 1.6}
            )

            # 4. Perform Design
            col_size = (data.col_width, data.col_depth) if data.check_punching == 'yes' else None
            res = engine.perform_complete_slab_design(geom, loads, mat_props, col_size)

            # 5. QTO
            vol_concrete, area_formwork, total_kg, rebar_rows = calculate_slab_qto(geom, res, data.fy)

            # --- Report Generation ---
            status_util = "#16A34A" if res.utilization_ratio <= 1.0 else "#DC2626"

            # Deflection limit logic
            span_mm = max(data.length_x, data.length_y)
            def_limit = span_mm / engine.deflection_limits['immediate']['floor']
            status_def = "#16A34A" if res.deflection <= def_limit else "#DC2626"

            notes_elements = [air.Ul(*[air.Li(f"{'⚠️' if 'exceeds' in n or 'inadequate' in n else 'ℹ️'} {n}") for n in
                                       set(res.design_notes)], class_="notes-list")] if res.design_notes else [
                air.P("No design warnings.", style="color: #6b7280; font-style: italic;")]

            report_content = air.Main(
                air.Div(
                    air.Button("🖨️ Save as PDF", onclick="window.print()", style="background-color: var(--secondary);"),
                    style="margin-bottom: 24px; display: flex; justify-content: flex-end;", class_="no-print"
                ),
                air.Div(
                    air.H2("Project Information"),
                    air.Div(
                        air.Div(air.Strong("Project Name: "), air.Span(data.proj_name, class_="data-value")),
                        air.Div(air.Strong("Location: "), air.Span(data.proj_loc, class_="data-value")),
                        air.Div(air.Strong("Structural Engineer: "), air.Span(data.proj_eng, class_="data-value")),
                        air.Div(air.Strong("Date: "), air.Span(data.proj_date, class_="data-value")),
                        style="display: flex; flex-wrap: wrap; gap: 16px; font-size: 16px;"
                    ), class_="card"
                ),
                air.Div(
                    air.H2("Input Parameters"),
                    air.Div(
                        air.Div(
                            air.H3("Geometry and Materials",
                                   style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                            air.Ul(
                                air.Li(air.Strong("Dimensions"),
                                       air.Span(f"Lx = {data.length_x}mm, Ly = {data.length_y}mm",
                                                class_="data-value")),
                                air.Li(air.Strong("Slab Section"),
                                       air.Span(f"t = {data.thickness}mm, cover = {data.cover}mm",
                                                class_="data-value")),
                                air.Li(air.Strong("Slab Type"),
                                       air.Span(f"{geom.slab_type.value.replace('_', ' ').title()}",
                                                class_="data-value")),
                                air.Li(air.Strong("Support"), air.Span(
                                    f"{geom.support_conditions['all_edges'].value.replace('_', ' ').title()}",
                                    class_="data-value")),
                                air.Li(air.Strong("Materials"),
                                       air.Span(f"f'c = {data.fc_prime} MPa, fy = {data.fy} MPa", class_="data-value")),
                            ), class_="section-box"
                        ),
                        air.Div(
                            air.H3("Loads (kN/m²)",
                                   style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                            air.Ul(
                                air.Li(air.Strong("Dead Load"), air.Span(f"{data.dead_load}", class_="data-value")),
                                air.Li(air.Strong("Superimposed Dead"),
                                       air.Span(f"{data.superimposed_dead}", class_="data-value")),
                                air.Li(air.Strong("Live Load"), air.Span(f"{data.live_load}", class_="data-value")),
                                air.Li(air.Strong("Factored Load (wu)"), air.Span(
                                    f"{((data.dead_load + data.superimposed_dead) * 1.2 + data.live_load * 1.6):.2f} kN/m²",
                                    class_="data-value", style="color:#db2777;")),
                            ), class_="section-box"
                        ),
                        class_="grid-2"
                    ), class_="card"
                ),
                air.Div(class_="page-break"),
                air.Div(
                    air.H2("Design Results"),
                    air.Div(
                        air.Div(
                            generate_slab_plan_css(data.length_x, data.length_y, data.thickness),
                            air.Div(
                                air.H4("Design Notes", style="margin-top: 20px; color: #92400e;"), *notes_elements,
                                style="padding: 16px; background: #fffbeb; border-radius: 8px; border: 1px solid #fde68a; margin-top: 20px;"
                            ),
                            style="display: flex; flex-direction: column;"
                        ),
                        air.Div(
                            air.H3("DCR & Serviceability"),
                            air.Ul(
                                air.Li(air.Strong("Max Utilization (DCR)"),
                                       air.Span(f"{res.utilization_ratio:.2f}", class_="data-value",
                                                style=f"color: {status_util}; font-weight: bold;")),
                                air.Li(air.Strong("Immediate Deflection"),
                                       air.Span(f"{res.deflection:.2f} mm", class_="data-value",
                                                style=f"color: {status_def}; font-weight: bold;")),
                                air.Li(air.Strong("Deflection Limit (L/360)"),
                                       air.Span(f"{def_limit:.1f} mm", class_="data-value")),
                                air.Li(air.Strong("Punching Shear Check"),
                                       air.Span("PASS" if res.punching_shear_ok else "FAIL/NA", class_="data-value",
                                                style=f"color: {'#16A34A' if res.punching_shear_ok else '#DC2626'};")),
                            ),
                            air.H3("Reinforcement Details", style="margin-top: 24px;"),
                            air.Ul(
                                air.Li(air.Strong("Main Bottom X"), air.Span(
                                    f"{res.reinforcement.main_bars_x} @ {res.reinforcement.main_spacing_x:.0f} mm",
                                    class_="data-value", style="color: #2563eb; font-weight: bold;")),
                                air.Li(air.Strong("Main Bottom Y"), air.Span(
                                    f"{res.reinforcement.main_bars_y} @ {res.reinforcement.main_spacing_y:.0f} mm",
                                    class_="data-value", style="color: #2563eb; font-weight: bold;")),
                                air.Li(air.Strong("Top Bars (Supports)"), air.Span(
                                    f"{res.reinforcement.top_bars} @ {res.reinforcement.top_spacing:.0f} mm",
                                    class_="data-value", style="color: #db2777;")),
                                air.Li(air.Strong("Shrinkage / Temp"), air.Span(
                                    f"{res.reinforcement.shrinkage_bars} @ {res.reinforcement.shrinkage_spacing:.0f} mm",
                                    class_="data-value", style="color: #D97706;")),
                            ),
                            air.H3("Demand Moments (kN·m/m)", style="margin-top: 24px;"),
                            air.Ul(
                                air.Li(air.Strong("+Mx (Span)"),
                                       air.Span(f"{res.moments.moment_x_positive:.1f}", class_="data-value")),
                                air.Li(air.Strong("-Mx (Support)"),
                                       air.Span(f"{res.moments.moment_x_negative:.1f}", class_="data-value")),
                                air.Li(air.Strong("+My (Span)"),
                                       air.Span(f"{res.moments.moment_y_positive:.1f}", class_="data-value")),
                                air.Li(air.Strong("-My (Support)"),
                                       air.Span(f"{res.moments.moment_y_negative:.1f}", class_="data-value")),
                            ),
                            class_="section-box", style="height: 100%;"
                        ),
                        class_="grid-2"
                    ), class_="card"
                ),
                air.Div(
                    air.H2("Material Takeoff (Per Panel)"),
                    air.Div(
                        air.Div(air.Div("Concrete Vol.", class_="metric-label"),
                                air.Div(f"{vol_concrete:.2f} m³", class_="metric-value"), class_="metric-card"),
                        air.Div(air.Div("Formwork", class_="metric-label"),
                                air.Div(f"{area_formwork:.1f} m²", class_="metric-value"), class_="metric-card blue"),
                        air.Div(air.Div("Rebar Weight", class_="metric-label"),
                                air.Div(f"{total_kg:.1f} kg", class_="metric-value"), class_="metric-card green"),
                        class_="grid-3"
                    ),
                    air.Table(
                        air.Thead(
                            air.Tr(air.Th("Type"), air.Th("Bar Size"), air.Th("Qty (per panel)"), air.Th("Cut Length"),
                                   air.Th("Est. Order"), air.Th("Weight"))),
                        air.Tbody(*rebar_rows)
                    ),
                    class_="card"
                )
            )

            resp = AirResponse(content=str(expressive_layout(
                air.Header(
                    air.A("← Edit Inputs", href="/slab", class_="back-link no-print"),
                    air.H1("RC Slab Designer"),
                    air.P("in accordance with ACI 318M-25", class_="subtitle"),
                    class_="module-header"
                ), report_content
            )), media_type="text/html")

            resp.set_cookie("slab_inputs", cookie_data, max_age=2592000)
            return resp

        except Exception as e:
            return AirResponse(content=str(expressive_layout(
                air.Header(
                    air.A("← Go Back", href="/slab", class_="back-link no-print"),
                    air.H1("Calculation Error"),
                    air.P("Failed to process slab demands.", class_="subtitle"),
                    class_="module-header"
                ),
                air.Main(air.Div(air.H2("Validation Failed", style="color: #DC2626;"), air.P(str(e)), class_="card"))
            )), media_type="text/html")