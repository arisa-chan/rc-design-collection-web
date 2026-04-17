# -*- coding: utf-8 -*-
"""
RC Slab Designer – User Manual Generator
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


def generate_slab_manual() -> bytes:
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
        r'\fancyhead[L]{\textcolor{acigray}{\small RC Slab Designer --- User Manual}}'
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
    doc.append(NoEscape(r'{\Huge \textbf{\textcolor{aciblue}{RC Slab Designer}}}\\[0.5em]'))
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
            r'The \textbf{RC Slab Designer} is a web-based structural engineering tool that performs '
            r'strength and serviceability design of two-way reinforced concrete slabs in full compliance '
            r'with \textbf{ACI 318M-25} (\textit{Building Code Requirements for Structural Concrete}). '
            r'The module models the slab as a three-dimensional shell finite element assembly using '
            r'\textbf{OpenSeesPy ShellMITC4} elements, captures the full biaxial and torsional moment '
            r'field, and applies the \textbf{Wood-Armer} design moment transformation before selecting '
            r'reinforcement.'
        ))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(r'\textbf{Design outputs include:}'))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Wood-Armer design moments in both directions (positive and negative)'))
            lst.add_item(NoEscape(r'Bottom reinforcement: bar size and spacing in x and y directions'))
            lst.add_item(NoEscape(r'Top reinforcement: bar size and spacing in x and y directions'))
            lst.add_item(NoEscape(r'Shrinkage and temperature reinforcement'))
            lst.add_item(NoEscape(r'Immediate live-load deflection and long-term deflection'))
            lst.add_item(NoEscape(r'Demand-to-Capacity Ratio (DCR) at all critical sections'))
            lst.add_item(NoEscape(r'Eight FEA contour plots: deflection, bending moments (Mxx, Myy, Mxy), '
                                  r'Wood-Armer moments, and shear forces (Vx, Vy)'))
            lst.add_item(NoEscape(r'Quantity take-off (concrete volume, formwork area, rebar weight and ordering)'))
            lst.add_item(NoEscape(r'Detailed PDF calculation report'))

    # ===================================================================
    # 2. SCOPE AND LIMITATIONS
    # ===================================================================
    with doc.create(Section('Scope and Limitations')):
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Solid two-way slabs only. Ribbed, waffle, flat-plate with drop panels, '
                                  r'and post-tensioned slabs are not supported.'))
            lst.add_item(NoEscape(r'Rectangular plan geometry only.'))
            lst.add_item(NoEscape(r'Normal-weight concrete assumed (\(\lambda = 1.0\)).'))
            lst.add_item(NoEscape(r'Uniform loading only. Point loads and line loads are not directly supported.'))
            lst.add_item(NoEscape(r'Loads are entered as service-level pressures (kPa); '
                                  r'the program applies the ACI 318M-25 load combination '
                                  r'\(w_u = 1.2D + 1.6L\) internally.'))
            lst.add_item(NoEscape(r'FEA mesh is fixed at \(12 \times 12\) shell elements; '
                                  r'mesh refinement is not user-configurable.'))
            lst.add_item(NoEscape(r'Slab openings and irregular boundaries are not handled.'))
            lst.add_item(NoEscape(r'Seismic design provisions (diaphragm action) are not activated '
                                  r'in this version.'))
            lst.add_item(NoEscape(r'Column-supported edges use point supports at node locations; '
                                  r'column flexibility is not explicitly modelled.'))
            lst.add_item(NoEscape(r'Punching shear at column supports is not checked in this version. '
                                  r'The engineer must verify punching shear independently.'))

    # ===================================================================
    # 3. INPUT PARAMETERS
    # ===================================================================
    with doc.create(Section('Input Parameters')):

        with doc.create(Subsection('Geometry')):
            doc.append(NoEscape(
                r'All dimensions are entered in \textbf{millimetres (mm)}.'
            ))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{4cm} p{2cm} p{8cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'Span in x-direction \(L_x\)', 'mm',
                     r'Clear-to-clear slab dimension in the x-direction (short or long span).'),
                    (r'Span in y-direction \(L_y\)', 'mm',
                     r'Clear-to-clear slab dimension in the y-direction.'),
                    (r'Slab thickness \(h\)', 'mm',
                     r'Overall slab thickness. Self-weight is computed as '
                     r'\(w_{sw} = 24\,h/1000\) kPa.'),
                    (r'Concrete cover \(c_c\)', 'mm',
                     r'Clear cover to the outermost reinforcement. '
                     r'Effective depths are: '
                     r'\(d_x = h - c_c - d_{b,x}/2\) (bottom x-bars) and '
                     r'\(d_y = h - c_c - d_{b,x} - d_{b,y}/2\) (bottom y-bars, second layer).'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

        with doc.create(Subsection('Edge Conditions')):
            doc.append(NoEscape(
                r'Each of the four slab edges (top, bottom, left, right) is independently defined '
                r'by two properties: \textbf{support type} and \textbf{continuity}.'
            ))
            doc.append(NoEscape(r'\medskip'))
            doc.append(NoEscape(r'\textbf{Support Type} --- controls the out-of-plane boundary condition:'))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{3.5cm} p{10cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Type'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'\textbf{Wall}',
                     r'Edge is supported on a masonry or concrete wall. '
                     r'Out-of-plane translation \(w = 0\) is enforced at all nodes along the edge. '
                     r'The wall thickness is entered for record-keeping only.'),
                    (r'\textbf{Beam}',
                     r'Edge is supported on a monolithic RC beam. '
                     r'The beam is modelled explicitly with elasticBeamColumn elements '
                     r'using reduced stiffness modifiers (\(0.35\,EI\)) per ACI 318M-25 Table~6.6.3.1. '
                     r'Beam width \(b\) and depth \(h_b\) must be provided.'),
                    (r'\textbf{Columns at ends}',
                     r'Edge is bounded by columns at its two endpoints (corner columns). '
                     r'Out-of-plane restraint \(w = 0\) is applied at the two corner nodes only. '
                     r'Column dimensions \(c_x \times c_y\) are entered but not explicitly modelled.'),
                    (r'\textbf{Free end}',
                     r'Edge has no support. No boundary restraints are applied. '
                     r'Both translation and rotation are free.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()
            doc.append(NoEscape(r'\medskip'))
            doc.append(NoEscape(r'\textbf{Continuity} --- controls the rotational boundary condition:'))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{3.5cm} p{10cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Setting'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'\textbf{Continuous}',
                     r'The slab is monolithic with the adjacent span. '
                     r'The rotation normal to the edge is restrained (\(\theta = 0\)). '
                     r'This generates hogging (negative) moments at the support.'),
                    (r'\textbf{Discontinuous}',
                     r'The edge is at the end of the slab or at a construction joint. '
                     r'Rotation is free. No hogging moment is developed at this edge.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()

        with doc.create(Subsection('Materials')):
            with doc.create(LongTable('p{4cm} p{2cm} p{8cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r"\(f'_c\)", 'MPa', r'Specified concrete compressive strength.'),
                    (r'\(f_y\)', 'MPa', r'Yield strength of flexural reinforcement.'),
                    (r'Bottom bar size', '---',
                     r'Preferred bar diameter for positive-moment (sagging) reinforcement '
                     r'in both x and y directions. The solver will upsize if the preferred '
                     r'bar cannot satisfy spacing limits.'),
                    (r'Top bar size', '---',
                     r'Preferred bar diameter for negative-moment (hogging) reinforcement '
                     r'at continuous edges.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()
            doc.append(NoEscape(r'\smallskip'))
            doc.append(NoEscape(
                r'The elastic modulus of concrete is computed per ACI 318M-25 Eq.\,(19.2.2.1b): '
            ))
            doc.append(_eq(r"E_c = 4700\,\sqrt{f'_c} \quad [\mathrm{MPa}]"))

        with doc.create(Subsection('Applied Loads')):
            doc.append(NoEscape(
                r'Loads are entered as \textbf{service-level pressures} in \textbf{kPa}. '
                r'The program combines them internally using the ACI 318M-25 factored combination.'
            ))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{4.5cm} p{2cm} p{7.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'Superimposed dead load \(q_{SDL}\)', 'kPa',
                     r'Additional dead load above self-weight: finishes, partitions, MEP, etc.'),
                    (r'Live load \(q_L\)', 'kPa',
                     r'Occupancy live load per applicable building code.'),
                    (r'Deflection limit', '---',
                     r'Allowable span-to-deflection ratio for the long-term check. '
                     r'Select \(L/240\) (non-sensitive finishes) or \(L/480\) (sensitive finishes). '
                     r'Immediate live-load deflection is always checked against \(L/360\).'),
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
                    r'The slab is discretised into a \(12 \times 12\) grid of '
                    r'\textbf{ShellMITC4} elements (Mixed Interpolation of Tensorial Components, '
                    r'4-node quadrilateral). Each element has six DOFs per node '
                    r'(\(u_x, u_y, w, \theta_x, \theta_y, \theta_z\)). '
                    r'The MITC4 formulation eliminates shear locking and is well-suited for '
                    r'thin-to-moderately-thick plate problems.'
                ))

            with doc.create(Subsubsection('Stiffness Modifiers')):
                doc.append(NoEscape(
                    r'To account for cracking, reduced stiffness properties are used per '
                    r'ACI 318M-25 Table~6.6.3.1:'
                ))
                doc.append(NoEscape(r'\medskip'))
                with doc.create(LongTable('p{4cm} p{4cm} p{6cm}')) as tbl:
                    tbl.add_hline()
                    tbl.add_row([bold('Member'), bold('Modifier'), bold('Applied to')])
                    tbl.add_hline()
                    tbl.add_row([NoEscape(r'Slab'), NoEscape(r'\(0.25\,E_c I_g\)'),
                                 NoEscape(r'Ultimate-load analysis')])
                    tbl.add_row([NoEscape(r'Slab'), NoEscape(r'\(1.0\,E_c I_g\)'),
                                 NoEscape(r'Service-load analyses (deflection)')])
                    tbl.add_row([NoEscape(r'Beam'), NoEscape(r'\(0.35\,E_c I_g\)'),
                                 NoEscape(r'Both ultimate and service analyses')])
                    tbl.add_hline()

            with doc.create(Subsubsection('Four Analysis Runs')):
                doc.append(NoEscape(
                    r'A total of four FEA analyses are performed per design cycle:'
                ))
                with doc.create(Enumerate()) as lst:
                    lst.add_item(NoEscape(
                        r'\textbf{Ultimate load} \((w_u)\): Factored load combination used to obtain '
                        r'design moments for reinforcement selection. '
                        r'Slab stiffness modifier = 0.25.'))
                    lst.add_item(NoEscape(
                        r'\textbf{Dead load} \((w_D)\): Service dead load only '
                        r'(\(w_{sw} + q_{SDL}\)). Slab stiffness modifier = 1.0.'))
                    lst.add_item(NoEscape(
                        r'\textbf{Sustained load} \((w_{sus})\): Dead load plus 50\,\% of live load '
                        r'(\(w_D + 0.5\,q_L\)). Used for long-term deflection. Modifier = 1.0.'))
                    lst.add_item(NoEscape(
                        r'\textbf{Total service load} \((w_{tot})\): Full service load '
                        r'(\(w_D + q_L\)). Used for total deflection and cracking check. Modifier = 1.0.'))

        # -------------------------------------------------------------- 4.2 Load Combination
        with doc.create(Subsection('Load Combinations and Self-Weight')):
            doc.append(NoEscape(r'The factored design load combination is (ACI 318M-25 \S5.3.1):'))
            doc.append(_eq(r'w_u = 1.2\,(w_{sw} + q_{SDL}) + 1.6\,q_L'))
            doc.append(NoEscape(r'Self-weight of the slab per unit area:'))
            doc.append(_eq(r'w_{sw} = 24\,\frac{h}{1000} \quad [\mathrm{kPa},\ h\ \mathrm{in\ mm}]'))
            doc.append(NoEscape(
                r'where the concrete unit weight is \(24\,\mathrm{kN/m^3}\) '
                r'(normal-weight concrete per ACI 318M-25).'
            ))

        # -------------------------------------------------------------- 4.3 Wood-Armer
        with doc.create(Subsection('Wood-Armer Moment Transformation')):
            doc.append(NoEscape(
                r'The FEA produces three moment components at each node: '
                r'\(M_{xx}\) (bending about y-axis), \(M_{yy}\) (bending about x-axis), '
                r'and \(M_{xy}\) (twisting moment). '
                r'The \textbf{Wood-Armer method} converts these to design moments '
                r'\(M_x^*\) and \(M_y^*\) that fully account for the torsional coupling '
                r'(Wood, 1968; Armer, 1968).'
            ))
            doc.append(NoEscape(r'\medskip'))
            doc.append(NoEscape(r'\textbf{Bottom (positive) reinforcement design moments:}'))
            doc.append(_eq(
                r'M_x^* = M_{xx} + |M_{xy}|, \qquad M_y^* = M_{yy} + |M_{xy}|'
            ))
            doc.append(NoEscape(
                r'Special case --- when one orthogonal moment is predominantly compressive '
                r'(e.g., \(M_{yy} < -|M_{xy}|\)):'
            ))
            doc.append(_eq(
                r"M_x^{*} = M_{xx} + \frac{M_{xy}^2}{|M_{yy}|}, \qquad M_y^{*} = 0"
            ))
            doc.append(NoEscape(r'\textbf{Top (negative) reinforcement design moments:}'))
            doc.append(_eq(
                r'M_x^* = M_{xx} - |M_{xy}|, \qquad M_y^* = M_{yy} - |M_{xy}|'
            ))
            doc.append(NoEscape(
                r'Only negative Wood-Armer moments \((M_x^* < 0)\) drive top reinforcement. '
                r'The governing (maximum absolute) value over the full slab grid is used '
                r'as the design moment for each strip.'
            ))

        # -------------------------------------------------------------- 4.4 Flexural Reinforcement
        with doc.create(Subsection('Flexural Reinforcement Design')):

            with doc.create(Subsubsection('Required Steel Area per Unit Width')):
                doc.append(NoEscape(
                    r'For a design strip of unit width \(b = 1000\,\mathrm{mm}\), '
                    r'the required steel area \(A_s\) is found from the strength condition '
                    r'\(\varphi M_n \geq M_u^*\) with \(\varphi = 0.90\). '
                    r'Substituting the rectangular stress-block expression:'
                ))
                doc.append(_eq(
                    r'\varphi f_y A_s \!\left(d - \frac{A_s f_y}{2 \times 0.85\,f'
                    r"'_c b}\right) = M_u^* \times 10^6"
                ))
                doc.append(NoEscape(
                    r"Rearranging as a quadratic in \(A_s\) with \(A = \varphi f_y^2 / (1.7\,f'_c b)\), "
                    r'\(B = -\varphi f_y d\), \(C = M_u^* \times 10^6\):'
                ))
                doc.append(_eq(
                    r'A_s = \frac{-B - \sqrt{B^2 - 4AC}}{2A} \geq A_{s,\min}'
                ))

            with doc.create(Subsubsection('Minimum Reinforcement')):
                doc.append(NoEscape(
                    r'The governing minimum is the \textbf{shrinkage and temperature} requirement '
                    r'per ACI 318M-25 \S24.4.3.2, which also serves as the minimum for two-way '
                    r'slab flexure:'
                ))
                doc.append(_eq(
                    r'\rho_{s+t} = \begin{cases}'
                    r'0.0020 & f_y \leq 420\,\mathrm{MPa} \\'
                    r'0.0018 & 420 < f_y \leq 520\,\mathrm{MPa} \\'
                    r'\max\!\left(0.0014,\; 0.0018 \times 420/f_y\right) & f_y > 520\,\mathrm{MPa}'
                    r'\end{cases}'
                ))
                doc.append(_eq(r'A_{s,\min} = \rho_{s+t}\,b\,h \quad (b = 1000\,\mathrm{mm})'))

            with doc.create(Subsubsection('Maximum Bar Spacing')):
                doc.append(NoEscape(r'Per ACI 318M-25 \S8.7.2.3 for two-way slabs:'))
                doc.append(_eq(r's_{\max} = \min(3h,\; 450\,\mathrm{mm})'))
                doc.append(NoEscape(
                    r'The minimum clear spacing between bars must also satisfy: '
                    r'\(\max(25\,\mathrm{mm},\; d_b) + d_b\).'
                ))

        # -------------------------------------------------------------- 4.5 Deflection
        with doc.create(Subsection('Deflection Check')):

            with doc.create(Subsubsection('Effective Moment of Inertia — ACI 318M-25 §24.2.3.5')):
                doc.append(NoEscape(
                    r'Deflections are computed from service-load FEA results and then scaled '
                    r'to account for cracking using the \textbf{effective moment of inertia} '
                    r'\(I_e\). The cracking moment for a unit strip:'
                ))
                doc.append(_eq(
                    r"M_{cr} = \frac{f_r\,I_g}{y_t}, \qquad f_r = 0.62\,\lambda\sqrt{f'_c}, "
                    r"\qquad I_g = \frac{1000\,h^3}{12}"
                ))
                doc.append(NoEscape(
                    r'The neutral-axis depth factor \(k\) for the transformed cracked section:'
                ))
                doc.append(_eq(
                    r'k = \sqrt{2\rho n + (\rho n)^2} - \rho n, \qquad '
                    r'n = E_s / E_c, \qquad \rho = A_s / (1000\,d)'
                ))
                doc.append(_eq(
                    r'I_{cr} = \frac{1000\,(kd)^3}{3} + n\,A_s\,(d - kd)^2'
                ))
                doc.append(NoEscape(r'Per ACI 318M-25 Eq.\,(24.2.3.5a):'))
                doc.append(_eq(
                    r'I_e = \frac{I_{cr}}{1 - \!\left(\dfrac{\tfrac{2}{3}M_{cr}}{M_a}\right)^{\!2} '
                    r'\!\left(1 - \dfrac{I_{cr}}{I_g}\right)}'
                    r'\qquad (I_{cr} \leq I_e \leq I_g)'
                ))
                doc.append(NoEscape(
                    r'where \(M_a = \max(M_{x,pos},\,M_{y,pos})\) is the maximum positive design moment '
                    r'from service analysis. The service deflection grid from FEA is scaled by '
                    r'\(I_g / I_e\) to obtain the cracked deflection grid.'
                ))

            with doc.create(Subsubsection('Long-Term Deflection')):
                doc.append(NoEscape(r'Per ACI 318M-25 \S24.2.4:'))
                doc.append(_eq(
                    r'\delta_{\mathrm{long}} = \delta_{\mathrm{live}} + 2.0\,\delta_{\mathrm{sus}}'
                ))
                doc.append(NoEscape(
                    r'where \(\delta_{\mathrm{live}} = \delta_{\mathrm{tot}} - \delta_{\mathrm{dead}}\) '
                    r'and \(\delta_{\mathrm{sus}}\) is the cracked deflection under sustained load '
                    r'(\(w_D + 0.5\,q_L\)). '
                    r'The multiplier 2.0 corresponds to the long-term creep factor \(\xi_t\) '
                    r'assuming no compression reinforcement \((\rho' r"' = 0)\)."
                ))

            with doc.create(Subsubsection('Allowable Deflection Limits')):
                with doc.create(LongTable('p{4cm} p{9.5cm}')) as tbl:
                    tbl.add_hline()
                    tbl.add_row([bold('Limit'), bold('Description')])
                    tbl.add_hline()
                    tbl.add_row([NoEscape(r'\(\delta_{\mathrm{live}} \leq L_n/360\)'),
                                 NoEscape(r'Immediate live-load deflection (ACI 318M-25 Table~24.2.2). '
                                          r'\(L_n\) is the longer clear span.')])
                    tbl.add_row([NoEscape(r'\(\delta_{\mathrm{long}} \leq L_n/240\)'),
                                 NoEscape(r'Long-term deflection for non-sensitive finishes '
                                          r'(user-selectable).')])
                    tbl.add_row([NoEscape(r'\(\delta_{\mathrm{long}} \leq L_n/480\)'),
                                 NoEscape(r'Long-term deflection for sensitive finishes '
                                          r'(user-selectable).')])
                    tbl.add_hline()
                doc.append(NoEscape(r'\smallskip'))
                doc.append(NoEscape(
                    r'The governing span \(L_n\) for the deflection limit is taken as the '
                    r'\textbf{longer} clear span (\(\max(L_x, L_y)\)).'
                ))

    # ===================================================================
    # 5. INTERPRETING DESIGN RESULTS
    # ===================================================================
    with doc.create(Section('Interpreting Design Results')):

        with doc.create(Subsection('Design Moments')):
            with doc.create(LongTable('p{4cm} p{9.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Output'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'\(M_{x,pos}^*\)',
                     r'Maximum Wood-Armer positive moment per unit width in x-strip. '
                     r'Governs bottom x-bar design.'),
                    (r'\(M_{x,neg}^*\)',
                     r'Maximum Wood-Armer negative moment per unit width in x-strip. '
                     r'Governs top x-bar design at continuous edges.'),
                    (r'\(M_{y,pos}^*\)',
                     r'Maximum Wood-Armer positive moment per unit width in y-strip. '
                     r'Governs bottom y-bar design.'),
                    (r'\(M_{y,neg}^*\)',
                     r'Maximum Wood-Armer negative moment per unit width in y-strip. '
                     r'Governs top y-bar design at continuous edges.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()

        with doc.create(Subsection('Reinforcement Schedule')):
            with doc.create(Itemize()) as lst:
                lst.add_item(NoEscape(
                    r'\textbf{Bottom bars (x / y):} Bar size and centre-to-centre spacing '
                    r'for sagging (positive) moments. Placed in the lower mat; '
                    r'x-bars are in the outermost layer (larger effective depth).'))
                lst.add_item(NoEscape(
                    r'\textbf{Top bars (x / y):} Bar size and centre-to-centre spacing '
                    r'for hogging (negative) moments at continuous edges. '
                    r'If the edge is discontinuous, top bars default to the '
                    r'shrinkage/temperature minimum.'))
                lst.add_item(NoEscape(
                    r'\textbf{Shrinkage bars:} Minimum-steel bars in both directions per '
                    r'ACI 318M-25 \S24.4.3.2. Placed where flexural demand is below minimum.'))

        with doc.create(Subsection('Deflection Output')):
            with doc.create(Itemize()) as lst:
                lst.add_item(NoEscape(
                    r'\textbf{Immediate live-load deflection} \(\delta_L\): '
                    r'Maximum cracked live-load deflection. Must satisfy \(\delta_L \leq L_n/360\).'))
                lst.add_item(NoEscape(
                    r'\textbf{Long-term deflection} \(\delta_{long}\): '
                    r'Includes creep and shrinkage under sustained load plus live-load deflection. '
                    r'Must satisfy the user-selected limit (\(L_n/240\) or \(L_n/480\)).'))

        with doc.create(Subsection('Demand-to-Capacity Ratio (DCR)')):
            doc.append(NoEscape(
                r'The reported DCR is the maximum of the four Wood-Armer moment utilization ratios:'
            ))
            doc.append(_eq(
                r'\mathrm{DCR} = \max\!\left(\frac{M_{x,pos}^*}{\varphi M_{n,bx}},\; '
                r'\frac{M_{x,neg}^*}{\varphi M_{n,tx}},\; '
                r'\frac{M_{y,pos}^*}{\varphi M_{n,by}},\; '
                r'\frac{M_{y,neg}^*}{\varphi M_{n,ty}}\right)'
            ))
            doc.append(NoEscape(r'DCR \(\leq 1.00\) indicates an adequate section (shown in green).'))

        with doc.create(Subsection('FEA Contour Plots')):
            with doc.create(LongTable('p{3.5cm} p{10cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Plot'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'Deflection', r'Absolute cracked service deflection field \(|w|\) in mm.'),
                    (r'\(M_{xx}\)', r'Bending moment per unit width about y-axis (kN-m/m).'),
                    (r'\(M_{yy}\)', r'Bending moment per unit width about x-axis (kN-m/m).'),
                    (r'\(M_{xy}\)', r'Twisting moment per unit width (kN-m/m). '
                                   r'Blue = hogging twist; red = sagging twist.'),
                    (r'Wood-Armer \(M_x^*\)',
                     r'Bottom design moment in x-strip (kN-m/m). Positive values drive bottom x-bars.'),
                    (r'Wood-Armer \(M_y^*\)',
                     r'Bottom design moment in y-strip (kN-m/m). Positive values drive bottom y-bars.'),
                    (r'Shear \(V_x\)', r'Transverse shear per unit width in x-direction (kN/m).'),
                    (r'Shear \(V_y\)', r'Transverse shear per unit width in y-direction (kN/m).'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()

        with doc.create(Subsection('Slab Plan Diagram')):
            doc.append(NoEscape(
                r'The slab plan view on the input page displays the boundary conditions '
                r'using line styles: \textbf{solid thick} = wall support; '
                r'\textbf{dashed pink} = beam support; \textbf{dotted} = free edge. '
                r'After design, the bar grid overlay visualises the reinforcement spacing '
                r'in both directions.'
            ))

        with doc.create(Subsection('Design Notes')):
            doc.append(NoEscape(
                r'The \textit{Design Notes} panel lists decisions and warnings generated '
                r'during the analysis. Entries prefixed with \textbf{CRITICAL} indicate '
                r'that the slab thickness is insufficient for the applied moments and must '
                r'be increased. Informational entries explain modelling choices made automatically '
                r'by the solver.'
            ))

    # ===================================================================
    # 6. QUANTITY TAKE-OFF
    # ===================================================================
    with doc.create(Section('Quantity Take-Off')):
        doc.append(NoEscape(
            r'The QTO section reports estimated material quantities for the slab panel:'
        ))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(
                r'\textbf{Concrete volume}: \(V = L_x \times L_y \times h / 10^9\) (m\textsuperscript{3}).'))
            lst.add_item(NoEscape(
                r'\textbf{Formwork area}: \(A_f = L_x \times L_y / 10^6\) (m\textsuperscript{2}).'))
            lst.add_item(NoEscape(
                r'\textbf{Rebar weight}: bar lengths accounting for cover at each end, '
                r'lap splices (\(40\,d_b\)) for bars longer than 12\,m, and '
                r'standard 90° hooks (\(12\,d_b + 100\,\mathrm{mm}\) per end).'))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(
            r'Rebar orders are expressed as the optimal combination of Philippine standard '
            r'stock lengths (6\,m, 7.5\,m, 9\,m, 10.5\,m, 12\,m) that minimises offcut waste '
            r'(1D bin-packing algorithm).'
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
                r'Wood, R.\,H. ``The Reinforcement of Slabs in Accordance with a Pre-Determined '
                r"Field of Moments,'' \textit{Concrete}, 2(2), 1968, pp.\,69--76."))
            lst.add_item(NoEscape(
                r'Armer, G.\,S.\,T. ``Discussion of Wood (1968),'' '
                r'\textit{Concrete}, 2(8), 1968, pp.\,319--320.'))
            lst.add_item(NoEscape(
                r'McKenna, F.; Fenves, G.\,L.; Scott, M.\,H. \textit{OpenSees: Open System for '
                r'Earthquake Engineering Simulation}. University of California, Berkeley, 2000. '
                r'\href{https://opensees.berkeley.edu}{opensees.berkeley.edu}'))
            lst.add_item(NoEscape(
                r'Wight, J.\,K. \textit{Reinforced Concrete: Mechanics and Design}, 8th ed. '
                r'Pearson Education, 2023.'))

    # ------------------------------------------------------------------ compile
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, 'slab_manual')
        doc.generate_pdf(tex_path, clean_tex=True, compiler='pdflatex',
                         compiler_args=['-interaction=nonstopmode'])
        pdf_path = tex_path + '.pdf'
        with open(pdf_path, 'rb') as f:
            return f.read()
