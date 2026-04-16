# -*- coding: utf-8 -*-
"""
RC Column Designer – User Manual Generator
Produces a standalone PDF user manual using PyLaTeX.
"""

import os
import tempfile
from pylatex import (Document, Section, Subsection, Subsubsection,
                     Command, NoEscape, PageStyle, Head, Foot, Tabular,
                     Itemize, Enumerate, LongTable)
from pylatex.utils import bold, italic


def _eq(latex_str: str) -> NoEscape:
    return NoEscape(r'\[' + latex_str + r'\]')


def _ineq(latex_str: str) -> NoEscape:
    return NoEscape(r'\(' + latex_str + r'\)')


def generate_column_manual() -> bytes:
    """Return the user-manual PDF as raw bytes."""

    geometry_options = {
        "margin": "1in",
        "headheight": "42pt",
        "includeheadfoot": True,
        "a4paper": True,
    }
    doc = Document(geometry_options=geometry_options)

    # ------------------------------------------------------------------ preamble
    doc.preamble.append(NoEscape(r'\usepackage{amsmath}'))
    doc.preamble.append(NoEscape(r'\usepackage{amssymb}'))
    doc.preamble.append(NoEscape(r'\usepackage{booktabs}'))
    doc.preamble.append(NoEscape(r'\usepackage{array}'))
    doc.preamble.append(NoEscape(r'\usepackage{xcolor}'))
    doc.preamble.append(NoEscape(r'\usepackage{tcolorbox}'))
    doc.preamble.append(NoEscape(r'\usepackage{enumitem}'))
    doc.preamble.append(NoEscape(r'\usepackage{hyperref}'))
    doc.preamble.append(NoEscape(r'\usepackage{fancyhdr}'))
    doc.preamble.append(NoEscape(r'\usepackage{titlesec}'))
    doc.preamble.append(NoEscape(
        r'\definecolor{acipink}{RGB}{219,39,119}'
        r'\definecolor{aciblue}{RGB}{37,99,235}'
        r'\definecolor{acigray}{RGB}{107,114,128}'
        r'\definecolor{noteboxbg}{RGB}{255,251,235}'
        r'\definecolor{noteboxborder}{RGB}{217,119,6}'
    ))
    doc.preamble.append(NoEscape(
        r'\tcbuselibrary{skins,breakable}'
        r'\newtcolorbox{notebox}[1][Note]{'
        r'  breakable, enhanced,'
        r'  colback=noteboxbg, colframe=noteboxborder,'
        r'  fonttitle=\bfseries, title=#1,'
        r'  left=4pt, right=4pt, top=4pt, bottom=4pt'
        r'}'
    ))
    doc.preamble.append(NoEscape(
        r'\pagestyle{fancy}'
        r'\fancyhf{}'
        r'\fancyhead[L]{\textcolor{acigray}{\small RC Column Designer --- User Manual}}'
        r'\fancyhead[R]{\textcolor{acigray}{\small ACI 318M-25}}'
        r'\fancyfoot[C]{\thepage}'
        r'\renewcommand{\headrulewidth}{0.4pt}'
    ))
    doc.preamble.append(NoEscape(
        r'\titleformat{\section}{\large\bfseries\color{aciblue}}{}{0em}{}'
        r'\titleformat{\subsection}{\normalsize\bfseries\color{acipink}}{}{0em}{}'
        r'\titleformat{\subsubsection}{\normalsize\bfseries\color{acigray}}{}{0em}{}'
    ))

    # ------------------------------------------------------------------ title page
    doc.append(NoEscape(r'\begin{center}'))
    doc.append(NoEscape(r'{\Huge \textbf{\textcolor{aciblue}{RC Column Designer}}}\\[0.5em]'))
    doc.append(NoEscape(r'{\Large \textbf{User Manual}}\\[0.3em]'))
    doc.append(NoEscape(r'{\large \textcolor{acigray}{ACI 318M-25 Compliant Design Module}}\\[0.2em]'))
    doc.append(NoEscape(r'{\normalsize Version 0.8.1 beta \quad \textcolor{acigray}{---} \quad April 2026}'))
    doc.append(NoEscape(r'\end{center}'))
    doc.append(NoEscape(r'\vspace{2em}'))
    doc.append(NoEscape(r'\hrule'))
    doc.append(NoEscape(r'\vspace{1.5em}'))

    # ===================================================================
    # 1. OVERVIEW
    # ===================================================================
    with doc.create(Section('Overview')):
        doc.append(NoEscape(
            r'The \textbf{RC Column Designer} is a web-based structural engineering tool that performs '
            r'strength design of reinforced concrete columns in full compliance with '
            r'\textbf{ACI 318M-25} (\textit{Building Code Requirements for Structural Concrete}). '
            r'The module supports rectangular (tied) and circular (tied or spiral) cross-sections '
            r'under combined biaxial bending and axial force, with optional seismic provisions for '
            r'Ordinary (OMF), Intermediate (IMF), and Special Moment Frames (SMF).'
        ))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(r'\textbf{Design outputs include:}'))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Longitudinal reinforcement selection from P-M interaction'))
            lst.add_item(NoEscape(r'Transverse reinforcement: ties (rectangular/circular) or spiral'))
            lst.add_item(NoEscape(r'Slenderness magnification per ACI 318M-25 \S6.6.4'))
            lst.add_item(NoEscape(r'Biaxial P-M interaction check (Bresler load contour method)'))
            lst.add_item(NoEscape(r'Shear capacity in both x and y directions'))
            lst.add_item(NoEscape(r'Confinement (SMF): hoop/spiral requirements per ACI 318M-25 \S18.7.5'))
            lst.add_item(NoEscape(r'Capacity design shear per ACI 318M-25 \S18.7.6 (SMF only)'))
            lst.add_item(NoEscape(r'Seismic joint checks: strong-column-weak-beam and joint shear (SDC D--F, SMF)'))
            lst.add_item(NoEscape(r'Beam projection check per ACI 318M-25 \S18.8.2.3'))
            lst.add_item(NoEscape(r'Quantity take-off (concrete volume, formwork area, rebar weight)'))
            lst.add_item(NoEscape(r'Detailed PDF calculation report'))

    # ===================================================================
    # 2. SCOPE & LIMITATIONS
    # ===================================================================
    with doc.create(Section('Scope and Limitations')):
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Rectangular and circular sections supported; T-shaped or L-shaped columns are not.'))
            lst.add_item(NoEscape(r'Normal-weight concrete assumed (\(\lambda = 1.0\)).'))
            lst.add_item(NoEscape(r'Forces are entered directly as factored demands '
                                  r'(\(P_u\), \(M_{ux}\), \(M_{uy}\), \(V_{ux}\), \(V_{uy}\)); '
                                  r'no load-combination engine is included.'))
            lst.add_item(NoEscape(r'Separate top and bottom moments/shears are accepted; '
                                  r'the governing (maximum absolute) values are used for design.'))
            lst.add_item(NoEscape(r'Slenderness is evaluated about both axes; the governing axis is used '
                                  r'for moment magnification.'))
            lst.add_item(NoEscape(r'Biaxial bending is checked via the Bresler load contour method '
                                  r'(non-dimensional interaction with exponent \(\alpha = 1.15\)).'))
            lst.add_item(NoEscape(r'Seismic joint checks (strong-column-weak-beam and joint shear) '
                                  r'apply only to SDC D, E, or F with Special Moment Frame selected.'))
            lst.add_item(NoEscape(r'The module checks only the top joint of the column. '
                                  r'Bottom joint should be checked by the column below.'))

    # ===================================================================
    # 3. INPUT PARAMETERS
    # ===================================================================
    with doc.create(Section('Input Parameters')):

        with doc.create(Subsection('Geometry')):
            doc.append(NoEscape(r'All dimensions are entered in \textbf{millimetres (mm)}.'))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{4.5cm} p{2cm} p{7cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    ('Column shape', '---',
                     r'Rectangular or Circular. Circular columns require only a diameter.'),
                    ('Column type', '---',
                     r'Tied (closed hoops) or Spiral (continuous helical reinforcement). '
                     r'Rectangular columns must be Tied.'),
                    ('Width along x / Diameter', 'mm',
                     r'For rectangular: cross-section dimension parallel to x-axis. '
                     r'For circular: overall diameter \(D\).'),
                    ('Width along y', 'mm',
                     r'For rectangular columns only: cross-section dimension parallel to y-axis.'),
                    (r'Floor-to-floor height \(H\)', 'mm',
                     r'Total column height from floor to floor.'),
                    (r'Clear height \(l_u\)', 'mm',
                     r'Unsupported (clear) height between lateral restraints. '
                     r'Used for slenderness evaluation.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

        with doc.create(Subsection('Materials')):
            with doc.create(LongTable('p{4.5cm} p{2cm} p{7cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r"\(f'_c\)", 'MPa', r'Specified concrete compressive strength.'),
                    (r'\(f_y\)', 'MPa', r'Yield strength of longitudinal (main) reinforcement.'),
                    (r'\(f_{yt}\)', 'MPa', r'Yield strength of transverse reinforcement (ties or spiral).'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()
            doc.append(NoEscape(r'\smallskip'))
            doc.append(NoEscape(
                r'The elastic modulus of concrete is computed internally per ACI 318M-25 Eq.\,(19.2.2.1b): '
            ))
            doc.append(_eq(r"E_c = 4700\,\sqrt{f'_c} \quad [\mathrm{MPa}]"))

        with doc.create(Subsection('Seismic Classification')):
            with doc.create(LongTable('p{4.5cm} p{9cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Description')])
                tbl.add_hline()
                rows = [
                    ('Seismic Design Category',
                     r'ACI/ASCE classification A through F. SDC D--F triggers SMF provisions '
                     r'when frame system is Special.'),
                    ('Frame System',
                     r'\textbf{Ordinary (OMF)} --- no special seismic provisions. '
                     r'\textbf{Intermediate (IMF)} --- intermediate ductility. '
                     r'\textbf{Special (SMF)} --- full ACI 18.7 and 18.8 provisions activated.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()

        with doc.create(Subsection('Preferred Reinforcement Sizes')):
            with doc.create(Itemize()) as lst:
                lst.add_item(NoEscape(
                    r'\textbf{Main bar diameter}: preferred longitudinal bar size (D10--D36). '
                    r'The solver selects the minimum number of bars of this size to satisfy '
                    r'the reinforcement ratio and P-M interaction requirements.'))
                lst.add_item(NoEscape(
                    r'\textbf{Tie/Spiral diameter}: preferred transverse bar size (D10--D36). '
                    r'The solver upsizes only if strength demands cannot be met with the preferred size.'))

        with doc.create(Subsection('Applied Forces')):
            doc.append(NoEscape(
                r'All forces are \textbf{factored (LRFD)} demands. '
                r'Top and bottom moments and shears are entered separately; '
                r'the program uses the governing (larger absolute) value for design.'
            ))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{3.5cm} p{2cm} p{8.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Symbol'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'\(P_u\)', 'kN', r'Factored axial force (compression positive).'),
                    (r'\(M_{ux}\) (top/bot)', r'kN\(\cdot\)m',
                     r'Factored moment about the x-axis at column top and bottom.'),
                    (r'\(M_{uy}\) (top/bot)', r'kN\(\cdot\)m',
                     r'Factored moment about the y-axis at column top and bottom.'),
                    (r'\(V_{ux}\) (top/bot)', 'kN',
                     r'Factored shear force in the x-direction at column top and bottom.'),
                    (r'\(V_{uy}\) (top/bot)', 'kN',
                     r'Factored shear force in the y-direction at column top and bottom.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

    # ===================================================================
    # 4. DESIGN METHODOLOGY
    # ===================================================================
    with doc.create(Section('Design Methodology')):

        # -------------------------------------------------------------- 4.1 Slenderness
        with doc.create(Subsection('Slenderness Check — ACI 318M-25 §6.2.5')):
            doc.append(NoEscape(
                r'The slenderness ratio \(kl_u/r\) is computed about both axes. '
                r'For rectangular sections, the radius of gyration is:'
            ))
            doc.append(_eq(r'r_x = \frac{b}{2\sqrt{3}}, \qquad r_y = \frac{h}{2\sqrt{3}}'))
            doc.append(NoEscape(r'For circular sections:'))
            doc.append(_eq(r'r = \frac{D}{4}'))
            doc.append(NoEscape(
                r'The effective length factor \(k = 1.0\) is assumed (sway frame, conservative). '
                r'If \(kl_u/r \leq 22\), slenderness effects may be neglected '
                r'(ACI 318M-25 \S6.2.5). Otherwise, moment magnification is applied.'
            ))

            with doc.create(Subsubsection('Moment Magnification — ACI 318M-25 §6.6.4')):
                doc.append(NoEscape(
                    r'The magnified moment is \(\delta_{ns}\,M_{u}\), where the non-sway '
                    r'magnification factor \(\delta_{ns}\) is:'
                ))
                doc.append(_eq(
                    r'\delta_{ns} = \frac{C_m}{1 - P_u / (0.75\,P_c)} \geq 1.0'
                ))
                doc.append(NoEscape(r'with \(C_m = 0.6\) (assumed uniform moment) and:'))
                doc.append(_eq(
                    r'P_c = \frac{\pi^2 EI}{(kl_u)^2}, \qquad '
                    r'EI = \frac{0.4\,E_c\,I_g}{1 + \beta_{dns}}'
                ))
                doc.append(NoEscape(r'\(\beta_{dns} = 0.6\) (sustained load ratio). '
                                    r'If \(P_u \geq 0.75\,P_c\), the section is critically slender and '
                                    r'must be enlarged.'))

        # -------------------------------------------------------------- 4.2 Longitudinal Reinforcement
        with doc.create(Subsection('Longitudinal Reinforcement — P-M Interaction')):

            with doc.create(Subsubsection('Reinforcement Ratio Limits')):
                doc.append(NoEscape(r'Per ACI 318M-25 \S10.6.1.1:'))
                doc.append(_eq(r'0.01 \leq \rho_g \leq 0.08'))
                doc.append(NoEscape(
                    r'For SMF columns the upper limit is reduced to 0.06 '
                    r'(ACI 318M-25 \S18.7.4.1) to ensure adequate ductility.'
                ))

            with doc.create(Subsubsection('Axial Capacity')):
                doc.append(NoEscape(r'The maximum nominal axial strength is (ACI 318M-25 Eq.\,22.4.2.1):'))
                doc.append(_eq(
                    r"P_o = 0.85\,f'_c\,(A_g - A_{st}) + f_y\,A_{st}"
                ))
                doc.append(NoEscape(r'The maximum usable strength accounting for accidental eccentricity:'))
                doc.append(_eq(
                    r'P_{n,\max} = \begin{cases} 0.80\,P_o & \text{tied} \\ 0.85\,P_o & \text{spiral} \end{cases}'
                ))
                doc.append(NoEscape(r'Applied strength reduction factor \(\varphi = 0.65\) (tied) or \(0.75\) (spiral).'))

            with doc.create(Subsubsection('Biaxial P-M Check — Bresler Load Contour')):
                doc.append(NoEscape(
                    r'Biaxial bending is evaluated using the Bresler load contour method. '
                    r'The nominal moment capacities \(M_{nx}\) and \(M_{ny}\) are computed '
                    r'from the full fibre-by-fibre interaction diagram at the applied axial load \(P_u\). '
                    r'The interaction criterion is:'
                ))
                doc.append(_eq(
                    r'\left(\frac{M_{ux}}{\varphi M_{nx}}\right)^\alpha + '
                    r'\left(\frac{M_{uy}}{\varphi M_{ny}}\right)^\alpha \leq 1.0, '
                    r'\qquad \alpha = 1.15'
                ))
                doc.append(NoEscape(
                    r'The reported \textbf{P-M Interaction Ratio} is the equivalent uniaxial DCR '
                    r'back-calculated from the Bresler sum.'
                ))

        # -------------------------------------------------------------- 4.3 Shear
        with doc.create(Subsection('Shear Design — ACI 318M-25 §22.5')):
            doc.append(NoEscape(
                r'Shear capacity is checked independently in the x and y directions. '
                r'The effective depth \(d\) for each direction is:'
            ))
            doc.append(_eq(
                r'd_{x} = h - c_c - d_{\mathrm{tie}} - d_{b,\mathrm{main}}/2, \qquad '
                r'd_{y} = b - c_c - d_{\mathrm{tie}} - d_{b,\mathrm{main}}/2'
            ))
            doc.append(NoEscape(r'Concrete shear contribution (ACI 318M-25 \S22.5.5.1):'))
            doc.append(_eq(
                r"V_c = \left[0.17\,\lambda\,\sqrt{f'_c} + \frac{N_u}{6\,A_g}\right] b\,d"
            ))
            doc.append(NoEscape(
                r'where \(N_u / A_g\) is the average compressive stress (\(N_u = P_u\) in kN). '
                r'\(\varphi_V = 0.75\).'
            ))
            doc.append(NoEscape(r'\medskip'))
            doc.append(NoEscape(r'Steel shear contribution:'))
            doc.append(_eq(
                r'V_s = \frac{n_{\mathrm{legs}}\,A_v\,f_{yt}\,d}{s}'
            ))

            with doc.create(Subsubsection('SMF Capacity Design Shear — ACI 318M-25 §18.7.6')):
                doc.append(NoEscape(
                    r'For SMF columns, the design shear \(V_e\) is the greater of the factored shear '
                    r'and the capacity-design shear from probable moment capacities:'
                ))
                doc.append(_eq(
                    r'V_e = \max\!\left(V_u,\; \frac{2\,M_{pr}}{l_u}\right)'
                ))
                doc.append(NoEscape(
                    r'where \(M_{pr}\) is the \textbf{probable moment capacity} computed '
                    r'with \(f_{y,pr} = 1.25\,f_y\) and \(\varphi = 1.0\). '
                    r'When the earthquake-induced shear component exceeds 50\,\% of \(V_e\) '
                    r"\textit{and} \(P_u < A_g f'_c / 20\), then \(V_c = 0\) "
                    r'(ACI 318M-25 \S18.7.6.2.1).'
                ))

        # -------------------------------------------------------------- 4.4 Confinement (SMF)
        with doc.create(Subsection('Confinement — ACI 318M-25 §18.7.5 (SMF only)')):
            doc.append(NoEscape(
                r'Within the confinement zone \(l_o\) from each end, the transverse '
                r'reinforcement must satisfy:'
            ))
            doc.append(_eq(
                r'l_o \geq \max\!\left(h_{\max},\; l_u/6,\; 450\,\mathrm{mm}\right)'
            ))
            doc.append(NoEscape(r'The required volumetric ratio for spiral columns (ACI 318M-25 Eq.\,18.7.5.4a):'))
            doc.append(_eq(
                r"\rho_s \geq \max\!\left(0.45\!\left(\frac{A_g}{A_{ch}}-1\right)\frac{f'_c}{f_{yt}},\;"
                r"0.12\,\frac{f'_c}{f_{yt}}\right)"
            ))
            doc.append(NoEscape(r'For rectangular tied columns (ACI 318M-25 Eq.\,18.7.5.3a):'))
            doc.append(_eq(
                r"A_{sh} \geq \max\!\left(0.3\,s\,b_c\!\left(\frac{A_g}{A_{ch}}-1\right)\frac{f'_c}{f_{yt}},\;"
                r"0.09\,s\,b_c\,\frac{f'_c}{f_{yt}}\right)"
            ))
            doc.append(NoEscape(r'Maximum spacing within \(l_o\) (ACI 318M-25 \S18.7.5.3):'))
            doc.append(_eq(
                r"s_o \leq \min\!\left(\frac{b_c}{4},\; 6\,d_{b,\mathrm{main}},\; s_o'\right), "
                r"\qquad s_o' = 100 + \frac{350 - h_x}{3} \in [100, 150]\,\mathrm{mm}"
            ))

    # ===================================================================
    # 5. SEISMIC JOINT CHECKS (SDC D–F, SMF)
    # ===================================================================
    with doc.create(Section('Seismic Joint Checks — ACI 318M-25 §18.8')):
        doc.append(NoEscape(
            r'When SDC D, E, or F is selected with a Special Moment Frame, the top joint of the '
            r'column is checked for (a) strong-column-weak-beam and (b) joint shear. '
            r'Users define up to four framing beams (two in each direction) and the column above.'
        ))

        with doc.create(Subsection('Strong-Column-Weak-Beam — ACI 318M-25 §18.7.3')):
            doc.append(NoEscape(
                r'The sum of column nominal moment strengths must exceed the sum of beam '
                r'nominal moment strengths at the joint:'
            ))
            doc.append(_eq(
                r'\sum M_{nc} \geq \frac{6}{5}\,\sum M_{nb}'
            ))
            doc.append(NoEscape(
                r'\(\sum M_{nc}\) is computed from the P-M interaction diagram of each column '
                r'(this column and the one above) at their respective axial loads. '
                r'\(\sum M_{nb}\) is the sum of nominal moment capacities (top and bottom) '
                r'of all beams framing into the joint in the direction being checked.'
            ))

        with doc.create(Subsection('Joint Shear — ACI 318M-25 §18.8.4')):
            doc.append(NoEscape(
                r'The factored joint shear \(V_j\) is computed from equilibrium considering '
                r'the probable tensile and compressive forces in the beam bars '
                r'and the column shear at the joint:'
            ))
            doc.append(_eq(
                r'V_j = T_{b1} + C_{b2} - V_{\mathrm{col}}'
            ))
            doc.append(NoEscape(
                r'where \(T_{b1} = 1.25\,f_y\,A_{s,\mathrm{top}}\) and '
                r'\(C_{b2} = 1.25\,f_y\,A_{s,\mathrm{bot}}\) for the two beams in the same direction.'
            ))
            doc.append(NoEscape(r'The nominal joint shear capacity (ACI 318M-25 \S18.8.4.1):'))
            doc.append(_eq(
                r"\varphi V_{nj} = \varphi\,\gamma\,\lambda\,\sqrt{f'_c}\,A_j, "
                r'\qquad \varphi = 0.85'
            ))
            doc.append(NoEscape(
                r'The confinement factor \(\gamma\) depends on the joint confinement condition '
                r'(number of beams confining the joint):'
            ))
            with doc.create(LongTable('p{4cm} p{9cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold(r'\(\gamma\)'), bold('Condition')])
                tbl.add_hline()
                tbl.add_row([NoEscape(r'2.4'), NoEscape(r'Joint confined on all four faces')])
                tbl.add_row([NoEscape(r'2.0'), NoEscape(r'Joint confined on three faces or two opposite faces')])
                tbl.add_row([NoEscape(r'1.5'), NoEscape(r'Other cases')])
                tbl.add_hline()

        with doc.create(Subsection('Beam Projection Check — ACI 318M-25 §18.8.2.3')):
            doc.append(NoEscape(
                r'When a beam is offset from the column centreline, the beam must not project '
                r'beyond the column face by more than:'
            ))
            doc.append(_eq(
                r'\mathrm{proj}_{\max} = \min\!\left(\frac{c_2}{4},\; 100\,\mathrm{mm}\right)'
            ))
            doc.append(NoEscape(
                r'where \(c_2\) is the column dimension perpendicular to the framing direction '
                r'of the beam. A violation is flagged in the Design Notes.'
            ))

    # ===================================================================
    # 6. INTERPRETING DESIGN RESULTS
    # ===================================================================
    with doc.create(Section('Interpreting Design Results')):

        with doc.create(Subsection('Section Diagrams')):
            with doc.create(Itemize()) as lst:
                lst.add_item(NoEscape(
                    r'\textbf{Cross-section view}: Blue filled circles represent longitudinal bars. '
                    r'Red dashed line/circle = tie hoops (rectangular or circular). '
                    r'For spiral columns, the spiral is shown as a solid red circle (cross-section cut). '
                    r'Interior red dashed lines = cross-tie legs (rectangular columns).'))
                lst.add_item(NoEscape(
                    r'\textbf{Elevation view}: Three vertical blue lines = longitudinal bars. '
                    r'Horizontal red lines = confinement zone ties/spiral; '
                    r'gray lines = midheight ties. '
                    r'For spiral columns, the elevation shows a zigzag (helix) pattern. '
                    r'Red bracket annotations indicate the confinement length \(l_o\).'))

        with doc.create(Subsection('Design Checks (DCR)')):
            with doc.create(LongTable('p{4cm} p{9cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Check'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'P-M interaction', r'Bresler biaxial interaction ratio. Must be \(\leq 1.00\).'),
                    (r'Shear (x / y)', r'Shear utilization in each principal direction. Must be \(\leq 1.00\).'),
                    (r'\(\Sigma M_{nc}/\Sigma M_{nb}\)', r'Strong-column-weak-beam ratio. Must be \(\geq 1.20\) (SMF).'),
                    (r'Joint shear DCR', r'\(V_j / \varphi V_{nj}\). Must be \(\leq 1.00\) (SMF).'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()

        with doc.create(Subsection('Reinforcement Details')):
            with doc.create(Itemize()) as lst:
                lst.add_item(NoEscape(
                    r'\textbf{Vertical bars}: number and size of longitudinal reinforcement.'))
                lst.add_item(NoEscape(
                    r'\textbf{Ties/Spiral (support zone)}: transverse reinforcement within the '
                    r'confinement length \(l_o\) at each end. Shown in the cross-section diagram '
                    r'and elevation diagram in red.'))
                lst.add_item(NoEscape(
                    r'\textbf{Ties/Spiral (midheight)}: transverse reinforcement outside the '
                    r'confinement zone. Shown in gray in the elevation diagram.'))

        with doc.create(Subsection('Design Notes')):
            doc.append(NoEscape(
                r'The \textit{Design Notes} panel summarises design decisions and warnings. '
                r'Entries prefixed with \textbf{Violation} or \textbf{CRITICAL} indicate '
                r'checks that failed and must be resolved by revising the geometry or loads. '
                r'Informational entries (\(\triangleright\)) explain design choices made '
                r'automatically by the solver.'
            ))

    # ===================================================================
    # 7. QUANTITY TAKE-OFF
    # ===================================================================
    with doc.create(Section('Quantity Take-Off')):
        doc.append(NoEscape(
            r'The QTO section reports estimated material quantities per column for procurement:'
        ))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(
                r'\textbf{Concrete volume}: \(V = A_g \times H\) (gross section area \(\times\) '
                r'floor-to-floor height).'))
            lst.add_item(NoEscape(
                r'\textbf{Formwork area}: perimeter of the cross-section \(\times\) '
                r'floor-to-floor height.'))
            lst.add_item(NoEscape(
                r'\textbf{Rebar weight}: individual bar lengths (including lap splices and '
                r'hooks where applicable) multiplied by unit weight.'))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(
            r'Rebar orders are expressed as the optimal combination of Philippine standard '
            r'stock lengths (6\,m, 7.5\,m, 9\,m, 10.5\,m, 12\,m) that minimises offcut waste.'
        ))

    # ===================================================================
    # 8. PDF REPORT
    # ===================================================================
    with doc.create(Section('Detailed PDF Report')):
        doc.append(NoEscape(
            r'Clicking \textbf{Generate Detailed Report} on the results page produces a '
            r'professionally formatted LaTeX-compiled PDF containing:'
        ))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Project header with name, location, engineer and date'))
            lst.add_item(NoEscape(r'Section 1: Material and geometry summary'))
            lst.add_item(NoEscape(r'Section 2: Reinforcement summary with cross-section and elevation TikZ diagrams'))
            lst.add_item(NoEscape(r'Section 3: Step-by-step design calculations (axial, slenderness, P-M, shear, confinement)'))
            lst.add_item(NoEscape(r'Section 4: Seismic joint checks (SMF SDC D--F only)'))
            lst.add_item(NoEscape(r'Section 5: Design checks summary table'))
            lst.add_item(NoEscape(r'Section 6: Design notes'))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(
            r'The cross-section TikZ diagram shows the actual bar arrangement. '
            r'For spiral columns the inner confinement boundary is shown as a solid circle; '
            r'for tied columns it is dashed. '
            r'The elevation TikZ diagram uses a zigzag line for spirals and horizontal lines for ties, '
            r'with red indicating the confinement zone and gray indicating the midheight zone.'
        ))

    # ===================================================================
    # 9. REFERENCES
    # ===================================================================
    with doc.create(Section('References')):
        with doc.create(Enumerate()) as lst:
            lst.add_item(NoEscape(
                r'ACI Committee 318. \textit{Building Code Requirements for Structural Concrete '
                r'(ACI 318M-25) and Commentary (ACI 318RM-25)}. American Concrete Institute, '
                r'Farmington Hills, MI, 2025.'))
            lst.add_item(NoEscape(
                r'ACI Committee 318. \textit{Appendix to ACI 318M-25 Metric SI Edition.} '
                r'American Concrete Institute, 2025.'))
            lst.add_item(NoEscape(
                r'Wight, J.\,K. \textit{Reinforced Concrete: Mechanics and Design}, 8th ed. '
                r'Pearson Education, 2023.'))
            lst.add_item(NoEscape(
                r'MacGregor, J.\,G. and Wight, J.\,K. \textit{Reinforced Concrete: Mechanics '
                r'and Design}, 7th ed. Prentice Hall, 2016.'))
            lst.add_item(NoEscape(
                r'Bresler, B. ``Design Criteria for Reinforced Columns Under Axial Load and '
                r"Biaxial Bending,'' \textit{ACI Journal}, 57(11), 1960."))

    # ------------------------------------------------------------------ compile
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, 'column_manual')
        doc.generate_pdf(tex_path, clean_tex=True, compiler='pdflatex',
                         compiler_args=['-interaction=nonstopmode'])
        pdf_path = tex_path + '.pdf'
        with open(pdf_path, 'rb') as f:
            return f.read()
