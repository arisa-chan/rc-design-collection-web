import os
import tempfile
from pylatex import Document, Section, Subsection, Math, Command, NoEscape, Head, Foot, PageStyle, Itemize
from pylatex.utils import bold

def generate_beam_report(data, mat_props, beam_geom, res_left, res_mid, res_right, defl_data=None):
    geometry_options = {"margin": "1in"}
    doc = Document(geometry_options=geometry_options)
    
    doc.preamble.append(NoEscape(r'\usepackage{amsmath}'))
    
    # Custom headers
    header = PageStyle("header")
    with header.create(Head("L")):
        header.append(bold("Project: "))
        header.append(data.proj_name + "\n")
        header.append(bold("Location: "))
        header.append(data.proj_loc)
    with header.create(Head("R")):
        header.append(bold("Engineer: "))
        header.append(data.proj_eng + "\n")
        header.append(bold("Date: "))
        header.append(data.proj_date)
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
    with doc.create(Section("Material & Geometry Parameters")):
        with doc.create(Itemize()) as itemize:
            itemize.add_item(NoEscape(fr"Concrete Strength, $f'_c = {data.fc_prime}$ MPa"))
            itemize.add_item(NoEscape(fr"Main Rebar Yield, $f_y = {data.fy}$ MPa"))
            itemize.add_item(NoEscape(fr"Stirrup Yield, $f_{{yt}} = {data.fyt}$ MPa"))
            itemize.add_item(NoEscape(fr"Beam Dimensions: Width $b_w = {data.width}$ mm, Height $h = {data.height}$ mm, Eff. Depth $d = {data.effective_depth}$ mm"))
            itemize.add_item(NoEscape(fr"Span Length: L = ${data.length}$ mm, Clear Span $L_n = {data.clear_span}$ mm"))
    
    def section_report(title, demands, res):
        with doc.create(Subsection(title)):
            doc.append(bold("Demands: "))
            doc.append(NoEscape(fr"$M_u^-$ = {demands['mu_neg']} kN-m | $M_u^+$ = {demands['mu_pos']} kN-m | $V_u$ = {demands['vu']} kN | $T_u$ = {demands['tu']} kN-m"))
            doc.append(NoEscape(r'\vspace*{1em}'))
            doc.append(NoEscape(r'\\'))

            doc.append(bold("Flexural Capacity Calculation"))
            # Left Top
            top_area = res.reinforcement.top_area
            bot_area = res.reinforcement.bottom_area
            
            top_bars = f"{len(res.reinforcement.top_bars)}x{res.reinforcement.top_bars[0]}" if res.reinforcement.top_bars else "None"
            bot_bars = f"{len(res.reinforcement.bottom_bars)}x{res.reinforcement.bottom_bars[0]}" if res.reinforcement.bottom_bars else "None"
            
            doc.append(NoEscape(r'\vspace*{0.5em}'))
            doc.append(NoEscape(r'\\'))
            doc.append(NoEscape(fr"Top Reinforcement: {top_bars} ($A_s$ = {top_area:.1f} mm$^2$)"))
            doc.append(NoEscape(r'\\'))
            doc.append(NoEscape(fr"Bottom Reinforcement: {bot_bars} ($A_s$ = {bot_area:.1f} mm$^2$)"))
            
            doc.append(Math(data=[NoEscape(r"\phi M_n = \phi A_s f_y \left(d - \frac{a}{2}\right)")]))
            doc.append(NoEscape(fr"Resulting capacity: top $\phi M_n^+$ = {res.moment_capacity_top:.1f} kN-m, bottom $\phi M_n^-$ = {res.moment_capacity_bot:.1f} kN-m."))
            
            doc.append(NoEscape(r'\vspace*{1em}'))
            doc.append(NoEscape(r'\\'))
            doc.append(bold("Shear and Torsion Calculation"))
            doc.append(NoEscape(r'\vspace*{0.5em}'))
            doc.append(NoEscape(r'\\'))
            s_val = res.reinforcement.stirrup_spacing_hinge if "Support" in title else res.reinforcement.stirrup_spacing
            doc.append(NoEscape(fr"Transverse Reinforcement: {res.reinforcement.stirrups} @ {s_val:.0f} mm spacing."))
            
            doc.append(Math(data=[NoEscape(r"\phi V_n = \phi \left(V_c + V_s\right), \quad V_s = \frac{A_v f_{yt} d}{s}")]))
            doc.append(NoEscape(fr"Resulting shear capacity, $\phi V_n$ = {res.shear_capacity:.1f} kN."))
            
            doc.append(Math(data=[NoEscape(r"\phi T_n = \phi \frac{2 A_o A_t f_{yt}}{s} \cot \theta")]))
            doc.append(NoEscape(fr"Resulting torsion capacity, $\phi T_n$ = {res.torsion_capacity:.1f} kN-m."))
            doc.append(NoEscape(r'\vspace*{1em}'))
            doc.append(NoEscape(r'\\'))
            doc.append(NoEscape(fr"\textbf{{Utilization Ratio:}} {res.utilization_ratio:.2f}"))
            
    with doc.create(Section("Section Detailed Calculations")):
        section_report("Left Support", {
            "mu_neg": data.left_mu_neg, "mu_pos": data.left_mu_pos, "vu": data.left_vu, "tu": data.left_tu
        }, res_left)
        
        section_report("Midspan", {
            "mu_neg": data.mid_mu_neg, "mu_pos": data.mid_mu_pos, "vu": data.mid_vu, "tu": data.mid_tu
        }, res_mid)
        
        section_report("Right Support", {
            "mu_neg": data.right_mu_neg, "mu_pos": data.right_mu_pos, "vu": data.right_vu, "tu": data.right_tu
        }, res_right)
    
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
                doc.append(NoEscape(r"Modulus of Rupture: $f_r = 0.62 \sqrt{f'_c}$"))
                doc.append(NoEscape(r"\\"))
                doc.append(NoEscape(fr"Cracking Moment: $M_{{cr}} = \frac{{f_r I_g}}{{y_t}} = {defl_data['M_cr']:.1f}$ kN-m"))
                doc.append(NoEscape(r"\\"))
                doc.append(NoEscape(fr"Gross Inertia: $I_g = {defl_data['I_g']/1e6:.0f} \times 10^6$ mm$^4$"))
                doc.append(NoEscape(r"\\"))
                icr_note = " (fixed-end section, hogging)" if is_cant else " (including compression steel)"
                doc.append(NoEscape(fr"Cracked Inertia: $I_{{cr}} = {defl_data['I_cr']/1e6:.0f} \times 10^6$ mm$^4${icr_note}"))
                doc.append(NoEscape(r"\\"))
                doc.append(NoEscape(fr"Effective Inertia $I_e$:"))
                doc.append(Math(data=[NoEscape(r"I_e = \frac{I_{cr}}{1 - \left( \frac{(2/3) M_{cr}}{M_a} \right)^2 \left( 1 - \frac{I_{cr}}{I_g} \right)} \leq I_g")]))
                doc.append(NoEscape(fr"Calculated $I_e = {defl_data['I_e']/1e6:.0f} \times 10^6$ mm$^4$"))

            with doc.create(Subsection("Deflection Results")):
                if is_cant:
                    doc.append(NoEscape(fr"Free-end deflection via Simpson's rule on M/EI diagram:"))
                    doc.append(Math(data=[NoEscape(r"\delta_{tip} = \frac{L^2}{6 \, E_c \, I_e} \left( 2 \, M_{mid} + M_{fixed} \right)")]))
                else:
                    doc.append(NoEscape(r"Midspan deflection via Simpson's rule on the moment diagram:"))
                    doc.append(Math(data=[NoEscape(r"\delta_{mid} = \frac{L^2}{96 \, E_c \, I_e} \left( M_A + 10 \, M_C + M_B \right)")]))
                    doc.append(NoEscape(r"where $M_A$, $M_B$ = service support moments (hogging $\rightarrow$ negative), $M_C$ = service midspan moment."))
                    doc.append(NoEscape(r"\\"))
                    if 'M_A_tot' in defl_data and 'M_B_tot' in defl_data:
                        doc.append(NoEscape(fr"Service support moments (total): $M_A = {defl_data['M_A_tot']:.2f}$ kN-m, $M_B = {defl_data['M_B_tot']:.2f}$ kN-m"))
                        doc.append(NoEscape(r"\\"))
                doc.append(NoEscape(fr"Immediate Live Load Deflection at {loc}: $\Delta_L = {defl_data['delta_live']:.2f}$ mm (Limit: $L/360 = {defl_data['lim_live']:.1f}$ mm)"))
                doc.append(NoEscape(r"\\"))
                doc.append(NoEscape(fr"Long-term Deflection at {loc}: $\Delta_{{long}} = {defl_data['delta_long']:.2f}$ mm (Limit: $L/240 = {defl_data['lim_long']:.1f}$ mm)"))
                doc.append(NoEscape(r"\\"))
                status = "PASS" if defl_data['delta_live'] <= defl_data['lim_live'] and defl_data['delta_long'] <= defl_data['lim_long'] else "FAIL"
                doc.append(bold(fr"Status: {status}"))
    
    # Save PDF
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "beam_report")
    doc.generate_pdf(filepath, clean_tex=False)
    
    # Read bytes
    with open(filepath + ".pdf", "rb") as f:
        pdf_bytes = f.read()
        
    return pdf_bytes
