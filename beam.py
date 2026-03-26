import air
from air import AirField, AirResponse
from pydantic import BaseModel
import math
import json
from datetime import date
import pdfkit

# Import the ACI 318M-25 library components
from aci318m25 import ConcreteStrengthClass, ReinforcementGrade, MaterialProperties
from aci318m25_complete import ACI318M25MemberLibrary
from aci318m25_beam import ACI318M25BeamDesign, BeamGeometry, BeamType, SeismicDesignCategory, FrameSystem
from shared import expressive_layout

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
    fc_prime: float = AirField(default=28.0)
    fy: float = AirField(default=420.0)
    fyt: float = AirField(default=420.0)
    left_mu: float = AirField(default=300.0)
    left_vu: float = AirField(default=180.0)
    left_tu: float = AirField(default=35.0)
    left_vg: float = AirField(default=80.0)
    mid_mu: float = AirField(default=200.0)
    mid_vu: float = AirField(default=50.0)
    mid_tu: float = AirField(default=5.0)
    mid_mlive: float = AirField(default=60.0)
    mid_msus: float = AirField(default=100.0)
    right_mu: float = AirField(default=280.0)
    right_vu: float = AirField(default=170.0)
    right_tu: float = AirField(default=15.0)
    right_vg: float = AirField(default=80.0)

# ----------------------------------------------------------------------
# 2. OVERRIDE ENGINE & QTO ALGORITHMS
# ----------------------------------------------------------------------
class ControlledBeamDesign(ACI318M25BeamDesign):
    def __init__(self, pref_main: str, pref_stirrup: str):
        super().__init__()
        self.pref_main = pref_main
        self.pref_stirrup = pref_stirrup

    def _select_reinforcement_bars(self, As_required: float, beam_geometry: BeamGeometry, fy: float, stirrup_size: str = 'D10', aggregate_size: float = 25.0) -> list:
        if As_required <= 0: return []
        area = self.aci.get_bar_area(self.pref_main)
        num_bars = max(2, math.ceil(As_required / area))
        return [self.pref_main] * num_bars

    def design_transverse_reinforcement(self, vu, tu, mpr, gravity_shear, beam_geometry, material_props, main_reinforcement):
        notes = []
        fc_prime, fy, fyt = material_props.fc_prime, material_props.fy, material_props.fyt 
        bw, d = beam_geometry.width, beam_geometry.effective_depth
        phi_v, phi_t = self.phi_factors['shear'], self.phi_factors['torsion']
        
        Vu, Tu, Ve = vu * 1000, tu * 1e6, vu * 1000
        if beam_geometry.frame_system == FrameSystem.SPECIAL and beam_geometry.clear_span > 0:
            Ve = max((gravity_shear * 1000) + ((2 * mpr * 1e6) / beam_geometry.clear_span), Vu)
            
        Vc = 0.17 * math.sqrt(fc_prime) * bw * d
        if beam_geometry.frame_system == FrameSystem.SPECIAL and (Ve - gravity_shear * 1000) > 0.5 * Ve: Vc = 0.0

        Vs_req = max(0.0, (Ve / phi_v) - Vc)
        Av_over_s = Vs_req / (fyt * d)
        
        torsion_required = self.check_torsion_requirement(tu, beam_geometry, material_props)
        props = self._calculate_torsional_properties(beam_geometry)
        At_over_s, Al_req = 0.0, 0.0
        
        if torsion_required:
            theta = math.radians(45)
            At_over_s = Tu / (phi_t * 2 * props['Ao'] * fyt * (1 / math.tan(theta)))
            At_over_s_min = max(At_over_s, 0.175 * bw / fyt)
            Al_req = max(At_over_s * props['ph'] * (fyt / fy) * (1 / math.tan(theta))**2, (0.42 * math.sqrt(fc_prime) * props['Acp'] / fy) - (At_over_s_min * props['ph'] * (fyt / fy)), 0.0)

        min_transverse = max(0.062 * math.sqrt(fc_prime) * bw / fyt, 0.35 * bw / fyt)
        sizes = [self.pref_stirrup] 
        max_legs = max(2, min(6, math.floor((bw - 2 * beam_geometry.cover) / 80) + 1))
        
        best_size, best_legs, s_req, found = self.pref_stirrup, 2, float('inf'), False
        for size in sizes:
            A_bar = self.aci.get_bar_area(size)
            for n in range(2, max_legs + 1):
                denom = At_over_s + (Av_over_s / n)
                s_demand = A_bar / denom if denom > 0 else float('inf')
                s_calc = min(s_demand, (n * A_bar) / min_transverse if min_transverse > 0 else float('inf'))
                if s_calc >= 75.0:
                    best_size, best_legs, s_req, found = size, n, s_calc, True
                    break
            if found: break
                
        if not found:
            best_legs = max_legs
            denom = At_over_s + (Av_over_s / best_legs)
            s_req = self.aci.get_bar_area(best_size) / denom if denom > 0 else 50.0
            
        stirrup_size = f"{best_legs}-leg {best_size}" if best_legs > 2 else best_size
        if best_legs > 2: notes.append(f"Demand exceeded 2-leg limits. Upgraded to {best_legs} legs.")

        s_span_max = min(d / 4, 300.0) if (Ve / phi_v - Vc) > (0.33 * math.sqrt(fc_prime) * bw * d) else min(d / 2, 600.0)
        if torsion_required: s_span_max = min(s_span_max, props['ph'] / 8, 300.0)
        
        s_hinge_max = min(d / 4, 6 * self.aci.get_bar_diameter(main_reinforcement.main_bars[0]), 150.0) if beam_geometry.frame_system == FrameSystem.SPECIAL else s_span_max 
        s_hinge_actual = math.floor(min(s_req, s_hinge_max) / 10) * 10
        s_span_actual = math.floor(min(s_req, s_span_max) / 10) * 10

        Tn_provided = (2 * props['Ao'] * self.aci.get_bar_area(best_size) * fyt / s_span_actual) / 1e6 if (torsion_required and s_span_actual > 0) else 0.0
        return stirrup_size, max(s_hinge_actual, 50.0), max(s_span_actual, 50.0), Ve / 1000, Al_req, Tn_provided, notes

def get_best_commercial_length(required_length_m, db_mm):
    commercial_lengths, splice_len_m = [6.0, 7.5, 9.0, 10.5, 12.0], (40 * db_mm) / 1000.0
    for stock in commercial_lengths:
        if required_length_m <= stock: return f"1 x {stock}m", stock, 0
    effective_stock_len = 12.0 - splice_len_m
    num_bars = math.ceil(required_length_m / effective_stock_len)
    return f"{num_bars} x 12.0m", num_bars * 12.0, num_bars - 1

def calculate_qto(geom, res_left, res_mid, res_right):
    L_m, w_m, h_m = geom.length / 1000.0, geom.width / 1000.0, geom.height / 1000.0
    vol_concrete, area_formwork = w_m * h_m * L_m, (w_m + 2 * h_m) * L_m
    rebar_rows, total_kg = [], 0.0

    def get_db(bars_list):
        if not bars_list: return 0.0
        val = bars_list[0] if isinstance(bars_list, list) else bars_list
        if "-leg" in val: val = val.split(" ")[1]
        try: return float(val.replace('D', ''))
        except: return 16.0

    def add_rebar(name, bars_list, theoretical_length_m, has_hooks=False):
        nonlocal total_kg
        if not bars_list: return
        db = get_db(bars_list)
        if db == 0: return
        num_bars = len(bars_list)
        req_len_per_bar = theoretical_length_m + (2 * ((12 * db + 100) / 1000.0 if has_hooks else 0.0))
        stock_text, total_ordered_m_per_bar, _ = get_best_commercial_length(req_len_per_bar, db)
        weight_kg = (total_ordered_m_per_bar * num_bars) * ((db**2) / 162.0)
        total_kg += weight_kg
        rebar_rows.append(air.Tr(air.Td(air.Strong(name)), air.Td(f"D{int(db)}"), air.Td(str(num_bars)), air.Td(f"{req_len_per_bar:.2f}m"), air.Td(air.Span(stock_text, style="color: #db2777; font-weight: 600;")), air.Td(f"{weight_kg:.1f} kg")))

    add_rebar("Bottom Continuous", res_mid.reinforcement.main_bars, L_m, has_hooks=True)
    add_rebar("Top Support (Left)", res_left.reinforcement.main_bars, L_m / 3, has_hooks=True)
    add_rebar("Top Support (Right)", res_right.reinforcement.main_bars, L_m / 3, has_hooks=True)
    add_rebar("Top Hanger (Midspan)", res_mid.reinforcement.compression_bars, L_m / 3, has_hooks=False)

    L_hl, s_hl = res_left.reinforcement.hinge_length, max(res_left.reinforcement.stirrup_spacing_hinge, 50) / 1000.0
    L_hr, s_hr = res_right.reinforcement.hinge_length, max(res_right.reinforcement.stirrup_spacing_hinge, 50) / 1000.0
    L_mid, s_m = max(0, L_m - (L_hl/1000.0) - (L_hr/1000.0)), max(res_mid.reinforcement.stirrup_spacing, 50) / 1000.0
    total_stirrups = int((L_hl/1000.0) / s_hl) + int((L_hr/1000.0) / s_hr) + int(L_mid / s_m)

    if total_stirrups > 0:
        db_s = get_db(res_mid.reinforcement.stirrups)
        legs = int(res_mid.reinforcement.stirrups.split('-')[0]) if "-leg" in res_mid.reinforcement.stirrups else 2
        c_m = geom.cover / 1000.0
        stirrup_len_m = (2*(w_m - 2*c_m) + 2*(h_m - 2*c_m) + (24 * db_s / 1000.0)) + ((legs - 2) * (h_m - 2*c_m + (12 * db_s / 1000.0)))
        weight_kg = (total_stirrups * stirrup_len_m) * ((db_s**2) / 162.0)
        total_kg += weight_kg
        rebar_rows.append(air.Tr(air.Td(air.Strong(f"Stirrups ({legs}-leg)")), air.Td(f"D{int(db_s)}"), air.Td(str(total_stirrups)), air.Td(f"{stirrup_len_m:.2f}m"), air.Td(f"Cut from 12m"), air.Td(f"{weight_kg:.1f} kg")))

    return vol_concrete, area_formwork, total_kg, rebar_rows

# ----------------------------------------------------------------------
# 3. VISUALIZATION COMPONENTS
# ----------------------------------------------------------------------
def generate_beam_elevation_css(length, height, res_left, res_mid, res_right):
    vis_height = max(100, min(240, 1000 * (height / length)))
    stirrup_elements = []
    s_hinge_left, hinge_len_left = max(res_left.reinforcement.stirrup_spacing_hinge, 50), res_left.reinforcement.hinge_length
    s_mid = max(res_mid.reinforcement.stirrup_spacing, 50)
    s_hinge_right, hinge_len_right = max(res_right.reinforcement.stirrup_spacing_hinge, 50), res_right.reinforcement.hinge_length

    x, loop_guard = 50.0, 0
    while x < length - 50.0 and loop_guard < 400:
        loop_guard += 1
        if x <= hinge_len_left: s, color, z_index = s_hinge_left, "#db2777", 2
        elif x >= length - hinge_len_right: s, color, z_index = s_hinge_right, "#db2777", 2
        else: s, color, z_index = s_mid, "#9ca3af", 1
        stirrup_elements.append(air.Div(style=f"position: absolute; left: {(x / length) * 100}%; top: 10%; bottom: 10%; width: 2px; background: {color}; z-index: {z_index};"))
        x += s

    beam_body = air.Div(
        air.Div(style="position: absolute; top: 12%; left: 0; right: 0; height: 4px; background: #2563eb; z-index: 3;"),
        air.Div(style="position: absolute; bottom: 12%; left: 0; right: 0; height: 4px; background: #2563eb; z-index: 3;"),
        *stirrup_elements, style=f"position: relative; width: 100%; height: {vis_height}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px; overflow: hidden; box-sizing: border-box;"
    )
    labels = air.Div(
        air.Div(f"Hinge ({hinge_len_left:.0f}mm)", style=f"position: absolute; left: 0; top: 100%; font-size: 12px; color: #db2777; font-weight: bold; width: {(hinge_len_left/length)*100}%; border-top: 2px solid #db2777; padding-top: 4px;"),
        air.Div(f"Midspan", style="position: absolute; left: 50%; top: 100%; font-size: 12px; color: #6b7280; transform: translateX(-50%); padding-top: 4px;"),
        air.Div(f"Hinge ({hinge_len_right:.0f}mm)", style=f"position: absolute; right: 0; top: 100%; font-size: 12px; color: #db2777; font-weight: bold; width: {(hinge_len_right/length)*100}%; border-top: 2px solid #db2777; padding-top: 4px; text-align: right;"),
        style="position: relative; width: 100%; height: 30px; margin-top: 4px;"
    )
    return air.Div(beam_body, labels, style="padding: 24px; background: #ffffff; border-radius: 8px; border: 2px dashed #e5e7eb; margin-bottom: 32px;")

def generate_beam_section_css(width, height, cover, stirrup_str, main_bars_list, comp_bars_list, is_support, torsion_req):
    top_bars, bottom_bars = (main_bars_list, comp_bars_list) if is_support else (comp_bars_list, main_bars_list)
    scale = min(200 / max(width, 1), 240 / max(height, 1))
    draw_w, draw_h, c_s = width * scale, height * scale, cover * scale

    children = []
    stirrup_w, stirrup_h = draw_w - 2 * c_s, draw_h - 2 * c_s
    legs = int(stirrup_str.split("-")[0]) if "-leg" in stirrup_str else 2
    
    if stirrup_w > 0 and stirrup_h > 0:
        children.append(air.Div(style=f"position: absolute; left: {c_s}px; top: {c_s}px; width: {stirrup_w}px; height: {stirrup_h}px; border: 2px dashed #db2777; border-radius: 6px; box-sizing: border-box;"))
        if legs > 2:
            inner_spacing = stirrup_w / (legs - 1)
            for i in range(1, legs - 1):
                children.append(air.Div(style=f"position: absolute; left: {c_s + i * inner_spacing}px; top: {c_s}px; width: 0px; height: {stirrup_h}px; border-left: 2px dashed #db2777; box-sizing: border-box;"))

    def create_css_bars(bars_list, is_top):
        bars = []
        if not bars_list: return bars
        db = float(bars_list[0].replace('D', '')) if 'D' in bars_list[0] else 20.0
        avail_w, min_s = width - 2*cover - 2*10, max(25.0, db)
        max_bars = max(2, int((avail_w + min_s) / (db + min_s)))
        layers, rem = [], len(bars_list)
        while rem > 0:
            take = min(rem, max_bars)
            layers.append(take)
            rem -= take
            
        for layer_idx, num_bars in enumerate(layers):
            y_pos = c_s + 4 + layer_idx * (12 + 25.0 * scale) if is_top else draw_h - c_s - 12 - 4 - layer_idx * (12 + 25.0 * scale)
            start_x, spacing = c_s + 4, (stirrup_w - 12 - 8) / (num_bars - 1) if num_bars > 1 else 0
            for i in range(num_bars):
                cx = start_x + (stirrup_w - 12 - 8)/2 if num_bars == 1 else start_x + i * spacing
                bars.append(air.Div(style=f"position: absolute; left: {cx}px; top: {y_pos}px; width: 12px; height: 12px; background: #2563eb; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))
        return bars

    children.extend(create_css_bars(top_bars, True))
    children.extend(create_css_bars(bottom_bars, False))
    
    if torsion_req:
        y_pos = (draw_h / 2) - 6
        children.append(air.Div(style=f"position: absolute; left: {c_s + 4}px; top: {y_pos}px; width: 12px; height: 12px; background: #D97706; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))
        children.append(air.Div(style=f"position: absolute; left: {draw_w - c_s - 16}px; top: {y_pos}px; width: 12px; height: 12px; background: #D97706; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))

    concrete_block = air.Div(*children, style=f"position: relative; width: {draw_w}px; height: {draw_h}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px; box-sizing: border-box;")
    return air.Div(
        air.Div(f"{width} mm", style="text-align: center; font-family: monospace; font-weight: 700; color: #6b7280; margin-bottom: 8px;"),
        air.Div(air.Div(f"{height} mm", style="position: absolute; left: -65px; top: 50%; transform: translateY(-50%); font-family: monospace; font-weight: 700; color: #6b7280;"), concrete_block, style="position: relative; display: inline-block; margin-left: 40px;"),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px 0; margin-bottom: 24px; background: #ffffff; border-radius: 8px; border: 2px dashed #e5e7eb;"
    )

def render_force_inputs(title, prefix, data, show_gravity=False, show_deflection=False):
    fields = [
        air.Div(air.Label("Factored load moment Mu (kN·m)"), air.Input(type="number", name=f"{prefix}_mu", value=str(getattr(data, f"{prefix}_mu")), step="any", required=True), class_="form-group"),
        air.Div(air.Label("Factored load shear Vu (kN)"), air.Input(type="number", name=f"{prefix}_vu", value=str(getattr(data, f"{prefix}_vu")), step="any", required=True), class_="form-group"),
        air.Div(air.Label("Factored load torsion Tu (kN·m)"), air.Input(type="number", name=f"{prefix}_tu", value=str(getattr(data, f"{prefix}_tu")), step="any", required=True), class_="form-group")
    ]
    if show_gravity: fields.append(air.Div(air.Label("Gravity load shear Vg (kN)"), air.Input(type="number", name=f"{prefix}_vg", value=str(getattr(data, f"{prefix}_vg")), step="any", required=True), class_="form-group"))
    else: fields.append(air.Input(type="hidden", name=f"{prefix}_vg", value="0"))
    if show_deflection:
        fields.append(air.Div(air.Label("Service live load moment (kN·m)"), air.Input(type="number", name=f"{prefix}_mlive", value=str(getattr(data, f"{prefix}_mlive")), step="any", required=True), class_="form-group"))
        fields.append(air.Div(air.Label("Sustained load moment (kN·m)"), air.Input(type="number", name=f"{prefix}_msus", value=str(getattr(data, f"{prefix}_msus")), step="any", required=True), class_="form-group"))
    else:
        fields.append(air.Input(type="hidden", name=f"{prefix}_mlive", value="0"))
        fields.append(air.Input(type="hidden", name=f"{prefix}_msus", value="0"))
    return air.Div(air.H3(title), *fields, class_="section-box")

def render_section_results(title, result, width, height, cover, is_support=False):
    main_bars = f"{len(result.reinforcement.main_bars)}x{result.reinforcement.main_bars[0]}" if result.reinforcement.main_bars else "None"
    comp_bars = f"{len(result.reinforcement.compression_bars)}x{result.reinforcement.compression_bars[0]}" if result.reinforcement.compression_bars else "None"
    transverse_str = f"{result.reinforcement.stirrups} @ {result.reinforcement.stirrup_spacing:.0f} mm"
    if is_support and result.reinforcement.stirrup_spacing_hinge > 0: transverse_str = f"{result.reinforcement.stirrups} @ {result.reinforcement.stirrup_spacing_hinge:.0f} mm (Hinge)"
        
    torsion_req = result.reinforcement.torsion_required
    torsion_str = f"Al = {result.reinforcement.torsion_longitudinal_area:.0f} mm²" if torsion_req else "Not Required"
    status_color = "#16A34A" if result.utilization_ratio <= 1.0 else "#DC2626"
    
    css_diagram = generate_beam_section_css(width, height, cover, result.reinforcement.stirrups, result.reinforcement.main_bars, result.reinforcement.compression_bars, is_support, torsion_req)

    return air.Div(
        air.H3(title), css_diagram,
        air.H4("Capacities"),
        air.Ul(
            air.Li(air.Strong("Flexure (φMn)"), air.Span(f"{result.moment_capacity:.1f} kN·m", class_="data-value")),
            air.Li(air.Strong("Shear (φVn / Ve)"), air.Span(f"{result.shear_capacity:.1f} / {result.capacity_shear_ve:.1f} kN", class_="data-value")),
            air.Li(air.Strong("Torsion (φTn)"), air.Span(f"{result.torsion_capacity:.1f} kN·m", class_="data-value")),
            air.Li(air.Strong("DCR"), air.Span(f"{result.utilization_ratio:.2f}", class_="data-value", style=f"color: {status_color};"))
        ),
        air.H4("Reinforcements"),
        air.Ul(
            air.Li(air.Strong("Tension bars"), air.Span(main_bars, class_="data-value", style="color: #2563eb;")),
            air.Li(air.Strong("Compression bars"), air.Span(comp_bars, class_="data-value")),
            air.Li(air.Strong("Stirrups"), air.Span(transverse_str, class_="data-value", style="color: #db2777;")),
            air.Li(air.Strong("Longitudinal torsion area"), air.Span(torsion_str, class_="data-value", style="color: #D97706;"))
        ),
        class_="section-box"
    )

# ----------------------------------------------------------------------
# 4. MODULE ROUTES
# ----------------------------------------------------------------------
def setup_beam_routes(app):
    """Registers the Beam Designer routes to the main application."""
    
    @app.get("/beam")
    def beam_index(request: air.Request):
        data = BeamDesignModel()
        saved_inputs = request.cookies.get("beam_inputs")
        if saved_inputs:
            try:
                parsed = json.loads(saved_inputs)
                data = BeamDesignModel(**parsed)
            except Exception: pass
                
        if not data.proj_date: data.proj_date = date.today().strftime("%Y-%m-%d")
            
        csrf_token = ""
        if hasattr(request, "state") and hasattr(request.state, "csrf_token"): csrf_token = request.state.csrf_token
        elif "csrftoken" in request.scope:
            token = request.scope["csrftoken"]
            csrf_token = token() if callable(token) else token
        elif "csrf_token" in request.scope:
            token = request.scope["csrf_token"]
            csrf_token = token() if callable(token) else token
        if not csrf_token: csrf_token = request.cookies.get("csrftoken", "dev_fallback_token")
        
        return expressive_layout(
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
                            air.Div(air.Label("Project Name"), air.Input(type="text", name="proj_name", value=data.proj_name, required=True), class_="form-group"),
                            air.Div(air.Label("Location"), air.Input(type="text", name="proj_loc", value=data.proj_loc, required=True), class_="form-group"),
                            air.Div(air.Label("Structural Engineer"), air.Input(type="text", name="proj_eng", value=data.proj_eng, required=True), class_="form-group"),
                            air.Div(air.Label("Date"), air.Input(type="date", name="proj_date", value=data.proj_date, required=True), class_="form-group"),
                            class_="grid-2"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Geometry and Materials"),
                        air.Div(
                            air.Div(air.Label("Beam width (mm)"), air.Input(type="number", name="width", value=str(data.width), required=True), class_="form-group"),
                            air.Div(air.Label("Beam depth (mm)"), air.Input(type="number", name="height", value=str(data.height), required=True), class_="form-group"),
                            air.Div(air.Label("Effective depth (mm)"), air.Input(type="number", name="effective_depth", value=str(data.effective_depth), required=True), class_="form-group"),
                            air.Div(air.Label("Center-to-center span (mm)"), air.Input(type="number", name="length", value=str(data.length), required=True), class_="form-group"),
                            air.Div(air.Label("Clear span (mm)"), air.Input(type="number", name="clear_span", value=str(data.clear_span), required=True), class_="form-group"),
                            air.Div(air.Label("Seismic Design Category"), air.Select(air.Option("A", value="A", selected=(data.sdc == "A")), air.Option("B", value="B", selected=(data.sdc == "B")), air.Option("C", value="C", selected=(data.sdc == "C")), air.Option("D", value="D", selected=(data.sdc == "D")), air.Option("E", value="E", selected=(data.sdc == "E")), air.Option("F", value="F", selected=(data.sdc == "F")), name="sdc"), class_="form-group"),
                            air.Div(air.Label("Concrete strength (MPa)"), air.Input(type="number", name="fc_prime", value=str(data.fc_prime), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Main bar yield strength (MPa)"), air.Input(type="number", name="fy", value=str(data.fy), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Stirrup yield strength (MPa)"), air.Input(type="number", name="fyt", value=str(data.fyt), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Moment frame system"), air.Select(air.Option("Ordinary", value="ordinary", selected=(data.frame_system == "ordinary")), air.Option("Intermediate", value="intermediate", selected=(data.frame_system == "intermediate")), air.Option("Special (SMF)", value="special", selected=(data.frame_system == "special")), name="frame_system"), class_="form-group"),
                            air.Div(air.Label("Main bar diameter"), air.Select(*[air.Option(opt, selected=(data.pref_main == opt)) for opt in ["D16", "D20", "D25", "D28", "D32"]], name="pref_main"), class_="form-group"),
                            air.Div(air.Label("Stirrup diameter"), air.Select(*[air.Option(opt, selected=(data.pref_stirrup == opt)) for opt in ["D10", "D12", "D16"]], name="pref_stirrup"), class_="form-group"),
                            class_="grid-3"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Section Forces (Demand)"),
                        air.Div(
                            render_force_inputs("Left support", "left", data, show_gravity=True),
                            render_force_inputs("Midspan", "mid", data, show_deflection=True),
                            render_force_inputs("Right support", "right", data, show_gravity=True),
                            class_="grid-3"
                        ),
                        air.Button("Analyze & View Report ✨", type="submit", style="width: 100%; font-size: 18px; margin-top: 32px;"),
                        class_="card"
                    ),
                    method="post", action="/beam/design"
                )
            )
        )

    @app.post("/beam/design")
    async def beam_design(request: air.Request):
        form_data = await request.form()
        cookie_data = json.dumps(dict(form_data))
        
        try:
            data = BeamDesignModel(**form_data)
        except Exception as e:
            error_html = str(expressive_layout(
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
            mat_props = MaterialProperties(fc_prime=data.fc_prime, fy=data.fy, fu=data.fy * 1.25, fyt=data.fyt, fut=data.fyt * 1.25, es=200000.0, ec=ec, gamma_c=24.0, description=f"Custom")
            beam_geom = BeamGeometry(length=data.length, width=data.width, height=data.height, effective_depth=data.effective_depth, cover=cover, flange_width=0.0, flange_thickness=0.0, beam_type=BeamType.RECTANGULAR, clear_span=data.clear_span, sdc=sdc_enum, frame_system=frame_enum)
            
            custom_lib = ACI318M25MemberLibrary()
            custom_lib.beam_design = ControlledBeamDesign(data.pref_main, data.pref_stirrup)
            
            res_left = custom_lib.beam_design.perform_complete_beam_design(mu=data.left_mu, vu=data.left_vu, tu=data.left_tu, gravity_shear=data.left_vg, beam_geometry=beam_geom, material_props=mat_props)
            res_mid = custom_lib.beam_design.perform_complete_beam_design(mu=data.mid_mu, vu=data.mid_vu, tu=data.mid_tu, beam_geometry=beam_geom, material_props=mat_props)
            res_right = custom_lib.beam_design.perform_complete_beam_design(mu=data.right_mu, vu=data.right_vu, tu=data.right_tu, gravity_shear=data.right_vg, beam_geometry=beam_geom, material_props=mat_props)
            
            vol_concrete, area_formwork, total_kg, rebar_rows = calculate_qto(beam_geom, res_left, res_mid, res_right)
            
            Ec, Ig = mat_props.ec, (data.width * (data.height**3)) / 12.0
            delta_live = (5 * data.mid_mlive * 1e6 * (data.length**2)) / (48 * Ec * Ig) if Ig > 0 else 0
            delta_sus = (5 * data.mid_msus * 1e6 * (data.length**2)) / (48 * Ec * Ig) if Ig > 0 else 0
            
            rho_prime = res_mid.reinforcement.compression_area / (data.width * data.effective_depth) if (data.width * data.effective_depth) > 0 else 0
            delta_long = delta_sus * (1 + (2.0 / (1 + 50 * rho_prime))) + delta_live
            
            lim_live, lim_long = data.length / 360, data.length / 240
            status_live = "#16A34A" if delta_live <= lim_live else "#DC2626"
            status_long = "#16A34A" if delta_long <= lim_long else "#DC2626"

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
                            air.H3("Geometry and Materials", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                            air.Ul(
                                air.Li(air.Strong("Dimensions"), air.Span(f"{data.width}mm × {data.height}mm (d = {data.effective_depth}mm)", class_="data-value")),
                                air.Li(air.Strong("Spans"), air.Span(f"L = {data.length}mm, Ln = {data.clear_span}mm", class_="data-value")),
                                air.Li(air.Strong("Seismic"), air.Span(f"SDC {data.sdc}, {frame_enum.value.title()}", class_="data-value")),
                                air.Li(air.Strong("Concrete"), air.Span(f"f'c = {data.fc_prime} MPa", class_="data-value")),
                                air.Li(air.Strong("Steel"), air.Span(f"fy = {data.fy} MPa, fyt = {data.fyt} MPa", class_="data-value")),
                                air.Li(air.Strong("Rebar sizes"), air.Span(f"Main {data.pref_main}, Ties {data.pref_stirrup}", class_="data-value")),
                            ), class_="section-box"
                        ),
                        air.Div(
                            air.H3("Loads", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                            air.Table(
                                air.Thead(air.Tr(air.Th("Force"), air.Th("Left"), air.Th("Midspan"), air.Th("Right"))),
                                air.Tbody(
                                    air.Tr(air.Td(air.Strong("Mu (kN·m)")), air.Td(str(data.left_mu)), air.Td(str(data.mid_mu)), air.Td(str(data.right_mu))),
                                    air.Tr(air.Td(air.Strong("Vu (kN)")), air.Td(str(data.left_vu)), air.Td(str(data.mid_vu)), air.Td(str(data.right_vu))),
                                    air.Tr(air.Td(air.Strong("Tu (kN·m)")), air.Td(str(data.left_tu)), air.Td(str(data.mid_tu)), air.Td(str(data.right_tu))),
                                    air.Tr(air.Td(air.Strong("Vg (kN)")), air.Td(str(data.left_vg)), air.Td("-"), air.Td(str(data.right_vg))),
                                    air.Tr(air.Td(air.Strong("M_live (kN·m)")), air.Td("-"), air.Td(str(data.mid_mlive)), air.Td("-")),
                                    air.Tr(air.Td(air.Strong("M_sus (kN·m)")), air.Td("-"), air.Td(str(data.mid_msus)), air.Td("-"))
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
                        air.Div(air.P(air.Strong("Immediate live load deflection = "), air.Span(f"{delta_live:.2f} mm", style=f"color: {status_live}; font-weight: 700;"), f" (Limit: L/360 = {lim_live:.1f} mm)"), style=f"padding: 16px; border-radius: 8px; border: 1px solid {'#bbf7d0' if delta_live <= lim_live else '#fecaca'}; background: {'#f0fdf4' if delta_live <= lim_live else '#fef2f2'}; margin-bottom: 12px;"),
                        air.Div(air.P(air.Strong("Long-term deflection = "), air.Span(f"{delta_long:.2f} mm", style=f"color: {status_long}; font-weight: 700;"), f" (Limit: L/240 = {lim_long:.1f} mm)"), style=f"padding: 16px; border-radius: 8px; border: 1px solid {'#bbf7d0' if delta_long <= lim_long else '#fecaca'}; background: {'#f0fdf4' if delta_long <= lim_long else '#fef2f2'};"),
                        style="margin-bottom: 16px;"
                    ), class_="card"
                ),
                air.Div(
                    air.H2("Design Results"),
                    air.Div(
                        render_section_results("Left support", res_left, data.width, data.height, cover, is_support=True),
                        render_section_results("Midspan", res_mid, data.width, data.height, cover, is_support=False),
                        render_section_results("Right support", res_right, data.width, data.height, cover, is_support=True),
                        class_="grid-3"
                    ), class_="card"
                ),
                air.Div(
                    air.H2("Material Takeoff"),
                    air.Div(
                        air.Div(air.Div("Concrete Volume", class_="metric-label"), air.Div(f"{vol_concrete:.2f} m³", class_="metric-value"), class_="metric-card"),
                        air.Div(air.Div("Formwork Area", class_="metric-label"), air.Div(f"{area_formwork:.2f} m²", class_="metric-value"), class_="metric-card blue"),
                        air.Div(air.Div("Rebar Weight", class_="metric-label"), air.Div(f"{total_kg:.1f} kg", class_="metric-value"), class_="metric-card green"),
                        class_="grid-3"
                    ),
                    air.Table(air.Thead(air.Tr(air.Th("Location"), air.Th("Size"), air.Th("Qty"), air.Th("Required Length/Bar"), air.Th("Recommended Order"), air.Th("Weight"))), air.Tbody(*rebar_rows)),
                    class_="card"
                )
            )

            full_html_layout = str(expressive_layout(
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
            error_html = str(expressive_layout(
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