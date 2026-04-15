import math
import os
import re
import tempfile
from pylatex import (
    Document,
    Section,
    Subsection,
    Math,
    Command,
    NoEscape,
    PageStyle,
    Head,
    Foot,
    Tabular,
    Figure,
    Itemize,
)
from pylatex.utils import bold
from aci318m25 import ACI318M25

aci_tool = ACI318M25()


def draw_footing_plan_tikz(
    L, B, cw, cd, ecc_x, ecc_y, bottom_x, bottom_y, top_x, top_y
):
    """Generate TikZ code for footing plan."""
    s = 4.0 / max(L, B)
    Lv, Bv = L * s, B * s
    cx, cy = ecc_x * s, ecc_y * s
    cw_v, cd_v = cw * s, cd * s

    tikz = [
        r"\begin{tikzpicture}[scale=1.0]",
        rf"\draw[line width=1.5pt] (0,0) rectangle ({Lv},{Bv});",  # Footing
        rf"\draw[line width=0.8pt, dashed, red] ({cx - cw_v / 2},{cy - cd_v / 2}) rectangle ({cx + cw_v / 2},{cy + cd_v / 2});",  # Column
    ]

    # Bottom bars X-direction (horizontal)
    if bottom_y > 0:
        for j in range(bottom_y):
            y = Bv * 0.15 + j * (Bv * 0.7 / max(bottom_y - 1, 1))
            tikz.append(
                rf"\draw[blue, line width=0.6pt] (0.2,{y}) -- ({Lv - 0.2},{y});"
            )

    # Bottom bars Y-direction (vertical)
    if bottom_x > 0:
        for i in range(bottom_x):
            x = Lv * 0.15 + i * (Lv * 0.7 / max(bottom_x - 1, 1))
            tikz.append(
                rf"\draw[blue, line width=0.6pt] ({x},{0.2}) -- ({x},{Bv - 0.2});"
            )

    # Dimensions
    tikz.append(
        rf"\draw[<->] (0, {Bv + 0.4}) -- ({Lv}, {Bv + 0.4}) node[midway, above] {{{L:.0f} mm}};"
    )
    tikz.append(
        rf"\draw[<->] ({-0.4}, 0) -- ({-0.4}, {Bv}) node[midway, left] {{{B:.0f} mm}};"
    )

    tikz.append(r"\end{tikzpicture}")
    return "\n".join(tikz)


def generate_footing_report(data, mat, geom, loads, res):
    """Generate a PDF report for the footing design.

    Parameters
    ----------
    data: FootingDesignModel (the Air input model)
    mat: MaterialProperties
    geom: FootingGeometry
    loads: FootingLoads (factored loads)
    res: FootingAnalysisResult

    Returns
    -------
    bytes of the generated PDF.
    """
    geometry_options = {"margin": "1in", "headheight": "38pt", "includeheadfoot": True}
    doc = Document(geometry_options=geometry_options)

    doc.preamble.append(NoEscape(r"\usepackage{amsmath}"))
    doc.preamble.append(NoEscape(r"\usepackage{tikz}"))

    # Header / Footer
    header = PageStyle("header")
    with header.create(Head("C")):
        with header.create(Tabular("|p{8cm}|p{8cm}|")) as table:
            table.add_hline()
            table.add_row(
                (
                    NoEscape(rf"\textbf{{Project:}} {data.proj_name}"),
                    NoEscape(rf"\textbf{{Engineer:}} {data.proj_eng}"),
                )
            )
            table.add_hline()
            table.add_row(
                (
                    NoEscape(rf"\textbf{{Location:}} {data.proj_loc}"),
                    NoEscape(rf"\textbf{{Date:}} {data.proj_date}"),
                )
            )
            table.add_hline()
    with header.create(Foot("C")):
        header.append(Command("thepage"))
    doc.preamble.append(header)
    doc.change_document_style("header")

    doc.append(NoEscape(r"\vspace*{1em}"))
    doc.append(Command("begin", "center"))
    doc.append(Command("huge", bold("RC Isolated Footing Design Report")))
    doc.append(Command("end", "center"))
    doc.append(NoEscape(r"\vspace*{1em}"))

    # --- Section 1: Material & Geometry ---
    with doc.create(Section("Material & Geometry")):
        with doc.create(Itemize()) as itemize:
            itemize.add_item(
                NoEscape(rf"Concrete $f'_c = {data.fc_prime}\,\text{{MPa}}$")
            )
            itemize.add_item(NoEscape(rf"Rebar $f_y = {data.fy}\,\text{{MPa}}$"))
            itemize.add_item(NoEscape(rf"Clear cover $= {data.cover}\,\text{{mm}}$"))
            itemize.add_item(
                NoEscape(
                    rf"Footing $L = {data.length}\,\text{{mm}}$, $B = {data.width}\,\text{{mm}}$, $h = {data.thickness}\,\text{{mm}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Column $c_w = {data.col_w}\,\text{{mm}}$, $c_d = {data.col_d}\,\text{{mm}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Eccentricity $e_x = {data.ecc_x}\,\text{{mm}}$, $e_y = {data.ecc_y}\,\text{{mm}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Soil $q_a = {data.soil_qa}\,\text{{kPa}}$, $k_s = {data.soil_ks}\,\text{{kN/m}}^3$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Soil unit weight $\gamma = {data.soil_unit_weight}\,\text{{kN/m}}^3$, $\phi = {data.soil_friction_angle}^\circ$"
                )
            )

    # --- Section 2: Loads ---
    with doc.create(Section("Applied Loads")):
        with doc.create(Subsection("Factored (Ultimate) Loads")):
            with doc.create(Itemize()) as itemize:
                itemize.add_item(NoEscape(rf"$P_u = {data.pu_ult}\,\text{{kN}}$"))
                itemize.add_item(
                    NoEscape(
                        rf"$M_{{ux}} = {data.mux_ult}\,\text{{kN-m}}$, $M_{{uy}} = {data.muy_ult}\,\text{{kN-m}}$"
                    )
                )

        with doc.create(Subsection("Service Loads")):
            with doc.create(Itemize()) as itemize:
                itemize.add_item(NoEscape(rf"$P_s = {data.pu_srv}\,\text{{kN}}$"))
                itemize.add_item(
                    NoEscape(
                        rf"$M_{{sx}} = {data.mux_srv}\,\text{{kN-m}}$, $M_{{sy}} = {data.muy_srv}\,\text{{kN-m}}$"
                    )
                )
                if data.surcharge_dl or data.surcharge_ll:
                    itemize.add_item(
                        NoEscape(
                            rf"Surcharge $w_s = {data.surcharge_dl + data.surcharge_ll}\,\text{{kPa}}$"
                        )
                    )

    # --- Section 3: Soil Bearing Pressure ---
    with doc.create(Section("Soil Bearing Pressure Check")):
        # Compute net allowable
        soil_overburden = data.soil_unit_weight * (data.soil_depth / 1000.0)
        surcharge_total = data.surcharge_dl + data.surcharge_ll
        net_qa = data.soil_qa - soil_overburden - surcharge_total
        gross_limit = data.soil_qa * 1.33 if data.transient_loads else data.soil_qa
        net_limit = net_qa * 1.33 if data.transient_loads else net_qa

        doc.append(bold("Net allowable bearing:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"q_{{a,net}} = q_a - \gamma D - w_s = {data.soil_qa:.0f} - {data.soil_unit_weight:.1f}\times{data.soil_depth / 1000:.3f} - {surcharge_total:.1f} = {net_qa:.1f}\,\text{{kPa}}"
                    )
                ]
            )
        )

        doc.append(Math(data=[NoEscape(rf"q_{{a,net}} = {net_qa:.1f}\,\text{{kPa}}")]))

        if data.transient_loads:
            doc.append(
                NoEscape(rf"Transient case: limit $\times 1.33 = {net_limit:.1f}$ kPa")
            )

        doc.append(bold("Maximum pressure from FEA:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"q_{{max}} = {res.bearing_pressure_max:.1f}\,\text{{kPa}}"
                    )
                ]
            )
        )
        doc.append(bold("Minimum pressure from FEA:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"q_{{min}} = {res.bearing_pressure_min:.1f}\,\text{{kPa}}"
                    )
                ]
            )
        )

        # Check status
        qmax_net = res.bearing_pressure_max - soil_overburden - surcharge_total
        net_ok = qmax_net <= net_limit

        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"q_{{max,net}} = q_{{max}} - \gamma D - w_s = {res.bearing_pressure_max:.1f} - {soil_overburden:.1f} - {surcharge_total:.1f} = {qmax_net:.1f}\,\text{{kPa}}"
                    )
                ]
            )
        )

        status = "PASS" if net_ok else "FAIL"
        doc.append(
            bold(
                rf"Bearing check: $q_{{max,net}} = {qmax_net:.1f} \leq {net_limit:.1f}$ kPa  \textbf{{{status}}}"
            )
        )

    # --- Section 4: One-Way Shear ---
    with doc.create(Section("One-Way Shear Check (ACI 318M-25)")):
        # Compute effective depth
        # d_eff = thickness - cover - db/2 per the changes
        db_bot = aci_tool.get_bar_diameter(data.bottom_bar_size)
        d_eff = data.thickness - data.cover - db_bot / 2.0

        doc.append(bold("Effective depth (bottom):"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"d = h - c - d_b/2 = {data.thickness} - {data.cover} - {db_bot}/2 = {d_eff:.1f}\,\text{{mm}}"
                    )
                ]
            )
        )

        # Shear capacity from concrete
        phi_v = 0.75
        vc = 0.17 * math.sqrt(data.fc_prime)  # MPa
        phi_vc = phi_v * vc * 1000 * d_eff / 1000  # kN/m

        doc.append(bold("Concrete shear capacity:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"\phi V_c = \phi (0.17 \sqrt{{f'_c}}) b d = 0.75 \times 0.17 \times \sqrt{{{data.fc_prime}}} \times 1000 \times {d_eff:.1f} / 1000 = {phi_vc:.1f}\,\text{{kN/m}}"
                    )
                ]
            )
        )

        # Show demand from FEA
        shear_demand = res.one_way_shear_demand
        shear_capacity = res.one_way_shear_capacity
        shear_ratio = shear_demand / shear_capacity if shear_capacity > 0 else 999
        shear_ok = shear_ratio <= 1.0

        doc.append(bold("Shear demand from FEA:"))
        doc.append(Math(data=[NoEscape(rf"V_u = {shear_demand:.1f}\,\text{{kN/m}}")]))
        doc.append(bold("Check:"))
        status = "PASS" if shear_ok else "FAIL"
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"DCR = V_u / \phi V_c = {shear_demand:.1f} / {shear_capacity:.1f} = {shear_ratio:.2f} \quad \textbf{{{status}}}"
                    )
                ]
            )
        )

    # --- Section 5: Two-Way (Punching) Shear ---
    with doc.create(Section("Two-Way (Punching) Shear Check")):
        # Critical perimeter
        c1 = data.col_w
        c2 = data.col_d
        b1 = c1 + d_eff
        b2 = c2 + d_eff
        bo = 2 * b1 + 2 * b2

        doc.append(bold("Critical perimeter:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"b_o = 2(c_1 + d) + 2(c_2 + d) = 2({c1:.0f} + {d_eff:.1f}) + 2({c2:.0f} + {d_eff:.1f}) = {bo:.0f}\,\text{{mm}}"
                    )
                ]
            )
        )

        # Shear demand
        Vu = res.two_way_shear_demand  # kN
        # Shear capacity from concrete
        beta = max(c1, c2) / min(c1, c2)
        alphas = 40  # interior column
        vc1 = 0.17 * (1 + 2 / beta) * math.sqrt(data.fc_prime)
        vc2 = 0.083 * (alphas * d_eff / bo + 2) * math.sqrt(data.fc_prime)
        vc3 = 0.33 * math.sqrt(data.fc_prime)
        vc = min(vc1, vc2, vc3)
        phi_vc = phi_v * vc
        phi_Vn = phi_vc * bo * d_eff / 1000  # kN
        two_way_ratio = Vu / phi_Vn if phi_Vn > 0 else 999
        two_way_ok = two_way_ratio <= 1.0

        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"v_c = \min(0.17(1+2/\beta)\sqrt{{f'_c}}, 0.083(\alpha_s d/b_o+2)\sqrt{{f'_c}}, 0.33\sqrt{{f'_c}}) = {vc:.3f}\,\text{{MPa}}"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"\phi V_n = \phi v_c b_o d / 1000 = {phi_vc:.3f} \times {bo:.0f} \times {d_eff:.1f} / 1000 = {phi_Vn:.1f}\,\text{{kN}}"
                    )
                ]
            )
        )

        status = "PASS" if two_way_ok else "FAIL"
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"V_u = {Vu:.1f}\,\text{{kN}}, \phi V_n = {phi_Vn:.1f}\,\text{{kN}}, DCR = {two_way_ratio:.2f} \quad \textbf{{{status}}}"
                    )
                ]
            )
        )

    # --- Section 6: Flexural Reinforcement ---
    with doc.create(Section("Flexural Reinforcement Design")):
        # Bottom reinforcement
        rho_min = 0.0018
        As_min = rho_min * 1000 * data.thickness

        doc.append(bold("Minimum reinforcement:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"A_{{s,min}} = 0.0018 b h = 0.0018 \times 1000 \times {data.thickness} = {As_min:.0f}\,\text{{mm}}^2/\text{{m}}"
                    )
                ]
            )
        )

        # Bottom X
        M_x = res.fea_moment_x_pos
        As_req_x = (
            phi_v * data.fy * d_eff
            - math.sqrt(
                (phi_v * data.fy * d_eff) ** 2
                - 4
                * (phi_v * data.fy**2 / (2 * 0.85 * data.fc_prime * 1000))
                * M_x
                * 1e6
            )
        ) / (2 * phi_v * data.fy**2 / (2 * 0.85 * data.fc_prime * 1000))
        if As_req_x < As_min:
            As_req_x = As_min
        bx = data.bottom_bar_size
        sx = res.reinforcement.bottom_spacing_x
        As_prov_x = aci_tool.get_bar_area(bx) * 1000 / sx

        doc.append(bold("Bottom X-direction:"))
        doc.append(Math(data=[NoEscape(rf"M_u = {M_x:.2f}\,\text{{kN-m}}")]))
        doc.append(
            Math(
                data=[
                    NoEscape(rf"A_{{s,req}} = {As_req_x:.1f}\,\text{{mm}}^2/\text{{m}}")
                ]
            )
        )
        doc.append(
            NoEscape(rf"Provided: {bx} @ {sx:.0f} mm ($A_s$ = {As_prov_x:.1f} mm²/m)")
        )

        # Bottom Y
        M_y = res.fea_moment_y_pos
        As_req_y = (
            phi_v * data.fy * d_eff
            - math.sqrt(
                (phi_v * data.fy * d_eff) ** 2
                - 4
                * (phi_v * data.fy**2 / (2 * 0.85 * data.fc_prime * 1000))
                * M_y
                * 1e6
            )
        ) / (2 * phi_v * data.fy**2 / (2 * 0.85 * data.fc_prime * 1000))
        if As_req_y < As_min:
            As_req_y = As_min
        by = data.bottom_bar_size
        sy = res.reinforcement.bottom_spacing_y
        As_prov_y = aci_tool.get_bar_area(by) * 1000 / sy

        doc.append(bold("Bottom Y-direction:"))
        doc.append(Math(data=[NoEscape(rf"M_u = {M_y:.2f}\,\text{{kN-m}}")]))
        doc.append(
            Math(
                data=[
                    NoEscape(rf"A_{{s,req}} = {As_req_y:.1f}\,\text{{mm}}^2/\text{{m}}")
                ]
            )
        )
        doc.append(
            NoEscape(rf"Provided: {by} @ {sy:.0f} mm ($A_s$ = {As_prov_y:.1f} mm²/m)")
        )

        # Top reinforcement (if any)
        if res.reinforcement.top_bars_x:
            doc.append(bold("Top reinforcement:"))
            doc.append(
                NoEscape(
                    rf"Top X: {res.reinforcement.top_bars_x} @ {res.reinforcement.top_spacing_x:.0f} mm"
                )
            )
            doc.append(
                NoEscape(
                    rf"Top Y: {res.reinforcement.top_bars_y} @ {res.reinforcement.top_spacing_y:.0f} mm"
                )
            )

    # --- Section 7: Overturning Stability ---
    with doc.create(Section("Overturning Stability Check")):
        # Compute weights
        L_m = data.length / 1000.0
        B_m = data.width / 1000.0
        h_m = data.thickness / 1000.0

        W_footing = 24.0 * L_m * B_m * h_m
        W_soil = (
            data.soil_unit_weight * L_m * B_m * (data.soil_depth / 1000.0)
            if data.soil_depth > 0
            else 0.0
        )
        W_surcharge = surcharge_total * L_m * B_m
        P_total = data.pu_srv + W_footing + W_soil + W_surcharge

        doc.append(bold("Total vertical load:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"P = P_s + W_f + W_{{soil}} + W_s = {data.pu_srv:.1f} + {W_footing:.1f} + {W_soil:.1f} + {W_surcharge:.1f} = {P_total:.1f}\,\text{{kN}}"
                    )
                ]
            )
        )

        # FS about X
        Mr_x = P_total * B_m / 2.0
        Mo_x = abs(data.mux_srv) + abs(data.vx_srv) * h_m
        fs_x = Mr_x / Mo_x
        status_x = "PASS" if fs_x >= (1.5 if data.transient_loads else 2.0) else "FAIL"

        doc.append(bold("FS about X-axis:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"FS_x = M_R / M_O = {Mr_x:.1f} / {Mo_x:.1f} = {fs_x:.2f} \quad \textbf{{{status_x}}}"
                    )
                ]
            )
        )

        # FS about Y
        Mr_y = P_total * L_m / 2.0
        Mo_y = abs(data.muy_srv) + abs(data.vy_srv) * h_m
        fs_y = Mr_y / Mo_y
        status_y = "PASS" if fs_y >= (1.5 if data.transient_loads else 2.0) else "FAIL"

        doc.append(bold("FS about Y-axis:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"FS_y = M_R / M_O = {Mr_y:.1f} / {Mo_y:.1f} = {fs_y:.2f} \quad \textbf{{{status_y}}}"
                    )
                ]
            )
        )

    # --- Section 8: Reinforcement Details (summary) ---
    with doc.create(Section("Reinforcement Schedule")):
        with doc.create(Tabular("l l l l")) as tab:
            tab.add_row(("Location", "Bar", "Spacing (mm)", "As (mm²/m)"))
            tab.add_hline()
            tab.add_row(
                ("Bottom X", data.bottom_bar_size, f"{sx:.0f}", f"{As_prov_x:.1f}")
            )
            tab.add_row(
                ("Bottom Y", data.bottom_bar_size, f"{sy:.0f}", f"{As_prov_y:.1f}")
            )
            if res.reinforcement.top_bars_x:
                tab.add_row(
                    (
                        "Top X",
                        res.reinforcement.top_bars_x,
                        f"{res.reinforcement.top_spacing_x:.0f}",
                        f"{aci_tool.get_bar_area(res.reinforcement.top_bars_x) * 1000 / res.reinforcement.top_spacing_x:.1f}",
                    )
                )
                tab.add_row(
                    (
                        "Top Y",
                        res.reinforcement.top_bars_y,
                        f"{res.reinforcement.top_spacing_y:.0f}",
                        f"{aci_tool.get_bar_area(res.reinforcement.top_bars_y) * 1000 / res.reinforcement.top_spacing_y:.1f}",
                    )
                )
            tab.add_hline()
            tab.add_row(
                (
                    "Development",
                    f"{data.bottom_bar_size}",
                    f"{res.reinforcement.development_length:.0f}",
                    "mm",
                )
            )

    # --- Section 9: Design Notes ---
    if res.design_notes:
        with doc.create(Section("Design Notes")):
            with doc.create(Itemize()) as itemize:
                for note in list(dict.fromkeys(res.design_notes)):
                    # Fix unicode for LaTeX
                    safe_note = (
                        note.replace("λ", r"$\lambda$")
                        .replace("φ", r"$\phi$")
                        .replace("≥", r"$\geq$")
                        .replace("≤", r"$\leq$")
                        .replace("√", r"$\sqrt{}$")
                    )
                    itemize.add_item(NoEscape(safe_note))

    # --- Generate PDF ---
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "footing_report")
    doc.generate_pdf(filepath, clean_tex=False)

    with open(filepath + ".pdf", "rb") as f:
        pdf_bytes = f.read()

    return pdf_bytes
