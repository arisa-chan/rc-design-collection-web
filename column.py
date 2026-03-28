import air
from air import AirField, AirResponse
from pydantic import BaseModel
import math
import json
from datetime import date

# Import the ACI 318M-25 library components
from aci318m25 import ConcreteStrengthClass, ReinforcementGrade, MaterialProperties
from aci318m25_complete import ACI318M25MemberLibrary
from aci318m25_column import ACI318M25ColumnDesign, ColumnGeometry, ColumnLoads, ColumnType, ColumnShape, LoadCondition, \
    SeismicDesignCategory, FrameSystem
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

    # Geometry
    width: float = AirField(default=500.0)  # b (X-axis)
    depth: float = AirField(default=500.0)  # h (Y-axis)
    height: float = AirField(default=3200.0)  # Total height Center-to-Center
    clear_height: float = AirField(default=2800.0)  # lu

    # Seismic & Materials
    sdc: str = AirField(default="D")
    frame_system: str = AirField(default="special")
    pref_main: str = AirField(default="D25")
    pref_tie: str = AirField(default="D12")
    fc_prime: float = AirField(default=28.0)
    fy: float = AirField(default=415.0)
    fyt: float = AirField(default=415.0)

    # Column Loads
    pu: float = AirField(default=2500.0)

    top_mux: float = AirField(default=150.0)
    top_muy: float = AirField(default=80.0)
    top_vux: float = AirField(default=120.0)
    top_vuy: float = AirField(default=90.0)

    bot_mux: float = AirField(default=180.0)
    bot_muy: float = AirField(default=90.0)
    bot_vux: float = AirField(default=120.0)
    bot_vuy: float = AirField(default=90.0)

    # Beam details (Top Joint) - For SC/WB Check
    top_b1_b: float = AirField(default=300.0)
    top_b1_d: float = AirField(default=440.0)
    top_b1_as_top: float = AirField(default=1200.0)
    top_b1_as_bot: float = AirField(default=600.0)
    top_b2_b: float = AirField(default=300.0)
    top_b2_d: float = AirField(default=440.0)
    top_b2_as_top: float = AirField(default=1200.0)
    top_b2_as_bot: float = AirField(default=600.0)

    # Beam details (Bottom Joint) - For SC/WB Check
    bot_b1_b: float = AirField(default=300.0)
    bot_b1_d: float = AirField(default=440.0)
    bot_b1_as_top: float = AirField(default=1200.0)
    bot_b1_as_bot: float = AirField(default=600.0)
    bot_b2_b: float = AirField(default=300.0)
    bot_b2_d: float = AirField(default=440.0)
    bot_b2_as_top: float = AirField(default=1200.0)
    bot_b2_as_bot: float = AirField(default=600.0)


# ----------------------------------------------------------------------
# 2. OVERRIDE ENGINE & QTO ALGORITHMS
# ----------------------------------------------------------------------
class ControlledColumnDesign(ACI318M25ColumnDesign):
    def __init__(self, pref_main: str, pref_tie: str):
        super().__init__()
        self.pref_main = pref_main
        self.pref_tie = pref_tie

    def select_longitudinal_reinforcement(self, As_required: float, geometry: ColumnGeometry,
                                          aggregate_size: float = 25.0, assumed_tie: str = 'D10') -> list:
        if As_required <= 0: return []
        area = self.aci.get_bar_area(self.pref_main)
        min_bars = 4 if geometry.shape == ColumnShape.RECTANGULAR else 6
        num_bars = max(min_bars, math.ceil(As_required / area))

        if geometry.shape == ColumnShape.RECTANGULAR and num_bars % 2 != 0:
            num_bars += 1

        return [self.pref_main] * num_bars


def get_beam_capacities(b, d, as_top, as_bot, fc, fy):
    """Calculates Nominal and Probable Flexural Capacities of a single beam framing into a joint."""
    if b <= 0 or d <= 0: return 0, 0, 0, 0
    fy_pr = 1.25 * fy

    # Nominal Capacities (Mnb) - using fy
    a_top = (as_top * fy) / (0.85 * fc * b) if b > 0 else 0
    mn_neg = as_top * fy * (d - a_top / 2.0) / 1e6 if as_top > 0 else 0

    a_bot = (as_bot * fy) / (0.85 * fc * b) if b > 0 else 0
    mn_pos = as_bot * fy * (d - a_bot / 2.0) / 1e6 if as_bot > 0 else 0

    # Probable Capacities (Mpr) - using 1.25fy
    a_pr_top = (as_top * fy_pr) / (0.85 * fc * b) if b > 0 else 0
    mpr_neg = as_top * fy_pr * (d - a_pr_top / 2.0) / 1e6 if as_top > 0 else 0

    a_pr_bot = (as_bot * fy_pr) / (0.85 * fc * b) if b > 0 else 0
    mpr_pos = as_bot * fy_pr * (d - a_pr_bot / 2.0) / 1e6 if as_bot > 0 else 0

    return mn_neg, mn_pos, mpr_neg, mpr_pos


def calculate_column_qto(geom: ColumnGeometry, res: 'ColumnAnalysisResult'):
    b_m, h_m, L_m = geom.width / 1000.0, geom.depth / 1000.0, geom.height / 1000.0
    vol_concrete = b_m * h_m * L_m
    area_formwork = (2 * (b_m + h_m) + 0.1) * L_m
    rebar_rows, total_kg = [], 0.0

    def get_db(bar_str):
        if not bar_str: return 0.0
        val = bar_str.split(" ")[1] if "-leg" in bar_str else bar_str
        try:
            return float(val.replace('D', ''))
        except:
            return 16.0

    def get_best_commercial_order(req_len, qty, db_mm):
        stocks = [6.0, 7.5, 9.0, 10.5, 12.0]
        splice_m = 40 * db_mm / 1000.0

        if req_len > 12.0:
            eff_12 = 12.0 - splice_m
            num_12 = int(req_len // eff_12)
            rem = req_len - num_12 * eff_12
            if rem > 0: rem += splice_m

            best_waste, best_S, best_count = float('inf'), 12.0, 0
            if rem > 0:
                for S in stocks:
                    if S >= rem:
                        pieces_per_S = int(S // rem)
                        if pieces_per_S > 0:
                            count = math.ceil(qty / pieces_per_S)
                            waste = count * S - (qty * rem)
                            if waste < best_waste:
                                best_waste, best_S, best_count = waste, S, count

            total_12m = num_12 * qty
            order_parts = []
            if total_12m > 0: order_parts.append(f"{total_12m} x 12.0m")
            if rem > 0 and best_count > 0: order_parts.append(f"{best_count} x {best_S}m")
            return " + ".join(order_parts), (total_12m * 12.0 + (best_count * best_S if rem > 0 else 0))
        else:
            best_waste, best_S, best_count = float('inf'), 12.0, 0
            for S in stocks:
                if S >= req_len:
                    pieces_per_S = int(S // req_len)
                    if pieces_per_S > 0:
                        count = math.ceil(qty / pieces_per_S)
                        waste = count * S - (qty * req_len)
                        if waste < best_waste:
                            best_waste, best_S, best_count = waste, S, count
            return f"{best_count} x {best_S}m", best_count * best_S

    def add_rebar(name, bars_list, base_len, splice_factor=40.0):
        nonlocal total_kg
        if not bars_list: return
        db = get_db(bars_list[0])
        if db == 0: return
        num_bars = len(bars_list)
        req_len = base_len + (splice_factor * db / 1000.0)
        stock_text, total_ordered_m = get_best_commercial_order(req_len, num_bars, db)
        weight_kg = total_ordered_m * ((db ** 2) / 162.0)
        total_kg += weight_kg
        rebar_rows.append(
            air.Tr(air.Td(air.Strong(name)), air.Td(f"D{int(db)}"), air.Td(str(num_bars)), air.Td(f"{req_len:.2f}m"),
                   air.Td(air.Span(stock_text, style="color: #2563eb; font-weight: 600;")),
                   air.Td(f"{weight_kg:.1f} kg")))

    add_rebar("Main Longitudinal", res.reinforcement.longitudinal_bars, L_m, splice_factor=40.0)

    s_m = max(res.reinforcement.tie_spacing, 50.0) / 1000.0
    total_stirrups = int(L_m / s_m)

    if total_stirrups > 0:
        db_t = get_db(res.reinforcement.tie_bars)
        c_m = geom.cover / 1000.0
        legs_x, legs_y = res.reinforcement.tie_legs_x, res.reinforcement.tie_legs_y

        outer_len = 2 * (b_m - 2 * c_m) + 2 * (h_m - 2 * c_m) + 24 * db_t / 1000.0
        cross_ties_len = max(0, legs_y - 2) * (h_m - 2 * c_m + 24 * db_t / 1000.0) + max(0, legs_x - 2) * (
                    b_m - 2 * c_m + 24 * db_t / 1000.0)
        tie_len_m = outer_len + cross_ties_len

        total_tie_length_m = total_stirrups * tie_len_m
        num_12m_bars = math.ceil(total_tie_length_m / 12.0)
        weight_kg = num_12m_bars * 12.0 * ((db_t ** 2) / 162.0)
        total_kg += weight_kg
        rebar_rows.append(air.Tr(air.Td(air.Strong(f"Ties ({legs_x}x{legs_y} legs)")), air.Td(f"D{int(db_t)}"),
                                 air.Td(str(total_stirrups)), air.Td(f"{tie_len_m:.2f}m"),
                                 air.Td(f"{num_12m_bars} x 12.0m", style="color: #db2777; font-weight: 600;"),
                                 air.Td(f"{weight_kg:.1f} kg")))

    return vol_concrete, area_formwork, total_kg, rebar_rows


# ----------------------------------------------------------------------
# 3. VISUALIZATION COMPONENTS
# ----------------------------------------------------------------------
def generate_column_section_css(width, depth, cover, num_bars, legs_x, legs_y):
    scale = min(200 / max(width, 1), 200 / max(depth, 1))
    draw_w, draw_h, c_s = width * scale, depth * scale, cover * scale

    children = []
    core_w, core_h = draw_w - 2 * c_s, draw_h - 2 * c_s

    if core_w > 0 and core_h > 0:
        # Outer Tie
        children.append(air.Div(
            style=f"position: absolute; left: {c_s}px; top: {c_s}px; width: {core_w}px; height: {core_h}px; border: 2px dashed #db2777; border-radius: 4px; box-sizing: border-box;"))
        # Inner Ties (X)
        if legs_x > 2:
            spacing_x = core_w / (legs_x - 1)
            for i in range(1, legs_x - 1):
                children.append(air.Div(
                    style=f"position: absolute; left: {c_s + i * spacing_x}px; top: {c_s}px; width: 0px; height: {core_h}px; border-left: 2px dashed #db2777; box-sizing: border-box;"))
        # Inner Ties (Y)
        if legs_y > 2:
            spacing_y = core_h / (legs_y - 1)
            for i in range(1, legs_y - 1):
                children.append(air.Div(
                    style=f"position: absolute; left: {c_s}px; top: {c_s + i * spacing_y}px; width: {core_w}px; height: 0px; border-top: 2px dashed #db2777; box-sizing: border-box;"))

    def add_bar(x, y):
        children.append(air.Div(
            style=f"position: absolute; left: {x - 6}px; top: {y - 6}px; width: 12px; height: 12px; background: #2563eb; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))

    # FIX: Calculate exact bar distribution using the mathematical engine logic
    nx_face = 0
    ny_face = 0
    if num_bars > 4:
        rem = num_bars - 4
        ratio = width / (width + depth) if (width + depth) > 0 else 0.5
        nx_inter = 2 * int(round(rem * ratio / 2.0))
        ny_inter = rem - nx_inter
        nx_face = nx_inter // 2
        ny_face = ny_inter // 2

    if core_w >= 0 and core_h >= 0:
        # 4 Corners
        add_bar(c_s, c_s)
        add_bar(c_s + core_w, c_s)
        add_bar(c_s, c_s + core_h)
        add_bar(c_s + core_w, c_s + core_h)

        # Top and Bottom faces
        if nx_face > 0:
            sp_x = core_w / (nx_face + 1)
            for i in range(1, nx_face + 1):
                add_bar(c_s + i * sp_x, c_s)
                add_bar(c_s + i * sp_x, c_s + core_h)

        # Left and Right faces
        if ny_face > 0:
            sp_y = core_h / (ny_face + 1)
            for i in range(1, ny_face + 1):
                add_bar(c_s, c_s + i * sp_y)
                add_bar(c_s + core_w, c_s + i * sp_y)

    concrete_block = air.Div(*children,
                             style=f"position: relative; width: {draw_w}px; height: {draw_h}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px; box-sizing: border-box;")
    return air.Div(
        air.Div(f"{width} mm",
                style="text-align: center; font-family: monospace; font-weight: 700; color: #6b7280; margin-bottom: 8px;"),
        air.Div(air.Div(f"{depth} mm",
                        style="position: absolute; left: -65px; top: 50%; transform: translateY(-50%); font-family: monospace; font-weight: 700; color: #6b7280;"),
                concrete_block, style="position: relative; display: inline-block; margin-left: 40px;"),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px 0; background: #ffffff; border-radius: 8px; border: 2px dashed #e5e7eb; height: 100%;"
    )


def render_beam_modal(modal_id, title, prefix, data):
    modal_style = "display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6);"
    content_style = "background-color: #fefefe; margin: 5% auto; padding: 24px; border: 1px solid #888; width: 90%; max-width: 600px; border-radius: 8px; position: relative;"
    close_style = "color: #aaa; position: absolute; right: 20px; top: 15px; font-size: 28px; font-weight: bold; cursor: pointer;"

    return air.Div(
        air.Div(
            air.Span("×", style=close_style, onclick=f"document.getElementById('{modal_id}').style.display='none'"),
            air.H3(title, style="margin-bottom: 24px; color: #1e3a8a;"),
            air.Div(
                air.Div(
                    air.H4("Beam 1 (e.g., Left Face)", style="margin-bottom: 12px; color: #4b5563;"),
                    air.Div(air.Label("Width b (mm)"),
                            air.Input(type="number", name=f"{prefix}_b1_b", value=str(getattr(data, f"{prefix}_b1_b")),
                                      step="any"), class_="form-group"),
                    air.Div(air.Label("Eff. Depth d (mm)"),
                            air.Input(type="number", name=f"{prefix}_b1_d", value=str(getattr(data, f"{prefix}_b1_d")),
                                      step="any"), class_="form-group"),
                    air.Div(air.Label("As Top (mm²)"), air.Input(type="number", name=f"{prefix}_b1_as_top",
                                                                 value=str(getattr(data, f"{prefix}_b1_as_top")),
                                                                 step="any"), class_="form-group"),
                    air.Div(air.Label("As Bot (mm²)"), air.Input(type="number", name=f"{prefix}_b1_as_bot",
                                                                 value=str(getattr(data, f"{prefix}_b1_as_bot")),
                                                                 step="any"), class_="form-group"),
                    class_="section-box"
                ),
                air.Div(
                    air.H4("Beam 2 (e.g., Right Face)", style="margin-bottom: 12px; color: #4b5563;"),
                    air.Div(air.Label("Width b (mm)"),
                            air.Input(type="number", name=f"{prefix}_b2_b", value=str(getattr(data, f"{prefix}_b2_b")),
                                      step="any"), class_="form-group"),
                    air.Div(air.Label("Eff. Depth d (mm)"),
                            air.Input(type="number", name=f"{prefix}_b2_d", value=str(getattr(data, f"{prefix}_b2_d")),
                                      step="any"), class_="form-group"),
                    air.Div(air.Label("As Top (mm²)"), air.Input(type="number", name=f"{prefix}_b2_as_top",
                                                                 value=str(getattr(data, f"{prefix}_b2_as_top")),
                                                                 step="any"), class_="form-group"),
                    air.Div(air.Label("As Bot (mm²)"), air.Input(type="number", name=f"{prefix}_b2_as_bot",
                                                                 value=str(getattr(data, f"{prefix}_b2_as_bot")),
                                                                 step="any"), class_="form-group"),
                    class_="section-box"
                ),
                class_="grid-2"
            ),
            air.Button("Save & Close", type="button",
                       onclick=f"document.getElementById('{modal_id}').style.display='none'",
                       style="width: 100%; margin-top: 16px; background-color: #10b981; border: none;"),
            style=content_style
        ),
        id=modal_id, style=modal_style
    )


# ----------------------------------------------------------------------
# 4. MODULE ROUTES
# ----------------------------------------------------------------------
def setup_column_routes(app):
    @app.get("/column")
    def column_index(request: air.Request):
        data = ColumnDesignModel()
        saved_inputs = request.cookies.get("col_inputs")
        if saved_inputs:
            try:
                parsed = json.loads(saved_inputs)
                data = ColumnDesignModel(**parsed)
            except Exception:
                pass

        if not data.proj_date: data.proj_date = date.today().strftime("%Y-%m-%d")

        csrf_token = getattr(request.state, "csrf_token", request.cookies.get("csrftoken", "dev_token"))
        bar_opts = ["D16", "D20", "D25", "D28", "D32", "D36"]
        tie_opts = ["D10", "D12", "D16"]

        show_seismic = data.sdc in ["D", "E", "F"] and data.frame_system == "special"
        panel_display = "block" if show_seismic else "none"

        js_toggle = "var s=document.getElementsByName('sdc')[0].value; var f=document.getElementsByName('frame_system')[0].value; var p=document.getElementById('seismic_joint_panel'); if((s==='D'||s==='E'||s==='F')&&f==='special'){p.style.display='block';}else{p.style.display='none';}"

        return expressive_layout(
            air.Header(
                air.A("← Dashboard", href="/", class_="back-link no-print"),
                air.H1("RC Column Designer"),
                air.P("in accordance with ACI 318M-25 (P-M Interaction & Seismic)", class_="subtitle"),
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
                            air.Div(air.Label("Section Width - b (mm)"),
                                    air.Input(type="number", name="width", value=str(data.width), required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Section Depth - h (mm)"),
                                    air.Input(type="number", name="depth", value=str(data.depth), required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Total C-C Height (mm)"),
                                    air.Input(type="number", name="height", value=str(data.height), required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Clear Height - lu (mm)"),
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
                                air.Option("Ordinary (OMF)", value="ordinary",
                                           selected=(data.frame_system == "ordinary")),
                                air.Option("Intermediate (IMF)", value="intermediate",
                                           selected=(data.frame_system == "intermediate")),
                                air.Option("Special (SMF)", value="special", selected=(data.frame_system == "special")),
                                name="frame_system", onchange=js_toggle), class_="form-group"),

                            air.Div(air.Label("Concrete f'c (MPa)"),
                                    air.Input(type="number", name="fc_prime", value=str(data.fc_prime), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Main bar yield fy (MPa)"),
                                    air.Input(type="number", name="fy", value=str(data.fy), step="any", required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Tie yield fyt (MPa)"),
                                    air.Input(type="number", name="fyt", value=str(data.fyt), step="any",
                                              required=True), class_="form-group"),

                            air.Div(air.Label("Preferred main bar"),
                                    air.Select(*[air.Option(opt, selected=(data.pref_main == opt)) for opt in bar_opts],
                                               name="pref_main"), class_="form-group"),
                            air.Div(air.Label("Preferred tie size"),
                                    air.Select(*[air.Option(opt, selected=(data.pref_tie == opt)) for opt in tie_opts],
                                               name="pref_tie"), class_="form-group"),

                            class_="grid-3"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Factored Loads"),
                        air.Div(
                            air.H3("Axial Load", style="margin-bottom: 12px;"),
                            air.Div(air.Label("Factored Axial Pu (kN)"),
                                    air.Input(type="number", name="pu", value=str(data.pu), step="any", required=True),
                                    class_="form-group"),
                            style="margin-bottom: 24px; border-bottom: 1px solid #e5e7eb; padding-bottom: 16px;"
                        ),
                        air.Div(
                            air.Div(
                                air.H3("Top of Column Forces"),
                                air.Div(air.Label("Moment Mux (kN·m)"),
                                        air.Input(type="number", name="top_mux", value=str(data.top_mux), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Moment Muy (kN·m)"),
                                        air.Input(type="number", name="top_muy", value=str(data.top_muy), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Shear Vux (kN)"),
                                        air.Input(type="number", name="top_vux", value=str(data.top_vux), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Shear Vuy (kN)"),
                                        air.Input(type="number", name="top_vuy", value=str(data.top_vuy), step="any",
                                                  required=True), class_="form-group"),
                                class_="section-box"
                            ),
                            air.Div(
                                air.H3("Bottom of Column Forces"),
                                air.Div(air.Label("Moment Mux (kN·m)"),
                                        air.Input(type="number", name="bot_mux", value=str(data.bot_mux), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Moment Muy (kN·m)"),
                                        air.Input(type="number", name="bot_muy", value=str(data.bot_muy), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Shear Vux (kN)"),
                                        air.Input(type="number", name="bot_vux", value=str(data.bot_vux), step="any",
                                                  required=True), class_="form-group"),
                                air.Div(air.Label("Shear Vuy (kN)"),
                                        air.Input(type="number", name="bot_vuy", value=str(data.bot_vuy), step="any",
                                                  required=True), class_="form-group"),
                                class_="section-box"
                            ),
                            class_="grid-2"
                        ),

                        # SC/WB Seismic Panel
                        air.Div(
                            air.H3("Seismic Joint Demands (SMF Strong-Column/Weak-Beam Check)"),
                            air.P(
                                "To satisfy ACI 18.7.3.2, define the beams framing into the column. The engine will automatically calculate and verify the Mpr (shear) and Mnb (flexure) requirements.",
                                style="color: #4b5563; font-size: 14px; margin-bottom: 16px;"),
                            air.Div(
                                air.Button("Define Top Joint Beams", type="button",
                                           onclick="document.getElementById('topModal').style.display='block'",
                                           style="margin-right: 16px; background-color: #3b82f6; border:none;"),
                                air.Button("Define Bottom Joint Beams", type="button",
                                           onclick="document.getElementById('botModal').style.display='block'",
                                           style="background-color: #3b82f6; border:none;"),
                                style="display: flex;"
                            ),
                            id="seismic_joint_panel",
                            style=f"display: {panel_display}; margin-top: 24px; padding: 24px; background: #eff6ff; border-radius: 8px; border: 1px dashed #93c5fd;"
                        ),

                        render_beam_modal("topModal", "Top Joint Framing Beams", "top", data),
                        render_beam_modal("botModal", "Bottom Joint Framing Beams", "bot", data),

                        air.Button("Analyze Column", type="submit",
                                   style="width: 100%; font-size: 18px; margin-top: 32px;"),
                        class_="card"
                    ),
                    method="post", action="/column/design"
                )
            )
        )

    @app.post("/column/design")
    async def column_design(request: air.Request):
        form_data = await request.form()
        cookie_data = json.dumps(dict(form_data))

        try:
            data = ColumnDesignModel(**form_data)
        except Exception as e:
            error_html = str(expressive_layout(
                air.Main(air.Div(air.H2("Validation Failed", style="color: #DC2626;"), air.P(str(e)), class_="card"))))
            return AirResponse(content=error_html, media_type="text/html")

        try:
            sdc_enum = SeismicDesignCategory(data.sdc)
            frame_enum = FrameSystem(data.frame_system)
            cover = 40.0

            ec = base_aci_lib.aci.get_concrete_modulus(data.fc_prime)
            mat_props = MaterialProperties(fc_prime=data.fc_prime, fy=data.fy, fu=data.fy * 1.25, fyt=data.fyt,
                                           fut=data.fyt * 1.25, es=200000.0, ec=ec, gamma_c=24.0, description=f"Custom")

            col_geom = ColumnGeometry(
                width=data.width, depth=data.depth, height=data.height, clear_height=data.clear_height,
                cover=cover, shape=ColumnShape.RECTANGULAR, column_type=ColumnType.TIED,
                effective_length=data.height, sdc=sdc_enum, frame_system=frame_enum
            )

            max_mux = max(abs(data.top_mux), abs(data.bot_mux))
            max_muy = max(abs(data.top_muy), abs(data.bot_muy))
            max_vux = max(abs(data.top_vux), abs(data.bot_vux))
            max_vuy = max(abs(data.top_vuy), abs(data.bot_vuy))

            t1_mnb_neg, t1_mnb_pos, t1_mpr_neg, t1_mpr_pos = get_beam_capacities(data.top_b1_b, data.top_b1_d,
                                                                                 data.top_b1_as_top, data.top_b1_as_bot,
                                                                                 data.fc_prime, data.fy)
            t2_mnb_neg, t2_mnb_pos, t2_mpr_neg, t2_mpr_pos = get_beam_capacities(data.top_b2_b, data.top_b2_d,
                                                                                 data.top_b2_as_top, data.top_b2_as_bot,
                                                                                 data.fc_prime, data.fy)

            sum_mnb_top = max(t1_mnb_pos + t2_mnb_neg, t1_mnb_neg + t2_mnb_pos)
            sum_mpr_top = max(t1_mpr_pos + t2_mpr_neg, t1_mpr_neg + t2_mpr_pos)

            b1_mnb_neg, b1_mnb_pos, b1_mpr_neg, b1_mpr_pos = get_beam_capacities(data.bot_b1_b, data.bot_b1_d,
                                                                                 data.bot_b1_as_top, data.bot_b1_as_bot,
                                                                                 data.fc_prime, data.fy)
            b2_mnb_neg, b2_mnb_pos, b2_mpr_neg, b2_mpr_pos = get_beam_capacities(data.bot_b2_b, data.bot_b2_d,
                                                                                 data.bot_b2_as_top, data.bot_b2_as_bot,
                                                                                 data.fc_prime, data.fy)

            sum_mnb_bot = max(b1_mnb_pos + b2_mnb_neg, b1_mnb_neg + b2_mnb_pos)
            sum_mpr_bot = max(b1_mpr_pos + b2_mpr_neg, b1_mpr_neg + b2_mpr_pos)

            col_loads = ColumnLoads(
                axial_force=data.pu, moment_x=max_mux, moment_y=max_muy, shear_x=max_vux, shear_y=max_vuy,
                load_condition=LoadCondition.BIAXIAL_BENDING,
                sum_beam_mpr_top=sum_mpr_top, sum_beam_mpr_bot=sum_mpr_bot,
                sum_beam_mnb_top=sum_mnb_top, sum_beam_mnb_bot=sum_mnb_bot
            )

            engine = ControlledColumnDesign(data.pref_main, data.pref_tie)
            res = engine.perform_complete_column_design(col_loads, col_geom, mat_props)

            vol_concrete, area_formwork, total_kg, rebar_rows = calculate_column_qto(col_geom, res)

            n_bars = len(res.reinforcement.longitudinal_bars)
            main_bar_str = f"{n_bars}x{res.reinforcement.longitudinal_bars[0]}" if n_bars > 0 else "None"
            tie_str = f"{res.reinforcement.tie_legs_x}x{res.reinforcement.tie_legs_y} legs {res.reinforcement.tie_bars} @ {res.reinforcement.tie_spacing:.0f} mm"

            status_color = "#16A34A" if res.utilization_ratio <= 1.0 else "#DC2626"

            notes_elements = []
            if res.design_notes:
                list_items = []
                for note in list(dict.fromkeys(res.design_notes)):
                    icon = "⚠️ " if any(x in note for x in ["Violation", "CRITICAL", "inadequate"]) else "ℹ️ "
                    list_items.append(air.Li(f"{icon} {note}"))
                notes_elements.append(air.Ul(*list_items, class_="notes-list"))

            sc_wb_element = ""
            if data.sdc in ["D", "E", "F"] and data.frame_system == "special":
                sc_wb_element = air.Div(
                    air.H4("Calculated Joint Demands", style="color: #1e3a8a; margin-top: 16px;"),
                    air.Ul(
                        air.Li(air.Strong("Top Joint: "),
                               f"Σ Mpr = {sum_mpr_top:.1f} kN-m, Σ Mnb = {sum_mnb_top:.1f} kN-m"),
                        air.Li(air.Strong("Bot Joint: "),
                               f"Σ Mpr = {sum_mpr_bot:.1f} kN-m, Σ Mnb = {sum_mnb_bot:.1f} kN-m")
                    ),
                    style="margin-top: 16px; padding: 12px; background: #f0fdf4; border-radius: 6px; border: 1px dashed #bbf7d0;"
                )

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
                    air.H2("Design Results"),
                    air.Div(
                        air.Div(
                            generate_column_section_css(data.width, data.depth, cover, n_bars,
                                                        res.reinforcement.tie_legs_x, res.reinforcement.tie_legs_y),
                        ),
                        air.Div(
                            air.H3("Interaction & Capacity"),
                            air.Ul(
                                air.Li(air.Strong("P-M Interaction Ratio"),
                                       air.Span(f"{res.capacity.interaction_ratio:.2f}", class_="data-value",
                                                style=f"color: {'#16A34A' if res.capacity.interaction_ratio <= 1.0 else '#DC2626'}; font-weight: bold;")),
                                air.Li(air.Strong("Max Axial Capacity (φPn)"),
                                       air.Span(f"{res.capacity.axial_capacity:.1f} kN", class_="data-value")),
                                air.Li(air.Strong("Shear Utilization (X / Y)"),
                                       air.Span(f"{res.shear_utilization_x:.2f} / {res.shear_utilization_y:.2f}",
                                                class_="data-value")),
                                air.Li(air.Strong("Shear Capacity (φVnx / φVny)"), air.Span(
                                    f"{res.capacity.shear_capacity_x:.1f} / {res.capacity.shear_capacity_y:.1f} kN",
                                    class_="data-value")),
                            ),
                            air.H3("Reinforcement Detail", style="margin-top: 24px;"),
                            air.Ul(
                                air.Li(air.Strong("Longitudinal Bars"), air.Span(main_bar_str, class_="data-value",
                                                                                 style="color: #2563eb; font-weight: bold;")),
                                air.Li(air.Strong("Steel Ratio (ρ)"), air.Span(
                                    f"{(res.reinforcement.longitudinal_area / (data.width * data.depth) * 100):.2f}%",
                                    class_="data-value")),
                                air.Li(air.Strong("Ties / Hoops"), air.Span(tie_str, class_="data-value",
                                                                            style="color: #db2777; font-weight: bold;")),
                            ),
                            sc_wb_element,
                            class_="section-box", style="height: 100%;"
                        ),
                        class_="grid-2"
                    ),
                    air.Div(
                        air.H4("Design Notes & Code Checks", style="margin-top: 20px; color: #92400e;"),
                        *notes_elements,
                        style="padding: 16px; background: #fffbeb; border-radius: 8px; border: 1px solid #fde68a; margin-top: 20px;"
                    ),
                    class_="card"
                ),
                air.Div(class_="page-break"),
                air.Div(
                    air.H2("Material Takeoff"),
                    air.Div(
                        air.Div(air.Div("Concrete Volume", class_="metric-label"),
                                air.Div(f"{vol_concrete:.2f} m³", class_="metric-value"), class_="metric-card"),
                        air.Div(air.Div("Formwork Area", class_="metric-label"),
                                air.Div(f"{area_formwork:.2f} m²", class_="metric-value"), class_="metric-card blue"),
                        air.Div(air.Div("Rebar Weight", class_="metric-label"),
                                air.Div(f"{total_kg:.1f} kg", class_="metric-value"), class_="metric-card green"),
                        class_="grid-3"
                    ),
                    air.Table(air.Thead(
                        air.Tr(air.Th("Location"), air.Th("Size"), air.Th("Qty"), air.Th("Required Length/Bar"),
                               air.Th("Recommended Order"), air.Th("Weight"))), air.Tbody(*rebar_rows)),
                    class_="card"
                )
            )

            full_html_layout = str(expressive_layout(
                air.Header(
                    air.A("← Edit Inputs", href="/column", class_="back-link no-print"),
                    air.H1("Structural Design Report"),
                    air.P("ACI 318M-25 Final Column Analysis", class_="subtitle"),
                    class_="module-header"
                ),
                report_content
            ))

            resp = AirResponse(content=full_html_layout, media_type="text/html")
            resp.set_cookie("col_inputs", cookie_data, max_age=2592000)
            return resp

        except Exception as e:
            error_html = str(expressive_layout(
                air.Header(
                    air.A("← Go Back", href="/column", class_="back-link no-print"),
                    air.H1("Calculation Error"),
                    air.P("Failed to process section demands.", class_="subtitle"),
                    class_="module-header"
                ),
                air.Main(air.Div(air.H2("Validation Failed", style="color: #DC2626;"), air.P(str(e)), class_="card"))
            ))
            return AirResponse(content=error_html, media_type="text/html")