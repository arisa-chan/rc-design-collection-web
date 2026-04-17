# -*- coding: utf-8 -*-

"""
ACI 318M-25 Beam Design Library
Building Code Requirements for Structural Concrete - Beam Design
"""

import math
from typing import Dict, Tuple, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from aci318m25 import ACI318M25, ConcreteStrengthClass, ReinforcementGrade, MaterialProperties


class BeamType(Enum):
    RECTANGULAR = "rectangular"
    T_BEAM = "t_beam"
    L_BEAM = "l_beam"
    INVERTED_T = "inverted_t"


class SeismicDesignCategory(Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"


class FrameSystem(Enum):
    ORDINARY = "ordinary"
    INTERMEDIATE = "intermediate"
    SPECIAL = "special"


@dataclass
class BeamGeometry:
    length: float
    width: float
    height: float
    effective_depth: float
    cover: float
    flange_width: float
    flange_thickness: float
    beam_type: BeamType
    clear_span: float = 0.0
    sdc: SeismicDesignCategory = SeismicDesignCategory.A
    frame_system: FrameSystem = FrameSystem.ORDINARY
    aggregate_size: float = 20.0  # Maximum aggregate size (mm), ACI 318M-25 §25.8.1
    column_width: float = 0.0    # supporting col. width ⊥ beam axis; for SMF §18.6.2.1(d)
    column_depth: float = 0.0    # supporting col. depth ∥ beam axis; 0 = assume = column_width


@dataclass
class ReinforcementDesign:
    top_bars: List[str]
    top_area: float
    bottom_bars: List[str]
    bottom_area: float
    stirrups: str
    stirrup_spacing: float
    development_length_top: float
    development_length_bot: float
    stirrup_spacing_hinge: float = 0.0
    hinge_length: float = 0.0
    torsion_longitudinal_area: float = 0.0
    torsion_required: bool = False
    side_bars: List[str] = field(default_factory=list)
    side_area: float = 0.0


@dataclass
class BeamAnalysisResult:
    moment_capacity_top: float
    moment_capacity_bot: float
    probable_moment_top: float
    probable_moment_bot: float
    shear_capacity: float
    capacity_shear_ve: float
    torsion_capacity: float
    deflection: float
    crack_width: float
    reinforcement: ReinforcementDesign
    utilization_ratio: float
    design_notes: List[str]


class ACI318M25BeamDesign:

    def __init__(self):
        self.aci = ACI318M25()
        self.phi_factors = {'flexure_tension_controlled': 0.90, 'flexure_compression_controlled_tied': 0.65,
                            'shear': 0.75, 'torsion': 0.75, 'seismic_joint_shear': 0.85}

    def _parse_stirrup(self, stirrup_str: str) -> Tuple[int, str]:
        if stirrup_str == 'None': return 0, 'D10'
        if "-leg " in stirrup_str:
            parts = stirrup_str.split('-leg ')
            return int(parts[0]), parts[1]
        return 2, stirrup_str

    def _calculate_vc(self, beam_geometry: BeamGeometry, material_props: MaterialProperties,
                      stirrup_size: str, spacing: float, As_provided: float = 0.0,
                      lambda_cc: float = 1.0) -> float:
        """Returns Vc in N per ACI 318M-25 Table 22.5.5.1."""
        bw, d = beam_geometry.width, beam_geometry.effective_depth
        fc_prime, fyt = material_props.fc_prime, material_props.fyt
        lambda_s = min(1.0, math.sqrt(2.0 / (1.0 + 0.004 * d)))  # size effect factor
        if stirrup_size != 'None' and spacing > 0:
            num_legs, actual_size = self._parse_stirrup(stirrup_size)
            Av_prov = num_legs * self.aci.get_bar_area(actual_size) / spacing  # mm²/mm
            Av_min = max(0.062 * math.sqrt(fc_prime) * bw / fyt, 0.35 * bw / fyt)  # mm²/mm
            if Av_prov >= Av_min:
                # Table 22.5.5.1 (a): simplified row, Av ≥ Av,min — no size effect
                return 0.17 * lambda_cc * math.sqrt(fc_prime) * bw * d  # N
            else:
                # Table 22.5.5.1 (b): detailed row, Av < Av,min — size effect applies
                rho_w = As_provided / (bw * d) if As_provided > 0.0 else 0.005
                return 0.66 * lambda_s * lambda_cc * (rho_w ** (1.0 / 3.0)) * math.sqrt(fc_prime) * bw * d  # N
        else:
            # No stirrups: detailed formula with size effect
            rho_w = As_provided / (bw * d) if As_provided > 0.0 else 0.005
            return 0.66 * lambda_s * lambda_cc * (rho_w ** (1.0 / 3.0)) * math.sqrt(fc_prime) * bw * d  # N

    # Dimension checks for SMF
    # OK
    def check_seismic_geometric_limits(self, geometry: BeamGeometry) -> List[str]:
        warnings = []
        if geometry.frame_system == FrameSystem.SPECIAL:
            if geometry.clear_span > 0 and (geometry.clear_span / geometry.effective_depth) < 4.0: warnings.append(
                "SMF Violation: Clear span to depth ratio must be >= 4.0.")
            if geometry.width < 250.0: warnings.append(
                f"SMF Violation: Beam width ({geometry.width:.0f} mm) must be >= 250 mm.")
            if (geometry.width / geometry.height) < 0.3: warnings.append(
                "SMF Violation: Beam width to overall depth ratio must be >= 0.3.")
            # ACI 318M-25 §18.6.2.1(d): beam width limit relative to supporting column
            if geometry.column_width > 0:
                h_col = geometry.column_depth if geometry.column_depth > 0 else geometry.column_width
                ext_max = min(geometry.column_width, 0.75 * h_col)
                bw_max = geometry.column_width + 2.0 * ext_max
                if geometry.width > bw_max:
                    warnings.append(
                        f"SMF §18.6.2.1(d) Violation: Beam width ({geometry.width:.0f} mm) > "
                        f"allowed ({bw_max:.0f} mm = bw_col + 2\u00d7min(bw_col, 0.75\u00d7h_col)).")
        return warnings

    def check_joint_shear(self, As_top: float, As_bot: float,
                          beam_geometry: BeamGeometry, material_props: MaterialProperties) -> List[str]:
        """Beam-column joint shear check per ACI 318M-25 §18.8 for SMF.
        Vj is computed conservatively (Vcol = 0). γ defaults to 1.0 (least confined);
        revise manually based on actual joint confinement per Table 18.8.4.1.
        Requires beam_geometry.column_width > 0; skips check otherwise.
        """
        if beam_geometry.frame_system != FrameSystem.SPECIAL or beam_geometry.column_width <= 0:
            return []
        notes = []
        fy = material_props.fy
        fc_prime = material_props.fc_prime
        bw = beam_geometry.width
        b_col = beam_geometry.column_width
        h_col = beam_geometry.column_depth if beam_geometry.column_depth > 0 else b_col

        # §18.8.4.3: effective joint width b_j (concentric joint assumed)
        # b_j = min(bw + h_col, b_col) — simplified for centered beam
        b_j = min(bw + h_col, b_col)
        b_j = max(b_j, bw)  # b_j cannot be less than bw
        Aj = b_j * h_col  # mm²

        # §18.8.4.1: joint strength factor γ (MPa^0.5); use 1.0 (conservative — other cases)
        # Revise to 1.25 (3-sided / 2-opp. confined) or 1.7 (all-4-sides confined) as appropriate.
        gamma = 1.0
        phi_j = self.phi_factors['seismic_joint_shear']  # 0.85
        # §22.5.3.1: cap √f'c at 8.3 MPa^0.5 for shear strength
        phi_Vn_joint = phi_j * gamma * min(math.sqrt(fc_prime), 8.3) * Aj / 1000  # kN

        # §18.8.3.1: design joint shear force (Vcol conservatively taken as 0)
        Vj = 1.25 * fy * (As_top + As_bot) / 1000  # kN

        util_j = Vj / phi_Vn_joint if phi_Vn_joint > 0 else float('inf')
        status = "OK" if Vj <= phi_Vn_joint else "EXCEEDS CAPACITY"
        notes.append(
            f"Joint Shear §18.8: Vj = {Vj:.1f} kN, \u03c6Vn = {phi_Vn_joint:.1f} kN "
            f"(\u03b3 = {gamma:.2f}, Aj = {Aj / 1e3:.0f} cm\u00b2, b_j = {b_j:.0f} \u00d7 h_col = {h_col:.0f} mm) "
            f"\u2014 {status}. Vcol = 0 assumed (conservative); revise \u03b3 per Table 18.8.4.1.")
        if Vj > phi_Vn_joint:
            notes.append(
                f"CRITICAL Joint Shear §18.8: DCR = {util_j:.2f}. "
                "Increase column dimensions or reduce beam longitudinal reinforcement.")
        return notes

    # Torsional properties
    # OK
    def _calculate_torsional_properties(self, beam_geometry: BeamGeometry, stirrup_size: str = 'D10') -> Dict[
        str, float]:
        _, actual_stirrup_sz = self._parse_stirrup(stirrup_size)
        bw, h, cover = beam_geometry.width, beam_geometry.height, beam_geometry.cover
        db_stirrup = self.aci.get_bar_diameter(actual_stirrup_sz)

        Acp, pcp = bw * h, 2 * (bw + h)
        x1, y1 = bw - 2 * cover - db_stirrup, h - 2 * cover - db_stirrup
        if x1 <= 0 or y1 <= 0: raise ValueError("Beam dimensions too small for cover and stirrups.")
        Aoh, ph = x1 * y1, 2 * (x1 + y1)
        Ao = 0.85 * Aoh
        return {'Acp': Acp, 'pcp': pcp, 'Aoh': Aoh, 'ph': ph, 'Ao': Ao, 'x1': x1, 'y1': y1}

    # Treshold torsion
    # OK
    def check_torsion_requirement(self, tu: float, beam_geometry: BeamGeometry,
                                  material_props: MaterialProperties) -> bool:
        if tu <= 0.0: return False
        props = self._calculate_torsional_properties(beam_geometry)
        Tth = 0.083 * math.sqrt(material_props.fc_prime) * (props['Acp'] ** 2 / props['pcp']) / 1e6
        return tu > (self.phi_factors['torsion'] * Tth)

    # Torsional longitudinal reinforcement
    # OK
    def _calculate_torsional_longitudinal_reinforcement(self, tu: float, beam_geometry: BeamGeometry,
                                                        material_props: MaterialProperties, stirrup_size: str) -> float:
        if not self.check_torsion_requirement(tu, beam_geometry, material_props): return 0.0

        props = self._calculate_torsional_properties(beam_geometry, stirrup_size)
        bw, fc_prime, fy, fyt = beam_geometry.width, material_props.fc_prime, material_props.fy, material_props.fyt
        phi_t = self.phi_factors['torsion']

        theta = math.radians(45)
        At_over_s = tu * 1e6 / (phi_t * 2 * props['Ao'] * fyt * (1 / math.tan(theta)))
        At_over_s_min = max(At_over_s, 0.175 * bw / fyt)

        Al = At_over_s * props['ph'] * (fyt / fy) * (1 / math.tan(theta)) ** 2
        Al_min = (0.42 * math.sqrt(fc_prime) * props['Acp'] / fy) - (At_over_s_min * props['ph'] * (fyt / fy))

        return max(0.0, Al, Al_min)

    def calculate_probable_moment_capacity(self, As: float, As_prime: float, beam_geometry: BeamGeometry,
                                           material_props: MaterialProperties, stirrup_size: str = 'D10',
                                           main_bar_size: str = 'D20') -> float:
        fc_prime, fy_pr = material_props.fc_prime, 1.25 * material_props.fy
        b, d = beam_geometry.width, beam_geometry.effective_depth
        _, actual_stirrup = self._parse_stirrup(stirrup_size)
        db_stirrup = self.aci.get_bar_diameter(actual_stirrup)
        db_main = self.aci.get_bar_diameter(main_bar_size)
        d_prime = beam_geometry.cover + db_stirrup + 0.5 * db_main  # ACI: distance from compression face to compression steel centroid
        a_net = (As * fy_pr - As_prime * fy_pr) / (0.85 * fc_prime * b)
        if a_net > 0:
            # Doubly-reinforced: compression steel yields, equilibrium holds.
            # Taking moments about the tension steel:
            #   Mn = Cc*(d - a/2) + Cs*(d - d')  ;  Cc = As*fpr - As'*fpr
            #      = As*fpr*(d - a/2) + As'*fpr*(a/2 - d')
            return max(0.0, (As * fy_pr * (d - a_net / 2) + As_prime * fy_pr * (a_net / 2 - d_prime)) / 1e6)
        else:
            # As < As': net compression block is negative, use singly-reinforced
            a = As * fy_pr / (0.85 * fc_prime * b)
            return max(0.0, As * fy_pr * (d - a / 2) / 1e6)

    def calculate_minimum_reinforcement_ratio(self, fc_prime: float, fy: float) -> float:
        return max(1.4 / fy, 0.25 * math.sqrt(fc_prime) / fy)

    def calculate_maximum_reinforcement_ratio(self, fc_prime: float, fy: float, beam_geometry: BeamGeometry) -> float:
        beta1 = self.aci.calculate_beta1(fc_prime)
        rho_max = 3 / 8 * 0.85 * fc_prime * beta1 / fy
        return min(rho_max, 0.025) if beam_geometry.frame_system == FrameSystem.SPECIAL else rho_max

    def _get_required_steel(self, mu: float, beam_geometry: BeamGeometry, material_props: MaterialProperties,
                            notes: List[str] = None) -> float:
        fc_prime, fy = material_props.fc_prime, material_props.fy
        bw, d = beam_geometry.width, beam_geometry.effective_depth
        As_min = self.calculate_minimum_reinforcement_ratio(fc_prime, fy) * bw * d

        if mu <= 0.0:
            if notes is not None:
                notes.append("Minimum flexural reinforcement governs (Mu ≤ 0 or zero demand at this face).")
            return As_min

        be = self._get_effective_width(beam_geometry)
        hf = beam_geometry.flange_thickness
        Mu = mu * 1e6
        phi = self.phi_factors['flexure_tension_controlled']

        if be > bw and hf > 0:
            # Check if flange alone is sufficient (a ≤ hf): solve as rectangular beam with width be
            Mf_cap = phi * 0.85 * fc_prime * be * hf * (d - hf / 2)
            if Mu <= Mf_cap:
                A = phi * fy ** 2 / (2 * 0.85 * fc_prime * be)
                B, C = -phi * fy * d, Mu
                disc = B ** 2 - 4 * A * C
                if disc < 0:
                    if notes is not None:
                        notes.append(
                            f"WARNING: Section too small for tension-controlled behavior at Mu = {mu:.1f} kNm. "
                            f"Increase beam dimensions.")
                    return self.calculate_maximum_reinforcement_ratio(fc_prime, fy, beam_geometry) * bw * d
                return max((-B - math.sqrt(disc)) / (2 * A), As_min)
            else:
                # T-section: NA falls in web — split into flange overhang + web contributions
                Cf = 0.85 * fc_prime * (be - bw) * hf
                Asf = Cf / fy
                Muf = phi * Cf * (d - hf / 2)
                Muw = Mu - Muf
                A = phi * fy ** 2 / (2 * 0.85 * fc_prime * bw)
                B, C = -phi * fy * d, Muw
                disc = B ** 2 - 4 * A * C
                if disc < 0:
                    if notes is not None:
                        notes.append(
                            f"WARNING: Web too small for remaining moment at Mu = {mu:.1f} kNm. "
                            f"Increase beam dimensions.")
                    return self.calculate_maximum_reinforcement_ratio(fc_prime, fy, beam_geometry) * bw * d + Asf
                return max((-B - math.sqrt(disc)) / (2 * A) + Asf, As_min)
        else:
            # Rectangular section
            A = phi * fy ** 2 / (2 * 0.85 * fc_prime * bw)
            B, C = -phi * fy * d, Mu
            disc = B ** 2 - 4 * A * C
            if disc < 0:
                As_max = self.calculate_maximum_reinforcement_ratio(fc_prime, fy, beam_geometry) * bw * d
                if notes is not None:
                    notes.append(
                        f"WARNING: Section too small for tension-controlled behavior at Mu = {mu:.1f} kNm. "
                        f"Increase beam dimensions. Design uses maximum reinforcement ratio as a lower bound.")
                return As_max
            return max((-B - math.sqrt(disc)) / (2 * A), As_min)

    def design_flexural_reinforcement(self, mu_top: float, mu_bot: float, al_top: float, al_bot: float,
                                      beam_geometry: BeamGeometry, material_props: MaterialProperties,
                                      is_support: bool = False, max_as_support: float = 0.0,
                                      pref_stirrup: str = 'D10') -> Tuple[ReinforcementDesign, List[str]]:
        notes = []
        fc_prime, fy = material_props.fc_prime, material_props.fy

        As_top_req = self._get_required_steel(mu_top, beam_geometry, material_props, notes) + al_top
        As_bot_req = self._get_required_steel(mu_bot, beam_geometry, material_props, notes) + al_bot

        if beam_geometry.frame_system == FrameSystem.SPECIAL:
            phi_f = self.phi_factors['flexure_tension_controlled']
            if is_support:
                Mn_top = self._calculate_moment_capacity(As_top_req, beam_geometry, material_props)
                Mn_bot = self._calculate_moment_capacity(As_bot_req, beam_geometry, material_props)
                if Mn_bot < 0.5 * Mn_top:
                    # Solve for As_bot giving Mn_bot = 0.5 * Mn_top (ACI 318M-25 §18.6.3.2)
                    As_bot_req = self._get_required_steel(phi_f * 0.5 * Mn_top, beam_geometry, material_props, notes) + al_bot
                    notes.append("SMF 18.6.3.2: +Mn at joint face increased to >= 50% of -Mn.")

            if max_as_support > 0:
                Mn_max_support = self._calculate_moment_capacity(max_as_support, beam_geometry, material_props)
                Mn_top = self._calculate_moment_capacity(As_top_req, beam_geometry, material_props)
                Mn_bot = self._calculate_moment_capacity(As_bot_req, beam_geometry, material_props)
                if Mn_top < 0.25 * Mn_max_support:
                    As_top_req = self._get_required_steel(phi_f * 0.25 * Mn_max_support, beam_geometry, material_props, notes) + al_top
                    notes.append("SMF 18.6.3.2: -Mn increased to >= 25% of max joint face moment.")
                if Mn_bot < 0.25 * Mn_max_support:
                    As_bot_req = self._get_required_steel(phi_f * 0.25 * Mn_max_support, beam_geometry, material_props, notes) + al_bot
                    notes.append("SMF 18.6.3.2: +Mn increased to >= 25% of max joint face moment.")

        # ACI 318M-25 §18.4.3.1: IMF minimum positive moment strength at joint faces
        if beam_geometry.frame_system == FrameSystem.INTERMEDIATE and is_support:
            phi_f = self.phi_factors['flexure_tension_controlled']
            Mn_top_imf = self._calculate_moment_capacity(As_top_req, beam_geometry, material_props)
            Mn_bot_imf = self._calculate_moment_capacity(As_bot_req, beam_geometry, material_props)
            if Mn_top_imf > 0 and Mn_bot_imf < (1.0 / 3.0) * Mn_top_imf:
                As_bot_req = (self._get_required_steel(phi_f * (1.0 / 3.0) * Mn_top_imf,
                                                       beam_geometry, material_props, notes) + al_bot)
                notes.append("IMF §18.4.3.1: +Mn at joint face increased to >= 1/3 of -Mn.")

        top_bars = self._select_reinforcement_bars(As_top_req, beam_geometry, fy, pref_stirrup,
                                                   beam_geometry.aggregate_size)
        bot_bars = self._select_reinforcement_bars(As_bot_req, beam_geometry, fy, pref_stirrup,
                                                   beam_geometry.aggregate_size)

        As_top_prov = sum(self.aci.get_bar_area(b) for b in top_bars) if top_bars else 0.0
        As_bot_prov = sum(self.aci.get_bar_area(b) for b in bot_bars) if bot_bars else 0.0

        # ACI 318M-25 §18.6.3.1(b): SMF — at least 2 bars must be continuous along both faces
        # ACI 318M-25 §18.6.3.3: SMF — lap splice zone restrictions
        if beam_geometry.frame_system == FrameSystem.SPECIAL:
            n_top_smf = len(top_bars) if top_bars else 0
            n_bot_smf = len(bot_bars) if bot_bars else 0
            if n_top_smf >= 2 and n_bot_smf >= 2:
                notes.append(
                    f"SMF \u00a718.6.3.1(b): {n_top_smf} top bar(s) and {n_bot_smf} bottom bar(s) provided. "
                    "At least 2 must run continuously along both faces throughout the member length.")
            else:
                notes.append(
                    "SMF \u00a718.6.3.1(b) WARNING: Fewer than 2 bars on one or both faces. "
                    "At least 2 bars must be continuous along each face throughout the member length.")
            notes.append(
                "SMF \u00a718.6.3.3: Lap splices NOT permitted within joints, within 2h of joint faces, "
                "or at locations where flexural yielding is anticipated. "
                "Use Class B tension lap splices elsewhere, confined by transverse reinforcement "
                "per \u00a718.6.4 throughout the splice length.")

        # ACI 318M-25 §25.5.2.3: cb = cover to stirrup face + stirrup db + 0.5 × main bar db
        _, actual_st = self._parse_stirrup(pref_stirrup)
        db_st = self.aci.get_bar_diameter(actual_st)
        cb_top = beam_geometry.cover + db_st + 0.5 * self.aci.get_bar_diameter(top_bars[0] if top_bars else 'D20')
        cb_bot = beam_geometry.cover + db_st + 0.5 * self.aci.get_bar_diameter(bot_bars[0] if bot_bars else 'D20')
        ld_top = self.aci.calculate_development_length(top_bars[0] if top_bars else 'D20', fc_prime, fy,
                                                       {'top_bar': 1.3}, cb=cb_top)
        ld_bot = self.aci.calculate_development_length(bot_bars[0] if bot_bars else 'D20', fc_prime, fy, cb=cb_bot)

        design = ReinforcementDesign(
            top_bars=top_bars, top_area=As_top_prov,
            bottom_bars=bot_bars, bottom_area=As_bot_prov,
            stirrups='D10', stirrup_spacing=200.0,
            development_length_top=ld_top, development_length_bot=ld_bot
        )
        return design, notes

    def design_transverse_reinforcement(self, vu: float, tu: float, mpr_top: float, mpr_bot: float,
                                        gravity_shear: float,
                                        beam_geometry: BeamGeometry, material_props: MaterialProperties,
                                        main_reinforcement: ReinforcementDesign, pref_stirrup: str = 'D10') -> Tuple[
        str, float, float, float, float, List[str]]:
        notes = []
        fc_prime, fy, fyt = material_props.fc_prime, material_props.fy, material_props.fyt
        bw, d = beam_geometry.width, beam_geometry.effective_depth
        phi_v, phi_t = self.phi_factors['shear'], self.phi_factors['torsion']

        Vu, Tu, Ve = vu * 1000, tu * 1e6, vu * 1000
        if beam_geometry.frame_system == FrameSystem.SPECIAL and beam_geometry.clear_span > 0:
            # ACI 318M-25 §18.6.5.1: both sway directions (same cross-section assumed at both ends)
            Ve_sway = (mpr_top + mpr_bot) * 1e6 / beam_geometry.clear_span  # N
            Ve_pos = Ve_sway + gravity_shear * 1000   # sway producing max shear
            Ve_neg = abs(Ve_sway - gravity_shear * 1000)  # opposite sway
            Ve = max(Ve_pos, Ve_neg, Vu)
            notes.append(
                f"SMF §18.6.5.1: Ve = {Ve / 1000:.1f} kN (both sway dirs; "
                f"Mpr_top={mpr_top:.1f}, Mpr_bot={mpr_bot:.1f} kNm)")

        lambda_cc = material_props.lambda_factor  # ACI 318M-25 §19.2.4
        # Design-phase Vc: stirrups not yet selected, so we target Av ≥ Av,min (design goal).
        # This justifies using the simplified row of ACI 318M-25 Table 22.5.5.1: Vc = 0.17λ√f’c·bw·d.
        # Capacity checks after design use _calculate_vc() with the actual Av/s.
        Vc = 0.17 * lambda_cc * math.sqrt(fc_prime) * bw * d  # N, Table 22.5.5.1(a)
        if beam_geometry.frame_system == FrameSystem.SPECIAL and (Ve - gravity_shear * 1000) > 0.5 * Ve:
            Vc = 0.0
            notes.append("SMF Detailing: Vc = 0")

        Vs_req = max(0.0, (Ve / phi_v) - Vc)
        Av_over_s = Vs_req / (fyt * d)

        torsion_required = self.check_torsion_requirement(tu, beam_geometry, material_props)
        props = self._calculate_torsional_properties(beam_geometry, pref_stirrup)
        At_over_s, Al_req = 0.0, 0.0

        if torsion_required:
            combined_stress = math.sqrt((Ve / (bw * d)) ** 2 + ((Tu * props['ph']) / (1.7 * props['Aoh'] ** 2)) ** 2)
            # §22.5.3.1: cap √f'c at 8.3 MPa^0.5 in the Vs_max term of the crushing envelope
            stress_limit = phi_v * (0.17 * math.sqrt(fc_prime) + 0.66 * min(math.sqrt(fc_prime), 8.3))
            if combined_stress > stress_limit:
                notes.append(
                    f"CRITICAL: Section inadequate for combined shear/torsion crushing envelope. Increase dimensions.")

            theta = math.radians(45)
            At_over_s = Tu / (phi_t * 2 * props['Ao'] * fyt * (1 / math.tan(theta)))
            At_over_s_min = max(At_over_s, 0.175 * bw / fyt)
            Al_req = max(At_over_s * props['ph'] * (fyt / fy) * (1 / math.tan(theta)) ** 2,
                         (0.42 * math.sqrt(fc_prime) * props['Acp'] / fy) - (At_over_s_min * props['ph'] * (fyt / fy)),
                         0.0)

        min_transverse = max(0.062 * math.sqrt(fc_prime) * bw / fyt, 0.35 * bw / fyt)

        # Start looking for sizes explicitly at the user's preferred size, only upsizing if necessary
        all_sizes = ['D10', 'D12', 'D16', 'D20', 'D25', 'D28', 'D32', 'D36']
        start_idx = all_sizes.index(pref_stirrup) if pref_stirrup in all_sizes else 0
        sizes = all_sizes[start_idx:]
        # Minimum center-to-center leg pitch: actual main bar diameter
        # + minimum clear spacing per ACI 318M-25 §25.8.1
        _pref_main_bar = main_reinforcement.top_bars[0] if main_reinforcement.top_bars else 'D20'
        _agg_size = beam_geometry.aggregate_size
        _min_leg_pitch = self.aci.get_bar_diameter(_pref_main_bar) + max(25.0, (4.0 / 3.0) * _agg_size)
        max_legs = max(2, min(6, math.floor((bw - 2 * beam_geometry.cover) / _min_leg_pitch) + 1))
        # Minimum practical stirrup spacing: 3× maximum aggregate size per ACI 318M-25 §26.4.2.1
        min_s_practical = 3.0 * _agg_size

        best_size, best_legs, s_req, found = pref_stirrup, 2, float('inf'), False

        for size in sizes:
            A_bar = self.aci.get_bar_area(size)
            for n in range(2, max_legs + 1):
                denom = At_over_s + (Av_over_s / n)
                s_demand = A_bar / denom if denom > 0 else float('inf')
                s_calc = min(s_demand, (n * A_bar) / min_transverse if min_transverse > 0 else float('inf'))
                if s_calc >= min_s_practical:
                    best_size, best_legs, s_req, found = size, n, s_calc, True
                    break
            if found: break

        if not found:
            best_size, best_legs = pref_stirrup, max_legs
            denom = At_over_s + (Av_over_s / best_legs)
            s_req = self.aci.get_bar_area(best_size) / denom if denom > 0 else 50.0

        stirrup_size = f"{best_legs}-leg {best_size}" if best_legs > 2 else best_size

        Vs_actual = max(0.0, Ve / phi_v - Vc)
        s_span_max = min(d / 4, 300.0) if Vs_actual > (0.33 * math.sqrt(fc_prime) * bw * d) else min(d / 2, 600.0)
        if torsion_required: s_span_max = min(s_span_max, props['ph'] / 8, 300.0)

        _main_bar_hinge = main_reinforcement.top_bars[0] if main_reinforcement.top_bars else 'D20'
        _db_main_hinge = self.aci.get_bar_diameter(_main_bar_hinge)
        _, _stir_bar_hinge = self._parse_stirrup(stirrup_size)
        _db_stir_hinge = self.aci.get_bar_diameter(_stir_bar_hinge)
        if beam_geometry.frame_system == FrameSystem.SPECIAL:
            s_hinge_max = min(d / 4, 6 * _db_main_hinge, 150.0)  # ACI §18.6.4.3
        elif beam_geometry.frame_system == FrameSystem.INTERMEDIATE:
            s_hinge_max = min(d / 4, 8 * _db_main_hinge, 24 * _db_stir_hinge, 300.0)  # ACI §18.4.3.2
        else:
            s_hinge_max = s_span_max

        s_hinge_actual = math.floor(min(s_req, s_hinge_max) / 10) * 10
        s_span_actual = math.floor(min(s_req, s_span_max) / 10) * 10

        if beam_geometry.frame_system == FrameSystem.SPECIAL:
            # ACI 318M-25 §18.6.4.2: first hoop ≤ 50 mm from joint face
            notes.append(
                "SMF §18.6.4.2: Place first hoop \u2264 50 mm from the face of the joint "
                f"(confinement zone = {2 * beam_geometry.height:.0f} mm, s = {max(s_hinge_actual, 50.0):.0f} mm).")
            # ACI 318M-25 §18.6.4.1: transverse reinforcement in confinement zones must be closed hoops
            notes.append(
                "SMF §18.6.4.1: Confinement-zone stirrups must be CLOSED HOOPS with "
                "seismic hooks (135\u00b0 bend + 6d\u2090 extension) \u2014 open stirrups are NOT permitted.")
        elif beam_geometry.frame_system == FrameSystem.INTERMEDIATE:
            # ACI 318M-25 §18.4.3.2
            notes.append(
                f"IMF §18.4.3.2: Place first hoop \u2264 50 mm from the face of the joint "
                f"(confinement zone = {2 * beam_geometry.height:.0f} mm, s = {max(s_hinge_actual, 50.0):.0f} mm).")
            notes.append(
                "IMF §18.4.3.2: Confinement-zone stirrups must be closed hoops with seismic hooks.")

        return stirrup_size, max(s_hinge_actual, 50.0), max(s_span_actual, 50.0), Ve / 1000, Al_req, notes

    def _get_effective_width(self, beam_geometry: BeamGeometry) -> float:
        """Effective flange width for T/L-beam sections per ACI 318M-25 §6.3.2.
        Uses beam_geometry.flange_width as the pre-computed effective width."""
        if (beam_geometry.beam_type in (BeamType.T_BEAM, BeamType.L_BEAM, BeamType.INVERTED_T)
                and beam_geometry.flange_width > beam_geometry.width):
            return beam_geometry.flange_width
        return beam_geometry.width

    def _calculate_effective_ie(self, Ma_kNm: float, As_bot: float, beam_geometry: BeamGeometry,
                                material_props: MaterialProperties) -> float:
        """Effective moment of inertia Ie (mm⁴) per ACI 318M-25 §24.2.3.5 (Branson's formula)."""
        bw, h, d = beam_geometry.width, beam_geometry.height, beam_geometry.effective_depth
        Ec, Es = material_props.ec, material_props.es
        n = Es / Ec
        Ig = bw * h ** 3 / 12
        yt = h / 2
        fr = 0.62 * math.sqrt(material_props.fc_prime)  # ACI §19.2.3.1
        Mcr = fr * Ig / yt  # N·mm
        Ma = Ma_kNm * 1e6  # kNm → N·mm
        if Ma <= Mcr or As_bot <= 0.0:
            return Ig
        # Neutral axis depth of cracked transformed section
        a_c, b_c, c_c = bw / 2, n * As_bot, -n * As_bot * d
        kd = (-b_c + math.sqrt(b_c ** 2 - 4 * a_c * c_c)) / (2 * a_c)
        Icr = bw * kd ** 3 / 3 + n * As_bot * (d - kd) ** 2
        Ie = (Mcr / Ma) ** 3 * Ig + (1 - (Mcr / Ma) ** 3) * Icr
        return min(Ie, Ig)

    def _check_compression_steel_yields(self, As_prov: float, As_prime: float,
                                         beam_geometry: BeamGeometry,
                                         material_props: MaterialProperties,
                                         d_prime: float) -> Tuple[bool, float]:
        """Strain-compatibility check for compression steel.
        Returns (yields: bool, fs_prime: MPa) per ACI R9.6.3 / strain compatibility.
        εcu = 0.003; c computed from equilibrium of singly-reinforced equivalent section."""
        fc, fy, Es = material_props.fc_prime, material_props.fy, material_props.es
        beta1 = self.aci.calculate_beta1(fc)
        be = self._get_effective_width(beam_geometry)
        bw = beam_geometry.width
        # Use net tension steel for equilibrium (omit As_prime on compression side for first pass)
        As_net = max(As_prov - As_prime, 0.0)
        a = As_net * fy / (0.85 * fc * be)
        c = a / beta1
        if c <= 0:
            return True, fy
        eps_prime = 0.003 * (c - d_prime) / c
        fs_prime = min(eps_prime * Es, fy)
        return fs_prime >= fy, fs_prime

    def _calculate_moment_capacity(self, As_prov: float, beam_geometry: BeamGeometry,
                                   material_props: MaterialProperties,
                                   As_prime: float = 0.0, d_prime: float = 0.0) -> float:
        if As_prov <= 0.0: return 0.0
        be = self._get_effective_width(beam_geometry)
        bw, hf = beam_geometry.width, beam_geometry.flange_thickness
        d, fc, fy = beam_geometry.effective_depth, material_props.fc_prime, material_props.fy
        Es = material_props.es

        # Fix #11: actual compression-steel stress via strain compatibility
        if As_prime > 0.0 and d_prime > 0.0:
            _, fs_prime = self._check_compression_steel_yields(As_prov, As_prime, beam_geometry, material_props, d_prime)
        else:
            fs_prime = fy

        a = (As_prov * fy - As_prime * fs_prime) / (0.85 * fc * be)
        if be > bw and hf > 0 and a > hf:
            # T-section: compression block extends below flange into web
            Cf = 0.85 * fc * (be - bw) * hf
            Asw = max(As_prov - As_prime * (fs_prime / fy) - Cf / fy, 0.0)
            aw = Asw * fy / (0.85 * fc * bw)
            Mn = (Cf * (d - hf / 2)
                  + 0.85 * fc * bw * aw * (d - aw / 2)
                  + As_prime * fs_prime * (d - d_prime))
        else:
            a = max(a, 0.0)  # guard against negative when As_prime dominates
            Mn = As_prov * fy * (d - a / 2) - As_prime * fs_prime * (d_prime - a / 2)
        return max(0.0, Mn / 1e6)

    def _calculate_torsion_capacity(self, beam_geometry: BeamGeometry, material_props: MaterialProperties,
                                    stirrup_size: str, spacing: float, Ve: float, Vc: float) -> float:
        """Returns Tn (torsion nominal capacity) in kNm per ACI 318M-25 §22.7.
        Ve and Vc must be supplied in N; return value is in kNm.
        """
        if stirrup_size == 'None' or spacing <= 0: return 0.0
        _, actual_size = self._parse_stirrup(stirrup_size)
        props = self._calculate_torsional_properties(beam_geometry, actual_size)
        Tn_steel = (2 * props['Ao'] * self.aci.get_bar_area(actual_size) * material_props.fyt / spacing) / 1e6

        bw, d = beam_geometry.width, beam_geometry.effective_depth
        v_c_stress = Vc / (bw * d)
        # §22.5.3.1: cap √f'c at 8.3 MPa^0.5 for the Vs_max term in the crushing envelope
        max_shear_stress = v_c_stress + 0.66 * min(math.sqrt(material_props.fc_prime), 8.3)
        v_n_req = (Ve / self.phi_factors['shear']) / (bw * d)

        if v_n_req >= max_shear_stress:
            Tn_max_crush = 0.0
        else:
            t_n_max_stress = math.sqrt(max_shear_stress ** 2 - v_n_req ** 2)
            Tn_max_crush = (t_n_max_stress * 1.7 * props['Aoh'] ** 2 / props['ph']) / 1e6

        return min(Tn_steel, Tn_max_crush)

    def _calculate_shear_capacity(self, beam_geometry: BeamGeometry, material_props: MaterialProperties,
                                  stirrup_size: str, spacing: float, As_provided: float = 0.0) -> float:
        """Returns (Vc + Vs) in kN per ACI 318M-25 §22.5.
        Note: Vc computed in N internally; divided by 1000 → kN before return.
        """
        bw, d = beam_geometry.width, beam_geometry.effective_depth
        fc_prime, fyt = material_props.fc_prime, material_props.fyt
        lambda_cc = material_props.lambda_factor  # ACI 318M-25 §19.2.4
        # ACI 318M-25 Table 22.5.5.1: size effect factor (d in mm)
        lambda_s = min(1.0, math.sqrt(2.0 / (1.0 + 0.004 * d)))
        if stirrup_size != 'None' and spacing > 0:
            num_legs, actual_size = self._parse_stirrup(stirrup_size)
            Av_prov = num_legs * self.aci.get_bar_area(actual_size) / spacing  # mm²/mm
            Av_min = max(0.062 * math.sqrt(fc_prime) * bw / fyt, 0.35 * bw / fyt)  # mm²/mm
            if Av_prov >= Av_min:
                # ACI 318M-25 Table 22.5.5.1 (simplified, Av ≥ Av,min): no size effect on Vc
                Vc = 0.17 * lambda_cc * math.sqrt(fc_prime) * bw * d / 1000  # kN
            else:
                # ACI 318M-25 Table 22.5.5.1 (detailed, Av < Av,min): size effect applies
                rho_w = As_provided / (bw * d) if As_provided > 0.0 else 0.005
                Vc = 0.66 * lambda_s * lambda_cc * (rho_w ** (1.0 / 3.0)) * math.sqrt(fc_prime) * bw * d / 1000  # kN
            Vs = num_legs * self.aci.get_bar_area(actual_size) * fyt * d / spacing / 1000  # kN
            # §22.5.3.1: cap √f'c at 8.3 MPa^0.5 (≈ f'c = 69 MPa) for Vs upper limit
            Vs_max = 0.66 * min(math.sqrt(fc_prime), 8.3) * bw * d / 1000  # kN
            Vs = min(Vs, Vs_max)
        else:
            # No stirrups: ACI 318M-25 Table 22.5.5.1 detailed formula with size effect
            rho_w = As_provided / (bw * d) if As_provided > 0.0 else 0.005
            Vc = 0.66 * lambda_s * lambda_cc * (rho_w ** (1.0 / 3.0)) * math.sqrt(fc_prime) * bw * d / 1000  # kN
            Vs = 0.0
        return Vc + Vs

    def perform_complete_beam_design(self, mu_top: float, mu_bot: float, vu: float, beam_geometry: BeamGeometry,
                                     material_props: MaterialProperties, service_moment: float = None, tu: float = 0.0,
                                     gravity_shear: float = 0.0, is_support: bool = False, max_as_support: float = 0.0,
                                     pref_stirrup: str = 'D10', pref_torsion: str = 'D12') -> BeamAnalysisResult:
        design_notes = self.check_seismic_geometric_limits(beam_geometry)

        Al_req = self._calculate_torsional_longitudinal_reinforcement(tu, beam_geometry, material_props, pref_stirrup)
        Al_top, Al_bot, Al_side_total = 0.0, 0.0, 0.0
        side_layers = 0
        side_bars = []

        if Al_req > 0:
            props = self._calculate_torsional_properties(beam_geometry, pref_stirrup)
            x1, y1 = props['x1'], props['y1']
            spaces = math.ceil(y1 / 300.0)
            side_layers = max(0, spaces - 1)

            if side_layers > 0:
                Al_side_total = Al_req * (y1 / (x1 + y1))
                Al_top_bot_total = Al_req - Al_side_total
                Al_top = Al_bot = Al_top_bot_total / 2.0

                bar_area = self.aci.get_bar_area(pref_torsion)
                req_bars = math.ceil(Al_side_total / bar_area)

                if req_bars % 2 != 0: req_bars += 1
                req_bars = max(req_bars, side_layers * 2)

                side_bars = [pref_torsion] * req_bars
            else:
                Al_top = Al_bot = Al_req / 2.0

            design_notes.append(
                f"Torsion: Al distributed proportionally. Side bars: {len(side_bars)}x{pref_torsion} (Spacing <= 300mm).")

        flexural_design, flex_notes = self.design_flexural_reinforcement(mu_top, mu_bot, Al_top, Al_bot, beam_geometry,
                                                                         material_props, is_support, max_as_support,
                                                                         pref_stirrup)
        design_notes.extend(flex_notes)

        flexural_design.side_bars = side_bars
        flexural_design.side_area = sum(self.aci.get_bar_area(b) for b in side_bars) if side_bars else 0.0

        # Fix #12: Skin reinforcement per ACI 318M-25 §9.7.2.3 (h > 900 mm, independent of torsion)
        if beam_geometry.height > 900.0:
            _, actual_stir_skin = self._parse_stirrup(pref_stirrup)
            db_stir_skin = self.aci.get_bar_diameter(actual_stir_skin)
            # Inner face height between top/bot bar layers
            db_top_skin = self.aci.get_bar_diameter(flexural_design.top_bars[0] if flexural_design.top_bars else 'D16')
            db_bot_skin = self.aci.get_bar_diameter(flexural_design.bottom_bars[0] if flexural_design.bottom_bars else 'D16')
            d_top_face = beam_geometry.cover + db_stir_skin + 0.5 * db_top_skin
            d_bot_face = beam_geometry.cover + db_stir_skin + 0.5 * db_bot_skin
            inner_height = beam_geometry.height - d_top_face - d_bot_face
            # §9.7.2.3: spacing ≤ min(d/6, 300 mm)
            skin_spacing = min(beam_geometry.effective_depth / 6, 300.0)
            bars_per_face = max(1, math.ceil(inner_height / skin_spacing) - 1)
            # Minimum skin bar size: D12 per common practice; use pref_torsion bar if already skin
            skin_bar = 'D12'
            skin_As_face = bars_per_face * self.aci.get_bar_area(skin_bar)
            # Only add if not already covered by torsion side bars
            existing_side_area = flexural_design.side_area
            if existing_side_area < 2 * skin_As_face:  # both faces
                extra_bars_per_face = math.ceil(
                    (2 * skin_As_face - existing_side_area) / (2 * self.aci.get_bar_area(skin_bar)))
                extra_bars_per_face = max(extra_bars_per_face, bars_per_face)
                new_side_bars = [skin_bar] * (extra_bars_per_face * 2)
                flexural_design.side_bars = new_side_bars
                flexural_design.side_area = sum(self.aci.get_bar_area(b) for b in new_side_bars)
                design_notes.append(
                    f"Skin Reinf. §9.7.2.3: h = {beam_geometry.height:.0f} mm > 900 mm. "
                    f"Added {len(new_side_bars)}\u00d7{skin_bar} skin bars "
                    f"({extra_bars_per_face} per face, s \u2264 {skin_spacing:.0f} mm).")

        if beam_geometry.frame_system == FrameSystem.SPECIAL:
            _top_bar = flexural_design.top_bars[0] if flexural_design.top_bars else 'D20'
            _bot_bar = flexural_design.bottom_bars[0] if flexural_design.bottom_bars else 'D20'
            mpr_top = self.calculate_probable_moment_capacity(flexural_design.top_area, flexural_design.bottom_area,
                                                              beam_geometry, material_props,
                                                              flexural_design.stirrups, _top_bar)
            mpr_bot = self.calculate_probable_moment_capacity(flexural_design.bottom_area, flexural_design.top_area,
                                                              beam_geometry, material_props,
                                                              flexural_design.stirrups, _bot_bar)
        else:
            mpr_top, mpr_bot = 0.0, 0.0

        # ACI 318M-25 §18.8: Beam-column joint shear check (SMF only)
        joint_notes = self.check_joint_shear(
            flexural_design.top_area, flexural_design.bottom_area, beam_geometry, material_props)
        design_notes.extend(joint_notes)

        # Do not fabricate a gravity shear when it is not supplied — use 0.0 (conservative for
        # SMF: it minimises the subtracted term in Ve_neg, giving the pure-seismic upper bound).
        gravity_v = gravity_shear
        if gravity_shear == 0.0 and beam_geometry.frame_system == FrameSystem.SPECIAL:
            design_notes.append(
                "SMF §18.6.5.1: gravity_shear not provided (= 0). Ve computed from seismic sway only. "
                "Supply gravity_shear for a more accurate design-shear calculation.")

        stirrup_size, s_hinge, s_span, ve_design, _, trans_notes = self.design_transverse_reinforcement(
            vu, tu, mpr_top, mpr_bot, gravity_v,
            beam_geometry, material_props, flexural_design, pref_stirrup)
        design_notes.extend(trans_notes)

        # Fix 7: Recompute Al with the actual selected stirrup bar size.
        # Stirrup diameter affects Aoh, ph, Ao → refine At/s and Al after bar size is known.
        if Al_req > 0:
            _, actual_stir_bar = self._parse_stirrup(stirrup_size)
            Al_req = self._calculate_torsional_longitudinal_reinforcement(
                tu, beam_geometry, material_props, actual_stir_bar)

        flexural_design.stirrups = stirrup_size
        flexural_design.stirrup_spacing_hinge = s_hinge
        flexural_design.stirrup_spacing = s_span
        flexural_design.hinge_length = (2 * beam_geometry.height
                                         if beam_geometry.frame_system in (FrameSystem.SPECIAL, FrameSystem.INTERMEDIATE)
                                         else 0.0)
        flexural_design.torsion_required = Al_req > 0
        flexural_design.torsion_longitudinal_area = Al_req

        actual_s = s_hinge if is_support else s_span

        # Capacity-phase Vc: stirrups are known — use the full ACI 318M-25 Table 22.5.5.1 formula
        As_prov_max = max(flexural_design.top_area, flexural_design.bottom_area)
        Vc = self._calculate_vc(beam_geometry, material_props, stirrup_size, actual_s, As_prov_max,
                                material_props.lambda_factor)
        if beam_geometry.frame_system == FrameSystem.SPECIAL and (ve_design * 1000 - gravity_v * 1000) > 0.5 * (
                ve_design * 1000):
            Vc = 0.0

        phi_f, phi_v, phi_t = self.phi_factors['flexure_tension_controlled'], self.phi_factors['shear'], \
        self.phi_factors['torsion']

        # Fix #13: pass compression-steel As and d' for doubly-reinforced capacity (fix #11 wired up)
        _, _stir_cap = self._parse_stirrup(stirrup_size)
        _db_stir_cap = self.aci.get_bar_diameter(_stir_cap)
        _db_top_cap = self.aci.get_bar_diameter(flexural_design.top_bars[0] if flexural_design.top_bars else 'D16')
        _db_bot_cap = self.aci.get_bar_diameter(flexural_design.bottom_bars[0] if flexural_design.bottom_bars else 'D16')
        _d_prime_top = beam_geometry.cover + _db_stir_cap + 0.5 * _db_top_cap  # comp. face (top) to top bar
        _d_prime_bot = beam_geometry.cover + _db_stir_cap + 0.5 * _db_bot_cap  # comp. face (bot) to bot bar
        moment_capacity_top = phi_f * self._calculate_moment_capacity(
            flexural_design.top_area, beam_geometry, material_props,
            As_prime=flexural_design.bottom_area, d_prime=_d_prime_bot)  # negative Mn: bot bars in compression
        moment_capacity_bot = phi_f * self._calculate_moment_capacity(
            flexural_design.bottom_area, beam_geometry, material_props,
            As_prime=flexural_design.top_area, d_prime=_d_prime_top)   # positive Mn: top bars in compression
        shear_capacity = phi_v * self._calculate_shear_capacity(beam_geometry, material_props, stirrup_size, actual_s,
                                                                max(flexural_design.top_area, flexural_design.bottom_area))

        if flexural_design.torsion_required:
            tn_cap = phi_t * self._calculate_torsion_capacity(beam_geometry, material_props, stirrup_size, actual_s,
                                                              ve_design * 1000, Vc)
        else:
            tn_cap = 0.0

        util_m_top = mu_top / moment_capacity_top if moment_capacity_top > 0 else 1.0
        util_m_bot = mu_bot / moment_capacity_bot if moment_capacity_bot > 0 else 1.0
        util_v = ve_design / shear_capacity if shear_capacity > 0 else 1.0
        util_t = tu / tn_cap if (tn_cap > 0 and tu > 0) else 0.0

        # Deflection: effective moment of inertia (Branson) per ACI 318M-25 §24.2.3.5
        if service_moment:
            span = beam_geometry.clear_span if beam_geometry.clear_span > 0 else beam_geometry.length
            Ie = self._calculate_effective_ie(service_moment, flexural_design.bottom_area,
                                              beam_geometry, material_props)
            deflection = 5 * service_moment * 1e6 * span ** 2 / (48 * material_props.ec * Ie)  # mm
        else:
            deflection = 0.0

        # Crack control per ACI 318M-25 §24.3.2 — Frosch (1999) formula
        crack_width = 0.0
        if flexural_design.bottom_bars:
            fs_s = (2.0 / 3.0) * material_props.fy  # service steel stress per ACI §24.3.2
            db_main_bot = self.aci.get_bar_diameter(flexural_design.bottom_bars[0])
            _, actual_stir = self._parse_stirrup(flexural_design.stirrups)
            db_st = self.aci.get_bar_diameter(actual_stir)
            dc = beam_geometry.cover + db_st + 0.5 * db_main_bot  # depth to tension bar centroid
            n_bot = len(flexural_design.bottom_bars)
            avail_w = beam_geometry.width - 2 * beam_geometry.cover - 2 * db_st - n_bot * db_main_bot
            s_cc = (avail_w / (n_bot - 1) + db_main_bot) if n_bot > 1 else 0.0  # center-to-center spacing
            crack_width = 2 * (fs_s / material_props.es) * math.sqrt(dc ** 2 + (s_cc / 2) ** 2)  # mm
            s_max = min(380 * (280 / fs_s) - 2.5 * beam_geometry.cover, 300 * (280 / fs_s))
            if s_cc > s_max:
                design_notes.append(
                    f"Crack Control §24.3.2: Bar c/c spacing ({s_cc:.0f} mm) exceeds limit "
                    f"({s_max:.0f} mm) at fs = {fs_s:.0f} MPa. Reduce bar size or add bars.")

        return BeamAnalysisResult(
            moment_capacity_top=moment_capacity_top, moment_capacity_bot=moment_capacity_bot,
            probable_moment_top=mpr_top, probable_moment_bot=mpr_bot,
            shear_capacity=shear_capacity, capacity_shear_ve=ve_design, torsion_capacity=tn_cap,
            deflection=deflection, crack_width=crack_width, reinforcement=flexural_design,
            utilization_ratio=max(util_m_top, util_m_bot, util_v, util_t), design_notes=design_notes
        )

    def _select_reinforcement_bars(self, As_required: float, beam_geometry: BeamGeometry, fy: float,
                                   stirrup_size: str = 'D10', aggregate_size: float = 25.0) -> List[str]:
        if As_required <= 0: return []
        bar_data = [('D10', 78.54), ('D12', 113.10), ('D16', 201.06), ('D20', 314.16),
                    ('D25', 490.87), ('D28', 615.75), ('D32', 804.25), ('D36', 1017.88)]
        _, actual_stirrup = self._parse_stirrup(stirrup_size)
        available_width = beam_geometry.width - 2 * beam_geometry.cover - 2 * self.aci.get_bar_diameter(actual_stirrup)

        for bar_size, area in bar_data:
            num_bars = max(2, math.ceil(As_required / area))
            db = self.aci.get_bar_diameter(bar_size)
            min_clear_spacing = max(25.0, db, (4.0 / 3.0) * aggregate_size)
            max_bars_per_layer = math.floor((available_width + min_clear_spacing) / (db + min_clear_spacing))
            if max_bars_per_layer >= 2 and math.ceil(num_bars / max_bars_per_layer) <= 2:
                return [bar_size] * num_bars
        return [bar_data[-1][0]] * max(2, math.ceil(As_required / bar_data[-1][1]))