# -*- coding: utf-8 -*-

"""
ACI 318M-25 Prestressed Concrete Design Library
Building Code Requirements for Structural Concrete - Prestress Design
Supports pretensioned/posttensioned, multi-span beams and slabs
Includes ASTM A416, A722, A421 materials.
"""

import math
import numpy as np
from typing import Dict, Tuple, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from aci318m25 import ACI318M25, MaterialProperties, StructuralElement


class PrestressingMethod(Enum):
    PRETENSIONED = "pretensioned"
    POSTTENSIONED_BONDED = "posttensioned_bonded"
    POSTTENSIONED_UNBONDED = "posttensioned_unbonded"


class PrestressMaterialType(Enum):
    ASTM_A416_STRAND = "astm_a416_strand"
    ASTM_A722_BAR = "astm_a722_bar"
    ASTM_A421_WIRE = "astm_a421_wire"


class PrestressMemberType(Enum):
    BEAM = "beam"
    SLAB = "slab"


@dataclass
class PrestressTendon:
    material_type: PrestressMaterialType
    diameter: float
    area: float
    fpu: float  # Ultimate tensile strength (MPa)
    fpy: float  # Yield strength (MPa)
    number_of_tendons: int
    eccentricity: float  # Distance from centroid (positive = down)
    slip: float = 6.0  # Anchorage slip (mm)
    friction_mu: float = 0.0  # Curvature friction coefficient
    friction_k: float = 0.0  # Wobble friction coefficient (1/m; standard PTI/AASHTO tables)
    jacking_force: float = 0.0 # Initial jacking force per tendon (kN). If <= 0, uses 0.75 fpu.
    time_loss_mpa: float = 0.0 # Time-dependent loss approximation (MPa)
    
    @property
    def total_area(self) -> float:
        return self.area * self.number_of_tendons


@dataclass
class SpanGeometry:
    length: float
    width: float  # For slab, usually 1000mm strip
    height: float
    t_flange_width: float = 0.0
    t_flange_height: float = 0.0
    area: float = 0.0
    moment_of_inertia: float = 0.0
    yt: float = 0.0  # Distance from centroid to top fiber
    yb: float = 0.0  # Distance from centroid to bottom fiber
    
    def __post_init__(self):
        # Auto-calculate section properties for rectangular shape if not overridden
        if self.area == 0.0:
            if self.t_flange_width > 0 and self.t_flange_height > 0:
                bw, hw = self.width, self.height - self.t_flange_height
                bf, hf = self.t_flange_width, self.t_flange_height
                self.area = bw * hw + bf * hf
                y_bottom = ((bw * hw * (hw / 2)) + (bf * hf * (hw + hf / 2))) / self.area
                self.yb = y_bottom
                self.yt = self.height - y_bottom
                self.moment_of_inertia = (bw * hw**3 / 12 + bw * hw * (y_bottom - hw / 2)**2) + \
                                         (bf * hf**3 / 12 + bf * hf * (hw + hf / 2 - y_bottom)**2)
            else:
                self.area = self.width * self.height
                self.yb = self.height / 2.0
                self.yt = self.height / 2.0
                self.moment_of_inertia = (self.width * self.height**3) / 12.0


@dataclass
class PrestressLoads:
    dead_load: float  # kN/m
    live_load: float  # kN/m
    superimposed_dl: float = 0.0  # kN/m


@dataclass
class PrestressAnalysisResult:
    # Core outputs from evaluate_span
    span_index: int
    initial_stress_top: float
    initial_stress_bot: float
    service_stress_top: float
    service_stress_bot: float
    fpi: float  # Initial tendon stress
    fpe: float  # Effective tendon stress
    fps: float  # Stress at nominal flexural strength
    moment_capacity: float
    cracking_moment: float
    deflection_initial: float
    deflection_final: float
    loss_total_percentage: float
    design_notes: List[str]

    # Extended outputs from run_continuous_analysis
    phi_Vn: float = 0.0
    Vu: float = 0.0
    Mu_max: float = 0.0
    allowable_deflection: float = 0.0
    Tu: float = 0.0
    phi_Tn: float = 0.001
    Mu_left: float = 0.0
    Mu_mid: float = 0.0
    Mu_right: float = 0.0
    Vu_left: float = 0.0
    Vu_mid: float = 0.0
    Vu_right: float = 0.0
    Tu_left: float = 0.0
    Tu_mid: float = 0.0
    Tu_right: float = 0.0
    left_st_i: float = 0.0
    mid_st_i: float = 0.0
    right_st_i: float = 0.0
    left_sb_i: float = 0.0
    mid_sb_i: float = 0.0
    right_sb_i: float = 0.0
    left_st_s: float = 0.0
    mid_st_s: float = 0.0
    right_st_s: float = 0.0
    left_sb_s: float = 0.0
    mid_sb_s: float = 0.0
    right_sb_s: float = 0.0
    dcr_flexure_left: float = 0.0
    dcr_flexure_mid: float = 0.0
    dcr_flexure_right: float = 0.0
    dcr_shear_left: float = 0.0
    dcr_shear_mid: float = 0.0
    dcr_shear_right: float = 0.0
    dcr_torsion_left: float = 0.0
    dcr_torsion_mid: float = 0.0
    dcr_torsion_right: float = 0.0
    dcr_comb_left: float = 0.0
    dcr_comb_mid: float = 0.0
    dcr_comb_right: float = 0.0
    dcr_deflect_left: float = 0.0
    dcr_deflect_mid: float = 0.0
    dcr_deflect_right: float = 0.0
    utilization_ratio: float = 0.0


class ACI318M25PrestressDesign:
    def __init__(self):
        self.aci = ACI318M25()
        self.phi_factors = {
            'flexure_tension_controlled': 0.90,
            'shear': 0.75,
            'compression_tied': 0.65
        }
        
        # ASTM A416 Low-Relaxation Seven-Wire Strand (Grade 250 & 270)
        self.a416_strands = {
            # Grade 270 mostly
            '9.53': {'diameter': 9.53, 'area': 54.8, 'fpu': 1860, 'fpy': 1674, 'description': '3/8 in'},
            '11.11': {'diameter': 11.11, 'area': 74.2, 'fpu': 1860, 'fpy': 1674, 'description': '7/16 in'},
            '12.70': {'diameter': 12.70, 'area': 98.7, 'fpu': 1860, 'fpy': 1674, 'description': '1/2 in'},
            '15.24': {'diameter': 15.24, 'area': 140.0, 'fpu': 1860, 'fpy': 1674, 'description': '0.6 in'},
            '17.78': {'diameter': 17.78, 'area': 206.0, 'fpu': 1860, 'fpy': 1674, 'description': '0.7 in'}
        }
        
        # ASTM A722 High-Strength Steel Bar (Type II/150 ksi)
        self.a722_bars = {
            '19': {'diameter': 19.0, 'area': 284, 'fpu': 1035, 'fpy': 828, 'description': '#6'},
            '22': {'diameter': 22.0, 'area': 387, 'fpu': 1035, 'fpy': 828, 'description': '#7'},
            '25': {'diameter': 25.0, 'area': 516, 'fpu': 1035, 'fpy': 828, 'description': '#8'},
            '29': {'diameter': 29.0, 'area': 645, 'fpu': 1035, 'fpy': 828, 'description': '#9'},
            '32': {'diameter': 32.0, 'area': 806, 'fpu': 1035, 'fpy': 828, 'description': '#10'},
            '36': {'diameter': 36.0, 'area': 1032, 'fpu': 1035, 'fpy': 828, 'description': '#11'},
            '40': {'diameter': 40.0, 'area': 1258, 'fpu': 1035, 'fpy': 828, 'description': '#12'},
            '46': {'diameter': 46.0, 'area': 1613, 'fpu': 1035, 'fpy': 828, 'description': '#14'},
            '65': {'diameter': 65.0, 'area': 3331, 'fpu': 1035, 'fpy': 828, 'description': '2-1/2 in'},
            '75': {'diameter': 75.0, 'area': 4419, 'fpu': 1035, 'fpy': 828, 'description': '3 in'}
        }
        
        # ASTM A421 Uncoated Stress-Relieved Wire (Type WA/BA)
        self.a421_wires = {
            '4.88': {'diameter': 4.88, 'area': 18.7, 'fpu': 1725, 'fpy': 1466, 'description': '0.192 in (WA/BA)'},
            '4.98': {'diameter': 4.98, 'area': 19.5, 'fpu': 1725, 'fpy': 1466, 'description': '0.196 in (WA/BA)'},
            '6.35': {'diameter': 6.35, 'area': 31.7, 'fpu': 1655, 'fpy': 1406, 'description': '0.250 in (WA/BA)'},
            '7.01': {'diameter': 7.01, 'area': 38.6, 'fpu': 1620, 'fpy': 1377, 'description': '0.276 in (WA/BA)'}
        }

    def get_prestress_material(self, mat_type: PrestressMaterialType, diameter: str) -> Dict:
        if mat_type == PrestressMaterialType.ASTM_A416_STRAND:
            return self.a416_strands.get(diameter, {})
        elif mat_type == PrestressMaterialType.ASTM_A722_BAR:
            return self.a722_bars.get(diameter, {})
        elif mat_type == PrestressMaterialType.ASTM_A421_WIRE:
            return self.a421_wires.get(diameter, {})
        return {}

    def get_permissible_stresses(self, fc_prime: float, fci_prime: float) -> tuple:
        """ACI 318M-25 permissible stresses in concrete"""
        # Initial stage (transfer)
        f_ci_comp_end = 0.70 * fci_prime
        f_ci_comp_other = 0.60 * fci_prime
        f_ti_tension_end = 0.50 * math.sqrt(fci_prime)
        f_ti_tension_other = 0.25 * math.sqrt(fci_prime)
        
        # Service stage
        f_c_comp_sustained = 0.45 * fc_prime
        f_c_comp_total = 0.60 * fc_prime
        # Class U (Uncracked) tension limit
        f_t_tension_u = 0.62 * math.sqrt(fc_prime)
        # Class T (Transition) tension limit
        f_t_tension_t = 1.0 * math.sqrt(fc_prime)
        
        return (f_ci_comp_end, f_ci_comp_other, f_ti_tension_end, f_ti_tension_other,
                f_c_comp_sustained, f_c_comp_total, f_t_tension_u, f_t_tension_t)
                
    def get_tendon_stress_limits(self, fpu: float, fpy: float, method: PrestressingMethod) -> tuple:
        """ACI 318M-25 Table 20.3.2.5.1 Prestressing steel stress limits"""
        # Due to jacking force — same limit for all methods per Table 20.3.2.5.1
        fpj_limit = min(0.94 * fpy, 0.80 * fpu)

        # Immediately after transfer
        if method in (PrestressingMethod.POSTTENSIONED_BONDED, PrestressingMethod.POSTTENSIONED_UNBONDED):
            fpi_limit = min(0.82 * fpy, 0.70 * fpu)
        else:  # pretensioned
            fpi_limit = min(0.82 * fpy, 0.74 * fpu)

        return fpj_limit, fpi_limit

    def calculate_continuous_moments(self, spans: List[SpanGeometry], loads: List[PrestressLoads]) -> List[Tuple[float, float, float]]:
        """
        Simplified moment calculation for multi-span continuous beams/slabs.
        Returns a list of (M_left, M_mid, M_right) for each span.
        This uses an approximate method for continuous spans.
        """
        num_spans = len(spans)
        moments = []
        for i in range(num_spans):
            L = spans[i].length / 1000.0  # m
            w_total = loads[i].dead_load + loads[i].superimposed_dl + loads[i].live_load
            
            # Simple assumption: wl^2 / 10 for negative moments, wl^2 / 12 for positive (approx ACI coefficients)
            if num_spans == 1:
                M_pos = (w_total * L**2) / 8.0
                moments.append((0.0, M_pos, 0.0))
            else:
                if i == 0:
                    M_pos = (w_total * L**2) / 11.0
                    M_right = -(w_total * L**2) / 10.0
                    moments.append((0.0, M_pos, M_right))
                elif i == num_spans - 1:
                    M_pos = (w_total * L**2) / 11.0
                    M_left = -(w_total * L**2) / 10.0
                    moments.append((M_left, M_pos, 0.0))
                else:
                    M_pos = (w_total * L**2) / 16.0
                    M_left = -(w_total * L**2) / 11.0
                    M_right = -(w_total * L**2) / 11.0
                    moments.append((M_left, M_pos, M_right))
        return moments

    def calculate_losses(self, method: PrestressingMethod, tendon: PrestressTendon, span: SpanGeometry,
                         material_props: MaterialProperties, fpi: float,
                         mg_nmm: float = 0.0) -> Tuple[float, float, Dict]:
        """Simplified lump sum losses combined with initial immediate losses"""
        loss_details = {}

        # Elastic shortening — fcgp per ACI R20.3.5.4
        # fcgp = Pi/Ag + Pi*e²/Ig - Mg*e/Ig  (self-weight moment reduces stress at tendon level)
        P_initial = tendon.total_area * fpi
        e = tendon.eccentricity
        fc_cir = (P_initial / span.area
                  + (P_initial * e ** 2) / span.moment_of_inertia
                  - (mg_nmm * e) / span.moment_of_inertia)
        
        if method == PrestressingMethod.PRETENSIONED:
            n_ratio = material_props.es / material_props.ec
            delta_fp_es = n_ratio * fc_cir
        else:
            # Post-tensioned elastic shortening varies, typically taken as half of pretensioned for sequential
            n_ratio = material_props.es / material_props.ec
            delta_fp_es = 0.5 * n_ratio * fc_cir
            
        loss_details['elastic_shortening'] = delta_fp_es
        
        # Time-dependent losses (Creep, Shrinkage, Relaxation) - Simplified ACI/PCI approach
        # Typical lump-sum approximations
        delta_fp_time = 0.0
        if tendon.time_loss_mpa and tendon.time_loss_mpa > 0:
            delta_fp_time = tendon.time_loss_mpa
        elif method == PrestressingMethod.PRETENSIONED:
            delta_fp_time = 240.0  # approximate MPa
        else:
            delta_fp_time = 205.0  # approximate MPa
            
        loss_details['time_dependent'] = delta_fp_time
        
        # Anchorage slip and friction for Post-Tensioned
        delta_fp_anc = 0.0
        delta_fp_friction = 0.0
        if method in [PrestressingMethod.POSTTENSIONED_BONDED, PrestressingMethod.POSTTENSIONED_UNBONDED]:
            # delta_fp_anc = (tendon.slip / span.length) * material_props.es
            delta_fp_anc = (tendon.slip / (span.length)) * material_props.es  # Length should be in mm for consistent slip in mm
            
            # Simplified immediate friction at midspan L/2
            # friction_k is in 1/m; span.length is in mm → convert: k[1/mm] = k[1/m] / 1000
            alpha = 8 * tendon.eccentricity / span.length  # approximate curvature angle (rad)
            px = fpi * (tendon.friction_mu * alpha + (tendon.friction_k / 1000.0) * (span.length / 2))
            delta_fp_friction = px
            
        loss_details['anchorage'] = delta_fp_anc
        loss_details['friction'] = delta_fp_friction
        
        total_loss = delta_fp_es + delta_fp_time + delta_fp_anc + delta_fp_friction
        fpe = fpi - total_loss
        loss_percentage = (total_loss / fpi) * 100
        
        return fpe, loss_percentage, loss_details

    def evaluate_span(self, span_index: int, span: SpanGeometry, loads: PrestressLoads,
                      tendon: PrestressTendon, material_props: MaterialProperties,
                      fci_prime: float, method: PrestressingMethod, member_type: PrestressMemberType,
                      moments: Tuple[float, float, float] = None,
                      long_term_multiplier: float = 2.0) -> PrestressAnalysisResult:
        
        notes = []
        fpj_limit, fpi_limit = self.get_tendon_stress_limits(tendon.fpu, tendon.fpy, method)
        
        # Use provided initial jacking force if available, otherwise assume max transfer limit
        if tendon.jacking_force and tendon.jacking_force > 0:
            fpi = min(fpi_limit, (tendon.jacking_force * 1000) / tendon.area)
        else:
            fpi = fpi_limit

        # Self-weight moment at midspan (N-mm) for elastic shortening fcgp calculation
        Mg_nmm = loads.dead_load * (span.length / 1000.0) ** 2 / 8.0 * 1e6
        fpe, loss_percent, loss_details = self.calculate_losses(method, tendon, span, material_props, fpi, Mg_nmm)
        
        # Forces
        Pi = tendon.total_area * fpi
        Pe = tendon.total_area * fpe
        
        # Moments
        w_d = loads.dead_load
        w_sd = loads.superimposed_dl
        w_l = loads.live_load
        
        if moments is not None:
            # moments are (M_left, M_mid, M_right) in kN-m, convert to N-mm
            M_total = moments[1] * 1e6
            M_d = w_d / (w_d + w_sd + w_l) * M_total if (w_d + w_sd + w_l) > 0 else 0
        else:
            # Simply supported midspan moment
            M_d = w_d * (span.length / 1000)**2 / 8 * 1e6  # N-mm
            M_sd = w_sd * (span.length / 1000)**2 / 8 * 1e6
            M_l = w_l * (span.length / 1000)**2 / 8 * 1e6
            M_total = M_d + M_sd + M_l
        
        # Section Properties Reminder
        A = span.area
        I = span.moment_of_inertia
        yt = span.yt
        yb = span.yb
        e = tendon.eccentricity
        
        # Initial Stresses at transfer (Dead load mostly)
        stress_top_i = -(Pi / A) + (Pi * e * yt) / I - (M_d * yt) / I
        stress_bot_i = -(Pi / A) - (Pi * e * yb) / I + (M_d * yb) / I
        
        # Service Stresses (Effective Prestress + Total Load)
        stress_top_s = -(Pe / A) + (Pe * e * yt) / I - (M_total * yt) / I
        stress_bot_s = -(Pe / A) - (Pe * e * yb) / I + (M_total * yb) / I
        
        # Get limits
        (f_ci_comp_end, f_ci_comp_other, f_ti_tension_end, f_ti_tension_other,
         f_c_comp_sustained, f_c_comp_total, f_t_tension_u, f_t_tension_t) = self.get_permissible_stresses(material_props.fc_prime, fci_prime)
        
        # Checking initial
        if stress_bot_i < -f_ci_comp_other:
            notes.append(f"Initial compression at bottom ({abs(stress_bot_i):.2f} MPa) exceeds limit ({f_ci_comp_other:.2f} MPa).")
        if stress_top_i > f_ti_tension_other:
            notes.append(f"Initial tension at top ({stress_top_i:.2f} MPa) exceeds limit ({f_ti_tension_other:.2f} MPa).")
            
        # Checking service
        if stress_top_s < -f_c_comp_total:
            notes.append(f"Service compression at top ({abs(stress_top_s):.2f} MPa) exceeds limit ({f_c_comp_total:.2f} MPa).")
        if stress_bot_s < -f_c_comp_total:
            notes.append(f"Service compression at bottom ({abs(stress_bot_s):.2f} MPa) exceeds limit ({f_c_comp_total:.2f} MPa).")
        
        tensile_class = "U"
        if stress_bot_s > f_t_tension_u:
            if stress_bot_s <= f_t_tension_t:
                tensile_class = "T"
            else:
                tensile_class = "C"
                notes.append(f"Class C cracked section. Stress ({stress_bot_s:.2f} MPa) > {f_t_tension_t:.2f} MPa. Ensure crack control.")
                
        notes.append(f"Section behaves as Class {tensile_class}.")

        # Nominal flexural strength (fps) ACI 20.3.2.3
        # dp: distance from extreme compression fiber to tendon centroid (correct for T-sections)
        dp = span.yt + tendon.eccentricity
        rho_p = tendon.total_area / (span.width * dp)
        
        fps = fpe
        if method == PrestressingMethod.PRETENSIONED or method == PrestressingMethod.POSTTENSIONED_BONDED:
            # Approximate ACI formula 20.3.2.3.1
            # ACI 318M-25 Table R20.3.2.3.1: gamma_p depends on fpy/fpu ratio
            fpy_fpu = tendon.fpy / tendon.fpu
            if fpy_fpu >= 0.90:
                gamma_p = 0.28
            elif fpy_fpu >= 0.80:
                gamma_p = 0.40
            else:
                gamma_p = 0.55
                
            beta1 = 0.85 - 0.05 * ((material_props.fc_prime - 28) / 7)
            beta1 = max(0.65, min(0.85, beta1))
            fps = tendon.fpu * (1 - (gamma_p / beta1) * (rho_p * tendon.fpu / material_props.fc_prime))
        elif method == PrestressingMethod.POSTTENSIONED_UNBONDED:
            # ACI formula 20.3.2.4.1 for unbonded span/depth <= 35
            L_depth_ratio = span.length / dp
            if L_depth_ratio <= 35:
                fps = fpe + 70 + material_props.fc_prime / (100 * rho_p)
                fps = min(fps, fpe + 420, tendon.fpy)
            else:
                fps = fpe + 70 + material_props.fc_prime / (300 * rho_p)
                fps = min(fps, fpe + 210, tendon.fpy)
        
        # Moment Capacity — T-section aware (ACI 318M-25)
        bf = span.t_flange_width if span.t_flange_width > 0 else span.width
        hf = span.t_flange_height if span.t_flange_width > 0 else span.height
        bw = span.width
        T_ps = tendon.total_area * fps
        a_trial = T_ps / (0.85 * material_props.fc_prime * bf)
        if span.t_flange_width > 0 and a_trial > hf:
            # T-section: compression block extends into web
            C_f = 0.85 * material_props.fc_prime * (bf - bw) * hf
            T_web = T_ps - C_f
            a_w = T_web / (0.85 * material_props.fc_prime * bw)
            arm_C = (C_f * (hf / 2) + T_web * (hf + a_w / 2)) / T_ps
        else:
            arm_C = a_trial / 2
        Mn = T_ps * (dp - arm_C) / 1e6  # kN-m
        phi_Mn = self.phi_factors['flexure_tension_controlled'] * Mn
        
        # Cracking Moment ACI 24.2.3.5
        f_r = 0.62 * math.sqrt(material_props.fc_prime)
        Mc = (I / yb) * (f_r + Pe / A + (Pe * e * yb) / I) / 1e6  # kN-m
        
        if phi_Mn < 1.2 * Mc:
            notes.append(f"Warning: φMn ({phi_Mn:.1f} kNm) < 1.2 Mcr ({1.2*Mc:.1f} kNm). (ACI 9.6.2.1)")
        # ACI 318M-25 Section 9.6.2.1 minimum Aps check:
        # Aps*fps must be ≥ (4/3) * (Aps_req * fps) where Aps_req satisfies phi*Mn_req = 1.2*Mcr
        # Simplified: if phi*Mn < 1.2*Mcr then Aps is insufficient unless 4/3 rule governs
        Mn_req_kNm = 1.2 * Mc  # kN-m
        if phi_Mn > 0 and Mc > 0:
            # Required Aps to satisfy (4/3)*Aps_req*fps >= Aps*fps, i.e. phi_Mn >= (4/3)*phi_Mn_req
            # Simplest form: warn if Aps*fps < (4/3)*(Aps_req*fps) equiv. phi_Mn*(3/4) < phi_Mn_req
            # but phi_Mn_req = phi_Mn, so flag only when prestress force is very low vs cracking
            Aps_fps = tendon.total_area * fps  # N
            # Minimum: Aps*fps >= (4/3) * (required tension force from cracking moment)
            # T_req = Mcr_kNm * 1e6 / (dp - arm_C) -- approximate using dp only
            phi_f = self.phi_factors['flexure_tension_controlled']
            dp_chk = span.yt + tendon.eccentricity
            T_req_min = (4.0 / 3.0) * (Mn_req_kNm * 1e6 / max(1.0, phi_f * dp_chk))
            if Aps_fps < T_req_min:
                notes.append(
                    f"Warning: Aps\u00b7fps ({Aps_fps/1000:.1f} kN) < (4/3)\u00d7min required "
                    f"({T_req_min/1000:.1f} kN). Section may be under-prestressed. (ACI 9.6.2.1)"
                )
        # Deflection — superposition of UDL + end restraint (continuity correction)
        ec = material_props.ec
        # Camber due to prestress (parabolic tendon, simply-supported approximation)
        delta_p = (5 * Pe * e * span.length**2) / (48 * ec * I)
        w_total_svc = max(0.0001, w_d + w_sd + w_l)
        if moments is not None and (moments[0] != 0.0 or moments[2] != 0.0):
            # Midspan deflection under UDL with end moments M_A, M_B (kN·m):
            # δ = 5wL⁴/(384EI) + (M_A + M_B)L²/(16EI)
            # Hogging end moments are negative → reduce (positive downward) deflection
            M_end_Nmm = (moments[0] + moments[2]) * 1e6  # N·mm
            moment_corr = M_end_Nmm * span.length ** 2 / (16.0 * ec * I)
            delta_dl = (5 * w_d * span.length**4) / (384 * ec * I) + (w_d / w_total_svc) * moment_corr
            delta_ll = (5 * w_l * span.length**4) / (384 * ec * I) + (w_l / w_total_svc) * moment_corr
        else:
            delta_dl = (5 * w_d * span.length**4) / (384 * ec * I)
            delta_ll = (5 * w_l * span.length**4) / (384 * ec * I)

        initial_deflection = delta_dl - delta_p
        # ACI 318M-25 Table 24.2.4.1.3 long-term multiplier (default 2.0 = 5+ years)
        final_deflection = (initial_deflection * long_term_multiplier) + delta_ll

        return PrestressAnalysisResult(
            span_index=span_index,
            initial_stress_top=stress_top_i,
            initial_stress_bot=stress_bot_i,
            service_stress_top=stress_top_s,
            service_stress_bot=stress_bot_s,
            fpi=fpi,
            fpe=fpe,
            fps=fps,
            moment_capacity=phi_Mn,
            cracking_moment=Mc,
            deflection_initial=initial_deflection,
            deflection_final=final_deflection,
            loss_total_percentage=loss_percent,
            design_notes=notes
        )

    def analyze_multispan(self, spans: List[SpanGeometry], loads: List[PrestressLoads], 
                          tendon: PrestressTendon, material_props: MaterialProperties, 
                          fci_prime: float, method: PrestressingMethod, member_type: PrestressMemberType) -> List[PrestressAnalysisResult]:
        """Iterates over a list of spans and returns localized results"""
        results = []
        continuous_moments = self.calculate_continuous_moments(spans, loads)
        
        for i, (span, load, moments) in enumerate(zip(spans, loads, continuous_moments)):
            result = self.evaluate_span(i, span, load, tendon, material_props, fci_prime, method, member_type, moments)
            results.append(result)
        return results

    def run_continuous_analysis(
        self,
        spans: List[SpanGeometry],
        span_loads: List[PrestressLoads],
        supports_types: List[str],
        tendon: PrestressTendon,
        mat_props: MaterialProperties,
        fci_prime: float,
        method: PrestressingMethod,
        member_type: PrestressMemberType,
        tendon_profile: str = "parabolic",
        rebar_as_bot: float = 0.0,
        rebar_as_top: float = 0.0,
        rebar_fy: float = 420.0,
        long_term_multiplier: float = 2.0,
        deflection_limit: float = 240.0,
    ) -> List[PrestressAnalysisResult]:
        """
        Full continuous beam stiffness-method analysis.

        Assembles and solves the global stiffness system, extracts internal
        forces at each span, runs evaluate_span, enriches each result with
        DCRs / stresses at three section points (left, mid, right), and
        adjusts deflection for the chosen tendon profile.
        Returns a list of fully-populated PrestressAnalysisResult objects.
        """
        num_spans = len(spans)
        n_nodes = num_spans + 1

        # --- 1. Stiffness matrix assembly ---
        K = np.zeros((2 * n_nodes, 2 * n_nodes))
        F = np.zeros(2 * n_nodes)

        for i in range(num_spans):
            L = max(0.001, spans[i].length / 1000.0)
            EI = max(0.001, mat_props.ec * spans[i].moment_of_inertia / 1e9)
            k = (EI / L ** 3) * np.array([
                [12,    6 * L,  -12,    6 * L],
                [6 * L, 4 * L ** 2, -6 * L, 2 * L ** 2],
                [-12,  -6 * L,  12,   -6 * L],
                [6 * L, 2 * L ** 2, -6 * L, 4 * L ** 2],
            ])
            idx = [2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3]
            for a in range(4):
                for b in range(4):
                    K[idx[a], idx[b]] += k[a, b]

            w_total = (span_loads[i].dead_load
                       + span_loads[i].superimposed_dl
                       + span_loads[i].live_load)
            fem = np.array([
                w_total * L / 2,
                w_total * L ** 2 / 12,
                w_total * L / 2,
                -w_total * L ** 2 / 12,
            ])
            for a in range(4):
                F[idx[a]] -= fem[a]

        # --- 2. Apply boundary conditions and solve ---
        # "pinned"/"roller": constrain translation only
        # "fixed"/"clamped": constrain translation + rotation
        fixed_dofs = []
        for _ni in range(n_nodes):
            if supports_types[_ni] != "unsupported":
                fixed_dofs.append(2 * _ni)          # translational DOF
            if supports_types[_ni] in ("fixed", "clamped"):
                fixed_dofs.append(2 * _ni + 1)      # rotational DOF
        free_dofs = [j for j in range(2 * n_nodes) if j not in fixed_dofs]

        U = np.zeros(2 * n_nodes)
        if free_dofs:
            K_ff = K[np.ix_(free_dofs, free_dofs)]
            F_f = F[free_dofs]
            try:
                U_f = np.linalg.solve(K_ff, F_f)
            except np.linalg.LinAlgError:
                U_f = np.zeros(len(free_dofs))
            U[free_dofs] = U_f

        # --- 3. Recover internal forces per span ---
        continuous_data_list = []
        for i in range(num_spans):
            L = max(0.001, spans[i].length / 1000.0)
            EI = max(0.001, mat_props.ec * spans[i].moment_of_inertia / 1e9)
            k = (EI / L ** 3) * np.array([
                [12,    6 * L,  -12,    6 * L],
                [6 * L, 4 * L ** 2, -6 * L, 2 * L ** 2],
                [-12,  -6 * L,  12,   -6 * L],
                [6 * L, 2 * L ** 2, -6 * L, 4 * L ** 2],
            ])
            idx = [2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3]
            w_total = (span_loads[i].dead_load
                       + span_loads[i].superimposed_dl
                       + span_loads[i].live_load)
            fem = np.array([
                w_total * L / 2,
                w_total * L ** 2 / 12,
                w_total * L / 2,
                -w_total * L ** 2 / 12,
            ])
            local_f = k @ U[idx] + fem
            M_left = -local_f[1]
            M_right = local_f[3]
            V_left = local_f[0]
            x_m = (min(max(0, V_left / max(0.0001, w_total)), L)
                   if w_total > 0 else L / 2)
            M_mid = M_left + V_left * x_m - w_total * x_m ** 2 / 2
            continuous_data_list.append(
                (M_left, M_mid, M_right, V_left, float(local_f[2]))
            )

        # --- 4. Evaluate each span ---
        results: List[PrestressAnalysisResult] = []
        for i, (span, load, cd) in enumerate(
            zip(spans, span_loads, continuous_data_list)
        ):
            moments = cd[:3]
            res = self.evaluate_span(
                i, span, load, tendon, mat_props,
                fci_prime, method, member_type, moments,
                long_term_multiplier=long_term_multiplier,
            )

            # Optional mild-rebar superposition on flexural capacity
            if rebar_as_top > 0 or rebar_as_bot > 0:
                dp = span.yt + tendon.eccentricity
                d_rebar_bot = span.height - 50
                d_prime = 50
                bf = span.t_flange_width if span.t_flange_width > 0 else span.width
                hf = span.t_flange_height if span.t_flange_width > 0 else span.height
                bw = span.width
                T_total = (tendon.total_area * res.fps
                           + rebar_as_bot * rebar_fy
                           - rebar_as_top * rebar_fy)
                if T_total > 0:
                    a_trial = T_total / (0.85 * mat_props.fc_prime * bf)
                    if span.t_flange_width > 0 and a_trial > hf:
                        C_f = 0.85 * mat_props.fc_prime * (bf - bw) * hf
                        T_web = T_total - C_f
                        a_w = T_web / (0.85 * mat_props.fc_prime * bw)
                        arm = (C_f * (hf / 2) + T_web * (hf + a_w / 2)) / T_total
                    else:
                        arm = a_trial / 2
                    d_eff = (tendon.total_area * res.fps * dp
                             + rebar_as_bot * rebar_fy * d_rebar_bot
                             - rebar_as_top * rebar_fy * d_prime) / T_total
                    Mn = T_total * (d_eff - arm)
                    res.moment_capacity = self.phi_factors['flexure_tension_controlled'] * Mn / 1e6
                res.design_notes.append(
                    f"Capacity adjusted for supplemental rebar "
                    f"(As={rebar_as_bot} mm², As'={rebar_as_top} mm²)."
                )

            # Factored load ratio
            wu = (1.2 * load.dead_load
                  + 1.2 * load.superimposed_dl
                  + 1.6 * load.live_load)
            w_unfact = max(
                0.0001,
                load.dead_load + load.superimposed_dl + load.live_load,
            )
            lf = wu / w_unfact  # load factor

            v_left, v_right = cd[3], cd[4]
            res.Vu = max(abs(v_left), abs(v_right)) * lf
            res.Mu_max = max(abs(moments[0]), abs(moments[1]), abs(moments[2])) * lf

            # Factored internal forces at three section points
            res.Mu_left  = moments[0] * lf
            res.Mu_mid   = moments[1] * lf
            res.Mu_right = moments[2] * lf
            res.Vu_left  = v_left * lf
            res.Vu_right = v_right * lf
            L_m = span.length / 1000.0
            v_mid = v_left - w_unfact * (L_m / 2)
            res.Vu_mid = v_mid * lf
            res.Tu_left = res.Tu_mid = res.Tu_right = 0.0
            res.Tu = 0.0

            # Concrete section shear capacity — ACI 318M-25 Section 22.5.6 (prestressed members)
            # Vc = (0.17λ√f'c + 0.3*fpc) * bw * dp + Vp  (λ=1.0 normal-weight)
            dp_shear = span.height / 2 + tendon.eccentricity
            d_shear = max(0.8 * span.height, dp_shear)
            Pe_N = tendon.total_area * res.fpe  # effective prestress force (N)
            fpc = Pe_N / span.area  # compressive stress at centroid (MPa)
            # Vertical component of Pe for parabolic tendon: slope at support = 4e/L
            Vp_kN = Pe_N * (4.0 * tendon.eccentricity / max(1.0, span.length)) / 1000.0
            Vc = (0.17 * math.sqrt(mat_props.fc_prime) + 0.3 * fpc) * span.width * d_shear / 1000.0 + Vp_kN
            res.phi_Vn = 0.75 * Vc

            # Torsional cracking capacity — ACI 318M-25 Section 22.7.4.1
            # Tcr = (1/3)λ√f'c × (Acp²/pcp) × √(1 + fpc/(0.33λ√f'c)) [N·mm, SI]
            bf_t = span.t_flange_width if span.t_flange_width > 0 else span.width
            Acp = span.area  # gross section area (mm²)
            pcp = 2.0 * (bf_t + span.height)  # outer perimeter (mm)
            sqrt_fc = math.sqrt(max(0.0001, mat_props.fc_prime))
            fpc_safe = max(0.0, fpc)
            prestress_factor = math.sqrt(1.0 + fpc_safe / max(0.0001, 0.33 * sqrt_fc))
            Tcr_Nmm = (1.0 / 3.0) * sqrt_fc * (Acp ** 2 / pcp) * prestress_factor
            res.phi_Tn = 0.75 * Tcr_Nmm / 1e6  # kN·m

            # Allowable deflection — ACI 318M-25 Table 24.2.2
            # deflection_limit: 240 (roof/no sensitive elements), 360 (floor w/ non-struct.), 480 (sensitive)
            res.allowable_deflection = span.length / deflection_limit

            # Stresses at left / mid / right section points
            A  = span.area
            I  = span.moment_of_inertia
            yt = span.yt
            yb = span.yb
            e  = tendon.eccentricity
            Pi = tendon.total_area * res.fpi
            Pe = tendon.total_area * res.fpe
            w_d = load.dead_load
            w_svc = max(0.0001, load.dead_load + load.superimposed_dl + load.live_load)

            def _stress(M_kNm: float):
                M_d = w_d / w_svc * M_kNm * 1e6
                M_s = M_kNm * 1e6
                st_i = -(Pi / A) + (Pi * e * yt) / I - (M_d * yt) / I
                sb_i = -(Pi / A) - (Pi * e * yb) / I + (M_d * yb) / I
                st_s = -(Pe / A) + (Pe * e * yt) / I - (M_s * yt) / I
                sb_s = -(Pe / A) - (Pe * e * yb) / I + (M_s * yb) / I
                return st_i, sb_i, st_s, sb_s

            res.left_st_i,  res.left_sb_i,  res.left_st_s,  res.left_sb_s  = _stress(moments[0])
            res.right_st_i, res.right_sb_i, res.right_st_s, res.right_sb_s = _stress(moments[2])
            res.mid_st_i = res.initial_stress_top
            res.mid_sb_i = res.initial_stress_bot
            res.mid_st_s = res.service_stress_top
            res.mid_sb_s = res.service_stress_bot

            # DCRs
            phiMn  = max(0.001, res.moment_capacity)
            phiVn  = max(0.001, res.phi_Vn)
            phiTn  = max(0.001, res.phi_Tn)
            delt_a = max(0.001, res.allowable_deflection)

            res.dcr_flexure_left  = abs(res.Mu_left)  / phiMn
            res.dcr_flexure_mid   = abs(res.Mu_mid)   / phiMn
            res.dcr_flexure_right = abs(res.Mu_right) / phiMn
            res.dcr_shear_left    = abs(res.Vu_left)  / phiVn
            res.dcr_shear_mid     = abs(res.Vu_mid)   / phiVn
            res.dcr_shear_right   = abs(res.Vu_right) / phiVn
            res.dcr_torsion_left  = res.Tu_left  / phiTn
            res.dcr_torsion_mid   = res.Tu_mid   / phiTn
            res.dcr_torsion_right = res.Tu_right / phiTn
            res.dcr_comb_left  = res.dcr_shear_left  + res.dcr_torsion_left
            res.dcr_comb_mid   = res.dcr_shear_mid   + res.dcr_torsion_mid
            res.dcr_comb_right = res.dcr_shear_right + res.dcr_torsion_right
            res.dcr_deflect_left  = 0.0
            res.dcr_deflect_right = 0.0

            # Tendon profile deflection correction
            profile_factors = {
                "straight":       (1.0 / 8.0)  / (5.0 / 48.0),
                "harped":         (1.0 / 12.0) / (5.0 / 48.0),
                "multiple_harped":(1.0 / 10.0) / (5.0 / 48.0),
            }
            factor = profile_factors.get(tendon_profile, 1.0)
            L_mm = max(1.0, span.length)
            if I > 0 and mat_props.ec > 0:
                delta_p_orig = (5 * Pe * e * L_mm ** 2) / (48 * mat_props.ec * I)
                camber_diff = delta_p_orig - delta_p_orig * factor
                res.deflection_initial += camber_diff
                res.deflection_final   += camber_diff * 2.0

            res.dcr_deflect_mid = abs(res.deflection_final) / delt_a

            res.utilization_ratio = max(
                res.dcr_flexure_left, res.dcr_flexure_mid,  res.dcr_flexure_right,
                res.dcr_shear_left,   res.dcr_shear_mid,    res.dcr_shear_right,
                res.dcr_comb_left,    res.dcr_comb_mid,     res.dcr_comb_right,
                res.dcr_deflect_mid,
            )

            results.append(res)

        return results
