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

    def check_torsion_requirement(self, tu: float, beam_geometry: BeamGeometry,
                                  material_props: MaterialProperties) -> bool:
        if tu <= 0.0: return False
        props = self._calculate_torsional_properties(beam_geometry)
        Tth = 0.083 * math.sqrt(material_props.fc_prime) * (props['Acp'] ** 2 / props['pcp']) / 1e6
        return tu > (self.phi_factors['torsion'] * Tth)

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
                                           material_props: MaterialProperties) -> float:
        fc_prime, fy_pr = material_props.fc_prime, 1.25 * material_props.fy
        b, d, d_prime = beam_geometry.width, beam_geometry.effective_depth, beam_geometry.cover + 20.0
        a_net = (As * fy_pr - As_prime * fy_pr) / (0.85 * fc_prime * b)
        if a_net > 0:
            # Doubly-reinforced: compression steel yields, equilibrium holds
            return max(0.0, (As * fy_pr * (d - a_net / 2) + As_prime * fy_pr * (a_net / 2 - d_prime)) / 1e6)
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

    def _get_required_steel(self, mu: float, beam_geometry: BeamGeometry, material_props: MaterialProperties) -> float:
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
            return As_max * 1.5

        As_required = max((-B - math.sqrt(discriminant)) / (2 * A),
                          self.calculate_minimum_reinforcement_ratio(fc_prime, fy) * b * d)
        return As_required

    def design_flexural_reinforcement(self, mu_top: float, mu_bot: float, al_top: float, al_bot: float,
                                      beam_geometry: BeamGeometry, material_props: MaterialProperties,
                                      is_support: bool = False, max_as_support: float = 0.0,
                                      pref_stirrup: str = 'D10') -> Tuple[ReinforcementDesign, List[str]]:
        notes = []
        fc_prime, fy = material_props.fc_prime, material_props.fy

        As_top_req = self._get_required_steel(mu_top, beam_geometry, material_props) + al_top
        As_bot_req = self._get_required_steel(mu_bot, beam_geometry, material_props) + al_bot

        if beam_geometry.frame_system == FrameSystem.SPECIAL:
            if is_support and As_bot_req < 0.5 * As_top_req:
                As_bot_req = 0.5 * As_top_req
                notes.append("SMF 18.6.3.2: +Mn at joint face increased to >= 50% of -Mn.")

            if max_as_support > 0:
                min_quarter = 0.25 * max_as_support
                if As_top_req < min_quarter:
                    As_top_req = min_quarter
                    notes.append("SMF 18.6.3.2: -Mn increased to >= 25% of max joint face moment.")
                if As_bot_req < min_quarter:
                    As_bot_req = min_quarter
                    notes.append("SMF 18.6.3.2: +Mn increased to >= 25% of max joint face moment.")

        top_bars = self._select_reinforcement_bars(As_top_req, beam_geometry, fy, pref_stirrup)
        bot_bars = self._select_reinforcement_bars(As_bot_req, beam_geometry, fy, pref_stirrup)

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

        Vc = 0.17 * math.sqrt(fc_prime) * bw * d
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
        max_legs = max(2, min(6, math.floor((bw - 2 * beam_geometry.cover) / 80) + 1))

        best_size, best_legs, s_req, found = pref_stirrup, 2, float('inf'), False

        for size in sizes:
            A_bar = self.aci.get_bar_area(size)
            for n in range(2, max_legs + 1):
                denom = At_over_s + (Av_over_s / n)
                s_demand = A_bar / denom if denom > 0 else float('inf')
                s_calc = min(s_demand, (n * A_bar) / min_transverse if min_transverse > 0 else float('inf'))
                if s_calc >= 75.0:
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
                                  stirrup_size: str, spacing: float) -> float:
        bw, d = beam_geometry.width, beam_geometry.effective_depth
        Vc = 0.17 * math.sqrt(material_props.fc_prime) * bw * d / 1000
        if stirrup_size != 'None' and spacing > 0:
            num_legs, actual_size = self._parse_stirrup(stirrup_size)
            Vs = num_legs * self.aci.get_bar_area(actual_size) * material_props.fyt * d / spacing / 1000
            Vs_max = 0.66 * math.sqrt(material_props.fc_prime) * bw * d / 1000
            Vs = min(Vs, Vs_max)
        else:
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
            mpr_top = self.calculate_probable_moment_capacity(flexural_design.top_area, flexural_design.bottom_area,
                                                              beam_geometry, material_props)
            mpr_bot = self.calculate_probable_moment_capacity(flexural_design.bottom_area, flexural_design.top_area,
                                                              beam_geometry, material_props)
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

        Vc = 0.17 * math.sqrt(material_props.fc_prime) * beam_geometry.width * beam_geometry.effective_depth
        if beam_geometry.frame_system == FrameSystem.SPECIAL and (ve_design * 1000 - gravity_v * 1000) > 0.5 * (
                ve_design * 1000):
            Vc = 0.0

        phi_f, phi_v, phi_t = self.phi_factors['flexure_tension_controlled'], self.phi_factors['shear'], \
        self.phi_factors['torsion']

        moment_capacity_top = phi_f * self._calculate_moment_capacity(flexural_design.top_area, beam_geometry,
                                                                      material_props)
        moment_capacity_bot = phi_f * self._calculate_moment_capacity(flexural_design.bottom_area, beam_geometry,
                                                                      material_props)
        shear_capacity = phi_v * self._calculate_shear_capacity(beam_geometry, material_props, stirrup_size, actual_s)

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