import math
import tempfile
import os
from pylatex import Document, Section, Subsection, Math, Command, NoEscape, Head, Foot, PageStyle, Itemize, Tabular, Figure
from pylatex.utils import bold
from aci318m25 import ACI318M25
from aci318m25_column import FrameSystem, ColumnShape

aci_tool = ACI318M25()


def draw_column_section_tikz(width, depth, cover, num_bars, legs_x, legs_y, shape="rectangular", column_type="tied"):
    """Generates TikZ code for a column cross-section diagram."""
    if shape == "circular":
        diameter = width
        s = 4.0 / diameter
        r = diameter * s / 2.0
        cx, cy = r, r
        c_r = (diameter / 2.0 - cover) * s
        r_bar = 0.08

        tikz = [
            r"\begin{tikzpicture}[scale=1.0]",
            fr"\draw[line width=1.5pt] ({cx:.3f},{cy:.3f}) circle ({r:.3f});",
        ]
        # Spiral: solid continuous circle; Tied: dashed hoops
        if column_type == "spiral":
            tikz.append(fr"\draw[line width=1.2pt, red] ({cx:.3f},{cy:.3f}) circle ({c_r:.3f});")
        else:
            tikz.append(fr"\draw[line width=0.8pt, dashed, red] ({cx:.3f},{cy:.3f}) circle ({c_r:.3f});")

        def bar(x, y):
            tikz.append(fr"\fill[blue] ({x:.3f},{y:.3f}) circle ({r_bar});")

        bar_r = c_r - 0.12
        for i in range(num_bars):
            theta = i * (2 * math.pi / max(1, num_bars))
            bar(cx + bar_r * math.cos(theta), cy + bar_r * math.sin(theta))

        # Dimension
        tikz.append(fr"\draw[<->] ({cx-r:.3f},{cy+r+0.4:.3f}) -- ({cx+r:.3f},{cy+r+0.4:.3f}) node[midway, above] {{\\diameter {diameter:.0f} mm}};")
        tikz.append(r"\end{tikzpicture}")
        return "\n".join(tikz)

    # Rectangular
    s = 4.0 / max(width, depth)
    w, h = width * s, depth * s
    c = cover * s

    tikz = [
        r"\begin{tikzpicture}[scale=1.0]",
        fr"\draw[line width=1.5pt] (0,0) rectangle ({w:.3f},{h:.3f});",
        fr"\draw[line width=0.8pt, dashed, red] ({c:.3f},{c:.3f}) rectangle ({w-c:.3f},{h-c:.3f});",
    ]

    # Interior tie legs
    core_w, core_h = w - 2 * c, h - 2 * c
    if legs_y > 2 and core_w > 0:
        sp_x = core_w / (legs_y - 1)
        for i in range(1, legs_y - 1):
            x = c + i * sp_x
            tikz.append(fr"\draw[line width=0.6pt, dashed, red] ({x:.3f},{c:.3f}) -- ({x:.3f},{h-c:.3f});")
    if legs_x > 2 and core_h > 0:
        sp_y = core_h / (legs_x - 1)
        for i in range(1, legs_x - 1):
            y = c + i * sp_y
            tikz.append(fr"\draw[line width=0.6pt, dashed, red] ({c:.3f},{y:.3f}) -- ({w-c:.3f},{y:.3f});")

    # Bar placement (same logic as column.py generate_column_section_css)
    inset = 0.15
    bx, by = c + inset, c + inset
    bw, bh = core_w - 2 * inset, core_h - 2 * inset
    r_bar = 0.08

    nx_face, ny_face = 0, 0
    if num_bars > 4:
        rem = num_bars - 4
        ratio = width / (width + depth) if (width + depth) > 0 else 0.5
        nx_inter = 2 * int(round(rem * ratio / 2.0))
        nx_face, ny_face = nx_inter // 2, (rem - nx_inter) // 2

    def bar(x, y):
        tikz.append(fr"\fill[blue] ({x:.3f},{y:.3f}) circle ({r_bar});")

    if bw >= 0 and bh >= 0:
        bar(bx, by); bar(bx + bw, by); bar(bx, by + bh); bar(bx + bw, by + bh)
        if nx_face > 0:
            sp = bw / (nx_face + 1)
            for i in range(1, nx_face + 1):
                bar(bx + i * sp, by); bar(bx + i * sp, by + bh)
        if ny_face > 0:
            sp = bh / (ny_face + 1)
            for i in range(1, ny_face + 1):
                bar(bx, by + i * sp); bar(bx + bw, by + i * sp)

    # Dimensions
    tikz.append(fr"\draw[<->] (0, {h+0.4:.3f}) -- ({w:.3f}, {h+0.4:.3f}) node[midway, above] {{{width:.0f} mm}};")
    tikz.append(fr"\draw[<->] ({-0.4:.3f}, 0) -- ({-0.4:.3f}, {h:.3f}) node[midway, left] {{{depth:.0f} mm}};")

    tikz.append(r"\end{tikzpicture}")
    return "\n".join(tikz)


def draw_column_elevation_tikz(height, clear_height, max_dim, s_hinge, s_mid, column_type="tied", shape="rectangular"):
    """Generates TikZ code for a column elevation showing tie/spiral spacing zones."""
    lo = max(max_dim, clear_height / 6.0, 450.0) if s_hinge != s_mid else 0.0
    if lo > 0 and lo * 2 >= clear_height:
        lo = clear_height / 2.0

    # Scale to ~8cm tall
    s = 8.0 / height
    vis_h = height * s
    vis_w = 1.6

    tikz = [
        r"\begin{tikzpicture}[scale=1.0]",
        fr"\draw[line width=1.5pt] (0,0) rectangle ({vis_w:.3f},{vis_h:.3f});",
    ]

    # Main bars (3 vertical lines)
    for xf in [0.2, 0.5, 0.8]:
        x = xf * vis_w
        tikz.append(fr"\draw[blue, line width=1pt] ({x:.3f},-0.1) -- ({x:.3f},{vis_h+0.1:.3f});")

    # Ties or Spiral zigzag
    y = 50.0 * s
    guard = 0
    if shape == "circular" and column_type == "spiral":
        going_right = True
        while y <= (height - 50.0) * s and guard < 300:
            guard += 1
            actual_y = y / s
            is_hinge = (actual_y <= lo) or (actual_y >= height - lo) if lo > 0 else False
            color = "red" if is_hinge else "gray"
            current_s = s_hinge if is_hinge else s_mid
            y_end = min(y + current_s * s, (height - 50.0) * s)
            if going_right:
                tikz.append(fr"\draw[{color}, line width=0.8pt] (0.08,{y:.3f}) -- ({vis_w-0.08:.3f},{y_end:.3f});")
            else:
                tikz.append(fr"\draw[{color}, line width=0.8pt] ({vis_w-0.08:.3f},{y:.3f}) -- (0.08,{y_end:.3f});")
            going_right = not going_right
            y = y_end
    else:
        while y <= (height - 50.0) * s and guard < 300:
            guard += 1
            actual_y = y / s
            is_hinge = (actual_y <= lo) or (actual_y >= height - lo) if lo > 0 else False
            color = "red" if is_hinge else "gray"
            tikz.append(fr"\draw[{color}, line width=0.6pt] (0.08,{y:.3f}) -- ({vis_w-0.08:.3f},{y:.3f});")
            current_s = s_hinge if is_hinge else s_mid
            y += current_s * s

    # Zone labels
    if lo > 0:
        lo_s = lo * s
        tikz.append(fr"\draw[<->, red] ({vis_w+0.3:.3f},0) -- ({vis_w+0.3:.3f},{lo_s:.3f}) node[midway, right, font=\tiny] {{$l_o$={lo:.0f}}};")
        tikz.append(fr"\draw[<->, gray] ({vis_w+0.3:.3f},{lo_s:.3f}) -- ({vis_w+0.3:.3f},{vis_h-lo_s:.3f}) node[midway, right, font=\tiny] {{mid}};")
        tikz.append(fr"\draw[<->, red] ({vis_w+0.3:.3f},{vis_h-lo_s:.3f}) -- ({vis_w+0.3:.3f},{vis_h:.3f}) node[midway, right, font=\tiny] {{$l_o$={lo:.0f}}};")

    tikz.append(fr"\draw[<->] ({-0.4:.3f},0) -- ({-0.4:.3f},{vis_h:.3f}) node[midway, left, font=\small] {{{height:.0f} mm}};")
    tikz.append(r"\end{tikzpicture}")
    return "\n".join(tikz)


def generate_column_report(data, mat, geom, loads, engine, res, n_bars, s_outside, qto, j_res=None):
    geometry_options = {"margin": "1in", "headheight": "38pt", "includeheadfoot": True}
    doc = Document(geometry_options=geometry_options)

    doc.preamble.append(NoEscape(r'\usepackage{amsmath}'))
    doc.preamble.append(NoEscape(r'\usepackage{tikz}'))

    # Header with project info
    header = PageStyle("header")
    with header.create(Head("C")):
        with header.create(Tabular('|p{8cm}|p{8cm}|')) as table:
            table.add_hline()
            table.add_row((NoEscape(fr"\textbf{{Project:}} {data.proj_name}"), NoEscape(fr"\textbf{{Engineer:}} {data.proj_eng}")))
            table.add_hline()
            table.add_row((NoEscape(fr"\textbf{{Location:}} {data.proj_loc}"), NoEscape(fr"\textbf{{Date:}} {data.proj_date}")))
            table.add_hline()
    with header.create(Foot("C")):
        header.append(Command("thepage"))
    doc.preamble.append(header)
    doc.change_document_style("header")

    doc.append(NoEscape(r'\vspace*{1em}'))
    doc.append(Command("begin", "center"))
    doc.append(Command("huge", bold("RC Column Design Report")))
    doc.append(Command("end", "center"))
    doc.append(NoEscape(r'\vspace*{1em}'))

    fc = data.fc_prime
    fy = data.fy
    fyt = data.fyt
    b = data.width
    h = data.depth
    is_circular = (data.shape == "circular")
    Ag = math.pi * (b / 2.0) ** 2 if is_circular else b * h
    As = res.reinforcement.longitudinal_area
    cover = 40.0
    is_smf = (data.frame_system == "special")

    # ── Section 1: Material & Geometry ──
    with doc.create(Section("Material \\& Geometry")):
        with doc.create(Itemize()) as itemize:
            itemize.add_item(NoEscape(fr"Concrete strength, $f'_c = {fc}$ MPa"))
            itemize.add_item(NoEscape(fr"Main rebar yield strength, $f_y = {fy}$ MPa"))
            itemize.add_item(NoEscape(fr"Tie yield strength, $f_{{yt}} = {fyt}$ MPa"))
            itemize.add_item(NoEscape(fr"Modulus of elasticity, $E_c = {mat.ec:.0f}$ MPa"))
            if is_circular:
                itemize.add_item(NoEscape(fr"Column diameter: $D = {b}$ mm"))
            else:
                itemize.add_item(NoEscape(fr"Column dimensions: $b = {b}$ mm $\times$ $h = {h}$ mm"))
            itemize.add_item(NoEscape(fr"Floor-to-floor height $H = {data.height}$ mm, clear height $l_u = {data.clear_height}$ mm"))
            itemize.add_item(NoEscape(fr"SDC {data.sdc}, {data.frame_system.title()} moment frame"))

    # ── Section 2: Reinforcement Summary ──
    with doc.create(Section("Reinforcement Summary")):
        rho = As / Ag
        tie_str_hinge = fr"{res.reinforcement.tie_legs_x}$\times${res.reinforcement.tie_legs_y} legs {res.reinforcement.tie_bars} @ {res.reinforcement.tie_spacing:.0f} mm"
        tie_str_mid = fr"{res.reinforcement.tie_legs_x}$\times${res.reinforcement.tie_legs_y} legs {res.reinforcement.tie_bars} @ {s_outside:.0f} mm"

        with doc.create(Itemize()) as itemize:
            itemize.add_item(NoEscape(fr"Longitudinal bars: {n_bars}$\times${data.pref_main} ($A_s$ = {As:.1f} mm$^2$)"))
            itemize.add_item(NoEscape(fr"Reinforcement ratio: $\rho = A_s / A_g = {As:.1f} / {Ag:.0f} = {rho:.4f}$"))
            itemize.add_item(NoEscape(fr"Ties (confinement zone): {tie_str_hinge}"))
            itemize.add_item(NoEscape(fr"Ties (midheight): {tie_str_mid}"))

        with doc.create(Figure(position='h!')) as fig:
            fig.append(NoEscape(draw_column_section_tikz(b, h, cover, n_bars,
                                                          res.reinforcement.tie_legs_x, res.reinforcement.tie_legs_y,
                                                          data.shape, data.column_type)))
            fig.add_caption("Column Cross-Section")

        with doc.create(Figure(position='h!')) as fig:
            fig.append(NoEscape(draw_column_elevation_tikz(data.height, data.clear_height,
                                                            max(b, h), res.reinforcement.tie_spacing, s_outside,
                                                            data.column_type, data.shape)))
            fig.add_caption("Column Elevation --- Tie/Spiral Zones")

    # ── Section 3: Design Calculations ──
    with doc.create(Section("Design Calculations")):

        # 3.1 Axial Capacity
        with doc.create(Subsection("Axial Capacity")):
            doc.append(bold("Factored loads: "))
            doc.append(NoEscape(fr"$P_u$ = {data.pu} kN, $M_{{ux}}$ = {loads.moment_x:.1f} kN-m, $M_{{uy}}$ = {loads.moment_y:.1f} kN-m"))
            doc.append(NoEscape(r'\vspace*{0.5em}'))
            doc.append(NoEscape(r'\\'))

            if is_circular:
                doc.append(Math(data=[NoEscape(fr"A_g = \frac{{\pi D^2}}{{4}} = \frac{{\pi \times {b:.0f}^2}}{{4}} = {Ag:.0f} \text{{ mm}}^2")]))
            else:
                doc.append(Math(data=[NoEscape(fr"A_g = b \times h = {b:.0f} \times {h:.0f} = {Ag:.0f} \text{{ mm}}^2")]))

            Po = 0.85 * fc * (Ag - As) + fy * As
            doc.append(Math(data=[NoEscape(
                fr"P_o = 0.85 f'_c (A_g - A_s) + f_y A_s = 0.85 \times {fc} \times ({Ag:.0f} - {As:.1f}) + {fy} \times {As:.1f} = {Po/1000:.1f} \text{{ kN}}")]))

            Pn_max = 0.80 * Po / 1000
            doc.append(Math(data=[NoEscape(
                fr"P_{{n,max}} = 0.80 \, P_o = 0.80 \times {Po/1000:.1f} = {Pn_max:.1f} \text{{ kN}}")]))

            phi_c = 0.65
            phi_Pn = phi_c * Pn_max
            doc.append(Math(data=[NoEscape(
                fr"\phi P_{{n,max}} = {phi_c} \times {Pn_max:.1f} = {phi_Pn:.1f} \text{{ kN}}")]))

            axial_ratio = abs(data.pu) / phi_Pn if phi_Pn > 0 else 999
            status = "OK" if axial_ratio <= 1.0 else "NG"
            doc.append(Math(data=[NoEscape(
                fr"P_u / \phi P_{{n,max}} = {abs(data.pu):.1f} / {phi_Pn:.1f} = {axial_ratio:.3f} \quad \textbf{{{status}}}")]))

        # 3.2 Slenderness
        with doc.create(Subsection("Slenderness Check (ACI 6.2.5)")):
            lu = data.clear_height
            k = 1.0
            r_x = b / (2 * math.sqrt(3))
            r_y = h / (2 * math.sqrt(3))

            doc.append(Math(data=[NoEscape(
                fr"r_x = \frac{{b}}{{2\sqrt{{3}}}} = \frac{{{b:.0f}}}{{2\sqrt{{3}}}} = {r_x:.1f} \text{{ mm}}")]))
            doc.append(Math(data=[NoEscape(
                fr"r_y = \frac{{h}}{{2\sqrt{{3}}}} = \frac{{{h:.0f}}}{{2\sqrt{{3}}}} = {r_y:.1f} \text{{ mm}}")]))

            kl_r_x = k * lu / r_x
            kl_r_y = k * lu / r_y
            kl_r = max(kl_r_x, kl_r_y)

            doc.append(Math(data=[NoEscape(
                fr"\frac{{k l_u}}{{r_x}} = \frac{{{k} \times {lu:.0f}}}{{{r_x:.1f}}} = {kl_r_x:.1f}")]))
            doc.append(Math(data=[NoEscape(
                fr"\frac{{k l_u}}{{r_y}} = \frac{{{k} \times {lu:.0f}}}{{{r_y:.1f}}} = {kl_r_y:.1f}")]))

            gov_axis = "x" if kl_r_x >= kl_r_y else "y"
            doc.append(Math(data=[NoEscape(
                fr"\frac{{k l_u}}{{r}}_{{gov}} = {kl_r:.1f} \quad (\text{{{gov_axis}-axis governs}})")]))

            if kl_r <= 22.0:
                doc.append(NoEscape(fr"$kl_u/r = {kl_r:.1f} \le 22.0$ — slenderness effects \textbf{{may be neglected}}."))
            else:
                doc.append(NoEscape(fr"$kl_u/r = {kl_r:.1f} > 22.0$ — \textbf{{slenderness effects must be considered}}."))
                doc.append(NoEscape(r'\vspace*{0.5em}'))
                doc.append(NoEscape(r'\\'))

                beta_dns = 0.6
                if kl_r_x >= kl_r_y:
                    Ig = h * b ** 3 / 12.0
                    ig_label = fr"I_g = h b^3 / 12 = {h:.0f} \times {b:.0f}^3 / 12"
                else:
                    Ig = b * h ** 3 / 12.0
                    ig_label = fr"I_g = b h^3 / 12 = {b:.0f} \times {h:.0f}^3 / 12"

                EI = 0.4 * mat.ec * Ig / (1 + beta_dns)
                doc.append(Math(data=[NoEscape(
                    fr"EI = \frac{{0.4 E_c I_g}}{{1 + \beta_{{dns}}}} = \frac{{0.4 \times {mat.ec:.0f} \times {Ig:.0f}}}{{1 + {beta_dns}}} = {EI:.0f} \text{{ N-mm}}^2")]))

                Pc = (math.pi ** 2 * EI) / (k * lu) ** 2 / 1000
                doc.append(Math(data=[NoEscape(
                    fr"P_c = \frac{{\pi^2 EI}}{{(k l_u)^2}} = \frac{{\pi^2 \times {EI:.0f}}}{{({k} \times {lu:.0f})^2}} \times 10^{{-3}} = {Pc:.1f} \text{{ kN}}")]))

                Pu = abs(data.pu)
                denom = 1.0 - Pu / (0.75 * Pc) if Pc > 0 else 0.0
                if denom <= 0:
                    mag = 2.0
                    doc.append(NoEscape(fr"$P_u / 0.75 P_c \ge 1.0$ — section is unstable. $\delta_{{ns}}$ capped at 2.0."))
                else:
                    mag = max(1.0, 1.0 / denom)
                    doc.append(Math(data=[NoEscape(
                        fr"\delta_{{ns}} = \frac{{C_m}}{{1 - P_u / (0.75 P_c)}} = \frac{{1.0}}{{1 - {Pu:.1f} / (0.75 \times {Pc:.1f})}} = {mag:.2f}")]))

        # 3.3 P-M Interaction
        with doc.create(Subsection("P-M Interaction Check")):
            bar_layout = engine.generate_bar_layout(geom, res.reinforcement.longitudinal_bars, res.reinforcement.tie_bars)
            Pu = abs(loads.axial_force)
            Mux = abs(loads.moment_x)
            Muy = abs(loads.moment_y)

            # Get nominal moment capacities at Pu
            Mnx = engine.calculate_nominal_moment_capacity(geom, mat, bar_layout, loads.axial_force, 'x')
            Mny = engine.calculate_nominal_moment_capacity(geom, mat, bar_layout, loads.axial_force, 'y')
            phi_Mnx = phi_c * Mnx
            phi_Mny = phi_c * Mny

            doc.append(NoEscape(r"Nominal moment capacities at $P_u$ from P-M interaction diagram:"))
            doc.append(NoEscape(r'\vspace*{0.5em}'))
            doc.append(Math(data=[NoEscape(fr"\phi M_{{nx}} = \phi_c \times M_{{nx}} = {phi_c} \times {Mnx:.1f} = {phi_Mnx:.1f} \text{{ kN-m}}")]))
            doc.append(Math(data=[NoEscape(fr"\phi M_{{ny}} = \phi_c \times M_{{ny}} = {phi_c} \times {Mny:.1f} = {phi_Mny:.1f} \text{{ kN-m}}")]))

            if res.capacity.slenderness_effects:
                _, mag_factor = engine.check_slenderness_effects(geom, loads, mat, As)
                Mux_mag = Mux * mag_factor
                Muy_mag = Muy * mag_factor
                doc.append(NoEscape(r'\vspace*{0.5em}'))
                doc.append(NoEscape(r'\\'))
                doc.append(NoEscape(fr"Moments magnified by $\delta_{{ns}} = {mag_factor:.2f}$:"))
                doc.append(Math(data=[NoEscape(fr"M_{{ux}} = {Mux:.1f} \times {mag_factor:.2f} = {Mux_mag:.1f} \text{{ kN-m}}")]))
                doc.append(Math(data=[NoEscape(fr"M_{{uy}} = {Muy:.1f} \times {mag_factor:.2f} = {Muy_mag:.1f} \text{{ kN-m}}")]))
                Mux, Muy = Mux_mag, Muy_mag

            alpha = 1.15
            ratio_x = (Mux / phi_Mnx) if phi_Mnx > 0 else 0
            ratio_y = (Muy / phi_Mny) if phi_Mny > 0 else 0

            doc.append(NoEscape(r'\vspace*{0.5em}'))
            doc.append(NoEscape(r'\\'))
            doc.append(bold("Bresler Load Contour (Biaxial Bending):"))
            doc.append(Math(data=[NoEscape(
                fr"\left(\frac{{M_{{ux}}}}{{\phi M_{{nx}}}}\right)^\alpha + \left(\frac{{M_{{uy}}}}{{\phi M_{{ny}}}}\right)^\alpha = "
                fr"\left(\frac{{{Mux:.1f}}}{{{phi_Mnx:.1f}}}\right)^{{{alpha}}} + \left(\frac{{{Muy:.1f}}}{{{phi_Mny:.1f}}}\right)^{{{alpha}}}")]))

            bresler = (ratio_x ** alpha + ratio_y ** alpha) ** (1.0 / alpha)
            status = "OK" if bresler <= 1.0 else "NG"
            doc.append(Math(data=[NoEscape(
                fr"= ({ratio_x:.3f})^{{{alpha}}} + ({ratio_y:.3f})^{{{alpha}}} = {bresler:.3f} \quad \textbf{{{status}}}")]))

            doc.append(NoEscape(r'\vspace*{0.5em}'))
            doc.append(NoEscape(r'\\'))
            doc.append(NoEscape(fr"\textbf{{P-M Interaction Ratio:}} {res.capacity.interaction_ratio:.3f}"))

        # 3.4 & 3.5 Shear Capacity
        tie_size = res.reinforcement.tie_bars
        tie_spacing = res.reinforcement.tie_spacing
        tie_dia = aci_tool.get_bar_diameter(tie_size)
        long_dia = aci_tool.get_bar_diameter(data.pref_main)
        Av = aci_tool.get_bar_area(tie_size)
        phi_v = 0.75

        # Check if Vc=0 applies (for display)
        vc_zero = False
        Ve_x_display = abs(loads.shear_x)
        Ve_y_display = abs(loads.shear_y)

        if is_smf:
            lu_m = data.clear_height / 1000.0
            Mpr_c = engine.calculate_probable_moment_capacity(geom, mat, bar_layout, loads.axial_force)
            Ve_req = (2.0 * Mpr_c) / lu_m if lu_m > 0 else Ve_x_display
            Ve_x_display = max(Ve_x_display, Ve_req)
            Ve_y_display = max(Ve_y_display, Ve_req)

            phi_Vnx_check, phi_Vny_check = engine.calculate_shear_capacity(
                geom, mat, tie_size, tie_spacing, res.reinforcement.tie_legs_x,
                res.reinforcement.tie_legs_y, res.reinforcement.longitudinal_bars)
            if (Ve_req > 0.5 * max(phi_Vnx_check, phi_Vny_check)) and (abs(loads.axial_force) * 1000 < Ag * fc / 20):
                vc_zero = True

        for axis, axis_label in [('x', 'X'), ('y', 'Y')]:
            with doc.create(Subsection(fr"Shear Capacity ({axis_label}-direction)")):
                if axis == 'x':
                    d_eff = b - cover - tie_dia - long_dia / 2
                    bw = h
                    legs = res.reinforcement.tie_legs_x
                    Vu = Ve_x_display
                else:
                    d_eff = h - cover - tie_dia - long_dia / 2
                    bw = b
                    legs = res.reinforcement.tie_legs_y
                    Vu = Ve_y_display

                doc.append(Math(data=[NoEscape(
                    fr"d_{axis} = {['b','h'][0 if axis=='x' else 1]} - c - d_{{tie}} - d_{{bar}}/2 = "
                    fr"{[b,h][0 if axis=='x' else 1]:.0f} - {cover:.0f} - {tie_dia:.1f} - {long_dia:.1f}/2 = {d_eff:.1f} \text{{ mm}}")]))

                if vc_zero:
                    doc.append(Math(data=[NoEscape(fr"V_c = 0 \text{{ kN}} \quad \text{{(ACI 18.7.6.2.1: low axial + high seismic shear)}}")]))
                    Vc = 0.0
                else:
                    Vc = 0.17 * math.sqrt(fc) * bw * d_eff / 1000
                    doc.append(Math(data=[NoEscape(
                        fr"V_c = 0.17 \sqrt{{f'_c}} \, b_w \, d = 0.17 \times \sqrt{{{fc}}} \times {bw:.0f} \times {d_eff:.1f} \times 10^{{-3}} = {Vc:.1f} \text{{ kN}}")]))

                Av_total = legs * Av
                Vs = Av_total * fyt * d_eff / tie_spacing / 1000
                doc.append(Math(data=[NoEscape(
                    fr"V_s = \frac{{n_{{legs}} A_v f_{{yt}} d}}{{s}} = \frac{{{legs} \times {Av:.1f} \times {fyt} \times {d_eff:.1f}}}{{{tie_spacing:.0f}}} \times 10^{{-3}} = {Vs:.1f} \text{{ kN}}")]))

                phi_Vn = phi_v * (Vc + Vs)
                doc.append(Math(data=[NoEscape(
                    fr"\phi V_n = \phi (V_c + V_s) = {phi_v} \times ({Vc:.1f} + {Vs:.1f}) = {phi_Vn:.1f} \text{{ kN}}")]))

                util = Vu / phi_Vn if phi_Vn > 0 else 999
                status = "OK" if util <= 1.0 else "NG"
                doc.append(Math(data=[NoEscape(
                    fr"V_u / \phi V_n = {Vu:.1f} / {phi_Vn:.1f} = {util:.2f} \quad \textbf{{{status}}}")]))

        # 3.6 Confinement (SMF)
        if is_smf:
            with doc.create(Subsection("Confinement Requirements (ACI 18.7.5)")):
                bc_x = h - 2 * cover
                bc_y = b - 2 * cover
                Ach = bc_x * bc_y

                doc.append(Math(data=[NoEscape(
                    fr"b_{{cx}} = h - 2c = {h:.0f} - 2 \times {cover:.0f} = {bc_x:.0f} \text{{ mm}}")]))
                doc.append(Math(data=[NoEscape(
                    fr"b_{{cy}} = b - 2c = {b:.0f} - 2 \times {cover:.0f} = {bc_y:.0f} \text{{ mm}}")]))
                doc.append(Math(data=[NoEscape(
                    fr"A_{{ch}} = b_{{cx}} \times b_{{cy}} = {bc_x:.0f} \times {bc_y:.0f} = {Ach:.0f} \text{{ mm}}^2")]))

                ash_s_req_x_1 = 0.3 * bc_x * fc / fyt * (Ag / Ach - 1.0)
                ash_s_req_x_2 = 0.09 * bc_x * fc / fyt
                ash_s_req_x = max(ash_s_req_x_1, ash_s_req_x_2)

                doc.append(NoEscape(r'\vspace*{0.5em}'))
                doc.append(NoEscape(r'\\'))
                doc.append(bold("X-direction:"))
                doc.append(Math(data=[NoEscape(
                    fr"\frac{{A_{{sh}}}}{{s}}_{{req}} = \max\left(0.3 \frac{{b_{{cx}} f'_c}}{{f_{{yt}}}} \left(\frac{{A_g}}{{A_{{ch}}}} - 1\right),\; 0.09 \frac{{b_{{cx}} f'_c}}{{f_{{yt}}}}\right) = \max({ash_s_req_x_1:.2f},\; {ash_s_req_x_2:.2f}) = {ash_s_req_x:.2f} \text{{ mm}}^2\text{{/mm}}")]))

                ash_prov_x = res.reinforcement.tie_legs_x * Av
                ash_s_prov_x = ash_prov_x / tie_spacing
                status_x = "OK" if ash_s_prov_x >= ash_s_req_x else "NG"
                doc.append(Math(data=[NoEscape(
                    fr"\frac{{A_{{sh}}}}{{s}}_{{prov}} = \frac{{{res.reinforcement.tie_legs_x} \times {Av:.1f}}}{{{tie_spacing:.0f}}} = {ash_s_prov_x:.2f} \text{{ mm}}^2\text{{/mm}} \quad \textbf{{{status_x}}}")]))

                ash_s_req_y_1 = 0.3 * bc_y * fc / fyt * (Ag / Ach - 1.0)
                ash_s_req_y_2 = 0.09 * bc_y * fc / fyt
                ash_s_req_y = max(ash_s_req_y_1, ash_s_req_y_2)

                doc.append(NoEscape(r'\vspace*{0.5em}'))
                doc.append(NoEscape(r'\\'))
                doc.append(bold("Y-direction:"))
                doc.append(Math(data=[NoEscape(
                    fr"\frac{{A_{{sh}}}}{{s}}_{{req}} = \max({ash_s_req_y_1:.2f},\; {ash_s_req_y_2:.2f}) = {ash_s_req_y:.2f} \text{{ mm}}^2\text{{/mm}}")]))

                ash_prov_y = res.reinforcement.tie_legs_y * Av
                ash_s_prov_y = ash_prov_y / tie_spacing
                status_y = "OK" if ash_s_prov_y >= ash_s_req_y else "NG"
                doc.append(Math(data=[NoEscape(
                    fr"\frac{{A_{{sh}}}}{{s}}_{{prov}} = \frac{{{res.reinforcement.tie_legs_y} \times {Av:.1f}}}{{{tie_spacing:.0f}}} = {ash_s_prov_y:.2f} \text{{ mm}}^2\text{{/mm}} \quad \textbf{{{status_y}}}")]))

                # Spacing limits
                min_dim = min(b, h)
                db_main = aci_tool.get_bar_diameter(data.pref_main)
                hx_approx = min_dim / min(res.reinforcement.tie_legs_x, res.reinforcement.tie_legs_y)
                sx = max(100.0, min(100.0 + (350.0 - hx_approx) / 3.0, 150.0))
                s_max = min(min_dim / 4.0, 6.0 * db_main, sx)

                doc.append(NoEscape(r'\vspace*{0.5em}'))
                doc.append(NoEscape(r'\\'))
                doc.append(bold("Maximum tie spacing:"))
                doc.append(Math(data=[NoEscape(
                    fr"s_{{max}} = \min\left(\frac{{b_{{min}}}}{{4}},\; 6 d_b,\; s_x\right) = \min\left(\frac{{{min_dim:.0f}}}{{4}},\; 6 \times {db_main:.0f},\; {sx:.0f}\right) = {s_max:.0f} \text{{ mm}}")]))
                s_status = "OK" if tie_spacing <= s_max else "NG"
                doc.append(NoEscape(fr"Provided spacing: {tie_spacing:.0f} mm $\le$ {s_max:.0f} mm — \textbf{{{s_status}}}"))

        # 3.7 SMF Capacity Design Shear
        if is_smf:
            with doc.create(Subsection("Capacity Design Shear (ACI 18.7.6)")):
                lu_m = data.clear_height / 1000.0

                doc.append(Math(data=[NoEscape(
                    fr"M_{{pr}} = {Mpr_c:.1f} \text{{ kN-m}} \quad \text{{(from P-M diagram at }} f_{{y,pr}} = 1.25 f_y = {1.25*fy:.0f} \text{{ MPa)}}")]))
                doc.append(Math(data=[NoEscape(
                    fr"V_e = \frac{{2 M_{{pr}}}}{{l_u}} = \frac{{2 \times {Mpr_c:.1f}}}{{{lu_m:.3f}}} = {Ve_req:.1f} \text{{ kN}}")]))

                if vc_zero:
                    doc.append(NoEscape(r'\vspace*{0.5em}'))
                    doc.append(NoEscape(r'\\'))
                    doc.append(NoEscape(fr"$P_u = {abs(loads.axial_force):.0f}$ kN $< A_g f'_c / 20 = {Ag*fc/20/1000:.0f}$ kN "
                                        fr"and $V_e > 0.5 \phi V_n$ — \textbf{{$V_c = 0$ per ACI 18.7.6.2.1.}}"))

    # ── Section 4: Seismic Joint Checks ──
    if j_res is not None:
        with doc.create(Section("Seismic Joint Checks (ACI 18.8)")):
            for d_res, dir_label in [(j_res.x_dir, "X"), (j_res.y_dir, "Y")]:
                with doc.create(Subsection(fr"{dir_label}-direction")):
                    if not d_res.exists:
                        doc.append(NoEscape("No framing beams defined in this direction."))
                        continue

                    doc.append(bold("Strong Column / Weak Beam:"))
                    doc.append(Math(data=[NoEscape(
                        fr"\sum M_{{nb}} = {d_res.sum_mnb:.1f} \text{{ kN-m}}")]))
                    doc.append(Math(data=[NoEscape(
                        fr"\sum M_{{nc}} = {d_res.sum_mnc:.1f} \text{{ kN-m}}")]))

                    scwb_status = "OK" if d_res.ratio_scwb >= 1.2 else "NG"
                    doc.append(Math(data=[NoEscape(
                        fr"\frac{{\sum M_{{nc}}}}{{\sum M_{{nb}}}} = \frac{{{d_res.sum_mnc:.1f}}}{{{d_res.sum_mnb:.1f}}} = {d_res.ratio_scwb:.2f} \ge 1.2 \quad \textbf{{{scwb_status}}}")]))

                    doc.append(NoEscape(r'\vspace*{0.5em}'))
                    doc.append(NoEscape(r'\\'))
                    doc.append(bold("Joint Shear:"))
                    doc.append(Math(data=[NoEscape(
                        fr"V_{{j}} = {d_res.vj_u:.1f} \text{{ kN}}")]))
                    doc.append(Math(data=[NoEscape(
                        fr"\phi V_{{nj}} = 0.85 \gamma \sqrt{{f'_c}} \, A_j = {d_res.phi_vj:.1f} \text{{ kN}} \quad (\gamma = {d_res.gamma})")]))

                    vj_status = "OK" if d_res.ratio_vj <= 1.0 else "NG"
                    doc.append(Math(data=[NoEscape(
                        fr"V_j / \phi V_{{nj}} = {d_res.vj_u:.1f} / {d_res.phi_vj:.1f} = {d_res.ratio_vj:.2f} \le 1.0 \quad \textbf{{{vj_status}}}")]))

    # ── Section 5: Design Checks Summary ──
    with doc.create(Section("Design Checks Summary")):
        rho_min = 0.01
        rho_max = 0.06 if is_smf else 0.08

        with doc.create(Itemize()) as itemize:
            # Geometric
            if is_smf:
                min_dim = min(b, h)
                max_dim = max(b, h)
                geo_status = "PASS" if min_dim >= 300 else "FAIL"
                itemize.add_item(NoEscape(fr"Min. dimension: {min_dim:.0f} mm $\ge$ 300 mm: \textbf{{{geo_status}}}"))
                ar = min_dim / max_dim if max_dim > 0 else 0
                ar_status = "PASS" if ar >= 0.4 else "FAIL"
                itemize.add_item(NoEscape(fr"Aspect ratio: {ar:.2f} $\ge$ 0.4: \textbf{{{ar_status}}}"))

            # Rho limits
            rho_status = "PASS" if rho_min <= rho <= rho_max else "FAIL"
            itemize.add_item(NoEscape(fr"Reinforcement ratio: $\rho = {rho:.4f}$ ({rho_min} to {rho_max}): \textbf{{{rho_status}}}"))

            # P-M
            pm_status = "PASS" if res.capacity.interaction_ratio <= 1.0 else "FAIL"
            itemize.add_item(NoEscape(fr"P-M interaction ratio: {res.capacity.interaction_ratio:.3f} $\le$ 1.0: \textbf{{{pm_status}}}"))

            # Shear
            vx_status = "PASS" if res.shear_utilization_x <= 1.0 else "FAIL"
            itemize.add_item(NoEscape(fr"Shear utilization (x): {res.shear_utilization_x:.2f} $\le$ 1.0: \textbf{{{vx_status}}}"))
            vy_status = "PASS" if res.shear_utilization_y <= 1.0 else "FAIL"
            itemize.add_item(NoEscape(fr"Shear utilization (y): {res.shear_utilization_y:.2f} $\le$ 1.0: \textbf{{{vy_status}}}"))

            if j_res is not None:
                for d_res, lbl in [(j_res.x_dir, "x"), (j_res.y_dir, "y")]:
                    if d_res.exists:
                        s1 = "PASS" if d_res.ratio_scwb >= 1.2 else "FAIL"
                        itemize.add_item(NoEscape(fr"SCWB ratio ({lbl}): {d_res.ratio_scwb:.2f} $\ge$ 1.2: \textbf{{{s1}}}"))
                        s2 = "PASS" if d_res.ratio_vj <= 1.0 else "FAIL"
                        itemize.add_item(NoEscape(fr"Joint shear ({lbl}): {d_res.ratio_vj:.2f} $\le$ 1.0: \textbf{{{s2}}}"))

    # ── Section 6: Design Notes ──
    if res.design_notes:
        with doc.create(Section("Design Notes")):
            with doc.create(Itemize()) as itemize:
                for note in list(dict.fromkeys(res.design_notes)):
                    safe_note = note.replace('λ', r'$\lambda$').replace('φ', r'$\phi$').replace('≥', r'$\geq$').replace('≤', r'$\leq$').replace('√', r'$\sqrt{}$')
                    itemize.add_item(NoEscape(safe_note))

    # ── Generate PDF ──
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "column_report")
    doc.generate_pdf(filepath, clean_tex=False)

    with open(filepath + ".pdf", "rb") as f:
        pdf_bytes = f.read()

    return pdf_bytes
