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
from aci318m25_column import ACI318M25ColumnDesign, ColumnGeometry, ColumnType, ColumnShape, LoadCondition, SeismicDesignCategory, FrameSystem, ColumnLoads
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
    width: float = AirField(default=500.0)
    depth: float = AirField(default=500.0)
    height: float = AirField(default=3500.0)
    clear_height: float = AirField(default=3000.0)
    
    # Seismic & Framing
    sdc: str = AirField(default="D")
    frame_system: str = AirField(default="special")
    
    # Preferences
    pref_main: str = AirField(default="D25")
    pref_tie: str = AirField(default="D10")
    
    # Materials
    fc_prime: float = AirField(default=35.0)
    fy: float = AirField(default=420.0)
    fyt: float = AirField(default=420.0)
    
    # Top Forces
    top_pu: float = AirField(default=2500.0)
    top_mux: float = AirField(default=150.0)
    top_muy: float = AirField(default=50.0)
    top_vux: float = AirField(default=120.0)
    top_vuy: float = AirField(default=30.0)
    
    # Mid Forces
    mid_pu: float = AirField(default=2550.0)
    mid_mux: float = AirField(default=80.0)
    mid_muy: float = AirField(default=25.0)
    mid_vux: float = AirField(default=120.0)
    mid_vuy: float = AirField(default=30.0)
    
    # Bottom Forces
    bot_pu: float = AirField(default=2600.0)
    bot_mux: float = AirField(default=160.0)
    bot_muy: float = AirField(default=55.0)
    bot_vux: float = AirField(default=120.0)
    bot_vuy: float = AirField(default=30.0)

# ----------------------------------------------------------------------
# 2. OVERRIDE ENGINE & QTO ALGORITHMS
# ----------------------------------------------------------------------
class ControlledColumnDesign(ACI318M25ColumnDesign):
    def __init__(self, pref_main: str, pref_tie: str):
        super().__init__()
        self.pref_main = pref_main
        self.pref_tie = pref_tie

    def select_longitudinal_reinforcement(self, As_required: float, geometry: ColumnGeometry, aggregate_size: float = 25.0, assumed_tie: str = 'D10') -> list:
        area = self.aci.get_bar_area(self.pref_main)
        min_bars = 4 if geometry.shape == ColumnShape.RECTANGULAR else 6
        num_bars = max(min_bars, math.ceil(As_required / area))
        if geometry.shape == ColumnShape.RECTANGULAR and num_bars % 2 != 0:
            num_bars += 1
        return [self.pref_main] * num_bars

    def design_tie_reinforcement(self, geometry, longitudinal_bars, loads, material_props):
        if longitudinal_bars:
            long_bar_diameter = self.aci.get_bar_diameter(longitudinal_bars[0])
        else:
            long_bar_diameter = 20.0
            
        tie_size = self.pref_tie  # INJECT PREFERRED TIE SIZE HERE
        tie_diameter = self.aci.get_bar_diameter(tie_size)
        tie_legs_x, tie_legs_y = 2, 2
        
        if geometry.shape == ColumnShape.RECTANGULAR and len(longitudinal_bars) >= 4:
            num_bars = len(longitudinal_bars)
            nx = max(2, int(round((geometry.width / (geometry.width + geometry.depth)) * (num_bars / 2.0))) + 1)
            ny = max(2, int((num_bars + 4 - 2 * nx) / 2))
            
            if nx > 1:
                clear_x = (geometry.width - 2 * geometry.cover - 2 * tie_diameter - long_bar_diameter) / (nx - 1) - long_bar_diameter
                tie_legs_y = nx if clear_x > 150.0 else math.ceil(nx / 2.0) + (1 if nx % 2 == 0 else 0)
            if ny > 1:
                clear_y = (geometry.depth - 2 * geometry.cover - 2 * tie_diameter - long_bar_diameter) / (ny - 1) - long_bar_diameter
                tie_legs_x = ny if clear_y > 150.0 else math.ceil(ny / 2.0) + (1 if ny % 2 == 0 else 0)

        if geometry.frame_system == FrameSystem.SPECIAL:
            min_col_dim = min(geometry.width, geometry.depth)
            hx_approx = min_col_dim / min(tie_legs_x, tie_legs_y)
            sx = max(100.0, min(100.0 + (350.0 - hx_approx) / 3.0, 150.0))
            spacing_confinement = min(min_col_dim / 4.0, 6.0 * long_bar_diameter, sx)
            
            fc_prime, fyt = material_props.fc_prime, material_props.fyt
            Ag = geometry.width * geometry.depth
            bc_x, bc_y = geometry.depth - 2 * geometry.cover, geometry.width - 2 * geometry.cover
            Ach = bc_x * bc_y
            
            Ash_req_x = max(0.3 * (spacing_confinement * bc_x * fc_prime / fyt) * (Ag / Ach - 1.0), 0.09 * spacing_confinement * bc_x * fc_prime / fyt)
            Ash_req_y = max(0.3 * (spacing_confinement * bc_y * fc_prime / fyt) * (Ag / Ach - 1.0), 0.09 * spacing_confinement * bc_y * fc_prime / fyt)
            
            A_tie = self.aci.get_bar_area(tie_size)
            while (tie_legs_x * A_tie < Ash_req_x) or (tie_legs_y * A_tie < Ash_req_y):
                if tie_size == 'D10': tie_size = 'D12'
                elif tie_size == 'D12': tie_size = 'D16'
                else: tie_legs_x += 1; tie_legs_y += 1
                A_tie = self.aci.get_bar_area(tie_size)
        else:
            spacing_confinement = min(16 * long_bar_diameter, 48 * tie_diameter, min(geometry.width, geometry.depth))

        fc_prime, fy_tie, phi_v = material_props.fc_prime, material_props.fyt, self.phi_factors['shear']
        A_tie_leg = self.aci.get_bar_area(tie_size)
        dx, dy = geometry.width - geometry.cover - tie_diameter - (long_bar_diameter / 2), geometry.depth - geometry.cover - tie_diameter - (long_bar_diameter / 2)
        
        Vu_x, Av_x = abs(loads.shear_x) * 1000, tie_legs_x * A_tie_leg
        Vc_x = 0.17 * math.sqrt(fc_prime) * geometry.depth * dx
        Vs_req_x = max(0.0, (Vu_x / phi_v) - Vc_x)
        s_shear_x = (Av_x * fy_tie * dx) / Vs_req_x if Vs_req_x > 0 else float('inf')
        max_s_shear_x = dx / 4.0 if Vs_req_x > 0.33 * math.sqrt(fc_prime) * geometry.depth * dx else dx / 2.0

        Vu_y, Av_y = abs(loads.shear_y) * 1000, tie_legs_y * A_tie_leg
        Vc_y = 0.17 * math.sqrt(fc_prime) * geometry.width * dy
        Vs_req_y = max(0.0, (Vu_y / phi_v) - Vc_y)
        s_shear_y = (Av_y * fy_tie * dy) / Vs_req_y if Vs_req_y > 0 else float('inf')
        max_s_shear_y = dy / 4.0 if Vs_req_y > 0.33 * math.sqrt(fc_prime) * geometry.width * dy else dy / 2.0

        s_final = max(math.floor(min(spacing_confinement, s_shear_x, s_shear_y, max_s_shear_x, max_s_shear_y) / 10.0) * 10.0, 50.0)
        return tie_size, s_final, tie_legs_x, tie_legs_y

def get_best_commercial_length(required_length_m, db_mm):
    commercial_lengths, splice_len_m = [6.0, 7.5, 9.0, 10.5, 12.0], (40 * db_mm) / 1000.0
    for stock in commercial_lengths:
        if required_length_m <= stock: return f"1 x {stock}m", stock, 0
    effective_stock_len = 12.0 - splice_len_m
    num_bars = math.ceil(required_length_m / effective_stock_len)
    return f"{num_bars} x 12.0m", num_bars * 12.0, num_bars - 1

def calculate_qto(geom, res_top, res_mid, res_bot):
    L_m, w_m, d_m = geom.height / 1000.0, geom.width / 1000.0, geom.depth / 1000.0
    vol_concrete, area_formwork = w_m * d_m * L_m, 2 * (w_m + d_m) * L_m
    rebar_rows, total_kg = [], 0.0

    def get_db(bars_list):
        if not bars_list: return 0.0
        val = bars_list[0] if isinstance(bars_list, list) else bars_list
        try: return float(val.replace('D', ''))
        except: return 16.0

    # 1. Main Longitudinal Bars
    if res_mid.reinforcement.longitudinal_bars:
        db = get_db(res_mid.reinforcement.longitudinal_bars)
        num_bars = len(res_mid.reinforcement.longitudinal_bars)
        req_len_per_bar = L_m + (40 * db / 1000.0) # Add lap splice allowance
        stock_text, total_ordered_m_per_bar, _ = get_best_commercial_length(req_len_per_bar, db)
        weight_kg = (total_ordered_m_per_bar * num_bars) * ((db**2) / 162.0)
        total_kg += weight_kg
        rebar_rows.append(air.Tr(air.Td(air.Strong("Longitudinal")), air.Td(f"D{int(db)}"), air.Td(str(num_bars)), air.Td(f"{req_len_per_bar:.2f}m"), air.Td(air.Span(stock_text, style="color: #db2777; font-weight: 600;")), air.Td(f"{weight_kg:.1f} kg")))

    # 2. Ties/Hoops
    if res_mid.reinforcement.tie_bars:
        db_t = get_db([res_mid.reinforcement.tie_bars])
        legs_x, legs_y = res_mid.reinforcement.tie_legs_x, res_mid.reinforcement.tie_legs_y
        
        # Calculate zones
        lo = max(max(geom.width, geom.depth), geom.clear_height / 6.0, 450.0) if geom.frame_system == FrameSystem.SPECIAL else 0
        s_hinge = max(res_top.reinforcement.tie_spacing, 50) / 1000.0
        s_mid = max(res_mid.reinforcement.tie_spacing, 50) / 1000.0
        
        L_mid = max(0, L_m - 2*(lo/1000.0))
        total_stirrups = int(2 * (lo/1000.0) / s_hinge) + int(L_mid / s_mid) if lo > 0 else int(L_m / s_mid)

        c_m = geom.cover / 1000.0
        tie_len_m = 2*(w_m - 2*c_m) + 2*(d_m - 2*c_m) + (legs_x - 2)*(d_m - 2*c_m) + (legs_y - 2)*(w_m - 2*c_m) + (24 * db_t / 1000.0)
        weight_kg = (total_stirrups * tie_len_m) * ((db_t**2) / 162.0)
        total_kg += weight_kg
        rebar_rows.append(air.Tr(air.Td(air.Strong("Ties / Hoops")), air.Td(f"D{int(db_t)}"), air.Td(str(total_stirrups)), air.Td(f"{tie_len_m:.2f}m"), air.Td(f"Cut from 12m"), air.Td(f"{weight_kg:.1f} kg")))

    return vol_concrete, area_formwork, total_kg, rebar_rows

# ----------------------------------------------------------------------
# 3. VISUALIZATION COMPONENTS
# ----------------------------------------------------------------------
def generate_column_elevation_css(geom, res_top, res_mid, res_bot):
    vis_h = 300
    vis_w = max(40, min(100, vis_h * (geom.width / geom.height)))
    
    lo = max(max(geom.width, geom.depth), geom.clear_height / 6.0, 450.0) if geom.frame_system == FrameSystem.SPECIAL else 0
    lo_pct = (lo / geom.height) * 100 if geom.height > 0 else 0

    tie_elements = []
    y, loop_guard = 5.0, 0
    while y < 95.0 and loop_guard < 100:
        loop_guard += 1
        if y <= 5.0 + lo_pct or y >= 95.0 - lo_pct: s_pct, color, z = max((res_top.reinforcement.tie_spacing/geom.height)*100, 2), "#db2777", 2
        else: s_pct, color, z = max((res_mid.reinforcement.tie_spacing/geom.height)*100, 4), "#9ca3af", 1
        tie_elements.append(air.Div(style=f"position: absolute; top: {y}%; left: 10%; right: 10%; height: 2px; background: {color}; z-index: {z};"))
        y += s_pct

    col_body = air.Div(
        air.Div(style="position: absolute; left: 15%; top: 0; bottom: 0; width: 4px; background: #2563eb; z-index: 3;"),
        air.Div(style="position: absolute; right: 15%; top: 0; bottom: 0; width: 4px; background: #2563eb; z-index: 3;"),
        *tie_elements, style=f"position: relative; width: {vis_w}px; height: {vis_h}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 2px; margin: 0 auto; overflow: hidden; box-sizing: border-box;"
    )
    
    labels = air.Div(
        air.Div(f"lo ({lo:.0f}mm)", style=f"position: absolute; right: -80px; top: 0; font-size: 11px; color: #db2777; font-weight: bold; height: {lo_pct}%; border-left: 2px solid #db2777; padding-left: 6px; display: flex; align-items: center;"),
        air.Div(f"lo ({lo:.0f}mm)", style=f"position: absolute; right: -80px; bottom: 0; font-size: 11px; color: #db2777; font-weight: bold; height: {lo_pct}%; border-left: 2px solid #db2777; padding-left: 6px; display: flex; align-items: center;"),
        col_body,
        style=f"position: relative; width: {vis_w}px; margin: 0 auto;"
    )
    return air.Div(labels, style="padding: 24px; background: #ffffff; border-radius: 8px; border: 2px dashed #e5e7eb; margin-bottom: 32px; display: flex; justify-content: center;")

def generate_column_section_css(geom, reinforcement):
    scale = min(200 / max(geom.width, 1), 200 / max(geom.depth, 1))
    draw_w, draw_h, c_s = geom.width * scale, geom.depth * scale, geom.cover * scale

    children = []
    tie_w, tie_h = draw_w - 2 * c_s, draw_h - 2 * c_s
    
    if tie_w > 0 and tie_h > 0:
        children.append(air.Div(style=f"position: absolute; left: {c_s}px; top: {c_s}px; width: {tie_w}px; height: {tie_h}px; border: 2px dashed #db2777; border-radius: 6px; box-sizing: border-box;"))
        # Inner ties X
        if reinforcement.tie_legs_x > 2:
            spacing_y = tie_h / (reinforcement.tie_legs_x - 1)
            for i in range(1, reinforcement.tie_legs_x - 1):
                children.append(air.Div(style=f"position: absolute; left: {c_s}px; top: {c_s + i * spacing_y}px; width: {tie_w}px; height: 0px; border-top: 2px dashed #db2777; box-sizing: border-box;"))
        # Inner ties Y
        if reinforcement.tie_legs_y > 2:
            spacing_x = tie_w / (reinforcement.tie_legs_y - 1)
            for i in range(1, reinforcement.tie_legs_y - 1):
                children.append(air.Div(style=f"position: absolute; left: {c_s + i * spacing_x}px; top: {c_s}px; width: 0px; height: {tie_h}px; border-left: 2px dashed #db2777; box-sizing: border-box;"))

    designer = ACI318M25ColumnDesign()
    layout = designer.generate_bar_layout(geom, reinforcement.longitudinal_bars, reinforcement.tie_bars)
    
    for x, y, _ in layout:
        css_x = (geom.width / 2 + x) * scale - 6
        css_y = (geom.depth / 2 - y) * scale - 6
        children.append(air.Div(style=f"position: absolute; left: {css_x}px; top: {css_y}px; width: 12px; height: 12px; background: #2563eb; border: 2px solid #111827; border-radius: 50%; box-sizing: border-box;"))

    concrete_block = air.Div(*children, style=f"position: relative; width: {draw_w}px; height: {draw_h}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px; box-sizing: border-box;")
    return air.Div(
        air.Div(f"{geom.width} mm", style="text-align: center; font-family: monospace; font-weight: 700; color: #6b7280; margin-bottom: 8px;"),
        air.Div(air.Div(f"{geom.depth} mm", style="position: absolute; left: -65px; top: 50%; transform: translateY(-50%); font-family: monospace; font-weight: 700; color: #6b7280;"), concrete_block, style="position: relative; display: inline-block; margin-left: 40px;"),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px 0; margin-bottom: 24px; background: #ffffff; border-radius: 8px; border: 2px dashed #e5e7eb;"
    )

def render_force_inputs(title, prefix, data):
    fields = [
        air.Div(air.Label("Factored axial Pu (kN)"), air.Input(type="number", name=f"{prefix}_pu", value=str(getattr(data, f"{prefix}_pu")), step="any", required=True), class_="form-group"),
        air.Div(air.Label("Factored moment Mux (kN·m)"), air.Input(type="number", name=f"{prefix}_mux", value=str(getattr(data, f"{prefix}_mux")), step="any", required=True), class_="form-group"),
        air.Div(air.Label("Factored moment Muy (kN·m)"), air.Input(type="number", name=f"{prefix}_muy", value=str(getattr(data, f"{prefix}_muy")), step="any", required=True), class_="form-group"),
        air.Div(air.Label("Factored shear Vux (kN)"), air.Input(type="number", name=f"{prefix}_vux", value=str(getattr(data, f"{prefix}_vux")), step="any", required=True), class_="form-group"),
        air.Div(air.Label("Factored shear Vuy (kN)"), air.Input(type="number", name=f"{prefix}_vuy", value=str(getattr(data, f"{prefix}_vuy")), step="any", required=True), class_="form-group")
    ]
    return air.Div(air.H3(title), *fields, class_="section-box")

def render_section_results(title, result, geom):
    main_bars = f"{len(result.reinforcement.longitudinal_bars)}x{result.reinforcement.longitudinal_bars[0]}" if result.reinforcement.longitudinal_bars else "None"
    transverse_str = f"{result.reinforcement.tie_bars} @ {result.reinforcement.tie_spacing:.0f} mm"
    legs_str = f"({result.reinforcement.tie_legs_x} legs X, {result.reinforcement.tie_legs_y} legs Y)"
    status_color = "#16A34A" if result.utilization_ratio <= 1.0 else "#DC2626"
    
    css_diagram = generate_column_section_css(geom, result.reinforcement)

    return air.Div(
        air.H3(title), css_diagram,
        air.H4("Capacities"),
        air.Ul(
            air.Li(air.Strong("Axial (φPn)"), air.Span(f"{result.capacity.axial_capacity:.1f} kN", class_="data-value")),
            air.Li(air.Strong("Shear (φVnx / φVny)"), air.Span(f"{result.capacity.shear_capacity_x:.1f} / {result.capacity.shear_capacity_y:.1f} kN", class_="data-value")),
            air.Li(air.Strong("DCR"), air.Span(f"{result.utilization_ratio:.2f}", class_="data-value", style=f"color: {status_color};"))
        ),
        air.H4("Reinforcements"),
        air.Ul(
            air.Li(air.Strong("Main bar"), air.Span(main_bars, class_="data-value", style="color: #2563eb;")),
            air.Li(air.Strong("Ties"), air.Span(transverse_str, class_="data-value", style="color: #db2777;")),
            air.Li(air.Strong("Tie arrangement"), air.Span(legs_str, class_="data-value"))
        ),
        class_="section-box"
    )

# ----------------------------------------------------------------------
# 4. MODULE ROUTES
# ----------------------------------------------------------------------
def setup_column_routes(app):
    """Registers the Column Designer routes to the main application."""
    
    @app.get("/column")
    def column_index(request: air.Request):
        data = ColumnDesignModel()
        saved_inputs = request.cookies.get("column_inputs")
        if saved_inputs:
            try:
                parsed = json.loads(saved_inputs)
                data = ColumnDesignModel(**parsed)
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
                air.H1("RC Column Designer"),
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
                            air.Div(air.Label("Column width cx (mm)"), air.Input(type="number", name="width", value=str(data.width), required=True), class_="form-group"),
                            air.Div(air.Label("Column depth cy (mm)"), air.Input(type="number", name="depth", value=str(data.depth), required=True), class_="form-group"),
                            air.Div(air.Label("Total height (mm)"), air.Input(type="number", name="height", value=str(data.height), required=True), class_="form-group"),
                            air.Div(air.Label("Clear height (mm)"), air.Input(type="number", name="clear_height", value=str(data.clear_height), required=True), class_="form-group"),
                            
                            air.Div(air.Label("Seismic Design Category"), air.Select(air.Option("A", value="A", selected=(data.sdc == "A")), air.Option("B", value="B", selected=(data.sdc == "B")), air.Option("C", value="C", selected=(data.sdc == "C")), air.Option("D", value="D", selected=(data.sdc == "D")), air.Option("E", value="E", selected=(data.sdc == "E")), air.Option("F", value="F", selected=(data.sdc == "F")), name="sdc"), class_="form-group"),
                            air.Div(air.Label("Moment frame system"), air.Select(air.Option("Ordinary", value="ordinary", selected=(data.frame_system == "ordinary")), air.Option("Intermediate", value="intermediate", selected=(data.frame_system == "intermediate")), air.Option("Special (SMF)", value="special", selected=(data.frame_system == "special")), name="frame_system"), class_="form-group"),
                            
                            air.Div(air.Label("Concrete strength (MPa)"), air.Input(type="number", name="fc_prime", value=str(data.fc_prime), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Main bar yield strength (MPa)"), air.Input(type="number", name="fy", value=str(data.fy), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Tie yield strength (MPa)"), air.Input(type="number", name="fyt", value=str(data.fyt), step="any", required=True), class_="form-group"),
                            
                            air.Div(air.Label("Main bar diameter"), air.Select(*[air.Option(opt, selected=(data.pref_main == opt)) for opt in ["D10", "D12", "D16", "D20", "D25", "D28", "D32", "D36", "D40"]], name="pref_main"), class_="form-group"),
                            air.Div(air.Label("Tie diameter"), air.Select(*[air.Option(opt, selected=(data.pref_tie == opt)) for opt in ["D10", "D12", "D16", "D20"]], name="pref_tie"), class_="form-group"),
                            class_="grid-3"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Loads"),
                        air.Div(
                            render_force_inputs("Top", "top", data),
                            render_force_inputs("Midheight", "mid", data),
                            render_force_inputs("Bottom", "bot", data),
                            class_="grid-3"
                        ),
                        air.Button("Perform Design", type="submit", style="width: 100%; font-size: 18px; margin-top: 32px;"),
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
                air.Header(
                    air.A("← Go Back", href="/column", class_="back-link no-print"),
                    air.H1("Calculation Error"), 
                    air.P("Form validation failed.", class_="subtitle"),
                    class_="module-header"
                ),
                air.Main(air.Div(air.H2("Invalid Inputs", style="color: #DC2626;"), air.P(str(e)), class_="card"))
            ))
            resp = AirResponse(content=error_html, media_type="text/html")
            resp.set_cookie("column_inputs", cookie_data, max_age=2592000)
            return resp
        
        try:
            sdc_enum, frame_enum = SeismicDesignCategory(data.sdc), FrameSystem(data.frame_system)
            cover = 40.0
            
            ec = base_aci_lib.aci.get_concrete_modulus(data.fc_prime)
            mat_props = MaterialProperties(fc_prime=data.fc_prime, fy=data.fy, fu=data.fy * 1.25, fyt=data.fyt, fut=data.fyt * 1.25, es=200000.0, ec=ec, gamma_c=24.0, description=f"Custom")
            
            col_geom = ColumnGeometry(
                width=data.width, depth=data.depth, height=data.height, clear_height=data.clear_height, cover=cover, 
                shape=ColumnShape.RECTANGULAR, column_type=ColumnType.TIED, effective_length=data.clear_height,
                sdc=sdc_enum, frame_system=frame_enum
            )
            
            loads_top = ColumnLoads(axial_force=data.top_pu, moment_x=data.top_mux, moment_y=data.top_muy, shear_x=data.top_vux, shear_y=data.top_vuy, load_condition=LoadCondition.BIAXIAL_BENDING)
            loads_mid = ColumnLoads(axial_force=data.mid_pu, moment_x=data.mid_mux, moment_y=data.mid_muy, shear_x=data.mid_vux, shear_y=data.mid_vuy, load_condition=LoadCondition.BIAXIAL_BENDING)
            loads_bot = ColumnLoads(axial_force=data.bot_pu, moment_x=data.bot_mux, moment_y=data.bot_muy, shear_x=data.bot_vux, shear_y=data.bot_vuy, load_condition=LoadCondition.BIAXIAL_BENDING)

            designer = ControlledColumnDesign(data.pref_main, data.pref_tie)
            
            res_top = designer.perform_complete_column_design(loads_top, col_geom, mat_props)
            res_mid = designer.perform_complete_column_design(loads_mid, col_geom, mat_props)
            res_bot = designer.perform_complete_column_design(loads_bot, col_geom, mat_props)
            
            vol_concrete, area_formwork, total_kg, rebar_rows = calculate_qto(col_geom, res_top, res_mid, res_bot)

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
                                air.Li(air.Strong("Dimensions"), air.Span(f"{data.width}mm × {data.depth}mm", class_="data-value")),
                                air.Li(air.Strong("Heights"), air.Span(f"H = {data.height}mm, Lu = {data.clear_height}mm", class_="data-value")),
                                air.Li(air.Strong("Seismic"), air.Span(f"SDC {data.sdc}, {frame_enum.value.title()}", class_="data-value")),
                                air.Li(air.Strong("Concrete"), air.Span(f"f'c = {data.fc_prime} MPa", class_="data-value")),
                                air.Li(air.Strong("Steel"), air.Span(f"fy = {data.fy} MPa, fyt = {data.fyt} MPa", class_="data-value")),
                                air.Li(air.Strong("Rebar sizes"), air.Span(f"Main {data.pref_main}, Ties {data.pref_tie}", class_="data-value")),
                            ), class_="section-box"
                        ),
                        air.Div(
                            air.H3("Loads", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                            air.Table(
                                air.Thead(air.Tr(air.Th("Force"), air.Th("Top"), air.Th("Mid"), air.Th("Bottom"))),
                                air.Tbody(
                                    air.Tr(air.Td(air.Strong("Pu (kN)")), air.Td(str(data.top_pu)), air.Td(str(data.mid_pu)), air.Td(str(data.bot_pu))),
                                    air.Tr(air.Td(air.Strong("Mux (kN·m)")), air.Td(str(data.top_mux)), air.Td(str(data.mid_mux)), air.Td(str(data.bot_mux))),
                                    air.Tr(air.Td(air.Strong("Muy (kN·m)")), air.Td(str(data.top_muy)), air.Td(str(data.mid_muy)), air.Td(str(data.bot_muy))),
                                    air.Tr(air.Td(air.Strong("Vux (kN)")), air.Td(str(data.top_vux)), air.Td(str(data.mid_vux)), air.Td(str(data.bot_vux))),
                                    air.Tr(air.Td(air.Strong("Vuy (kN)")), air.Td(str(data.top_vuy)), air.Td(str(data.mid_vuy)), air.Td(str(data.bot_vuy)))
                                )
                            ), class_="section-box"
                        ), class_="grid-2"
                    ), class_="card"
                ),
                air.Div(class_="page-break"),
                air.Div(
                    air.H2("Elevation View"),
                    generate_column_elevation_css(col_geom, res_top, res_mid, res_bot),
                    class_="card"
                ),
                air.Div(
                    air.H2("Design Results"),
                    air.Div(
                        render_section_results("Top", res_top, col_geom),
                        render_section_results("Midheight", res_mid, col_geom),
                        render_section_results("Bottom", res_bot, col_geom),
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
                    air.A("← Edit Inputs", href="/column", class_="back-link no-print"),
                    air.H1("Structural Design Report"), 
                    air.P("ACI 318M-25 Final Column Analysis", class_="subtitle"),
                    class_="module-header"
                ),
                report_content
            ))

            resp = AirResponse(content=full_html_layout, media_type="text/html")
            resp.set_cookie("column_inputs", cookie_data, max_age=2592000)
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
            resp = AirResponse(content=error_html, media_type="text/html")
            resp.set_cookie("column_inputs", cookie_data, max_age=2592000)
            return resp