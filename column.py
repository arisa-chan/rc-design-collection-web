import air
from air import AirField, AirResponse
from pydantic import BaseModel
import math
import json
from datetime import date

from aci318m25 import MaterialProperties
from aci318m25_complete import ACI318M25MemberLibrary
from aci318m25_column import (
    ACI318M25ColumnDesign, ColumnGeometry, ColumnLoads, ColumnShape, ColumnType,
    LoadCondition, SeismicDesignCategory, FrameSystem, JointBeamElement, JointColumnElement
)
from shared import expressive_layout

base_aci_lib = ACI318M25MemberLibrary()


# ----------------------------------------------------------------------
# 1. NATIVE AIR SCHEMA
# ----------------------------------------------------------------------
class ColumnDesignModel(BaseModel):
    action: str = AirField(default="view")
    proj_name: str = AirField(default="Typical Column Design")
    proj_loc: str = AirField(default="Manila, PH")
    proj_eng: str = AirField(default="Engr. Doe")
    proj_date: str = AirField(default="")

    width: float = AirField(default=500.0)
    depth: float = AirField(default=500.0)
    height: float = AirField(default=3200.0)
    clear_height: float = AirField(default=2800.0)

    sdc: str = AirField(default="D")
    frame_system: str = AirField(default="special")
    pref_main: str = AirField(default="D25")
    pref_tie: str = AirField(default="D12")
    fc_prime: float = AirField(default=28.0)
    fy: float = AirField(default=415.0)
    fyt: float = AirField(default=415.0)

    pu: float = AirField(default=2500.0)
    top_mux: float = AirField(default=150.0)
    top_muy: float = AirField(default=80.0)
    top_vux: float = AirField(default=120.0)
    top_vuy: float = AirField(default=90.0)
    bot_mux: float = AirField(default=180.0)
    bot_muy: float = AirField(default=90.0)
    bot_vux: float = AirField(default=120.0)
    bot_vuy: float = AirField(default=90.0)

    top_bx1_exists: str = AirField(default="yes")
    top_bx1_b: float = AirField(default=300.0)
    top_bx1_d: float = AirField(default=440.0)
    top_bx1_qty_top: int = AirField(default=4)
    top_bx1_dia_top: str = AirField(default="D20")
    top_bx1_qty_bot: int = AirField(default=2)
    top_bx1_dia_bot: str = AirField(default="D20")

    top_bx2_exists: str = AirField(default="yes")
    top_bx2_b: float = AirField(default=300.0)
    top_bx2_d: float = AirField(default=440.0)
    top_bx2_qty_top: int = AirField(default=4)
    top_bx2_dia_top: str = AirField(default="D20")
    top_bx2_qty_bot: int = AirField(default=2)
    top_bx2_dia_bot: str = AirField(default="D20")

    top_by1_exists: str = AirField(default="no")
    top_by1_b: float = AirField(default=300.0)
    top_by1_d: float = AirField(default=440.0)
    top_by1_qty_top: int = AirField(default=4)
    top_by1_dia_top: str = AirField(default="D20")
    top_by1_qty_bot: int = AirField(default=2)
    top_by1_dia_bot: str = AirField(default="D20")

    top_by2_exists: str = AirField(default="no")
    top_by2_b: float = AirField(default=300.0)
    top_by2_d: float = AirField(default=440.0)
    top_by2_qty_top: int = AirField(default=4)
    top_by2_dia_top: str = AirField(default="D20")
    top_by2_qty_bot: int = AirField(default=2)
    top_by2_dia_bot: str = AirField(default="D20")

    top_ca_exists: str = AirField(default="yes")
    top_ca_b: float = AirField(default=500.0)
    top_ca_h: float = AirField(default=500.0)
    top_ca_qty: int = AirField(default=8)
    top_ca_dia: str = AirField(default="D20")
    top_ca_pu: float = AirField(default=2000.0)


# ----------------------------------------------------------------------
# 2. UI RENDER HELPERS
# ----------------------------------------------------------------------
def generate_column_section_css(width, depth, cover, num_bars, legs_x, legs_y):
    scale = min(200 / max(width, 1), 200 / max(depth, 1))
    draw_w, draw_h, c_s = width * scale, depth * scale, cover * scale
    children = []
    core_w, core_h = draw_w - 2 * c_s, draw_h - 2 * c_s

    if core_w > 0 and core_h > 0:
        # Draw Ties
        children.append(air.Div(
            style=f"position: absolute; left: {c_s}px; top: {c_s}px; width: {core_w}px; height: {core_h}px; border: 2px dashed #db2777; border-radius: 4px; box-sizing: border-box;"))
        if legs_x > 2:
            spacing_x = core_w / (legs_x - 1)
            for i in range(1, legs_x - 1): children.append(air.Div(
                style=f"position: absolute; left: {c_s + i * spacing_x}px; top: {c_s}px; width: 0px; height: {core_h}px; border-left: 2px dashed #db2777; box-sizing: border-box;"))
        if legs_y > 2:
            spacing_y = core_h / (legs_y - 1)
            for i in range(1, legs_y - 1): children.append(air.Div(
                style=f"position: absolute; left: {c_s}px; top: {c_s + i * spacing_y}px; width: {core_w}px; height: 0px; border-top: 2px dashed #db2777; box-sizing: border-box;"))

    # INSET OFFSET: Pushes main bars inside the tie boundary for realistic overlap prevention
    inset = 4
    bx, by = c_s + inset, c_s + inset
    bw, bh = core_w - 2 * inset, core_h - 2 * inset

    def add_bar(x, y):
        children.append(air.Div(
            style=f"position: absolute; left: {x - 6}px; top: {y - 6}px; width: 12px; height: 12px; background: #2563eb; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))

    nx_face, ny_face = 0, 0
    if num_bars > 4:
        rem = num_bars - 4
        ratio = width / (width + depth) if (width + depth) > 0 else 0.5
        nx_inter = 2 * int(round(rem * ratio / 2.0))
        nx_face, ny_face = nx_inter // 2, (rem - nx_inter) // 2

    if bw >= 0 and bh >= 0:
        add_bar(bx, by);
        add_bar(bx + bw, by);
        add_bar(bx, by + bh);
        add_bar(bx + bw, by + bh)
        if nx_face > 0:
            sp_x = bw / (nx_face + 1)
            for i in range(1, nx_face + 1): add_bar(bx + i * sp_x, by); add_bar(bx + i * sp_x, by + bh)
        if ny_face > 0:
            sp_y = bh / (ny_face + 1)
            for i in range(1, ny_face + 1): add_bar(bx, by + i * sp_y); add_bar(bx + bw, by + i * sp_y)

    concrete_block = air.Div(*children,
                             style=f"position: relative; width: {draw_w}px; height: {draw_h}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px; box-sizing: border-box; margin: 0 auto;")
    return air.Div(
        air.Div(f"{width} mm",
                style="text-align: center; font-family: monospace; font-weight: 700; color: #6b7280; margin-bottom: 8px;"),
        air.Div(air.Div(f"{depth} mm",
                        style="position: absolute; left: -65px; top: 50%; transform: translateY(-50%); font-family: monospace; font-weight: 700; color: #6b7280;"),
                concrete_block, style="position: relative; display: inline-block; margin-left: 40px;"),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; background: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; width: 100%; box-sizing: border-box;"
    )


def generate_column_elevation_css(height, clear_height, max_dim, s_hinge, s_mid):
    lo = max(max_dim, clear_height / 6.0, 450.0) if s_hinge != s_mid else 0.0
    if lo * 2 >= clear_height: lo = clear_height / 2.0

    vis_height = 280
    vis_width = 80
    scale = vis_height / height

    children = []

    # Vertical Main Bars (3 lines representation)
    children.append(air.Div(
        style="position: absolute; left: 15%; top: -5px; bottom: -5px; width: 4px; background: #2563eb; border-radius: 2px; z-index: 2;"))
    children.append(air.Div(
        style="position: absolute; left: 50%; top: -5px; bottom: -5px; width: 4px; background: #2563eb; border-radius: 2px; transform: translateX(-50%); z-index: 2;"))
    children.append(air.Div(
        style="position: absolute; right: 15%; top: -5px; bottom: -5px; width: 4px; background: #2563eb; border-radius: 2px; z-index: 2;"))

    # Horizontal Ties
    y = 50.0
    loop_guard = 0
    while y <= height - 50.0 and loop_guard < 300:
        loop_guard += 1
        is_hinge = (y <= lo) or (y >= height - lo)
        current_s = s_hinge if is_hinge else s_mid
        color = "#db2777" if is_hinge else "#9ca3af"
        children.append(air.Div(
            style=f"position: absolute; bottom: {y * scale}px; left: 5%; right: 5%; height: 2px; background: {color}; z-index: 1;"))
        y += current_s

    # Confinement Zone Dimension Labels
    labels = []
    if lo > 0:
        lo_px = lo * scale
        labels.append(air.Div(f"lo ({lo:.0f} mm)",
                              style=f"position: absolute; right: -90px; bottom: 0; height: {lo_px}px; display: flex; align-items: center; font-size: 11px; color: #db2777; font-weight: bold; border-left: 2px solid #db2777; padding-left: 6px;"))
        labels.append(air.Div(f"Midheight",
                              style=f"position: absolute; right: -90px; bottom: {lo_px}px; top: {lo_px}px; display: flex; align-items: center; font-size: 11px; color: #6b7280; border-left: 2px dashed #9ca3af; padding-left: 6px;"))
        labels.append(air.Div(f"lo ({lo:.0f} mm)",
                              style=f"position: absolute; right: -90px; top: 0; height: {lo_px}px; display: flex; align-items: center; font-size: 11px; color: #db2777; font-weight: bold; border-left: 2px solid #db2777; padding-left: 6px;"))

    concrete_block = air.Div(*children, *labels,
                             style=f"position: relative; width: {vis_width}px; height: {vis_height}px; background: #f3f4f6; border: 2px solid #111827; border-radius: 2px; box-sizing: border-box; margin: 0 auto;")
    return air.Div(
        concrete_block,
        air.Div(f"Elevation (H = {height} mm)",
                style="text-align: center; font-family: monospace; font-weight: 700; color: #6b7280; margin-top: 12px;"),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px 100px 16px 16px; background: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; width: 100%; box-sizing: border-box;"
    )


def render_top_joint_modal(modal_id, data):
    modal_style = "display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6);"
    content_style = "background-color: #fefefe; margin: 5% auto; padding: 24px; border: 1px solid #888; width: 95%; max-width: 800px; border-radius: 8px; position: relative;"
    bar_opts = ["D16", "D20", "D25", "D28", "D32", "D36"]

    def render_element_block(title, prefix, is_col=False):
        exists_val = getattr(data, f"{prefix}_exists")
        display_style = "block" if exists_val == "yes" else "none"
        js_func = f"document.getElementById('{prefix}_fields').style.display = this.value === 'yes' ? 'block' : 'none';"

        if is_col:
            fields = [
                air.Div(air.Label("Dimension along x (mm)"),
                        air.Input(type="number", name=f"{prefix}_b", value=str(getattr(data, f"{prefix}_b")),
                                  step="any"), class_="form-group"),
                air.Div(air.Label("Dimension along y (mm)"),
                        air.Input(type="number", name=f"{prefix}_h", value=str(getattr(data, f"{prefix}_h")),
                                  step="any"), class_="form-group"),
                air.Div(
                    air.Div(air.Label("Number of vertical bars"),
                            air.Input(type="number", name=f"{prefix}_qty", value=str(getattr(data, f"{prefix}_qty")),
                                      step="1"), class_="form-group"),
                    air.Div(air.Label("Vertical bar diameter"), air.Select(
                        *[air.Option(opt, selected=(getattr(data, f"{prefix}_dia") == opt)) for opt in bar_opts],
                        name=f"{prefix}_dia"), class_="form-group"),
                    class_="grid-2"
                ),
                air.Div(air.Label("Factored axial Pu (kN)"),
                        air.Input(type="number", name=f"{prefix}_pu", value=str(getattr(data, f"{prefix}_pu")),
                                  step="any"), class_="form-group")
            ]
        else:
            fields = [
                air.Div(air.Label("Beam width (mm)"),
                        air.Input(type="number", name=f"{prefix}_b", value=str(getattr(data, f"{prefix}_b")),
                                  step="any"), class_="form-group"),
                air.Div(air.Label("Beam effective depth (mm)"),
                        air.Input(type="number", name=f"{prefix}_d", value=str(getattr(data, f"{prefix}_d")),
                                  step="any"), class_="form-group"),
                air.Div(
                    air.Div(air.Label("Number of top bars"), air.Input(type="number", name=f"{prefix}_qty_top",
                                                                 value=str(getattr(data, f"{prefix}_qty_top")),
                                                                 step="1"), class_="form-group"),
                    air.Div(air.Label("Top bar diameter"), air.Select(
                        *[air.Option(opt, selected=(getattr(data, f"{prefix}_dia_top") == opt)) for opt in bar_opts],
                        name=f"{prefix}_dia_top"), class_="form-group"),
                    class_="grid-2"
                ),
                air.Div(
                    air.Div(air.Label("Number of bottom bars"), air.Input(type="number", name=f"{prefix}_qty_bot",
                                                                 value=str(getattr(data, f"{prefix}_qty_bot")),
                                                                 step="1"), class_="form-group"),
                    air.Div(air.Label("Bottom bar diameter"), air.Select(
                        *[air.Option(opt, selected=(getattr(data, f"{prefix}_dia_bot") == opt)) for opt in bar_opts],
                        name=f"{prefix}_dia_bot"), class_="form-group"),
                    class_="grid-2"
                )
            ]
        return air.Div(
            air.H4(title, style="margin-bottom: 12px; color: #4b5563; font-size: 15px;"),
            air.Div(air.Label("Is element present?"),
                    air.Select(air.Option("Yes", value="yes", selected=exists_val == "yes"),
                               air.Option("No", value="no", selected=exists_val == "no"), name=f"{prefix}_exists",
                               onchange=js_func), class_="form-group"),
            air.Div(*fields, id=f"{prefix}_fields", style=f"display: {display_style};"),
            class_="section-box"
        )

    return air.Div(
        air.Div(
            air.Span("×",
                     style="color: #aaa; position: absolute; right: 20px; top: 15px; font-size: 28px; font-weight: bold; cursor: pointer;",
                     onclick=f"document.getElementById('{modal_id}').style.display='none'"),
            air.H3("Seismic Joint Checks", style="margin-bottom: 16px; color: #1e3a8a;"),
            air.H4("Framing along x-direction",
                   style="border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin-bottom: 16px;"),
            air.Div(render_element_block("Left beam", "top_bx1"), render_element_block("Right beam", "top_bx2"),
                    class_="grid-2", style="margin-bottom: 24px;"),
            air.H4("Framing along y-direction",
                   style="border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin-bottom: 16px;"),
            air.Div(render_element_block("Left beam", "top_by1"), render_element_block("Right beam", "top_by2"),
                    class_="grid-2", style="margin-bottom: 24px;"),
            air.H4("Column above",
                   style="border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin-bottom: 16px;"),
            render_element_block("Column above", "top_ca", is_col=True),
            air.Button("Save & Close", type="button",
                       onclick=f"document.getElementById('{modal_id}').style.display='none'",
                       style="width: 100%; margin-top: 16px; background-color: #10b981; border: none;"),
            style=content_style
        ), id=modal_id, style=modal_style
    )


def build_scwb_element(d_res, title):
    if not d_res.exists:
        return air.Div(air.H5(title, style="margin-bottom: 8px; color: #4b5563; font-size: 15px;"),
                       air.P("No beams defined.", style="font-size: 13px; color: #6b7280;"))
    c_scwb = "#16A34A" if d_res.ratio_scwb >= 1.2 else "#DC2626"
    c_vj = "#16A34A" if d_res.ratio_vj <= 1.0 else "#DC2626"
    return air.Div(
        air.H5(title, style="margin-bottom: 8px; color: #4b5563; font-size: 15px;"),
        air.Ul(
            air.Li(air.Strong("ΣMnc/ΣMnb"),
                   air.Span(f"{d_res.ratio_scwb:.2f} ≥ 1.2", style=f"color: {c_scwb}; font-weight: bold;")),
            air.Li(air.Strong("Factored shear Vj"), f"{d_res.vj_u:.1f} kN"),
            air.Li(air.Strong("Joint capacity ɸVnj"), f"{d_res.phi_vj:.1f} kN (γ = {d_res.gamma})"),
            air.Li(air.Strong("Joint shear DCR"),
                   air.Span(f"{d_res.ratio_vj:.2f} ≤ 1.0", style=f"color: {c_vj}; font-weight: bold;"))
        )
    )


# ----------------------------------------------------------------------
# 3. MODULE ROUTES
# ----------------------------------------------------------------------
def setup_column_routes(app):
    @app.get("/column")
    def column_index(request: air.Request):
        data = ColumnDesignModel(**json.loads(request.cookies.get("col_inputs", "{}"))) if request.cookies.get(
            "col_inputs") else ColumnDesignModel()
        if not data.proj_date: data.proj_date = date.today().strftime("%Y-%m-%d")
        csrf_token = getattr(request.state, "csrf_token", request.cookies.get("csrftoken", "dev_token"))
        bar_opts = ["D16", "D20", "D25", "D28", "D32", "D36"]
        tie_opts = ["D10", "D12", "D16"]
        js_toggle = "var s=document.getElementsByName('sdc')[0].value; var f=document.getElementsByName('frame_system')[0].value; document.getElementById('seismic_joint_panel').style.display = ((s==='D'||s==='E'||s==='F')&&f==='special') ? 'block' : 'none';"

        return expressive_layout(
            air.Header(air.A("← Dashboard", href="/", class_="back-link no-print"), air.H1("RC Column Designer"),
                       air.P("in accordance with ACI 318M-25", class_="subtitle"),
                       class_="module-header"),
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
                            air.Div(air.Label("Width along x (mm)"),
                                    air.Input(type="number", name="width", value=str(data.width), required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Width along y (mm)"),
                                    air.Input(type="number", name="depth", value=str(data.depth), required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Floor-to-floor height (mm)"),
                                    air.Input(type="number", name="height", value=str(data.height), required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Clear Height (mm)"),
                                    air.Input(type="number", name="clear_height", value=str(data.clear_height),
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Seismic Design Category"),
                                    air.Select(air.Option("A", value="A", selected=(data.sdc == "A")),
                                               air.Option("B", value="B", selected=(data.sdc == "B")),
                                               air.Option("C", value="C", selected=(data.sdc == "C")),
                                               air.Option("D", value="D", selected=(data.sdc == "D")),
                                               air.Option("E", value="E", selected=(data.sdc == "E")),
                                               air.Option("F", value="F", selected=(data.sdc == "F")), name="sdc",
                                               onchange=js_toggle), class_="form-group"),
                            air.Div(air.Label("Moment frame system"), air.Select(
                                air.Option("Ordinary (OMF)", value="ordinary", selected=(data.frame_system == "ordinary")),
                                air.Option("Intermediate (IMF)", value="intermediate",
                                           selected=(data.frame_system == "intermediate")),
                                air.Option("Special (SMF)", value="special", selected=(data.frame_system == "special")),
                                name="frame_system", onchange=js_toggle), class_="form-group"),
                            air.Div(air.Label("Concrete strength (MPa)"),
                                    air.Input(type="number", name="fc_prime", value=str(data.fc_prime), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Main bar yield strength (MPa)"),
                                    air.Input(type="number", name="fy", value=str(data.fy), step="any", required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Tie yield strength (MPa)"),
                                    air.Input(type="number", name="fyt", value=str(data.fyt), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Main bar diameter"),
                                    air.Select(*[air.Option(opt, selected=(data.pref_main == opt)) for opt in bar_opts],
                                               name="pref_main"), class_="form-group"),
                            air.Div(air.Label("Tie diameter"),
                                    air.Select(*[air.Option(opt, selected=(data.pref_tie == opt)) for opt in tie_opts],
                                               name="pref_tie"), class_="form-group"),
                            class_="grid-3"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Loads"),
                        air.Div(air.Label("Factored axial Pu (kN)"),
                                air.Input(type="number", name="pu", value=str(data.pu), step="any", required=True),
                                class_="form-group"),
                        air.Div(
                            air.Div(
                                air.H3("Column Top"),
                                air.Div(air.Label("Factored moment Mux (kN·m)"),
                                        air.Input(type="number", name="top_mux", value=str(data.top_mux), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Factored moment Muy (kN·m)"),
                                        air.Input(type="number", name="top_muy", value=str(data.top_muy), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Factored shear Vux (kN)"),
                                        air.Input(type="number", name="top_vux", value=str(data.top_vux), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Factored shear Vuy (kN)"),
                                        air.Input(type="number", name="top_vuy", value=str(data.top_vuy), step="any",
                                                  required=True), class_="form-group"),
                                class_="section-box"
                            ),
                            air.Div(
                                air.H3("Column Bottom"),
                                air.Div(air.Label("Factored moment Mux (kN·m)"),
                                        air.Input(type="number", name="bot_mux", value=str(data.bot_mux), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Factored moment Muy (kN·m)"),
                                        air.Input(type="number", name="bot_muy", value=str(data.bot_muy), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Factored shear Vux (kN)"),
                                        air.Input(type="number", name="bot_vux", value=str(data.bot_vux), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Factored shear Vuy (kN)"),
                                        air.Input(type="number", name="bot_vuy", value=str(data.bot_vuy), step="any",
                                                  required=True), class_="form-group"),
                                class_="section-box"
                            ),
                            class_="grid-2"
                        ),
                        air.Div(
                            air.H3("Seismic Joint Checks"),
                            air.Button("Define Elements", type="button",
                                       onclick="document.getElementById('topModal').style.display='block'",
                                       style="background-color: #3b82f6; border:none;"),
                            id="seismic_joint_panel",
                            style=f"display: {'block' if data.sdc in ['D', 'E', 'F'] and data.frame_system == 'special' else 'none'}; margin-top: 24px; padding: 24px; background: #eff6ff; border-radius: 8px;"
                        ),
                        render_top_joint_modal("topModal", data),
                        air.Button("Analyze Column", type="submit",
                                   style="width: 100%; font-size: 18px; margin-top: 32px;"),
                        class_="card"
                    ), method="post", action="/column/design"
                )
            )
        )

    @app.post("/column/design")
    async def column_design(request: air.Request):
        form_data = await request.form()
        try:
            data = ColumnDesignModel(**form_data)
        except Exception as e:
            return AirResponse(content=str(expressive_layout(
                air.Main(air.Div(air.H2("Validation Failed", style="color: #DC2626;"), air.P(str(e)), class_="card")))),
                               media_type="text/html")

        try:
            frame_enum = FrameSystem(data.frame_system)
            mat = MaterialProperties(fc_prime=data.fc_prime, fy=data.fy, fu=data.fy * 1.25, fyt=data.fyt,
                                     fut=data.fyt * 1.25, es=200000.0,
                                     ec=base_aci_lib.aci.get_concrete_modulus(data.fc_prime), gamma_c=24.0,
                                     description="")
            geom = ColumnGeometry(data.width, data.depth, data.height, data.clear_height, 40.0, ColumnShape.RECTANGULAR,
                                  ColumnType.TIED, data.height, SeismicDesignCategory(data.sdc), frame_enum)
            loads = ColumnLoads(data.pu, max(abs(data.top_mux), abs(data.bot_mux)),
                                max(abs(data.top_muy), abs(data.bot_muy)), max(abs(data.top_vux), abs(data.bot_vux)),
                                max(abs(data.top_vuy), abs(data.bot_vuy)), LoadCondition.BIAXIAL_BENDING)

            engine = ACI318M25ColumnDesign()
            engine.reinforcement_limits['min_bar_size'] = data.pref_main
            res = engine.perform_complete_column_design(loads, geom, mat, data.pref_main, data.pref_tie)

            def get_as(qty, dia):
                return qty * base_aci_lib.aci.get_bar_area(dia)

            bx1_as_top = get_as(data.top_bx1_qty_top, data.top_bx1_dia_top)
            bx1_as_bot = get_as(data.top_bx1_qty_bot, data.top_bx1_dia_bot)
            bx2_as_top = get_as(data.top_bx2_qty_top, data.top_bx2_dia_top)
            bx2_as_bot = get_as(data.top_bx2_qty_bot, data.top_bx2_dia_bot)

            by1_as_top = get_as(data.top_by1_qty_top, data.top_by1_dia_top)
            by1_as_bot = get_as(data.top_by1_qty_bot, data.top_by1_dia_bot)
            by2_as_top = get_as(data.top_by2_qty_top, data.top_by2_dia_top)
            by2_as_bot = get_as(data.top_by2_qty_bot, data.top_by2_dia_bot)

            ca_as = get_as(data.top_ca_qty, data.top_ca_dia)

            loads_table = air.Table(
                air.Thead(air.Tr(air.Th("Force"), air.Th("Top Joint"), air.Th("Bot Joint"))),
                air.Tbody(
                    air.Tr(air.Td(air.Strong("Pu (kN)")),
                           air.Td(str(data.pu), colspan="2", style="text-align: center;")),
                    air.Tr(air.Td(air.Strong("Mux (kN·m)")), air.Td(str(data.top_mux)), air.Td(str(data.bot_mux))),
                    air.Tr(air.Td(air.Strong("Muy (kN·m)")), air.Td(str(data.top_muy)), air.Td(str(data.bot_muy))),
                    air.Tr(air.Td(air.Strong("Vux (kN)")), air.Td(str(data.top_vux)), air.Td(str(data.bot_vux))),
                    air.Tr(air.Td(air.Strong("Vuy (kN)")), air.Td(str(data.top_vuy)), air.Td(str(data.bot_vuy)))
                )
            )

            input_content = [
                air.Div(
                    air.H3("Geometry and Materials",
                           style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                    air.Ul(
                        air.Li(air.Strong("Dimensions"),
                               air.Span(f"{data.width}mm × {data.depth}mm (Lu = {data.clear_height}mm)",
                                        class_="data-value")),
                        air.Li(air.Strong("Seismic"),
                               air.Span(f"SDC {data.sdc}, {frame_enum.value.title()}", class_="data-value")),
                        air.Li(air.Strong("Concrete"), air.Span(f"f'c = {data.fc_prime} MPa", class_="data-value")),
                        air.Li(air.Strong("Steel"),
                               air.Span(f"fy = {data.fy} MPa, fyt = {data.fyt} MPa", class_="data-value")),
                        air.Li(air.Strong("Rebar sizes"),
                               air.Span(f"Main {data.pref_main}, Ties {data.pref_tie}", class_="data-value")),
                    ), class_="section-box"
                ),
                air.Div(
                    air.H3("Loads", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                    loads_table, class_="section-box"
                )
            ]

            sc_wb_element = ""
            if data.sdc in ["D", "E", "F"] and data.frame_system == "special":
                j_res = engine.evaluate_top_joint_seismic(
                    geom, mat, res,
                    JointBeamElement(data.top_bx1_exists == 'yes', data.top_bx1_b, data.top_bx1_d, bx1_as_top,
                                     bx1_as_bot),
                    JointBeamElement(data.top_bx2_exists == 'yes', data.top_bx2_b, data.top_bx2_d, bx2_as_top,
                                     bx2_as_bot),
                    JointBeamElement(data.top_by1_exists == 'yes', data.top_by1_b, data.top_by1_d, by1_as_top,
                                     by1_as_bot),
                    JointBeamElement(data.top_by2_exists == 'yes', data.top_by2_b, data.top_by2_d, by2_as_top,
                                     by2_as_bot),
                    JointColumnElement(data.top_ca_exists == 'yes', data.top_ca_b, data.top_ca_h, ca_as,
                                       data.top_ca_pu), data.pu
                )
                res.design_notes.extend(j_res.notes)
                sc_wb_element = air.Div(
                    air.H4("Seismic Joint Checks", style="color: #1e3a8a; margin-bottom: 12px;"),
                    air.Div(build_scwb_element(j_res.x_dir, "x-direction"),
                            build_scwb_element(j_res.y_dir, "y-direction"), class_="grid-2"),
                    style="margin-top: 16px; padding: 12px; background: #f0fdf4; border-radius: 6px; border: 1px dashed #bbf7d0;"
                )

                def f_beam(exists, b, d, qt, dt, qb,
                           db): return f"{b}mm x {d}mm (Top: {qt}-{dt}, Bot: {qb}-{db})" if exists == 'yes' else "None"

                def f_col(exists, b, h, q, d_dia,
                          pu): return f"{b}mm x {h}mm ({q}-{d_dia}, Pu = {pu} kN)" if exists == 'yes' else "None"

                input_content.append(
                    air.Div(
                        air.H3("Top Joint Elements",
                               style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                        air.Ul(
                            air.Li(air.Strong("Beam left (x)"), air.Span(
                                f_beam(data.top_bx1_exists, data.top_bx1_b, data.top_bx1_d, data.top_bx1_qty_top,
                                       data.top_bx1_dia_top, data.top_bx1_qty_bot, data.top_bx1_dia_bot),
                                class_="data-value")),
                            air.Li(air.Strong("Beam right (x)"), air.Span(
                                f_beam(data.top_bx2_exists, data.top_bx2_b, data.top_bx2_d, data.top_bx2_qty_top,
                                       data.top_bx2_dia_top, data.top_bx2_qty_bot, data.top_bx2_dia_bot),
                                class_="data-value")),
                            air.Li(air.Strong("Beam left (y)"), air.Span(
                                f_beam(data.top_by1_exists, data.top_by1_b, data.top_by1_d, data.top_by1_qty_top,
                                       data.top_by1_dia_top, data.top_by1_qty_bot, data.top_by1_dia_bot),
                                class_="data-value")),
                            air.Li(air.Strong("Beam right (y)"), air.Span(
                                f_beam(data.top_by2_exists, data.top_by2_b, data.top_by2_d, data.top_by2_qty_top,
                                       data.top_by2_dia_top, data.top_by2_qty_bot, data.top_by2_dia_bot),
                                class_="data-value")),
                            air.Li(air.Strong("Column above"), air.Span(
                                f_col(data.top_ca_exists, data.top_ca_b, data.top_ca_h, data.top_ca_qty,
                                      data.top_ca_dia, data.top_ca_pu), class_="data-value"))
                        ), class_="section-box"
                    )
                )

            qto = engine.calculate_qto(geom, res)
            rebar_rows = [
                air.Tr(air.Td(air.Strong(r.name)), air.Td(r.size), air.Td(str(r.qty)), air.Td(f"{r.cut_length:.2f}m"),
                       air.Td(r.order), air.Td(f"{r.weight:.1f} kg")) for r in qto.rows]

            n_bars = len(res.reinforcement.longitudinal_bars)
            s_outside = max(50.0, math.floor((min(150.0, 6.0 * float(
                data.pref_main.replace('D', ''))) if data.frame_system == 'special' else min(
                16 * float(data.pref_main.replace('D', '')), min(data.width, data.depth))) / 10.0) * 10.0)
            tie_hinge_str = f"{res.reinforcement.tie_legs_x}x{res.reinforcement.tie_legs_y} legs {res.reinforcement.tie_bars} @ {res.reinforcement.tie_spacing:.0f} mm"
            tie_mid_str = f"{res.reinforcement.tie_legs_x}x{res.reinforcement.tie_legs_y} legs {res.reinforcement.tie_bars} @ {s_outside:.0f} mm"

            notes_elements = [air.Ul(*[air.Li(f"{'⚠️' if 'Violation' in n or 'CRITICAL' in n else 'ℹ️'} {n}") for n in
                                       set(res.design_notes)], class_="notes-list")] if res.design_notes else []

            report_content = air.Main(
                air.Div(
                    air.Button("🖨️ Save as PDF", onclick="window.print()", style="background-color: var(--secondary);"),
                    style="margin-bottom: 24px; display: flex; justify-content: flex-end;", class_="no-print"),
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
                    air.Div(*input_content, class_="grid-3" if len(input_content) == 3 else "grid-2"),
                    class_="card"
                ),
                air.Div(class_="page-break"),
                air.Div(air.H2("Design Results"), air.Div(
                    air.Div(
                        generate_column_section_css(data.width, data.depth, 40.0, n_bars, res.reinforcement.tie_legs_x,
                                                    res.reinforcement.tie_legs_y),
                        generate_column_elevation_css(data.height, data.clear_height, max(data.width, data.depth),
                                                      res.reinforcement.tie_spacing, s_outside),
                        style="display: flex; flex-direction: column; gap: 16px;"
                    ),
                    air.Div(
                        air.H3("DCR"),
                        air.Ul(
                            air.Li(air.Strong("P-M interaction"),
                                   air.Span(f"{res.capacity.interaction_ratio:.2f}", class_="data-value",
                                            style=f"color: {'#16A34A' if res.capacity.interaction_ratio <= 1.0 else '#DC2626'}; font-weight: bold;")),
                            air.Li(air.Strong("Shear (x / y)"),
                                   air.Span(f"{res.shear_utilization_x:.2f} / {res.shear_utilization_y:.2f}",
                                            class_="data-value")),
                        ),
                        air.H3("Reinforcement Details", style="margin-top: 24px;"),
                        air.Ul(
                            air.Li(air.Strong("Vertical bars"),
                                   air.Span(f"{n_bars}x{data.pref_main}", class_="data-value",
                                            style="color: #2563eb; font-weight: bold;")),
                            air.Li(air.Strong("Ties (support)"), air.Span(tie_hinge_str, class_="data-value",
                                                                          style="color: #db2777; font-weight: bold;")),
                            air.Li(air.Strong("Ties (midheight)"),
                                   air.Span(tie_mid_str, class_="data-value", style="color: #db2777;")),
                        ), sc_wb_element, class_="section-box", style="height: 100%;"
                    ), class_="grid-2"),
                        air.Div(air.H4("Design Notes", style="margin-top: 20px; color: #92400e;"), *notes_elements,
                                style="padding: 16px; background: #fffbeb; border-radius: 8px; border: 1px solid #fde68a; margin-top: 20px;"),
                        class_="card"
                        ),
                air.Div(air.H2("Material Takeoff"), air.Div(
                    air.Div(air.Div("Concrete", class_="metric-label"),
                            air.Div(f"{qto.volume:.2f} m³", class_="metric-value"), class_="metric-card"),
                    air.Div(air.Div("Formwork", class_="metric-label"),
                            air.Div(f"{qto.formwork:.2f} m²", class_="metric-value"), class_="metric-card blue"),
                    air.Div(air.Div("Rebar Weight", class_="metric-label"),
                            air.Div(f"{qto.total_weight:.1f} kg", class_="metric-value"), class_="metric-card green"),
                    class_="grid-3"),
                        air.Table(air.Thead(
                            air.Tr(air.Th("Location"), air.Th("Size"), air.Th("Qty"), air.Th("Cut Length"),
                                   air.Th("Order"), air.Th("Weight"))), air.Tbody(*rebar_rows)), class_="card"
                        )
            )

            resp = AirResponse(content=str(expressive_layout(
                air.Header(air.A("← Edit Inputs", href="/column", class_="back-link no-print"),
                           air.H1("RC Column Designer"),
                       air.P("in accordance with ACI 318M-25", class_="subtitle"), class_="module-header"), report_content)),
                               media_type="text/html")
            resp.set_cookie("col_inputs", json.dumps(dict(form_data)), max_age=2592000)
            return resp

        except Exception as e:
            return AirResponse(content=str(expressive_layout(
                air.Main(air.Div(air.H2("Validation Failed", style="color: #DC2626;"), air.P(str(e)), class_="card")))),
                               media_type="text/html")