import math
import os
import tempfile

from pylatex import Document, Section, Subsection, Math, Command, NoEscape, Head, Foot, PageStyle, Itemize, Tabular, Figure
from pylatex.utils import bold
from aci318m25 import ACI318M25

aci_tool = ACI318M25()


def _safe_note(note: str) -> str:
    """Escape or replace unicode characters that are unsafe in LaTeX."""
    return (
        note.replace("λ", r"$\lambda$")
        .replace("φ", r"$\phi$")
        .replace("≥", r"$\geq$")
        .replace("≤", r"$\leq$")
        .replace("√", r"$\sqrt{}$")
        .replace("⚠️", "")
        .replace("⚠", "")
        .replace("\ufe0f", "")
        .replace("ℹ️", "")
        .replace("ℹ", "")
        .replace("·", r"$\cdot$")
    )


def generate_slab_report(data, mat_props, geom, loads, res):
    """Generate a PDF report for the slab design.

    Parameters
    ----------
    data : SlabDesignModel
    mat_props : MaterialProperties
    geom : SlabGeometry
    loads : SlabLoads
    res : SlabAnalysisResult

    Returns
    -------
    bytes
        Raw bytes of the generated PDF.
    """
    geometry_options = {"margin": "1in", "headheight": "38pt", "includeheadfoot": True}
    doc = Document(geometry_options=geometry_options)

    doc.preamble.append(NoEscape(r"\usepackage{amsmath}"))
    doc.preamble.append(NoEscape(r"\usepackage{booktabs}"))
    doc.preamble.append(NoEscape(r"\usepackage{array}"))

    # ── Header / Footer ──
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
    doc.append(Command("huge", bold("RC Slab Design Report")))
    doc.append(Command("end", "center"))
    doc.append(NoEscape(r"\vspace*{1em}"))

    # ── Convenience aliases ──
    fc = data.fc_prime
    fy = data.fy
    lx = data.length_x
    ly = data.length_y
    t = data.thickness
    cover = data.cover
    dx = geom.effective_depth_x
    dy = geom.effective_depth_y
    phi_f = 0.90

    w_sw = loads.self_weight  # kN/m²
    w_sdl = loads.superimposed_dead  # kN/m²
    w_ll = loads.live_load  # kN/m²
    lf_d = loads.load_factors.get("D", 1.2)
    lf_l = loads.load_factors.get("L", 1.6)
    w_u = lf_d * (w_sw + w_sdl) + lf_l * w_ll  # kN/m²

    # ── Section 1: Material & Geometry ──
    with doc.create(Section("Material \\& Geometry")):
        ec_val = mat_props.ec
        with doc.create(Itemize()) as itemize:
            itemize.add_item(
                NoEscape(rf"Concrete strength, $f'_c = {fc}\,\text{{MPa}}$")
            )
            itemize.add_item(
                NoEscape(rf"Rebar yield strength, $f_y = {fy}\,\text{{MPa}}$")
            )
            itemize.add_item(
                NoEscape(
                    rf"Modulus of elasticity of concrete, $E_c = 4700\sqrt{{f'_c}} = 4700 \times \sqrt{{{fc}}} = {ec_val:.0f}\,\text{{MPa}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Slab dimensions: $L_x = {lx}\,\text{{mm}}$, $L_y = {ly}\,\text{{mm}}$, thickness $t = {t}\,\text{{mm}}$"
                )
            )
            itemize.add_item(
                NoEscape(rf"Clear concrete cover, $c_c = {cover}\,\text{{mm}}$")
            )
            db_bot_mm = float(data.bottom_bar_size.replace("D", ""))
            db_top_mm = float(data.top_bar_size.replace("D", ""))
            itemize.add_item(
                NoEscape(
                    rf"Effective depth (x-direction): $d_x = t - c_c - d_{{b,bot}}/2 = {t} - {cover} - {db_bot_mm}/2 = {dx:.1f}\,\text{{mm}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Effective depth (y-direction): $d_y = d_x - d_{{b,bot}} = {dx:.1f} - {db_bot_mm} = {dy:.1f}\,\text{{mm}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Preferred bottom bar: {data.bottom_bar_size}; preferred top bar: {data.top_bar_size}"
                )
            )

    # ── Section 2: Edge Conditions ──
    with doc.create(Section("Edge Support Conditions")):
        def _edge_desc(prefix):
            sup = getattr(data, f"{prefix}_support", "wall")
            cont = getattr(data, f"{prefix}_cont", "discontinuous")
            sup_str = {"wall": "Wall", "beam": "Beam", "column": "Columns at ends", "none": "Free"}.get(sup, sup)
            cont_str = "Continuous" if cont == "continuous" else "Discontinuous"
            detail = ""
            if sup == "wall":
                wt = getattr(data, f"{prefix}_wall_t", 0)
                detail = rf", wall thickness = {wt}\,\text{{mm}}"
            elif sup == "beam":
                bb = getattr(data, f"{prefix}_beam_b", 0)
                bh = getattr(data, f"{prefix}_beam_h", 0)
                detail = rf", beam $b = {bb}\,\text{{mm}}$, $h = {bh}\,\text{{mm}}$"
            elif sup == "column":
                cx = getattr(data, f"{prefix}_col_cx", 0)
                cy = getattr(data, f"{prefix}_col_cy", 0)
                detail = rf", column $c_x = {cx}\,\text{{mm}}$, $c_y = {cy}\,\text{{mm}}$"
            return rf"{sup_str} ({cont_str}{detail})"

        with doc.create(Itemize()) as itemize:
            itemize.add_item(NoEscape(rf"Top edge: {_edge_desc('edge_top')}"))
            itemize.add_item(NoEscape(rf"Bottom edge: {_edge_desc('edge_bot')}"))
            itemize.add_item(NoEscape(rf"Left edge: {_edge_desc('edge_left')}"))
            itemize.add_item(NoEscape(rf"Right edge: {_edge_desc('edge_right')}"))

    # ── Section 3: Applied Loads ──
    with doc.create(Section("Applied Loads")):
        doc.append(bold("Dead Loads:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"w_{{sw}} = \gamma_c \times t = 24.0 \times \frac{{{t}}}{{1000}} = {w_sw:.3f}\,\text{{kN/m}}^2"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"w_{{SDL}} = {w_sdl:.3f}\,\text{{kN/m}}^2"
                    )
                ]
            )
        )
        doc.append(bold("Live Load:"))
        doc.append(
            Math(
                data=[
                    NoEscape(rf"w_{{LL}} = {w_ll:.3f}\,\text{{kN/m}}^2")
                ]
            )
        )
        doc.append(bold("Factored Load (ACI 318M-25 §5.3.1a):"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"w_u = {lf_d}(w_{{sw}} + w_{{SDL}}) + {lf_l}\,w_{{LL}} = {lf_d}({w_sw:.3f} + {w_sdl:.3f}) + {lf_l} \times {w_ll:.3f} = {w_u:.3f}\,\text{{kN/m}}^2"
                    )
                ]
            )
        )
        doc.append(bold("Service Load Cases (for deflection):"))
        w_dead = w_sw + w_sdl
        w_sus = w_sw + w_sdl + 0.5 * w_ll
        w_tot = w_sw + w_sdl + w_ll
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"w_{{dead}} = w_{{sw}} + w_{{SDL}} = {w_sw:.3f} + {w_sdl:.3f} = {w_dead:.3f}\,\text{{kN/m}}^2"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"w_{{sus}} = w_{{sw}} + w_{{SDL}} + 0.5\,w_{{LL}} = {w_sw:.3f} + {w_sdl:.3f} + 0.5 \times {w_ll:.3f} = {w_sus:.3f}\,\text{{kN/m}}^2"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"w_{{tot}} = w_{{sw}} + w_{{SDL}} + w_{{LL}} = {w_dead:.3f} + {w_ll:.3f} = {w_tot:.3f}\,\text{{kN/m}}^2"
                    )
                ]
            )
        )

    # ── Section 4: FEA Analysis (Design Moments) ──
    with doc.create(Section("FEA Analysis — Design Moments")):
        doc.append(
            NoEscape(
                r"Analysis performed using a 12$\times$12 OpenSeesPy ShellMITC4 finite element model. "
                r"A stiffness modifier of 0.25 is applied to the slab and 0.35 to any supporting beams "
                r"for ultimate load analysis (ACI 318M-25 Table 6.6.3.1). "
                r"Wood-Armer moment resultants are used as design moments."
            )
        )
        doc.append(NoEscape(r"\vspace{0.5em}"))

        m_xp = res.moments.moment_x_positive
        m_xn = res.moments.moment_x_negative
        m_yp = res.moments.moment_y_positive
        m_yn = res.moments.moment_y_negative

        with doc.create(Itemize()) as itemize:
            itemize.add_item(
                NoEscape(
                    rf"Positive moment along x-direction (bottom): $M_{{xx}}^+ = {m_xp:.2f}\,\text{{kN-m/m}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Negative moment along x-direction (top): $M_{{xx}}^- = {m_xn:.2f}\,\text{{kN-m/m}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Positive moment along y-direction (bottom): $M_{{yy}}^+ = {m_yp:.2f}\,\text{{kN-m/m}}$"
                )
            )
            itemize.add_item(
                NoEscape(
                    rf"Negative moment along y-direction (top): $M_{{yy}}^- = {m_yn:.2f}\,\text{{kN-m/m}}$"
                )
            )

    # ── Section 5: Minimum Reinforcement ──
    with doc.create(Section("Minimum Reinforcement (ACI 318M-25 \\S{}7.6.1.1)")):
        if fy <= 420:
            rho_temp = 0.0020
            rho_formula = r"\rho_{temp} = 0.0020 \quad (f_y \leq 420\,\text{MPa})"
        elif fy <= 520:
            rho_temp = 0.0018
            rho_formula = r"\rho_{temp} = 0.0018 \quad (420 < f_y \leq 520\,\text{MPa})"
        else:
            rho_temp = max(0.0014, 0.0018 * 420.0 / fy)
            rho_formula = rf"\rho_{{temp}} = \max\!\left(0.0014,\; 0.0018 \times \frac{{420}}{{{fy}}}\right) = {rho_temp:.4f}"

        As_min = rho_temp * 1000.0 * t

        doc.append(Math(data=[NoEscape(rho_formula)]))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"A_{{s,min}} = \rho_{{temp}} \times b \times t = {rho_temp} \times 1000 \times {t} = {As_min:.0f}\,\text{{mm}}^2/\text{{m}}"
                    )
                ]
            )
        )
        s_max = min(3 * t, 450.0)
        doc.append(
            NoEscape(
                rf"Maximum bar spacing: $s_{{max}} = \min(3t, 450) = \min(3 \times {t}, 450) = {s_max:.0f}\,\text{{mm}}$"
            )
        )

    # ── Section 6: Flexural Reinforcement Design ──
    with doc.create(Section("Flexural Reinforcement Design")):

        def _design_calcs(subsec_title, Mu_knm_m, d_eff, pref_bar, bar_size, spacing):
            """Show step-by-step reinforcement design for one case."""
            with doc.create(Subsection(subsec_title)):
                doc.append(
                    Math(
                        data=[
                            NoEscape(rf"M_u = {Mu_knm_m:.2f}\,\text{{kN-m/m}}")
                        ]
                    )
                )

                if Mu_knm_m <= 0:
                    doc.append(
                        NoEscape(
                            r"No positive design moment; minimum reinforcement governs."
                        )
                    )
                    As_req = As_min
                else:
                    # Quadratic approach: φMn = φ As fy (d - a/2) = φ As fy d - φ As²fy²/(2×0.85×fc×b)
                    # Rearranged: A·As² + B·As + C = 0
                    # where A = φfy²/(2×0.85×fc×b), B = -φfyd, C = Mu (N-mm)
                    Mu_Nmm = Mu_knm_m * 1e6  # N-mm/m
                    A_coef = phi_f * fy ** 2 / (2 * 0.85 * fc * 1000)
                    B_coef = -phi_f * fy * d_eff
                    C_coef = Mu_Nmm
                    discriminant = B_coef ** 2 - 4 * A_coef * C_coef

                    doc.append(bold("Solving quadratic for required steel area:"))
                    doc.append(
                        Math(
                            data=[
                                NoEscape(
                                    rf"\phi M_n = \phi A_s f_y \!\left(d - \frac{{A_s f_y}}{{2 \times 0.85 f'_c b}}\right)"
                                )
                            ]
                        )
                    )
                    doc.append(
                        NoEscape(
                            r"Rearranging: $\frac{\phi f_y^2}{2 \times 0.85 f'_c b} A_s^2 - \phi f_y d \cdot A_s + M_u = 0$"
                        )
                    )
                    doc.append(NoEscape(r"\\"))
                    doc.append(
                        Math(
                            data=[
                                NoEscape(
                                    rf"A = \frac{{\phi f_y^2}}{{2 \times 0.85 f'_c b}} = \frac{{{phi_f} \times {fy}^2}}{{2 \times 0.85 \times {fc} \times 1000}} = {A_coef:.6f}"
                                )
                            ]
                        )
                    )
                    doc.append(
                        Math(
                            data=[
                                NoEscape(
                                    rf"B = -\phi f_y d = -{phi_f} \times {fy} \times {d_eff:.1f} = {B_coef:.1f}"
                                )
                            ]
                        )
                    )
                    doc.append(
                        Math(
                            data=[
                                NoEscape(
                                    rf"C = M_u = {Mu_knm_m:.2f} \times 10^6 = {C_coef:.0f}\,\text{{N-mm/m}}"
                                )
                            ]
                        )
                    )

                    if discriminant < 0:
                        doc.append(
                            NoEscape(
                                r"\textbf{WARNING: Discriminant is negative — section may be inadequate. "
                                r"Increase slab thickness.}"
                            )
                        )
                        As_req = max(-B_coef / (2 * A_coef), As_min)
                    else:
                        As_req = max((-B_coef - math.sqrt(discriminant)) / (2 * A_coef), As_min)
                        doc.append(
                            Math(
                                data=[
                                    NoEscape(
                                        rf"A_{{s,req}} = \frac{{-B - \sqrt{{B^2 - 4AC}}}}{{2A}} = \frac{{{-B_coef:.1f} - \sqrt{{{B_coef:.1f}^2 - 4 \times {A_coef:.6f} \times {C_coef:.0f}}}}}{{2 \times {A_coef:.6f}}} = {As_req:.1f}\,\text{{mm}}^2/\text{{m}}"
                                    )
                                ]
                            )
                        )
                    As_req = max(As_req, As_min)
                    doc.append(
                        NoEscape(
                            rf"Governing required area: $A_{{s,req}} = \max(A_{{s,calc}},\, A_{{s,min}}) = {As_req:.1f}\,\text{{mm}}^2/\text{{m}}$"
                        )
                    )

                # Selected bar
                bar_area = aci_tool.get_bar_area(bar_size)
                As_prov = bar_area * 1000.0 / spacing
                doc.append(
                    NoEscape(
                        rf"Selected: \textbf{{{bar_size} @ {spacing:.0f} mm}} "
                        rf"$\Rightarrow A_{{s,prov}} = \dfrac{{{bar_area:.1f} \times 1000}}{{{spacing:.0f}}} = {As_prov:.1f}\,\text{{mm}}^2/\text{{m}}$"
                    )
                )
                doc.append(NoEscape(r"\\"))

                # Capacity verification
                a = (As_prov * fy) / (0.85 * fc * 1000.0)
                phi_mn = phi_f * As_prov * fy * (d_eff - a / 2.0) / 1e6
                dcr = Mu_knm_m / phi_mn if phi_mn > 0 else 99.9
                status = "OK" if dcr <= 1.0 else "NG"
                doc.append(bold("Capacity verification:"))
                doc.append(
                    Math(
                        data=[
                            NoEscape(
                                rf"a = \frac{{A_s f_y}}{{0.85 f'_c b}} = \frac{{{As_prov:.1f} \times {fy}}}{{0.85 \times {fc} \times 1000}} = {a:.2f}\,\text{{mm}}"
                            )
                        ]
                    )
                )
                doc.append(
                    Math(
                        data=[
                            NoEscape(
                                rf"\phi M_n = \phi A_s f_y \!\left(d - \frac{{a}}{{2}}\right) = {phi_f} \times {As_prov:.1f} \times {fy} \times \left({d_eff:.1f} - \frac{{{a:.2f}}}{{2}}\right) \times 10^{{-6}} = {phi_mn:.2f}\,\text{{kN-m/m}}"
                            )
                        ]
                    )
                )
                doc.append(
                    Math(
                        data=[
                            NoEscape(
                                rf"DCR = \frac{{M_u}}{{\phi M_n}} = \frac{{{Mu_knm_m:.2f}}}{{{phi_mn:.2f}}} = {dcr:.3f} \quad \textbf{{{status}}}"
                            )
                        ]
                    )
                )
                return As_prov

        # Bottom X
        As_bx = _design_calcs(
            "Bottom Reinforcement — X-direction ($+M_{xx}$)",
            res.moments.moment_x_positive,
            dx,
            data.bottom_bar_size,
            res.reinforcement.main_bars_x,
            res.reinforcement.main_spacing_x,
        )

        # Bottom Y
        As_by = _design_calcs(
            "Bottom Reinforcement — Y-direction ($+M_{yy}$)",
            res.moments.moment_y_positive,
            dy,
            data.bottom_bar_size,
            res.reinforcement.main_bars_y,
            res.reinforcement.main_spacing_y,
        )

        # Top X
        _design_calcs(
            "Top Reinforcement — X-direction ($-M_{xx}$)",
            res.moments.moment_x_negative,
            dx,
            data.top_bar_size,
            res.reinforcement.top_bars_x,
            res.reinforcement.top_spacing_x,
        )

        # Top Y
        _design_calcs(
            "Top Reinforcement — Y-direction ($-M_{yy}$)",
            res.moments.moment_y_negative,
            dy,
            data.top_bar_size,
            res.reinforcement.top_bars_y,
            res.reinforcement.top_spacing_y,
        )

        # Shrinkage / temperature
        with doc.create(Subsection("Shrinkage and Temperature Reinforcement")):
            bsh = res.reinforcement.shrinkage_bars
            ssh = res.reinforcement.shrinkage_spacing
            bar_area_sh = aci_tool.get_bar_area(bsh)
            As_sh_prov = bar_area_sh * 1000.0 / ssh
            doc.append(
                NoEscape(
                    rf"$A_{{s,min}} = {As_min:.0f}\,\text{{mm}}^2/\text{{m}}$"
                )
            )
            doc.append(NoEscape(r"\\"))
            doc.append(
                NoEscape(
                    rf"Selected: \textbf{{{bsh} @ {ssh:.0f} mm}} "
                    rf"$\Rightarrow A_{{s,prov}} = \dfrac{{{bar_area_sh:.1f} \times 1000}}{{{ssh:.0f}}} = {As_sh_prov:.1f}\,\text{{mm}}^2/\text{{m}}$"
                )
            )

    # ── Section 7: Deflection Check ──
    with doc.create(Section("Serviceability — Deflection Check (ACI 318M-25 \\S{}24.2)")):
        doc.append(
            NoEscape(
                r"Deflection is computed using the effective moment of inertia $I_e$ per "
                r"ACI 318M-25 Eq.~(24.2.3.5a). Cracked and gross section properties are "
                r"calculated per unit width (1000~mm) of the governing direction."
            )
        )
        doc.append(NoEscape(r"\vspace{0.5em}"))

        # Gross properties (per m width)
        Ig = 1000.0 * t ** 3 / 12.0  # mm⁴/m
        yt = t / 2.0
        fr = 0.62 * math.sqrt(fc)
        Mcr_Nmm = fr * Ig / yt  # N-mm/m
        Mcr = Mcr_Nmm / 1e6  # kN-m/m

        doc.append(bold("Gross Section Properties (per 1000 mm width):"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"I_g = \frac{{b\,t^3}}{{12}} = \frac{{1000 \times {t}^3}}{{12}} = {Ig/1e6:.0f} \times 10^6\,\text{{mm}}^4/\text{{m}}"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"f_r = 0.62\sqrt{{f'_c}} = 0.62 \times \sqrt{{{fc}}} = {fr:.3f}\,\text{{MPa}}"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"M_{{cr}} = \frac{{f_r I_g}}{{y_t}} = \frac{{{fr:.3f} \times {Ig/1e6:.0f} \times 10^6}}{{{yt:.1f}}} \times 10^{{-6}} = {Mcr:.2f}\,\text{{kN-m/m}}"
                    )
                ]
            )
        )

        # Cracked section properties — use governing bottom As (x-direction)
        As_gov = As_bx  # mm²/m (governing bottom reinforcement)
        n = 200000.0 / mat_props.ec
        rho = As_gov / (1000.0 * dx)
        k = math.sqrt(2.0 * rho * n + (rho * n) ** 2) - rho * n
        Icr = (1000.0 * (k * dx) ** 3) / 3.0 + n * As_gov * (dx * (1.0 - k)) ** 2  # mm⁴/m

        doc.append(bold("Cracked Section Properties:"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"n = \frac{{E_s}}{{E_c}} = \frac{{200,000}}{{{mat_props.ec:.0f}}} = {n:.3f}"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"\rho = \frac{{A_s}}{{b\,d}} = \frac{{{As_gov:.1f}}}{{1000 \times {dx:.1f}}} = {rho:.5f}"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"k = \sqrt{{2\rho n + (\rho n)^2}} - \rho n = {k:.4f}"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"I_{{cr}} = \frac{{b\,(kd)^3}}{{3}} + n A_s(d - kd)^2 = \frac{{1000 \times ({k:.4f} \times {dx:.1f})^3}}{{3}} + {n:.3f} \times {As_gov:.1f} \times ({dx:.1f} \times (1-{k:.4f}))^2 = {Icr/1e6:.0f} \times 10^6\,\text{{mm}}^4/\text{{m}}"
                    )
                ]
            )
        )

        # Governing service moment for Ie
        Ma = max(res.moments.moment_x_positive, res.moments.moment_y_positive)
        doc.append(
            NoEscape(
                rf"Governing service moment (positive): $M_a = \max(M_{{xx}}^+, M_{{yy}}^+) = {Ma:.2f}\,\text{{kN-m/m}}$"
            )
        )
        doc.append(NoEscape(r"\\"))

        # Effective moment of inertia — ACI 318M-25 Eq. 24.2.3.5a
        if Ma <= (2.0 / 3.0) * Mcr:
            Ie = Ig
            doc.append(
                NoEscape(
                    rf"Since $M_a = {Ma:.2f} \leq \tfrac{{2}}{{3}} M_{{cr}} = {(2/3)*Mcr:.2f}$, section remains uncracked: $I_e = I_g = {Ig/1e6:.0f} \times 10^6\,\text{{mm}}^4/\text{{m}}$"
                )
            )
        else:
            factor_m = ((2.0 / 3.0) * Mcr / Ma) ** 2
            Ie = Icr / (1.0 - factor_m * (1.0 - Icr / Ig))
            Ie = max(Icr, min(Ie, Ig))
            doc.append(bold("Effective Inertia (ACI 318M-25 Eq.~24.2.3.5a):"))
            doc.append(
                Math(
                    data=[
                        NoEscape(
                            r"I_e = \frac{I_{cr}}{1 - \left(\frac{\frac{2}{3}M_{cr}}{M_a}\right)^2 \left(1 - \frac{I_{cr}}{I_g}\right)}"
                        )
                    ]
                )
            )
            doc.append(
                Math(
                    data=[
                        NoEscape(
                            rf"I_e = \frac{{{Icr/1e6:.0f} \times 10^6}}{{1 - \left(\frac{{\frac{{2}}{{3}} \times {Mcr:.2f}}}{{{Ma:.2f}}}\right)^2 \left(1 - \frac{{{Icr/1e6:.0f}}}{{{Ig/1e6:.0f}}}\right)}} = {Ie/1e6:.0f} \times 10^6\,\text{{mm}}^4/\text{{m}}"
                        )
                    ]
                )
            )

        doc.append(NoEscape(r"\vspace{0.5em}"))

        # Deflection results (from FEA with Ie correction)
        span_mm = max(lx, ly)
        def_lim_live = span_mm / 360.0
        try:
            lim_long_div = float(data.deflection_limit)
        except (AttributeError, TypeError, ValueError):
            lim_long_div = 240.0
        def_lim_long = span_mm / lim_long_div

        delta_live = res.deflection_live
        delta_long = res.deflection_long

        doc.append(bold("Deflection Results (from FEA with $I_e$ correction):"))
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"\Delta_{{live}} = {delta_live:.2f}\,\text{{mm}} \quad \left(\text{{Limit: }} \frac{{L}}{{360}} = \frac{{{span_mm:.0f}}}{{360}} = {def_lim_live:.1f}\,\text{{mm}}\right)"
                    )
                ]
            )
        )
        live_status = "PASS" if delta_live <= def_lim_live else "FAIL"
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"\Delta_{{live}} = {delta_live:.2f} \leq {def_lim_live:.1f}\,\text{{mm}} \quad \textbf{{{live_status}}}"
                    )
                ]
            )
        )
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"\Delta_{{long}} = \Delta_{{live}} + 2\,\Delta_{{sus}} = {delta_long:.2f}\,\text{{mm}} \quad \left(\text{{Limit: }} \frac{{L}}{{{int(lim_long_div)}}} = {def_lim_long:.1f}\,\text{{mm}}\right)"
                    )
                ]
            )
        )
        long_status = "PASS" if delta_long <= def_lim_long else "FAIL"
        doc.append(
            Math(
                data=[
                    NoEscape(
                        rf"\Delta_{{long}} = {delta_long:.2f} \leq {def_lim_long:.1f}\,\text{{mm}} \quad \textbf{{{long_status}}}"
                    )
                ]
            )
        )

    # ── Section 8: Design Checks Summary ──
    with doc.create(Section("Design Checks Summary")):
        with doc.create(Tabular("l l l l")) as tab:
            tab.add_hline()
            tab.add_row(
                (bold("Check"), bold("Demand"), bold("Capacity / Limit"), bold("Status"))
            )
            tab.add_hline()

            # Flexure — DCR
            dcr_val = res.utilization_ratio
            dcr_status = "PASS" if dcr_val <= 1.0 else "FAIL"
            tab.add_row(
                (
                    NoEscape(r"Flexure (max DCR)"),
                    f"{dcr_val:.3f}",
                    "1.000",
                    NoEscape(rf"\textbf{{{dcr_status}}}"),
                )
            )

            # Live deflection
            tab.add_row(
                (
                    NoEscape(r"Live deflection"),
                    f"{delta_live:.2f} mm",
                    f"{def_lim_live:.1f} mm",
                    NoEscape(rf"\textbf{{{live_status}}}"),
                )
            )

            # Long-term deflection
            tab.add_row(
                (
                    NoEscape(r"Long-term deflection"),
                    f"{delta_long:.2f} mm",
                    f"{def_lim_long:.1f} mm",
                    NoEscape(rf"\textbf{{{long_status}}}"),
                )
            )
            tab.add_hline()

    # ── Section 9: Reinforcement Schedule ──
    with doc.create(Section("Reinforcement Schedule")):
        def _as_prov(bar, spacing):
            if not bar or spacing <= 0:
                return 0.0
            return aci_tool.get_bar_area(bar) * 1000.0 / spacing

        with doc.create(Tabular("l l r r")) as tab:
            tab.add_hline()
            tab.add_row(
                (
                    bold("Location"),
                    bold("Bar @ Spacing"),
                    bold("As prov. (mm²/m)"),
                    bold("As min. (mm²/m)"),
                )
            )
            tab.add_hline()
            bx = res.reinforcement.main_bars_x
            sx = res.reinforcement.main_spacing_x
            by = res.reinforcement.main_bars_y
            sy = res.reinforcement.main_spacing_y
            tx = res.reinforcement.top_bars_x
            stx = res.reinforcement.top_spacing_x
            ty_bar = res.reinforcement.top_bars_y
            sty = res.reinforcement.top_spacing_y
            bsh = res.reinforcement.shrinkage_bars
            ssh = res.reinforcement.shrinkage_spacing

            tab.add_row(
                ("Bottom X", f"{bx} @ {sx:.0f} mm", f"{_as_prov(bx, sx):.1f}", f"{As_min:.0f}")
            )
            tab.add_row(
                ("Bottom Y", f"{by} @ {sy:.0f} mm", f"{_as_prov(by, sy):.1f}", f"{As_min:.0f}")
            )
            if tx:
                tab.add_row(
                    ("Top X", f"{tx} @ {stx:.0f} mm", f"{_as_prov(tx, stx):.1f}", f"{As_min:.0f}")
                )
            if ty_bar:
                tab.add_row(
                    ("Top Y", f"{ty_bar} @ {sty:.0f} mm", f"{_as_prov(ty_bar, sty):.1f}", f"{As_min:.0f}")
                )
            tab.add_row(
                (
                    "Shrinkage/Temp.",
                    f"{bsh} @ {ssh:.0f} mm",
                    f"{_as_prov(bsh, ssh):.1f}",
                    f"{As_min:.0f}",
                )
            )
            tab.add_hline()

    # ── Section 10: Design Notes ──
    if res.design_notes:
        with doc.create(Section("Design Notes")):
            with doc.create(Itemize()) as itemize:
                for note in list(dict.fromkeys(res.design_notes)):
                    itemize.add_item(NoEscape(_safe_note(note)))

    # ── Generate PDF ──
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "slab_report")
    doc.generate_pdf(filepath, clean_tex=False)

    with open(filepath + ".pdf", "rb") as f:
        pdf_bytes = f.read()

    return pdf_bytes
