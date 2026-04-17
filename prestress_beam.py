import air
from air import AirField, AirResponse
from fastapi.responses import Response
from pydantic import BaseModel
import json
from datetime import date
from shared import blueprint_layout
from prestress_beam_pdf import generate_prestress_beam_report

from aci318m25 import MaterialProperties
from aci318m25_prestress import (
    ACI318M25PrestressDesign, SpanGeometry, PrestressLoads, 
    PrestressTendon, PrestressMaterialType, PrestressingMethod, PrestressMemberType
)

class PrestressBeamModel(BaseModel):
    proj_name: str = AirField(default="Typical Prestress Beam")
    proj_loc: str = AirField(default="Manila, PH")
    proj_eng: str = AirField(default="Engr. Doe")
    proj_date: str = AirField(default="")
    
    width: float = AirField(default=400.0)
    height: float = AirField(default=600.0)
    t_flange_width: float = AirField(default=0.0)
    t_flange_height: float = AirField(default=0.0)
    num_spans: int = AirField(default=1)
    spans_data: str = AirField(default='[{"length": 10000.0}]')
    supports_data: str = AirField(default='[{"type":"column/wall"},{"type":"column/wall"}]')
    loads_data: str = AirField(default='[{"span":1,"type":"uniform","loc":0,"dl":10,"sdl":5,"ll":15}]')
    
    fc_prime: float = AirField(default=40.0)
    fci_prime: float = AirField(default=30.0)
    gamma_c: float = AirField(default=24.0)
    
    method: str = AirField(default="pretensioned")
    material: str = AirField(default="astm_a416_strand")
    strand_dia: str = AirField(default="12.70")
    num_tendons: int = AirField(default=10)
    tendon_profile: str = AirField(default="straight")
    eccentricity: float = AirField(default=200.0)
    slip: float = AirField(default=6.0)
    friction_mu: float = AirField(default=0.2)
    friction_k: float = AirField(default=0.0066)  # 1/m — PTI grouted duct midrange
    jacking_force: float = AirField(default=0.0)
    time_loss_mpa: float = AirField(default=0.0)
    
    # Optional Rebar
    rebar_fy: float = AirField(default=420.0)
    rebar_as_top: float = AirField(default=0.0)
    rebar_as_bot: float = AirField(default=0.0)

    # Deflection Settings (ACI 318M-25 Table 24.2.4.1.3 / Table 24.2.2)
    long_term_multiplier: float = AirField(default=2.0)
    deflection_limit: float = AirField(default=240.0)


def setup_prestress_beam_routes(app):
    @app.get("/prestress-beam")
    def prestress_index(request: air.Request):
        data = PrestressBeamModel()
        saved_inputs = request.cookies.get("prestress_beam_inputs")
        if saved_inputs:
            try:
                parsed = json.loads(saved_inputs)
                data = PrestressBeamModel(**parsed)
            except Exception:
                pass
        
        if not data.proj_date: data.proj_date = date.today().strftime("%Y-%m-%d")

        # Safely re-serialise the three JSON blobs so they can be embedded in a
        # <script> tag without any HTML-attribute escaping issues.
        def _safe_js_json(raw, fallback):
            try:
                # json.dumps ensures valid JSON; replace '/' so '</script>' can't leak.
                return json.dumps(json.loads(raw)).replace('/', '\\/')
            except Exception:
                return fallback

        safe_spans    = _safe_js_json(data.spans_data,    '[{"length":10000.0}]')
        safe_supports = _safe_js_json(data.supports_data, '[{"type":"column/wall"},{"type":"column/wall"}]')
        safe_loads    = _safe_js_json(data.loads_data,    '[]')
        ps_init_script = (
            f'window._psInit = {{"spans":{safe_spans},'
            f'"supports":{safe_supports},"loads":{safe_loads}}};'
        )

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

        return blueprint_layout(
            air.Header(
                air.A("← Dashboard", href="/", class_="back-link no-print"),
                air.H1("Prestressed Beam Designer"),
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
                        air.H2("Geometry and Loads"),
                        air.Div(
                            air.Div(air.Label("Beam width bw (mm)"), air.Input(type="number", name="width", value=str(data.width), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Beam depth h (mm)"), air.Input(type="number", name="height", value=str(data.height), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Number of spans"), air.Input(type="number", name="num_spans", id="num_spans", value=str(data.num_spans), step="1", min="1", required=True), class_="form-group"),
                            air.Div(air.Label("T-Flange width bf (mm) [0 = rect]"), air.Input(type="number", name="t_flange_width", value=str(data.t_flange_width), step="any", min="0"), class_="form-group"),
                            air.Div(air.Label("T-Flange height hf (mm) [0 = rect]"), air.Input(type="number", name="t_flange_height", value=str(data.t_flange_height), step="any", min="0"), class_="form-group"),
                            class_="grid-3"
                        ),
                        air.Input(type="hidden", name="spans_data",    id="spans_data",    value=""),
                        air.Input(type="hidden", name="supports_data", id="supports_data", value=""),
                        air.Input(type="hidden", name="loads_data",    id="loads_data",    value=""),
                        air.Script(ps_init_script),
                        air.Div(
                            air.H3("Geometry and Tendon Visualization", style="margin-top: 16px;"),
                            air.Canvas(id="beam_viz", width="800", height="200", style="width: 100%; border: 1px solid #ddd; background: #f9fafb; border-radius: 4px; margin-bottom: 16px;"),
                            air.H3("Spans (Lengths)", style="margin-top: 16px;"),
                            air.Div(id="spans_container"),
                            air.H3("Supports", style="margin-top: 16px;"),
                            air.Div(id="supports_container"),
                            air.H3("Loads", style="margin-top: 16px; display:inline-block; margin-right: 16px;"),
                            air.Button("Add Load", type="button", id="add_load_btn", class_="button secondary", style="padding: 4px 12px; font-size:12px; margin-bottom: 8px;"),
                            air.Div(id="loads_container"),
                        ),
                        air.Script('''
                            document.addEventListener("DOMContentLoaded", () => {
                                // Read initial state injected via <script> tag (avoids HTML-attribute
                                // double-quote escaping issues that would break JSON).
                                let _init        = (window._psInit || {});
                                let spansData    = (_init.spans    || [{length: 10000}]).slice();
                                let supportsData = (_init.supports || [{type:"column/wall"},{type:"column/wall"}]).slice();
                                let loadsData    = (_init.loads    || []).slice();

                                // Flush current in-memory state to hidden inputs right before POST
                                document.querySelector("form").addEventListener("submit", () => {
                                    syncFromTable();
                                    updateInputs();
                                });

                                // Read any values still pending in the rendered inputs
                                function syncFromTable() {
                                    document.querySelectorAll(".span-length").forEach(el => {
                                        let i = parseInt(el.dataset.idx);
                                        if (!spansData[i]) spansData[i] = {length: 10000};
                                        spansData[i].length = parseFloat(el.value) || 10000;
                                    });
                                    document.querySelectorAll(".ld-span").forEach(el => { let i=parseInt(el.dataset.idx); if(loadsData[i]) loadsData[i].span = parseInt(el.value)||1; });
                                    document.querySelectorAll(".ld-loc" ).forEach(el => { let i=parseInt(el.dataset.idx); if(loadsData[i]) loadsData[i].loc  = parseFloat(el.value)||0; });
                                    document.querySelectorAll(".ld-dl"  ).forEach(el => { let i=parseInt(el.dataset.idx); if(loadsData[i]) loadsData[i].dl   = parseFloat(el.value)||0; });
                                    document.querySelectorAll(".ld-sdl" ).forEach(el => { let i=parseInt(el.dataset.idx); if(loadsData[i]) loadsData[i].sdl  = parseFloat(el.value)||0; });
                                    document.querySelectorAll(".ld-ll"  ).forEach(el => { let i=parseInt(el.dataset.idx); if(loadsData[i]) loadsData[i].ll   = parseFloat(el.value)||0; });
                                }

                                function render() {
                                    let n = parseInt(document.getElementById("num_spans").value) || 1;

                                    // ── Spans table ──
                                    let spansHtml = `<table style="width:100%;border-collapse:collapse;margin-top:8px;margin-bottom:16px">
                                        <thead><tr style="border-bottom:2px solid #ccc">
                                            <th style="padding:8px;text-align:left">Span #</th>
                                            <th style="padding:8px;text-align:left">Length (mm)</th>
                                        </tr></thead><tbody>`;
                                    for(let i=0; i<n; i++) {
                                        let L = spansData[i] ? spansData[i].length : 10000;
                                        spansHtml += `<tr style="border-bottom:1px solid #eee">
                                            <td style="padding:8px">${i+1}</td>
                                            <td style="padding:8px"><input type="number" class="span-length" data-idx="${i}" value="${L}" style="width:130px" oninput="_psSpanUpdate(this)"></td>
                                        </tr>`;
                                    }
                                    spansHtml += "</tbody></table>";
                                    document.getElementById("spans_container").innerHTML = spansHtml;

                                    // ── Supports table ──
                                    let supportsHtml = `<table style="width:100%;border-collapse:collapse;margin-top:8px;margin-bottom:16px">
                                        <thead><tr style="border-bottom:2px solid #ccc">
                                            <th style="padding:8px;text-align:left">Support #</th>
                                            <th style="padding:8px;text-align:left">Type</th>
                                        </tr></thead><tbody>`;
                                    for(let i=0; i<=n; i++) {
                                        let sel = supportsData[i] ? supportsData[i].type : "column/wall";
                                        supportsHtml += `<tr style="border-bottom:1px solid #eee">
                                            <td style="padding:8px">${i+1}</td>
                                            <td style="padding:8px">
                                                <select class="support-type" data-idx="${i}" style="width:100%" onchange="_psSupportUpdate(this)">
                                                    <option value="column/wall"   ${sel==="column/wall"   ?"selected":""}>Column / Wall</option>
                                                    <option value="spandrel_beam" ${sel==="spandrel_beam" ?"selected":""}>Spandrel Beam</option>
                                                    <option value="fixed"         ${sel==="fixed"         ?"selected":""}>Fixed (Clamped End)</option>
                                                    <option value="unsupported"   ${sel==="unsupported"   ?"selected":""}>Unsupported</option>
                                                </select>
                                            </td>
                                        </tr>`;
                                    }
                                    supportsHtml += "</tbody></table>";
                                    document.getElementById("supports_container").innerHTML = supportsHtml;

                                    // ── Loads table ──
                                    let loadsHtml = `<table style="width:100%;border-collapse:collapse;margin-top:8px">
                                        <thead><tr style="border-bottom:2px solid #ccc;text-align:left">
                                            <th style="padding:8px">Span</th>
                                            <th style="padding:8px">Type</th>
                                            <th style="padding:8px">Loc (mm)<br><small><em>point load only</em></small></th>
                                            <th style="padding:8px">DL<br><small>(kN/m or kN)</small></th>
                                            <th style="padding:8px">SDL<br><small>(kN/m or kN)</small></th>
                                            <th style="padding:8px">LL<br><small>(kN/m or kN)</small></th>
                                            <th></th>
                                        </tr></thead><tbody>`;
                                    loadsData.forEach((ld, idx) => {
                                        let isPoint = ld.type === "point";
                                        let locStyle = isPoint ? "width:80px" : "width:80px;opacity:0.3;pointer-events:none";
                                        loadsHtml += `<tr style="border-bottom:1px solid #eee">
                                            <td style="padding:8px"><input type="number" class="ld-span" data-idx="${idx}" value="${ld.span||1}" min="1" max="${n}" style="width:55px" oninput="_psLoadField('span',${idx},this,true)"></td>
                                            <td style="padding:8px">
                                                <select class="ld-type" data-idx="${idx}" onchange="_psLoadType(${idx},this)">
                                                    <option value="uniform" ${ld.type==="uniform"?"selected":""}>Uniform (kN/m)</option>
                                                    <option value="point"   ${ld.type==="point"  ?"selected":""}>Point (kN)</option>
                                                </select>
                                            </td>
                                            <td style="padding:8px"><input type="number" class="ld-loc" data-idx="${idx}" value="${ld.loc||0}" style="${locStyle}" oninput="_psLoadField('loc',${idx},this)"></td>
                                            <td style="padding:8px"><input type="number" class="ld-dl"  data-idx="${idx}" value="${ld.dl||0}"  style="width:70px" oninput="_psLoadField('dl', ${idx},this)"></td>
                                            <td style="padding:8px"><input type="number" class="ld-sdl" data-idx="${idx}" value="${ld.sdl||0}" style="width:70px" oninput="_psLoadField('sdl',${idx},this)"></td>
                                            <td style="padding:8px"><input type="number" class="ld-ll"  data-idx="${idx}" value="${ld.ll||0}"  style="width:70px" oninput="_psLoadField('ll', ${idx},this)"></td>
                                            <td style="padding:8px"><button type="button" onclick="_psDelLoad(${idx})" style="background:#ef4444;border:none;padding:4px 10px;color:white;border-radius:4px;cursor:pointer">✕</button></td>
                                        </tr>`;
                                    });
                                    loadsHtml += "</tbody></table>";
                                    document.getElementById("loads_container").innerHTML = loadsHtml;

                                    // ── Visualization ──
                                    drawVisualization(n);
                                }

                                function drawVisualization(n) {
                                    const cvs = document.getElementById("beam_viz");
                                    if(!cvs) return;
                                    const ctx = cvs.getContext("2d");
                                    ctx.clearRect(0,0,cvs.width,cvs.height);
                                    
                                    let totalL = spansData.reduce((acc, s) => acc + (s ? s.length||10000 : 10000), 0);
                                    if(totalL <= 0) totalL = 10000;
                                    const scale = (cvs.width - 40) / totalL;
                                    
                                    ctx.font = "12px sans-serif";
                                    ctx.textAlign = "center";

                                    // Draw Beam
                                    ctx.fillStyle = "#e2e8f0";
                                    ctx.fillRect(20, 80, totalL*scale, 40);
                                    ctx.strokeStyle = "#94a3b8";
                                    ctx.strokeRect(20, 80, totalL*scale, 40);

                                    // Draw Supports
                                    let cl = 20;
                                    for(let i=0; i<=n; i++) {
                                        let currType = supportsData[i]?.type || "column/wall";
                                        if (currType === "column/wall") {
                                            ctx.fillStyle = "#64748b";
                                            ctx.fillRect(cl-6, 120, 12, 30);
                                        } else if (currType === "spandrel_beam") {
                                            ctx.fillStyle = "#475569";
                                            ctx.fillRect(cl-8, 120, 16, 16);
                                            ctx.strokeStyle = "#1e293b";
                                            ctx.strokeRect(cl-8, 120, 16, 16);
                                        } else if (currType === "fixed") {
                                            // Fixed/clamped end: filled rectangle + horizontal hatch lines
                                            ctx.fillStyle = "#1e293b";
                                            ctx.fillRect(cl-10, 118, 20, 32);
                                            ctx.strokeStyle = "#94a3b8";
                                            ctx.lineWidth = 1;
                                            for (let hh = 0; hh < 5; hh++) {
                                                ctx.beginPath();
                                                ctx.moveTo(cl-10, 122 + hh * 6);
                                                ctx.lineTo(cl+10, 122 + hh * 6);
                                                ctx.stroke();
                                            }
                                        }
                                        if (i < n) cl += (spansData[i]?.length || 10000) * scale;
                                    }

                                    // Draw Spans Text
                                    cl = 20;
                                    ctx.fillStyle = "#334155";
                                    for(let i=0; i<n; i++) {
                                        let L = spansData[i]?.length || 10000;
                                        ctx.fillText(`L = ${L} mm`, cl + L*scale/2, 140);
                                        cl += L*scale;
                                    }

                                    // Draw Tendon
                                    let profile = document.querySelector("select[name='tendon_profile']")?.value || "straight";
                                    let e = parseFloat(document.querySelector("input[name='eccentricity']")?.value || "200");
                                    let h = parseFloat(document.querySelector("input[name='height']")?.value || "600");
                                    // Beam rectangle spans y=80..120 (40px). Centroid at y=100.
                                    // Scale eccentricity (positive=below centroid) to canvas pixels.
                                    const beamPx = 40; // px height of drawn beam rect
                                    const ePx = Math.min((e / Math.max(1, h)) * beamPx, beamPx * 0.48);
                                    const yEnd = 100 + ePx;       // tendon y at ends (eccentricity below centroid)
                                    const yMid = 100 + ePx;       // for straight/constant profiles
                                    ctx.strokeStyle = "#ef4444";
                                    ctx.setLineDash([5, 5]);
                                    ctx.lineWidth = 2;
                                    ctx.fillStyle = "#ef4444";
                                    cl = 20;
                                    for(let i=0; i<n; i++) {
                                        let L = spansData[i]?.length || 10000;
                                        let x0 = cl, x1 = cl + L*scale;
                                        ctx.beginPath();
                                        ctx.moveTo(x0, yEnd);
                                        if(profile === "straight") {
                                            ctx.lineTo(x1, yEnd);
                                            ctx.stroke();
                                            ctx.fillText(`e=${e}mm`, (x0+x1)/2, Math.min(yEnd + 12, 155));
                                        } else if (profile === "harped") {
                                            let midObj = (x0 + x1)/2;
                                            // Harped: tendon drops from ends (at ePx) to max droop at midspan
                                            let yHarpMid = Math.min(100 + ePx * 1.5, 118);
                                            ctx.lineTo(midObj, yHarpMid);
                                            ctx.lineTo(x1, yEnd);
                                            ctx.stroke();
                                            ctx.fillText(`Max e=${e}mm`, midObj, Math.min(yHarpMid + 12, 155));
                                        } else if (profile === "multiple_harped") {
                                            let yHarpMid = Math.min(100 + ePx * 1.5, 118);
                                            ctx.lineTo(x0 + L*scale/3, yHarpMid);
                                            ctx.lineTo(x0 + 2*L*scale/3, yHarpMid);
                                            ctx.lineTo(x1, yEnd);
                                            ctx.stroke();
                                            ctx.fillText(`e=${e}mm`, x0 + L*scale/2, Math.min(yHarpMid + 12, 155));
                                        } else { // Parabolic
                                            let yParabMid = Math.min(100 + ePx * 1.6, 120);
                                            ctx.quadraticCurveTo((x0+x1)/2, yParabMid, x1, yEnd);
                                            ctx.stroke();
                                            ctx.fillText(`Max e=${e}mm`, (x0+x1)/2, Math.min(yParabMid + 12, 155));
                                        }
                                        cl = x1;
                                    }
                                    ctx.setLineDash([]);
                                    
                                    // Draw Loads
                                    loadsData.forEach(ld => {
                                        if(!ld) return;
                                        let sIdx = parseInt(ld.span||1)-1;
                                        if(sIdx < 0 || sIdx >= n) return;
                                        let sumLd = (parseFloat(ld.dl)||0) + (parseFloat(ld.sdl)||0) + (parseFloat(ld.ll)||0);
                                        
                                        let xLeft = 20;
                                        for(let i=0; i<sIdx; i++) xLeft += (spansData[i]?.length || 10000) * scale;
                                        let spanL = spansData[sIdx]?.length || 10000;
                                        
                                        ctx.fillStyle = "#3b82f6";
                                        if(ld.type === "uniform") {
                                            ctx.globalAlpha = 0.3;
                                            ctx.fillRect(xLeft, 60, spanL*scale, 10);
                                            ctx.globalAlpha = 1.0;
                                            ctx.fillText(`${sumLd} kN/m`, xLeft + spanL*scale/2, 55);
                                        } else {
                                            let loc = parseFloat(ld.loc || 0)*scale;
                                            ctx.beginPath();
                                            ctx.moveTo(xLeft+loc-5, 50);
                                            ctx.lineTo(xLeft+loc+5, 50);
                                            ctx.lineTo(xLeft+loc, 75);
                                            ctx.fill();
                                            ctx.fillText(`${sumLd} kN`, xLeft+loc, 45);
                                        }
                                    });
                                }

                                // Global helpers (needed so oninput/onchange inline attrs can reach them)
                                window._psSpanUpdate = function(el) {
                                    let i = parseInt(el.dataset.idx);
                                    if (!spansData[i]) spansData[i] = {};
                                    spansData[i].length = parseFloat(el.value) || 10000;
                                    updateInputs();
                                };
                                window._psSupportUpdate = function(el) {
                                    let i = parseInt(el.dataset.idx);
                                    if (!supportsData[i]) supportsData[i] = {};
                                    supportsData[i].type = el.value;
                                    updateInputs();
                                };
                                window._psLoadField = function(field, idx, el, asInt) {
                                    loadsData[idx][field] = asInt ? (parseInt(el.value)||1) : (parseFloat(el.value)||0);
                                    updateInputs();
                                };
                                window._psLoadType = function(idx, el) {
                                    loadsData[idx].type = el.value;
                                    updateInputs();
                                    render();
                                };
                                window._psDelLoad = function(idx) {
                                    loadsData.splice(idx, 1);
                                    updateInputs();
                                    render();
                                };

                                function updateInputs() {
                                    let n = parseInt(document.getElementById("num_spans").value) || 1;
                                    while (spansData.length < n)    spansData.push({length: 10000.0});
                                    spansData    = spansData.slice(0, n);
                                    while (supportsData.length < n+1) supportsData.push({type: "column/wall"});
                                    supportsData = supportsData.slice(0, n+1);
                                    document.getElementById("spans_data").value    = JSON.stringify(spansData);
                                    document.getElementById("supports_data").value = JSON.stringify(supportsData);
                                    document.getElementById("loads_data").value    = JSON.stringify(loadsData);
                                }

                                document.getElementById("num_spans").addEventListener("change", () => { updateInputs(); render(); });
                                document.getElementById("add_load_btn").addEventListener("click", () => {
                                    loadsData.push({span: 1, type: "uniform", loc: 0, dl: 10, sdl: 5, ll: 15});
                                    updateInputs(); render();
                                });
                                // Update visualization on profile, eccentricity, or height change
                                document.querySelector("select[name='tendon_profile']").addEventListener("change", render);
                                document.querySelector("input[name='eccentricity']").addEventListener("input", render);
                                document.querySelector("input[name='height']").addEventListener("input", render);

                                render();
                                updateInputs();   // sync hidden inputs from initial data on page load
                            });
                        '''),
                        class_="card"
                    ),
                    air.Div(
                        air.H2("Material and Prestress Properties"),
                        air.Div(
                            air.Div(air.Label("Method"), air.Select(
                                air.Option("Pretensioned", value="pretensioned", selected=(data.method=="pretensioned")),
                                air.Option("Post-Tensioned (Bonded)", value="posttensioned_bonded", selected=(data.method=="posttensioned_bonded")),
                                air.Option("Post-Tensioned (Unbonded)", value="posttensioned_unbonded", selected=(data.method=="posttensioned_unbonded")),
                                name="method"
                            ), class_="form-group"),
                            air.Div(air.Label("Tendon Profile"), air.Select(
                                air.Option("Straight", value="straight", selected=(data.tendon_profile=="straight")),
                                air.Option("Parabolic", value="parabolic", selected=(data.tendon_profile=="parabolic")),
                                air.Option("Harped", value="harped", selected=(data.tendon_profile=="harped")),
                                air.Option("Multiple Harped", value="multiple_harped", selected=(data.tendon_profile=="multiple_harped")),
                                name="tendon_profile"
                            ), class_="form-group"),
                            air.Div(air.Label("Material Type"), air.Select(
                                air.Option("ASTM A416 Strand", value="astm_a416_strand", selected=(data.material=="astm_a416_strand")),
                                air.Option("ASTM A722 Bar", value="astm_a722_bar", selected=(data.material=="astm_a722_bar")),
                                air.Option("ASTM A421 Wire", value="astm_a421_wire", selected=(data.material=="astm_a421_wire")),
                                name="material"
                            ), class_="form-group"),
                            air.Div(
                                air.Label("Strand / Bar / Wire Size"),
                                air.Select(id="strand_dia_select", name="strand_dia"),
                                air.Script(f'''
                                    (function() {{
                                        const DIAMETERS = {{
                                            "astm_a416_strand": [
                                                ["9.53", "9.53 mm (3/8 in)"],
                                                ["11.11", "11.11 mm (7/16 in)"],
                                                ["12.70", "12.70 mm (1/2 in)"],
                                                ["15.24", "15.24 mm (0.6 in)"],
                                                ["17.78", "17.78 mm (0.7 in)"]
                                            ],
                                            "astm_a722_bar": [
                                                ["19", "19 mm (#6)"],
                                                ["22", "22 mm (#7)"],
                                                ["25", "25 mm (#8)"],
                                                ["29", "29 mm (#9)"],
                                                ["32", "32 mm (#10)"],
                                                ["36", "36 mm (#11)"],
                                                ["40", "40 mm (#12)"],
                                                ["46", "46 mm (#14)"],
                                                ["65", "65 mm (2-1/2 in)"],
                                                ["75", "75 mm (3 in)"]
                                            ],
                                            "astm_a421_wire": [
                                                ["4.88", "4.88 mm (0.192 in WA/BA)"],
                                                ["4.98", "4.98 mm (0.196 in WA/BA)"],
                                                ["6.35", "6.35 mm (0.250 in WA/BA)"],
                                                ["7.01", "7.01 mm (0.276 in WA/BA)"]
                                            ]
                                        }};
                                        const sel = document.getElementById("strand_dia_select");
                                        const matSel = document.querySelector("select[name=\'material\']");
                                        const savedDia = {json.dumps(data.strand_dia)};
                                        function populateDia() {{
                                            const mat = matSel.value;
                                            const opts = DIAMETERS[mat] || [];
                                            sel.innerHTML = "";
                                            opts.forEach(([val, label]) => {{
                                                const opt = document.createElement("option");
                                                opt.value = val;
                                                opt.textContent = label;
                                                if (val === savedDia) opt.selected = true;
                                                sel.appendChild(opt);
                                            }});
                                        }}
                                        populateDia();
                                        matSel.addEventListener("change", populateDia);
                                    }})();
                                '''),
                                class_="form-group"
                            ),
                            air.Div(air.Label("Number of Tendons"), air.Input(type="number", name="num_tendons", value=str(data.num_tendons), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Eccentricity e (mm, ≤ h/2−50mm cover)"), air.Input(type="number", name="eccentricity", value=str(data.eccentricity), step="any", required=True, max=str(data.height / 2 - 50)), class_="form-group"),
                            air.Div(air.Label("Init. Jacking Force (kN/tendon) [0=auto]"), air.Input(type="number", name="jacking_force", value=str(data.jacking_force), step="any"), class_="form-group"),
                            
                            air.Div(air.Label("Unit Weight γc (kN/m³)"), air.Input(type="number", name="gamma_c", value=str(data.gamma_c), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("f'c / 28 days (MPa)"), air.Input(type="number", name="fc_prime", value=str(data.fc_prime), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("f'ci / transfer (MPa)"), air.Input(type="number", name="fci_prime", value=str(data.fci_prime), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Anchorage Slip (mm) [PT]"), air.Input(type="number", name="slip", value=str(data.slip), step="any"), class_="form-group"),
                            
                            air.Div(air.Label("Friction μ [PT]"), air.Input(type="number", name="friction_mu", value=str(data.friction_mu), step="any"), class_="form-group"),
                            air.Div(air.Label("Friction k (1/m) [PT]"), air.Input(type="number", name="friction_k", value=str(data.friction_k), step="any"), class_="form-group"),
                            air.Div(air.Label("Time-Dependent Loss (MPa) [0=auto]"), air.Input(type="number", name="time_loss_mpa", value=str(data.time_loss_mpa), step="any"), class_="form-group"),

                            air.Div(air.Label("Rebar Yield fy (MPa) [Optional]"), air.Input(type="number", name="rebar_fy", value=str(data.rebar_fy), step="any", required=True), class_="form-group"),
                            air.Div(air.Label("Top Rebar As' (mm²) [Optional]"), air.Input(type="number", name="rebar_as_top", value=str(data.rebar_as_top), step="any"), class_="form-group"),
                            air.Div(air.Label("Bot Rebar As (mm²) [Optional]"), air.Input(type="number", name="rebar_as_bot", value=str(data.rebar_as_bot), step="any"), class_="form-group"),
                            air.Div(air.Label("Long-Term Multiplier (ACI T.24.2.4.1.3)"), air.Select(
                                air.Option("2.0 — 5+ years",   value="2.0", selected=(data.long_term_multiplier == 2.0)),
                                air.Option("1.4 — 12 months",  value="1.4", selected=(data.long_term_multiplier == 1.4)),
                                air.Option("1.2 — 6 months",   value="1.2", selected=(data.long_term_multiplier == 1.2)),
                                air.Option("1.0 — 3 months",   value="1.0", selected=(data.long_term_multiplier == 1.0)),
                                name="long_term_multiplier"
                            ), class_="form-group"),
                            air.Div(air.Label("Deflection Limit (ACI T.24.2.2)"), air.Select(
                                air.Option("L/240 — Roof (no sensitive elements)",     value="240.0", selected=(data.deflection_limit == 240.0)),
                                air.Option("L/360 — Floor (non-structural elements)", value="360.0", selected=(data.deflection_limit == 360.0)),
                                air.Option("L/480 — Sensitive elements",              value="480.0", selected=(data.deflection_limit == 480.0)),
                                name="deflection_limit"
                            ), class_="form-group"),
                            class_="grid-3"
                        ),
                        air.Div(
                            air.Button("Run Analysis", type="submit", formaction="/prestress-beam/design",
                                       style="flex:1; font-size: 18px; padding: 12px; background: var(--accent); color: var(--bg-deep); border: none; border-radius: 6px; cursor: pointer; font-weight: 600;"),
                            air.Button("Run Design", type="submit", formaction="/prestress-beam/auto-design",
                                       style="flex:1; font-size: 18px; padding: 12px; background: #2563eb; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;",
                                       title="Auto-size strand diameter, jacking force, and eccentricity. Calculate supplemental rebar if needed."),
                            style="display: flex; gap: 12px; margin-top: 32px;",
                        ),
                        class_="card"
                    ),
                    method="post", action="/prestress-beam/design"
                )
            )
        )

    @app.post("/prestress-beam/design")
    async def prestress_design(request: air.Request):
        form_data = await request.form()
        cookie_data = json.dumps(dict(form_data))
        
        try:
            data = PrestressBeamModel(**form_data)
        except Exception as e:
            error_html = str(blueprint_layout(
                air.Header(
                    air.A("← Go Back", href="/prestress-beam", class_="back-link no-print"),
                    air.H1("Calculation Error"),
                    air.P("Form validation failed.", class_="subtitle"),
                    class_="module-header"
                ),
                air.Main(air.Div(air.H2("Invalid Inputs", style="color: #DC2626;"), air.P(str(e)), class_="card"))
            ))
            resp = AirResponse(content=error_html, media_type="text/html")
            resp.set_cookie("prestress_beam_inputs", cookie_data, max_age=2592000, httponly=True, samesite="lax")
            return resp
            
        designer = ACI318M25PrestressDesign()
        mat_type = PrestressMaterialType(data.material)
        method_type = PrestressingMethod(data.method)
        prop = designer.get_prestress_material(mat_type, data.strand_dia)
        
        _lookup_failed = not prop
        if _lookup_failed:
            prop = {'diameter': float(data.strand_dia) if data.strand_dia.replace('.','',1).isdigit() else 12.7, 'area': 98.7, 'fpu': 1860, 'fpy': 1674, 'description': 'Custom (A416 12.70mm fallback)'}
        
        tendon = PrestressTendon(
            material_type=mat_type,
            diameter=prop['diameter'],
            area=prop['area'],
            fpu=prop['fpu'],
            fpy=prop['fpy'],
            number_of_tendons=data.num_tendons,
            eccentricity=data.eccentricity,
            slip=data.slip,
            friction_mu=data.friction_mu,
            friction_k=data.friction_k,
            jacking_force=data.jacking_force,
            time_loss_mpa=data.time_loss_mpa
        )
        
        try:
            spans_json = json.loads(data.spans_data)
        except Exception:
            spans_json = [{"length": 10000.0}] * data.num_spans
            
        try:
            loads_json = json.loads(data.loads_data)
        except Exception:
            loads_json = []
        
        # Use the JSON array length as the authoritative span count
        num_spans = max(1, len(spans_json))
        
        # Build spans list
        spans = []
        for s in spans_json:
            spans.append(SpanGeometry(
                length=float(s.get('length', 10000)),
                width=data.width,
                height=data.height,
                t_flange_width=data.t_flange_width,
                t_flange_height=data.t_flange_height,
            ))
        
        # Beam self-weight (kN/m) — added to dead load automatically
        # For T-sections, use the actual gross cross-sectional area computed by SpanGeometry
        sw_kNm = data.gamma_c * (spans[0].area / 1e6) if spans else data.gamma_c * (data.width * data.height / 1e6)

        # Initialise per-span load accumulators (self-weight pre-applied)
        span_loads = [PrestressLoads(dead_load=sw_kNm, superimposed_dl=0, live_load=0) for _ in range(num_spans)]
            
        for ld in loads_json:
            s_idx = max(0, min(num_spans - 1, int(ld.get('span', 1)) - 1))
            l_type = ld.get('type', 'uniform')
            dl  = float(ld.get('dl',  0))
            sdl = float(ld.get('sdl', 0))
            ll  = float(ld.get('ll',  0))
            if l_type == 'uniform':
                span_loads[s_idx].dead_load       += dl
                span_loads[s_idx].superimposed_dl += sdl
                span_loads[s_idx].live_load        += ll
            else:
                # Point load at location `a` mm from left support.
                # Equivalent uniform load that produces the same midspan moment:
                #   M_max = P*a*(L-a)/L  =>  w_eq = 8*P*a*(L-a)/L^3
                # If loc == 0 (unset), assume midspan (a = L/2) => w_eq = 2P/L
                L_mm = max(1.0, spans[s_idx].length)
                L_m  = L_mm / 1000.0
                a_mm = float(ld.get('loc', 0))
                if a_mm <= 0 or a_mm >= L_mm:
                    a_mm = L_mm / 2.0   # default to midspan
                a_m = a_mm / 1000.0
                w_factor = 8.0 * a_m * (L_m - a_m) / max(0.001, L_m ** 3)
                span_loads[s_idx].dead_load       += dl  * w_factor
                span_loads[s_idx].superimposed_dl += sdl * w_factor
                span_loads[s_idx].live_load        += ll  * w_factor

        mat_props = MaterialProperties(
            fc_prime=data.fc_prime, fy=data.rebar_fy, fu=data.rebar_fy*1.2, fyt=data.rebar_fy, fut=data.rebar_fy*1.2,
            es=200000.0, ec=designer.aci.get_concrete_modulus(data.fc_prime), gamma_c=data.gamma_c, description="Concrete"
        )

        try:
            supports_types = [s.get('type', 'column/wall') for s in json.loads(data.supports_data)]
        except Exception:
            supports_types = ['column/wall'] * (num_spans + 1)
        if len(supports_types) < num_spans + 1:
            supports_types += ['column/wall'] * (num_spans + 1 - len(supports_types))

        results = designer.run_continuous_analysis(
            spans=spans,
            span_loads=span_loads,
            supports_types=supports_types,
            tendon=tendon,
            mat_props=mat_props,
            fci_prime=data.fci_prime,
            method=method_type,
            member_type=PrestressMemberType.BEAM,
            tendon_profile=data.tendon_profile,
            rebar_as_bot=data.rebar_as_bot,
            rebar_as_top=data.rebar_as_top,
            rebar_fy=data.rebar_fy,
            long_term_multiplier=data.long_term_multiplier,
            deflection_limit=data.deflection_limit,
        )

        
        result_elements = []

        # ── Buttons (no-print) ──────────────────────────────────────────────
        result_elements.append(air.Div(
            air.Div(
                air.Button(
                    "\U0001f5a8 Print Summary",
                    onclick="window.print()",
                    style="background-color: var(--accent); color: var(--bg-deep); border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 600;"
                ),
                air.A(
                    "\U0001f4c4 Download Detailed Report",
                    href="/prestress-beam/pdf",
                    target="_blank",
                    style="background-color: var(--accent); color: var(--bg-deep); text-decoration: none; padding: 8px 16px; border-radius: 4px; font-weight: 600;"
                ),
                style="display: flex; justify-content: flex-end; align-items: center; gap: 8px;",
            ),
            style="margin-bottom: 24px;",
            class_="no-print",
        ))

        # ── Project Information ─────────────────────────────────────────────
        result_elements.append(air.Div(
            air.H2("Project Information"),
            air.Div(
                air.Div(air.Strong("Project Name: "), air.Span(data.proj_name, class_="data-value")),
                air.Div(air.Strong("Location: "), air.Span(data.proj_loc, class_="data-value")),
                air.Div(air.Strong("Structural Engineer: "), air.Span(data.proj_eng, class_="data-value")),
                air.Div(air.Strong("Date: "), air.Span(data.proj_date, class_="data-value")),
                style="display: flex; flex-wrap: wrap; gap: 16px; font-size: 16px;"
            ),
            style="margin-bottom: 24px; padding-bottom: 20px; border-bottom: 2px dashed #e5e7eb;"
        ))

        # ── Input Parameters ───────────────────────────────────────────────
        result_elements.append(air.Div(
            air.H2("Input Parameters"),
            air.Div(
                air.Div(
                    air.H3("Geometry", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                    air.Ul(
                        air.Li(air.Strong("Cross-section: "), air.Span(f"bw = {data.width:.0f} mm \u00d7 h = {data.height:.0f} mm", class_="data-value")),
                        *(
                            [air.Li(air.Strong("T-Flange: "), air.Span(f"bf = {data.t_flange_width:.0f} mm, hf = {data.t_flange_height:.0f} mm", class_="data-value"))]
                            if data.t_flange_width > 0 else []
                        ),
                        *[air.Li(air.Strong(f"Span {j+1}: "), air.Span(f"L = {sp.get('length', 10000):.0f} mm", class_="data-value")) for j, sp in enumerate(spans_json)],
                        *[air.Li(air.Strong(f"Support {j+1}: "), air.Span(st, class_="data-value")) for j, st in enumerate(supports_types)],
                    ),
                    class_="section-box"
                ),
                air.Div(
                    air.H3("Materials & Prestress", style="font-size: 16px; margin-bottom: 8px; border:none; padding:0;"),
                    air.Ul(
                        air.Li(air.Strong("Concrete: "), air.Span(f"f\u2019c = {data.fc_prime} MPa, f\u2019ci = {data.fci_prime} MPa, \u03b3c = {data.gamma_c} kN/m\u00b3", class_="data-value")),
                        air.Li(air.Strong("Method: "), air.Span(data.method.replace('_', ' ').title(), class_="data-value")),
                        air.Li(air.Strong("Material / Size: "), air.Span(f"{data.material.replace('_', ' ').upper()} \u2014 {data.strand_dia} mm", class_="data-value")),
                        air.Li(air.Strong("Tendons: "), air.Span(f"{data.num_tendons} \u00d7 {data.tendon_profile.replace('_', ' ').title()}, e = {data.eccentricity} mm", class_="data-value")),
                        air.Li(air.Strong("Jacking force: "), air.Span(f"{data.jacking_force:.1f} kN/tendon" + (" (auto)" if data.jacking_force == 0 else ""), class_="data-value")),
                        air.Li(air.Strong("Losses: "), air.Span(f"slip = {data.slip} mm, \u03bc = {data.friction_mu}, k = {data.friction_k} /m, time-dep. = {data.time_loss_mpa} MPa" + (" (auto)" if data.time_loss_mpa == 0 else ""), class_="data-value")),
                        air.Li(air.Strong("Passive rebar: "), air.Span(f"fy = {data.rebar_fy} MPa, As\u2019 = {data.rebar_as_top:.0f} mm\u00b2, As = {data.rebar_as_bot:.0f} mm\u00b2", class_="data-value")),
                        air.Li(air.Strong("Deflection: "), air.Span(f"\u03bb\u0394 = {data.long_term_multiplier}, limit = L/{data.deflection_limit:.0f}", class_="data-value")),
                    ),
                    class_="section-box"
                ),
                class_="grid-2"
            ),
            style="margin-bottom: 24px; padding-bottom: 20px; border-bottom: 2px dashed #e5e7eb;"
        ))

        # Material lookup warning banner (shown once at top of results)
        if _lookup_failed:
            result_elements.append(air.Div(
                air.Strong("⚠️ Strand/bar size not found in material database."),
                air.Span(
                    f" The entered size \"{data.strand_dia}\" was not matched for {data.material}. "
                    "Design used A416 Grade 270 12.70mm properties as fallback "
                    "(area=98.7 mm², fpu=1860 MPa, fpy=1674 MPa). "
                    "Please verify inputs."
                ),
                style="background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;"
                      "padding:12px 16px;margin-bottom:20px;color:#92400e;"
            ))

        # ── Span selector (multi-span only) ────────────────────────────────
        if len(results) > 1:
            span_options = [
                air.Option(f"Span {r.span_index + 1}", value=str(r.span_index))
                for r in results
            ]
            result_elements.append(air.Div(
                air.Label("View Results for:", style="font-weight:600; margin-right:8px;"),
                air.Select(
                    *span_options,
                    id="span_selector",
                    onchange=(
                        "(function(sel){"
                        "document.querySelectorAll('.span-result-panel')"
                        ".forEach(function(p){p.style.display='none';});"
                        "var t=document.getElementById('span-result-'+sel.value);"
                        "if(t)t.style.display='block';"
                        "})(this)"
                    ),
                    style="padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;font-size:15px;"
                ),
                style="margin-bottom:20px;display:flex;align-items:center;"
            ))

        for i, res in enumerate(results):

            notes = []
            if res.design_notes:
                notes.append(air.H4("Design Notes", style="margin-top: 16px; color: #92400e;"))
                for note in res.design_notes:
                    icon = "⚠️ " if "exceeds" in note.lower() else "ℹ️ "
                    notes.append(air.Li(f"{icon} {note}"))
                notes_element = air.Ul(*notes, class_="notes-list")
            else:
                notes_element = air.Div()

            # Schematic diagrams using simple HTML Canvas for this span Result
            canvas_id = f"res_canvas_{i}"
            res_vis_script = f"""
            (function() {{
                const cvs = document.getElementById("{canvas_id}");
                if (!cvs) return;
                const ctx = cvs.getContext("2d");
                
                const initTops = [{res.left_st_i}, {res.mid_st_i}, {res.right_st_i}];
                const initBots = [{res.left_sb_i}, {res.mid_sb_i}, {res.right_sb_i}];
                const servTops = [{res.left_st_s}, {res.mid_st_s}, {res.right_st_s}];
                const servBots = [{res.left_sb_s}, {res.mid_sb_s}, {res.right_sb_s}];
                
                const muMax = {res.Mu_max};
                const vuMax = {res.Vu};
                const df = {res.deflection_final};
                
                ctx.fillStyle = "#f8fafc";
                ctx.fillRect(0, 0, cvs.width, cvs.height);
                
                ctx.font = "11px sans-serif";
                ctx.textAlign = "center";
                
                // Helper to draw a stress profile at a specific X location
                function drawStressProfile(tops, bots, xPositions, title, labelColor, fillStyle, strokeStyle, yTop, yBot) {{
                    ctx.fillStyle = "#334155";
                    ctx.fillText(title, xPositions[1], 20);
                    
                    let maxStr = Math.max(
                        Math.max(...tops.map(Math.abs)), 
                        Math.max(...bots.map(Math.abs)), 1
                    );
                    let sc = 12 / maxStr; // ±12px max bars — prevents panel overlap at 80px x-spacing
                    
                    for(let i = 0; i < 3; i++) {{
                        let x = xPositions[i];
                        
                        // Zero-axis vertical reference line
                        ctx.beginPath();
                        ctx.moveTo(x, yTop);
                        ctx.lineTo(x, yBot);
                        ctx.strokeStyle = "#94a3b8";
                        ctx.lineWidth = 1;
                        ctx.stroke();
                        
                        // C / T legend at top of each axis (only for first profile to avoid clutter)
                        if (i === 1) {{
                            ctx.save();
                            ctx.font = "9px sans-serif";
                            ctx.fillStyle = "#64748b";
                            ctx.textAlign = "right";
                            ctx.fillText("C", x - 2, yTop + 10);
                            ctx.textAlign = "left";
                            ctx.fillText("T", x + 2, yTop + 10);
                            ctx.textAlign = "center";
                            ctx.restore();
                        }}
                        
                        // Stress shape
                        ctx.beginPath();
                        ctx.moveTo(x + tops[i]*sc, yTop);
                        ctx.lineTo(x + bots[i]*sc, yBot);
                        ctx.lineTo(x, yBot);
                        ctx.lineTo(x, yTop);
                        ctx.fillStyle = fillStyle;
                        ctx.fill();
                        ctx.strokeStyle = strokeStyle;
                        ctx.stroke();
                        
                        // Labels
                        ctx.fillStyle = labelColor;
                        ctx.fillText(tops[i].toFixed(1), x + tops[i]*sc + ((tops[i]>0)?1:-1)*8, yTop - 5);
                        ctx.fillText(bots[i].toFixed(1), x + bots[i]*sc + ((bots[i]>0)?1:-1)*8, yBot + 12);
                    }}
                }}
                
                // --- 1. Initial Stresses ---
                ctx.save();
                drawStressProfile(
                    initTops, initBots, [40, 120, 200], 
                    "Initial Stresses (L/M/R)", "#7e22ce", "rgba(168, 85, 247, 0.2)", "#9333ea", 40, 140
                );
                ctx.restore();

                // --- 2. Service Stresses ---
                ctx.save();
                drawStressProfile(
                    servTops, servBots, [240, 320, 400], 
                    "Service Stresses (L/M/R)", "#1e40af", "rgba(59, 130, 246, 0.2)", "#2563eb", 40, 140
                );
                ctx.restore();

                // --- 3. Bending Moment Diagram ---
                // Map Mu_left, Mu_mid, Mu_right
                const mLeft = {res.Mu_left};
                const mMid = {res.Mu_mid};
                const mRight = {res.Mu_right};
                let maxM = Math.max(Math.abs(mLeft), Math.abs(mMid), Math.abs(mRight), 1);
                let sfM = 35 / maxM; // Scale factor
                
                ctx.fillStyle = "#334155";
                ctx.fillText("Bending Moment (L/M/R)", 500, 20);
                
                ctx.beginPath();
                ctx.moveTo(420, 90 + mLeft*sfM);
                // Control point calculation for quadratic curve passing through mMid
                let mCp = 2 * mMid - (mLeft + mRight) / 2;
                ctx.quadraticCurveTo(500, 90 + mCp*sfM, 580, 90 + mRight*sfM);
                ctx.strokeStyle = "#16a34a"; // Green
                ctx.lineWidth = 2;
                ctx.stroke();
                
                ctx.beginPath();
                ctx.moveTo(420, 90);
                ctx.lineTo(580, 90);
                ctx.strokeStyle = "#94a3b8";
                ctx.lineWidth = 1;
                ctx.stroke();
                
                ctx.fillStyle = "#15803d";
                ctx.fillText(mLeft.toFixed(1), 420, 90 + mLeft*sfM + ((mLeft<0)?-5:12));
                ctx.fillText(mMid.toFixed(1), 500, 90 + mMid*sfM + ((mMid<0)?-5:12));
                ctx.fillText(mRight.toFixed(1), 580, 90 + mRight*sfM + ((mRight<0)?-5:12));

                // --- 4. Shear Force Diagram ---
                // Map Vu_left, Vu_mid, Vu_right
                const vLeft = {res.Vu_left};
                const vMid = {res.Vu_mid};
                const vRight = {res.Vu_right};
                let maxV = Math.max(Math.abs(vLeft), Math.abs(vMid), Math.abs(vRight), 1);
                let sfV = 35 / maxV;
                
                ctx.fillStyle = "#334155";
                ctx.fillText("Shear Force (L/M/R)", 700, 20);
                
                // Right-end shear by beam convention is -vRight (library stores upward reaction)
                const vRightConv = -vRight;
                ctx.beginPath();
                // Draw SFD: left end above axis (+), right end below axis (−) for downward loading
                ctx.moveTo(620, 90 - vLeft*sfV);
                ctx.lineTo(700, 90 - vMid*sfV);
                ctx.lineTo(780, 90 + vRight*sfV);
                
                ctx.strokeStyle = "#f59e0b"; // Orange
                ctx.lineWidth = 2;
                ctx.stroke();
                
                // Zero axis line
                ctx.beginPath();
                ctx.moveTo(620, 90);
                ctx.lineTo(780, 90);
                ctx.strokeStyle = "#94a3b8";
                ctx.lineWidth = 1;
                ctx.stroke();
                
                // Vertical lines to axis (aesthetic only)
                ctx.beginPath();
                ctx.moveTo(620, 90); ctx.lineTo(620, 90 - vLeft*sfV);
                ctx.moveTo(700, 90); ctx.lineTo(700, 90 - vMid*sfV);
                ctx.moveTo(780, 90); ctx.lineTo(780, 90 + vRight*sfV);
                ctx.strokeStyle = "#fcd34d";
                ctx.lineWidth = 1;
                ctx.setLineDash([2, 2]);
                ctx.stroke();
                ctx.setLineDash([]);
                
                ctx.fillStyle = "#b45309";
                ctx.fillText(vLeft.toFixed(1), 620, 90 - vLeft*sfV + ((vLeft>0)?-5:12));
                ctx.fillText(vMid.toFixed(1), 700, 90 - vMid*sfV + ((vMid>0)?-5:12));
                ctx.fillText(vRightConv.toFixed(1), 780, 90 + vRight*sfV + ((vRight>0)?12:-5));

                // --- 5. Deflection Trace ---
                ctx.fillStyle = "#334155";
                ctx.fillText("Deflection Trace", 900, 20);
                ctx.beginPath();
                ctx.moveTo(820, 90);
                ctx.quadraticCurveTo(900, 90 + Math.max(-50, Math.min(50, df * 2)), 980, 90); 
                ctx.strokeStyle = "#dc2626"; // Red
                ctx.lineWidth = 2;
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(820, 90);
                ctx.lineTo(980, 90);
                ctx.strokeStyle = "#94a3b8";
                ctx.lineWidth = 1;
                ctx.stroke();
                ctx.fillStyle = "#b91c1c";
                ctx.fillText("Δ = " + df.toFixed(1) + " mm", 900, 90 + Math.max(-50, Math.min(50, df * 2)) + ((df>0)?15:-5));
            }})();
            """

            result_elements.append(air.Div(
                air.H2(f"Span {res.span_index + 1} Capacity and Checks", style="color: #2563eb;"),
                air.Canvas(id=canvas_id, width=1000, height=180, style="width:100%; border: 1px solid #e2e8f0; border-radius: 4px; margin-bottom: 20px; background: #f8fafc;"),
                air.Script(res_vis_script),
                air.H4("Capacities & DCR (Left / Mid / Right)"),
                air.Ul(
                    air.Li(air.Strong("Flexure (φMn): "), air.Span(f"{res.moment_capacity:.1f} kN·m | DCR: {res.dcr_flexure_left:.2f} / {res.dcr_flexure_mid:.2f} / {res.dcr_flexure_right:.2f}", class_="data-value")),
                    air.Li(air.Strong("Shear (φVc): "), air.Span(f"{res.phi_Vn:.1f} kN | DCR: {res.dcr_shear_left:.2f} / {res.dcr_shear_mid:.2f} / {res.dcr_shear_right:.2f}", class_="data-value")),
                    air.Li(air.Strong("Torsion (φTn): "), air.Span(f"{res.phi_Tn:.1f} kN·m | DCR: {res.dcr_torsion_left:.2f} / {res.dcr_torsion_mid:.2f} / {res.dcr_torsion_right:.2f}", class_="data-value")),
                    air.Li(air.Strong("Combined Shear-Torsion: "), air.Span(f"DCR: {res.dcr_comb_left:.2f} / {res.dcr_comb_mid:.2f} / {res.dcr_comb_right:.2f}", class_="data-value")),
                    air.Li(air.Strong("Deflection (midspan) Allowable: "), air.Span(f"{res.allowable_deflection:.1f} mm | DCR (midspan): {res.dcr_deflect_mid:.2f}", class_="data-value")),
                    air.Li(air.Strong("Overall DCR"), air.Span(f"{res.utilization_ratio:.2f} {'≤' if res.utilization_ratio <= 1.0 else '>'} 1.00", class_=f"status-badge {'pass' if res.utilization_ratio <= 1.0 else 'fail'}")),
                ),
                air.H4("Stresses (Left / Mid / Right)"),
                air.Ul(
                    air.Li(air.Strong("Initial Top: "), air.Span(f"{res.left_st_i:.2f} / {res.mid_st_i:.2f} / {res.right_st_i:.2f} MPa", class_="data-value")),
                    air.Li(air.Strong("Initial Bot: "), air.Span(f"{res.left_sb_i:.2f} / {res.mid_sb_i:.2f} / {res.right_sb_i:.2f} MPa", class_="data-value")),
                    air.Li(air.Strong("Init. Comp. Limit (C): "), air.Span(
                        f"−{0.70*data.fci_prime:.2f} MPa (ends)  /  −{0.60*data.fci_prime:.2f} MPa (other)  "
                        f"[ACI T.24.5.3.1 & 24.5.3.2]",
                        class_="data-value", style="color:#7c3aed"
                    )),
                    air.Li(air.Strong("Init. Tension Limit (T): "), air.Span(
                        f"+{0.50*(data.fci_prime**0.5):.2f} MPa (ends)  /  +{0.25*(data.fci_prime**0.5):.2f} MPa (other)  "
                        f"[ACI T.24.5.3.1 & 24.5.3.2]",
                        class_="data-value", style="color:#7c3aed"
                    )),
                    air.Li(air.Strong("Service Top: "), air.Span(f"{res.left_st_s:.2f} / {res.mid_st_s:.2f} / {res.right_st_s:.2f} MPa", class_="data-value")),
                    air.Li(air.Strong("Service Bot: "), air.Span(f"{res.left_sb_s:.2f} / {res.mid_sb_s:.2f} / {res.right_sb_s:.2f} MPa", class_="data-value")),
                    air.Li(air.Strong("Svc. Comp. Limit (C): "), air.Span(
                        f"−{0.45*data.fc_prime:.2f} MPa (sustained)  /  −{0.60*data.fc_prime:.2f} MPa (total)  "
                        f"[ACI T.24.5.4.1]",
                        class_="data-value", style="color:#1d4ed8"
                    )),
                    air.Li(air.Strong("Svc. Tension Limit (T): "), air.Span(
                        f"Class U: +{0.62*(data.fc_prime**0.5):.2f} MPa  /  "
                        f"Class T: +{1.0*(data.fc_prime**0.5):.2f} MPa  "
                        f"[ACI T.24.5.4.1]",
                        class_="data-value", style="color:#1d4ed8"
                    )),
                    air.Li(air.Strong("Cracking Moment (Mcr): "), air.Span(f"{res.cracking_moment:.1f} kN·m", class_="data-value")),
                ),
                air.H4("Design Variables"),
                air.Ul(
                    air.Li(air.Strong("Max Factored Moment (Mu): "), air.Span(f"{res.Mu_max:.1f} kN·m  (φMn = {res.moment_capacity:.1f} kN·m)", class_="data-value")),
                    air.Li(air.Strong("Max Factored Shear (Vu): "), air.Span(f"{res.Vu:.1f} kN  (φVc = {res.phi_Vn:.1f} kN)", class_="data-value")),
                    air.Li(air.Strong("Initial Prestress (fpi): "), air.Span(f"{res.fpi:.1f} MPa", class_="data-value")),
                    air.Li(air.Strong("Effective Prestress (fpe): "), air.Span(f"{res.fpe:.1f} MPa", class_="data-value")),
                    air.Li(air.Strong("Stress at Flexural Strength (fps): "), air.Span(f"{res.fps:.1f} MPa", class_="data-value")),
                    air.Li(air.Strong("Total Loss Percentage: "), air.Span(f"{res.loss_total_percentage:.1f}%", class_="data-value")),
                    air.Li(air.Strong("Initial Deflection: "), air.Span(f"{res.deflection_initial:.1f} mm", class_="data-value")),
                    air.Li(air.Strong("Final Deflection: "), air.Span(f"{res.deflection_final:.1f} mm", class_="data-value")),
                ),
                notes_element,
                id=f"span-result-{i}",
                class_="span-result-panel",
                style=("margin-bottom: 32px; padding-bottom: 24px; border-bottom: 2px dashed #e5e7eb;"
                       + ("" if i == 0 else " display:none;"))
            ))

        html_content = blueprint_layout(
            air.Header(
                air.A("← Edit Design", href="/prestress-beam", class_="back-link no-print"),
                air.H1("Prestressed Beam Analysis Result"),
                air.P(f"Project: {data.proj_name}", class_="subtitle"),
                class_="module-header"
            ),
            air.Main(
                air.Div(
                    *result_elements,
                    class_="card section-box"
                )
            )
        )
        
        resp = AirResponse(content=str(html_content), media_type="text/html")
        resp.set_cookie("prestress_beam_inputs", cookie_data, max_age=2592000, httponly=True, samesite="lax")
        return resp

    @app.post("/prestress-beam/auto-design")
    async def prestress_auto_design(request: air.Request):
        import math as _math
        form_data = await request.form()
        cookie_data = json.dumps(dict(form_data))

        try:
            data = PrestressBeamModel(**form_data)
        except Exception as e:
            error_html = str(blueprint_layout(
                air.Header(
                    air.A("← Go Back", href="/prestress-beam", class_="back-link no-print"),
                    air.H1("Design Error"),
                    air.P("Form validation failed.", class_="subtitle"),
                    class_="module-header"
                ),
                air.Main(air.Div(air.H2("Invalid Inputs", style="color:#DC2626;"), air.P(str(e)), class_="card"))
            ))
            resp = AirResponse(content=error_html, media_type="text/html")
            resp.set_cookie("prestress_beam_inputs", cookie_data, max_age=2592000, httponly=True, samesite="lax")
            return resp

        designer = ACI318M25PrestressDesign()
        mat_type = PrestressMaterialType(data.material)
        method_type = PrestressingMethod(data.method)

        # ── Parse spans and loads ─────────────────────────────────────────
        try:
            spans_json = json.loads(data.spans_data)
        except Exception:
            spans_json = [{"length": 10000.0}] * data.num_spans
        try:
            loads_json = json.loads(data.loads_data)
        except Exception:
            loads_json = []

        num_spans = max(1, len(spans_json))
        spans = [SpanGeometry(
            length=float(s.get('length', 10000)),
            width=data.width, height=data.height,
            t_flange_width=data.t_flange_width,
            t_flange_height=data.t_flange_height,
        ) for s in spans_json]

        sw_kNm = data.gamma_c * (spans[0].area / 1e6)
        span_loads = [PrestressLoads(dead_load=sw_kNm, superimposed_dl=0, live_load=0) for _ in range(num_spans)]

        for ld in loads_json:
            s_idx  = max(0, min(num_spans - 1, int(ld.get('span', 1)) - 1))
            l_type = ld.get('type', 'uniform')
            dl, sdl, ll = float(ld.get('dl', 0)), float(ld.get('sdl', 0)), float(ld.get('ll', 0))
            if l_type == 'uniform':
                span_loads[s_idx].dead_load       += dl
                span_loads[s_idx].superimposed_dl += sdl
                span_loads[s_idx].live_load        += ll
            else:
                L_mm = max(1.0, spans[s_idx].length)
                L_m  = L_mm / 1000.0
                a_mm = float(ld.get('loc', 0))
                if a_mm <= 0 or a_mm >= L_mm:
                    a_mm = L_mm / 2.0
                a_m = a_mm / 1000.0
                w_factor = 8.0 * a_m * (L_m - a_m) / max(0.001, L_m ** 3)
                span_loads[s_idx].dead_load       += dl  * w_factor
                span_loads[s_idx].superimposed_dl += sdl * w_factor
                span_loads[s_idx].live_load        += ll  * w_factor

        mat_props = MaterialProperties(
            fc_prime=data.fc_prime, fy=data.rebar_fy, fu=data.rebar_fy * 1.2,
            fyt=data.rebar_fy, fut=data.rebar_fy * 1.2,
            es=200000.0, ec=designer.aci.get_concrete_modulus(data.fc_prime),
            gamma_c=data.gamma_c, description="Concrete",
        )

        try:
            supports_types = [s.get('type', 'column/wall') for s in json.loads(data.supports_data)]
        except Exception:
            supports_types = ['column/wall'] * (num_spans + 1)
        if len(supports_types) < num_spans + 1:
            supports_types += ['column/wall'] * (num_spans + 1 - len(supports_types))

        # ── Step 1: Simplified service moments for design ─────────────────
        service_moments = designer.calculate_continuous_moments(spans, span_loads)
        # Each entry: (M_left, M_mid, M_right) in kN·m (unfactored)

        # ── Step 2: Material database ──────────────────────────────────────
        mat_db = {
            PrestressMaterialType.ASTM_A416_STRAND: designer.a416_strands,
            PrestressMaterialType.ASTM_A722_BAR:    designer.a722_bars,
            PrestressMaterialType.ASTM_A421_WIRE:   designer.a421_wires,
        }.get(mat_type, designer.a416_strands)
        sorted_sizes = sorted(mat_db.items(), key=lambda x: x[1]['area'])

        mat_name = {
            PrestressMaterialType.ASTM_A416_STRAND: "ASTM A416 Grade 270 Seven-Wire Strand",
            PrestressMaterialType.ASTM_A722_BAR:    "ASTM A722 High-Strength Bar",
            PrestressMaterialType.ASTM_A421_WIRE:   "ASTM A421 Stress-Relieved Wire",
        }.get(mat_type, "Prestressing Material")

        # ── Step 3: Design eccentricity per span ──────────────────────────
        COVER = 50.0  # mm (clear cover to tendon centroid)
        fc = data.fc_prime
        f_ts = 0.62 * (fc ** 0.5)  # Class U tension limit (MPa)

        span_design = []
        P_e_per_span = []
        for i, span in enumerate(spans):
            e_max_down = max(0.0, span.yb - COVER)   # max eccentricity below centroid
            e_max_up   = max(0.0, span.yt - COVER)   # max eccentricity above centroid
            e_mid = e_max_down                         # maximise efficiency at midspan

            def _e_at_support(M_kNm, is_end_span):
                if is_end_span or abs(M_kNm) < 1.0:
                    return 0.0
                return -e_max_up   # interior continuous support → tendon above centroid

            is_left_end  = (i == 0)
            is_right_end = (i == num_spans - 1)
            e_left  = _e_at_support(service_moments[i][0], is_left_end)
            e_right = _e_at_support(service_moments[i][2], is_right_end)

            if data.tendon_profile == 'straight':
                e_left = e_right = e_mid   # constant for straight tendons

            span_design.append({'e_left': e_left, 'e_mid': e_mid, 'e_right': e_right})

            # Min P_e from Class-U bottom-fiber service tension limit at midspan
            A_g, I_g = span.area, span.moment_of_inertia
            y_b = span.yb
            M_s = max(abs(service_moments[i][0]),
                      abs(service_moments[i][1]),
                      abs(service_moments[i][2])) * 1e6   # N·mm
            coeff = 1.0 / A_g + e_mid * y_b / I_g
            rhs   = M_s * y_b / I_g - f_ts           # MPa → if negative, no tension issue
            P_e_stress = max(0.0, rhs / coeff) if coeff > 0 else 0.0  # N

            # Balance load: at least 70 % of DL moment
            w_dl = span_loads[i].dead_load
            L_m  = span.length / 1000.0
            M_dl = w_dl * L_m ** 2 / 8.0 * 1e6   # N·mm (simply-supported approx)
            P_e_balance = 0.70 * M_dl / e_mid if e_mid > 0 else 0.0  # N

            P_e_per_span.append(max(P_e_stress, P_e_balance))

        P_e_required = max(P_e_per_span) if P_e_per_span else 0.0  # N

        # ── Step 4: Select strand diameter and count ───────────────────────
        # Estimate effective prestress at 60 % of fpu (conservative after losses)
        selected_dia_key = selected_n = selected_prop = None
        for dia_key, prop in sorted_sizes:
            f_pe_est = 0.60 * prop['fpu']
            n = max(1, _math.ceil(P_e_required / max(1.0, f_pe_est * prop['area'])))
            if n <= 60:
                selected_dia_key, selected_n, selected_prop = dia_key, n, prop
                break
        if selected_dia_key is None:   # fallback: largest size
            dia_key, prop = sorted_sizes[-1]
            f_pe_est = 0.60 * prop['fpu']
            selected_dia_key = dia_key
            selected_n  = max(1, _math.ceil(P_e_required / max(1.0, f_pe_est * prop['area'])))
            selected_prop = prop

        # ── Step 5: Jacking force ─────────────────────────────────────────
        fpj_limit, fpi_limit = designer.get_tendon_stress_limits(
            selected_prop['fpu'], selected_prop['fpy'], method_type
        )
        F_jack_per_tendon = fpi_limit * selected_prop['area'] / 1000.0   # kN/tendon
        F_jack_total      = F_jack_per_tendon * selected_n                # kN total

        # ── Step 6: Full analysis with designed tendon ────────────────────
        e_design = span_design[0]['e_mid']   # single eccentricity for the solver
        tendon = PrestressTendon(
            material_type=mat_type,
            diameter=selected_prop['diameter'],
            area=selected_prop['area'],
            fpu=selected_prop['fpu'],
            fpy=selected_prop['fpy'],
            number_of_tendons=selected_n,
            eccentricity=e_design,
            slip=data.slip,
            friction_mu=data.friction_mu,
            friction_k=data.friction_k,
            jacking_force=F_jack_per_tendon,
            time_loss_mpa=data.time_loss_mpa,
        )

        analysis_results = designer.run_continuous_analysis(
            spans=spans, span_loads=span_loads,
            supports_types=supports_types, tendon=tendon,
            mat_props=mat_props, fci_prime=data.fci_prime,
            method=method_type, member_type=PrestressMemberType.BEAM,
            tendon_profile=data.tendon_profile,
            rebar_as_bot=0.0, rebar_as_top=0.0, rebar_fy=data.rebar_fy,
            long_term_multiplier=data.long_term_multiplier,
            deflection_limit=data.deflection_limit,
        )

        # ── Step 7: Supplemental rebar requirements ────────────────────────
        COVER_REBAR = 50.0
        rebar_reqs   = []
        stirrup_reqs = []

        for res in analysis_results:
            i    = res.span_index
            span = spans[i]
            d_flex  = span.height - COVER_REBAR
            d_shear = max(0.8 * span.height, span.yt + e_design)
            Vc      = res.phi_Vn / 0.75   # kN

            # Positive moment → bottom bars
            Mu_pos = max(0.0, res.Mu_mid,
                         res.Mu_left  if res.Mu_left  > 0 else 0.0,
                         res.Mu_right if res.Mu_right > 0 else 0.0)
            As_bot = 0.0
            if res.moment_capacity < Mu_pos:
                delta_Mu = (Mu_pos - res.moment_capacity) * 1e6   # N·mm
                As_bot = delta_Mu / (0.9 * data.rebar_fy * 0.85 * d_flex)

            # Negative moment → top bars
            Mu_neg = max(0.0,
                         -res.Mu_left  if res.Mu_left  < 0 else 0.0,
                         -res.Mu_right if res.Mu_right < 0 else 0.0)
            As_top = 0.0
            if res.moment_capacity < Mu_neg:
                delta_Mu_neg = (Mu_neg - res.moment_capacity) * 1e6
                As_top = delta_Mu_neg / (0.9 * data.rebar_fy * 0.85 * d_flex)

            rebar_reqs.append({
                'span': i + 1, 'As_bot': As_bot, 'As_top': As_top,
                'Mu_pos': Mu_pos, 'Mu_neg': Mu_neg, 'phi_Mn': res.moment_capacity,
            })

            # Shear → stirrups  (ACI minimum Av/s if any stirrups are needed)
            Vs_req    = 0.0
            Av_per_m  = 0.0
            if res.phi_Vn < res.Vu:
                Vs_req   = max(0.0, res.Vu / 0.75 - Vc)     # kN
                dv       = 0.9 * d_shear                       # mm
                Av_s     = Vs_req * 1000.0 / (data.rebar_fy * dv)  # mm²/mm
                Av_per_m = Av_s * 1000.0                       # mm²/m

            stirrup_reqs.append({
                'span': i + 1, 'Vs_req': Vs_req, 'Av_per_m': Av_per_m,
                'phi_Vn': res.phi_Vn, 'Vu': res.Vu,
            })

        # ── Build HTML results ────────────────────────────────────────────
        A_ps_total = selected_prop['area'] * selected_n

        def _ok_cell(val, unit="mm²"):
            if val > 0:
                return air.Td(f"{val:.0f} {unit}",
                              style="padding:8px;text-align:center;color:#dc2626;font-weight:600;")
            return air.Td("OK", style="padding:8px;text-align:center;color:#16a34a;")

        # Section 1 – Strand selection
        s1 = air.Div(
            air.H2("1. Strand Selection"),
            air.Ul(
                air.Li(air.Strong("Material: "),
                       air.Span(mat_name, class_="data-value")),
                air.Li(air.Strong("Recommended Diameter: "),
                       air.Span(f"{selected_prop['diameter']} mm  ({selected_prop.get('description', '')})",
                                class_="data-value")),
                air.Li(air.Strong("Number of Strands/Bars: "),
                       air.Span(str(selected_n), class_="data-value")),
                air.Li(air.Strong("Area per strand: "),
                       air.Span(f"{selected_prop['area']:.1f} mm²", class_="data-value")),
                air.Li(air.Strong("Total Aps: "),
                       air.Span(f"{selected_n} × {selected_prop['area']:.1f} = {A_ps_total:.1f} mm²",
                                class_="data-value")),
                air.Li(air.Strong("fpu / fpy: "),
                       air.Span(f"{selected_prop['fpu']:.0f} MPa  /  {selected_prop['fpy']:.0f} MPa",
                                class_="data-value")),
                air.Li(air.Strong("Required Pe (estimated): "),
                       air.Span(f"{P_e_required/1000:.1f} kN", class_="data-value")),
            ),
            style="margin-bottom:24px;padding-bottom:20px;border-bottom:2px dashed #e5e7eb;"
        )

        # Section 2 – Jacking force
        s2 = air.Div(
            air.H2("2. Initial Jacking Force"),
            air.Ul(
                air.Li(air.Strong("Jacking stress limit (ACI Table 20.3.2.5.1): "),
                       air.Span(f"fpj = {fpj_limit:.1f} MPa", class_="data-value")),
                air.Li(air.Strong("Transfer stress limit (ACI Table 20.3.2.5.1): "),
                       air.Span(f"fpi = {fpi_limit:.1f} MPa", class_="data-value")),
                air.Li(air.Strong("Jacking force per tendon: "),
                       air.Span(f"F_jack = fpi × Ap = {fpi_limit:.1f} × {selected_prop['area']:.1f} / 1000"
                                f" = {F_jack_per_tendon:.1f} kN/tendon", class_="data-value")),
                air.Li(air.Strong("Total initial jacking force: "),
                       air.Span(f"{selected_n} × {F_jack_per_tendon:.1f} = {F_jack_total:.1f} kN",
                                class_="data-value")),
            ),
            style="margin-bottom:24px;padding-bottom:20px;border-bottom:2px dashed #e5e7eb;"
        )

        # Section 3 – Eccentricity profile
        profile_note_map = {
            'straight':       "Constant (straight tendon)",
            'parabolic':      "Parabolic – varies from support to midspan",
            'harped':         "Harped – linear from end to harp point",
            'multiple_harped':"Multiple harped",
        }
        profile_note = profile_note_map.get(data.tendon_profile, data.tendon_profile)

        ecc_rows = []
        for i, sdd in enumerate(span_design):
            def _fmt(v):
                return f"+{v:.1f}" if v >= 0 else f"{v:.1f}"
            ecc_rows.append(air.Tr(
                air.Td(f"Span {i+1}", style="padding:8px;"),
                air.Td(_fmt(sdd['e_left'])  + " mm", style="padding:8px;text-align:center;"),
                air.Td(_fmt(sdd['e_mid'])   + " mm", style="padding:8px;text-align:center;font-weight:600;"),
                air.Td(_fmt(sdd['e_right']) + " mm", style="padding:8px;text-align:center;"),
                style="border-bottom:1px solid #e2e8f0;"
            ))

        s3 = air.Div(
            air.H2("3. Tendon Eccentricity Profile"),
            air.P(f"Profile: {profile_note}  |  Positive = below centroid, Negative = above centroid.",
                  style="color:#64748b;font-size:14px;margin-bottom:8px;"),
            air.Table(
                air.Thead(air.Tr(
                    air.Th("Span", style="padding:8px;text-align:left;border-bottom:2px solid #94a3b8;"),
                    air.Th("Left Support", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                    air.Th("Midspan (design e)", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                    air.Th("Right Support", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                )),
                air.Tbody(*ecc_rows),
                style="width:100%;border-collapse:collapse;"
            ),
            style="margin-bottom:24px;padding-bottom:20px;border-bottom:2px dashed #e5e7eb;"
        )

        # Section 4 – Supplemental reinforcement
        any_rebar = any(r['As_bot'] > 0 or r['As_top'] > 0 for r in rebar_reqs)
        any_stirrup = any(s['Av_per_m'] > 0 for s in stirrup_reqs)
        rebar_rows = []
        for req, stirrup in zip(rebar_reqs, stirrup_reqs):
            stirrup_cell = (
                air.Td(f"{stirrup['Av_per_m']:.0f} mm²/m  (Vs = {stirrup['Vs_req']:.1f} kN)",
                       style="padding:8px;text-align:center;color:#dc2626;font-weight:600;")
                if stirrup['Av_per_m'] > 0
                else air.Td(f"OK  (φVn = {stirrup['phi_Vn']:.1f} ≥ Vu = {stirrup['Vu']:.1f} kN)",
                            style="padding:8px;text-align:center;color:#16a34a;")
            )
            rebar_rows.append(air.Tr(
                air.Td(f"Span {req['span']}", style="padding:8px;"),
                _ok_cell(req['As_bot']),
                _ok_cell(req['As_top']),
                stirrup_cell,
                style="border-bottom:1px solid #e2e8f0;"
            ))

        banner_msg = ("✓ Prestress alone is sufficient — no supplemental reinforcement required."
                      if not (any_rebar or any_stirrup)
                      else "⚠ Supplemental mild steel required where prestress is insufficient for strength.")
        banner_color = "#16a34a" if not (any_rebar or any_stirrup) else "#dc2626"

        s4 = air.Div(
            air.H2("4. Supplemental Reinforcement Requirements"),
            air.P(banner_msg, style=f"color:{banner_color};font-weight:600;margin-bottom:8px;"),
            air.Table(
                air.Thead(air.Tr(
                    air.Th("Span", style="padding:8px;text-align:left;border-bottom:2px solid #94a3b8;"),
                    air.Th("Bottom Bars  As (mm²)", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                    air.Th("Top Bars  As' (mm²)", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                    air.Th("Stirrups  Av (mm²/m)", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                )),
                air.Tbody(*rebar_rows),
                style="width:100%;border-collapse:collapse;"
            ),
            style="margin-bottom:24px;padding-bottom:20px;border-bottom:2px dashed #e5e7eb;"
        )

        # Section 5 – Verification DCR table
        dcr_rows = []
        for res in analysis_results:
            ok = res.utilization_ratio <= 1.0
            dcr_rows.append(air.Tr(
                air.Td(f"Span {res.span_index + 1}", style="padding:8px;"),
                air.Td(f"{res.dcr_flexure_mid:.2f}", style="padding:8px;text-align:center;"),
                air.Td(f"{max(res.dcr_shear_left, res.dcr_shear_mid, res.dcr_shear_right):.2f}",
                       style="padding:8px;text-align:center;"),
                air.Td(f"{res.dcr_deflect_mid:.2f}", style="padding:8px;text-align:center;"),
                air.Td(f"{res.utilization_ratio:.2f}",
                       style=f"padding:8px;text-align:center;font-weight:600;"
                             f"color:{'#16a34a' if ok else '#dc2626'};"),
                air.Td("✓ PASS" if ok else "✗ EXCEEDS",
                       style=f"padding:8px;text-align:center;font-weight:600;"
                             f"color:{'#16a34a' if ok else '#dc2626'};"),
                style="border-bottom:1px solid #e2e8f0;"
            ))

        s5 = air.Div(
            air.H2("5. Verification Analysis (with Designed Parameters)"),
            air.P(f"Tendon used for verification: {selected_n} × {selected_prop['diameter']} mm  "
                  f"({mat_name}),  e = {e_design:.1f} mm,  "
                  f"F_jack = {F_jack_per_tendon:.1f} kN/tendon.",
                  style="color:#64748b;font-size:14px;margin-bottom:8px;"),
            air.Table(
                air.Thead(air.Tr(
                    air.Th("Span", style="padding:8px;text-align:left;border-bottom:2px solid #94a3b8;"),
                    air.Th("DCR Flexure (mid)", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                    air.Th("DCR Shear (max)", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                    air.Th("DCR Deflection", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                    air.Th("Max DCR", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                    air.Th("Status", style="padding:8px;text-align:center;border-bottom:2px solid #94a3b8;"),
                )),
                air.Tbody(*dcr_rows),
                style="width:100%;border-collapse:collapse;"
            ),
        )

        html_content = blueprint_layout(
            air.Header(
                air.A("← Edit Design", href="/prestress-beam", class_="back-link no-print"),
                air.H1("Prestressed Beam — Auto Design"),
                air.P(f"Project: {data.proj_name}", class_="subtitle"),
                class_="module-header"
            ),
            air.Main(air.Div(s1, s2, s3, s4, s5, class_="card section-box"))
        )

        resp = AirResponse(content=str(html_content), media_type="text/html")
        resp.set_cookie("prestress_beam_inputs", cookie_data, max_age=2592000, httponly=True, samesite="lax")
        return resp

    @app.get("/prestress-beam/pdf")
    async def prestress_beam_pdf_export(request: air.Request):
        cookie_inputs = request.cookies.get("prestress_beam_inputs")
        if not cookie_inputs:
            return AirResponse(
                content="No saved design found. Please run an analysis first.",
                status_code=400,
            )
        try:
            data = PrestressBeamModel(**json.loads(cookie_inputs))

            designer = ACI318M25PrestressDesign()
            mat_type    = PrestressMaterialType(data.material)
            method_type = PrestressingMethod(data.method)
            prop = designer.get_prestress_material(mat_type, data.strand_dia)
            if not prop:
                prop = {
                    'diameter': float(data.strand_dia) if data.strand_dia.replace('.', '', 1).isdigit() else 12.7,
                    'area': 98.7, 'fpu': 1860, 'fpy': 1674,
                    'description': 'Custom (A416 12.70mm fallback)'
                }

            tendon = PrestressTendon(
                material_type=mat_type,
                diameter=prop['diameter'], area=prop['area'],
                fpu=prop['fpu'], fpy=prop['fpy'],
                number_of_tendons=data.num_tendons,
                eccentricity=data.eccentricity,
                slip=data.slip, friction_mu=data.friction_mu,
                friction_k=data.friction_k,
                jacking_force=data.jacking_force,
                time_loss_mpa=data.time_loss_mpa,
            )

            try:
                spans_json = json.loads(data.spans_data)
            except Exception:
                spans_json = [{"length": 10000.0}] * data.num_spans
            try:
                loads_json = json.loads(data.loads_data)
            except Exception:
                loads_json = []

            num_spans = max(1, len(spans_json))
            spans = [
                SpanGeometry(
                    length=float(s.get('length', 10000)),
                    width=data.width, height=data.height,
                    t_flange_width=data.t_flange_width,
                    t_flange_height=data.t_flange_height,
                )
                for s in spans_json
            ]

            sw_kNm = data.gamma_c * (spans[0].area / 1e6) if spans else data.gamma_c * (data.width * data.height / 1e6)
            span_loads = [PrestressLoads(dead_load=sw_kNm, superimposed_dl=0, live_load=0) for _ in range(num_spans)]

            for ld in loads_json:
                s_idx  = max(0, min(num_spans - 1, int(ld.get('span', 1)) - 1))
                l_type = ld.get('type', 'uniform')
                dl, sdl, ll = float(ld.get('dl', 0)), float(ld.get('sdl', 0)), float(ld.get('ll', 0))
                if l_type == 'uniform':
                    span_loads[s_idx].dead_load       += dl
                    span_loads[s_idx].superimposed_dl += sdl
                    span_loads[s_idx].live_load        += ll
                else:
                    L_mm = max(1.0, spans[s_idx].length)
                    L_m  = L_mm / 1000.0
                    a_mm = float(ld.get('loc', 0))
                    if a_mm <= 0 or a_mm >= L_mm:
                        a_mm = L_mm / 2.0
                    a_m = a_mm / 1000.0
                    w_factor = 8.0 * a_m * (L_m - a_m) / max(0.001, L_m ** 3)
                    span_loads[s_idx].dead_load       += dl  * w_factor
                    span_loads[s_idx].superimposed_dl += sdl * w_factor
                    span_loads[s_idx].live_load        += ll  * w_factor

            mat_props = MaterialProperties(
                fc_prime=data.fc_prime, fy=data.rebar_fy, fu=data.rebar_fy * 1.2,
                fyt=data.rebar_fy, fut=data.rebar_fy * 1.2,
                es=200000.0, ec=designer.aci.get_concrete_modulus(data.fc_prime),
                gamma_c=data.gamma_c, description="Concrete",
            )

            try:
                supports_types = [s.get('type', 'column/wall') for s in json.loads(data.supports_data)]
            except Exception:
                supports_types = ['column/wall'] * (num_spans + 1)
            if len(supports_types) < num_spans + 1:
                supports_types += ['column/wall'] * (num_spans + 1 - len(supports_types))

            results = designer.run_continuous_analysis(
                spans=spans, span_loads=span_loads,
                supports_types=supports_types, tendon=tendon,
                mat_props=mat_props, fci_prime=data.fci_prime,
                method=method_type, member_type=PrestressMemberType.BEAM,
                tendon_profile=data.tendon_profile,
                rebar_as_bot=data.rebar_as_bot, rebar_as_top=data.rebar_as_top,
                rebar_fy=data.rebar_fy,
                long_term_multiplier=data.long_term_multiplier,
                deflection_limit=data.deflection_limit,
            )

            pdf_bytes = generate_prestress_beam_report(data, results)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": 'attachment; filename="prestress_beam_report.pdf"'},
            )
        except Exception as e:
            return AirResponse(content=f"Error generating PDF: {str(e)}", status_code=500)
