import air
from air import AirField, AirResponse
from pydantic import BaseModel
import json
import hashlib
import os
import pickle
from datetime import date

from aci318m25 import MaterialProperties
from aci318m25_complete import ACI318M25MemberLibrary
from aci318m25_footing import (
    ACI318M25FootingDesign,
    FootingGeometry,
    FootingLoads,
    SoilProperties,
    FootingType,
)
from footing_pdf import generate_footing_report
from shared import blueprint_layout

base_aci_lib = ACI318M25MemberLibrary()


def _status_badge(text, passed):
    cls = "pass" if passed else "fail"
    return air.Span(text, class_=f"status-badge {cls}")


def _dcr_badge(dcr_val):
    if dcr_val <= 0.9:
        return air.Span(f"{dcr_val:.2f}", class_="status-badge dcr-ok")
    elif dcr_val <= 1.0:
        return air.Span(f"{dcr_val:.2f}", class_="status-badge dcr-warn")
    else:
        return air.Span(f"{dcr_val:.2f}", class_="status-badge fail")


_FOOTING_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".footing_cache")
os.makedirs(_FOOTING_CACHE_DIR, exist_ok=True)


def _footing_cache_key(data, geom, loads, soil, mat):
    payload = (
        data.length,
        data.width,
        data.thickness,
        data.cover,
        data.col_w,
        data.col_d,
        data.ecc_x,
        data.ecc_y,
        data.fc_prime,
        data.fy,
        data.soil_qa,
        data.soil_ks,
        data.soil_depth,
        data.soil_unit_weight,
        data.soil_friction_angle,
        data.surcharge_dl,
        data.surcharge_ll,
        data.pu_ult,
        data.mux_ult,
        data.muy_ult,
        data.pu_srv,
        data.mux_srv,
        data.muy_srv,
        data.bottom_bar_size,
        data.top_bar_size,
    )
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _footing_cache_path(key: str) -> str:
    return os.path.join(_FOOTING_CACHE_DIR, f"{key}.pkl")


def _load_footing_cache(key: str):
    path = _footing_cache_path(key)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def _save_footing_cache(key: str, value):
    path = _footing_cache_path(key)
    try:
        with open(path, "wb") as f:
            pickle.dump(value, f)
    except Exception:
        pass


# ----------------------------------------------------------------------
# 1. NATIVE AIR SCHEMA
# ----------------------------------------------------------------------
class FootingDesignModel(BaseModel):
    proj_name: str = AirField(default="Typical Isolated Footing")
    proj_loc: str = AirField(default="Manila, PH")
    proj_eng: str = AirField(default="Engr. Doe")
    proj_date: str = AirField(default="")

    # Footing dimensions
    length: float = AirField(default=2500.0)
    width: float = AirField(default=2000.0)
    thickness: float = AirField(default=450.0)
    cover: float = AirField(default=75.0)

    # Column
    col_w: float = AirField(default=400.0)
    col_d: float = AirField(default=400.0)
    ecc_x: float = AirField(default=0.0)
    ecc_y: float = AirField(default=0.0)

    # Materials
    fc_prime: float = AirField(default=28.0)
    fy: float = AirField(default=415.0)
    bottom_bar_size: str = AirField(default="D16")
    top_bar_size: str = AirField(default="D16")

    # Soil
    soil_qa: float = AirField(default=200.0)
    soil_ks: float = AirField(default=40000.0)
    soil_depth: float = AirField(default=0.0)
    soil_unit_weight: float = AirField(default=18.0)
    soil_friction_angle: float = AirField(default=30.0)
    surcharge_dl: float = AirField(default=0.0)
    surcharge_ll: float = AirField(default=0.0)

    # Loads
    pu_ult: float = AirField(default=1500.0)
    mux_ult: float = AirField(default=150.0)
    muy_ult: float = AirField(default=80.0)
    pu_srv: float = AirField(default=1050.0)
    mux_srv: float = AirField(default=105.0)
    muy_srv: float = AirField(default=55.0)

    # Options
    transient_loads: bool = AirField(default=False)


# ----------------------------------------------------------------------
# 2. UI RENDER HELPERS
# ----------------------------------------------------------------------
def render_footing_plan_css(geom: FootingGeometry):
    scale = 200 / max(geom.length, geom.width)
    dw, dh = geom.length * scale, geom.width * scale
    cw, cd = geom.column_width * scale, geom.column_depth * scale

    center_x, center_y = dw / 2, dh / 2
    cx = center_x + (geom.ecc_x * scale) - (cw / 2)
    cy = center_y - (geom.ecc_y * scale) - (cd / 2)

    return air.Div(
        air.Div(
            f"{geom.length} mm",
            style="text-align: center; font-weight: bold; color: #6b7280; margin-bottom: 4px;",
        ),
        air.Div(
            air.Div(
                f"{geom.width} mm",
                style="position: absolute; left: -75px; top: 50%; transform: translateY(-50%); font-weight: bold; color: #6b7280;",
            ),
            air.Div(
                air.Div(
                    style=f"position: absolute; left: {cx}px; top: {cy}px; width: {cw}px; height: {cd}px; background: #2563eb; border: 2px solid #111827; border-radius: 2px;"
                ),
                air.Div(
                    style="position: absolute; left: 0; top: 50%; width: 100%; height: 1px; background: rgba(0,0,0,0.1); border-top: 1px dashed #9ca3af;"
                ),
                air.Div(
                    style="position: absolute; left: 50%; top: 0; width: 1px; height: 100%; background: rgba(0,0,0,0.1); border-left: 1px dashed #9ca3af;"
                ),
                style=f"position: relative; width: {dw}px; height: {dh}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px;",
            ),
            style="position: relative; display: inline-block; margin-left: 60px;",
        ),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; background: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; width: 100%; box-sizing: border-box;",
    )


def render_contour_card(title, b64_img):
    return air.Div(
        air.H4(
            title,
            style="text-align: center; color: #4b5563; margin-bottom: 12px; font-size: 15px;",
        ),
        air.Img(
            src=f"data:image/png;base64,{b64_img}",
            style="width: 100%; border-radius: 8px; border: 1px solid #e5e7eb;",
        ),
        class_="section-box",
        style="padding: 12px;",
    )


CONTOUR_OPTIONS = [
    ("soil_pressure", "Soil Bearing Pressure"),
    ("settlement", "Settlement"),
    ("mxx", "Bending Mxx"),
    ("myy", "Bending Myy"),
    ("mxy", "Bending Mxy"),
    ("vx", "Shear Vx"),
    ("vy", "Shear Vy"),
    ("wa_mx", "Wood-Armer Mx"),
    ("wa_my", "Wood-Armer My"),
    ("as_bot", "Required As_bot"),
    ("as_top", "Required As_top"),
]


def render_contour_selector(contours):
    js = """
    function showContour(key) {
        document.querySelectorAll('.contour-card').forEach(el => el.style.display = 'none');
        const target = document.getElementById('contour-' + key);
        if (target) target.style.display = 'block';
    }
    """
    buttons = [
        air.Button(
            key_label,
            type="button",
            onclick=f"showContour('{key}')",
            class_="contour-btn",
            style="font-family: 'IBM Plex Mono', monospace; font-size: 13px; font-weight: 600; "
            "background: #f3f4f6; color: #374151; border: 2px solid #e5e7eb; border-radius: 8px; "
            "padding: 8px 14px; cursor: pointer; transition: all 0.15s;",
        )
        for key, key_label in CONTOUR_OPTIONS
        if key in contours
    ]

    cards = []
    for key, key_label in CONTOUR_OPTIONS:
        if key not in contours:
            continue
        display = "block" if key == "soil_pressure" else "none"
        cards.append(
            air.Div(
                render_contour_card(key_label, contours[key]),
                id=f"contour-{key}",
                class_="contour-card",
                style=f"display: {display};",
            )
        )

    return air.Div(
        air.Script(js),
        air.Div(
            *buttons,
            style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; justify-content: center;",
        ),
        *cards,
        style="width: 100%;",
    )


def render_progress_modal():
    modal_style = """
        display: none; position: fixed; z-index: 9999; left: 0; top: 0; width: 100%; height: 100%;
        background-color: rgba(17, 24, 39, 0.85); backdrop-filter: blur(4px);
        align-items: center; justify-content: center; flex-direction: column;
    """
    card_style = """
        background: #ffffff; padding: 40px; border-radius: 12px; width: 90%; max-width: 500px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        text-align: center;
    """
    js_script = """
        function showProgressModal() {
            document.getElementById('analysisProgressModal').style.display = 'flex';
            let bar = document.getElementById('progressBar');
            let text = document.getElementById('progressText');
            let pctText = document.getElementById('progressPct');
            let progress = 0;

            let interval = setInterval(() => {
                progress += 1;
                if(progress > 98) {
                    clearInterval(interval);
                    return;
                }

                bar.style.width = progress + '%';
                pctText.innerText = progress + '%';

                if(progress < 15) text.innerText = 'Constructing the OpenSees FEA model...';
                else if(progress < 45) text.innerText = 'Running service checks...';
                else if(progress < 75) text.innerText = 'Designing footing reinforcements...';
                else if(progress < 90) text.innerText = 'Calculating material quantities...';
                else text.innerText = 'Finalizing results...';
            }, 100);
        }
    """
    return air.Div(
        air.Script(js_script),
        air.Div(
            air.H2("Analyzing Footing", style="margin-bottom: 8px; color: #111827;"),
            air.P(
                "Depending on your computer specs, this may take about 2 to 10 seconds. Please wait.",
                style="color: #6b7280; margin-bottom: 24px; font-size: 14px;",
            ),
            air.Div(
                air.Div(
                    id="progressBar",
                    style="width: 0%; height: 100%; background-color: #db2777; border-radius: 8px; transition: width 0.1s linear;",
                ),
                style="width: 100%; height: 12px; background-color: #e5e7eb; border-radius: 8px; margin-bottom: 16px; overflow: hidden;",
            ),
            air.Div(
                air.Span(id="progressText", style="font-weight: 600; color: #2563eb;"),
                air.Span(id="progressPct", style="font-weight: bold; color: #111827;"),
                style="display: flex; justify-content: space-between; font-size: 14px;",
            ),
            style=card_style,
        ),
        id="analysisProgressModal",
        style=modal_style,
    )


def _bar_options(selected):
    return [
        air.Option(db, value=db, selected=db == selected)
        for db in ["D10", "D12", "D16", "D20", "D25", "D28", "D32", "D36"]
    ]


BAR_SELECT_STYLE = "font-family: 'IBM Plex Mono', monospace; font-size: 15px; padding: 10px 14px; border: 2px solid #e5e7eb; border-radius: 12px; width: 100%;"


# ----------------------------------------------------------------------
# 3. MODULE ROUTES
# ----------------------------------------------------------------------
def setup_footing_routes(app):
    @app.get("/footing")
    def footing_index(request: air.Request):
        data = (
            FootingDesignModel(
                **json.loads(request.cookies.get("footing_inputs", "{}"))
            )
            if request.cookies.get("footing_inputs")
            else FootingDesignModel()
        )
        if not data.proj_date:
            data.proj_date = date.today().strftime("%Y-%m-%d")
        csrf_token = getattr(
            request.state, "csrf_token", request.cookies.get("csrftoken", "dev_token")
        )

        return blueprint_layout(
            render_progress_modal(),
            air.Header(
                air.A("← Dashboard", href="/", class_="back-link no-print"),
                air.H1("RC Isolated Footing Designer"),
                air.P("in accordance with ACI 318M-25", class_="subtitle"),
                class_="module-header",
            ),
            air.Main(
                air.Form(
                    air.Input(type="hidden", name="csrf_token", value=csrf_token),
                    # ── Card 1: Project Information ──
                    air.Div(
                        air.H2("Project Information"),
                        air.Div(
                            air.Div(
                                air.Label("Project Name"),
                                air.Input(
                                    type="text",
                                    name="proj_name",
                                    value=data.proj_name,
                                    required=True,
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Location"),
                                air.Input(
                                    type="text",
                                    name="proj_loc",
                                    value=data.proj_loc,
                                    required=True,
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Structural Engineer"),
                                air.Input(
                                    type="text",
                                    name="proj_eng",
                                    value=data.proj_eng,
                                    required=True,
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Date"),
                                air.Input(
                                    type="date",
                                    name="proj_date",
                                    value=data.proj_date,
                                    required=True,
                                ),
                                class_="form-group",
                            ),
                            class_="grid-2",
                        ),
                        class_="card",
                    ),
                    # ── Card 2: Footing Dimensions ──
                    air.Div(
                        air.H2("Footing Dimensions"),
                        air.Div(
                            air.Div(
                                air.Label("Dimension along x (mm)"),
                                air.Input(
                                    type="number", name="length", value=str(data.length)
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Dimension along y (mm)"),
                                air.Input(
                                    type="number", name="width", value=str(data.width)
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Thickness (mm)"),
                                air.Input(
                                    type="number",
                                    name="thickness",
                                    value=str(data.thickness),
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Clear cover (mm)"),
                                air.Input(
                                    type="number", name="cover", value=str(data.cover)
                                ),
                                class_="form-group",
                            ),
                            class_="grid-2",
                        ),
                        class_="card",
                    ),
                    # ── Card 3: Column Geometry ──
                    air.Div(
                        air.H2("Column Geometry"),
                        air.Div(
                            air.Div(
                                air.Label("Dimension along x (mm)"),
                                air.Input(
                                    type="number", name="col_w", value=str(data.col_w)
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Dimension along y (mm)"),
                                air.Input(
                                    type="number", name="col_d", value=str(data.col_d)
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Eccentricity along x (mm)"),
                                air.Input(
                                    type="number", name="ecc_x", value=str(data.ecc_x)
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Eccentricity along y (mm)"),
                                air.Input(
                                    type="number", name="ecc_y", value=str(data.ecc_y)
                                ),
                                class_="form-group",
                            ),
                            class_="grid-2",
                        ),
                        class_="card",
                    ),
                    # ── Card 4: Concrete & Reinforcement ──
                    air.Div(
                        air.H2("Concrete & Reinforcement"),
                        air.Div(
                            air.Div(
                                air.Label("Concrete strength (MPa)"),
                                air.Input(
                                    type="number",
                                    name="fc_prime",
                                    value=str(data.fc_prime),
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Rebar yield strength (MPa)"),
                                air.Input(type="number", name="fy", value=str(data.fy)),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Bottom bar diameter"),
                                air.Select(
                                    *_bar_options(data.bottom_bar_size),
                                    name="bottom_bar_size",
                                    style=BAR_SELECT_STYLE,
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Top bar diameter"),
                                air.Select(
                                    *_bar_options(data.top_bar_size),
                                    name="top_bar_size",
                                    style=BAR_SELECT_STYLE,
                                ),
                                class_="form-group",
                            ),
                            class_="grid-2",
                        ),
                        class_="card",
                    ),
                    # ── Card 5: Soil Properties ──
                    air.Div(
                        air.H2("Soil Properties"),
                        air.Div(
                            air.Div(
                                air.Label("Allowable soil bearing capacity (kPa)"),
                                air.Input(
                                    type="number",
                                    name="soil_qa",
                                    value=str(data.soil_qa),
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Subgrade modulus (kN/m^3)"),
                                air.Input(
                                    type="number",
                                    name="soil_ks",
                                    value=str(data.soil_ks),
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Depth of soil above footing (mm)"),
                                air.Input(
                                    type="number",
                                    name="soil_depth",
                                    value=str(data.soil_depth),
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Soil unit weight (kN/m^3)"),
                                air.Input(
                                    type="number",
                                    name="soil_unit_weight",
                                    value=str(data.soil_unit_weight),
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Soil friction angle (degrees)"),
                                air.Input(
                                    type="number",
                                    name="soil_friction_angle",
                                    value=str(data.soil_friction_angle),
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Dead load surcharge (kPa)"),
                                air.Input(
                                    type="number",
                                    name="surcharge_dl",
                                    value=str(data.surcharge_dl),
                                    step="any",
                                ),
                                class_="form-group",
                            ),
                            air.Div(
                                air.Label("Live load surcharge (kPa)"),
                                air.Input(
                                    type="number",
                                    name="surcharge_ll",
                                    value=str(data.surcharge_ll),
                                    step="any",
                                ),
                                class_="form-group",
                            ),
                            class_="grid-2",
                        ),
                        class_="card",
                    ),
                    # ── Card 6: Loads ──
                    air.Div(
                        air.H2("Loads"),
                        air.Div(
                            air.Div(
                                air.H3("Factored Strength Loads"),
                                air.Div(
                                    air.Label("Axial Pu (kN)"),
                                    air.Input(
                                        type="number",
                                        name="pu_ult",
                                        value=str(data.pu_ult),
                                    ),
                                    class_="form-group",
                                ),
                                air.Div(
                                    air.Label("Moment Mux (kN-m)"),
                                    air.Input(
                                        type="number",
                                        name="mux_ult",
                                        value=str(data.mux_ult),
                                    ),
                                    class_="form-group",
                                ),
                                air.Div(
                                    air.Label("Moment Muy (kN-m)"),
                                    air.Input(
                                        type="number",
                                        name="muy_ult",
                                        value=str(data.muy_ult),
                                    ),
                                    class_="form-group",
                                ),
                                class_="section-box",
                            ),
                            air.Div(
                                air.H3("Service Loads"),
                                air.Div(
                                    air.Label("Axial Ps (kN)"),
                                    air.Input(
                                        type="number",
                                        name="pu_srv",
                                        value=str(data.pu_srv),
                                    ),
                                    class_="form-group",
                                ),
                                air.Div(
                                    air.Label("Moment Msx (kN-m)"),
                                    air.Input(
                                        type="number",
                                        name="mux_srv",
                                        value=str(data.mux_srv),
                                    ),
                                    class_="form-group",
                                ),
                                air.Div(
                                    air.Label("Msy (kN-m)"),
                                    air.Input(
                                        type="number",
                                        name="muy_srv",
                                        value=str(data.muy_srv),
                                    ),
                                    class_="form-group",
                                ),
                                class_="section-box",
                            ),
                            class_="grid-2",
                        ),
                        air.Div(
                            air.Div(
                                air.Input(
                                    type="checkbox",
                                    name="transient_loads",
                                    value="1",
                                    checked=data.transient_loads,
                                    style="width: auto; margin-right: 8px;",
                                ),
                                air.Span(
                                    "Increase allowable bearing by 33% (wind/seismic governs)?",
                                    style="font-size: 14px; color: var(--text-muted);",
                                ),
                                style="display: flex; align-items: center;",
                            ),
                            style="margin-top: 16px; padding: 12px 16px; background: #eff6ff; border-radius: 8px; border: 1px solid #bfdbfe;",
                        ),
                        air.Button(
                            "Analyze Footing",
                            type="submit",
                            style="width: 100%; font-size: 18px; margin-top: 24px;",
                        ),
                        class_="card",
                    ),
                    method="post",
                    action="/footing/design",
                    onsubmit="showProgressModal()",
                )
            ),
        )

    @app.post("/footing/design")
    async def footing_design(request: air.Request):
        form_data = await request.form()
        try:
            data = FootingDesignModel(**form_data)
        except Exception as e:
            return AirResponse(
                content=str(
                    blueprint_layout(
                        air.Main(
                            air.Div(
                                air.H2("Validation Failed"),
                                air.P(str(e)),
                                class_="card",
                            )
                        )
                    )
                ),
                media_type="text/html",
            )

        try:
            form_dict = dict(form_data)
            is_transient = form_dict.get("transient_loads", "0") in ("1", "on", "true")

            engine = ACI318M25FootingDesign()
            mat = MaterialProperties(
                fc_prime=data.fc_prime,
                fy=data.fy,
                fu=data.fy * 1.25,
                fyt=data.fy,
                fut=data.fy * 1.25,
                es=200000.0,
                ec=base_aci_lib.aci.get_concrete_modulus(data.fc_prime),
                gamma_c=24.0,
                description="",
            )

            # Validate column placement
            col_left = data.ecc_x - data.col_w / 2
            col_right = data.ecc_x + data.col_w / 2
            col_front = data.ecc_y - data.col_d / 2
            col_back = data.ecc_y + data.col_d / 2
            footing_left = -data.length / 2
            footing_right = data.length / 2
            footing_front = -data.width / 2
            footing_back = data.width / 2

            if (
                col_left < footing_left
                or col_right > footing_right
                or col_front < footing_front
                or col_back > footing_back
            ):
                modal_js = """
                document.addEventListener('DOMContentLoaded', function() {
                    document.getElementById('errorModal').style.display = 'flex';
                });
                """
                return AirResponse(
                    content=str(
                        blueprint_layout(
                            air.Script(modal_js),
                            air.Div(
                                air.Div(
                                    air.H2(
                                        "Invalid Column Placement",
                                        style="margin-bottom: 8px; color: #DC2626;",
                                    ),
                                    air.P(
                                        "The column extends beyond the footing boundary.",
                                        style="color: #6b7280; margin-bottom: 16px;",
                                    ),
                                    air.Div(
                                        air.Ul(
                                            air.Li(
                                                air.Strong("Footing bounds along x:"),
                                                air.Span(
                                                    f"{footing_left:.0f} to {footing_right:.0f} mm",
                                                    class_="data-value",
                                                ),
                                            ),
                                            air.Li(
                                                air.Strong("Column bounds along x:"),
                                                air.Span(
                                                    f"{col_left:.0f} to {col_right:.0f} mm",
                                                    class_="data-value",
                                                ),
                                            ),
                                            air.Li(
                                                air.Strong("Footing bounds along y:"),
                                                air.Span(
                                                    f"{footing_front:.0f} to {footing_back:.0f} mm",
                                                    class_="data-value",
                                                ),
                                            ),
                                            air.Li(
                                                air.Strong("Column bounds along y:"),
                                                air.Span(
                                                    f"{col_front:.0f} to {col_back:.0f} mm",
                                                    class_="data-value",
                                                ),
                                            ),
                                        ),
                                        style="text-align: left; margin-bottom: 24px;",
                                    ),
                                    air.A(
                                        "← Go Back",
                                        href="/footing",
                                        class_="button",
                                        style="background-color: #DC2626;",
                                    ),
                                    style="background: #ffffff; padding: 40px; border-radius: 12px; width: 90%; max-width: 500px; "
                                    "box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); text-align: center;",
                                ),
                                id="errorModal",
                                style="display: none; position: fixed; z-index: 9999; left: 0; top: 0; width: 100%; height: 100%; "
                                "background-color: rgba(17, 24, 39, 0.85); backdrop-filter: blur(4px); "
                                "align-items: center; justify-content: center; flex-direction: column;",
                            ),
                            air.Main(
                                air.Div(
                                    air.H2(
                                        "Invalid Column Placement",
                                        style="color: #DC2626;",
                                    ),
                                    air.P(
                                        "The column extends beyond the footing boundary. Adjust the eccentricity or footing dimensions."
                                    ),
                                    air.A(
                                        "← Go Back",
                                        href="/footing",
                                        class_="button secondary",
                                    ),
                                    class_="card",
                                )
                            ),
                        )
                    ),
                    media_type="text/html",
                )

            geom = FootingGeometry(
                data.length,
                data.width,
                data.thickness,
                data.cover,
                data.col_w,
                data.col_d,
                FootingType.ISOLATED,
                data.ecc_x,
                data.ecc_y,
                data.soil_ks,
            )
            soil = SoilProperties(
                data.soil_qa,
                data.soil_unit_weight,
                data.soil_depth,
                data.soil_friction_angle,
            )
            loads = FootingLoads(
                data.pu_ult,
                data.mux_ult,
                data.muy_ult,
                0,
                0,
                data.pu_srv,
                data.mux_srv,
                data.muy_srv,
                data.surcharge_dl,
                data.surcharge_ll,
            )

            cache_key = None
            cached_res = None
            try:
                cache_key = _footing_cache_key(data, geom, loads, soil, mat) + (
                    "_t" if is_transient else "_n"
                )
                cached_res = _load_footing_cache(cache_key)
            except Exception:
                cached_res = None

            if cached_res is not None:
                res = cached_res
            else:
                res = engine.perform_complete_design(
                    geom,
                    loads,
                    soil,
                    mat,
                    is_transient=is_transient,
                    preferred_bottom_bar=data.bottom_bar_size,
                    preferred_top_bar=data.top_bar_size,
                )
                if cache_key:
                    _save_footing_cache(cache_key, res)
            qto = engine.calculate_qto(geom, res)

            notes_elements = (
                [
                    air.Ul(
                        *[
                            air.Li(
                                f"{'⚠️' if any(x in n for x in ['Violation', 'CRITICAL', 'inadequate', 'exceeded']) else 'ℹ️'} {n}"
                            )
                            for n in list(dict.fromkeys(res.design_notes))
                        ],
                        class_="notes-list",
                    )
                ]
                if res.design_notes
                else []
            )

            reinf_str_x = f"{res.reinforcement.bottom_bars_x} @ {res.reinforcement.bottom_spacing_x:.0f} mm"
            reinf_str_y = f"{res.reinforcement.bottom_bars_y} @ {res.reinforcement.bottom_spacing_y:.0f} mm"
            reinf_str_tx = f"{res.reinforcement.top_bars_x} @ {res.reinforcement.top_spacing_x:.0f} mm"
            reinf_str_ty = f"{res.reinforcement.top_bars_y} @ {res.reinforcement.top_spacing_y:.0f} mm"

            # Computed values for calculations display
            net_qa = (
                soil.bearing_capacity
                - soil.unit_weight * (soil.soil_depth / 1000.0)
                - (loads.surcharge_dl + loads.surcharge_ll)
            )
            M_x_pos = res.fea_moment_x
            M_y_pos = res.fea_moment_y
            M_x_neg = 0.0 if not res.reinforcement.top_bars_x else M_x_pos * 0.3
            M_y_neg = 0.0 if not res.reinforcement.top_bars_y else M_y_pos * 0.3
            L_m = geom.length / 1000.0
            B_m = geom.width / 1000.0
            W_footing = 24.0 * L_m * B_m * (geom.thickness / 1000.0)
            W_soil = (
                soil.unit_weight * L_m * B_m * (soil.soil_depth / 1000.0)
                if soil.soil_depth > 0
                else 0.0
            )
            W_surcharge = (loads.surcharge_dl + loads.surcharge_ll) * L_m * B_m
            P_total = loads.service_axial + W_footing + W_soil + W_surcharge
            ot_limit = 1.5 if is_transient else 2.0
            d_eff_calc = geom.thickness - geom.cover - 20

            report_content = air.Main(
                air.Div(
                    air.Div(
                        air.Button(
                            "Print Summary",
                            onclick="window.print()",
                            style="background-color: var(--accent); color: var(--bg-deep); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 600;",
                        ),
                        air.A(
                            "Download PDF",
                            href="/footing/pdf",
                            target="_blank",
                            style="background-color: #4F46E5; color: white; text-decoration: none; padding: 8px 16px; border-radius: 4px; font-weight: 600;",
                        ),
                        style="display: flex; justify-content: flex-end; align-items: center; gap: 8px;",
                    ),
                    style="margin-bottom: 24px;",
                    class_="no-print",
                ),
                # ── Input Summary ──
                air.Div(
                    air.H2("Input Parameters"),
                    air.Div(
                        air.Div(
                            air.H3(
                                "Project",
                                style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;",
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Project Name"),
                                    air.Span(data.proj_name, class_="data-value"),
                                ),
                                air.Li(
                                    air.Strong("Location"),
                                    air.Span(data.proj_loc, class_="data-value"),
                                ),
                                air.Li(
                                    air.Strong("Structural Engineer"),
                                    air.Span(data.proj_eng, class_="data-value"),
                                ),
                                air.Li(
                                    air.Strong("Date"),
                                    air.Span(data.proj_date, class_="data-value"),
                                ),
                            ),
                            class_="section-box",
                        ),
                        air.Div(
                            air.H3(
                                "Footing & Column",
                                style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;",
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Footing"),
                                    air.Span(
                                        f"{data.length} mm × {data.width} mm × {data.thickness} mm",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Column"),
                                    air.Span(
                                        f"{data.col_w} mm × {data.col_d} mm",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Footing clear cover"),
                                    air.Span(f"{data.cover} mm", class_="data-value"),
                                ),
                                air.Li(
                                    air.Strong("Column eccentricity"),
                                    air.Span(
                                        f"ex = {data.ecc_x} mm, ey = {data.ecc_y} mm",
                                        class_="data-value",
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        class_="grid-2",
                    ),
                    air.Div(
                        air.Div(
                            air.H3(
                                "Materials",
                                style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;",
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Concrete"),
                                    air.Span(
                                        f"f'c = {data.fc_prime} MPa",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Rebar"),
                                    air.Span(
                                        f"fy = {data.fy} MPa", class_="data-value"
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Bottom bars"),
                                    air.Span(data.bottom_bar_size, class_="data-value"),
                                ),
                                air.Li(
                                    air.Strong("Top bars"),
                                    air.Span(data.top_bar_size, class_="data-value"),
                                ),
                            ),
                            class_="section-box",
                        ),
                        air.Div(
                            air.H3(
                                "Soil",
                                style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;",
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("SBC"),
                                    air.Span(
                                        f"{data.soil_qa} kPa", class_="data-value"
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Subgrade modulus"),
                                    air.Span(
                                        f"{data.soil_ks} kN/m^3", class_="data-value"
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Unit weight"),
                                    air.Span(
                                        f"D = {data.soil_depth} mm, γ = {data.soil_unit_weight} kN/m^3",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Friction angle"),
                                    air.Span(
                                        f"{data.soil_friction_angle}°",
                                        class_="data-value",
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        class_="grid-2",
                    ),
                    air.Div(
                        air.Div(
                            air.H3(
                                "Factored Loads",
                                style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;",
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Pu"),
                                    air.Span(f"{data.pu_ult} kN", class_="data-value"),
                                ),
                                air.Li(
                                    air.Strong("Mux / Muy"),
                                    air.Span(
                                        f"{data.mux_ult} / {data.muy_ult} kN-m",
                                        class_="data-value",
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        air.Div(
                            air.H3(
                                "Service Loads",
                                style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;",
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Ps"),
                                    air.Span(f"{data.pu_srv} kN", class_="data-value"),
                                ),
                                air.Li(
                                    air.Strong("Msx / Msy"),
                                    air.Span(
                                        f"{data.mux_srv} / {data.muy_srv} kN-m",
                                        class_="data-value",
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        class_="grid-2",
                    ),
                    class_="card",
                ),
                # ── Design Results ──
                air.Div(
                    air.H2("Design Results"),
                    air.Div(
                        air.Div(
                            render_footing_plan_css(geom),
                            air.H4("Stability Checks", style="margin-top: 16px;"),
                            air.Ul(
                                air.Li(
                                    air.Strong("Maximum soil bearing pressure"),
                                    _status_badge(
                                        f"{res.bearing_pressure_max:.1f} kPa {'≤' if res.bearing_pressure_max <= res.bearing_limit_used else '>'} {res.bearing_limit_used:.1f} kPa ({'Pass' if res.bearing_pressure_max <= res.bearing_limit_used else 'Fail'})",
                                        res.bearing_pressure_max
                                        <= res.bearing_limit_used,
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Minimum soil bearing pressure"),
                                    air.Span(
                                        f"{res.bearing_pressure_min:.1f} kPa",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("FS overturning about x"),
                                    _status_badge(
                                        f"{res.fs_overturning_x:.2f} {'≥' if res.fs_overturning_x >= 2.0 else '<'} 2.00 ({'Pass' if res.fs_overturning_x >= 2.0 else 'Fail'})",
                                        res.fs_overturning_x >= 2.0,
                                    ),
                                ),
                                air.Li(
                                    air.Strong("FS overturning about y"),
                                    _status_badge(
                                        f"{res.fs_overturning_y:.2f} {'≥' if res.fs_overturning_y >= 2.0 else '<'} 2.00 ({'Pass' if res.fs_overturning_y >= 2.0 else 'Fail'})",
                                        res.fs_overturning_y >= 2.0,
                                    ),
                                ),
                            ),
                            air.H4("Shear Checks", style="margin-top: 16px;"),
                            air.Ul(
                                air.Li(
                                    air.Strong("One-way shear"),
                                    _status_badge(
                                        f"{res.one_way_shear_demand:.1f} kN/m ÷ {res.one_way_shear_capacity:.1f} kN/m = {res.one_way_shear_demand / res.one_way_shear_capacity if res.one_way_shear_capacity > 0 else 99.9:.2f} ({'Pass' if res.one_way_shear_ok else 'Fail'})",
                                        res.one_way_shear_ok,
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Two-way shear"),
                                    _status_badge(
                                        f"{res.two_way_shear_demand:.1f} kN ÷ {res.two_way_shear_capacity:.1f} kN = {res.two_way_shear_demand / res.two_way_shear_capacity if res.two_way_shear_capacity > 0 else 99.9:.2f} ({'Pass' if res.two_way_shear_ok else 'Fail'})",
                                        res.two_way_shear_ok,
                                    ),
                                ),
                            ),
                            air.H4("Reinforcement Details", style="margin-top: 16px;"),
                            air.Ul(
                                air.Li(
                                    air.Strong("Bottom bars along x"),
                                    air.Span(
                                        reinf_str_x,
                                        class_="data-value",
                                        style="color: #2563eb; font-weight: bold;",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Bottom bars along y"),
                                    air.Span(
                                        reinf_str_y,
                                        class_="data-value",
                                        style="color: #db2777; font-weight: bold;",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Top bars along x"),
                                    air.Span(
                                        reinf_str_tx,
                                        class_="data-value",
                                        style="color: #2563eb; font-weight: bold;",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Top bars along y"),
                                    air.Span(
                                        reinf_str_ty,
                                        class_="data-value",
                                        style="color: #db2777; font-weight: bold;",
                                    ),
                                ),
                            ),
                            style="height: 100%; display: flex; flex-direction: column; justify-content: flex-start;",
                        ),
                        air.Div(
                            render_contour_selector(res.contours),
                        ),
                        class_="grid-2",
                    ),
                    air.Div(
                        air.H4(
                            "Design Notes", style="margin-top: 20px; color: #92400e;"
                        ),
                        *notes_elements,
                        style="padding: 16px; background: #fffbeb; border-radius: 8px; border: 1px solid #fde68a; margin-top: 20px;",
                    ),
                    class_="card",
                ),
                # ── Detailed Calculations (with toggle and KaTeX) ──
                air.Div(
                    air.Button(
                        "Show Calculations",
                        type="button",
                        id="toggleCalcsBtn",
                        onclick="toggleCalcs()",
                        style="width: 100%; font-size: 16px; background: #1e40af; color: white; padding: 12px; border-radius: 8px; cursor: pointer; border: none;",
                    ),
                ),
                air.Div(
                    air.Div(
                        air.Div(
                            air.H3("Soil Bearing Pressure Check"),
                            air.Raw(
                                f"$$q_{{a,net}} = q_a - \\gamma_{{soil}} \\cdot D = {soil.bearing_capacity:.0f} - {soil.unit_weight:.1f} \\times {soil.soil_depth / 1000:.3f} = {net_qa:.1f} \\text{{ kPa}}$$"
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Maximum pressure (FEA)"),
                                    air.Span(
                                        f"q_max = {res.bearing_pressure_max:.1f} kPa",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Minimum pressure (FEA)"),
                                    air.Span(
                                        f"q_min = {res.bearing_pressure_min:.1f} kPa",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Check"),
                                    _status_badge(
                                        f"{res.bearing_pressure_max:.1f} kPa {'≤' if res.bearing_pressure_max <= res.bearing_limit_used else '>'} {res.bearing_limit_used:.1f} kPa ({'Pass' if res.bearing_ok else 'Fail'})",
                                        res.bearing_ok,
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        air.Div(
                            air.H3("Flexural Design — Bottom Reinforcement"),
                            air.Raw(
                                f"$$A_s = \\frac{{-B - \\sqrt{{B^2 - 4AC}}}}{{2A}}, \\quad A = \\frac{{\\phi f_y^2}}{{1.7 f'_c}}, \\quad B = -\\phi f_y d, \\quad C = M_u \\times 10^6$$"
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("M_x (positive)"),
                                    air.Span(
                                        f"{M_x_pos:.2f} kN-m/m", class_="data-value"
                                    ),
                                ),
                                air.Li(
                                    air.Strong("M_y (positive)"),
                                    air.Span(
                                        f"{M_y_pos:.2f} kN-m/m", class_="data-value"
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Effective depth"),
                                    air.Span(
                                        f"d = {d_eff_calc:.0f} mm", class_="data-value"
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Minimum reinforcement"),
                                    air.Span(
                                        f"A_s,min = {0.0018 * 1000 * geom.thickness:.0f} mm²/m",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("X-direction"),
                                    air.Span(
                                        reinf_str_x,
                                        class_="data-value",
                                        style="color: #2563eb; font-weight: bold;",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Y-direction"),
                                    air.Span(
                                        reinf_str_y,
                                        class_="data-value",
                                        style="color: #db2777; font-weight: bold;",
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        class_="grid-2",
                    ),
                    air.Div(
                        air.Div(
                            air.H3("Flexural Design — Top Reinforcement"),
                            air.Ul(
                                air.Li(
                                    air.Strong("M_x (negative)"),
                                    air.Span(
                                        f"{M_x_neg:.2f} kN-m/m", class_="data-value"
                                    ),
                                ),
                                air.Li(
                                    air.Strong("M_y (negative)"),
                                    air.Span(
                                        f"{M_y_neg:.2f} kN-m/m", class_="data-value"
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Effective depth (top)"),
                                    air.Span(
                                        f"d_top = {geom.thickness - geom.cover - 40:.0f} mm",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("X-direction"),
                                    air.Span(
                                        reinf_str_tx if reinf_str_tx else "None",
                                        class_="data-value",
                                        style=f"color: {'#2563eb' if reinf_str_tx else '#9ca3af'}; font-weight: bold;",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Y-direction"),
                                    air.Span(
                                        reinf_str_ty if reinf_str_ty else "None",
                                        class_="data-value",
                                        style=f"color: {'#db2777' if reinf_str_ty else '#9ca3af'}; font-weight: bold;",
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        air.Div(
                            air.H3("One-Way Shear Check"),
                            air.Raw(
                                f"$$\\phi V_c = \\phi \\cdot 0.17 \\sqrt{{f'_c}} \\cdot b \\cdot d = 0.75 \\times 0.17 \\times \\sqrt{{{mat.fc_prime}}} \\times 1000 \\times {d_eff_calc} / 1000 = {res.one_way_shear_capacity:.1f} \\text{{ kN/m}}$$"
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Shear demand"),
                                    air.Span(
                                        f"V_u = {res.one_way_shear_demand:.1f} kN/m",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Shear capacity"),
                                    air.Span(
                                        f"φV_c = {res.one_way_shear_capacity:.1f} kN/m",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Check"),
                                    _status_badge(
                                        f"{res.one_way_shear_demand:.1f} kN/m ÷ {res.one_way_shear_capacity:.1f} kN/m = {res.one_way_shear_demand / res.one_way_shear_capacity if res.one_way_shear_capacity > 0 else 99.9:.2f} ({'Pass' if res.one_way_shear_ok else 'Fail'})",
                                        res.one_way_shear_ok,
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        class_="grid-2",
                    ),
                    air.Div(
                        air.Div(
                            air.H3("Two-Way (Punching) Shear Check"),
                            air.Raw(
                                f"$$b_o = 2(c_1 + d) + 2(c_2 + d) = 2({geom.column_width} + {d_eff_calc:.0f}) + 2({geom.column_depth} + {d_eff_calc:.0f}) = {2 * (geom.column_width + d_eff_calc) + 2 * (geom.column_depth + d_eff_calc):.0f} \\text{{ mm}}$$"
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Shear demand"),
                                    air.Span(
                                        f"V_u = {res.two_way_shear_demand:.1f} kN",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Shear capacity"),
                                    air.Span(
                                        f"φV_n = {res.two_way_shear_capacity:.1f} kN",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("Check"),
                                    _status_badge(
                                        f"{res.two_way_shear_demand:.1f} kN ÷ {res.two_way_shear_capacity:.1f} kN = {res.two_way_shear_demand / res.two_way_shear_capacity if res.two_way_shear_capacity > 0 else 99.9:.2f} ({'Pass' if res.two_way_shear_ok else 'Fail'})",
                                        res.two_way_shear_ok,
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        air.Div(
                            air.H3("Overturning Stability Check"),
                            air.Raw(
                                f"$$FS_x = \\frac{{M_{{R,x}}}}{{M_{{O,x}}}} = \\frac{{{P_total * B_m / 2:.1f}}}{{{abs(loads.service_moment_x) + abs(loads.shear_x) * geom.thickness / 1000:.1f}}} = {res.fs_overturning_x:.2f}$$"
                            ),
                            air.Ul(
                                air.Li(
                                    air.Strong("Total vertical load"),
                                    air.Span(
                                        f"P_total = {P_total:.1f} kN",
                                        class_="data-value",
                                    ),
                                ),
                                air.Li(
                                    air.Strong("FS overturning (x-axis)"),
                                    _status_badge(
                                        f"{res.fs_overturning_x:.2f} {'≥' if res.fs_overturning_x >= ot_limit else '<'} {ot_limit:.2f} ({'Pass' if res.fs_overturning_x >= ot_limit else 'Fail'})",
                                        res.fs_overturning_x >= ot_limit,
                                    ),
                                ),
                                air.Li(
                                    air.Strong("FS overturning (y-axis)"),
                                    _status_badge(
                                        f"{res.fs_overturning_y:.2f} {'≥' if res.fs_overturning_y >= ot_limit else '<'} {ot_limit:.2f} ({'Pass' if res.fs_overturning_y >= ot_limit else 'Fail'})",
                                        res.fs_overturning_y >= ot_limit,
                                    ),
                                ),
                            ),
                            class_="section-box",
                        ),
                        class_="grid-2",
                    ),
                    id="detailedCalcs",
                    style="display: none; margin-top: 16px;",
                    class_="card",
                ),
                # ── Material Takeoff (cards) ──
                air.Div(
                    air.H2("Material Takeoff"),
                    air.Div(
                        air.Div(
                            air.Div("CONCRETE", class_="metric-label"),
                            air.Div(f"{qto['volume']:.2f} m³", class_="metric-value"),
                            class_="metric-card concrete",
                        ),
                        air.Div(
                            air.Div("FORMWORK", class_="metric-label"),
                            air.Div(f"{qto['formwork']:.2f} m²", class_="metric-value"),
                            class_="metric-card formwork",
                        ),
                        air.Div(
                            air.Div("REBAR WEIGHT", class_="metric-label"),
                            air.Div(f"{qto['weight']:.1f} kg", class_="metric-value"),
                            class_="metric-card rebar",
                        ),
                        class_="grid-3",
                    ),
                    class_="card",
                ),
                # ── Cutting List (simplified headers) ──
                air.Div(
                    air.H2("Reinforcement Cutting List"),
                    air.Table(
                        air.Thead(
                            air.Tr(
                                air.Th("Location"),
                                air.Th("Size"),
                                air.Th("Qty"),
                                air.Th("Cut Length"),
                                air.Th("Order"),
                                air.Th("Weight"),
                            )
                        ),
                        air.Tbody(
                            *[
                                air.Tr(
                                    air.Td(it["label"]),
                                    air.Td(it["bar"]),
                                    air.Td(str(it["qty"])),
                                    air.Td(f"{it.get('each_len_m', 0):.2f}m"),
                                    air.Td(
                                        f"{it.get('com_bars', 0)} x {it.get('commercial_len_m', 0):.1f}m"
                                    ),
                                    air.Td(f"{it.get('weight_kg', 0):.1f} kg"),
                                )
                                for it in qto.get("cutting_list", [])
                            ]
                        ),
                        style="width: 100%; border-collapse: collapse; font-size: 14px;",
                    ),
                    class_="card",
                )
                if qto.get("cutting_list")
                else air.Div(),
            )

            katex_head = [
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">',
                '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>',
                '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>',
                """<script>
function toggleCalcs() {
    var el = document.getElementById('detailedCalcs');
    var btn = document.getElementById('toggleCalcsBtn');
    if (el.style.display === 'none') {
        el.style.display = 'block';
        btn.textContent = 'Hide Calculations';
        if (typeof renderMathInElement === 'function' && !el.dataset.katexRendered) {
            renderMathInElement(el, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false}
                ],
                throwOnError: false
            });
            el.dataset.katexRendered = 'true';
        }
    } else {
        el.style.display = 'none';
        btn.textContent = 'Show Calculations';
    }
}
</script>""",
            ]

            resp = AirResponse(
                content=str(
                    blueprint_layout(
                        air.Header(
                            air.A(
                                "← Edit Inputs",
                                href="/footing",
                                class_="back-link no-print",
                            ),
                            air.H1("RC Isolated Footing Designer"),
                            air.P("in accordance with ACI 318M-25", class_="subtitle"),
                            class_="module-header",
                        ),
                        report_content,
                        head_extra=katex_head,
                    )
                ),
                media_type="text/html",
            )
            resp.set_cookie(
                "footing_inputs", json.dumps(dict(form_data)), max_age=2592000
            )
            return resp

        except Exception as e:
            return AirResponse(
                content=str(
                    blueprint_layout(
                        air.Main(
                            air.Div(
                                air.H2("Analysis Error", style="color: #DC2626;"),
                                air.P(str(e)),
                                class_="card",
                            )
                        )
                    )
                ),
                media_type="text/html",
            )
