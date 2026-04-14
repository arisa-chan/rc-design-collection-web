import math
import tempfile
import os
from pylatex import Document, Section, Subsection, Math, Command, NoEscape, Head, Foot, PageStyle, Itemize, Tabular, Figure
from pylatex.utils import bold
from aci318m25 import ACI318M25

aci_tool = ACI318M25()

def draw_section_tikz(width, height, res_section, title="Section"):
    """Generates TikZ code for a beam section diagram."""
    # Scale: 0.05 cm per mm (e.g., 400mm -> 2cm)
    s = 4.0 / max(width, height)
    w, h = width * s, height * s
    cover = 40.0 * s
    
    top_bars = len(res_section.reinforcement.top_bars)
    bot_bars = len(res_section.reinforcement.bottom_bars)
    
    # TikZ boilerplate
    tikz = [
        r"\begin{tikzpicture}[scale=1.0]",
        fr"\draw[line width=1.5pt] (0,0) rectangle ({w},{h});", # Beam outer
        fr"\draw[line width=0.8pt, dashed, red] ({cover},{cover}) rectangle ({w-cover},{h-cover});", # Stirrup
    ]
    
    # Draw Top bars
    if top_bars >= 2:
        spacing = (w - 2*cover - 0.4) / (top_bars - 1)
        for i in range(top_bars):
            x = cover + 0.2 + i * spacing
            tikz.append(fr"\fill[blue] ({x},{h-cover-0.2}) circle (0.1);")
            
    # Draw Bot bars
    if bot_bars >= 2:
        spacing = (w - 2*cover - 0.4) / (bot_bars - 1)
        for i in range(bot_bars):
            x = cover + 0.2 + i * spacing
            tikz.append(fr"\fill[blue] ({x},{cover+0.2}) circle (0.1);")
            
    # Dimensions
    tikz.append(fr"\draw[<->] (0, {h+0.5}) -- ({w}, {h+0.5}) node[midway, above] {{{width:.0f} mm}};")
    tikz.append(fr"\draw[<->] ({-0.5}, 0) -- ({-0.5}, {h}) node[midway, left] {{{height:.0f} mm}};")
    
    tikz.append(r"\end{tikzpicture}")
    return "\n".join(tikz)

def generate_beam_report(data, mat_props, beam_geom, res_left, res_mid, res_right, defl_data=None):
    geometry_options = {"margin": "1in", "headheight": "38pt", "includeheadfoot": True}
    doc = Document(geometry_options=geometry_options)
    
    doc.preamble.append(NoEscape(r'\usepackage{amsmath}'))
    doc.preamble.append(NoEscape(r'\usepackage{tikz}'))
    
    # Custom grid header
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
    doc.append(Command("huge", bold("RC Beam Design Report")))
    doc.append(Command("end", "center"))
    doc.append(NoEscape(r'\vspace*{1em}'))
    
    # Material Props
    with doc.create(Section("Material & Geometry")):
        with doc.create(Itemize()) as itemize:
            itemize.add_item(NoEscape(fr"Concrete strength, $f'_c = {data.fc_prime}$ MPa"))
            itemize.add_item(NoEscape(fr"Main rebar yield strength, $f_y = {data.fy}$ MPa"))
            itemize.add_item(NoEscape(fr"Stirrup yield strength, $f_{{yt}} = {data.fyt}$ MPa"))
            itemize.add_item(NoEscape(fr"Beam dimensions: width $b_w = {data.width}$ mm, height $h = {data.height}$ mm, effective depth $d = {data.effective_depth}$ mm"))
            itemize.add_item(NoEscape(fr"Span length: $L = {data.length}$ mm, clear span $L_n = {data.clear_span}$ mm"))
    
    def section_report(title, demands, res):
        with doc.create(Subsection(title)):
            doc.append(bold("Factored loads: "))
            doc.append(NoEscape(fr"$M_u^-$ = {demands['mu_neg']} kN-m | $M_u^+$ = {demands['mu_pos']} kN-m | $V_u$ = {demands['vu']} kN | $T_u$ = {demands['tu']} kN-m"))
            doc.append(NoEscape(r'\vspace*{1em}'))
            doc.append(NoEscape(r'\\'))

            doc.append(bold("Flexural Capacities"))
            # Top
            top_area = res.reinforcement.top_area
            bot_area = res.reinforcement.bottom_area
            
            top_bars = f"{len(res.reinforcement.top_bars)}x{res.reinforcement.top_bars[0]}" if res.reinforcement.top_bars else "None"
            bot_bars = f"{len(res.reinforcement.bottom_bars)}x{res.reinforcement.bottom_bars[0]}" if res.reinforcement.bottom_bars else "None"
            
            doc.append(NoEscape(r'\vspace*{0.5em}'))
            doc.append(NoEscape(r'\\'))
            doc.append(NoEscape(fr"Top reinforcement: {top_bars} ($A_s$ = {top_area:.1f} mm$^2$)"))
            doc.append(NoEscape(r'\\'))
            doc.append(NoEscape(fr"Bottom einforcement: {bot_bars} ($A_s$ = {bot_area:.1f} mm$^2$)"))
            doc.append(NoEscape(r'\vspace*{0.5em}'))
            
            phi = 0.90
            fy = data.fy
            fc = data.fc_prime
            b = data.width
            d = data.effective_depth
            
            # Show calculations for Top Capacity (Negative Moment) if top_area > 0
            if top_area > 0:
                doc.append(NoEscape(r'\\'))
                doc.append(bold("Negative Moment"))
                a_top = (top_area * fy) / (0.85 * fc * b)
                doc.append(Math(data=[NoEscape(fr"a = \frac{{A_s f_y}}{{0.85 f'_c b}} = \frac{{{top_area:.1f} \times {fy}}}{{0.85 \times {fc} \times {b}}} = {a_top:.2f} \text{{ mm}}")]))
                doc.append(Math(data=[NoEscape(fr"\phi M_n^ - = \phi A_s f_y \left(d - \frac{{a}}{{2}}\right) = 0.90 \times {top_area:.1f} \times {fy} \times \left({d} - \frac{{{a_top:.2f}}}{{2}}\right) \times 10^{{-6}} = {res.moment_capacity_top:.1f} \text{{ kN-m}}")]))

            # Show calculations for Bottom Capacity (Positive Moment) if bot_area > 0
            if bot_area > 0:
                doc.append(NoEscape(r'\\'))
                doc.append(bold("Positive Moment"))
                a_bot = (bot_area * fy) / (0.85 * fc * b)
                doc.append(Math(data=[NoEscape(fr"a = \frac{{A_s f_y}}{{0.85 f'_c b}} = \frac{{{bot_area:.1f} \times {fy}}}{{0.85 \times {fc} \times {b}}} = {a_bot:.2f} \text{{ mm}}")]))
                doc.append(Math(data=[NoEscape(fr"\phi M_n^+ = \phi A_s f_y \left(d - \frac{{a}}{{2}}\right) = 0.90 \times {bot_area:.1f} \times {fy} \times \left({d} - \frac{{{a_bot:.2f}}}{{2}}\right) \times 10^{{-6}} = {res.moment_capacity_bot:.1f} \text{{ kN-m}}")]))

            doc.append(NoEscape(r'\vspace*{1em}'))
            doc.append(NoEscape(r'\\'))
            doc.append(bold("Shear and Torsion"))
            doc.append(NoEscape(r'\vspace*{0.5em}'))
            doc.append(NoEscape(r'\\'))
            s_val = res.reinforcement.stirrup_spacing_hinge if "Support" in title else res.reinforcement.stirrup_spacing
            doc.append(NoEscape(fr"Transverse reinforcement: {res.reinforcement.stirrups} @ {s_val:.0f} mm spacing."))
            
            # Parse stirrup legs and size
            s_str = res.reinforcement.stirrups
            if "-leg " in s_str:
                parts = s_str.split('-leg ')
                legs = int(parts[0])
                s_size = parts[1]
            else:
                legs = 2
                s_size = s_str
            
            av = legs * aci_tool.get_bar_area(s_size)
            fyt = data.fyt
            phi_v = 0.75
            
            doc.append(NoEscape(r'\\'))
            vc = 0.17 * math.sqrt(fc) * b * d / 1000.0
            doc.append(Math(data=[NoEscape(fr"V_c = 0.17 \sqrt{{f'_c}} b_w d = 0.17 \times \sqrt{{{fc}}} \times {b} \times {d} \times 10^{{-3}} = {vc:.1f} \text{{ kN}}")]))
            
            vs = (av * fyt * d / s_val) / 1000.0
            doc.append(Math(data=[NoEscape(fr"V_s = \frac{{A_v f_{{yt}} d}}{{s}} = \frac{{{av:.1f} \times {fyt} \times {d}}}{{{s_val:.0f}}} \times 10^{{-3}} = {vs:.1f} \text{{ kN}}")]))
            
            doc.append(Math(data=[NoEscape(fr"\phi V_n = \phi (V_c + V_s) = 0.75 \times ({vc:.1f} + {vs:.1f}) = {res.shear_capacity:.1f} \text{{ kN}}")]))

            if res.reinforcement.torsion_required:
                doc.append(NoEscape(r'\\'))
                doc.append(bold("Torsion Capacity:"))
                phi_t = 0.75
                # Recalculate torsion properties for display
                db_s = aci_tool.get_bar_diameter(s_size)
                cover = 40.0 # From beam.py
                x1 = b - 2*cover - db_s
                y1 = data.height - 2*cover - db_s
                aoh = x1 * y1
                ao = 0.85 * aoh
                at = aci_tool.get_bar_area(s_size) # area of one leg for torsion
                
                doc.append(Math(data=[NoEscape(fr"A_o = 0.85 A_{{oh}} = 0.85 \times ({x1:.0f} \times {y1:.0f}) = {ao:.1f} \text{{ mm}}^2")]))
                doc.append(Math(data=[NoEscape(fr"\phi T_n = \phi \frac{{2 A_o A_t f_{{yt}}}}{{s}} \cot \theta = 0.75 \times \frac{{2 \times {ao:.1f} \times {at:.1f} \times {fyt}}}{{{s_val:.0f}}} \times 1.0 \times 10^{{-6}} = {res.torsion_capacity:.1f} \text{{ kN-m}}")]))

            doc.append(NoEscape(fr"\textbf{{Utilization Ratio:}} {res.utilization_ratio:.2f}"))
            
            # Visualization
            doc.append(NoEscape(r'\vspace*{1em}'))
            with doc.create(Figure(position='h!')) as fig:
                fig.append(NoEscape(draw_section_tikz(data.width, data.height, res, title)))
                fig.add_caption(fr"Reinforcement Detail - {title}")
            
    with doc.create(Section("Design Calculations")):
        section_report("Left Support", {
            "mu_neg": data.left_mu_neg, "mu_pos": data.left_mu_pos, "vu": data.left_vu, "tu": data.left_tu
        }, res_left)
        
        section_report("Midspan", {
            "mu_neg": data.mid_mu_neg, "mu_pos": data.mid_mu_pos, "vu": data.mid_vu, "tu": data.mid_tu
        }, res_mid)
        
        section_report("Right Support", {
            "mu_neg": data.right_mu_neg, "mu_pos": data.right_mu_pos, "vu": data.right_vu, "tu": data.right_tu
        }, res_right)

    # Detailed Code Checks Section
    with doc.create(Section("Design and Detailing Checks")):
        is_smf = (data.frame_system == "special")
        is_seismic = data.sdc in ["D", "E", "F"]
        
        with doc.create(Subsection("Dimensional Checks")):
            with doc.create(Itemize()) as itemize:
                # Span to Depth
                l_d_ratio = data.clear_span / data.effective_depth if data.effective_depth > 0 else 0
                l_d_status = "PASS" if not is_smf or l_d_ratio >= 4.0 else "FAIL"
                itemize.add_item(NoEscape(fr"Clear Span to Eff. Depth ($L_n/d$): {l_d_ratio:.2f} $\ge$ 4.0 (Req. for SMF): \textbf{{{l_d_status}}}"))
                
                # Width limits
                w_status = "PASS" if not is_smf or data.width >= 250 else "FAIL"
                itemize.add_item(NoEscape(fr"Beam Width ($b_w$): {data.width} mm $\ge$ 250 mm: \textbf{{{w_status}}}"))
                
                # b/h ratio
                bh_ratio = data.width / data.height if data.height > 0 else 0
                bh_status = "PASS" if not is_smf or bh_ratio >= 0.3 else "FAIL"
                itemize.add_item(NoEscape(fr"Width to Height Ratio ($b_w/h$): {bh_ratio:.2f} $\ge$ 0.3: \textbf{{{bh_status}}}"))

        with doc.create(Subsection("Reinforcement Detailing Checks")):
            rho_min = max(1.4 / data.fy, 0.25 * math.sqrt(data.fc_prime) / data.fy)
            rho_max = 0.025 if is_smf else 0.04 # 0.025 limit for SMF
            
            def check_rho(area, label):
                rho = area / (data.width * data.effective_depth)
                status = "PASS" if rho_min <= rho <= rho_max else "FAIL"
                return NoEscape(fr"{label} Reinforcement Ratio $\rho$: {rho:.4f} (Limits: {rho_min:.4f} to {rho_max:.4f}): \textbf{{{status}}}")

            with doc.create(Itemize()) as itemize:
                itemize.add_item(check_rho(res_mid.reinforcement.bottom_area, "Midspan Bottom (Positive)"))
                itemize.add_item(check_rho(res_left.reinforcement.top_area, "Support Top (Negative)"))
                
                # Continuous bar check
                cont_status = "PASS" if len(res_mid.reinforcement.top_bars) >= 2 and len(res_mid.reinforcement.bottom_bars) >= 2 else "FAIL"
                itemize.add_item(NoEscape(fr"Continuous Bars (Top and Bottom): $\ge$ 2 bars: \textbf{{{cont_status}}}"))

        if is_smf:
            with doc.create(Subsection("Seismic Capacity Checks (ACI 18.6)")):
                with doc.create(Itemize()) as itemize:
                    # Joint capacity: Pos Mn >= 0.5 Neg Mn
                    ratio_l = res_left.moment_capacity_bot / res_left.moment_capacity_top if res_left.moment_capacity_top > 0 else 0
                    stat_l = "PASS" if ratio_l >= 0.5 else "FAIL"
                    itemize.add_item(NoEscape(fr"Left Joint Flexural Ratio ($\phi M_n^+ / \phi M_n^-$): {ratio_l:.2f} $\ge$ 0.50: \textbf{{{stat_l}}}"))
                    
                    ratio_r = res_right.moment_capacity_bot / res_right.moment_capacity_top if res_right.moment_capacity_top > 0 else 0
                    stat_r = "PASS" if ratio_r >= 0.5 else "FAIL"
                    itemize.add_item(NoEscape(fr"Right Joint Flexural Ratio ($\phi M_n^+ / \phi M_n^-$): {ratio_r:.2f} $\ge$ 0.50: \textbf{{{stat_r}}}"))
                    
                    # Midspan capacity ratio
                    max_joint = max(res_left.moment_capacity_top, res_right.moment_capacity_top)
                    ratio_mid = res_mid.moment_capacity_bot / max_joint if max_joint > 0 else 0
                    stat_mid = "PASS" if ratio_mid >= 0.25 else "FAIL"
                    itemize.add_item(NoEscape(fr"Midspan to Joint Capacity Ratio: {ratio_mid:.2f} $\ge$ 0.25: \textbf{{{stat_mid}}}"))
    
    if defl_data:
        is_cant = defl_data.get('is_cantilever', False)
        loc = defl_data.get('defl_location', 'midspan')
        
        with doc.create(Section("Serviceability and Deflection (ACI 318M-25)")):
            if is_cant:
                doc.append(NoEscape(fr"Cantilever beam detected. Deflection calculated at the {loc}."))
                doc.append(NoEscape(r"\\"))
                doc.append(NoEscape(r"Per ACI 318 Table 24.2.3.6b: $I_e$ evaluated at the support (fixed end)."))
            else:
                doc.append(NoEscape(r"Calculations based on the midspan section properties and service load demands."))
            doc.append(NoEscape(r"\vspace{0.5em}"))
            doc.append(NoEscape(r"\\"))
            
            with doc.create(Subsection("Cracking and Inertia Properties")):
                fr = 0.62 * math.sqrt(data.fc_prime)
                doc.append(Math(data=[NoEscape(fr"f_r = 0.62 \sqrt{{f'_c}} = 0.62 \times \sqrt{{{data.fc_prime}}} = {fr:.2f} \text{{ MPa}}")]))
                
                ig = defl_data['I_g']
                yt = data.height / 2.0
                mcr = (fr * ig / yt) / 1e6
                doc.append(Math(data=[NoEscape(fr"M_{{cr}} = \frac{{f_r I_g}}{{y_t}} = \frac{{{fr:.2f} \times {ig/1e6:.0f}\times 10^6}}{{{yt:.1f}}} \times 10^{{-6}} = {mcr:.1f} \text{{ kN-m}}")]))
                
                icr = defl_data['I_cr']
                icr_note = " (fixed-end)" if is_cant else " (midspan)"
                doc.append(Math(data=[NoEscape(fr"I_{{cr}}{icr_note} = {icr/1e6:.0f} \times 10^6 \text{{ mm}}^4")]))

                ma = defl_data.get('M_a', mcr * 1.5) # Fallback if Ma not passed
                doc.append(NoEscape(fr"Effective Inertia $I_e$ for $M_a = {ma:.1f}$ kN-m:"))
                
                ie = defl_data['I_e']
                doc.append(Math(data=[NoEscape(r"I_e = \frac{I_{cr}}{1 - \left( \frac{(2/3) M_{cr}}{M_a} \right)^2 \left( 1 - \frac{I_{cr}}{I_g} \right)} \leq I_g")]))
                doc.append(Math(data=[NoEscape(fr"I_e = {ie/1e6:.0f} \times 10^6 \text{{ mm}}^4")]))

            with doc.create(Subsection("Deflection Results")):
                ec = mat_props.ec
                l_defl = data.length
                if is_cant:
                    doc.append(NoEscape(fr"Free-end deflection via Simpson's rule:"))
                    doc.append(Math(data=[NoEscape(r"\delta_{tip} = \frac{L^2}{6 \, E_c \, I_e} \left( 2 \, M_{mid} + M_{fixed} \right)")]))
                else:
                    doc.append(NoEscape(r"Midspan deflection via Simpson's rule:"))
                    doc.append(Math(data=[NoEscape(r"\delta_{mid} = \frac{L^2}{96 \, E_c \, I_e} \left( M_A + 10 \, M_C + M_B \right)")]))
                
                doc.append(Math(data=[NoEscape(fr"\Delta_L = {defl_data['delta_live']:.2f} \text{{ mm}} \quad (Limit: {defl_data['lim_live']:.1f} \text{{ mm}}) ")]))
                doc.append(Math(data=[NoEscape(fr"\Delta_{{long}} = {defl_data['delta_long']:.2f} \text{{ mm}} \quad (Limit: {defl_data['lim_long']:.1f} \text{{ mm}}) ")]))
                
                status = "PASS" if defl_data['delta_live'] <= defl_data['lim_live'] and defl_data['delta_long'] <= defl_data['lim_long'] else "FAIL"
                doc.append(bold(fr"Deflection Status: {status}"))
    
    # Save PDF
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "beam_report")
    doc.generate_pdf(filepath, clean_tex=False)
    
    # Read bytes
    with open(filepath + ".pdf", "rb") as f:
        pdf_bytes = f.read()
        
    return pdf_bytes
