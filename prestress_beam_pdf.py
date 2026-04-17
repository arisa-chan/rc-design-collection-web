import math
import json
import tempfile
import os
from pylatex import (
    Document, Section, Subsection, Math, Command, NoEscape,
    Head, Foot, PageStyle, Itemize, Tabular,
)
from pylatex.utils import bold, escape_latex
from aci318m25_prestress import (
    ACI318M25PrestressDesign,
    SpanGeometry,
    PrestressMaterialType,
    PrestressingMethod,
)


# Characters that pdflatex cannot render directly — map to inline LaTeX math.
_UNICODE_TO_LATEX = {
    'φ': r'\(\phi\)', 'Φ': r'\(\Phi\)', 'μ': r'\(\mu\)',
    'λ': r'\(\lambda\)', 'γ': r'\(\gamma\)', 'α': r'\(\alpha\)',
    'β': r'\(\beta\)', 'δ': r'\(\delta\)', 'ε': r'\(\varepsilon\)',
    'σ': r'\(\sigma\)', 'ρ': r'\(\rho\)', 'θ': r'\(\theta\)',
    '≤': r'\(\leq\)', '≥': r'\(\geq\)', '≠': r'\(\neq\)',
    '×': r'\(\times\)', '÷': r'\(\div\)', '±': r'\(\pm\)',
    '·': r'\(\cdot\)', '°': r'\({}^{\circ}\)', '≈': r'\(\approx\)',
    '√': r'\(\surd\)', '²': r'\({}^{2}\)', '³': r'\({}^{3}\)',
    '→': r'\(\to\)', '–': r'--', '—': r'---',
    '’': r"'", '‘': r'`', '“': r"``", '”': r"''",
}


def _sanitize_for_latex(text: str) -> NoEscape:
    """Escape LaTeX special characters then replace Unicode math symbols."""
    escaped = escape_latex(str(text))
    for char, repl in _UNICODE_TO_LATEX.items():
        escaped = escaped.replace(char, repl)
    return NoEscape(escaped)


def _eq(expr: str) -> Math:
    """Return a single displayed equation from a raw LaTeX expression string."""
    return Math(data=[NoEscape(expr)])


def _reconstruct_span(data, span_idx: int) -> SpanGeometry:
    """Rebuild SpanGeometry from form data for the given 0-based span index."""
    try:
        L = float(json.loads(data.spans_data)[span_idx].get("length", 10000.0))
    except Exception:
        L = 10000.0
    return SpanGeometry(
        length=L,
        width=data.width,
        height=data.height,
        t_flange_width=data.t_flange_width,
        t_flange_height=data.t_flange_height,
    )


def _span_loads(data, span_idx: int):
    """Aggregate DL/SDL/LL for the given 0-based span index (kN/m)."""
    w_dl = w_sdl = w_ll = 0.0
    try:
        for ent in json.loads(data.loads_data):
            if int(ent.get("span", 1)) - 1 == span_idx:
                w_dl  += float(ent.get("dl",  0.0))
                w_sdl += float(ent.get("sdl", 0.0))
                w_ll  += float(ent.get("ll",  0.0))
    except Exception:
        pass
    return w_dl, w_sdl, w_ll


def _tendon_props(data):
    """Return (Aps_per_strand, fpu, fpy) from ACI318M25PrestressDesign tables."""
    try:
        design = ACI318M25PrestressDesign()
        mat = design.get_prestress_material(
            PrestressMaterialType(data.material), str(data.strand_dia))
        return float(mat["area"]), float(mat["fpu"]), float(mat["fpy"])
    except Exception:
        return 98.7, 1860.0, 1674.0


def _pmethod(data):
    """Return PrestressingMethod enum for data.method."""
    try:
        return PrestressingMethod(data.method)
    except Exception:
        return PrestressingMethod.PRETENSIONED


def generate_prestress_beam_report(data, results):
    """Generate a detailed step-by-step ACI 318M-25 prestressed beam calculation report.

    Each calculation follows the format:
        symbol = formula = substituted values = result [unit]

    Parameters
    ----------
    data : PrestressBeamModel
    results : list[PrestressAnalysisResult]

    Returns
    -------
    bytes  -- raw PDF content
    """
    geometry_options = {"margin": "1in", "headheight": "38pt", "includeheadfoot": True}
    doc = Document(geometry_options=geometry_options)

    doc.preamble.append(NoEscape(r"\usepackage{amsmath}"))
    doc.preamble.append(NoEscape(r"\usepackage{amssymb}"))
    doc.preamble.append(NoEscape(r"\usepackage{booktabs}"))
    doc.preamble.append(NoEscape(r"\usepackage{xcolor}"))
    doc.preamble.append(NoEscape(r"\usepackage{array}"))
    doc.preamble.append(NoEscape(r"\definecolor{passgreen}{HTML}{15803d}"))
    doc.preamble.append(NoEscape(r"\definecolor{failred}{HTML}{DC2626}"))
    doc.preamble.append(NoEscape(r"\setlength{\parindent}{0pt}"))

    # ── Page header / footer ──────────────────────────────────────────────────
    header = PageStyle("header")
    with header.create(Head("C")):
        with header.create(Tabular("|p{8cm}|p{8cm}|")) as tab:
            tab.add_hline()
            tab.add_row((
                NoEscape(r"\textbf{Project:} " + data.proj_name),
                NoEscape(r"\textbf{Engineer:} " + data.proj_eng),
            ))
            tab.add_hline()
            tab.add_row((
                NoEscape(r"\textbf{Location:} " + data.proj_loc),
                NoEscape(r"\textbf{Date:} " + data.proj_date),
            ))
            tab.add_hline()
    with header.create(Foot("C")):
        header.append(Command("thepage"))

    doc.preamble.append(header)
    doc.change_document_style("header")

    # ── Title ─────────────────────────────────────────────────────────────────
    doc.append(NoEscape(r"\vspace*{1em}"))
    doc.append(Command("begin", "center"))
    doc.append(NoEscape(
        r"\Large\textbf{Prestressed Beam Design -- Step-by-Step Calculations}\\[4pt]"))
    doc.append(NoEscape(r"\normalsize\textit{in accordance with ACI 318M-25 | SI Units}"))
    doc.append(Command("end", "center"))
    doc.append(NoEscape(r"\vspace{1em}"))

    # ── Section 1: Input Summary ──────────────────────────────────────────────
    with doc.create(Section("Input Summary")):

        with doc.create(Subsection("Geometry")):
            with doc.create(Itemize()) as it:
                it.add_item(NoEscape(
                    fr"Web: $b_w = {data.width:.0f}$\,mm, $h = {data.height:.0f}$\,mm"
                ))
                if data.t_flange_width > 0 and data.t_flange_height > 0:
                    it.add_item(NoEscape(
                        fr"Flange: $b_f = {data.t_flange_width:.0f}$\,mm,"
                        fr" $h_f = {data.t_flange_height:.0f}$\,mm"
                    ))
                it.add_item(f"Number of spans: {data.num_spans}")
                try:
                    for j, sp in enumerate(json.loads(data.spans_data)):
                        it.add_item(NoEscape(
                            fr"Span {j + 1}: $L = {sp.get('length', 10000):.0f}$\,mm"
                        ))
                except Exception:
                    pass
                try:
                    for j, supp in enumerate(json.loads(data.supports_data)):
                        it.add_item(f"Support {j + 1}: {supp.get('type', 'column/wall')}")
                except Exception:
                    pass

        with doc.create(Subsection("Materials and Prestress")):
            with doc.create(Itemize()) as it:
                it.add_item(NoEscape(
                    fr"Concrete: $f'_c = {data.fc_prime}$\,MPa,"
                    fr" $f'_{{ci}} = {data.fci_prime}$\,MPa,"
                    fr" $\gamma_c = {data.gamma_c}$\,kN/m$^3$"
                ))
                it.add_item(f"Prestressing method: {data.method.replace('_', ' ').title()}")
                it.add_item(f"Tendon material: {data.material.replace('_', ' ').upper()}")
                it.add_item(NoEscape(fr"Strand/bar dia.: {data.strand_dia}\,mm"))
                it.add_item(f"Number of tendons: {data.num_tendons}")
                # Per-span tendon details (derive from spans_detail_data)
                try:
                    import json as _json
                    _pdf_sd = _json.loads(data.spans_detail_data) if data.spans_detail_data else []
                except Exception:
                    _pdf_sd = []
                _pdf_first_sd = _pdf_sd[0] if _pdf_sd else {}
                _pdf_e = _pdf_first_sd.get('e_m', 200.0)
                _pdf_profile = _pdf_first_sd.get('profile', 'parabolic').replace('_', ' ').title()
                it.add_item(NoEscape(fr"Eccentricity (Span 1 midspan): $e = {_pdf_e}$\,mm"))
                it.add_item(f"Tendon profile (Span 1): {_pdf_profile}")
                it.add_item(NoEscape(
                    fr"Jacking force: {data.jacking_force:.1f}\,kN/tendon"
                    + (" (auto)" if data.jacking_force <= 0 else "")
                ))
                it.add_item(NoEscape(
                    fr"Friction: $\mu = {data.friction_mu}$,"
                    fr" $k = {data.friction_k}$\,m$^{{-1}}$"
                ))
                it.add_item(NoEscape(fr"Anchorage slip: $\Delta_{{anc}} = {data.slip:.1f}$\,mm"))
                it.add_item(NoEscape(
                    fr"Time-dep. loss: {data.time_loss_mpa:.1f}\,MPa"
                    + (" (auto)" if data.time_loss_mpa <= 0 else "")
                ))
                import math as _pdf_m
                _pdf_as_bot = max(
                    (_pdf_m.pi/4*float(sd.get('bd_m',20))**2*int(sd.get('bn_m',0)) for sd in _pdf_sd),
                    default=0.0
                )
                _pdf_as_top = max(
                    (_pdf_m.pi/4*float(sd.get('td_m',16))**2*int(sd.get('tn_m',0)) for sd in _pdf_sd),
                    default=0.0
                )
                if _pdf_as_bot > 0 or _pdf_as_top > 0:
                    it.add_item(NoEscape(
                        fr"Passive rebar: $f_y = {data.rebar_fy}$\,MPa,"
                        fr" $A_s = {_pdf_as_bot:.1f}$\,mm$^2$ (bot.),"
                        fr" $A'_s = {_pdf_as_top:.1f}$\,mm$^2$ (top.)"
                    ))
                it.add_item(NoEscape(
                    fr"Long-term multiplier: $\lambda_\Delta = {data.long_term_multiplier}$"
                    r" (ACI Table 24.2.4.1.3)"
                ))
                it.add_item(NoEscape(
                    fr"Deflection limit: $L/{data.deflection_limit:.0f}$"
                    r" (ACI Table 24.2.2)"
                ))

    # ── Section 2: ACI 318M-25 Permissible Stresses ───────────────────────────
    fci = data.fci_prime
    fc  = data.fc_prime

    with doc.create(Section("ACI 318M-25 Permissible Stresses")):
        with doc.create(Subsection("At Transfer --- ACI Table 24.5.3")):
            with doc.create(Tabular("p{6.5cm}p{4.5cm}p{3.5cm}")) as tab:
                tab.add_hline()
                tab.add_row((bold("Condition"), bold("Limit"), bold("Reference")))
                tab.add_hline()
                tab.add_row((
                    "Compression (ends)",
                    NoEscape(fr"$-0.70\,f'_{{ci}} = -{0.70*fci:.2f}$\,MPa"),
                    "Table 24.5.3.1",
                ))
                tab.add_row((
                    "Compression (other sections)",
                    NoEscape(fr"$-0.60\,f'_{{ci}} = -{0.60*fci:.2f}$\,MPa"),
                    "Table 24.5.3.2",
                ))
                tab.add_row((
                    "Tension (ends)",
                    NoEscape(fr"$+0.50\sqrt{{f'_{{ci}}}} = +{0.50*math.sqrt(fci):.2f}$\,MPa"),
                    "Table 24.5.3.1",
                ))
                tab.add_row((
                    "Tension (other sections)",
                    NoEscape(fr"$+0.25\sqrt{{f'_{{ci}}}} = +{0.25*math.sqrt(fci):.2f}$\,MPa"),
                    "Table 24.5.3.2",
                ))
                tab.add_hline()

        with doc.create(Subsection("At Service --- ACI Table 24.5.4.1")):
            with doc.create(Tabular("p{6.5cm}p{4.5cm}p{3.5cm}")) as tab:
                tab.add_hline()
                tab.add_row((bold("Condition"), bold("Limit"), bold("Reference")))
                tab.add_hline()
                tab.add_row((
                    "Compression (sustained load)",
                    NoEscape(fr"$-0.45\,f'_c = -{0.45*fc:.2f}$\,MPa"),
                    "Table 24.5.4.1",
                ))
                tab.add_row((
                    "Compression (total load)",
                    NoEscape(fr"$-0.60\,f'_c = -{0.60*fc:.2f}$\,MPa"),
                    "Table 24.5.4.1",
                ))
                tab.add_row((
                    "Tension, Class U (uncracked)",
                    NoEscape(fr"$+0.62\sqrt{{f'_c}} = +{0.62*math.sqrt(fc):.2f}$\,MPa"),
                    "Table 24.5.4.1",
                ))
                tab.add_row((
                    "Tension, Class T (transition)",
                    NoEscape(fr"$+1.00\sqrt{{f'_c}} = +{1.00*math.sqrt(fc):.2f}$\,MPa"),
                    "Table 24.5.4.1",
                ))
                tab.add_hline()

    # ── Section 3: Detailed Step-by-Step Calculations per Span ───────────────
    with doc.create(Section("Detailed Calculations")):

        # Shared tendon / material data (same for every span)
        Aps_1, fpu, fpy = _tendon_props(data)
        Aps       = Aps_1 * data.num_tendons
        method_en = _pmethod(data)
        is_pt     = method_en in (
            PrestressingMethod.POSTTENSIONED_BONDED,
            PrestressingMethod.POSTTENSIONED_UNBONDED,
        )
        Ec = 4700.0 * math.sqrt(data.fc_prime)   # MPa  (ACI 19.2.2.1)
        Es = 200_000.0                             # MPa
        n  = Es / Ec

        for res in results:
            si   = res.span_index
            span = _reconstruct_span(data, si)
            w_dl, w_sdl, w_ll = _span_loads(data, si)
            w_tot = w_dl + w_sdl + w_ll
            wu    = 1.2 * w_dl + 1.2 * w_sdl + 1.6 * w_ll
            L_mm  = span.length
            L_m   = L_mm / 1000.0

            # Section properties
            A  = span.area
            I  = span.moment_of_inertia
            yt = span.yt
            yb = span.yb
            bw = data.width
            bf = data.t_flange_width  if data.t_flange_width  > 0 else data.width
            hf = data.t_flange_height if data.t_flange_width  > 0 else data.height
            try:
                import json as _json_pdf
                _sd_list = _json_pdf.loads(data.spans_detail_data) if data.spans_detail_data else []
            except Exception:
                _sd_list = []
            _sd_span = _sd_list[res.span_index] if res.span_index < len(_sd_list) else {}
            e  = float(_sd_span.get('e_m', 200.0))
            dp = yt + e

            # Prestress forces (from stored results)
            fpi = res.fpi
            fpe = res.fpe
            Pi  = Aps * fpi      # N
            Pe  = Aps * fpe      # N

            # Losses (reconstructed with same formulas as the library)
            Mg_nmm   = w_dl * L_m**2 / 8.0 * 1e6                  # N·mm
            fc_cir   = Pi / A + (Pi * e**2) / I - (Mg_nmm * e) / I
            delta_es = (0.5 if is_pt else 1.0) * (Es / Ec) * fc_cir
            delta_td = (data.time_loss_mpa if data.time_loss_mpa > 0
                        else (205.0 if is_pt else 240.0))
            if is_pt:
                delta_anc = (data.slip / L_mm) * Es
                alpha_rad = 8.0 * e / L_mm
                delta_fr  = fpi * (data.friction_mu * alpha_rad
                                   + (data.friction_k / 1000.0) * (L_mm / 2.0))
            else:
                delta_anc = delta_fr = alpha_rad = 0.0
            delta_total = delta_es + delta_td + delta_anc + delta_fr

            # Back-calculate service and dead-load moments at midspan from stored stresses
            # f_top_s = -(Pe/A) + (Pe·e·yt)/I - (Ms·yt)/I  →  Ms·yt/I = ...
            Ms_mid = (I / yt * (-(Pe / A) + (Pe * e * yt) / I - res.mid_st_s)) / 1e6
            Md_mid = (I / yt * (-(Pi / A) + (Pi * e * yt) / I - res.mid_st_i)) / 1e6

            # Flexural strength intermediates
            fpy_fpu = fpy / fpu
            if fpy_fpu >= 0.90:
                gamma_p = 0.28
            elif fpy_fpu >= 0.80:
                gamma_p = 0.40
            else:
                gamma_p = 0.55
            beta1   = max(0.65, min(0.85, 0.85 - 0.05 * (data.fc_prime - 28.0) / 7.0))
            rho_p   = Aps / (bw * dp)
            fps     = res.fps
            T_ps    = Aps * fps
            a_trial = T_ps / (0.85 * data.fc_prime * bf)
            if data.t_flange_width > 0 and a_trial > hf:
                C_f   = 0.85 * data.fc_prime * (bf - bw) * hf
                T_web = T_ps - C_f
                a_web = T_web / (0.85 * data.fc_prime * bw)
                arm_C = (C_f * (hf / 2) + T_web * (hf + a_web / 2)) / T_ps
                is_T  = True
            else:
                arm_C = a_trial / 2
                is_T  = False
            Mn     = T_ps * (dp - arm_C) / 1e6   # kN·m
            phi_Mn = res.moment_capacity           # includes mild rebar if any

            f_r  = 0.62 * math.sqrt(data.fc_prime)
            Mcr  = res.cracking_moment

            # Shear intermediates
            dp_sh   = 0.8 * span.height
            fpc_val = Pe / A
            Vp_kN   = Pe * (4.0 * e / max(1.0, L_mm)) / 1000.0
            Vc      = ((0.17 * math.sqrt(data.fc_prime) + 0.3 * fpc_val)
                       * bw * dp_sh / 1000.0 + Vp_kN)
            phi_Vn  = res.phi_Vn

            # Torsion intermediates
            Acp    = A
            pcp    = 2.0 * (bf + span.height)
            sqfc   = math.sqrt(max(0.0001, data.fc_prime))
            pf_tor = math.sqrt(1.0 + fpc_val / max(0.0001, 0.33 * sqfc))
            Tcr    = (1.0 / 3.0) * sqfc * (Acp**2 / pcp) * pf_tor / 1e6   # kN·m
            phi_Tn = res.phi_Tn

            # Deflection intermediates
            delta_p_mm = (5.0 * Pe * e * L_mm**2) / (48.0 * Ec * I)
            delta_DL   = (5.0 * w_dl * L_mm**4) / (384.0 * Ec * I)
            delta_LL   = (5.0 * w_ll * L_mm**4) / (384.0 * Ec * I)
            allow_defl = L_mm / data.deflection_limit

            with doc.create(Subsection(f"Span {si + 1}  (L = {L_m:.2f} m)")):

                # ── Step 1: Section Properties ───────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 1 \textendash{} Section Properties}"
                    r"\par\smallskip"))
                if data.t_flange_width > 0 and data.t_flange_height > 0:
                    hw = data.height - data.t_flange_height
                    doc.append(_eq(
                        fr"A_g = b_w h_w + b_f h_f"
                        fr" = {bw:.0f}\times{hw:.0f} + {bf:.0f}\times{hf:.0f}"
                        fr" = {A:,.0f}\;\text{{mm}}^2"
                    ))
                    doc.append(_eq(
                        fr"y_t = {yt:.1f}\;\text{{mm}},\quad y_b = {yb:.1f}\;\text{{mm}}"
                        fr"\quad\text{{(T-section, shifted centroid)}}"
                    ))
                else:
                    doc.append(_eq(
                        fr"A_g = b_w \times h"
                        fr" = {bw:.0f} \times {data.height:.0f}"
                        fr" = {A:,.0f}\;\text{{mm}}^2"
                    ))
                    doc.append(_eq(
                        fr"I_g = \frac{{b_w h^3}}{{12}}"
                        fr" = \frac{{{bw:.0f} \times {data.height:.0f}^3}}{{12}}"
                        fr" = {I:.4g}\;\text{{mm}}^4"
                    ))
                    doc.append(_eq(
                        fr"y_t = y_b = \frac{{h}}{{2}}"
                        fr" = \frac{{{data.height:.0f}}}{{2}}"
                        fr" = {yt:.1f}\;\text{{mm}}"
                    ))
                doc.append(_eq(
                    fr"S_t = \frac{{I_g}}{{y_t}}"
                    fr" = \frac{{{I:.4g}}}{{{yt:.1f}}}"
                    fr" = {I/yt:.4g}\;\text{{mm}}^3"
                ))
                doc.append(_eq(
                    fr"S_b = \frac{{I_g}}{{y_b}}"
                    fr" = \frac{{{I:.4g}}}{{{yb:.1f}}}"
                    fr" = {I/yb:.4g}\;\text{{mm}}^3"
                ))

                # ── Step 2: Material Properties ──────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 2 \textendash{} Material Properties}"
                    r"\par\smallskip"))
                doc.append(_eq(
                    fr"E_c = 4700\sqrt{{f'_c}}"
                    fr" = 4700\sqrt{{{data.fc_prime:.0f}}}"
                    fr" = {Ec:,.1f}\;\text{{MPa}}"
                    r"\quad\text{(ACI 19.2.2.1)}"
                ))
                doc.append(_eq(
                    r"E_s = 200\,000\;\text{MPa}"
                    r"\quad\text{(prestressing steel)}"
                ))
                doc.append(_eq(
                    fr"n = \frac{{E_s}}{{E_c}}"
                    fr" = \frac{{200\,000}}{{{Ec:,.1f}}}"
                    fr" = {n:.3f}"
                ))

                # ── Step 3: Tendon Properties ────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 3 \textendash{} Tendon Properties}"
                    r"\par\smallskip"))
                mat_label = data.material.replace("_", " ").upper()
                doc.append(_eq(
                    fr"A_{{ps,1}} = {Aps_1:.1f}\;\text{{mm}}^2"
                    fr"\quad\text{{({mat_label}, {data.strand_dia}\,mm)}}"
                ))
                doc.append(_eq(
                    fr"A_{{ps}} = n_{{tendons}} \times A_{{ps,1}}"
                    fr" = {data.num_tendons} \times {Aps_1:.1f}"
                    fr" = {Aps:.1f}\;\text{{mm}}^2"
                ))
                doc.append(_eq(
                    fr"f_{{pu}} = {fpu:.0f}\;\text{{MPa}},\quad "
                    fr"f_{{py}} = {fpy:.0f}\;\text{{MPa}},\quad "
                    fr"f_{{py}}/f_{{pu}} = {fpy_fpu:.3f}"
                ))
                doc.append(_eq(
                    fr"d_p = y_t + e = {yt:.1f} + {e:.1f} = {dp:.1f}\;\text{{mm}}"
                ))
                doc.append(_eq(
                    fr"\rho_p = \frac{{A_{{ps}}}}{{b_w d_p}}"
                    fr" = \frac{{{Aps:.1f}}}{{{bw:.0f} \times {dp:.1f}}}"
                    fr" = {rho_p:.6f}"
                ))

                # ── Step 4: ACI Tendon Stress Limits ─────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 4 \textendash{} ACI Tendon Stress Limits"
                    r" (Table 20.3.2.5.1)}\par\smallskip"))
                fpj_lim = min(0.94 * fpy, 0.80 * fpu)
                if is_pt:
                    fpi_lim = min(0.82 * fpy, 0.70 * fpu)
                    fpi_coeff2_label = r"0.70\,f_{pu}"
                    fpi_val2 = 0.70 * fpu
                else:
                    fpi_lim = min(0.82 * fpy, 0.74 * fpu)
                    fpi_coeff2_label = r"0.74\,f_{pu}"
                    fpi_val2 = 0.74 * fpu
                doc.append(_eq(
                    fr"f_{{pj,\max}} = \min(0.94\,f_{{py}},\;0.80\,f_{{pu}})"
                    fr" = \min({0.94*fpy:.1f},\;{0.80*fpu:.1f})"
                    fr" = {fpj_lim:.1f}\;\text{{MPa}}"
                ))
                doc.append(_eq(
                    fr"f_{{pi,\max}} = \min(0.82\,f_{{py}},\;{fpi_coeff2_label})"
                    fr" = \min({0.82*fpy:.1f},\;{fpi_val2:.1f})"
                    fr" = {fpi_lim:.1f}\;\text{{MPa}}"
                ))

                # ── Step 5: Initial Prestress ─────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 5 \textendash{} Initial Prestress"
                    r" at Transfer}\par\smallskip"))
                if data.jacking_force > 0:
                    fpj_actual = (data.jacking_force * 1000.0) / Aps_1
                    doc.append(_eq(
                        fr"f_{{pi}} = \min\!\left(f_{{pi,\max}},\;"
                        fr"\frac{{F_{{jack}}}}{{A_{{ps,1}}}}\right)"
                        fr" = \min\!\left({fpi_lim:.1f},\;"
                        fr"\frac{{{data.jacking_force:.1f} \times 10^3}}{{{Aps_1:.1f}}}\right)"
                        fr" = {fpi:.1f}\;\text{{MPa}}"
                    ))
                else:
                    doc.append(_eq(
                        fr"f_{{pi}} = f_{{pi,\max}} = {fpi:.1f}\;\text{{MPa}}"
                        r"\quad\text{(auto: no jacking force specified)}"
                    ))
                doc.append(_eq(
                    fr"P_i = A_{{ps}} \cdot f_{{pi}}"
                    fr" = {Aps:.1f} \times {fpi:.1f}"
                    fr" = {Pi/1000:.2f}\;\text{{kN}}"
                ))

                # ── Step 6: Prestress Losses ──────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 6 \textendash{} Prestress Losses}"
                    r"\par\smallskip"))

                doc.append(NoEscape(
                    r"\noindent\textit{6a.\ Self-weight moment at midspan"
                    r" (for $f_{cgp}$, ACI R20.3.5.4):}\par"))
                doc.append(_eq(
                    fr"M_g = \frac{{w_{{DL}}\,L^2}}{{8}}"
                    fr" = \frac{{{w_dl:.3f} \times {L_m:.3f}^2}}{{8}}"
                    fr" = {Mg_nmm/1e6:.3f}\;\text{{kN\,m}}"
                ))

                doc.append(NoEscape(
                    r"\noindent\textit{6b.\ Concrete stress at centroid of"
                    r" prestress (compressive positive):}\par"))
                doc.append(NoEscape(
                    r"\[f_{cgp} = \frac{P_i}{A_g}"
                    r" + \frac{P_i\,e^2}{I_g}"
                    r" - \frac{M_g\,e}{I_g}\]"
                ))
                doc.append(_eq(
                    fr"f_{{cgp}}"
                    fr" = \frac{{{Pi/1000:.2f} \times 10^3}}{{{A:.0f}}}"
                    fr" + \frac{{{Pi/1000:.2f} \times 10^3 \times {e:.1f}^2}}{{{I:.4g}}}"
                    fr" - \frac{{{Mg_nmm/1e6:.3f} \times 10^6 \times {e:.1f}}}{{{I:.4g}}}"
                    fr" = {fc_cir:.4f}\;\text{{MPa}}"
                ))

                es_note = r"$\times\,0.5$ for post-tensioned" if is_pt else r"pretensioned"
                doc.append(NoEscape(
                    fr"\noindent\textit{{6c.\ Elastic shortening ({es_note}):}}\par"))
                es_coeff_str  = r"0.5\,n" if is_pt else r"n"
                es_coeff_val  = 0.5 * n if is_pt else n
                doc.append(_eq(
                    fr"\Delta f_{{p,es}} = {es_coeff_str}\,f_{{cgp}}"
                    fr" = {es_coeff_val:.4f} \times {fc_cir:.4f}"
                    fr" = {delta_es:.3f}\;\text{{MPa}}"
                ))

                doc.append(NoEscape(
                    r"\noindent\textit{6d.\ Time-dependent losses"
                    r" (creep + shrinkage + relaxation):}\par"))
                if data.time_loss_mpa > 0:
                    doc.append(_eq(
                        fr"\Delta f_{{p,\mathrm{{time}}}} = {delta_td:.1f}\;\text{{MPa}}"
                        r"\quad\text{(user-specified)}"
                    ))
                else:
                    lump_src = "205" if is_pt else "240"
                    doc.append(_eq(
                        fr"\Delta f_{{p,\mathrm{{time}}}} \approx {lump_src}\;\text{{MPa}}"
                        r"\quad\text{(ACI/PCI lump-sum approximation)}"
                    ))

                if is_pt:
                    doc.append(NoEscape(
                        r"\noindent\textit{6e.\ Anchorage slip loss:}\par"))
                    doc.append(_eq(
                        fr"\Delta f_{{p,\mathrm{{anc}}}}"
                        fr" = \frac{{\Delta_{{anc}}}}{{L}}\,E_s"
                        fr" = \frac{{{data.slip:.1f}}}{{{L_mm:.0f}}} \times 200\,000"
                        fr" = {delta_anc:.3f}\;\text{{MPa}}"
                    ))
                    doc.append(NoEscape(
                        r"\noindent\textit{6f.\ Friction loss at midspan:}\par"))
                    doc.append(NoEscape(
                        r"\[\Delta f_{p,fr} = f_{pi}\!\left(\mu\,\alpha"
                        r" + \frac{k}{1000}\cdot\frac{L}{2}\right)\]"
                    ))
                    doc.append(_eq(
                        fr"\alpha = \frac{{8\,e}}{{L}}"
                        fr" = \frac{{8 \times {e:.1f}}}{{{L_mm:.0f}}}"
                        fr" = {alpha_rad:.5f}\;\text{{rad}}"
                    ))
                    doc.append(_eq(
                        fr"\Delta f_{{p,fr}}"
                        fr" = {fpi:.1f}\!\left("
                        fr"{data.friction_mu} \times {alpha_rad:.5f}"
                        fr" + \frac{{{data.friction_k}}}{{1000}}"
                        fr" \times \frac{{{L_mm:.0f}}}{{2}}\right)"
                        fr" = {delta_fr:.3f}\;\text{{MPa}}"
                    ))

                doc.append(NoEscape(
                    r"\noindent\textit{6g.\ Total loss and effective prestress:}\par"))
                if is_pt:
                    doc.append(_eq(
                        fr"\Delta f_p"
                        fr" = \Delta f_{{p,es}} + \Delta f_{{p,\mathrm{{time}}}}"
                        fr" + \Delta f_{{p,\mathrm{{anc}}}} + \Delta f_{{p,fr}}"
                        fr" = {delta_es:.3f} + {delta_td:.1f}"
                        fr" + {delta_anc:.3f} + {delta_fr:.3f}"
                        fr" = {delta_total:.3f}\;\text{{MPa}}"
                    ))
                else:
                    doc.append(_eq(
                        fr"\Delta f_p"
                        fr" = \Delta f_{{p,es}} + \Delta f_{{p,\mathrm{{time}}}}"
                        fr" = {delta_es:.3f} + {delta_td:.1f}"
                        fr" = {delta_total:.3f}\;\text{{MPa}}"
                    ))
                doc.append(_eq(
                    fr"f_{{pe}} = f_{{pi}} - \Delta f_p"
                    fr" = {fpi:.1f} - {delta_total:.3f}"
                    fr" = {fpe:.1f}\;\text{{MPa}}"
                ))
                loss_pct = (delta_total / max(0.001, fpi)) * 100.0
                doc.append(_eq(
                    fr"\text{{Loss\%}}"
                    fr" = \frac{{\Delta f_p}}{{f_{{pi}}}} \times 100\%"
                    fr" = \frac{{{delta_total:.3f}}}{{{fpi:.1f}}} \times 100\%"
                    fr" = {loss_pct:.1f}\%"
                ))

                # ── Step 7: Effective Prestress Force ─────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 7 \textendash{} Effective"
                    r" Prestress Force}\par\smallskip"))
                doc.append(_eq(
                    fr"P_e = A_{{ps}} \cdot f_{{pe}}"
                    fr" = {Aps:.1f} \times {fpe:.1f}"
                    fr" = {Pe/1000:.2f}\;\text{{kN}}"
                ))

                # ── Step 8: Applied Loads ─────────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 8 \textendash{} Applied Loads}"
                    r"\par\smallskip"))
                with doc.create(Tabular("p{4cm}p{3cm}p{3cm}p{3cm}")) as tab:
                    tab.add_hline()
                    tab.add_row((bold("Load"),
                                 bold("DL (kN/m)"), bold("SDL (kN/m)"), bold("LL (kN/m)")))
                    tab.add_hline()
                    tab.add_row(("Unfactored service",
                                 f"{w_dl:.3f}", f"{w_sdl:.3f}", f"{w_ll:.3f}"))
                    tab.add_hline()
                doc.append(_eq(
                    fr"w_{{total}} = w_{{DL}} + w_{{SDL}} + w_{{LL}}"
                    fr" = {w_dl:.3f} + {w_sdl:.3f} + {w_ll:.3f}"
                    fr" = {w_tot:.3f}\;\text{{kN/m}}"
                ))
                doc.append(_eq(
                    fr"w_u = 1.2\,w_{{DL}} + 1.2\,w_{{SDL}} + 1.6\,w_{{LL}}"
                    fr" = 1.2({w_dl:.3f}) + 1.2({w_sdl:.3f}) + 1.6({w_ll:.3f})"
                    fr" = {wu:.3f}\;\text{{kN/m}}"
                ))

                # ── Step 9: Factored Demands ──────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 9 \textendash{} Factored Demands"
                    r" (Stiffness Analysis, ACI 5.3.1)}\par\smallskip"))
                with doc.create(Tabular("p{3.5cm}p{3cm}p{3cm}p{3cm}")) as tab:
                    tab.add_hline()
                    tab.add_row((bold("Demand"),
                                 bold("Left"), bold("Midspan"), bold("Right")))
                    tab.add_hline()
                    tab.add_row((
                        NoEscape(r"$M_u$ (kN\,m)"),
                        f"{res.Mu_left:.2f}", f"{res.Mu_mid:.2f}", f"{res.Mu_right:.2f}",
                    ))
                    tab.add_row((
                        NoEscape(r"$V_u$ (kN)"),
                        f"{res.Vu_left:.2f}", f"{res.Vu_mid:.2f}", f"{res.Vu_right:.2f}",
                    ))
                    tab.add_hline()

                # ── Step 10: Stresses at Transfer ────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 10 \textendash{} Concrete Stresses"
                    r" at Transfer (ACI \S24.5.3)}\par\smallskip"))
                doc.append(NoEscape(
                    r"\noindent Sign convention: compression (--), tension (+).\par"))
                doc.append(NoEscape(
                    r"\[f_{top,i} = -\frac{P_i}{A_g}"
                    r" + \frac{P_i\,e\,y_t}{I_g}"
                    r" - \frac{M_D\,y_t}{I_g}\]"
                ))
                doc.append(NoEscape(
                    r"\[f_{bot,i} = -\frac{P_i}{A_g}"
                    r" - \frac{P_i\,e\,y_b}{I_g}"
                    r" + \frac{M_D\,y_b}{I_g}\]"
                ))
                doc.append(NoEscape(r"\noindent\textit{Substituting at midspan:}\par"))
                doc.append(_eq(
                    fr"M_D = {Md_mid:.3f}\;\text{{kN\,m}}"
                    r"\quad\text{(dead-load moment from stiffness analysis)}"
                ))
                doc.append(_eq(
                    fr"f_{{top,i}}"
                    fr" = -\frac{{{Pi/1000:.2f}\times10^3}}{{{A:.0f}}}"
                    fr" + \frac{{{Pi/1000:.2f}\times10^3 \times {e:.1f} \times {yt:.1f}}}{{{I:.4g}}}"
                    fr" - \frac{{{Md_mid:.3f}\times10^6 \times {yt:.1f}}}{{{I:.4g}}}"
                    fr" = {res.mid_st_i:.3f}\;\text{{MPa}}"
                ))
                doc.append(_eq(
                    fr"f_{{bot,i}}"
                    fr" = -\frac{{{Pi/1000:.2f}\times10^3}}{{{A:.0f}}}"
                    fr" - \frac{{{Pi/1000:.2f}\times10^3 \times {e:.1f} \times {yb:.1f}}}{{{I:.4g}}}"
                    fr" + \frac{{{Md_mid:.3f}\times10^6 \times {yb:.1f}}}{{{I:.4g}}}"
                    fr" = {res.mid_sb_i:.3f}\;\text{{MPa}}"
                ))
                f_ti_other = 0.25 * math.sqrt(fci)
                f_ci_other = 0.60 * fci
                top_ok_i   = res.mid_st_i <= f_ti_other
                bot_ok_i   = abs(min(res.mid_sb_i, 0)) <= f_ci_other
                doc.append(NoEscape(r"\noindent\textit{ACI limits (other sections):}\par"))
                doc.append(NoEscape(
                    fr"\[f_{{top,i}} = {res.mid_st_i:.3f}\;\text{{MPa}} "
                    + (r"\leq" if top_ok_i else r">")
                    + fr" +{f_ti_other:.3f}\;\text{{MPa}}\;(\text{{tension limit}})"
                    + (r"\quad\checkmark" if top_ok_i
                       else r"\quad\textcolor{failred}{\textbf{EXCEEDS}}")
                    + r"\]"
                ))
                doc.append(NoEscape(
                    fr"\[|f_{{bot,i}}| = {abs(res.mid_sb_i):.3f}\;\text{{MPa}} "
                    + (r"\leq" if bot_ok_i else r">")
                    + fr" {f_ci_other:.3f}\;\text{{MPa}}\;(\text{{compression limit}})"
                    + (r"\quad\checkmark" if bot_ok_i
                       else r"\quad\textcolor{failred}{\textbf{EXCEEDS}}")
                    + r"\]"
                ))

                # ── Step 11: Stresses at Service ──────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 11 \textendash{} Concrete Stresses"
                    r" at Service (ACI \S24.5.4)}\par\smallskip"))
                doc.append(NoEscape(
                    r"\[f_{top,s} = -\frac{P_e}{A_g}"
                    r" + \frac{P_e\,e\,y_t}{I_g}"
                    r" - \frac{M_s\,y_t}{I_g}\]"
                ))
                doc.append(NoEscape(
                    r"\[f_{bot,s} = -\frac{P_e}{A_g}"
                    r" - \frac{P_e\,e\,y_b}{I_g}"
                    r" + \frac{M_s\,y_b}{I_g}\]"
                ))
                doc.append(NoEscape(r"\noindent\textit{Substituting at midspan:}\par"))
                doc.append(_eq(
                    fr"M_s = {Ms_mid:.3f}\;\text{{kN\,m}}"
                    r"\quad\text{(total service moment from stiffness analysis)}"
                ))
                doc.append(_eq(
                    fr"f_{{top,s}}"
                    fr" = -\frac{{{Pe/1000:.2f}\times10^3}}{{{A:.0f}}}"
                    fr" + \frac{{{Pe/1000:.2f}\times10^3 \times {e:.1f} \times {yt:.1f}}}{{{I:.4g}}}"
                    fr" - \frac{{{Ms_mid:.3f}\times10^6 \times {yt:.1f}}}{{{I:.4g}}}"
                    fr" = {res.mid_st_s:.3f}\;\text{{MPa}}"
                ))
                doc.append(_eq(
                    fr"f_{{bot,s}}"
                    fr" = -\frac{{{Pe/1000:.2f}\times10^3}}{{{A:.0f}}}"
                    fr" - \frac{{{Pe/1000:.2f}\times10^3 \times {e:.1f} \times {yb:.1f}}}{{{I:.4g}}}"
                    fr" + \frac{{{Ms_mid:.3f}\times10^6 \times {yb:.1f}}}{{{I:.4g}}}"
                    fr" = {res.mid_sb_s:.3f}\;\text{{MPa}}"
                ))
                f_t_u   = 0.62 * math.sqrt(fc)
                f_t_t   = 1.00 * math.sqrt(fc)
                f_c_tot = 0.60 * fc
                top_ok_s = abs(min(res.mid_st_s, 0)) <= f_c_tot
                doc.append(NoEscape(r"\noindent\textit{ACI limits (total load):}\par"))
                doc.append(NoEscape(
                    fr"\[|f_{{top,s}}| = {abs(res.mid_st_s):.3f}\;\text{{MPa}} "
                    + (r"\leq" if top_ok_s else r">")
                    + fr" {f_c_tot:.3f}\;\text{{MPa}}\;(\text{{compression limit}})"
                    + (r"\quad\checkmark" if top_ok_s
                       else r"\quad\textcolor{failred}{\textbf{EXCEEDS}}")
                    + r"\]"
                ))
                bot_svc = res.mid_sb_s
                if bot_svc > f_t_t:
                    sect_class = "C (cracked)"
                elif bot_svc > f_t_u:
                    sect_class = "T (transition)"
                else:
                    sect_class = "U (uncracked)"
                doc.append(_eq(
                    fr"f_{{bot,s}} = {bot_svc:.3f}\;\text{{MPa}}"
                    + (fr" \leq +{f_t_u:.3f}" if bot_svc <= f_t_u
                       else fr" > +{f_t_u:.3f}")
                    + fr"\;\text{{MPa (Class\,U limit)}}"
                    + fr" \implies \text{{Class {sect_class}}}"
                ))
                doc.append(NoEscape(
                    r"\smallskip\noindent\textit{Stresses at all three sections:}\par"))
                with doc.create(Tabular("p{2cm}p{5.5cm}p{5.5cm}")) as tab:
                    tab.add_hline()
                    tab.add_row((bold("Stage"),
                                 bold("Top Fiber (L/M/R) [MPa]"),
                                 bold("Bot Fiber (L/M/R) [MPa]")))
                    tab.add_hline()
                    tab.add_row((
                        "Initial",
                        f"{res.left_st_i:.3f} / {res.mid_st_i:.3f} / {res.right_st_i:.3f}",
                        f"{res.left_sb_i:.3f} / {res.mid_sb_i:.3f} / {res.right_sb_i:.3f}",
                    ))
                    tab.add_row((
                        "Service",
                        f"{res.left_st_s:.3f} / {res.mid_st_s:.3f} / {res.right_st_s:.3f}",
                        f"{res.left_sb_s:.3f} / {res.mid_sb_s:.3f} / {res.right_sb_s:.3f}",
                    ))
                    tab.add_hline()

                # ── Step 12: Flexural Strength ────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 12 \textendash{} Flexural Strength"
                    r" (ACI \S20.3.2 \& \S22.3)}\par\smallskip"))
                doc.append(_eq(
                    fr"\beta_1 = 0.85 - 0.05 \cdot \frac{{f'_c - 28}}{{7}}"
                    fr" = 0.85 - 0.05 \times \frac{{{data.fc_prime:.0f} - 28}}{{7}}"
                    fr" = {beta1:.4f}"
                    r"\quad(0.65 \leq \beta_1 \leq 0.85)"
                ))
                if method_en in (PrestressingMethod.PRETENSIONED,
                                 PrestressingMethod.POSTTENSIONED_BONDED):
                    ratio_note = (r"\geq 0.90" if fpy_fpu >= 0.90 else
                                  (r"\geq 0.80" if fpy_fpu >= 0.80 else r"< 0.80"))
                    doc.append(_eq(
                        fr"\gamma_p = {gamma_p}"
                        fr"\quad(f_{{py}}/f_{{pu}} = {fpy_fpu:.3f}\;{ratio_note})"
                    ))
                    doc.append(NoEscape(
                        r"\[f_{ps} = f_{pu}\!\left[1 - \frac{\gamma_p}{\beta_1}"
                        r"\left(\rho_p \frac{f_{pu}}{f'_c}\right)\right]"
                        r"\quad\text{(ACI Eq. 20.3.2.3.1)}\]"
                    ))
                    doc.append(_eq(
                        fr"f_{{ps}} = {fpu:.0f}\!\left[1 - "
                        fr"\frac{{{gamma_p}}}{{{beta1:.4f}}}"
                        fr" \times {rho_p:.6f}"
                        fr" \times \frac{{{fpu:.0f}}}{{{data.fc_prime:.0f}}}\right]"
                        fr" = {fps:.1f}\;\text{{MPa}}"
                    ))
                elif method_en == PrestressingMethod.POSTTENSIONED_UNBONDED:
                    L_dp = L_mm / dp
                    coeff = 100 if L_dp <= 35 else 300
                    fps_cap = fpe + 420 if L_dp <= 35 else fpe + 210
                    fps_raw = fpe + 70 + data.fc_prime / (coeff * rho_p)
                    aci_ref = r"L/d_p \leq 35" if L_dp <= 35 else r"L/d_p > 35"
                    doc.append(NoEscape(
                        fr"\[f_{{ps}} = f_{{pe}} + 70 + \frac{{f'_c}}{{{coeff}\,\rho_p}}"
                        fr"\quad({aci_ref})\]"
                    ))
                    doc.append(_eq(
                        fr"f_{{ps}} = {fpe:.1f} + 70"
                        fr" + \frac{{{data.fc_prime:.0f}}}{{{coeff} \times {rho_p:.6f}}}"
                        fr" = {fps_raw:.1f} \;\to\; \min({fps_cap:.1f},\;{fpy:.0f})"
                        fr" = {fps:.1f}\;\text{{MPa}}"
                    ))

                doc.append(_eq(
                    fr"T_{{ps}} = A_{{ps}}\,f_{{ps}}"
                    fr" = {Aps:.1f} \times {fps:.1f}"
                    fr" = {T_ps/1000:.2f}\;\text{{kN}}"
                ))
                if not is_T:
                    doc.append(_eq(
                        fr"a = \frac{{T_{{ps}}}}{{0.85\,f'_c\,b_w}}"
                        fr" = \frac{{{T_ps/1000:.2f} \times 10^3}}"
                        fr"{{0.85 \times {data.fc_prime:.0f} \times {bw:.0f}}}"
                        fr" = {a_trial:.2f}\;\text{{mm}}"
                    ))
                    doc.append(_eq(
                        fr"M_n = T_{{ps}}\!\left(d_p - \frac{{a}}{{2}}\right)"
                        fr" = {T_ps/1000:.2f} \times 10^3"
                        fr"\!\left({dp:.1f} - \frac{{{a_trial:.2f}}}{{2}}\right)"
                        fr" \times 10^{{-6}}"
                        fr" = {Mn:.2f}\;\text{{kN\,m}}"
                    ))
                else:
                    doc.append(_eq(
                        fr"a_{{trial}} = {a_trial:.2f}\;\text{{mm}}"
                        fr" > h_f = {hf:.0f}\;\text{{mm}}"
                        r" \implies \text{T-section: block extends into web}"
                    ))
                    doc.append(_eq(
                        fr"M_n = {Mn:.2f}\;\text{{kN\,m}}"
                        r"\quad\text{(T-section composite moment arm)}"
                    ))
                doc.append(_eq(
                    fr"\phi M_n = 0.90 \times M_n"
                    fr" = 0.90 \times {Mn:.2f}"
                    fr" = {phi_Mn:.2f}\;\text{{kN\,m}}"
                ))

                # ── Step 13: Cracking Moment ──────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 13 \textendash{} Cracking Moment"
                    r" (ACI \S24.2.3.5 \& \S9.6.2.1)}\par\smallskip"))
                doc.append(_eq(
                    fr"f_r = 0.62\sqrt{{f'_c}}"
                    fr" = 0.62\sqrt{{{fc:.0f}}}"
                    fr" = {f_r:.4f}\;\text{{MPa}}"
                ))
                doc.append(NoEscape(
                    r"\[M_{cr} = \frac{I_g}{y_b}\!\left("
                    r"f_r + \frac{P_e}{A_g} + \frac{P_e\,e\,y_b}{I_g}"
                    r"\right) \times 10^{-6}\;\text{kN\,m}\]"
                ))
                doc.append(_eq(
                    fr"M_{{cr}}"
                    fr" = \frac{{{I:.4g}}}{{{yb:.1f}}}"
                    fr"\!\left({f_r:.4f}"
                    fr" + \frac{{{Pe/1000:.2f}\times10^3}}{{{A:.0f}}}"
                    fr" + \frac{{{Pe/1000:.2f}\times10^3\times{e:.1f}\times{yb:.1f}}}{{{I:.4g}}}"
                    fr"\right)\times10^{{-6}}"
                    fr" = {Mcr:.2f}\;\text{{kN\,m}}"
                ))
                mcr_12 = 1.2 * Mcr
                mcr_ok = phi_Mn >= mcr_12
                doc.append(NoEscape(
                    fr"\[\phi M_n = {phi_Mn:.2f}\;\text{{kN\,m}} "
                    + (r"\geq" if mcr_ok else r"<")
                    + fr" 1.2\,M_{{cr}} = 1.2 \times {Mcr:.2f} = {mcr_12:.2f}\;\text{{kN\,m}}"
                    + (r"\quad\checkmark\;\text{(ACI 9.6.2.1 satisfied)}"
                       if mcr_ok
                       else r"\quad\textcolor{failred}{\textbf{WARNING (ACI 9.6.2.1)}}")
                    + r"\]"
                ))

                # ── Step 14: Shear Capacity ───────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 14 \textendash{} Shear Capacity"
                    r" (ACI \S22.5.6)}\par\smallskip"))
                doc.append(_eq(
                    fr"d_{{shear}} = 0.8\,h"
                    fr" = 0.8 \times {span.height:.0f}"
                    fr" = {dp_sh:.0f}\;\text{{mm}}"
                ))
                doc.append(_eq(
                    fr"f_{{pc}} = \frac{{P_e}}{{A_g}}"
                    fr" = \frac{{{Pe/1000:.2f}\times10^3}}{{{A:.0f}}}"
                    fr" = {fpc_val:.4f}\;\text{{MPa}}"
                ))
                doc.append(_eq(
                    fr"V_p = P_e \cdot \frac{{4\,e}}{{L}}"
                    fr" = {Pe/1000:.2f}\times10^3"
                    fr" \times \frac{{4 \times {e:.1f}}}{{{L_mm:.0f}}}"
                    fr" \times 10^{{-3}}"
                    fr" = {Vp_kN:.3f}\;\text{{kN}}"
                    r"\quad\text{(vertical component of }P_e\text{, parabolic)}"
                ))
                doc.append(NoEscape(
                    r"\[V_c = \!\left(0.17\lambda\sqrt{f'_c}"
                    r" + 0.3\,f_{pc}\right)b_w\,d_{shear}"
                    r" + V_p\quad(\lambda = 1.0)\]"
                ))
                doc.append(_eq(
                    fr"V_c = \!\left(0.17\sqrt{{{data.fc_prime:.0f}}}"
                    fr" + 0.3 \times {fpc_val:.4f}\right)"
                    fr" \times {bw:.0f} \times {dp_sh:.0f} \times 10^{{-3}}"
                    fr" + {Vp_kN:.3f}"
                    fr" = {Vc:.3f}\;\text{{kN}}"
                ))
                doc.append(_eq(
                    fr"\phi V_n = 0.75 \times V_c"
                    fr" = 0.75 \times {Vc:.3f}"
                    fr" = {phi_Vn:.3f}\;\text{{kN}}"
                ))

                # ── Step 15: Torsional Cracking Capacity ──────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 15 \textendash{} Torsional Cracking"
                    r" Capacity (ACI \S22.7.4.1)}\par\smallskip"))
                doc.append(_eq(
                    fr"A_{{cp}} = {Acp:,.0f}\;\text{{mm}}^2,\quad "
                    fr"p_{{cp}} = 2(b_f + h)"
                    fr" = 2({bf:.0f} + {span.height:.0f})"
                    fr" = {pcp:.0f}\;\text{{mm}}"
                ))
                doc.append(NoEscape(
                    r"\[T_{cr} = \frac{\lambda\sqrt{f'_c}}{3}"
                    r"\cdot\frac{A_{cp}^2}{p_{cp}}"
                    r"\cdot\sqrt{1 + \frac{f_{pc}}{0.33\sqrt{f'_c}}}"
                    r"\quad[\text{N\,mm}]\]"
                ))
                doc.append(_eq(
                    fr"T_{{cr}}"
                    fr" = \frac{{\sqrt{{{data.fc_prime:.0f}}}}}{{3}}"
                    fr" \times \frac{{{Acp:,.0f}^2}}{{{pcp:.0f}}}"
                    fr" \times \sqrt{{1 + \frac{{{fpc_val:.4f}}}{{0.33\sqrt{{{data.fc_prime:.0f}}}}}}}"
                    fr" \times 10^{{-6}}"
                    fr" = {Tcr:.4f}\;\text{{kN\,m}}"
                ))
                doc.append(_eq(
                    fr"\phi T_n = 0.75 \times T_{{cr}}"
                    fr" = 0.75 \times {Tcr:.4f}"
                    fr" = {phi_Tn:.4f}\;\text{{kN\,m}}"
                ))

                # ── Step 16: Deflections ──────────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 16 \textendash{} Deflections"
                    r" (ACI \S24.2)}\par\smallskip"))
                doc.append(NoEscape(
                    r"\noindent Sign convention: downward (+), upward camber (--).\par"))
                doc.append(NoEscape(
                    r"\[\delta_p = \frac{5\,P_e\,e\,L^2}{48\,E_c\,I_g}"
                    r"\quad\text{(parabolic tendon camber, upward)}\]"
                ))
                doc.append(_eq(
                    fr"\delta_p"
                    fr" = \frac{{5 \times {Pe/1000:.2f}\times10^3"
                    fr" \times {e:.1f} \times {L_mm:.0f}^2}}"
                    fr"{{48 \times {Ec:,.1f} \times {I:.4g}}}"
                    fr" = {delta_p_mm:.3f}\;\text{{mm (upward)}}"
                ))
                doc.append(NoEscape(
                    r"\[\delta_{DL} = \frac{5\,w_{DL}\,L^4}{384\,E_c\,I_g}\]"
                ))
                doc.append(_eq(
                    fr"\delta_{{DL}}"
                    fr" = \frac{{5 \times {w_dl:.4f} \times {L_mm:.0f}^4}}"
                    fr"{{384 \times {Ec:,.1f} \times {I:.4g}}}"
                    fr" = {delta_DL:.3f}\;\text{{mm}}"
                ))
                doc.append(NoEscape(
                    r"\[\delta_{LL} = \frac{5\,w_{LL}\,L^4}{384\,E_c\,I_g}\]"
                ))
                doc.append(_eq(
                    fr"\delta_{{LL}}"
                    fr" = \frac{{5 \times {w_ll:.4f} \times {L_mm:.0f}^4}}"
                    fr"{{384 \times {Ec:,.1f} \times {I:.4g}}}"
                    fr" = {delta_LL:.3f}\;\text{{mm}}"
                ))
                doc.append(_eq(
                    fr"\delta_i = \delta_{{DL}} - \delta_p"
                    fr" = {delta_DL:.3f} - {delta_p_mm:.3f}"
                    fr" = {res.deflection_initial:.3f}\;\text{{mm}}"
                ))
                doc.append(_eq(
                    fr"\delta_f = \lambda_\Delta\,\delta_i + \delta_{{LL}}"
                    fr" = {data.long_term_multiplier} \times {res.deflection_initial:.3f}"
                    fr" + {delta_LL:.3f}"
                    fr" = {res.deflection_final:.3f}\;\text{{mm}}"
                    r"\quad\text{(ACI Table 24.2.4.1.3)}"
                ))
                doc.append(_eq(
                    fr"\delta_{{allow}} = \frac{{L}}{{{data.deflection_limit:.0f}}}"
                    fr" = \frac{{{L_mm:.0f}}}{{{data.deflection_limit:.0f}}}"
                    fr" = {allow_defl:.1f}\;\text{{mm}}"
                    r"\quad\text{(ACI Table 24.2.2)}"
                ))
                defl_ok = abs(res.deflection_final) <= allow_defl
                doc.append(NoEscape(
                    fr"\[|\delta_f| = {abs(res.deflection_final):.3f}\;\text{{mm}} "
                    + (r"\leq" if defl_ok else r">")
                    + fr" \delta_{{allow}} = {allow_defl:.1f}\;\text{{mm}}"
                    + (r"\quad\checkmark" if defl_ok
                       else r"\quad\textcolor{failred}{\textbf{EXCEEDS}}")
                    + r"\]"
                ))

                # ── Step 17: Design Summary ───────────────────────────────────
                doc.append(NoEscape(
                    r"\medskip\noindent\textbf{Step 17 \textendash{} Design Summary"
                    r" (DCR Table)}\par\smallskip"))

                def _dcr_cell(v):
                    col = "passgreen" if v <= 1.0 else "failred"
                    lbl = "PASS" if v <= 1.0 else "FAIL"
                    return NoEscape(fr"\textcolor{{{col}}}{{\textbf{{{lbl}}}}}")

                max_flex  = max(res.dcr_flexure_left,
                                res.dcr_flexure_mid, res.dcr_flexure_right)
                max_shear = max(res.dcr_shear_left,
                                res.dcr_shear_mid,  res.dcr_shear_right)
                max_tors  = max(res.dcr_torsion_left,
                                res.dcr_torsion_mid, res.dcr_torsion_right)

                with doc.create(Tabular("p{3.5cm}p{3cm}p{4.5cm}p{1.5cm}")) as tab:
                    tab.add_hline()
                    tab.add_row((bold("Check"), bold("Capacity"),
                                 bold("DCR  (L / M / R)"), bold("Status")))
                    tab.add_hline()
                    tab.add_row((
                        NoEscape(r"Flexure $\phi M_n$"),
                        NoEscape(fr"{phi_Mn:.2f}\,kN\,m"),
                        (f"{res.dcr_flexure_left:.2f} / {res.dcr_flexure_mid:.2f}"
                         f" / {res.dcr_flexure_right:.2f}"),
                        _dcr_cell(max_flex),
                    ))
                    tab.add_row((
                        NoEscape(r"Shear $\phi V_c$"),
                        NoEscape(fr"{phi_Vn:.2f}\,kN"),
                        (f"{res.dcr_shear_left:.2f} / {res.dcr_shear_mid:.2f}"
                         f" / {res.dcr_shear_right:.2f}"),
                        _dcr_cell(max_shear),
                    ))
                    tab.add_row((
                        NoEscape(r"Torsion $\phi T_n$"),
                        NoEscape(fr"{phi_Tn:.4f}\,kN\,m"),
                        (f"{res.dcr_torsion_left:.2f} / {res.dcr_torsion_mid:.2f}"
                         f" / {res.dcr_torsion_right:.2f}"),
                        _dcr_cell(max_tors),
                    ))
                    tab.add_row((
                        "Deflection (mid.)",
                        NoEscape(fr"{allow_defl:.1f}\,mm"),
                        f"-- / {res.dcr_deflect_mid:.2f} / --",
                        _dcr_cell(res.dcr_deflect_mid),
                    ))
                    tab.add_hline()
                    ur_col = "passgreen" if res.utilization_ratio <= 1.0 else "failred"
                    tab.add_row((
                        bold("Overall DCR"), "", "",
                        NoEscape(
                            fr"\textcolor{{{ur_col}}}{{\textbf{{{res.utilization_ratio:.2f}}}}}"
                        ),
                    ))
                    tab.add_hline()

                # ── Design Notes ──────────────────────────────────────────────
                if res.design_notes:
                    doc.append(NoEscape(
                        r"\medskip\noindent\textbf{Design Notes:}\par\smallskip"))
                    with doc.create(Itemize()) as it:
                        for note in res.design_notes:
                            it.add_item(_sanitize_for_latex(note))

    # ── Generate PDF ──────────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "prestress_beam_report")
        doc.generate_pdf(tex_path, clean_tex=False)
        with open(tex_path + ".pdf", "rb") as f:
            return f.read()

