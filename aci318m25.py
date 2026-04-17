#! /Users/tsuno/.pyenv/shims/python3
# -*- coding: utf-8 -*-

"""
ACI 318M-25 Building Code for Structural Concrete Implementation
Based on ACI CODE-318-25 International System of Units
"""

import math
from typing import Dict, Tuple, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

class ConcreteStrengthClass(Enum):
    FC14 = "13.8"    
    FC17 = "17.3"    
    FC21 = "20.7"    
    FC28 = "27.6"    
    FC35 = "34.5"    
    FC42 = "41.4"    
    FC50 = "48.3"    
    FC55 = "55.2"    
    FC70 = "70"      
    FC80 = "80"      
    FC100 = "100"    

class ReinforcementGrade(Enum):
    GRADE280 = "276"   
    GRADE420 = "415"   
    GRADE520 = "520"   
    GRADE550 = "550"   

class ExposureCondition(Enum):
    F0 = "F0"  
    F1 = "F1"  
    F2 = "F2"  
    F3 = "F3"  
    S0 = "S0"  
    S1 = "S1"  
    S2 = "S2"  
    S3 = "S3"  
    C0 = "C0"  
    C1 = "C1"  
    C2 = "C2"  

class StructuralElement(Enum):
    SLAB = "slab"
    BEAM = "beam"
    COLUMN = "column"
    WALL = "wall"
    FOUNDATION = "foundation"
    JOIST = "joist"
    FOOTING = "footing"

@dataclass
class ACI318LoadCombination:
    name: str
    formula: str
    description: str
    load_factors: Dict[str, float]
    category: str 

@dataclass
class MaterialProperties:
    """Material properties according to ACI 318M-25"""
    fc_prime: float       # Specified compressive strength (MPa)
    fy: float             # Yield strength for longitudinal bars (MPa)
    fu: float             # Tensile strength for longitudinal bars (MPa)
    fyt: float            # Yield strength for transverse reinforcement (MPa)
    fut: float            # Tensile strength for transverse reinforcement (MPa)
    es: float             # Modulus of elasticity of steel (MPa)
    ec: float             # Modulus of elasticity of concrete (MPa)
    gamma_c: float        # Unit weight of concrete (kN/m³)
    description: str
    lambda_factor: float = 1.0  # ACI 318M-25 §19.2.4: 1.0 NW, 0.85 sand-LW, 0.75 all-LW concrete

class ACI318M25:
    
    def __init__(self):
        self.concrete_strengths = {
            ConcreteStrengthClass.FC14: {'fc_prime': 14.0, 'usage': 'Plain concrete, non-structural', 'min_cement_content': 280, 'max_w_c_ratio': 0.70},
            ConcreteStrengthClass.FC17: {'fc_prime': 17.0, 'usage': 'Plain concrete, footings', 'min_cement_content': 300, 'max_w_c_ratio': 0.65},
            ConcreteStrengthClass.FC21: {'fc_prime': 21.0, 'usage': 'Structural concrete, normal applications', 'min_cement_content': 320, 'max_w_c_ratio': 0.60},
            ConcreteStrengthClass.FC28: {'fc_prime': 28.0, 'usage': 'Structural concrete, standard', 'min_cement_content': 350, 'max_w_c_ratio': 0.55},
            ConcreteStrengthClass.FC35: {'fc_prime': 35.0, 'usage': 'High-strength applications', 'min_cement_content': 375, 'max_w_c_ratio': 0.50},
            ConcreteStrengthClass.FC42: {'fc_prime': 42.0, 'usage': 'High-strength structural concrete', 'min_cement_content': 400, 'max_w_c_ratio': 0.45},
            ConcreteStrengthClass.FC50: {'fc_prime': 50.0, 'usage': 'High-strength structural concrete', 'min_cement_content': 425, 'max_w_c_ratio': 0.40},
            ConcreteStrengthClass.FC55: {'fc_prime': 55.0, 'usage': 'High-performance concrete', 'min_cement_content': 450, 'max_w_c_ratio': 0.38},
            ConcreteStrengthClass.FC70: {'fc_prime': 70.0, 'usage': 'High-performance concrete', 'min_cement_content': 475, 'max_w_c_ratio': 0.35},
            ConcreteStrengthClass.FC80: {'fc_prime': 80.0, 'usage': 'Ultra-high-strength concrete', 'min_cement_content': 500, 'max_w_c_ratio': 0.32},
            ConcreteStrengthClass.FC100: {'fc_prime': 100.0, 'usage': 'Ultra-high-strength concrete', 'min_cement_content': 550, 'max_w_c_ratio': 0.28}
        }
        
        self.reinforcement_grades = {
            ReinforcementGrade.GRADE280: {'fy': 280.0, 'fu': 420.0, 'es': 200000.0, 'grade_designation': 'Grade 280 (40 ksi)', 'astm_specification': 'ASTM A615/A615M', 'usage': 'Standard reinforcement for most applications'},
            ReinforcementGrade.GRADE420: {'fy': 420.0, 'fu': 620.0, 'es': 200000.0, 'grade_designation': 'Grade 420 (60 ksi)', 'astm_specification': 'ASTM A615/A615M', 'usage': 'Most common grade for structural concrete'},
            ReinforcementGrade.GRADE520: {'fy': 520.0, 'fu': 690.0, 'es': 200000.0, 'grade_designation': 'Grade 520 (75 ksi)', 'astm_specification': 'ASTM A615/A615M', 'usage': 'High-strength applications'},
            ReinforcementGrade.GRADE550: {'fy': 550.0, 'fu': 725.0, 'es': 200000.0, 'grade_designation': 'Grade 550 (80 ksi)', 'astm_specification': 'ASTM A615/A615M', 'usage': 'High-strength structural applications'}
        }
        
        self.bar_areas = {
            'D10': {'diameter': 10.0, 'area': 78.54},
            'D12': {'diameter': 12.0, 'area': 113.10},
            'D16': {'diameter': 16.0, 'area': 201.06},
            'D20': {'diameter': 20.0, 'area': 314.16},
            'D25': {'diameter': 25.0, 'area': 490.87},
            'D28': {'diameter': 28.0, 'area': 615.75},
            'D32': {'diameter': 32.0, 'area': 804.25},
            'D36': {'diameter': 36.0, 'area': 1017.88},
            'D40': {'diameter': 40.0, 'area': 1256.64},
            'D50': {'diameter': 50.0, 'area': 1963.50}
        }
        
        self.cover_requirements = {
            'cast_in_place': {
                StructuralElement.SLAB: {'normal': 20, 'corrosive': 25, 'severe': 30},
                StructuralElement.BEAM: {'normal': 40, 'corrosive': 50, 'severe': 65},
                StructuralElement.COLUMN: {'normal': 40, 'corrosive': 50, 'severe': 65},
                StructuralElement.WALL: {'normal': 20, 'corrosive': 25, 'severe': 40},
                StructuralElement.FOOTING: {'normal': 75, 'corrosive': 100, 'severe': 150}
            },
            'precast': {
                StructuralElement.SLAB: {'normal': 15, 'corrosive': 20, 'severe': 25},
                StructuralElement.BEAM: {'normal': 25, 'corrosive': 40, 'severe': 50}
            }
        }
        
        self.load_combinations_strength = [
            ACI318LoadCombination("Eq. (5.3.1a)", "1.4D", "Dead load only", {'D': 1.4, 'L': 0.0, 'Lr': 0.0, 'W': 0.0, 'E': 0.0}, "strength"),
            ACI318LoadCombination("Eq. (5.3.1b)", "1.2D + 1.6L + 0.5(Lr or S or R)", "Dead and live loads", {'D': 1.2, 'L': 1.6, 'Lr': 0.5, 'W': 0.0, 'E': 0.0}, "strength"),
            ACI318LoadCombination("Eq. (5.3.1c)", "1.2D + 1.6(Lr or S or R) + (1.0L or 0.5W)", "Dead and roof live loads", {'D': 1.2, 'L': 1.0, 'Lr': 1.6, 'W': 0.5, 'E': 0.0}, "strength"),
            ACI318LoadCombination("Eq. (5.3.1d)", "1.2D + 1.0W + 1.0L + 0.5(Lr or S or R)", "Dead, live, and wind loads", {'D': 1.2, 'L': 1.0, 'Lr': 0.5, 'W': 1.0, 'E': 0.0}, "strength"),
            ACI318LoadCombination("Eq. (5.3.1e)", "1.2D + 1.0E + 1.0L + 0.2S", "Dead, live, and earthquake loads", {'D': 1.2, 'L': 1.0, 'Lr': 0.0, 'W': 0.0, 'E': 1.0}, "strength"),
            ACI318LoadCombination("Eq. (5.3.1f)", "0.9D + 1.0W", "Dead and wind loads (uplift)", {'D': 0.9, 'L': 0.0, 'Lr': 0.0, 'W': 1.0, 'E': 0.0}, "strength"),
            ACI318LoadCombination("Eq. (5.3.1g)", "0.9D + 1.0E", "Dead and earthquake loads (uplift)", {'D': 0.9, 'L': 0.0, 'Lr': 0.0, 'W': 0.0, 'E': 1.0}, "strength")
        ]
        
        self.load_combinations_service = [
            ACI318LoadCombination("Service-1", "1.0D + 1.0L", "Dead and live loads", {'D': 1.0, 'L': 1.0, 'Lr': 0.0, 'W': 0.0, 'E': 0.0}, "service"),
            ACI318LoadCombination("Service-2", "1.0D + 1.0W", "Dead and wind loads", {'D': 1.0, 'L': 0.0, 'Lr': 0.0, 'W': 1.0, 'E': 0.0}, "service"),
            ACI318LoadCombination("Service-3", "1.0D + 1.0E", "Dead and earthquake loads", {'D': 1.0, 'L': 0.0, 'Lr': 0.0, 'W': 0.0, 'E': 1.0}, "service")
        ]
        
        self.strength_reduction_factors = {
            'tension_controlled': 0.90, 'compression_controlled_tied': 0.65, 'compression_controlled_spiral': 0.75,
            'shear': 0.75, 'torsion': 0.75, 'bearing': 0.65, 'plain_concrete': 0.60, 'development': 0.75, 'strut_and_tie': 0.75
        }

    def get_concrete_modulus(self, fc_prime: float, lambda_factor: float = 1.0, gamma_c: float = 24.0) -> float:
        if gamma_c == 24.0:
            ec = 4700 * math.sqrt(fc_prime) * lambda_factor
        else:
            w_c = gamma_c * 101.9716
            ec = (w_c ** 1.5) * 0.043 * math.sqrt(fc_prime) * lambda_factor
        return ec

    def get_concrete_cover(self, element: StructuralElement, exposure: str = 'normal', construction_type: str = 'cast_in_place') -> Tuple[float, str, str]:
        if construction_type in self.cover_requirements:
            if element in self.cover_requirements[construction_type]:
                cover_data = self.cover_requirements[construction_type][element]
                cover_mm = cover_data.get(exposure, cover_data['normal'])
                return cover_mm, 'mm', f'{element.value} - {exposure} exposure'
        return 40.0, 'mm', f'{element.value} - default cover'

    def get_strength_reduction_factor(self, failure_mode: str) -> float:
        return self.strength_reduction_factors.get(failure_mode, 0.75)

    def check_load_combinations(self, loads: Dict[str, float], combination_type: str = 'strength') -> List[Dict]:
        combinations = self.load_combinations_strength if combination_type == 'strength' else self.load_combinations_service
        results = []
        for combo in combinations:
            factored_load = 0.0
            load_details = []
            for load_type, factor in combo.load_factors.items():
                if load_type in loads and factor > 0:
                    contribution = factor * loads[load_type]
                    factored_load += contribution
                    if contribution > 0:
                        load_details.append(f"{factor}×{loads[load_type]:.1f}")
            
            results.append({
                'name': combo.name, 'formula': combo.formula, 'description': combo.description,
                'factored_load': factored_load, 'calculation': " + ".join(load_details) if load_details else "0",
                'category': combo.category
            })
        return results

    def calculate_development_length(self, bar_size: str, fc_prime: float, fy: float,
                                      modification_factors: Dict = None,
                                      cb: float = None, Ktr: float = 0.0) -> float:
        db = self.get_bar_diameter(bar_size)
        psi_t = modification_factors.get('top_bar', 1.0) if modification_factors else 1.0
        psi_e = modification_factors.get('epoxy', 1.0) if modification_factors else 1.0
        psi_s = modification_factors.get('size', 1.0) if modification_factors else 1.0
        lambda_factor = modification_factors.get('lambda', 1.0) if modification_factors else 1.0
        # ACI 318M-25 §25.5.2.2: grade factor ψg (1.15 for Grade 550, 1.0 otherwise)
        psi_g = 1.15 if fy > 420.0 else 1.0
        # ACI 318M-25 §25.5.2.3: confinement term (cb + Ktr)/db, capped at 2.5.
        # cb = distance from bar centre to nearest concrete surface.
        # Ktr = 40·Atr/(s·n); use 0 (conservative) when not explicitly computed.
        if cb is not None:
            confinement = min((cb + Ktr) / db, 2.5)
        else:
            confinement = 1.0  # conservative default: no confinement credit assumed
        # ACI 318M-25 Table 25.5.2.1 (SI): ld/db = fy·ψt·ψe·ψg·ψs / (1.1·λ·√f'c·(cb+Ktr)/db)
        ld = (fy * psi_t * psi_e * psi_g * psi_s * db) / (1.1 * lambda_factor * math.sqrt(fc_prime) * confinement)
        return max(ld, 300.0)

    def calculate_beta1(self, fc_prime: float) -> float:
        """Compression-zone factor β1 per ACI 318M-25 §22.2.2.3."""
        if fc_prime <= 28.0:
            return 0.85
        elif fc_prime <= 55.0:
            return 0.85 - 0.05 * (fc_prime - 28.0) / 7.0
        else:
            return 0.65

    def calculate_balanced_reinforcement_ratio(self, fc_prime: float, fy: float, beta1: float = None) -> float:
        if beta1 is None:
            beta1 = self.calculate_beta1(fc_prime)
        es = 200000 
        ecu = 0.003  
        ey = fy / es  
        cb_over_d = ecu / (ecu + ey)
        rho_b = (0.85 * fc_prime * beta1 / fy) * cb_over_d
        return rho_b

    def calculate_minimum_reinforcement_ratio(self, fc_prime: float, fy: float) -> float:
        return max(1.4 / fy, 0.25 * math.sqrt(fc_prime) / fy)

    def calculate_maximum_reinforcement_ratio(self, fc_prime: float, fy: float) -> float:
        return (3.0 / 8.0) * 0.85 * fc_prime * self.calculate_beta1(fc_prime) / fy

    def calculate_deflection_multiplier(self, rho: float, rho_prime: float = 0.0) -> float:
        return 2.0 / (1 + 50 * rho_prime)

    def calculate_effective_moment_of_inertia(self, ma: float, mcr: float, ig: float, icr: float) -> float:
        if ma <= mcr: return ig
        ratio = mcr / ma
        ie = (ratio ** 3) * ig + (1 - ratio ** 3) * icr
        return min(ie, ig)

    def calculate_cracking_moment(self, fr: float, ig: float, yt: float) -> float:
        return fr * ig / yt

    def calculate_modulus_of_rupture(self, fc_prime: float, lambda_factor: float = 1.0) -> float:
        return 0.62 * lambda_factor * math.sqrt(fc_prime)

    def check_crack_control(self, fy: float, cc: float, fs: float = None) -> Dict:
        if fs is None: fs = (2.0 / 3.0) * fy
        s_limit_1 = 380 * (280 / fs) - 2.5 * cc
        s_limit_2 = 300 * (280 / fs)
        return {'steel_stress_mpa': fs, 'clear_cover_mm': cc, 's_limit_1_mm': s_limit_1, 's_limit_2_mm': s_limit_2, 'max_spacing_mm': min(s_limit_1, s_limit_2)}

    def get_material_properties(self, concrete_class: ConcreteStrengthClass, 
                              steel_grade: ReinforcementGrade,
                              transverse_steel_grade: ReinforcementGrade = None) -> MaterialProperties:
        """Get comprehensive material properties including distinct transverse reinforcement"""
        concrete_data = self.concrete_strengths[concrete_class]
        steel_data = self.reinforcement_grades[steel_grade]
        
        # Determine transverse grade (default to longitudinal if not provided)
        transverse_steel_grade = transverse_steel_grade or steel_grade
        transverse_data = self.reinforcement_grades[transverse_steel_grade]
        
        fc_prime = concrete_data['fc_prime']
        fy = steel_data['fy']
        fu = steel_data['fu']
        fyt = transverse_data['fy']
        fut = transverse_data['fu']
        es = steel_data['es']
        
        ec = self.get_concrete_modulus(fc_prime)
        gamma_c = 24.0 
        
        desc = f"fc' = {fc_prime} MPa, fy = {fy} MPa, fyt = {fyt} MPa"
        
        return MaterialProperties(
            fc_prime=fc_prime, fy=fy, fu=fu, fyt=fyt, fut=fut,
            es=es, ec=ec, gamma_c=gamma_c, description=desc
        )

    def get_bar_area(self, bar_size: str) -> float:
        if bar_size in self.bar_areas: return self.bar_areas[bar_size]['area']
        raise ValueError(f"Unknown bar size: {bar_size}")

    def get_bar_diameter(self, bar_size: str) -> float:
        if bar_size in self.bar_areas: return self.bar_areas[bar_size]['diameter']
        raise ValueError(f"Unknown bar size: {bar_size}")

    def calculate_area_per_meter(self, bar_size: str, spacing: float) -> float:
        return (self.get_bar_area(bar_size) * 1000) / spacing

    def check_minimum_spacing(self, bar_size: str, aggregate_size: float = 25.0) -> float:
        return max(25.0, self.get_bar_diameter(bar_size), (4.0/3.0) * aggregate_size)