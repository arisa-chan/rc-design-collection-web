# -*- coding: utf-8 -*-
"""
RC Beam Designer – User Manual Generator
Produces a standalone PDF user manual using PyLaTeX.
"""

import os
import tempfile
from pylatex import (Document, Section, Subsection, Subsubsection,
                     Command, NoEscape, PageStyle, Head, Foot, Tabular,
                     Itemize, Enumerate, LongTable, MiniPage, LineBreak)
from pylatex.utils import bold, italic


# ---------------------------------------------------------------------------
# Helper: emit a display equation block without the equation environment
#         (avoids numbering issues when used inside boxes)
# ---------------------------------------------------------------------------
def _eq(latex_str: str) -> NoEscape:
    return NoEscape(r'\[' + latex_str + r'\]')


def _ineq(latex_str: str) -> NoEscape:
    return NoEscape(r'\(' + latex_str + r'\)')


def generate_beam_manual() -> bytes:
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
        r'\fancyhead[L]{\textcolor{acigray}{\small RC Beam Designer --- User Manual}}'
        r'\fancyhead[R]{\textcolor{acigray}{\small ACI 318M-25}}'
        r'\fancyfoot[C]{\thepage}'
        r'\renewcommand{\headrulewidth}{0.4pt}'
    ))
    # section colour
    doc.preamble.append(NoEscape(
        r'\titleformat{\section}{\large\bfseries\color{aciblue}}{}{0em}{}'
        r'\titleformat{\subsection}{\normalsize\bfseries\color{acipink}}{}{0em}{}'
        r'\titleformat{\subsubsection}{\normalsize\bfseries\color{acigray}}{}{0em}{}'
    ))

    # ------------------------------------------------------------------ title page
    doc.append(NoEscape(r'\begin{center}'))
    doc.append(NoEscape(r'{\Huge \textbf{\textcolor{aciblue}{RC Beam Designer}}}\\[0.5em]'))
    doc.append(NoEscape(r'{\Large \textbf{User Manual}}\\[0.3em]'))
    doc.append(NoEscape(r'{\large \textcolor{acigray}{ACI 318M-25 Compliant Design Module}}\\[0.2em]'))
    doc.append(NoEscape(r'{\normalsize Version 0.8.2 beta \quad \textcolor{acigray}{---} \quad April 2026}'))
    doc.append(NoEscape(r'\end{center}'))
    doc.append(NoEscape(r'\vspace{2em}'))
    doc.append(NoEscape(r'\hrule'))
    doc.append(NoEscape(r'\vspace{1.5em}'))

    # ===================================================================
    # 1. OVERVIEW
    # ===================================================================
    with doc.create(Section('Overview')):
        doc.append(NoEscape(
            r'The \textbf{RC Beam Designer} is a web-based structural engineering tool that performs '
            r'strength and serviceability design of reinforced concrete beams in full compliance with '
            r'\textbf{ACI 318M-25} (\textit{Building Code Requirements for Structural Concrete}). '
            r'The module covers rectangular sections under combined flexure, shear, and torsion, with '
            r'optional seismic provisions for Ordinary (OMF), Intermediate (IMF), and Special Moment '
            r'Frames (SMF).'
        ))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(r'\textbf{Design outputs include:}'))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Flexural reinforcement (top \& bottom bars)'))
            lst.add_item(NoEscape(r'Transverse reinforcement (stirrups) --- span and hinge zones'))
            lst.add_item(NoEscape(r'Torsional reinforcement (longitudinal \textit{Al} and transverse \textit{At/s})'))
            lst.add_item(NoEscape(r'Torsional skin/web bars where required'))
            lst.add_item(NoEscape(r'Section capacity check: \(\varphi M_n\), \(\varphi V_n\), \(\varphi T_n\)'))
            lst.add_item(NoEscape(r'Demand-to-Capacity Ratio (DCR)'))
            lst.add_item(NoEscape(r'Immediate and long-term deflections per ACI 318M-25 \S24'))
            lst.add_item(NoEscape(r'Quantity take-off (concrete volume, formwork area, rebar weight)'))

    # ===================================================================
    # 2. SCOPE & LIMITATIONS
    # ===================================================================
    with doc.create(Section('Scope and Limitations')):
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'Rectangular cross-sections only (T-beam / L-beam flanges not activated).'))
            lst.add_item(NoEscape(r'Normal-weight concrete assumed (\(\lambda = 1.0\)).'))
            lst.add_item(NoEscape(r'Forces are entered directly as factored demands '
                                  r'(\(M_u\), \(V_u\), \(T_u\)); no load-combination engine is included.'))
            lst.add_item(NoEscape(r'Three design zones only: left support, midspan, right support. '
                                  r'Reinforcement is automatically unified across zones for constructability.'))
            lst.add_item(NoEscape(r'Deflection is computed from midspan service moments (dead + live).'))
            lst.add_item(NoEscape(r'Development lengths are calculated but bar cut-off detailing is not automated.'))
            lst.add_item(NoEscape(r'The module does \textbf{not} check beam-column joint shear.'))

    # ===================================================================
    # 3. INPUT PARAMETERS
    # ===================================================================
    with doc.create(Section('Input Parameters')):

        with doc.create(Subsection('Geometry')):
            doc.append(NoEscape(
                r'All dimensions are entered in \textbf{millimetres (mm)}.'
            ))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{4cm} p{2.5cm} p{7.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    ('Width \\(b_w\\)', 'mm', 'Beam web width.'),
                    ('Height \\(h\\)', 'mm', 'Overall beam depth.'),
                    ('Effective depth \\(d\\)', 'mm',
                     'Distance from extreme compression fibre to centroid of tension steel. '
                     'Typically \\(d = h - c_c - d_{\\mathrm{stirrup}} - d_b/2\\).'),
                    ('Center-to-center span \\(L\\)', 'mm', 'Overall beam span between support centrelines.'),
                    ('Clear span \\(L_n\\)', 'mm',
                     'Clear distance between column faces. Used for SMF capacity design shear.'),
                    ('Max aggregate size \\(d_{\\mathrm{agg}}\\)', 'mm',
                     'Maximum nominal aggregate size. Drives minimum stirrup spacing '
                     '(\\(s \\geq 3\\,d_{\\mathrm{agg}}\\), ACI 318M-25 \\S26.4.2.1) and '
                     'minimum clear bar spacing.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

        with doc.create(Subsection('Materials')):
            with doc.create(LongTable('p{4cm} p{2.5cm} p{7.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Parameter'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    ("\\(f'_c\\)", 'MPa', "Specified concrete compressive strength."),
                    ('\\(f_y\\)', 'MPa', 'Yield strength of longitudinal reinforcement.'),
                    ('\\(f_{yt}\\)', 'MPa', 'Yield strength of transverse reinforcement (stirrups).'),
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
                    ('Seismic Design Category', 'ACI/ASCE classification A through F. '
                                                'SDC D--F triggers SMF requirements when frame system is Special.'),
                    ('Frame System', r'\textbf{Ordinary (OMF)} --- no special seismic provisions. '
                                    r'\textbf{Intermediate (IMF)} --- intermediate ductility. '
                                    r'\textbf{Special (SMF)} --- full ACI 18.6 provisions.'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()

        with doc.create(Subsection('Preferred Reinforcement Sizes')):
            with doc.create(Itemize()) as lst:
                lst.add_item(NoEscape(r'\textbf{Main bar diameter}: preferred size for top and bottom '
                                      r'longitudinal bars (D16 -- D36).'))
                lst.add_item(NoEscape(r'\textbf{Stirrup diameter}: preferred transverse bar size (D10 -- D16 '
                                      r'typical). The solver upsizes only if the preferred size cannot satisfy '
                                      r'strength demands.'))
                lst.add_item(NoEscape(r'\textbf{Side bar diameter}: torsional skin bar size for web bars '
                                      r'spaced \(\leq 300\,\mathrm{mm}\) along the height.'))

        with doc.create(Subsection('Applied Forces')):
            doc.append(NoEscape(
                r'Forces are factored (LRFD) demands. All three zones must be filled. '
                r'Set a force to zero if it does not apply.'
            ))
            doc.append(NoEscape(r'\medskip'))
            with doc.create(LongTable('p{3.5cm} p{2cm} p{8.5cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Symbol'), bold('Unit'), bold('Description')])
                tbl.add_hline()
                rows = [
                    ('\\(M_u^{-}\\) (top)', 'kN·m', 'Factored hogging (negative) moment --- tension at top.'),
                    ('\\(M_u^{+}\\) (bot)', 'kN·m', 'Factored sagging (positive) moment --- tension at bottom.'),
                    ('\\(V_u\\)', 'kN', 'Factored shear force.'),
                    ('\\(T_u\\)', 'kN·m', 'Factored torsional moment.'),
                    ('\\(V_g\\)', 'kN',
                     'Gravity-load shear at support. Used in SMF capacity-design shear calculation. '
                     'Typically the shear from factored gravity loads alone (no seismic).'),
                    ('\\(M_D\\)', 'kN·m', 'Service (unfactored) dead-load moment at midspan (deflection check).'),
                    ('\\(M_L\\)', 'kN·m', 'Service (unfactored) live-load moment at midspan (deflection check).'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1]), NoEscape(r[2])])
                tbl.add_hline()

    # ===================================================================
    # 4. DESIGN METHODOLOGY
    # ===================================================================
    with doc.create(Section('Design Methodology')):

        # -------------------------------------------------------------- 4.1 Flexure
        with doc.create(Subsection('Flexural Reinforcement Design')):

            with doc.create(Subsubsection('Required Steel Area')):
                doc.append(NoEscape(
                    r'For a given factored moment \(M_u\), the required steel area \(A_s\) is solved from '
                    r'the strength condition \(\varphi M_n \geq M_u\) with \(\varphi = 0.90\) '
                    r'(tension-controlled section). Substituting the rectangular stress-block expressions:'
                ))
                doc.append(_eq(
                    r"\varphi f_y A_s \!\left(d - \frac{A_s f_y}{2 \times 0.85 f'_c b_w}\right) = M_u"
                ))
                doc.append(NoEscape(
                    r'This is rearranged into a quadratic in \(A_s\). '
                    r'If the discriminant is negative the section is too small for tension-controlled '
                    r'behaviour; the module issues a \textbf{WARNING} and uses \(\rho_{\max}\) as a lower bound.'
                ))

            with doc.create(Subsubsection('Minimum and Maximum Steel Ratios')):
                doc.append(NoEscape(r'Per ACI 318M-25 \S9.6.1.2:'))
                doc.append(_eq(
                    r"\rho_{\min} = \max\!\left(\frac{0.25\sqrt{f'_c}}{f_y},\; \frac{1.4}{f_y}\right)"
                ))
                doc.append(NoEscape(r'Maximum ratio (net tensile strain \(\varepsilon_t \geq 0.004\)):'))
                doc.append(_eq(
                    r"\rho_{\max} = \frac{3}{8} \cdot \frac{0.85\,f'_c\,\beta_1}{f_y}"
                ))
                doc.append(NoEscape(
                    r'For SMF beams, \(\rho_{\max}\) is additionally capped at 0.025 '
                    r'(ACI 318M-25 \S18.6.4.1).'
                ))
                doc.append(NoEscape(r'\smallskip'))
                doc.append(NoEscape(
                    r'The concrete stress-block factor \(\beta_1\) is per ACI 318M-25 Table 22.2.2.4.3:'
                ))
                doc.append(_eq(
                    r"\beta_1 = \begin{cases} 0.85 & f'_c \leq 28\,\mathrm{MPa}\\ "
                    r"0.85 - 0.05\,\dfrac{f'_c - 28}{7} & 28 < f'_c \leq 55\,\mathrm{MPa}\\ "
                    r"0.65 & f'_c > 55\,\mathrm{MPa} \end{cases}"
                ))

            with doc.create(Subsubsection('Torsional Contribution to Longitudinal Steel')):
                doc.append(NoEscape(
                    r'When torsion is significant (see Section~\ref{sec:torsion}), an additional '
                    r'longitudinal area \(A_\ell / 2\) is added to both the top and bottom '
                    r'required areas before bar selection.'
                ))

        # -------------------------------------------------------------- 4.2 Torsion
        with doc.create(Subsection('Torsion Design', label='sec:torsion')):

            with doc.create(Subsubsection('Threshold Torsion')):
                doc.append(NoEscape(
                    r'Torsion is neglected when \(T_u \leq \varphi T_{th}\) '
                    r'(ACI 318M-25 \S22.7.3.1), where:'
                ))
                doc.append(_eq(
                    r"T_{th} = 0.083\,\lambda\sqrt{f'_c}\;\frac{A_{cp}^2}{p_{cp}}"
                ))
                doc.append(NoEscape(
                    r'with \(A_{cp} = b_w h\) (gross section area) and \(p_{cp} = 2(b_w + h)\) '
                    r'(outer perimeter), \(\varphi_T = 0.75\).'
                ))

            with doc.create(Subsubsection('Torsional Section Properties')):
                doc.append(NoEscape(
                    r'The effective stirrup centroid distance from each face is '
                    r'\(c_c + d_{\mathrm{stirrup}}\). The centerline dimensions of the '
                    r'closed stirrup are:'
                ))
                doc.append(_eq(
                    r'x_1 = b_w - 2c_c - d_{\mathrm{stirrup}}, \qquad '
                    r'y_1 = h - 2c_c - d_{\mathrm{stirrup}}'
                ))
                doc.append(_eq(
                    r'A_{oh} = x_1\,y_1, \quad p_h = 2(x_1 + y_1), \quad A_o = 0.85\,A_{oh}'
                ))

            with doc.create(Subsubsection('Transverse Torsional Reinforcement')):
                doc.append(NoEscape(r'Required \(A_t / s\) per ACI 318M-25 Eq.\,(22.7.6.1a):'))
                doc.append(_eq(
                    r'\frac{A_t}{s} = \frac{T_u}{\varphi_T \cdot 2\,A_o\,f_{yt}\,\cot\theta}, '
                    r'\qquad \theta = 45^\circ'
                ))

            with doc.create(Subsubsection('Longitudinal Torsional Reinforcement')):
                doc.append(NoEscape(r'Required total \(A_\ell\) per ACI 318M-25 Eq.\,(22.7.6.1b):'))
                doc.append(_eq(
                    r'A_\ell = \frac{A_t}{s}\,p_h\,\frac{f_{yt}}{f_y}\,\cot^2\!\theta'
                ))
                doc.append(NoEscape(r'Subject to the minimum (ACI 318M-25 Eq.\,(22.7.6.2)):'))
                doc.append(_eq(
                    r"A_{\ell,\min} = \frac{0.42\sqrt{f'_c}\,A_{cp}}{f_y} "
                    r'- \frac{A_t}{s}\,p_h\,\frac{f_{yt}}{f_y}'
                ))
                doc.append(NoEscape(
                    r'\(A_\ell\) is distributed to top, bottom and side bars proportionally to '
                    r'their perimeter contribution. Side bars are required when the inner stirrup '
                    r'height exceeds 300~mm (ACI 318M-25 \S26.7.2.2), spaced \(\leq 300\)~mm.'
                ))

            with doc.create(Subsubsection('Combined Shear–Torsion Section Check')):
                doc.append(NoEscape(r'Per ACI 318M-25 Eq.\,(22.7.7.1a):'))
                doc.append(_eq(
                    r'\sqrt{\!\left(\frac{V_u}{b_w d}\right)^{\!2} + '
                    r'\left(\frac{T_u\,p_h}{1.7\,A_{oh}^2}\right)^{\!2}} '
                    r"\leq \varphi_v\!\left(\frac{V_c}{b_w d} + \frac{0.66\sqrt{f'_c}}{1}\right)"
                ))

        # -------------------------------------------------------------- 4.3 Shear
        with doc.create(Subsection('Shear Design')):

            with doc.create(Subsubsection('Concrete Shear Strength — ACI 318M-25 Table 22.5.5.1')):
                doc.append(NoEscape(
                    r'The module selects between two rows of ACI 318M-25 Table~22.5.5.1 based on '
                    r'whether the provided transverse reinforcement meets the minimum ratio:'
                ))
                doc.append(_eq(
                    r"A_{v,\min}/s = \max\!\left(\frac{0.062\sqrt{f'_c}\,b_w}{f_{yt}},\; "
                    r'\frac{0.35\,b_w}{f_{yt}}\right)'
                ))
                doc.append(NoEscape(
                    r'\textbf{Simplified row} (used when \(A_v/s \geq A_{v,\min}/s\) or during the '
                    r'design-phase where stirrups are not yet selected):'
                ))
                doc.append(_eq(r"V_c = 0.17\,\lambda\,\sqrt{f'_c}\,b_w\,d"))
                doc.append(NoEscape(
                    r'\textbf{Detailed row} (used in the capacity-check phase when \(A_v/s < A_{v,\min}/s\) '
                    r'or no stirrups are present):'
                ))
                doc.append(_eq(
                    r"V_c = 0.66\,\lambda_s\,\lambda\,\rho_w^{1/3}\,\sqrt{f'_c}\,b_w\,d"
                ))
                doc.append(NoEscape(
                    r'where the \textbf{size effect factor} \(\lambda_s\) accounts for reduced aggregate '
                    r'interlock in deep beams (ACI 318M-25 Table~22.5.5.1, footnote\,\textit{e}):'
                ))
                doc.append(_eq(
                    r'\lambda_s = \min\!\left(1.0,\; \sqrt{\frac{2}{1 + 0.004\,d}}\right)'
                    r'\quad (d\ \mathrm{in\ mm})'
                ))
                doc.append(NoEscape(
                    r'\(\rho_w = A_s / (b_w d)\) is the longitudinal tensile reinforcement ratio. '
                    r'For the current implementation \(\lambda = 1.0\) (normal-weight concrete). '
                    r'The \(\lambda_s\) factor is always \(\leq 1.0\) and becomes governing for '
                    r'\(d > 250\)~mm.'
                ))

            with doc.create(Subsubsection('Steel Shear Contribution')):
                doc.append(_eq(r'V_s = \frac{n_{\mathrm{legs}}\,A_{\mathrm{bar}}\,f_{yt}\,d}{s}'))
                doc.append(NoEscape(
                    r"capped at \(V_{s,\max} = 0.66\sqrt{f'_c}\,b_w\,d\) per ACI 318M-25 \S22.5.8.2. "
                    r'\(\varphi_V = 0.75\).'
                ))

            with doc.create(Subsubsection('Maximum Stirrup Spacing')):
                doc.append(NoEscape(r'Span zone (ACI 318M-25 \S9.7.6.2.2):'))
                doc.append(_eq(
                    r"s_{\max} = \begin{cases} \min(d/4,\;300\,\mathrm{mm}) & V_s > 0.33\sqrt{f'_c}\,b_w\,d \\ "
                    r'\min(d/2,\;600\,\mathrm{mm}) & \text{otherwise} \end{cases}'
                ))
                doc.append(NoEscape(r'When torsion is significant an additional limit applies:'))
                doc.append(_eq(r's_{\max} \leq \min\!\left(s_{\mathrm{span}},\; p_h/8,\; 300\,\mathrm{mm}\right)'))

            with doc.create(Subsubsection('Minimum Stirrup Spacing')):
                doc.append(NoEscape(
                    r'Two practical lower limits are enforced. The absolute minimum spacing from '
                    r'concrete consolidation requirements (ACI 318M-25 \S26.4.2.1):'
                ))
                doc.append(_eq(r's_{\min} = 3\,d_{\mathrm{agg}}'))
                doc.append(NoEscape(
                    r'The minimum centre-to-centre pitch between adjacent stirrup legs '
                    r'(ACI 318M-25 \S25.8.1, assuming 25~mm nominal aggregate):'
                ))
                doc.append(_eq(
                    r'\Delta_{\mathrm{leg}} = d_{b,\mathrm{main}} + \max\!\left(25\,\mathrm{mm},\; '
                    r'\tfrac{4}{3}\,d_{\mathrm{agg}}\right)'
                ))
                doc.append(NoEscape(r'Maximum number of stirrup legs:'))
                doc.append(_eq(
                    r'n_{\mathrm{legs},\max} = '
                    r'\min\!\left(6,\; \left\lfloor \frac{b_w - 2c_c}{\Delta_{\mathrm{leg}}} \right\rfloor + 1\right)'
                ))

        # -------------------------------------------------------------- 4.4 SMF
        with doc.create(Subsection('Seismic Provisions for Special Moment Frames (SMF)')):

            with doc.create(Subsubsection('Geometric Limits — ACI 318M-25 §18.6.2')):
                with doc.create(Itemize()) as lst:
                    lst.add_item(NoEscape(r'Clear-span-to-depth ratio: \(L_n / d \geq 4.0\)'))
                    lst.add_item(NoEscape(r'Width: \(b_w \geq 250\,\mathrm{mm}\)'))
                    lst.add_item(NoEscape(r'Width-to-depth ratio: \(b_w / h \geq 0.30\)'))

            with doc.create(Subsubsection('Longitudinal Reinforcement — ACI 318M-25 §18.6.3')):
                doc.append(NoEscape(r'At each joint face (support) the following must hold:'))
                doc.append(_eq(
                    r'M_{n,\mathrm{bot}} \geq \tfrac{1}{2}\,M_{n,\mathrm{top}} \quad '
                    r'\text{(ACI 318M-25 \S18.6.3.2)}'
                ))
                doc.append(NoEscape(
                    r'At every cross-section (top and bottom) the moment capacity must satisfy:'
                ))
                doc.append(_eq(
                    r'M_n \geq \tfrac{1}{4}\,M_{n,\max\,\mathrm{support}} \quad '
                    r'\text{(ACI 318M-25 \S18.6.3.2)}'
                ))
                doc.append(NoEscape(
                    r'Both checks compare \textbf{moment capacities} \(M_n\), '
                    r'not reinforcement areas. If a check fails the solver back-calculates the required '
                    r'\(A_s\) to just meet the moment threshold.'
                ))

            with doc.create(Subsubsection('Capacity Design Shear — ACI 318M-25 §18.6.5')):
                doc.append(NoEscape(
                    r'The design shear \(V_e\) for SMF beams is the greater of the factored shear '
                    r'and the capacity-design shear computed from probable moment capacities:'
                ))
                doc.append(_eq(
                    r'V_e = \max\!\left(V_u,\; V_g + \frac{M_{pr,L} + M_{pr,R}}{L_n}\right)'
                ))
                doc.append(NoEscape(
                    r'where \(M_{pr}\) is the \textbf{probable moment capacity} computed with '
                    r'\(f_{y,pr} = 1.25\,f_y\) and \(\varphi = 1.0\):'
                ))
                doc.append(_eq(
                    r"M_{pr} = A_s\,f_{y,pr}\!\left(d - \frac{a}{2}\right) + A_s'\,f_{y,pr}(d - d')"
                ))
                doc.append(NoEscape(
                    r"The compression steel cover \(d'\) is computed from the actual bar geometry: "
                    r"\(d' = c_c + d_{b,\mathrm{stirrup}} + \tfrac{1}{2}\,d_{b,\mathrm{main}}\)."
                ))

            with doc.create(Subsubsection('Concrete Contribution — ACI 318M-25 §18.6.5.2')):
                doc.append(NoEscape(
                    r'When the earthquake-induced shear component exceeds 50\,\% of \(V_e\):'
                ))
                doc.append(_eq(
                    r'(V_e - V_g) > 0.5\,V_e \implies V_c = 0'
                ))

            with doc.create(Subsubsection('Confinement Stirrup Spacing — ACI 318M-25 §18.6.4')):
                doc.append(NoEscape(
                    r'Within the hinge zone \(\ell_o = 2h\) from each face of the support, '
                    r'stirrups must not exceed:'
                ))
                doc.append(_eq(
                    r's_{\mathrm{hinge}} \leq \min\!\left(\frac{d}{4},\; 6\,d_{b,\mathrm{main}},\; 150\,\mathrm{mm}\right)'
                ))

        # -------------------------------------------------------------- 4.5 Deflection
        with doc.create(Subsection('Deflection Check')):

            with doc.create(Subsubsection('Effective Moment of Inertia — ACI 318M-25 §24.2.3.5')):
                doc.append(NoEscape(
                    r'The effective moment of inertia \(I_e\) interpolates between '
                    r'\(I_g\) (uncracked) and \(I_{cr}\) (fully cracked):'
                ))
                doc.append(_eq(
                    r'I_e = \frac{I_{cr}}{1 - \!\left(\dfrac{\tfrac{2}{3}M_{cr}}{M_a}\right)^{\!2} '
                    r'\!\left(1 - \dfrac{I_{cr}}{I_g}\right)}'
                    r'\qquad (I_{cr} \leq I_e \leq I_g)'
                ))
                doc.append(NoEscape(r'where the cracking moment is:'))
                doc.append(_eq(
                    r"M_{cr} = \frac{f_r\,I_g}{y_t}, \qquad f_r = 0.62\,\lambda\,\sqrt{f'_c}"
                ))
                doc.append(NoEscape(
                    r'The cracked moment of inertia \(I_{cr}\) is found from the neutral axis depth '
                    r'\(kd\) for the transformed doubly-reinforced section, solving:'
                ))
                doc.append(_eq(
                    r"\frac{b\,(kd)^2}{2} + (n-1)\,A_s'\,(kd - d') = n\,A_s\,(d - kd)"
                ))

            with doc.create(Subsubsection('Immediate Deflections')):
                doc.append(NoEscape(r'\textbf{Span beam} --- midspan deflection via Simpson\'s rule:'))
                doc.append(_eq(
                    r'\delta_{\mathrm{imm}} = \frac{L^2}{96\,E_c\,I_e}(M_A + 10\,M_C + M_B)'
                ))
                doc.append(NoEscape(
                    r'\(M_A\), \(M_C\), \(M_B\) are service moments at the left support, midspan, '
                    r'and right support respectively. Support moments are scaled from the given '
                    r'ultimate-to-service ratio of the midspan moment.'
                ))
                doc.append(NoEscape(r'\medskip'))
                doc.append(NoEscape(r'\textbf{Cantilever} --- tip deflection via Simpson\'s rule:'))
                doc.append(_eq(
                    r'\delta_{\mathrm{tip}} = \frac{L^2}{6\,E_c\,I_e}(2\,M_{\mathrm{mid}} + M_{\mathrm{fixed}})'
                ))
                doc.append(NoEscape(
                    r'For cantilevers, \(I_e\) is evaluated at the fixed support per '
                    r'ACI 318M-25 Table~24.2.3.6b.'
                ))

            with doc.create(Subsubsection('Long-Term Deflection')):
                doc.append(NoEscape(r'Per ACI 318M-25 \S24.2.4:'))
                doc.append(_eq(
                    r'\delta_{\mathrm{long}} = \delta_{\mathrm{live}} + \xi_t\,\delta_{\mathrm{sus}}'
                ))
                doc.append(_eq(
                    r"\xi_t = \frac{2.0}{1 + 50\,\rho'}, \qquad "
                    r"\rho' = \frac{A_s'}{b_w d}"
                ))
                doc.append(NoEscape(
                    r'\(\xi_t = 2.0\) for the sustained (dead) loading time factor. '
                    r'\(\delta_{\mathrm{sus}}\) is the immediate deflection under sustained loads '
                    r'(\(M_D + 0.25\,M_L\)).'
                ))

            with doc.create(Subsubsection('Allowable Deflection Limits')):
                with doc.create(LongTable('p{4cm} p{9cm}')) as tbl:
                    tbl.add_hline()
                    tbl.add_row([bold('Limit'), bold('Description')])
                    tbl.add_hline()
                    tbl.add_row([NoEscape(r'\(\delta_{\mathrm{live}} \leq L/360\)'),
                                 NoEscape(r'Immediate live-load deflection (ACI 318M-25 Table~24.2.2).')])
                    tbl.add_row([NoEscape(r'\(\delta_{\mathrm{long}} \leq L/240\)'),
                                 NoEscape(r'Long-term deflection for non-sensitive finishes (user-selectable).')])
                    tbl.add_row([NoEscape(r'\(\delta_{\mathrm{long}} \leq L/480\)'),
                                 NoEscape(r'Long-term deflection for sensitive finishes (user-selectable).')])
                    tbl.add_hline()

    # ===================================================================
    # 5. UNIFICATION ENGINE
    # ===================================================================
    with doc.create(Section('Unification and Constructability Engine')):
        doc.append(NoEscape(
            r'After the three zones are independently designed, the module enforces '
            r'constructability rules before reporting final results:'
        ))
        with doc.create(Enumerate()) as lst:
            lst.add_item(NoEscape(
                r'\textbf{Stirrup legs:} The maximum number of legs across all three zones is adopted '
                r'uniformly. This prevents field confusion from varying cross-tie arrangements.'))
            lst.add_item(NoEscape(
                r'\textbf{Bar count floor:} The number of bars in any zone is at least equal to the '
                r'number of stirrup legs (to ensure the stirrup cage has at least one bar at every corner).'))
            lst.add_item(NoEscape(
                r'\textbf{Support bar synchronisation:} The governing (larger) top-bar count from '
                r'either support is applied to both supports. Similarly for bottom bars.'))
            lst.add_item(NoEscape(
                r'\textbf{Hinge spacing (SMF):} The smaller hinge-zone stirrup spacing from either '
                r'support is applied to both. For cantilevers only the fixed end carries a hinge zone.'))
            lst.add_item(NoEscape(
                r'\textbf{Torsion skin bars:} The zone requiring the most skin bars governs all zones.'))
            lst.add_item(NoEscape(
                r'\textbf{Capacity recalculation:} All capacities (\(\varphi M_n\), \(\varphi V_n\), '
                r'\(\varphi T_n\), DCR) are recomputed for the unified section.'))

    # ===================================================================
    # 6. DESIGN RESULTS INTERPRETATION
    # ===================================================================
    with doc.create(Section('Interpreting Design Results')):

        with doc.create(Subsection('Section Capacities')):
            with doc.create(LongTable('p{4cm} p{9cm}')) as tbl:
                tbl.add_hline()
                tbl.add_row([bold('Output'), bold('Description')])
                tbl.add_hline()
                rows = [
                    (r'\(\varphi M_n\) (top/bot)', r'Factored moment capacities for negative and positive bending.'),
                    (r'\(\varphi V_n / V_e\)',
                     r'Factored shear capacity and the design shear (= \(V_u\) for non-SMF; '
                     r'= capacity-design shear for SMF).'),
                    (r'\(\varphi T_n\)',
                     r'Factored torsion capacity. Shown as 0.0 when \(T_u \leq \varphi T_{th}\) '
                     r'(torsion below threshold). The DCR does not include torsion in that case.'),
                    ('DCR',
                     r'Maximum of the four utilisation ratios: '
                     r'\(\mathrm{DCR} = \max(M_u^{-}/\varphi M_{n,t},\; M_u^{+}/\varphi M_{n,b},\; '
                     r'V_u/\varphi V_n,\; T_u/\varphi T_n)\). '
                     r'Values \(\leq 1.00\) indicate an adequate section (shown in green).'),
                ]
                for r in rows:
                    tbl.add_row([NoEscape(r[0]), NoEscape(r[1])])
                tbl.add_hline()

        with doc.create(Subsection('Reinforcement Schedule')):
            with doc.create(Itemize()) as lst:
                lst.add_item(NoEscape(
                    r'\textbf{Top bars:} Hogging (tension-top) reinforcement. '
                    r'At supports these include any additional steel required by the SMF 25\% rule.'))
                lst.add_item(NoEscape(
                    r'\textbf{Bottom bars:} Sagging (tension-bottom) reinforcement.'))
                lst.add_item(NoEscape(
                    r'\textbf{Web bars:} Torsional skin bars placed along the height, '
                    r'one bar per side per layer, spaced \(\leq 300\)~mm.'))
                lst.add_item(NoEscape(
                    r'\textbf{Stirrups (Hinge):} Displayed at support zones for SMF. '
                    r'Applies over \(\ell_o = 2h\) from each joint face.'))
                lst.add_item(NoEscape(
                    r'\textbf{Stirrups (Span):} Applies over the middle portion of the beam.'))

        with doc.create(Subsection('Design Notes')):
            doc.append(NoEscape(
                r'The \textit{Notes} panel in each zone summarises design decisions and warnings. '
                r'Icon legend: \(\triangleright\) informational, \(\triangle\) warning or SMF '
                r'trigger, CRITICAL: section inadequate (increase dimensions or loads must be reduced).'
            ))

    # ===================================================================
    # 7. QUANTITY TAKE-OFF
    # ===================================================================
    with doc.create(Section('Quantity Take-Off')):
        doc.append(NoEscape(
            r'The QTO section reports estimated material quantities for procurement. '
            r'Rebar lengths account for standard 90° hooks where applicable:'
        ))
        with doc.create(Itemize()) as lst:
            lst.add_item(NoEscape(r'\textbf{Hook length} (per end): \(12\,d_b + 100\,\mathrm{mm}\)'))
            lst.add_item(NoEscape(r'\textbf{Splice length}: \(40\,d_b\) (used for bars longer than 12\,m)'))
        doc.append(NoEscape(r'\medskip'))
        doc.append(NoEscape(
            r'Rebar orders are expressed in terms of the optimal combination of '
            r'Philippine standard stock lengths (6\,m, 7.5\,m, 9\,m, 10.5\,m, 12\,m) '
            r'that minimises waste (1D bin-packing). '
            r'Stirrup quantities are estimated from the total length of all stirrup runs '
            r'(hinge + span zones on both sides, plus midspan), divided into 12\,m stock.'
        ))

    # ===================================================================
    # 8. REFERENCES
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
                r'MacGregor, J.\,G. and Wight, J.\,K. \textit{Reinforced Concrete: Mechanics and '
                r'Design}, 7th ed. Prentice Hall, 2016.'))

    # ------------------------------------------------------------------ compile
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, 'beam_manual')
        doc.generate_pdf(tex_path, clean_tex=True, compiler='pdflatex',
                         compiler_args=['-interaction=nonstopmode'])
        pdf_path = tex_path + '.pdf'
        with open(pdf_path, 'rb') as f:
            return f.read()
