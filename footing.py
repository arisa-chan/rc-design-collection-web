import air
from air import AirField, AirResponse
from pydantic import BaseModel
import json
from datetime import date

from aci318m25 import MaterialProperties
from aci318m25_complete import ACI318M25MemberLibrary
from aci318m25_footing import ACI318M25FootingDesign, FootingGeometry, FootingLoads, SoilProperties, FootingType
from shared import expressive_layout

base_aci_lib = ACI318M25MemberLibrary()


# ----------------------------------------------------------------------
# 1. NATIVE AIR SCHEMA
# ----------------------------------------------------------------------
class FootingDesignModel(BaseModel):
    proj_name: str = AirField(default="Typical Isolated Footing")
    proj_loc: str = AirField(default="Manila, PH")
    proj_eng: str = AirField(default="Engr. Doe")
    proj_date: str = AirField(default="")

    # Geometry
    length: float = AirField(default=2500.0)
    width: float = AirField(default=2000.0)
    thickness: float = AirField(default=450.0)
    col_w: float = AirField(default=400.0)
    col_d: float = AirField(default=400.0)
    ecc_x: float = AirField(default=0.0)
    ecc_y: float = AirField(default=0.0)

    # Material
    fc_prime: float = AirField(default=28.0)
    fy: float = AirField(default=415.0)
    soil_qa: float = AirField(default=200.0)
    soil_ks: float = AirField(default=40000.0)

    # Loads
    pu_ult: float = AirField(default=1500.0)
    mux_ult: float = AirField(default=150.0)
    muy_ult: float = AirField(default=80.0)
    pu_srv: float = AirField(default=1050.0)
    mux_srv: float = AirField(default=105.0)
    muy_srv: float = AirField(default=55.0)


# ----------------------------------------------------------------------
# 2. UI RENDER HELPERS
# ----------------------------------------------------------------------
def render_footing_plan_css(geom: FootingGeometry):
    scale = 200 / max(geom.length, geom.width)
    dw, dh = geom.length * scale, geom.width * scale
    cw, cd = geom.column_width * scale, geom.column_depth * scale

    # Calculate screen center coordinates
    center_x, center_y = dw / 2, dh / 2

    # Apply Eccentricity (Mapped to screen)
    cx = center_x + (geom.ecc_x * scale) - (cw / 2)
    cy = center_y - (geom.ecc_y * scale) - (cd / 2)  # Invert Y for standard Cartesian

    return air.Div(
        air.Div(f"{geom.length} mm",
                style="text-align: center; font-weight: bold; color: #6b7280; margin-bottom: 4px;"),
        air.Div(
            air.Div(f"{geom.width} mm",
                    style="position: absolute; left: -75px; top: 50%; transform: translateY(-50%); font-weight: bold; color: #6b7280;"),
            air.Div(
                # Column Indicator
                air.Div(
                    style=f"position: absolute; left: {cx}px; top: {cy}px; width: {cw}px; height: {cd}px; background: #2563eb; border: 2px solid #111827; border-radius: 2px;"),
                # Origin Axis lines
                air.Div(
                    style="position: absolute; left: 0; top: 50%; width: 100%; height: 1px; background: rgba(0,0,0,0.1); border-top: 1px dashed #9ca3af;"),
                air.Div(
                    style="position: absolute; left: 50%; top: 0; width: 1px; height: 100%; background: rgba(0,0,0,0.1); border-left: 1px dashed #9ca3af;"),
                style=f"position: relative; width: {dw}px; height: {dh}px; background: #f3f4f6; border: 3px solid #111827; border-radius: 4px;"
            ),
            style="position: relative; display: inline-block; margin-left: 60px;"
        ),
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; background: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; width: 100%; box-sizing: border-box;"
    )


def render_contour_card(title, b64_img):
    return air.Div(
        air.H4(title, style="text-align: center; color: #4b5563; margin-bottom: 12px; font-size: 15px;"),
        air.Img(src=f"data:image/png;base64,{b64_img}",
                style="width: 100%; border-radius: 8px; border: 1px solid #e5e7eb;"),
        class_="section-box", style="padding: 12px;"
    )


def render_progress_modal():
    """Generates the hidden progress modal and its driving JavaScript."""
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

            // Runs over ~9.5 seconds to simulate the FEA analysis steps
            let interval = setInterval(() => {
                progress += 1;
                if(progress > 98) {
                    clearInterval(interval);
                    return; // Hold at 98% until server responds
                }

                bar.style.width = progress + '%';
                pctText.innerText = progress + '%';

                if(progress < 15) text.innerText = 'Initializing OpenSees FEA Mesh...';
                else if(progress < 45) text.innerText = 'Running Service State Analysis (Nonlinear Soil)...';
                else if(progress < 75) text.innerText = 'Running Ultimate State Analysis...';
                else if(progress < 90) text.innerText = 'Evaluating ACI 318M-25 Demands...';
                else text.innerText = 'Finalizing Contours & QTO...';
            }, 100); 
        }
    """
    return air.Div(
        air.Script(js_script),
        air.Div(
            air.H2("Analyzing Footing", style="margin-bottom: 8px; color: #111827;"),
            air.P("Please wait. OpenSeesPy is calculating demands.",
                  style="color: #6b7280; margin-bottom: 24px; font-size: 14px;"),
            air.Div(
                air.Div(id="progressBar",
                        style="width: 0%; height: 100%; background-color: #db2777; border-radius: 8px; transition: width 0.1s linear;"),
                style="width: 100%; height: 12px; background-color: #e5e7eb; border-radius: 8px; margin-bottom: 16px; overflow: hidden;"
            ),
            air.Div(
                air.Span(id="progressText", style="font-weight: 600; color: #2563eb;"),
                air.Span(id="progressPct", style="font-weight: bold; color: #111827;"),
                style="display: flex; justify-content: space-between; font-size: 14px;"
            ),
            style=card_style
        ),
        id="analysisProgressModal", style=modal_style
    )


# ----------------------------------------------------------------------
# 3. MODULE ROUTES
# ----------------------------------------------------------------------
def setup_footing_routes(app):
    @app.get("/footing")
    def footing_index(request: air.Request):
        data = FootingDesignModel(**json.loads(request.cookies.get("footing_inputs", "{}"))) if request.cookies.get(
            "footing_inputs") else FootingDesignModel()
        if not data.proj_date: data.proj_date = date.today().strftime("%Y-%m-%d")
        csrf_token = getattr(request.state, "csrf_token", request.cookies.get("csrftoken", "dev_token"))

        return expressive_layout(
            render_progress_modal(),  # Inject the hidden modal
            air.Header(air.A("← Dashboard", href="/", class_="back-link no-print"), air.H1("RC Footing Designer"),
                       air.P("Nonlinear FEA Base in accordance with ACI 318M-25", class_="subtitle"),
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
                        air.H2("Geometry, Material & Soil"),
                        air.Div(
                            air.Div(air.Label("Length X (mm)"),
                                    air.Input(type="number", name="length", value=str(data.length)),
                                    class_="form-group"),
                            air.Div(air.Label("Width Y (mm)"),
                                    air.Input(type="number", name="width", value=str(data.width)), class_="form-group"),
                            air.Div(air.Label("Thickness (mm)"),
                                    air.Input(type="number", name="thickness", value=str(data.thickness)),
                                    class_="form-group"),

                            air.Div(air.Label("Column Width (mm)"),
                                    air.Input(type="number", name="col_w", value=str(data.col_w)), class_="form-group"),
                            air.Div(air.Label("Column Depth (mm)"),
                                    air.Input(type="number", name="col_d", value=str(data.col_d)), class_="form-group"),
                            air.Div(air.Label("Subgrade Modulus Ks (kN/m³)"),
                                    air.Input(type="number", name="soil_ks", value=str(data.soil_ks)),
                                    class_="form-group"),

                            air.Div(air.Label("Eccentricity X (mm)"),
                                    air.Input(type="number", name="ecc_x", value=str(data.ecc_x)), class_="form-group"),
                            air.Div(air.Label("Eccentricity Y (mm)"),
                                    air.Input(type="number", name="ecc_y", value=str(data.ecc_y)), class_="form-group"),
                            air.Div(air.Label("Allowable Bearing Qa (kPa)"),
                                    air.Input(type="number", name="soil_qa", value=str(data.soil_qa)),
                                    class_="form-group"),

                            air.Div(air.Label("f'c (MPa)"),
                                    air.Input(type="number", name="fc_prime", value=str(data.fc_prime)),
                                    class_="form-group"),
                            air.Div(air.Label("fy (MPa)"), air.Input(type="number", name="fy", value=str(data.fy)),
                                    class_="form-group"),
                            class_="grid-3"
                        ), class_="card"
                    ),
                    air.Div(
                        air.H2("Loading"),
                        air.Div(
                            air.Div(
                                air.H3("Ultimate Demands (Strength)"),
                                air.Div(air.Label("Factored Axial Pu (kN)"),
                                        air.Input(type="number", name="pu_ult", value=str(data.pu_ult)),
                                        class_="form-group"),
                                air.Div(air.Label("Factored Moment Mux (kN-m)"),
                                        air.Input(type="number", name="mux_ult", value=str(data.mux_ult)),
                                        class_="form-group"),
                                air.Div(air.Label("Factored Moment Muy (kN-m)"),
                                        air.Input(type="number", name="muy_ult", value=str(data.muy_ult)),
                                        class_="form-group"),
                                class_="section-box"
                            ),
                            air.Div(
                                air.H3("Service Demands (Soil Pressure)"),
                                air.Div(air.Label("Service Axial P (kN)"),
                                        air.Input(type="number", name="pu_srv", value=str(data.pu_srv)),
                                        class_="form-group"),
                                air.Div(air.Label("Service Moment Mx (kN-m)"),
                                        air.Input(type="number", name="mux_srv", value=str(data.mux_srv)),
                                        class_="form-group"),
                                air.Div(air.Label("Service Moment My (kN-m)"),
                                        air.Input(type="number", name="muy_srv", value=str(data.muy_srv)),
                                        class_="form-group"),
                                class_="section-box"
                            ),
                            class_="grid-2"
                        ),
                        air.Button("Analyze Footing", type="submit",
                                   style="width: 100%; font-size: 18px; margin-top: 32px;"),
                        class_="card"
                    ), method="post", action="/footing/design", onsubmit="showProgressModal()"
                    # <-- Attached JS hook here
                )
            )
        )

    @app.post("/footing/design")
    async def footing_design(request: air.Request):
        form_data = await request.form()
        try:
            data = FootingDesignModel(**form_data)
        except Exception as e:
            return AirResponse(content=str(
                expressive_layout(air.Main(air.Div(air.H2("Validation Failed"), air.P(str(e)), class_="card")))),
                               media_type="text/html")

        try:
            engine = ACI318M25FootingDesign()
            mat = MaterialProperties(fc_prime=data.fc_prime, fy=data.fy, fu=data.fy * 1.25, fyt=data.fy,
                                     fut=data.fy * 1.25, es=200000.0,
                                     ec=base_aci_lib.aci.get_concrete_modulus(data.fc_prime), gamma_c=24.0,
                                     description="")
            geom = FootingGeometry(data.length, data.width, data.thickness, 75.0, data.col_w, data.col_d,
                                   FootingType.ISOLATED, data.ecc_x, data.ecc_y, data.soil_ks)
            soil = SoilProperties(data.soil_qa)
            loads = FootingLoads(data.pu_ult, data.mux_ult, data.muy_ult, 0, 0, data.pu_srv, data.mux_srv, data.muy_srv)

            res = engine.perform_complete_design(geom, loads, soil, mat)
            qto = engine.calculate_qto(geom, res)

            notes_elements = [
                air.Ul(*[air.Li(f"{n}") for n in res.design_notes], class_="notes-list")] if res.design_notes else []

            reinf_str_x = f"{res.reinforcement.bottom_bars_x} @ {res.reinforcement.bottom_spacing_x:.0f} mm"
            reinf_str_y = f"{res.reinforcement.bottom_bars_y} @ {res.reinforcement.bottom_spacing_y:.0f} mm"

            report_content = air.Main(
                air.Div(
                    air.Button("🖨️ Save as PDF", onclick="window.print()", style="background-color: var(--secondary);"),
                    style="margin-bottom: 24px; display: flex; justify-content: flex-end;", class_="no-print"),
                air.Div(
                    air.H2("Input Summary"),
                    air.Div(
                        air.Div(
                            air.H3("Dimensions", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                            air.Ul(
                                air.Li(air.Strong("Pad Size"),
                                       air.Span(f"{data.length}x{data.width}x{data.thickness} mm",
                                                class_="data-value")),
                                air.Li(air.Strong("Column"),
                                       air.Span(f"{data.col_w}x{data.col_d} mm", class_="data-value")),
                                air.Li(air.Strong("Eccentricity"),
                                       air.Span(f"ex={data.ecc_x}, ey={data.ecc_y} mm", class_="data-value")),
                            ), class_="section-box"
                        ),
                        air.Div(
                            air.H3("Properties", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                            air.Ul(
                                air.Li(air.Strong("Soil Qa"), air.Span(f"{data.soil_qa} kPa", class_="data-value")),
                                air.Li(air.Strong("Soil Ks"), air.Span(f"{data.soil_ks} kN/m³", class_="data-value")),
                                air.Li(air.Strong("Materials"),
                                       air.Span(f"f'c={data.fc_prime}, fy={data.fy} MPa", class_="data-value")),
                            ), class_="section-box"
                        ), class_="grid-2"
                    ), class_="card"
                ),
                air.Div(
                    air.H2("Design Results"),
                    air.Div(
                        air.Div(
                            render_footing_plan_css(geom),
                            air.H4("Analysis Utilization"),
                            air.Ul(
                                air.Li(air.Strong("Max Bearing Pressure"),
                                       air.Span(f"{res.bearing_pressure_max:.1f} kPa", class_="data-value",
                                                style=f"color: {'#16A34A' if res.bearing_ok else '#DC2626'}; font-weight: bold;")),
                                air.Li(air.Strong("Min Bearing Pressure"),
                                       air.Span(f"{res.bearing_pressure_min:.1f} kPa", class_="data-value")),
                                air.Li(air.Strong("1-Way Shear OK?"),
                                       air.Span(f"{'Pass' if res.one_way_shear_ok else 'Fail'}", class_="data-value",
                                                style=f"color: {'#16A34A' if res.one_way_shear_ok else '#DC2626'}; font-weight: bold;")),
                                air.Li(air.Strong("2-Way Shear OK?"),
                                       air.Span(f"{'Pass' if res.two_way_shear_ok else 'Fail'}", class_="data-value",
                                                style=f"color: {'#16A34A' if res.two_way_shear_ok else '#DC2626'}; font-weight: bold;")),
                            ),
                            air.H4("Provided Reinforcement"),
                            air.Ul(
                                air.Li(air.Strong("X-Direction (Bottom)"), air.Span(reinf_str_x, class_="data-value",
                                                                                    style="color: #2563eb; font-weight: bold;")),
                                air.Li(air.Strong("Y-Direction (Bottom)"), air.Span(reinf_str_y, class_="data-value",
                                                                                    style="color: #db2777; font-weight: bold;")),
                            ), style="height: 100%; display: flex; flex-direction: column; justify-content: flex-start;"
                        ),
                        air.Div(
                            render_contour_card("Bearing Pressure (Service)", res.contours['soil_pressure']),
                            render_contour_card("Bending Mxx (Ultimate)", res.contours['mxx']),
                        ),
                        class_="grid-2"
                    ),
                    air.Div(air.H4("Design Notes", style="margin-top: 20px; color: #92400e;"), *notes_elements,
                            style="padding: 16px; background: #fffbeb; border-radius: 8px; border: 1px solid #fde68a; margin-top: 20px;"),
                    class_="card"
                ),
                air.Div(air.H2("Material Takeoff"), air.Div(
                    air.Div(air.Div("Concrete", class_="metric-label"),
                            air.Div(f"{qto['volume']:.2f} m³", class_="metric-value"), class_="metric-card"),
                    air.Div(air.Div("Formwork", class_="metric-label"),
                            air.Div(f"{qto['formwork']:.2f} m²", class_="metric-value"), class_="metric-card blue"),
                    air.Div(air.Div("Rebar Weight", class_="metric-label"),
                            air.Div(f"{qto['weight']:.1f} kg", class_="metric-value"), class_="metric-card green"),
                    class_="grid-3"), class_="card"
                        )
            )

            resp = AirResponse(content=str(expressive_layout(
                air.Header(air.A("← Edit Inputs", href="/footing", class_="back-link no-print"),
                           air.H1("RC Footing Designer"),
                           air.P("Nonlinear FEA Base in accordance with ACI 318M-25", class_="subtitle"),
                           class_="module-header"), report_content)), media_type="text/html")
            resp.set_cookie("footing_inputs", json.dumps(dict(form_data)), max_age=2592000)
            return resp

        except Exception as e:
            return AirResponse(content=str(expressive_layout(
                air.Main(air.Div(air.H2("Analysis Error", style="color: #DC2626;"), air.P(str(e)), class_="card")))),
                               media_type="text/html")