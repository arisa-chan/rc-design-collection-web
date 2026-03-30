import air
from air import AirField, AirResponse
from pydantic import BaseModel
import math
import json
from datetime import date

from aci318m25 import MaterialProperties
from aci318m25_slab import (
    ACI318M25SlabDesign, SlabGeometry, SlabLoads,
    LoadPattern, EdgeCondition, EdgeSupport, EdgeContinuity
)
from shared import expressive_layout


class SlabDesignModel(BaseModel):
    action: str = AirField(default="view")
    proj_name: str = AirField(default="Typical Floor Slab")
    proj_loc: str = AirField(default="Manila, PH")
    proj_eng: str = AirField(default="Engr. Doe")
    proj_date: str = AirField(default="")

    length_x: float = AirField(default=5000.0)
    length_y: float = AirField(default=6000.0)
    thickness: float = AirField(default=150.0)
    cover: float = AirField(default=20.0)

    edge_top_support: str = AirField(default="none")
    edge_top_cont: str = AirField(default="discontinuous")
    edge_top_wall_t: float = AirField(default=200.0)
    edge_top_beam_b: float = AirField(default=300.0)
    edge_top_beam_h: float = AirField(default=450.0)
    edge_top_col_cx: float = AirField(default=400.0)
    edge_top_col_cy: float = AirField(default=400.0)

    edge_bot_support: str = AirField(default="wall")
    edge_bot_cont: str = AirField(default="continuous")
    edge_bot_wall_t: float = AirField(default=200.0)
    edge_bot_beam_b: float = AirField(default=300.0)
    edge_bot_beam_h: float = AirField(default=450.0)
    edge_bot_col_cx: float = AirField(default=400.0)
    edge_bot_col_cy: float = AirField(default=400.0)

    edge_left_support: str = AirField(default="wall")
    edge_left_cont: str = AirField(default="discontinuous")
    edge_left_wall_t: float = AirField(default=200.0)
    edge_left_beam_b: float = AirField(default=300.0)
    edge_left_beam_h: float = AirField(default=450.0)
    edge_left_col_cx: float = AirField(default=400.0)
    edge_left_col_cy: float = AirField(default=400.0)

    edge_right_support: str = AirField(default="wall")
    edge_right_cont: str = AirField(default="continuous")
    edge_right_wall_t: float = AirField(default=200.0)
    edge_right_beam_b: float = AirField(default=300.0)
    edge_right_beam_h: float = AirField(default=450.0)
    edge_right_col_cx: float = AirField(default=400.0)
    edge_right_col_cy: float = AirField(default=400.0)

    fc_prime: float = AirField(default=28.0)
    fy: float = AirField(default=420.0)

    superimposed_dead: float = AirField(default=1.2)
    live_load: float = AirField(default=4.8)
    deflection_limit: str = AirField(default="240")


def render_edge_input(edge_name: str, prefix: str, data: SlabDesignModel):
    sup_val = getattr(data, f"{prefix}_support")
    js_toggle = f"document.getElementById('{prefix}_wall').style.display = (this.value === 'wall') ? 'block' : 'none'; document.getElementById('{prefix}_beam').style.display = (this.value === 'beam') ? 'flex' : 'none'; document.getElementById('{prefix}_col').style.display = (this.value === 'column') ? 'flex' : 'none';"

    return air.Div(
        air.H4(f"{edge_name} Edge", style="margin-top: 0; margin-bottom: 8px; color: #4b5563; font-size: 15px;"),
        air.Div(
            air.Div(air.Label("Support Type"), air.Select(
                air.Option("Wall", value="wall", selected=(sup_val == "wall")),
                air.Option("Beam", value="beam", selected=(sup_val == "beam")),
                air.Option("Column (Ends Only)", value="column", selected=(sup_val == "column")),
                air.Option("None (Free Edge)", value="none", selected=(sup_val == "none")),
                name=f"{prefix}_support", onchange=js_toggle
            ), class_="form-group"),
            air.Div(air.Label("Continuity"), air.Select(
                air.Option("Continuous", value="continuous",
                           selected=(getattr(data, f"{prefix}_cont") == "continuous")),
                air.Option("Discontinuous", value="discontinuous",
                           selected=(getattr(data, f"{prefix}_cont") == "discontinuous")),
                name=f"{prefix}_cont"
            ), class_="form-group"),
            class_="grid-2"
        ),
        air.Div(
            air.Label("Wall Thickness (mm)"),
            air.Input(type="number", name=f"{prefix}_wall_t", value=str(getattr(data, f"{prefix}_wall_t")), step="any"),
            id=f"{prefix}_wall", style=f"display: {'block' if sup_val == 'wall' else 'none'}; margin-top: 8px;",
            class_="form-group"
        ),
        air.Div(
            air.Div(air.Label("Beam Width, b (mm)"),
                    air.Input(type="number", name=f"{prefix}_beam_b", value=str(getattr(data, f"{prefix}_beam_b")),
                              step="any"), class_="form-group"),
            air.Div(air.Label("Beam Depth, h (mm)"),
                    air.Input(type="number", name=f"{prefix}_beam_h", value=str(getattr(data, f"{prefix}_beam_h")),
                              step="any"), class_="form-group"),
            id=f"{prefix}_beam", class_="grid-2",
            style=f"display: {'flex' if sup_val == 'beam' else 'none'}; margin-top: 8px; gap: 16px;"
        ),
        air.Div(
            air.Div(air.Label("Col. Dim X, cx (mm)"),
                    air.Input(type="number", name=f"{prefix}_col_cx", value=str(getattr(data, f"{prefix}_col_cx")),
                              step="any"), class_="form-group"),
            air.Div(air.Label("Col. Dim Y, cy (mm)"),
                    air.Input(type="number", name=f"{prefix}_col_cy", value=str(getattr(data, f"{prefix}_col_cy")),
                              step="any"), class_="form-group"),
            id=f"{prefix}_col", class_="grid-2",
            style=f"display: {'flex' if sup_val == 'column' else 'none'}; margin-top: 8px; gap: 16px;"
        ),
        class_="section-box", style="margin-bottom: 16px;"
    )


def generate_slab_plan_css(lx, ly, thickness, data: SlabDesignModel, res=None):
    max_dim = max(lx, ly)
    scale = 240 / max(max_dim, 1)
    draw_w = lx * scale
    draw_h = ly * scale

    def get_border(support):
        if support == "wall": return "4px solid #111827"
        if support == "beam": return "4px dashed #db2777"
        if support == "none": return "1px dotted #9ca3af"
        return "1px solid transparent"

    border_top = get_border(data.edge_top_support)
    border_bot = get_border(data.edge_bot_support)
    border_left = get_border(data.edge_left_support)
    border_right = get_border(data.edge_right_support)

    children = []
    if res is not None:
        css_sx = max(2, res.reinforcement.main_spacing_x * scale)
        css_sy = max(2, res.reinforcement.main_spacing_y * scale)
        children.append(air.Div(
            style=f"position: absolute; top: 0; left: 0; right: 0; bottom: 0; opacity: 0.35; pointer-events: none; "
                  f"background-image: "
                  f"repeating-linear-gradient(to right, transparent, transparent calc({css_sx}px - 1px), #2563eb calc({css_sx}px - 1px), #2563eb {css_sx}px), "
                  f"repeating-linear-gradient(to bottom, transparent, transparent calc({css_sy}px - 1px), #ef4444 calc({css_sy}px - 1px), #ef4444 {css_sy}px);"
        ))

    def draw_cols(edge_support, is_top_or_bot):
        if edge_support == "column":
            y_pos = "-6px" if is_top_or_bot == "top" else f"{draw_h - 6}px"
            x_pos = "-6px" if is_top_or_bot == "left" else f"{draw_w - 6}px"
            if is_top_or_bot in ["top", "bot"]:
                children.append(air.Div(
                    style=f"position:absolute; left:-6px; top:{y_pos}; width:12px; height:12px; background:#1e3a8a;"))
                children.append(air.Div(
                    style=f"position:absolute; right:-6px; top:{y_pos}; width:12px; height:12px; background:#1e3a8a;"))
            else:
                children.append(air.Div(
                    style=f"position:absolute; top:-6px; left:{x_pos}; width:12px; height:12px; background:#1e3a8a;"))
                children.append(air.Div(
                    style=f"position:absolute; bottom:-6px; left:{x_pos}; width:12px; height:12px; background:#1e3a8a;"))

    draw_cols(data.edge_top_support, "top")
    draw_cols(data.edge_bot_support, "bot")
    draw_cols(data.edge_left_support, "left")
    draw_cols(data.edge_right_support, "right")

    return air.Div(
        air.Div(f"Lx = {lx} mm",
                style="text-align: center; font-family: monospace; font-weight: 700; color: #6b7280; margin-bottom: 8px;"),
        air.Div(
            air.Div(f"Ly = {ly} mm",
                    style="position: absolute; left: -85px; top: 50%; transform: translateY(-50%); font-family: monospace; font-weight: 700; color: #6b7280; white-space: nowrap;"),
            air.Div(
                *children,
                style=f"position: relative; width: {draw_w}px; height: {draw_h}px; background: #f3f4f6; border-top: {border_top}; border-bottom: {border_bot}; border-left: {border_left}; border-right: {border_right}; box-sizing: border-box; margin: 0 auto; box-shadow: inset 0 0 10px rgba(0,0,0,0.05); overflow: hidden;"
            ),
            style="position: relative; display: inline-block; margin-left: 60px;"
        ),
        air.Div(f"Thickness (t) = {thickness} mm",
                style="text-align: center; font-family: monospace; font-weight: 700; color: #db2777; margin-top: 16px;"),
        air.Div("Solid = Wall | Dashed = Beam | Dots = Columns | Dotted = Free",
                style="font-size:11px; color:#9ca3af; margin-top: 8px;"),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px 24px; background: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; width: 100%; box-sizing: border-box;"
    )


def render_contour_viewer(contours_dict):
    if not contours_dict: return air.Div()

    options = [
        ("deflection", "Deflection"), ("mxx", "Mxx (Span X)"), ("myy", "Myy (Span Y)"),
        ("mxy", "Mxy (Twisting)"), ("mx_wa", "Wood-Armer Mx (Bot)"), ("my_wa", "Wood-Armer My (Bot)"),
        ("vx", "Shear Vx"), ("vy", "Shear Vy")
    ]

    img_elements = []
    for key, title in options:
        b64 = contours_dict.get(key, "")
        display = "block" if key == "deflection" else "none"
        img_elements.append(air.Img(
            src=f"data:image/png;base64,{b64}",
            id=f"contour_{key}",
            style=f"display: {display}; width: 100%; max-width: 550px; height: auto; margin: 0 auto; border-radius: 4px;"
        ))

    js_toggle = "document.querySelectorAll('[id^=contour_]').forEach(el => el.style.display = 'none'); document.getElementById('contour_' + this.value).style.display = 'block';"

    return air.Div(
        air.H2("FEA Contour Plots"),
        air.Div(
            air.Div(
                air.Label("Select Contour Output:", style="font-size: 14px; margin-bottom: 8px; display: block;"),
                air.Select(*[air.Option(title, value=key) for key, title in options], onchange=js_toggle),
                style="margin-bottom: 16px; text-align: center;"
            ),
            air.Div(*img_elements,
                    style="display: flex; flex-direction: column; align-items: center; justify-content: center; background: #ffffff; border: 1px dashed #e5e7eb; padding: 24px; border-radius: 8px;"),
        ), class_="card no-print"
    )


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
        csrf_token = getattr(request.state, "csrf_token", request.cookies.get("csrftoken", "dev_token"))

        return expressive_layout(
            air.Header(
                air.A("← Dashboard", href="/", class_="back-link no-print"),
                air.H1("RC Slab Designer"),
                air.P("OpenSees FEA Engine", class_="subtitle"),
                class_="module-header"
            ),
            air.Main(
                air.Form(
                    air.Input(type="hidden", name="csrf_token", value=csrf_token),
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
                        air.H2("Edge Support Conditions"),
                        air.Div(
                            render_edge_input("Top (Y=Ly)", "edge_top", data),
                            render_edge_input("Bottom (Y=0)", "edge_bot", data),
                            render_edge_input("Left (X=0)", "edge_left", data),
                            render_edge_input("Right (X=Lx)", "edge_right", data),
                            class_="grid-2"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Loading & Serviceability"),
                        air.P(
                            f"Note: Slab self-weight is automatically computed based on {data.thickness}mm thickness.",
                            style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;"),
                        air.Div(
                            air.Div(air.Label("Superimposed Dead Load (SDL)"),
                                    air.Input(type="number", name="superimposed_dead",
                                              value=str(data.superimposed_dead), step="any", required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Live Load (LL)"),
                                    air.Input(type="number", name="live_load", value=str(data.live_load), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Long Term Deflection Limit"), air.Select(
                                air.Option("L/240 (Non-sensitive finishes)", value="240",
                                           selected=(str(data.deflection_limit) == "240")),
                                air.Option("L/480 (Sensitive finishes)", value="480",
                                           selected=(str(data.deflection_limit) == "480")),
                                name="deflection_limit"
                            ), class_="form-group"),
                            class_="grid-3"
                        ),
                        air.Button("Analyze via OpenSees FEA", type="submit",
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
            return AirResponse(content=str(
                expressive_layout(air.Main(air.Div(air.H2("Validation Failed"), air.P(str(e)), class_="card")))),
                               media_type="text/html")

        try:
            engine = ACI318M25SlabDesign()
            mat_props = MaterialProperties(
                fc_prime=data.fc_prime, fy=data.fy, fu=data.fy * 1.25, fyt=data.fy, fut=data.fy * 1.25,
                es=200000.0, ec=4700 * math.sqrt(data.fc_prime), gamma_c=24.0, description="Custom Slab Material"
            )

            dx = data.thickness - data.cover - 6.0
            dy = dx - 12.0

            geom = SlabGeometry(
                length_x=data.length_x, length_y=data.length_y,
                thickness=data.thickness, cover=data.cover,
                effective_depth_x=dx, effective_depth_y=dy,
                edge_top=EdgeCondition(EdgeSupport(data.edge_top_support), EdgeContinuity(data.edge_top_cont),
                                       data.edge_top_wall_t, data.edge_top_beam_b, data.edge_top_beam_h,
                                       data.edge_top_col_cx, data.edge_top_col_cy),
                edge_bottom=EdgeCondition(EdgeSupport(data.edge_bot_support), EdgeContinuity(data.edge_bot_cont),
                                          data.edge_bot_wall_t, data.edge_bot_beam_b, data.edge_bot_beam_h,
                                          data.edge_bot_col_cx, data.edge_bot_col_cy),
                edge_left=EdgeCondition(EdgeSupport(data.edge_left_support), EdgeContinuity(data.edge_left_cont),
                                        data.edge_left_wall_t, data.edge_left_beam_b, data.edge_left_beam_h,
                                        data.edge_left_col_cx, data.edge_left_col_cy),
                edge_right=EdgeCondition(EdgeSupport(data.edge_right_support), EdgeContinuity(data.edge_right_cont),
                                         data.edge_right_wall_t, data.edge_right_beam_b, data.edge_right_beam_h,
                                         data.edge_right_col_cx, data.edge_right_col_cy)
            )

            self_weight_knm2 = (data.thickness / 1000.0) * 24.0

            loads = SlabLoads(
                self_weight=self_weight_knm2, live_load=data.live_load, superimposed_dead=data.superimposed_dead,
                load_pattern=LoadPattern.UNIFORM, load_factors={'D': 1.2, 'L': 1.6}
            )

            res = engine.perform_complete_slab_design(geom, loads, mat_props)

            status_util = "#16A34A" if res.utilization_ratio <= 1.0 else "#DC2626"

            span_mm = max(data.length_x, data.length_y)
            def_lim_live = span_mm / 360.0
            def_lim_long = span_mm / float(data.deflection_limit)

            status_def_live = "#16A34A" if res.deflection_live <= def_lim_live else "#DC2626"
            status_def_long = "#16A34A" if res.deflection_long <= def_lim_long else "#DC2626"

            if res.deflection_live > def_lim_live:
                res.design_notes.append(
                    f"Immediate Live Deflection ({res.deflection_live:.1f} mm) exceeds L/360 limit ({def_lim_live:.1f} mm).")
            if res.deflection_long > def_lim_long:
                res.design_notes.append(
                    f"Long-Term Deflection ({res.deflection_long:.1f} mm) exceeds L/{data.deflection_limit} limit ({def_lim_long:.1f} mm).")

            notes_elements = [air.Ul(*[air.Li(f"ℹ️ {n}") for n in set(res.design_notes)],
                                     class_="notes-list")] if res.design_notes else []

            report_content = air.Main(
                air.Div(
                    air.H2("OpenSees FEA Results"),
                    air.Div(
                        air.Div(
                            generate_slab_plan_css(data.length_x, data.length_y, data.thickness, data, res),
                            air.Div(
                                air.H4("Analysis Log", style="margin-top: 20px; color: #92400e;"), *notes_elements,
                                style="padding: 16px; background: #fffbeb; border-radius: 8px; border: 1px solid #fde68a; margin-top: 20px;"
                            ),
                            style="display: flex; flex-direction: column;"
                        ),
                        air.Div(
                            air.H3("DCR & Deflection"),
                            air.Ul(
                                air.Li(air.Strong("Max Flexural DCR"),
                                       air.Span(f"{res.utilization_ratio:.2f}", class_="data-value",
                                                style=f"color: {status_util}; font-weight: bold;")),
                                air.Li(air.Strong("Immediate Live Deflection"),
                                       air.Span(f"{res.deflection_live:.2f} mm", class_="data-value",
                                                style=f"color: {status_def_live}; font-weight: bold;")),
                                air.Li(air.Strong("Limit (L/360)"),
                                       air.Span(f"{def_lim_live:.1f} mm", class_="data-value")),
                                air.Li(air.Strong("Long-Term Deflection"),
                                       air.Span(f"{res.deflection_long:.2f} mm", class_="data-value",
                                                style=f"color: {status_def_long}; font-weight: bold;")),
                                air.Li(air.Strong(f"Limit (L/{data.deflection_limit})"),
                                       air.Span(f"{def_lim_long:.1f} mm", class_="data-value")),
                            ),
                            air.H3("Reinforcement Details", style="margin-top: 24px;"),
                            air.Ul(
                                air.Li(air.Strong("Main Bottom X (Blue)"), air.Span(
                                    f"{res.reinforcement.main_bars_x} @ {res.reinforcement.main_spacing_x:.0f} mm",
                                    class_="data-value", style="color: #2563eb; font-weight: bold;")),
                                air.Li(air.Strong("Top X (Supports)"), air.Span(
                                    f"{res.reinforcement.top_bars_x} @ {res.reinforcement.top_spacing_x:.0f} mm",
                                    class_="data-value", style="color: #db2777;")),
                                air.Li(air.Strong("Main Bottom Y (Red)"), air.Span(
                                    f"{res.reinforcement.main_bars_y} @ {res.reinforcement.main_spacing_y:.0f} mm",
                                    class_="data-value", style="color: #ef4444; font-weight: bold;")),
                                air.Li(air.Strong("Top Y (Supports)"), air.Span(
                                    f"{res.reinforcement.top_bars_y} @ {res.reinforcement.top_spacing_y:.0f} mm",
                                    class_="data-value", style="color: #db2777;")),
                            ),
                            air.H3("FEA Demand Moments (kN·m/m)", style="margin-top: 24px;"),
                            air.Ul(
                                air.Li(air.Strong("+Mxx (Span X)"),
                                       air.Span(f"{res.moments.moment_x_positive:.1f}", class_="data-value")),
                                air.Li(air.Strong("-Mxx (Support X)"),
                                       air.Span(f"{res.moments.moment_x_negative:.1f}", class_="data-value")),
                                air.Li(air.Strong("+Myy (Span Y)"),
                                       air.Span(f"{res.moments.moment_y_positive:.1f}", class_="data-value")),
                                air.Li(air.Strong("-Myy (Support Y)"),
                                       air.Span(f"{res.moments.moment_y_negative:.1f}", class_="data-value")),
                            ),
                            class_="section-box", style="height: 100%;"
                        ),
                        class_="grid-2"
                    ), class_="card"
                ),
                render_contour_viewer(res.contours)
            )

            resp = AirResponse(content=str(expressive_layout(
                air.Header(
                    air.A("← Edit Inputs", href="/slab", class_="back-link no-print"),
                    air.H1("RC Slab Designer"),
                    air.P("OpenSees FEA Engine", class_="subtitle"),
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
                    air.P("FEA Failed.", class_="subtitle"),
                    class_="module-header"
                ),
                air.Main(air.Div(air.H2("Exception"), air.P(str(e)), class_="card"))
            )), media_type="text/html")