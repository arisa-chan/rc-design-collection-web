# -*- coding: utf-8 -*-
"""
RC Isolated Footing Designer – User Manual Generator
Produces a standalone PDF user manual using PyLaTeX.
"""

import os
import tempfile
from pylatex import (Document, Section, Subsection, Subsubsection,
                     Command, NoEscape, PageStyle, Head, Foot, Tabular,
                     Itemize, Enumerate, LongTable, MiniPage, LineBreak)
from pylatex.utils import bold, italic


def _eq(latex_str: str) -> NoEscape:
    return NoEscape(r'\[' + latex_str + r'\]')


def _ineq(latex_str: str) -> NoEscape:
    return NoEscape(r'\(' + latex_str + r'\)')


def generate_footing_manual() -> bytes:
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
        r'\fancyhead[L]{\textcolor{acigray}{\small RC Isolated Footing Designer --- User Manual}}'
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
    doc.append(NoEscape(r'{\Huge \textbf{\textcolor{aciblue}{RC Isolated Footing Designer}}}\\[0.5em]'))
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
            r'The \textbf{RC Isolated Footing Designer} is a web-based structural engineering tool '
            r'that performs complete design and stability verification of rectangular isolated '
            r'(spread) footings in full compliance with \textbf{ACI 318M-25} '
            r'(\textit{Building Code Requirements for Structural Concrete}). '
            r'The module uses an \textbf{OpenSeesPy ShellMITC4} finite element model with '
            r'\textbf{compression-only (ENT) Winkler spring} supports to capture the '
            r'soil-structure interaction and determine the bearing pressure distribution, '
            r'bending moments, and shear forces throughout the footing.'
        ))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(r'\textbf{Design outputs include:}'))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Soil bearing pressure check (maximum and minimum)'))
            lst.add_item(NoEscape(r'Overturning stability check with factor of safety (x and y axes)'))
            lst.add_item(NoEscape(r'Sliding check using passive soil friction'))
            lst.add_item(NoEscape(r'One-way (beam) shear capacity check per ACI 318M-25 \S22.5'))
            lst.add_item(NoEscape(r'Two-way (punching) shear capacity check per ACI 318M-25 \S22.6'))
            lst.add_item(NoEscape(r'Bottom flexural reinforcement (x and y directions)'))
            lst.add_item(NoEscape(r'Top flexural reinforcement where negative moments occur'))
            lst.add_item(NoEscape(r'Column-to-footing dowel bars with development lengths'))
            lst.add_item(NoEscape(r'FEA contour plots: bearing pressure, settlement, bending moments, '
                                  r'shear forces, Wood-Armer design moments, and required steel area'))
            lst.add_item(NoEscape(r'Quantity take-off (concrete volume, formwork area, rebar weight)'))
            lst.add_item(NoEscape(r'Detailed PDF calculation report'))

    # ===================================================================
    # 2. SCOPE AND LIMITATIONS
    # ===================================================================
    with doc.create(Section('Scope and Limitations')):
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Isolated (individual) rectangular footings only. '
                                  r'Combined, strip, mat, and pile foundations are not supported.'))
            lst.add_item(NoEscape(r'Normal-weight concrete assumed (\(\lambda = 1.0\)).'))
            lst.add_item(NoEscape(r'Soil is modelled as a Winkler (spring) foundation with a constant '
                                  r'modulus of subgrade reaction \(k_s\). '
                                  r'Non-linear or cohesive soil behaviour is not modelled.'))
            lst.add_item(NoEscape(r'Springs are compression-only (ENT material); '
                                  r'uplift is captured by spring deactivation.'))
            lst.add_item(NoEscape(r'Allowable bearing pressure design (ASD for soil); '
                                  r'structural design uses LRFD factored loads (ACI 318M-25).'))
            lst.add_item(NoEscape(r'The column is modelled as a rigid spider (rigidLink) transferring '
                                  r'forces to the footing shell at the column footprint nodes. '
                                  r'Column flexibility is not modelled.'))
            lst.add_item(NoEscape(r'Rocking and liquefaction checks are outside the scope of this module.'))

    # ===================================================================
    # 3. INPUT PARAMETERS
    # ===================================================================
    with doc.create(Section('Input Parameters')):

        with doc.create(Subsection('Footing Geometry')):
            doc.append(NoEscape(r'All dimensions are entered in \textbf{millimetres (mm)}.'))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{4.5cm} p{2cm} p{7.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'Length \(L\)', 'mm', r'Footing dimension in the x-direction.'),
                    (r'Width \(B\)', 'mm', r'Footing dimension in the y-direction.'),
                    (r'Thickness \(h\)', 'mm', r'Overall footing depth. Self-weight is computed as '
                                               r'\(\gamma_c = 24\,\mathrm{kN/m^3}\).'),
                    (r'Cover \(c_c\)', 'mm',
                     r'Clear cover to the outermost bar layer (bottom bars). '
                     r'ACI 318M-25 \S20.6.1.3 requires \(\geq 75\,\mathrm{mm}\) '
                     r'for footings cast against soil.'),
                    (r'Column width \(c_x\)', 'mm', r'Column dimension in the x-direction.'),
                    (r'Column depth \(c_y\)', 'mm', r'Column dimension in the y-direction.'),
                    (r'Eccentricity \(e_x\)', 'mm',
                     r'Offset of the column centroid from the footing centroid in x. '
                     r'Positive = shift towards \(+x\).'),
                    (r'Eccentricity \(e_y\)', 'mm',
                     r'Offset of the column centroid from the footing centroid in y.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

        with doc.create(Subsection('Materials')):
            with doc.create(LongTable('p{4.5cm} p{2cm} p{7.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r"\(f'_c\)", 'MPa', r'Specified concrete compressive strength.'),
                    (r'\(f_y\)', 'MPa', r'Yield strength of flexural reinforcement.'),
                    (r'Bottom bar size', '---',
                     r'Preferred bar diameter for bottom (positive-moment) reinforcement '
                     r'in both x and y directions.'),
                    (r'Top bar size', '---',
                     r'Preferred bar diameter for top reinforcement where FEA indicates '
                     r'negative moments (thick footings with moments from concentrated loads).'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

        with doc.create(Subsection('Soil Properties')):
            with doc.create(LongTable('p{5cm} p{2cm} p{7cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'Allowable bearing \(q_a\)', 'kPa',
                     r'Gross allowable soil bearing pressure from geotechnical report. '
                     r'The net allowable pressure is: '
                     r'\(q_{a,net} = q_a - \gamma_{soil}\,D_f\).'),
                    (r'Modulus of subgrade reaction \(k_s\)', r'kN/m\textsuperscript{3}',
                     r'Winkler spring stiffness per unit area. '
                     r'Typical range: 10,000--100,000\,kN/m\textsuperscript{3} '
                     r'for cohesive to dense granular soils.'),
                    (r'Soil depth \(D_f\)', 'mm',
                     r'Depth of soil above the top of the footing '
                     r'(embedment depth minus footing thickness). '
                     r'Used to compute soil overburden weight and net bearing capacity.'),
                    (r'Soil unit weight \(\gamma_{soil}\)', r'kN/m\textsuperscript{3}',
                     r'Unit weight of the soil above the footing. '
                     r'Typical range: 16--20\,kN/m\textsuperscript{3}.'),
                    (r'Friction angle \(\phi\)', r'degrees',
                     r'Internal friction angle of the soil. '
                     r'Used to compute sliding resistance and active earth pressure '
                     r'coefficient \(K_a\).'),
                    (r'Dead load surcharge \(q_{s,DL}\)', 'kPa',
                     r'Additional dead load on the soil surface above the footing '
                     r'(e.g., slab on grade). Applied with load factor 1.2.'),
                    (r'Live load surcharge \(q_{s,LL}\)', 'kPa',
                     r'Live load surcharge on the soil surface. Applied with load factor 1.6.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

        with doc.create(Subsection('Applied Forces')):
            doc.append(NoEscape(
                r'Two sets of loads are required: \textbf{factored (LRFD) ultimate} loads '
                r'for structural design and \textbf{service (unfactored)} loads for '
                r'bearing pressure and overturning checks.'
            ))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{3.5cm} p{2cm} p{8.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Symbol'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'\(P_u\)', 'kN', r'Factored axial force (compression positive).'),
                    (r'\(M_{ux}\)', r'kN\(\cdot\)m',
                     r'Factored moment about the x-axis (causes bending in the y-direction).'),
                    (r'\(M_{uy}\)', r'kN\(\cdot\)m',
                     r'Factored moment about the y-axis (causes bending in the x-direction).'),
                    (r'\(V_{ux}\)', 'kN', r'Factored shear force in the x-direction.'),
                    (r'\(V_{uy}\)', 'kN', r'Factored shear force in the y-direction.'),
                    (r'\(P_s\)', 'kN',
                     r'Service axial force. Used for bearing pressure and overturning checks.'),
                    (r'\(M_{sx}\)', r'kN\(\cdot\)m',
                     r'Service moment about the x-axis.'),
                    (r'\(M_{sy}\)', r'kN\(\cdot\)m',
                     r'Service moment about the y-axis.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

    # ===================================================================
    # 4. DESIGN METHODOLOGY
    # ===================================================================
    with doc.create(Section('Design Methodology')):

        # -------------------------------------------------------------- 4.1 FEA Model
        with doc.create(Subsection('Finite Element Model')):

            with doc.create(Subsubsection('Element Type and Mesh')):
                doc.append(NoEscape(
                    r'The footing is discretised into a \(N_x \times N_y\) grid of '
                    r'\textbf{ShellMITC4} elements. The mesh density targets a nominal '
                    r'element size of 250\,mm, with a minimum of 4 elements per side '
                    r'(i.e., \(N = \max(4,\,\lceil L/250 \rceil)\)). '
                    r'This yields approximately \(10 \times 10\) or finer for '
                    r'typical isolated footings.'
                ))

            with doc.create(Subsubsection('Compression-Only Winkler Springs')):
                doc.append(NoEscape(
                    r'At every node a \textbf{compression-only (ENT)} uniaxial spring element '
                    r'is attached in the vertical direction (DOF~3). '
                    r'The tributary spring stiffness is:'
                ))
                doc.append(_eq(
                    r'k_{node} = k_s \times A_{trib} \quad [\mathrm{N/mm}]'
                ))
                doc.append(NoEscape(
                    r'where \(k_s\) is the modulus of subgrade reaction in MPa/mm '
                    r'(converted from kN/m\textsuperscript{3} by dividing by \(10^6\)) '
                    r'and \(A_{trib}\) is the tributary area of the node in mm\textsuperscript{2}. '
                    r'The ENT (elastic-no-tension) model activates the spring only in compression, '
                    r'correctly capturing footing lift-off under large eccentricities.'
                ))

            with doc.create(Subsubsection('Column Load Application')):
                doc.append(NoEscape(
                    r'Column loads are transferred to the footing through a '
                    r'\textbf{rigid link spider} centred at the column application point '
                    r'(\(e_x, e_y\) from the footing centroid). '
                    r'The master node receives the full axial force \(P\), '
                    r'biaxial moments \(M_x, M_y\), and in-plane equilibrium is maintained '
                    r'by fixing one central node against lateral translation and twist.'
                ))

        # -------------------------------------------------------------- 4.2 Bearing Pressure
        with doc.create(Subsection('Soil Bearing Pressure Check')):
            doc.append(NoEscape(
                r'The maximum soil pressure \(q_{max}\) is extracted from the '
                r'compression-only spring reactions in the service-load FEA run. '
                r'The ENT spring model automatically captures non-uniform (trapezoidal or '
                r'triangular) pressure distributions and eliminates tension zones. '
                r'The check is:'
            ))
            doc.append(_eq(r'q_{max} \leq q_{a,net} \quad \text{(service load)}'))
            doc.append(NoEscape(r'where the net allowable pressure accounts for soil overburden:'))
            doc.append(_eq(r'q_{a,net} = q_a - \gamma_{soil}\,D_f'))
            doc.append(NoEscape(
                r'When moments are present (\(M \neq 0\)), the bearing limit is '
                r'increased by 33\,\% for transient load combinations '
                r'(a common allowable-stress design practice): '
                r'\(q_{a,net,transient} = 1.33\,q_{a,net}\).'
            ))

        # -------------------------------------------------------------- 4.3 Overturning
        with doc.create(Subsection('Overturning and Sliding Stability')):

            with doc.create(Subsubsection('Overturning Factor of Safety')):
                doc.append(NoEscape(
                    r'The overturning stability is checked about both the x-axis '
                    r'and the y-axis using service loads. '
                    r'The total vertical load includes footing self-weight and soil overburden:'
                ))
                doc.append(_eq(
                    r'P_{total} = P_s + W_{footing} + W_{soil}, \qquad '
                    r'W_{footing} = 24\,L\,B\,h / 10^6'
                ))
                doc.append(_eq(
                    r'FS_x = \frac{P_{total} \cdot B/2}{|M_{sx}| + |V_{sy}| \cdot h/1000} \geq 1.5'
                    r'\quad \text{(sustained)}'
                ))
                doc.append(_eq(
                    r'FS_y = \frac{P_{total} \cdot L/2}{|M_{sy}| + |V_{sx}| \cdot h/1000} \geq 1.5'
                    r'\quad \text{(sustained)}'
                ))
                doc.append(NoEscape(
                    r'The required factor of safety is \(1.5\) for sustained (gravity) loads and '
                    r'\(1.2\) for transient combinations that include wind or seismic effects.'
                ))

            with doc.create(Subsubsection('Sliding Check')):
                doc.append(NoEscape(
                    r'The passive friction resistance of the soil against sliding is:'
                ))
                doc.append(_eq(
                    r'F_{resist} = P_{total}\,\tan\phi'
                ))
                doc.append(NoEscape(
                    r'where \(\phi\) is the soil friction angle. '
                    r'The applied horizontal force is \(H = \sqrt{V_x^2 + V_y^2}\). '
                    r'The check \(F_{resist} \geq H\) is reported in the Design Notes.'
                ))
                doc.append(NoEscape(r'The active earth pressure coefficient is also reported for reference:'))
                doc.append(_eq(
                    r'K_a = \frac{1 - \sin\phi}{1 + \sin\phi}'
                ))

        # -------------------------------------------------------------- 4.4 One-way shear
        with doc.create(Subsection('One-Way Shear — ACI 318M-25 §22.5')):
            doc.append(NoEscape(
                r'One-way (beam) shear is checked by integrating the FEA soil pressure over '
                r'the critical section at a distance \(d\) from the column face in each direction. '
                r'The concrete shear capacity for a 1\,m-wide strip without transverse reinforcement '
                r'(ACI 318M-25 Table~22.5.5.1):'
            ))
            doc.append(_eq(r"V_c = 0.17\,\lambda\,\sqrt{f'_c}\,b\,d \quad [\mathrm{N/mm}]"))
            doc.append(_eq(r'\phi V_c = 0.75\,V_c'))
            doc.append(NoEscape(
                r'where \(b = 1000\,\mathrm{mm}\), \(d = d_{\mathrm{eff}}\), and '
                r'\(\lambda = 1.0\) (normal-weight concrete). '
                r'The maximum FEA shear from both directions is compared against \(\phi V_c\). '
                r'If the check fails, the footing thickness must be increased — transverse '
                r'reinforcement is not used in footings per common practice.'
            ))

        # -------------------------------------------------------------- 4.5 Two-way shear
        with doc.create(Subsection('Two-Way (Punching) Shear — ACI 318M-25 §22.6')):
            doc.append(NoEscape(
                r'The critical punching perimeter is located at \(d/2\) from the column face. '
                r'Its dimensions depend on whether the critical section is interior, edge, or corner:'
            ))
            doc.append(_eq(
                r'b_1 = c_x + d, \quad b_2 = c_y + d \quad \text{(interior column)}'
            ))
            doc.append(_eq(
                r'b_o = 2\,b_1 + 2\,b_2 \quad \text{(interior)}'
            ))
            doc.append(NoEscape(r'The concentric punching shear stress:'))
            doc.append(_eq(
                r'v_{u,conc} = \frac{V_u}{b_o\,d}, \qquad '
                r'V_u = P_u - q_u\,(b_1 b_2)'
            ))
            doc.append(NoEscape(
                r'The eccentric moment transfer fraction resisted by shear is '
                r'\(\gamma_v = 1 - \gamma_f\):'
            ))
            doc.append(_eq(
                r'\gamma_{fx} = \frac{1}{1 + \tfrac{2}{3}\sqrt{b_1/b_2}}, \qquad '
                r'\gamma_{fy} = \frac{1}{1 + \tfrac{2}{3}\sqrt{b_2/b_1}}'
            ))
            doc.append(_eq(
                r'v_{u,M_x} = \frac{\gamma_{vx}\,|M_{ux}|\,(b_2/2)}{J_{cx}}, \qquad '
                r'v_{u,M_y} = \frac{\gamma_{vy}\,|M_{uy}|\,(b_1/2)}{J_{cy}}'
            ))
            doc.append(_eq(r'v_{u,max} = v_{u,conc} + v_{u,M_x} + v_{u,M_y}'))
            doc.append(NoEscape(r'Nominal concrete punching strength (ACI 318M-25 \S22.6.5.2):'))
            doc.append(_eq(
                r'v_c = \min\!\left('
                r'0.17\,\lambda_s\!\left(1+\frac{2}{\beta}\right)\!\sqrt{f'
                r"'_c},\;"
                r'0.083\,\lambda_s\!\left(\frac{\alpha_s d}{b_o}+2\right)\!\sqrt{f'
                r"'_c},\;"
                r'0.33\,\lambda_s\sqrt{f'
                r"'_c}\right)"
            ))
            doc.append(NoEscape(
                r'where \(\beta = \max(c_x,c_y)/\min(c_x,c_y)\), '
                r'\(\alpha_s = 40\) for interior, 30 for edge, 20 for corner columns, '
                r'and the size effect factor:'
            ))
            doc.append(_eq(
                r'\lambda_s = \min\!\left(1.0,\;\sqrt{\frac{2}{1+0.004\,d}}\right) '
                r'\quad (d\ \mathrm{in\ mm})'
            ))
            doc.append(_eq(r'\phi v_c = 0.75\,v_c'))

        # -------------------------------------------------------------- 4.6 Flexure
        with doc.create(Subsection('Flexural Reinforcement Design')):

            with doc.create(Subsubsection('Design Moments')):
                doc.append(NoEscape(
                    r'The FEA produces bending moment contours \(M_{xx}\) and \(M_{yy}\) '
                    r'throughout the footing due to the net upward soil pressure. '
                    r'The \textbf{Wood-Armer method} is then applied to obtain orthogonal '
                    r'design moments \(M_x^*\) and \(M_y^*\) that account for the '
                    r'twisting moment \(M_{xy}\):'
                ))
                doc.append(_eq(
                    r'M_x^* = M_{xx} + |M_{xy}|, \qquad M_y^* = M_{yy} + |M_{xy}|'
                    r'\quad \text{(bottom, positive)}'
                ))
                doc.append(_eq(
                    r'M_x^* = M_{xx} - |M_{xy}|, \qquad M_y^* = M_{yy} - |M_{xy}|'
                    r'\quad \text{(top, negative)}'
                ))
                doc.append(NoEscape(
                    r'The maximum positive Wood-Armer moment governs bottom reinforcement; '
                    r'the maximum negative value governs top reinforcement.'
                ))

            with doc.create(Subsubsection('Required Steel Area')):
                doc.append(NoEscape(
                    r'For each unit strip (\(b = 1000\,\mathrm{mm}\)) the required '
                    r'\(A_s\) is found from \(\varphi M_n \geq M_u^*\) '
                    r'using the same quadratic formula as the slab module '
                    r'(Section~4.4.1 of the RC Slab Designer Manual). '
                    r'\(\varphi = 0.90\), \(\varphi_{\mathrm{shear}} = 0.75\).'
                ))
                doc.append(NoEscape(r'\medskip'))
                doc.append(NoEscape(r'\textbf{Effective depths:}'))
                doc.append(_eq(
                    r'd = h - c_c - d_{b,bot}/2 \quad \text{(bottom bars, x-layer)}'
                ))
                doc.append(_eq(
                    r'd_{top} = h - c_c - d_{b,top}/2 \quad \text{(top bars)}'
                ))

            with doc.create(Subsubsection('Minimum Reinforcement')):
                doc.append(NoEscape(
                    r'Per ACI 318M-25 \S7.6.1.1 for non-prestressed footings '
                    r'(Grade 280--420 steel):'
                ))
                doc.append(_eq(r'\rho_{min} = 0.0018, \qquad A_{s,min} = 0.0018\,b\,h'))
                doc.append(NoEscape(r'Per ACI 318M-25 \S26.8.2.1, maximum bar spacing in footings:'))
                doc.append(_eq(r's_{max} = \min(3h,\; 450\,\mathrm{mm})'))

            with doc.create(Subsubsection('Development Length')):
                doc.append(NoEscape(
                    r'The straight-bar development length for bottom bars is computed per '
                    r'ACI 318M-25 \S25.5.2.1:'
                ))
                doc.append(_eq(
                    r'\ell_d = \frac{f_y\,\psi_t\,\psi_e}{1.1\,\lambda\,\sqrt{f'
                    r"'_c}} \cdot \frac{d_b}{c_b + K_{tr}} \cdot d_b"
                ))
                doc.append(NoEscape(
                    r'A simplified approach with \(\psi_t = \psi_e = 1.0\) and '
                    r'\(\lambda = 1.0\) is used. The available development length '
                    r'is the horizontal distance from the critical section to the bar end '
                    r'minus end cover.'
                ))

        # -------------------------------------------------------------- 4.7 Dowels
        with doc.create(Subsection('Column-to-Footing Dowel Bars')):
            doc.append(NoEscape(
                r'Dowel bars transfer the column axial force and moment to the footing '
                r'through bearing and reinforcement. The required dowel area per '
                r'ACI 318M-25 \S16.3.5.1:'
            ))
            doc.append(_eq(
                r'A_{s,dowel} \geq \max\!\left(A_{g,col} \times 0.005,\; '
                r'A_{g,col} \times \rho_{\min}\right)'
            ))
            doc.append(NoEscape(
                r'where \(A_{g,col} = c_x \times c_y\). '
                r'The minimum number of dowels is 4 (one per corner). '
                r'The required lap splice length in the footing is '
                r'\(\ell_{lap} = 1.3\,\ell_d\) per ACI 318M-25 \S26.5.3.'
            ))

    # ===================================================================
    # 5. INTERPRETING DESIGN RESULTS
    # ===================================================================
    with doc.create(Section('Interpreting Design Results')):

        with doc.create(Subsection('Design Checks Summary')):
            with doc.create(LongTable('p{4cm} p{9.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Check'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'Bearing pressure',
                     r'Passes when \(q_{max} \leq q_{a,net}\) (or \(\times 1.33\) for transient). '
                     r'Shown in green (\checkmark) or red (\(\times\)).'),
                    (r'Overturning (x, y)',
                     r'Passes when \(FS \geq 1.5\) (sustained) or \(\geq 1.2\) (transient). '
                     r'Factors of safety are reported for both axes.'),
                    (r'Sliding',
                     r'\(F_{resist} = P_{total}\,\tan\phi \geq H_{applied}\). '
                     r'Result reported in Design Notes.'),
                    (r'One-way shear',
                     r'Passes when \(V_{max} \leq \phi V_c\). '
                     r'If shear fails, increase \(h\) until it passes.'),
                    (r'Two-way shear',
                     r'Passes when \(v_{u,max} \leq \phi v_c\). '
                     r'The DCR is shown; values above 1.0 require a larger footing plan.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()

        with doc.create(Subsection('Reinforcement Schedule')):
            with doc.create(Itemize()) as lst:
                lst.add_item(NoEscape(
                    r'\textbf{Bottom bars (x / y):} Bar size and centre-to-centre spacing '
                    r'for the bottom mat. x-bars are placed in the outermost layer.'))
                lst.add_item(NoEscape(
                    r'\textbf{Top bars (x / y):} Bar size and spacing where FEA shows negative '
                    r'moments. Defaults to minimum steel if no negative moments are detected.'))
                lst.add_item(NoEscape(
                    r'\textbf{Dowel bars:} Number and size of column-to-footing dowels. '
                    r'The required lap splice length into the footing is reported.'))
                lst.add_item(NoEscape(
                    r'\textbf{Development length:} Required straight development length for '
                    r'bottom bars from the critical section (column face) to bar end.'))

        with doc.create(Subsection('FEA Contour Plots')):
            with doc.create(LongTable('p{3.5cm} p{10cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Plot'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'Bearing pressure', r'Soil contact pressure from ENT spring reactions (kPa). '
                                          r'Zero values indicate lifted (no-contact) zones.'),
                    (r'Settlement', r'Vertical displacement field from FEA (mm). '
                                    r'Negative values indicate downward settlement.'),
                    (r'\(M_{xx}\)', r'Bending moment per unit width in x-direction (kN-m/m). '
                                   r'Positive = tension on bottom face.'),
                    (r'\(M_{yy}\)', r'Bending moment per unit width in y-direction (kN-m/m).'),
                    (r'\(M_{xy}\)', r'Twisting moment per unit width (kN-m/m).'),
                    (r'Shear \(V_x / V_y\)', r'Integrated shear force per unit width from soil '
                                              r'pressure (kN/m). Governs one-way shear check.'),
                    (r'Wood-Armer \(M_x^*\)', r'Design moment for bottom x-reinforcement (kN-m/m).'),
                    (r'Wood-Armer \(M_y^*\)', r'Design moment for bottom y-reinforcement (kN-m/m).'),
                    (r'Required \(A_s\) (bottom)', r'Required steel area per unit width at each '
                                                   r'point in the footing (mm\textsuperscript{2}/m). '
                                                   r'Useful for variable-thickness or custom designs.'),
                    (r'Required \(A_s\) (top)', r'Required steel area for top reinforcement '
                                                r'where negative moments exist.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()
            doc.append(NoEscape(r'\smallskip'))
            doc.append(NoEscape(
                r'A black rectangle on each plot marks the column footprint. '
                r'The column centroid may be offset from the footing centre when '
                r'\(e_x \neq 0\) or \(e_y \neq 0\).'
            ))

        with doc.create(Subsection('Design Notes')):
            doc.append(NoEscape(
                r'The \textit{Design Notes} panel summarises all design decisions and warnings. '
                r'Entries prefixed with \textbf{CRITICAL} indicate structural failures '
                r'(shear or moment capacity exceeded) that require geometry changes. '
                r'\textbf{Warning} entries flag checks that are marginal or exceeded '
                r'for overturning and bearing. '
                r'Informational entries (\(\triangleright\)) explain automatic solver decisions.'
            ))

    # ===================================================================
    # 6. QUANTITY TAKE-OFF
    # ===================================================================
    with doc.create(Section('Quantity Take-Off')):
        doc.append(NoEscape(
            r'The QTO section reports estimated material quantities per footing for procurement:'
        ))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(
                r'\textbf{Concrete volume}: '
                r'\(V = L \times B \times h / 10^9\) (m\textsuperscript{3}).'))
            lst.add_item(NoEscape(
                r'\textbf{Formwork area}: perimeter of the footing \(\times\) thickness '
                r'\((2(L+B) \times h / 10^6)\) (m\textsuperscript{2}). '
                r'The bottom face (against soil) is typically not formed.'))
            lst.add_item(NoEscape(
                r'\textbf{Rebar weight}: bar lengths accounting for end cover and '
                r'lap splices (\(40\,d_b\)) multiplied by unit weight '
                r'\((d_b^2 / 162\,\mathrm{kg/m})\).'))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(
            r'Rebar orders are expressed as the optimal combination of Philippine standard '
            r'stock lengths (6\,m, 7.5\,m, 9\,m, 10.5\,m, 12\,m) that minimises offcut waste.'
        ))

    # ===================================================================
    # 7. REFERENCES
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
                r'Coduto, D.\,P.; Kitch, W.\,A.; Yeung, M.\,R. '
                r'\textit{Foundation Design: Principles and Practices}, 3rd ed. '
                r'Pearson Education, 2016.'))
            lst.add_item(NoEscape(
                r'Das, B.\,M. \textit{Principles of Foundation Engineering}, 9th ed. '
                r'Cengage Learning, 2019.'))
            lst.add_item(NoEscape(
                r'McKenna, F.; Fenves, G.\,L.; Scott, M.\,H. \textit{OpenSees: Open System for '
                r'Earthquake Engineering Simulation}. University of California, Berkeley, 2000. '
                r'\href{https://opensees.berkeley.edu}{opensees.berkeley.edu}'))
            lst.add_item(NoEscape(
                r'Wight, J.\,K. \textit{Reinforced Concrete: Mechanics and Design}, 8th ed. '
                r'Pearson Education, 2023.'))

    # ------------------------------------------------------------------ compile
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, 'footing_manual')
        doc.generate_pdf(tex_path, clean_tex=True, compiler='pdflatex',
                         compiler_args=['-interaction=nonstopmode'])
        pdf_path = tex_path + '.pdf'
        with open(pdf_path, 'rb') as f:
            return f.read()
