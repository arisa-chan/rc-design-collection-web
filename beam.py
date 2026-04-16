import air
from air import AirField, AirResponse
from fastapi.responses import Response
from pydantic import BaseModel
import math
import json
from datetime import date
import pdfkit
from beam_pdf import generate_beam_report
from beam_manual import generate_beam_manual

# Import the ACI 318M-25 library components
from aci318m25 import ConcreteStrengthClass, ReinforcementGrade, MaterialProperties
from aci318m25_complete import ACI318M25MemberLibrary
from aci318m25_beam import ACI318M25BeamDesign, BeamGeometry, BeamType, SeismicDesignCategory, FrameSystem
from shared import blueprint_layout

base_aci_lib = ACI318M25MemberLibrary()


# ----------------------------------------------------------------------
# 1. NATIVE AIR SCHEMA
# ----------------------------------------------------------------------
class BeamDesignModel(BaseModel):
    action: str = AirField(default="view")
    proj_name: str = AirField(default="Typical Beam Design")
    proj_loc: str = AirField(default="Manila, PH")
    proj_eng: str = AirField(default="Engr. Doe")
    proj_date: str = AirField(default="")
    width: float = AirField(default=400.0)
    height: float = AirField(default=600.0)
    effective_depth: float = AirField(default=540.0)
    length: float = AirField(default=6000.0)
    clear_span: float = AirField(default=5500.0)
    sdc: str = AirField(default="D")
    frame_system: str = AirField(default="special")
    pref_main: str = AirField(default="D20")
    pref_stirrup: str = AirField(default="D10")
    pref_torsion: str = AirField(default="D12")
    fc_prime: float = AirField(default=28.0)
    fy: float = AirField(default=420.0)
    fyt: float = AirField(default=420.0)
    aggregate_size: float = AirField(default=20.0)

    deflection_limit: str = AirField(default="240")
    generate_pdf: str = AirField(default="")

    # Left Support Forces
    left_mu_neg: float = AirField(default=300.0)
    left_mu_pos: float = AirField(default=100.0)
    left_vu: float = AirField(default=180.0)
    left_tu: float = AirField(default=35.0)
    left_vg: float = AirField(default=80.0)
    left_mdead: float = AirField(default=0.0)
    left_mlive: float = AirField(default=0.0)

    # Midspan Forces
    mid_mu_neg: float = AirField(default=50.0)
    mid_mu_pos: float = AirField(default=200.0)
    mid_vu: float = AirField(default=50.0)
    mid_tu: float = AirField(default=5.0)
    mid_mdead: float = AirField(default=70.0)
    mid_mlive: float = AirField(default=60.0)

    # Right Support Forces
    right_mu_neg: float = AirField(default=280.0)
    right_mu_pos: float = AirField(default=120.0)
    right_vu: float = AirField(default=170.0)
    right_tu: float = AirField(default=15.0)
    right_vg: float = AirField(default=80.0)
    right_mdead: float = AirField(default=0.0)
    right_mlive: float = AirField(default=0.0)


# ----------------------------------------------------------------------
# 2. OVERRIDE ENGINE & QTO ALGORITHMS
# ----------------------------------------------------------------------
class ControlledBeamDesign(ACI318M25BeamDesign):
    def __init__(self, pref_main: str, pref_stirrup: str, pref_torsion: str):
        super().__init__()
        self.pref_main = pref_main
        self.pref_stirrup = pref_stirrup
        self.pref_torsion = pref_torsion

    def _select_reinforcement_bars(self, As_required: float, beam_geometry: BeamGeometry, fy: float,
                                   stirrup_size: str = 'D10', aggregate_size: float = 25.0) -> list:
        if As_required <= 0: return []
        area = self.aci.get_bar_area(self.pref_main)
        num_bars = max(2, math.ceil(As_required / area))
        return [self.pref_main] * num_bars

    def perform_complete_beam_design(self, mu_top: float, mu_bot: float, vu: float, beam_geometry: BeamGeometry,
                                     material_props: MaterialProperties, service_moment: float = None, tu: float = 0.0,
                                     gravity_shear: float = 0.0, is_support: bool = False, max_as_support: float = 0.0):
        # We process the base design. Unification happens later across all three zones.
        res = super().perform_complete_beam_design(mu_top, mu_bot, vu, beam_geometry, material_props, service_moment,
                                                   tu, gravity_shear, is_support, max_as_support, self.pref_stirrup,
                                                   self.pref_torsion)
        return res


def calculate_qto(geom, res_left, res_mid, res_right):
    L_m, w_m, h_m = geom.length / 1000.0, geom.width / 1000.0, geom.height / 1000.0
    vol_concrete = w_m * h_m * L_m
    area_formwork = (w_m + 2 * h_m + 0.1) * L_m

    rebar_rows, total_kg = [], 0.0

    def get_db(bars_list):
        if not bars_list: return 0.0
        val = bars_list[0] if isinstance(bars_list, list) else bars_list
        if "-leg" in val: val = val.split(" ")[1]
        try:
            return float(val.replace('D', ''))
        except:
            return 16.0

    # Optimal 1D Bin Packing for Standard Rebar Lengths
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

    def add_rebar(name, bars_list, theoretical_length_m, has_hooks=False):
        nonlocal total_kg
        if not bars_list: return
        db = get_db(bars_list)
        if db == 0: return
        num_bars = len(bars_list)
        req_len_per_bar = theoretical_length_m + (2 * ((12 * db + 100) / 1000.0 if has_hooks else 0.0))
        stock_text, total_ordered_m = get_best_commercial_order(req_len_per_bar, num_bars, db)
        weight_kg = total_ordered_m * ((db ** 2) / 162.0)
        total_kg += weight_kg
        rebar_rows.append(air.Tr(air.Td(air.Strong(name)), air.Td(f"D{int(db)}"), air.Td(str(num_bars)),
                                 air.Td(f"{req_len_per_bar:.2f}m"),
                                 air.Td(air.Span(stock_text, style="color: #db2777; font-weight: 600;")),
                                 air.Td(f"{weight_kg:.1f} kg")))

    # Extract detailed layers based on unified geometry
    n_top_cont = len(res_mid.reinforcement.top_bars)
    top_cont_bars = res_mid.reinforcement.top_bars
    top_add_left_bars = res_left.reinforcement.top_bars[n_top_cont:] if len(
        res_left.reinforcement.top_bars) > n_top_cont else []
    top_add_right_bars = res_right.reinforcement.top_bars[n_top_cont:] if len(
        res_right.reinforcement.top_bars) > n_top_cont else []

    n_bot_cont = min(len(res_left.reinforcement.bottom_bars), len(res_right.reinforcement.bottom_bars))
    if n_bot_cont == 0: n_bot_cont = len(res_mid.reinforcement.bottom_bars)
    bot_cont_bars = res_mid.reinforcement.bottom_bars[:n_bot_cont]
    bot_add_mid_bars = res_mid.reinforcement.bottom_bars[n_bot_cont:] if len(
        res_mid.reinforcement.bottom_bars) > n_bot_cont else []

    # Inject detailed bar logic per requested behavior
    add_rebar("Top Continuous", top_cont_bars, L_m, has_hooks=True)
    if top_add_left_bars: add_rebar("Top Additional (Left)", top_add_left_bars, 0.30 * L_m, has_hooks=True)
    if top_add_right_bars: add_rebar("Top Additional (Right)", top_add_right_bars, 0.30 * L_m, has_hooks=True)

    add_rebar("Bottom Continuous", bot_cont_bars, L_m, has_hooks=True)
    if bot_add_mid_bars: add_rebar("Bottom Additional (Midspan)", bot_add_mid_bars, (2.0 / 3.0) * L_m, has_hooks=False)

    add_rebar("Web bars", res_mid.reinforcement.side_bars, L_m, has_hooks=False)

    L_hl, s_hl = res_left.reinforcement.hinge_length, max(res_left.reinforcement.stirrup_spacing_hinge, 50) / 1000.0
    L_hr, s_hr = res_right.reinforcement.hinge_length, max(res_right.reinforcement.stirrup_spacing_hinge, 50) / 1000.0
    L_mid, s_m = max(0, L_m - (L_hl / 1000.0) - (L_hr / 1000.0)), max(res_mid.reinforcement.stirrup_spacing,
                                                                      50) / 1000.0
    total_stirrups = int((L_hl / 1000.0) / s_hl) + int((L_hr / 1000.0) / s_hr) + int(L_mid / s_m)

    if total_stirrups > 0:
        db_s = get_db(res_mid.reinforcement.stirrups)
        legs = int(res_mid.reinforcement.stirrups.split('-')[0]) if "-leg" in res_mid.reinforcement.stirrups else 2
        c_m = geom.cover / 1000.0

        outer_hoop_len = 2 * (w_m - 2 * c_m) + 2 * (h_m - 2 * c_m) + 24 * db_s / 1000.0
        cross_ties_len = max(0, legs - 2) * (h_m - 2 * c_m + 24 * db_s / 1000.0)
        stirrup_len_m = outer_hoop_len + cross_ties_len

        total_stirrup_length_m = total_stirrups * stirrup_len_m
        num_12m_bars = math.ceil(total_stirrup_length_m / 12.0)
        weight_kg = num_12m_bars * 12.0 * ((db_s ** 2) / 162.0)
        total_kg += weight_kg
        rebar_rows.append(
            air.Tr(air.Td(air.Strong(f"Stirrups ({legs}-leg)")), air.Td(f"D{int(db_s)}"), air.Td(str(total_stirrups)),
                   air.Td(f"{stirrup_len_m:.2f}m"), air.Td(f"{num_12m_bars} x 12.0m"), air.Td(f"{weight_kg:.1f} kg")))

    return vol_concrete, area_formwork, total_kg, rebar_rows


# ----------------------------------------------------------------------
# 3. VISUALIZATION COMPONENTS
# ----------------------------------------------------------------------
def generate_beam_elevation_css(length, height, res_left, res_mid, res_right):
    vis_height = max(100, min(240, 1000 * (height / length)))
    stirrup_elements = []
    s_hinge_left, hinge_len_left = max(res_left.reinforcement.stirrup_spacing_hinge,
                                       50), res_left.reinforcement.hinge_length
    s_mid = max(res_mid.reinforcement.stirrup_spacing, 50)
    s_hinge_right, hinge_len_right = max(res_right.reinforcement.stirrup_spacing_hinge,
                                         50), res_right.reinforcement.hinge_length

    x, loop_guard = 50.0, 0
    while x < length - 50.0 and loop_guard < 400:
        loop_guard += 1
        if x <= hinge_len_left:
            s, color, z_index = s_hinge_left, "#db2777", 2
        elif x >= length - hinge_len_right:
            s, color, z_index = s_hinge_right, "#db2777", 2
        else:
            s, color, z_index = s_mid, "#9ca3af", 1
        stirrup_elements.append(air.Div(
            style=f"position: absolute; left: {(x / length) * 100}%; top: 10%; bottom: 10%; width: 2px; background: {color}; z-index: {z_index};"))
        x += s

    beam_body = air.Div(
        air.Div(style="position: absolute; top: 12%; left: 0; right: 0; height: 4px; background: #2563eb; z-index: 3;"),
        air.Div(
            style="position: absolute; bottom: 12%; left: 0; right: 0; height: 4px; background: #2563eb; z-index: 3;"),
        *stirrup_elements,
        style=f"position: relative; width: 100%; height: {vis_height}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px; overflow: hidden; box-sizing: border-box;"
    )
    labels = air.Div(
        air.Div(f"Hinge ({hinge_len_left:.0f}mm)",
                style=f"position: absolute; left: 0; top: 100%; font-size: 12px; color: #db2777; font-weight: bold; width: {(hinge_len_left / length) * 100}%; border-top: 2px solid #db2777; padding-top: 4px;"),
        air.Div(f"Midspan",
                style="position: absolute; left: 50%; top: 100%; font-size: 12px; color: #6b7280; transform: translateX(-50%); padding-top: 4px;"),
        air.Div(f"Hinge ({hinge_len_right:.0f}mm)",
                style=f"position: absolute; right: 0; top: 100%; font-size: 12px; color: #db2777; font-weight: bold; width: {(hinge_len_right / length) * 100}%; border-top: 2px solid #db2777; padding-top: 4px; text-align: right;"),
        style="position: relative; width: 100%; height: 30px; margin-top: 4px;"
    )
    return air.Div(beam_body, labels,
                   style="padding: 24px; background: #ffffff; border-radius: 8px; border: 2px dashed #e5e7eb; margin-bottom: 32px;")


def generate_beam_section_css(width, height, cover, stirrup_str, top_bars_list, bot_bars_list, side_bars_list):
    scale = min(200 / max(width, 1), 240 / max(height, 1))
    draw_w, draw_h, c_s = width * scale, height * scale, cover * scale

    children = []
    stirrup_w, stirrup_h = draw_w - 2 * c_s, draw_h - 2 * c_s
    legs = int(stirrup_str.split("-")[0]) if "-leg" in stirrup_str else 2

    if stirrup_w > 0 and stirrup_h > 0:
        children.append(air.Div(
            style=f"position: absolute; left: {c_s}px; top: {c_s}px; width: {stirrup_w}px; height: {stirrup_h}px; border: 2px dashed #db2777; border-radius: 6px; box-sizing: border-box;"))
        if legs > 2:
            inner_spacing = stirrup_w / (legs - 1)
            for i in range(1, legs - 1):
                children.append(air.Div(
                    style=f"position: absolute; left: {c_s + i * inner_spacing}px; top: {c_s}px; width: 0px; height: {stirrup_h}px; border-left: 2px dashed #db2777; box-sizing: border-box;"))

    def create_css_bars(bars_list, is_top):
        bars = []
        if not bars_list: return bars
        db = float(bars_list[0].replace('D', '')) if 'D' in bars_list[0] else 20.0
        avail_w, min_s = width - 2 * cover - 2 * 10, max(25.0, db)
        max_bars = max(2, int((avail_w + min_s) / (db + min_s)))
        layers, rem = [], len(bars_list)
        while rem > 0:
            take = min(rem, max_bars)
            layers.append(take)
            rem -= take

        for layer_idx, num_bars in enumerate(layers):
            y_pos = c_s + 4 + layer_idx * (12 + 25.0 * scale) if is_top else draw_h - c_s - 12 - 4 - layer_idx * (
                        12 + 25.0 * scale)
            start_x, spacing = c_s + 4, (stirrup_w - 12 - 8) / (num_bars - 1) if num_bars > 1 else 0
            for i in range(num_bars):
                cx = start_x + (stirrup_w - 12 - 8) / 2 if num_bars == 1 else start_x + i * spacing
                bars.append(air.Div(
                    style=f"position: absolute; left: {cx}px; top: {y_pos}px; width: 12px; height: 12px; background: #2563eb; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))
        return bars

    children.extend(create_css_bars(top_bars_list, True))
    children.extend(create_css_bars(bot_bars_list, False))

    if side_bars_list:
        layers = len(side_bars_list) // 2
        y_inner_space = stirrup_h - 24
        spacing_y = y_inner_space / (layers + 1)
        for i in range(layers):
            y_pos = c_s + 12 + (i + 1) * spacing_y - 6
            children.append(air.Div(
                style=f"position: absolute; left: {c_s + 4}px; top: {y_pos}px; width: 12px; height: 12px; background: #D97706; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))
            children.append(air.Div(
                style=f"position: absolute; left: {draw_w - c_s - 16}px; top: {y_pos}px; width: 12px; height: 12px; background: #D97706; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))

    concrete_block = air.Div(*children,
                             style=f"position: relative; width: {draw_w}px; height: {draw_h}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px; box-sizing: border-box;")
    return air.Div(
        air.Div(f"{width} mm",
                style="text-align: center; font-family: monospace; font-weight: 700; color: #6b7280; margin-bottom: 8px;"),
        air.Div(air.Div(f"{height} mm",
                        style="position: absolute; left: -65px; top: 50%; transform: translateY(-50%); font-family: monospace; font-weight: 700; color: #6b7280;"),
                concrete_block, style="position: relative; display: inline-block; margin-left: 40px;"),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px 0; margin-bottom: 24px; background: #ffffff; border-radius: 8px; border: 2px dashed #e5e7eb;"
    )


def render_force_inputs(title, prefix, data, show_gravity=False, show_deflection=False):
    fields = [
        air.Div(air.Label("Factored -Mu [Top] (kN·m)"),
                air.Input(type="number", name=f"{prefix}_mu_neg", value=str(getattr(data, f"{prefix}_mu_neg")),
                          step="any", required=True), class_="form-group"),
        air.Div(air.Label("Factored +Mu [Bottom] (kN·m)"),
                air.Input(type="number", name=f"{prefix}_mu_pos", value=str(getattr(data, f"{prefix}_mu_pos")),
                          step="any", required=True), class_="form-group"),
        air.Div(air.Label("Factored shear Vu (kN)"),
                air.Input(type="number", name=f"{prefix}_vu", value=str(getattr(data, f"{prefix}_vu")), step="any",
                          required=True), class_="form-group"),
        air.Div(air.Label("Factored torsion Tu (kN·m)"),
                air.Input(type="number", name=f"{prefix}_tu", value=str(getattr(data, f"{prefix}_tu")), step="any",
                          required=True), class_="form-group")
    ]
    if show_gravity:
        fields.append(air.Div(air.Label("Gravity shear Vg (kN)"),
                              air.Input(type="number", name=f"{prefix}_vg", value=str(getattr(data, f"{prefix}_vg")),
                                        step="any", required=True), class_="form-group"))
    else:
        fields.append(air.Input(type="hidden", name=f"{prefix}_vg", value="0"))
    if show_deflection:
        fields.append(air.Div(air.Label("Service dead moment (kN·m)"), air.Input(type="number", name=f"{prefix}_mdead",
                                                                                 value=str(
                                                                                     getattr(data, f"{prefix}_mdead")),
                                                                                 step="any", required=True),
                              class_="form-group"))
        fields.append(air.Div(air.Label("Service live moment (kN·m)"), air.Input(type="number", name=f"{prefix}_mlive",
                                                                                 value=str(
                                                                                     getattr(data, f"{prefix}_mlive")),
                                                                                 step="any", required=True),
                              class_="form-group"))
    else:
        fields.append(air.Input(type="hidden", name=f"{prefix}_mdead", value="0"))
        fields.append(air.Input(type="hidden", name=f"{prefix}_mlive", value="0"))
    return air.Div(air.H3(title), *fields, class_="section-box")


def render_section_results(title, result, width, height, cover):
    top_bars = f"{len(result.reinforcement.top_bars)}x{result.reinforcement.top_bars[0]}" if result.reinforcement.top_bars else "None"
    bot_bars = f"{len(result.reinforcement.bottom_bars)}x{result.reinforcement.bottom_bars[0]}" if result.reinforcement.bottom_bars else "None"
    side_bars = f"{len(result.reinforcement.side_bars)}x{result.reinforcement.side_bars[0]}" if result.reinforcement.side_bars else "None"

    transverse_str = f"{result.reinforcement.stirrups} @ {result.reinforcement.stirrup_spacing:.0f} mm"
    if result.reinforcement.stirrup_spacing_hinge > 0 and result.reinforcement.hinge_length > 0:
        transverse_str = f"{result.reinforcement.stirrups} @ {result.reinforcement.stirrup_spacing_hinge:.0f} mm (Hinge)"

    status_color = "#16A34A" if result.utilization_ratio <= 1.0 else "#DC2626"

    css_diagram = generate_beam_section_css(width, height, cover, result.reinforcement.stirrups,
                                            result.reinforcement.top_bars, result.reinforcement.bottom_bars,
                                            result.reinforcement.side_bars)

    notes_elements = []
    if result.design_notes:
        notes_elements.append(air.H4("Notes", style="margin-top: 20px; color: #92400e;"))
        list_items = []
        for note in list(dict.fromkeys(result.design_notes)):
            icon = "⚠️ " if any(x in note for x in ["Violation", "CRITICAL", "inadequate", "exceeded"]) else "ℹ️ "
            list_items.append(air.Li(f"{icon} {note}"))
        notes_elements.append(air.Ul(*list_items, class_="notes-list"))

    return air.Div(
        air.H3(title), css_diagram,
        air.H4("Capacities"),
        air.Ul(
            air.Li(air.Strong("Flexure (φMn) Top/Bot"),
                   air.Span(f"{result.moment_capacity_top:.1f} / {result.moment_capacity_bot:.1f} kN·m",
                            class_="data-value")),
            air.Li(air.Strong("Shear (φVn / Ve)"),
                   air.Span(f"{result.shear_capacity:.1f} / {result.capacity_shear_ve:.1f} kN", class_="data-value")),
            air.Li(air.Strong("Torsion (φTn)"), air.Span(f"{result.torsion_capacity:.1f} kN·m", class_="data-value")),
            air.Li(air.Strong("DCR"),
                   air.Span(f"{result.utilization_ratio:.2f} {'≤' if result.utilization_ratio <= 1.0 else '>'} 1.00",
                            class_=f"status-badge {'pass' if result.utilization_ratio <= 1.0 else 'fail'}"))
        ),
        air.H4("Reinforcements"),
        air.Ul(
            air.Li(air.Strong("Top bars"), air.Span(top_bars, class_="data-value", style="color: #2563eb;")),
            air.Li(air.Strong("Bottom bars"), air.Span(bot_bars, class_="data-value", style="color: #2563eb;")),
            air.Li(air.Strong("Web bars"),
                   air.Span(side_bars, class_="data-value", style="color: #D97706;")),
            air.Li(air.Strong("Stirrups"), air.Span(transverse_str, class_="data-value", style="color: #db2777;"))
        ),
        *notes_elements,
        class_="section-box"
    )


# ----------------------------------------------------------------------
# 4. MODULE ROUTES
# ----------------------------------------------------------------------
def setup_beam_routes(app):
    @app.get("/beam")
    def beam_index(request: air.Request):
        data = BeamDesignModel()
        saved_inputs = request.cookies.get("beam_inputs")
        if saved_inputs:
            try:
                parsed = json.loads(saved_inputs)
                data = BeamDesignModel(**parsed)
            except Exception:
                pass

        if not data.proj_date: data.proj_date = date.today().strftime("%Y-%m-%d")

        csrf_token = ""
        if hasattr(request, "state") and hasattr(request.state, "csrf_token"):
            csrf_token = request.state.csrf_token
        elif "csrftoken" in request.scope:
            token = request.scope["csrftoken"]
            csrf_token = token() if callable(token) else token
        elif "csrf_token" in request.scope:
            token = request.scope["csrf_token"]
            csrf_token = token() if callable(token) else token
        if not csrf_token: csrf_token = request.cookies.get("csrftoken", "dev_fallback_token")

        bar_opts = ["D10", "D12", "D16", "D20", "D25", "D28", "D32", "D36"]

        return blueprint_layout(
            air.Header(
                air.A("← Dashboard", href="/", class_="back-link no-print"),
                air.H1("RC Beam Designer"),
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
                            air.Div(air.Label("Beam width (mm)"),
                                    air.Input(type="number", name="width", value=str(data.width), step="any", required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Beam depth (mm)"),
                                    air.Input(type="number", name="height", value=str(data.height), step="any", required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Effective depth (mm)"),
                                    air.Input(type="number", name="effective_depth", value=str(data.effective_depth), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Center-to-center span (mm)"),
                                    air.Input(type="number", name="length", value=str(data.length), step="any", required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Clear span (mm)"),
                                    air.Input(type="number", name="clear_span", value=str(data.clear_span), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Seismic Design Category"),
                                    air.Select(air.Option("A", value="A", selected=(data.sdc == "A")),
                                               air.Option("B", value="B", selected=(data.sdc == "B")),
                                               air.Option("C", value="C", selected=(data.sdc == "C")),
                                               air.Option("D", value="D", selected=(data.sdc == "D")),
                                               air.Option("E", value="E", selected=(data.sdc == "E")),
                                               air.Option("F", value="F", selected=(data.sdc == "F")), name="sdc"),
                                    class_="form-group"),
                            air.Div(air.Label("Concrete strength (MPa)"),
                                    air.Input(type="number", name="fc_prime", value=str(data.fc_prime), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Main bar yield strength (MPa)"),
                                    air.Input(type="number", name="fy", value=str(data.fy), step="any", required=True),
                                    class_="form-group"),
                            air.Div(air.Label("Stirrup yield strength (MPa)"),
                                    air.Input(type="number", name="fyt", value=str(data.fyt), step="any",
                                              required=True), class_="form-group"),
                            air.Div(air.Label("Max aggregate size (mm)"),
                                    air.Input(type="number", name="aggregate_size", value=str(data.aggregate_size),
                                              step="any", min="10", required=True), class_="form-group"),
                            air.Div(air.Label("Moment frame system"), air.Select(
                                air.Option("Ordinary (OMF)", value="ordinary",
                                           selected=(data.frame_system == "ordinary")),
                                air.Option("Intermediate (IMF)", value="intermediate",
                                           selected=(data.frame_system == "intermediate")),
                                air.Option("Special (SMF)", value="special", selected=(data.frame_system == "special")),
                                name="frame_system"), class_="form-group"),

                            air.Div(air.Label("Main bar diameter"),
                                    air.Select(*[air.Option(opt, selected=(data.pref_main == opt)) for opt in bar_opts],
                                               name="pref_main"), class_="form-group"),
                            air.Div(air.Label("Stirrup diameter"), air.Select(
                                *[air.Option(opt, selected=(data.pref_stirrup == opt)) for opt in bar_opts],
                                name="pref_stirrup"), class_="form-group"),
                            air.Div(air.Label("Side bar diameter"), air.Select(
                                *[air.Option(opt, selected=(data.pref_torsion == opt)) for opt in bar_opts],
                                name="pref_torsion"), class_="form-group"),

                            air.Div(air.Label("Long term deflection limit"), air.Select(
                                air.Option("L/240 (non-sensitive finishes)", value="240",
                                           selected=(str(data.deflection_limit) == "240")),
                                air.Option("L/480 (sensitive finishes)", value="480",
                                           selected=(str(data.deflection_limit) == "480")), name="deflection_limit"),
                                    class_="form-group"),

                            class_="grid-3"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Loads"),
                        air.Div(
                            render_force_inputs("Left support", "left", data, show_gravity=True),
                            render_force_inputs("Midspan", "mid", data, show_deflection=True),
                            render_force_inputs("Right support", "right", data, show_gravity=True),
                            class_="grid-3"
                        ),
                        air.Button("Run Analysis", type="submit",
                                   style="width: 100%; font-size: 18px; margin-top: 32px;"),
                        class_="card"
                    ),
                    method="post", action="/beam/design"
                )
            )
        )

    @app.get("/beam/manual")
    def beam_manual(request: air.Request):
        pdf_bytes = generate_beam_manual()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="rc_beam_designer_manual.pdf"'},
        )

    @app.post("/beam/design")
    async def beam_design(request: air.Request):
        form_data = await request.form()
        cookie_data = json.dumps(dict(form_data))

        try:
            data = BeamDesignModel(**form_data)
        except Exception as e:
            error_html = str(blueprint_layout(
                air.Header(
                    air.A("← Go Back", href="/beam", class_="back-link no-print"),
                    air.H1("Calculation Error"),
                    air.P("Form validation failed.", class_="subtitle"),
                    class_="module-header"
                ),
                air.Main(air.Div(air.H2("Invalid Inputs", style="color: #DC2626;"), air.P(str(e)), class_="card"))
            ))
            resp = AirResponse(content=error_html, media_type="text/html")
            resp.set_cookie("beam_inputs", cookie_data, max_age=2592000)
            return resp

        try:
            sdc_enum, frame_enum = SeismicDesignCategory(data.sdc), FrameSystem(data.frame_system)
            cover = 40.0

            ec = base_aci_lib.aci.get_concrete_modulus(data.fc_prime)
            mat_props = MaterialProperties(fc_prime=data.fc_prime, fy=data.fy, fu=data.fy * 1.25, fyt=data.fyt,
                                           fut=data.fyt * 1.25, es=200000.0, ec=ec, gamma_c=24.0, description=f"Custom")
            beam_geom = BeamGeometry(length=data.length, width=data.width, height=data.height,
                                     effective_depth=data.effective_depth, cover=cover, flange_width=0.0,
                                     flange_thickness=0.0, beam_type=BeamType.RECTANGULAR, clear_span=data.clear_span,
                                     sdc=sdc_enum, frame_system=frame_enum, aggregate_size=data.aggregate_size)

            custom_lib = ACI318M25MemberLibrary()
            custom_lib.beam_design = ControlledBeamDesign(data.pref_main, data.pref_stirrup, data.pref_torsion)

            max_as_support = 0.0
            if frame_enum == FrameSystem.SPECIAL:
                as_top_l = custom_lib.beam_design._get_required_steel(data.left_mu_neg, beam_geom, mat_props)
                as_bot_l = max(custom_lib.beam_design._get_required_steel(data.left_mu_pos, beam_geom, mat_props),
                               0.5 * as_top_l)
                as_top_r = custom_lib.beam_design._get_required_steel(data.right_mu_neg, beam_geom, mat_props)
                as_bot_r = max(custom_lib.beam_design._get_required_steel(data.right_mu_pos, beam_geom, mat_props),
                               0.5 * as_top_r)
                max_as_support = max(as_top_l, as_bot_l, as_top_r, as_bot_r)

            res_left = custom_lib.beam_design.perform_complete_beam_design(data.left_mu_neg, data.left_mu_pos,
                                                                           data.left_vu, beam_geom, mat_props,
                                                                           tu=data.left_tu, gravity_shear=data.left_vg,
                                                                           is_support=True,
                                                                           max_as_support=max_as_support)
            res_mid = custom_lib.beam_design.perform_complete_beam_design(data.mid_mu_neg, data.mid_mu_pos, data.mid_vu,
                                                                          beam_geom, mat_props,
                                                                          service_moment=data.mid_mlive, tu=data.mid_tu,
                                                                          gravity_shear=0.0, is_support=False,
                                                                          max_as_support=max_as_support)
            res_right = custom_lib.beam_design.perform_complete_beam_design(data.right_mu_neg, data.right_mu_pos,
                                                                            data.right_vu, beam_geom, mat_props,
                                                                            tu=data.right_tu,
                                                                            gravity_shear=data.right_vg,
                                                                            is_support=True,
                                                                            max_as_support=max_as_support)

            # ----- UNIFICATION & CONSTRUCTABILITY ENGINE -----

            # Detect cantilever early so unification steps can use it
            _left_is_free = (float(data.left_mu_neg) == 0 and float(data.left_mu_pos) == 0)
            _right_is_free = (float(data.right_mu_neg) == 0 and float(data.right_mu_pos) == 0)
            _is_cantilever = (_left_is_free != _right_is_free)  # exactly one end free

            # 1. Sync Stirrup Legs & Enforce Minimum Constructability
            def get_legs(s):
                return int(s.split("-")[0]) if "-leg" in s else 2

            max_legs = max(get_legs(res_left.reinforcement.stirrups), get_legs(res_mid.reinforcement.stirrups),
                           get_legs(res_right.reinforcement.stirrups))
            unified_stirrup = f"{max_legs}-leg {data.pref_stirrup}" if max_legs > 2 else data.pref_stirrup
            for r in [res_left, res_mid, res_right]: r.reinforcement.stirrups = unified_stirrup

            def enforce_legs(bars):
                if not bars: return [data.pref_main] * max_legs
                if len(bars) < max_legs: return [data.pref_main] * max_legs
                return list(bars)

            for r in [res_left, res_mid, res_right]:
                r.reinforcement.top_bars = enforce_legs(r.reinforcement.top_bars)
                r.reinforcement.bottom_bars = enforce_legs(r.reinforcement.bottom_bars)

            # 2. Sync Left and Right Main Bars
            def get_area(bars):
                return len(bars) * custom_lib.beam_design.aci.get_bar_area(bars[0]) if bars else 0.0

            if get_area(res_left.reinforcement.top_bars) >= get_area(res_right.reinforcement.top_bars):
                res_right.reinforcement.top_bars = list(res_left.reinforcement.top_bars)
            else:
                res_left.reinforcement.top_bars = list(res_right.reinforcement.top_bars)

            if get_area(res_left.reinforcement.bottom_bars) >= get_area(res_right.reinforcement.bottom_bars):
                res_right.reinforcement.bottom_bars = list(res_left.reinforcement.bottom_bars)
            else:
                res_left.reinforcement.bottom_bars = list(res_right.reinforcement.bottom_bars)

            for r in [res_left, res_mid, res_right]:
                r.reinforcement.top_area = get_area(r.reinforcement.top_bars)
                r.reinforcement.bottom_area = get_area(r.reinforcement.bottom_bars)

            # 3. Sync Stirrup Spacing (Left & Right Hinge)
            if _is_cantilever:
                # For a cantilever, only the fixed end has a seismic hinge zone.
                # Clear hinge properties on the free end so it uses regular span spacing.
                if _left_is_free:
                    res_left.reinforcement.hinge_length = 0.0
                    res_left.reinforcement.stirrup_spacing_hinge = res_left.reinforcement.stirrup_spacing
                else:  # right end is free
                    res_right.reinforcement.hinge_length = 0.0
                    res_right.reinforcement.stirrup_spacing_hinge = res_right.reinforcement.stirrup_spacing
            else:
                # Span beam: sync both hinge spacings to the more restrictive (smaller) value
                min_hinge_s = min(res_left.reinforcement.stirrup_spacing_hinge,
                                  res_right.reinforcement.stirrup_spacing_hinge)
                res_left.reinforcement.stirrup_spacing_hinge = min_hinge_s
                res_right.reinforcement.stirrup_spacing_hinge = min_hinge_s

            # 4. Sync Torsion Side Bars uniformly
            max_side_area = max(get_area(res_left.reinforcement.side_bars), get_area(res_mid.reinforcement.side_bars),
                                get_area(res_right.reinforcement.side_bars))
            if get_area(res_left.reinforcement.side_bars) == max_side_area:
                max_side_bars = res_left.reinforcement.side_bars
            elif get_area(res_mid.reinforcement.side_bars) == max_side_area:
                max_side_bars = res_mid.reinforcement.side_bars
            else:
                max_side_bars = res_right.reinforcement.side_bars

            for r in [res_left, res_mid, res_right]:
                r.reinforcement.side_bars = list(max_side_bars)
                r.reinforcement.side_area = get_area(max_side_bars)

            # 5. Recalculate Final Capacities for Unified Sections
            def recalc(r, is_support, mu_top, mu_bot, vu, tu, gravity_v):
                phi_f = custom_lib.beam_design.phi_factors['flexure_tension_controlled']
                phi_v = custom_lib.beam_design.phi_factors['shear']
                phi_t = custom_lib.beam_design.phi_factors['torsion']

                r.moment_capacity_top = phi_f * custom_lib.beam_design._calculate_moment_capacity(
                    r.reinforcement.top_area, beam_geom, mat_props)
                r.moment_capacity_bot = phi_f * custom_lib.beam_design._calculate_moment_capacity(
                    r.reinforcement.bottom_area, beam_geom, mat_props)

                actual_s = r.reinforcement.stirrup_spacing_hinge if is_support else r.reinforcement.stirrup_spacing
                As_prov = max(r.reinforcement.top_area, r.reinforcement.bottom_area)
                r.shear_capacity = phi_v * custom_lib.beam_design._calculate_shear_capacity(beam_geom, mat_props,
                                                                                            r.reinforcement.stirrups,
                                                                                            actual_s, As_prov)

                # Compute Vc for torsion interaction using ACI 318M-25 Table 22.5.5.1 (Av-aware)
                Vc = custom_lib.beam_design._calculate_vc(beam_geom, mat_props,
                                                         r.reinforcement.stirrups, actual_s, As_prov)  # N
                if beam_geom.frame_system == FrameSystem.SPECIAL:
                    ve_component = r.capacity_shear_ve - gravity_v  # kN
                    if ve_component >= 0.5 * vu:  # both in kN
                        Vc = 0.0

                # Always compute torsion capacity — section has stirrups providing inherent
                # torsion resistance regardless of whether torsion reinforcement was required.
                r.torsion_capacity = phi_t * custom_lib.beam_design._calculate_torsion_capacity(beam_geom,
                                                                                                mat_props,
                                                                                                r.reinforcement.stirrups,
                                                                                                actual_s,
                                                                                                r.capacity_shear_ve * 1000,  # Ve in N
                                                                                                Vc)  # Vc in N

                # All demands and capacities in consistent units:
                #   moments: kN-m, shear: kN, torsion: kN-m
                util_m_top = mu_top / r.moment_capacity_top if r.moment_capacity_top > 0 else 1.0
                util_m_bot = mu_bot / r.moment_capacity_bot if r.moment_capacity_bot > 0 else 1.0
                util_v = vu / r.shear_capacity if r.shear_capacity > 0 else 1.0
                # Only count torsion in DCR when tu exceeds the ACI threshold (torsion_required)
                util_t = tu / r.torsion_capacity if (r.torsion_capacity > 0 and tu > 0 and r.reinforcement.torsion_required) else 0.0
                r.utilization_ratio = max(util_m_top, util_m_bot, util_v, util_t)

            recalc(res_left, True, data.left_mu_neg, data.left_mu_pos, data.left_vu, data.left_tu, data.left_vg)
            recalc(res_mid, False, data.mid_mu_neg, data.mid_mu_pos, data.mid_vu, data.mid_tu, 0.0)
            recalc(res_right, True, data.right_mu_neg, data.right_mu_pos, data.right_vu, data.right_tu, data.right_vg)
            # ----- END UNIFICATION ENGINE -----

            vol_concrete, area_formwork, total_kg, rebar_rows = calculate_qto(beam_geom, res_left, res_mid, res_right)

            # ---------------------------------------------------------
            # RIGOROUS ACI 318-25 DEFLECTION CALCULATION (Effective I)
            # ---------------------------------------------------------
            L_mm = float(data.length)
            M_l = float(data.mid_mlive)

            M_d = float(data.mid_mdead)
            M_sus = M_d + 0.25 * M_l
            M_tot = M_d + M_l

            fr = 0.62 * math.sqrt(data.fc_prime)
            Ec = mat_props.ec
            Ig = (data.width * (data.height ** 3)) / 12.0
            yt = data.height / 2.0
            M_cr = (fr * Ig) / yt / 1e6

            n = 200000.0 / Ec
            d = data.effective_depth
            d_prime = max(40.0, data.height - data.effective_depth)
            b = data.width

            # Reuse cantilever flags already computed before the unification engine
            left_is_free = _left_is_free
            right_is_free = _right_is_free
            is_cantilever = _is_cantilever

            if is_cantilever:
                # ---------------------------------------------------------
                # CANTILEVER CASE
                # Deflection computed at the free end (tip).
                # Per ACI 318 Table 24.2.3.6b: use Ie at the support (fixed end).
                # Icr uses fixed-end reinforcement (hogging: tension at top).
                # Tip deflection via Simpson's rule on M/EI diagram:
                #   δ_tip = L² / (6·Ec·Ie) × (2·M_mid + M_fixed)
                # ---------------------------------------------------------
                if left_is_free:
                    res_fixed = res_right
                    Mu_fixed = max(float(data.right_mu_neg), float(data.right_mu_pos))
                    defl_location = "free end (left)"
                else:
                    res_fixed = res_left
                    Mu_fixed = max(float(data.left_mu_neg), float(data.left_mu_pos))
                    defl_location = "free end (right)"

                # Tension steel at fixed end (hogging → top bars in tension)
                As_t = res_fixed.reinforcement.top_area
                As_c = res_fixed.reinforcement.bottom_area

                # Governing ultimate midspan moment for scaling
                Mu_mid_gov = max(float(data.mid_mu_neg), float(data.mid_mu_pos))

                # Scale service midspan moments to fixed-end service moments
                if Mu_mid_gov > 0:
                    scale_fixed = Mu_fixed / Mu_mid_gov
                else:
                    scale_fixed = 2.0  # approximate default for cantilever

                M_fixed_d = M_d * scale_fixed
                M_fixed_l = M_l * scale_fixed
                M_fixed_sus = M_fixed_d + 0.25 * M_fixed_l
                M_fixed_tot = M_fixed_d + M_fixed_l

            else:
                # ---------------------------------------------------------
                # SPAN BEAM CASE (simply-supported or continuous)
                # Icr from midspan reinforcement (sagging: tension at bottom).
                # ---------------------------------------------------------
                As_t = res_mid.reinforcement.bottom_area
                As_c = res_mid.reinforcement.top_area
                defl_location = "midspan"

            # ---------------------------------------------------------
            # Calculate Icr (same quadratic, different As for cant/span)
            # ---------------------------------------------------------
            A_quad = 0.5 * b
            B_quad = (n - 1) * As_c + n * As_t
            C_quad = -((n - 1) * As_c * d_prime + n * As_t * d)

            discriminant = B_quad**2 - 4 * A_quad * C_quad
            if discriminant > 0:
                kd = (-B_quad + math.sqrt(discriminant)) / (2 * A_quad)
                Icr = (b * kd**3) / 3.0 + (n - 1) * As_c * (kd - d_prime)**2 + n * As_t * (d - kd)**2
            else:
                Icr = Ig

            def calc_Ie(M_applied):
                if M_applied <= 0: return Ig
                if M_applied <= (2.0/3.0) * M_cr:
                    return Ig
                # ACI 318M-25 §24.2.3.5: Ie = Icr / (1 - ((2/3*Mcr)/Ma)^2 * (1 - Icr/Ig))
                factor_m = ((2.0/3.0) * M_cr / M_applied) ** 2
                Ie_calc = Icr / (1.0 - factor_m * (1.0 - Icr / Ig))
                return max(Icr, min(Ie_calc, Ig))

            if is_cantilever:
                # Per ACI Table 24.2.3.6b: Ie at support for cantilevers
                Ie_d = calc_Ie(M_fixed_d)
                Ie_sus = calc_Ie(M_fixed_sus)
                Ie_tot = calc_Ie(M_fixed_tot)

                # Tip deflection via Simpson's rule:
                #   δ_tip = L² / (6·Ec·Ie) × (2·M_mid + M_fixed)
                def calc_delta_cant(M_mid_s, M_fixed_s, Ie):
                    if Ie <= 0 or (M_mid_s <= 0 and M_fixed_s <= 0):
                        return 0.0
                    return max(0.0, (L_mm ** 2) / (6.0 * Ec * Ie) * (2.0 * M_mid_s * 1e6 + M_fixed_s * 1e6))

                delta_d_imm = calc_delta_cant(M_d, M_fixed_d, Ie_d)
                delta_sus_imm = calc_delta_cant(M_sus, M_fixed_sus, Ie_sus)
                delta_tot_imm = calc_delta_cant(M_tot, M_fixed_tot, Ie_tot)

                # Support moments not applicable for cantilever PDF display
                M_A_tot = M_B_tot = 0.0

            else:
                # Span beam: Ie at midspan
                Ie_d = calc_Ie(M_d)
                Ie_sus = calc_Ie(M_sus)
                Ie_tot = calc_Ie(M_tot)

                # ---------------------------------------------------------
                # Estimate service-level support moments from ultimate ratios
                # ---------------------------------------------------------
                Mu_mid_pos = float(data.mid_mu_pos)
                Mu_left_neg = float(data.left_mu_neg)
                Mu_right_neg = float(data.right_mu_neg)

                if Mu_mid_pos > 0:
                    scale_d = M_d / Mu_mid_pos
                    M_A_d = -Mu_left_neg * scale_d
                    M_B_d = -Mu_right_neg * scale_d
                    scale_sus = M_sus / Mu_mid_pos
                    M_A_sus = -Mu_left_neg * scale_sus
                    M_B_sus = -Mu_right_neg * scale_sus
                    scale_tot = M_tot / Mu_mid_pos
                    M_A_tot = -Mu_left_neg * scale_tot
                    M_B_tot = -Mu_right_neg * scale_tot
                else:
                    M_A_d = M_B_d = M_A_sus = M_B_sus = M_A_tot = M_B_tot = 0.0

                # ---------------------------------------------------------
                # Midspan deflection via Simpson's rule:
                #   δ = L² / (96·Ec·Ie) × (M_A + 10·M_C + M_B)
                # ---------------------------------------------------------
                def calc_delta(M_A, M_C, M_B, Ie):
                    if Ie <= 0 or M_C <= 0:
                        return 0.0
                    return max(0.0, (L_mm ** 2) / (96.0 * Ec * Ie) * (M_A * 1e6 + 10.0 * M_C * 1e6 + M_B * 1e6))

                delta_d_imm = calc_delta(M_A_d, M_d, M_B_d, Ie_d)
                delta_sus_imm = calc_delta(M_A_sus, M_sus, M_B_sus, Ie_sus)
                delta_tot_imm = calc_delta(M_A_tot, M_tot, M_B_tot, Ie_tot)

            delta_live = max(0.0, delta_tot_imm - delta_d_imm)

            rho_prime = As_c / (data.width * data.effective_depth) if (data.width * data.effective_depth) > 0 else 0
            time_factor = 2.0 / (1 + 50 * rho_prime)

            delta_long = delta_live + time_factor * delta_sus_imm

            lim_live = data.length / 360

            lim_long_divisor = float(data.deflection_limit)
            lim_long = data.length / lim_long_divisor

            status_live = "#16A34A" if delta_live <= lim_live else "#DC2626"
            status_long = "#16A34A" if delta_long <= lim_long else "#DC2626"

            if data.generate_pdf == "1":
                # Create a data object for deflection values
                defl_data = {
                    "M_cr": M_cr, "I_g": Ig, "I_cr": Icr, "I_e": Ie_tot,
                    "delta_live": delta_live, "delta_long": delta_long,
                    "lim_live": lim_live, "lim_long": lim_long,
                    "M_A_tot": M_A_tot, "M_B_tot": M_B_tot,
                    "M_a": M_fixed_tot if is_cantilever else M_tot,
                    "is_cantilever": is_cantilever, "defl_location": defl_location
                }
                pdf_bytes = generate_beam_report(data, mat_props, beam_geom, res_left, res_mid, res_right, defl_data)
                return Response(
                    content=pdf_bytes, 
                    media_type="application/pdf", 
                    headers={"Content-Disposition": 'attachment; filename="beam_report.pdf"'}
                )

            hidden_inputs = [air.Input(type="hidden", name=k, value=str(v)) for k, v in data.model_dump().items() if k != "generate_pdf"]
            if "csrf_token" in form_data:
                hidden_inputs.append(air.Input(type="hidden", name="csrf_token", value=form_data.get("csrf_token")))

            report_content = air.Main(
                air.Div(
                    air.Form(
                        *hidden_inputs,
                        air.Input(type="hidden", name="generate_pdf", value="1"),
                        air.Button("Print Summary", onclick="window.print()", type="button", style="background-color: var(--accent); color: var(--bg-deep); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 600;"),
                        air.Button("Generate Detailed Report", type="submit", style="background-color: var(--accent); color: var(--bg-deep); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 600;"),
                        method="post", action="/beam/design", style="display: flex; justify-content: flex-end; align-items: center; gap: 8px;"
                    ),
                    style="margin-bottom: 24px;", class_="no-print"
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
                                       air.Span(f"{data.width}mm × {data.height}mm (d = {data.effective_depth}mm)",
                                                class_="data-value")),
                                air.Li(air.Strong("Spans"),
                                       air.Span(f"L = {data.length}mm, Ln = {data.clear_span}mm", class_="data-value")),
                                air.Li(air.Strong("Seismic"),
                                       air.Span(f"SDC {data.sdc}, {frame_enum.value.title()}", class_="data-value")),
                                air.Li(air.Strong("Concrete"),
                                       air.Span(f"f'c = {data.fc_prime} MPa", class_="data-value")),
                                air.Li(air.Strong("Steel"),
                                       air.Span(f"fy = {data.fy} MPa, fyt = {data.fyt} MPa", class_="data-value")),
                                air.Li(air.Strong("Rebar sizes"), air.Span(
                                    f"Main {data.pref_main}, Stirrups {data.pref_stirrup}, Web {data.pref_torsion}",
                                    class_="data-value")),
                            ), class_="section-box"
                        ),
                        air.Div(
                            air.H3("Loads", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                            air.Table(
                                air.Thead(air.Tr(air.Th("Force"), air.Th("Left"), air.Th("Midspan"), air.Th("Right"))),
                                air.Tbody(
                                    air.Tr(air.Td(air.Strong("-Mu (kN·m)")), air.Td(str(data.left_mu_neg)),
                                           air.Td(str(data.mid_mu_neg)), air.Td(str(data.right_mu_neg))),
                                    air.Tr(air.Td(air.Strong("+Mu (kN·m)")), air.Td(str(data.left_mu_pos)),
                                           air.Td(str(data.mid_mu_pos)), air.Td(str(data.right_mu_pos))),
                                    air.Tr(air.Td(air.Strong("Vu (kN)")), air.Td(str(data.left_vu)),
                                           air.Td(str(data.mid_vu)), air.Td(str(data.right_vu))),
                                    air.Tr(air.Td(air.Strong("Tu (kN·m)")), air.Td(str(data.left_tu)),
                                           air.Td(str(data.mid_tu)), air.Td(str(data.right_tu))),
                                    air.Tr(air.Td(air.Strong("Vg (kN)")), air.Td(str(data.left_vg)), air.Td("-"),
                                           air.Td(str(data.right_vg))),
                                    air.Tr(air.Td(air.Strong("Md (kN-m)")), air.Td("-"), air.Td(str(data.mid_mdead)),
                                           air.Td("-")),
                                    air.Tr(air.Td(air.Strong("Ml (kN-m)")), air.Td("-"), air.Td(str(data.mid_mlive)),
                                           air.Td("-"))
                                )
                            ), class_="section-box"
                        ), class_="grid-2"
                    ), class_="card"
                ),
                air.Div(class_="page-break"),
                air.Div(
                    air.H2("Serviceability Checks"),
                    generate_beam_elevation_css(data.length, data.height, res_left, res_mid, res_right),
                    air.Div(
                        air.Div(
                            air.P(air.Strong(f"Immediate live load deflection at {defl_location} = "),
                                  air.Span(f"{delta_live:.2f} mm",
                                           style=f"color: {status_live}; font-weight: 700;"),
                                  air.Span(
                                      f" {delta_live:.2f} mm {'≤' if delta_live <= lim_live else '>'} L/360 = {lim_live:.1f} mm",
                                      class_=f"status-badge {'pass' if delta_live <= lim_live else 'fail'}")),
                            style=f"padding: 16px; border-radius: 8px; border: 1px solid {'#bbf7d0' if delta_live <= lim_live else '#fecaca'}; background: {'#f0fdf4' if delta_live <= lim_live else '#fef2f2'}; margin-bottom: 12px;"),
                        air.Div(
                            air.P(air.Strong(f"Long-term deflection at {defl_location} = "), air.Span(f"{delta_long:.2f} mm",
                                                                                  style=f"color: {status_long}; font-weight: 700;"),
                                  air.Span(
                                      f" {delta_long:.2f} mm {'≤' if delta_long <= lim_long else '>'} L/{int(lim_long_divisor)} = {lim_long:.1f} mm",
                                      class_=f"status-badge {'pass' if delta_long <= lim_long else 'fail'}")),
                            style=f"padding: 16px; border-radius: 8px; border: 1px solid {'#bbf7d0' if delta_long <= lim_long else '#fecaca'}; background: {'#f0fdf4' if delta_long <= lim_long else '#fef2f2'};"),
                        air.Div(
                            air.P(air.Strong("Properties"), style="font-size: 13px; color: var(--text-muted); margin-bottom: 4px;"),
                            air.Ul(
                                air.Li(air.Strong("M_cr"), air.Span(f"{M_cr:.1f} kN-m", class_="data-value")),
                                air.Li(air.Strong("I_g"), air.Span(f"{Ig / 1e6:.0f} \u00d7 10\u2076 mm\u2074", class_="data-value")),
                                air.Li(air.Strong("I_cr"), air.Span(f"{Icr / 1e6:.0f} \u00d7 10\u2076 mm\u2074", class_="data-value")),
                                air.Li(air.Strong("I_e"), air.Span(f"{Ie_tot / 1e6:.0f} \u00d7 10\u2076 mm\u2074", class_="data-value")),
                                air.Li(air.Strong("Mode"), air.Span(f"Cantilever ({defl_location})" if is_cantilever else "Span beam", class_="data-value")),
                            ),
                            style="padding: 0 16px;"
                        ),
                        style="margin-bottom: 16px;"
                    ), class_="card"
                ),
                air.Div(
                    air.H2("Design Results"),
                    air.Div(
                        render_section_results("Left support", res_left, data.width, data.height, cover),
                        render_section_results("Midspan", res_mid, data.width, data.height, cover),
                        render_section_results("Right support", res_right, data.width, data.height, cover),
                        class_="grid-3"
                    ), class_="card"
                ),
                air.Div(
                    air.H2("Material Takeoff"),
                    air.Div(
                        air.Div(air.Div("CONCRETE", class_="metric-label"),
                                air.Div(f"{vol_concrete:.2f} m³", class_="metric-value"), class_="metric-card concrete"),
                        air.Div(air.Div("FORMWORK", class_="metric-label"),
                                air.Div(f"{area_formwork:.2f} m²", class_="metric-value"), class_="metric-card formwork"),
                        air.Div(air.Div("REBAR WEIGHT", class_="metric-label"),
                                air.Div(f"{total_kg:.1f} kg", class_="metric-value"), class_="metric-card rebar"),
                        class_="grid-3"
                    ),
                    air.Table(air.Thead(
                        air.Tr(air.Th("Location"), air.Th("Size"), air.Th("Qty"), air.Th("Required Length/Bar"),
                               air.Th("Recommended Order"), air.Th("Weight"))), air.Tbody(*rebar_rows)),
                    class_="card"
                )
            )

            full_html_layout = str(blueprint_layout(
                air.Header(
                    air.A("← Edit Inputs", href="/beam", class_="back-link no-print"),
                    air.H1("RC Beam Designer"),
                    air.P("in accordance with ACI 318M-25", class_="subtitle"),
                    class_="module-header"
                ),
                report_content
            ))

            resp = AirResponse(content=full_html_layout, media_type="text/html")
            resp.set_cookie("beam_inputs", cookie_data, max_age=2592000)
            return resp

        except Exception as e:
            error_html = str(blueprint_layout(
                air.Header(
                    air.A("← Go Back", href="/beam", class_="back-link no-print"),
                    air.H1("Calculation Error"),
                    air.P("Failed to process section demands.", class_="subtitle"),
                    class_="module-header"
                ),
                air.Main(air.Div(air.H2("Validation Failed", style="color: #DC2626;"), air.P(str(e)), class_="card"))
            ))
            resp = AirResponse(content=error_html, media_type="text/html")
            resp.set_cookie("beam_inputs", cookie_data, max_age=2592000)
            return resp