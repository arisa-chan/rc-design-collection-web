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


class LoadType(Enum):
    POINT_LOAD = "point_load"
    UNIFORMLY_DISTRIBUTED = "uniformly_distributed"
    TRIANGULAR = "triangular"
    TRAPEZOIDAL = "trapezoidal"


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
        return warnings

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
            # Doubly-reinforced: compression steel yields, equilibrium holds
            return max(0.0, (As * fy_pr * (d - a_net / 2) + As_prime * fy_pr * (d - d_prime)) / 1e6)
        else:
            # As < As': net compression block is negative, use singly-reinforced
            a = As * fy_pr / (0.85 * fc_prime * b)
            return max(0.0, As * fy_pr * (d - a / 2) / 1e6)

    def calculate_minimum_reinforcement_ratio(self, fc_prime: float, fy: float) -> float:
        return max(1.4 / fy, 0.25 * math.sqrt(fc_prime) / fy)

    def calculate_maximum_reinforcement_ratio(self, fc_prime: float, fy: float, beam_geometry: BeamGeometry) -> float:
        beta1 = self._calculate_beta1(fc_prime)
        rho_max = 3 / 8 * 0.85 * fc_prime * beta1 / fy
        return min(rho_max, 0.025) if beam_geometry.frame_system == FrameSystem.SPECIAL else rho_max

    def _get_required_steel(self, mu: float, beam_geometry: BeamGeometry, material_props: MaterialProperties,
                            notes: List[str] = None) -> float:
        if mu <= 0.0:
            return self.calculate_minimum_reinforcement_ratio(material_props.fc_prime,
                                                              material_props.fy) * beam_geometry.width * beam_geometry.effective_depth

        fc_prime, fy = material_props.fc_prime, material_props.fy
        b, d, Mu = beam_geometry.width, beam_geometry.effective_depth, mu * 1e6
        phi = self.phi_factors['flexure_tension_controlled']

        A, B, C = phi * fy ** 2 / (2 * 0.85 * fc_prime * b), -phi * fy * d, Mu
        discriminant = B ** 2 - 4 * A * C

        if discriminant < 0:
            As_max = self.calculate_maximum_reinforcement_ratio(fc_prime, fy, beam_geometry) * b * d
            if notes is not None:
                notes.append(
                    f"WARNING: Section too small for tension-controlled behavior at Mu = {mu:.1f} kNm. "
                    f"Increase beam dimensions. Design uses maximum reinforcement ratio as a lower bound.")
            return As_max

        As_required = max((-B - math.sqrt(discriminant)) / (2 * A),
                          self.calculate_minimum_reinforcement_ratio(fc_prime, fy) * b * d)
        return As_required

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

        top_bars = self._select_reinforcement_bars(As_top_req, beam_geometry, fy, pref_stirrup,
                                                   beam_geometry.aggregate_size)
        bot_bars = self._select_reinforcement_bars(As_bot_req, beam_geometry, fy, pref_stirrup,
                                                   beam_geometry.aggregate_size)

        As_top_prov = sum(self.aci.get_bar_area(b) for b in top_bars) if top_bars else 0.0
        As_bot_prov = sum(self.aci.get_bar_area(b) for b in bot_bars) if bot_bars else 0.0

        ld_top = self.aci.calculate_development_length(top_bars[0] if top_bars else 'D20', fc_prime, fy,
                                                       {'top_bar': 1.3})
        ld_bot = self.aci.calculate_development_length(bot_bars[0] if bot_bars else 'D20', fc_prime, fy)

        design = ReinforcementDesign(
            top_bars=top_bars, top_area=As_top_prov,
            bottom_bars=bot_bars, bottom_area=As_bot_prov,
            stirrups='D10', stirrup_spacing=200.0,
            development_length_top=ld_top, development_length_bot=ld_bot
        )
        return design, notes

    # FIX: Pass pref_stirrup to strictly enforce user sizing where possible
    def design_transverse_reinforcement(self, vu: float, tu: float, mpr: float, gravity_shear: float,
                                        beam_geometry: BeamGeometry, material_props: MaterialProperties,
                                        main_reinforcement: ReinforcementDesign, pref_stirrup: str = 'D10') -> Tuple[
        str, float, float, float, float, float, List[str]]:
        notes = []
        fc_prime, fy, fyt = material_props.fc_prime, material_props.fy, material_props.fyt
        bw, d = beam_geometry.width, beam_geometry.effective_depth
        phi_v, phi_t = self.phi_factors['shear'], self.phi_factors['torsion']

        Vu, Tu, Ve = vu * 1000, tu * 1e6, vu * 1000
        if beam_geometry.frame_system == FrameSystem.SPECIAL and beam_geometry.clear_span > 0:
            Ve = max((gravity_shear * 1000) + ((2 * mpr * 1e6) / beam_geometry.clear_span), Vu)
            notes.append(f"SMF Capacity Design: Seismic shear Ve = {Ve / 1000:.1f} kN")

        lambda_cc = 1.0  # ACI 318M-25 §19.2.4: λ = 1.0 for normal-weight concrete (conservative default)
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
            stress_limit = phi_v * ((0.17 * math.sqrt(fc_prime)) + 0.66 * math.sqrt(fc_prime))
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

        s_hinge_max = min(d / 4, 6 * self.aci.get_bar_diameter(
            main_reinforcement.top_bars[0] if main_reinforcement.top_bars else 'D20'),
                          150.0) if beam_geometry.frame_system == FrameSystem.SPECIAL else s_span_max

        s_hinge_actual = math.floor(min(s_req, s_hinge_max) / 10) * 10
        s_span_actual = math.floor(min(s_req, s_span_max) / 10) * 10

        return stirrup_size, max(s_hinge_actual, 50.0), max(s_span_actual, 50.0), Ve / 1000, Al_req, 0.0, notes

    def _calculate_moment_capacity(self, As_prov: float, beam_geometry: BeamGeometry,
                                   material_props: MaterialProperties) -> float:
        if As_prov <= 0.0: return 0.0
        a = As_prov * material_props.fy / (0.85 * material_props.fc_prime * beam_geometry.width)
        return max(0.0, As_prov * material_props.fy * (beam_geometry.effective_depth - a / 2) / 1e6)

    def _calculate_torsion_capacity(self, beam_geometry: BeamGeometry, material_props: MaterialProperties,
                                    stirrup_size: str, spacing: float, Ve: float, Vc: float) -> float:
        if stirrup_size == 'None' or spacing <= 0: return 0.0
        _, actual_size = self._parse_stirrup(stirrup_size)
        props = self._calculate_torsional_properties(beam_geometry, actual_size)
        Tn_steel = (2 * props['Ao'] * self.aci.get_bar_area(actual_size) * material_props.fyt / spacing) / 1e6

        bw, d = beam_geometry.width, beam_geometry.effective_depth
        v_c_stress = Vc / (bw * d)
        max_shear_stress = v_c_stress + 0.66 * math.sqrt(material_props.fc_prime)
        v_n_req = (Ve / self.phi_factors['shear']) / (bw * d)

        if v_n_req >= max_shear_stress:
            Tn_max_crush = 0.0
        else:
            t_n_max_stress = math.sqrt(max_shear_stress ** 2 - v_n_req ** 2)
            Tn_max_crush = (t_n_max_stress * 1.7 * props['Aoh'] ** 2 / props['ph']) / 1e6

        return min(Tn_steel, Tn_max_crush)

    def _calculate_shear_capacity(self, beam_geometry: BeamGeometry, material_props: MaterialProperties,
                                  stirrup_size: str, spacing: float, As_provided: float = 0.0) -> float:
        bw, d = beam_geometry.width, beam_geometry.effective_depth
        fc_prime, fyt = material_props.fc_prime, material_props.fyt
        lambda_cc = 1.0  # ACI 318M-25 §19.2.4: λ = 1.0 for normal-weight concrete (conservative default)
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
            Vs_max = 0.66 * math.sqrt(fc_prime) * bw * d / 1000
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

        if beam_geometry.frame_system == FrameSystem.SPECIAL:
            _top_bar = flexural_design.top_bars[0] if flexural_design.top_bars else 'D20'
            _bot_bar = flexural_design.bottom_bars[0] if flexural_design.bottom_bars else 'D20'
            mpr_top = self.calculate_probable_moment_capacity(flexural_design.top_area, flexural_design.bottom_area,
                                                              beam_geometry, material_props,
                                                              flexural_design.stirrups, _top_bar)
            mpr_bot = self.calculate_probable_moment_capacity(flexural_design.bottom_area, flexural_design.top_area,
                                                              beam_geometry, material_props,
                                                              flexural_design.stirrups, _bot_bar)
            mpr_avg = (mpr_top + mpr_bot) / 2.0
        else:
            mpr_top, mpr_bot, mpr_avg = 0.0, 0.0, 0.0

        gravity_v = gravity_shear if gravity_shear > 0 else vu * 0.5

        # FIX: Explicitly pass pref_stirrup into the transverse design method
        stirrup_size, s_hinge, s_span, ve_design, al_req, _, trans_notes = self.design_transverse_reinforcement(vu, tu,
                                                                                                                mpr_avg,
                                                                                                                gravity_v,
                                                                                                                beam_geometry,
                                                                                                                material_props,
                                                                                                                flexural_design,
                                                                                                                pref_stirrup)
        design_notes.extend(trans_notes)

        flexural_design.stirrups = stirrup_size
        flexural_design.stirrup_spacing_hinge = s_hinge
        flexural_design.stirrup_spacing = s_span
        flexural_design.hinge_length = 2 * beam_geometry.height if beam_geometry.frame_system == FrameSystem.SPECIAL else 0.0
        flexural_design.torsion_required = Al_req > 0
        flexural_design.torsion_longitudinal_area = Al_req

        actual_s = s_hinge if is_support else s_span

        # Capacity-phase Vc: stirrups are known — use the full ACI 318M-25 Table 22.5.5.1 formula
        As_prov_max = max(flexural_design.top_area, flexural_design.bottom_area)
        Vc = self._calculate_vc(beam_geometry, material_props, stirrup_size, actual_s, As_prov_max)
        if beam_geometry.frame_system == FrameSystem.SPECIAL and (ve_design * 1000 - gravity_v * 1000) > 0.5 * (
                ve_design * 1000):
            Vc = 0.0

        phi_f, phi_v, phi_t = self.phi_factors['flexure_tension_controlled'], self.phi_factors['shear'], \
        self.phi_factors['torsion']

        moment_capacity_top = phi_f * self._calculate_moment_capacity(flexural_design.top_area, beam_geometry,
                                                                      material_props)
        moment_capacity_bot = phi_f * self._calculate_moment_capacity(flexural_design.bottom_area, beam_geometry,
                                                                      material_props)
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

        deflection = (5 * service_moment * 1e6 * beam_geometry.length ** 2) / (48 * material_props.ec * (
                    beam_geometry.width * beam_geometry.height ** 3 / 12)) if service_moment else 0.0

        return BeamAnalysisResult(
            moment_capacity_top=moment_capacity_top, moment_capacity_bot=moment_capacity_bot,
            probable_moment_top=mpr_top, probable_moment_bot=mpr_bot,
            shear_capacity=shear_capacity, capacity_shear_ve=ve_design, torsion_capacity=tn_cap,
            deflection=deflection, crack_width=0.0, reinforcement=flexural_design,
            utilization_ratio=max(util_m_top, util_m_bot, util_v, util_t), design_notes=design_notes
        )

    def _calculate_beta1(self, fc_prime: float) -> float:
        if fc_prime <= 28.0:
            return 0.85
        elif fc_prime <= 55.0:
            return 0.85 - 0.05 * (fc_prime - 28.0) / 7.0
        else:
            return 0.65

    def _select_reinforcement_bars(self, As_required: float, beam_geometry: BeamGeometry, fy: float,
                                   stirrup_size: str = 'D10', aggregate_size: float = 25.0) -> List[str]:
        if As_required <= 0: return []
        bar_data = [('D16', 201.06), ('D20', 314.16), ('D25', 490.87), ('D28', 615.75), ('D32', 804.25),
                    ('D36', 1017.88)]
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