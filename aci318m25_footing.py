# -*- coding: utf-8 -*-

"""
ACI 318M-25 Footing Design Library with OpenSeesPy FEA
Building Code Requirements for Structural Concrete - Foundation Design
"""

import math
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
import io
import base64
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

from aci318m25 import ACI318M25, MaterialProperties

try:
    import openseespy.opensees as ops

    OPENSEES_AVAILABLE = True
except ImportError:
    OPENSEES_AVAILABLE = False


class FootingType(Enum):
    ISOLATED = "isolated"


class SoilCondition(Enum):
    ALLOWABLE_STRESS = "allowable_stress"


@dataclass
class FootingGeometry:
    length: float
    width: float
    thickness: float
    cover: float
    column_width: float
    column_depth: float
    footing_type: FootingType
    ecc_x: float = 0.0
    ecc_y: float = 0.0
    soil_modulus: float = 50000.0  # kN/m³
    mesh_nx: int = 16
    mesh_ny: int = 16


@dataclass
class SoilProperties:
    bearing_capacity: float  # kPa
    unit_weight: float = 18.0
    condition: SoilCondition = SoilCondition.ALLOWABLE_STRESS


@dataclass
class FootingLoads:
    axial_force: float
    moment_x: float
    moment_y: float
    shear_x: float
    shear_y: float
    service_axial: float
    service_moment_x: float
    service_moment_y: float


@dataclass
class FootingReinforcement:
    bottom_bars_x: str
    bottom_spacing_x: float
    bottom_bars_y: str
    bottom_spacing_y: float
    top_bars_x: str
    top_spacing_x: float
    top_bars_y: str
    top_spacing_y: float
    development_length: float
    dowel_bars: str
    dowel_length: float


@dataclass
class FootingAnalysisResult:
    bearing_pressure_max: float
    bearing_pressure_min: float
    bearing_ok: bool
    one_way_shear_ok: bool
    two_way_shear_ok: bool
    reinforcement: FootingReinforcement
    utilization_ratio: float
    design_notes: List[str]
    fea_moment_x: float
    fea_moment_y: float
    fea_shear_x: float
    fea_shear_y: float
    contours: Dict[str, str] = None


class ACI318M25FootingDesign:

    def __init__(self):
        self.aci = ACI318M25()
        self.phi_factors = {'flexure': 0.90, 'shear': 0.75, 'bearing': 0.65}

    def _run_opensees_analysis(self, geom: FootingGeometry, loads: FootingLoads, mat_props: MaterialProperties,
                               is_service: bool = False) -> Tuple[dict, List[str]]:
        notes = []
        if not OPENSEES_AVAILABLE:
            raise ImportError("OpenSeesPy is required.")

        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)

        Ec = mat_props.ec
        nu = 0.2
        h = geom.thickness

        # Slab Section
        ops.nDMaterial('ElasticIsotropic', 1, Ec, nu)
        ops.section('ElasticMembranePlateSection', 1, Ec, nu, h, 0.0)

        Lx, Ly = geom.length, geom.width
        nx, ny = geom.mesh_nx, geom.mesh_ny
        dx, dy = Lx / nx, Ly / ny

        # Create nodes (center of footing at 0,0)
        nodeTags = {}
        for i in range(nx + 1):
            for j in range(ny + 1):
                tag = i * (ny + 1) + j + 1
                x = i * dx - Lx / 2.0
                y = j * dy - Ly / 2.0
                ops.node(tag, x, y, 0.0)
                nodeTags[(i, j)] = tag

        # Shell elements
        eleTag = 1
        for i in range(nx):
            for j in range(ny):
                n1 = nodeTags[(i, j)]
                n2 = nodeTags[(i + 1, j)]
                n3 = nodeTags[(i + 1, j + 1)]
                n4 = nodeTags[(i, j + 1)]
                ops.element('ShellMITC4', eleTag, n1, n2, n3, n4, 1)
                eleTag += 1

        # Compression-only Soil Springs (using ENT material)
        ks_mpa_mm = geom.soil_modulus * 1e-6  # Convert kN/m³ to N/mm³ (MPa/mm)
        matTag_spring = 100

        for i in range(nx + 1):
            for j in range(ny + 1):
                ax = dx if (0 < i < nx) else dx / 2.0
                ay = dy if (0 < j < ny) else dy / 2.0
                trib_area = ax * ay  # mm²

                k_spring = ks_mpa_mm * trib_area  # N/mm
                if k_spring < 1e-9: continue

                spring_mat = matTag_spring + nodeTags[(i, j)]
                ops.uniaxialMaterial('ENT', spring_mat, k_spring)

                support_tag = nodeTags[(i, j)] + 10000
                ops.node(support_tag, i * dx - Lx / 2.0, j * dy - Ly / 2.0, 0.0)
                ops.fix(support_tag, 1, 1, 1, 1, 1, 1)

                # ZeroLength element acting in Z direction (DOF 3)
                ops.element('zeroLength', eleTag, support_tag, nodeTags[(i, j)], '-mat', spring_mat, '-dir', 3)
                eleTag += 1

        # Torsional stability constraint (soil provides no X/Y/Rot restraint)
        ops.fix(nodeTags[(nx // 2, ny // 2)], 1, 1, 0, 0, 0, 1)

        # Apply Column Loads via Rigid Spider to prevent moment singularities
        col_x, col_y = geom.ecc_x, geom.ecc_y
        master_node = 99999
        ops.node(master_node, col_x, col_y, 0.0)

        # Find nodes within column footprint
        cw, cd = geom.column_width, geom.column_depth
        footprint_nodes = []
        for (i, j), tag in nodeTags.items():
            x = i * dx - Lx / 2.0
            y = j * dy - Ly / 2.0
            if abs(x - col_x) <= cw / 2.0 and abs(y - col_y) <= cd / 2.0:
                footprint_nodes.append(tag)

        if not footprint_nodes:
            # Fallback to nearest node if footprint is too small
            min_dist, best_node = float('inf'), None
            for (i, j), tag in nodeTags.items():
                x = i * dx - Lx / 2.0;
                y = j * dy - Ly / 2.0
                d = math.hypot(x - col_x, y - col_y)
                if d < min_dist: min_dist, best_node = d, tag
            footprint_nodes.append(best_node)

        # Rigidly link master to footprint nodes
        for fn in footprint_nodes:
            ops.rigidLink('beam', master_node, fn)

        # Apply Loads
        P = loads.service_axial if is_service else loads.axial_force
        Mx = loads.service_moment_x if is_service else loads.moment_x
        My = loads.service_moment_y if is_service else loads.moment_y

        # Load values (Convert kN, kN-m to N, N-mm)
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        ops.load(master_node, 0.0, 0.0, -P * 1000.0, Mx * 1e6, My * 1e6, 0.0)

        # Add self-weight
        w_sw = 24e-6 * h  # N/mm²
        factor = 1.0 if is_service else 1.2
        for (i, j), tag in nodeTags.items():
            ax = dx if (0 < i < nx) else dx / 2.0
            ay = dy if (0 < j < ny) else dy / 2.0
            ops.load(tag, 0.0, 0.0, -w_sw * (ax * ay) * factor, 0.0, 0.0, 0.0)

        # Analysis settings (Nonlinear due to ENT)
        ops.system('BandGeneral')
        ops.numberer('RCM')
        ops.constraints('Transformation')
        ops.test('NormDispIncr', 1.0e-5, 100, 0)
        ops.algorithm('Newton')
        ops.integrator('LoadControl', 0.1)
        ops.analysis('Static')

        ok = ops.analyze(10)
        if ok != 0:
            notes.append(
                "⚠️ Nonlinear soil springs failed to converge. Reverting to linear elastic soil (uplift ignored).")
            ops.wipeAnalysis()
            for i in range(nx + 1):
                for j in range(ny + 1):
                    ax = dx if (0 < i < nx) else dx / 2.0;
                    ay = dy if (0 < j < ny) else dy / 2.0
                    ops.uniaxialMaterial('Elastic', matTag_spring + nodeTags[(i, j)], ks_mpa_mm * ax * ay)
            ops.system('BandSPD')
            ops.test('NormDispIncr', 1.0e-6, 100, 0)
            ops.algorithm('Linear')
            ops.analyze(10)

        # Extract Results
        W = np.zeros((nx + 1, ny + 1))
        MXX = np.zeros((nx + 1, ny + 1))
        MYY = np.zeros((nx + 1, ny + 1))
        Q_SOIL = np.zeros((nx + 1, ny + 1))

        D = (Ec * h ** 3) / (12.0 * (1.0 - nu ** 2))

        def get_w(xi, yj):
            return ops.nodeDisp(xi * (ny + 1) + yj + 1, 3)

        for i in range(nx + 1):
            for j in range(ny + 1):
                n_c = i * (ny + 1) + j + 1
                wc = ops.nodeDisp(n_c, 3)
                W[i, j] = wc

                # Soil Pressure (kPa) -> w(mm) * ks(N/mm3) * 1000 = kPa
                if wc < 0:
                    Q_SOIL[i, j] = abs(wc) * ks_mpa_mm * 1000.0

                # Basic Finite Difference for moments (simplified boundaries)
                wl = get_w(max(0, i - 1), j)
                wr = get_w(min(nx, i + 1), j)
                wb = get_w(i, max(0, j - 1))
                wt = get_w(i, min(ny, j + 1))

                dx_eff = dx if (0 < i < nx) else dx * 2
                dy_eff = dy if (0 < j < ny) else dy * 2

                d2w_dx2 = (wl - 2 * wc + wr) / (dx_eff ** 2) if (0 < i < nx) else 0
                d2w_dy2 = (wb - 2 * wc + wt) / (dy_eff ** 2) if (0 < j < ny) else 0

                mxx = D * (d2w_dx2 + nu * d2w_dy2) * 0.001  # kN-m/m
                myy = D * (d2w_dy2 + nu * d2w_dx2) * 0.001  # kN-m/m

                MXX[i, j] = mxx
                MYY[i, j] = myy

        VX, VY = np.zeros((nx + 1, ny + 1)), np.zeros((nx + 1, ny + 1))
        dx_m, dy_m = dx / 1000.0, dy / 1000.0
        for i in range(nx + 1):
            for j in range(ny + 1):
                VX[i, j] = (MXX[min(i + 1, nx), j] - MXX[max(i - 1, 0), j]) / (2 * dx_m if 0 < i < nx else dx_m)
                VY[i, j] = (MYY[i, min(j + 1, ny)] - MYY[i, max(j - 1, 0)]) / (2 * dy_m if 0 < j < ny else dy_m)

        res_data = {
            'W': W, 'MXX': MXX, 'MYY': MYY, 'VX': VX, 'VY': VY, 'Q_SOIL': Q_SOIL
        }
        return res_data, notes

    def generate_contour_plots(self, geom: FootingGeometry, grid_data: dict) -> Dict[str, str]:
        x_lin = np.linspace(-geom.length / 2, geom.length / 2, grid_data['W'].shape[0])
        y_lin = np.linspace(-geom.width / 2, geom.width / 2, grid_data['W'].shape[1])
        X, Y = np.meshgrid(x_lin, y_lin, indexing='ij')

        plots = {}
        configs = [
            ('soil_pressure', 'Q_SOIL', 'Bearing Pressure (kPa)', 'YlOrRd'),
            ('mxx', 'MXX', 'Mxx Bending (kN-m/m)', 'RdBu_r'),
            ('myy', 'MYY', 'Myy Bending (kN-m/m)', 'RdBu_r'),
            ('vx', 'VX', 'Shear Vx (kN/m)', 'coolwarm'),
            ('vy', 'VY', 'Shear Vy (kN/m)', 'coolwarm'),
        ]

        for key, grid_key, title, cmap in configs:
            Z = grid_data[grid_key]
            plt.figure(figsize=(5, 4.5))
            cs = plt.contourf(X, Y, Z, levels=20, cmap=cmap)
            plt.colorbar(cs)

            # Plot column outline
            cw, cd = geom.column_width, geom.column_depth
            cx, cy = geom.ecc_x, geom.ecc_y
            plt.plot([cx - cw / 2, cx + cw / 2, cx + cw / 2, cx - cw / 2, cx - cw / 2],
                     [cy - cd / 2, cy - cd / 2, cy + cd / 2, cy + cd / 2, cy - cd / 2], 'k-', linewidth=2)

            plt.title(title, fontsize=12, fontweight='bold', color='#111827')
            plt.xlabel("X (mm)")
            plt.ylabel("Y (mm)")
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=120)
            plt.close()
            buf.seek(0)
            plots[key] = base64.b64encode(buf.read()).decode('utf-8')
        return plots

    def check_two_way_shear(self, geom: FootingGeometry, loads: FootingLoads, mat: MaterialProperties) -> Tuple[
        bool, float]:
        fc_prime = mat.fc_prime
        d = geom.thickness - geom.cover - 20
        bo = 2 * (geom.column_width + d) + 2 * (geom.column_depth + d)

        bearing_area = geom.length * geom.width / 1e6
        qu = loads.axial_force / bearing_area
        critical_area = (geom.column_width + d) * (geom.column_depth + d) / 1e6
        Vu = loads.axial_force - qu * critical_area

        beta = max(geom.column_width, geom.column_depth) / min(geom.column_width, geom.column_depth)
        alphas = 40
        vc1 = 0.17 * (1 + 2 / beta) * math.sqrt(fc_prime)
        vc2 = 0.083 * (alphas * d / bo + 2) * math.sqrt(fc_prime)
        vc3 = 0.33 * math.sqrt(fc_prime)
        vc = min(vc1, vc2, vc3)

        phi_Vn = self.phi_factors['shear'] * vc * bo * d / 1000
        ratio = Vu / phi_Vn if phi_Vn > 0 else 99.9
        return ratio <= 1.0, ratio

    def _select_rebar(self, As_req: float, width: float, thickness: float) -> Tuple[str, float]:
        bar_sizes = ['D12', 'D16', 'D20', 'D25']
        max_s = min(3 * thickness, 450.0)
        for bar in bar_sizes:
            area = self.aci.get_bar_area(bar)
            s = area * width / As_req
            db = self.aci.get_bar_diameter(bar)
            if (max(25.0, db) + db) <= s <= max_s:
                return bar, math.floor(s / 10.0) * 10.0
        return 'D20', math.floor(max_s / 10.0) * 10.0

    def perform_complete_design(self, geom: FootingGeometry, loads: FootingLoads, soil: SoilProperties,
                                mat: MaterialProperties) -> FootingAnalysisResult:
        notes = ["FEA analysis performed using OpenSeesPy ShellMITC4 elements."]

        # 1. Service Analysis (Bearing Pressure)
        srv_data, srv_notes = self._run_opensees_analysis(geom, loads, mat, is_service=True)
        notes.extend(srv_notes)
        qmax = np.max(srv_data['Q_SOIL'])
        qmin = np.min(srv_data['Q_SOIL'])

        bearing_ok = qmax <= soil.bearing_capacity
        if not bearing_ok: notes.append(
            f"⚠️ Bearing pressure ({qmax:.1f} kPa) exceeds capacity ({soil.bearing_capacity} kPa).")
        if qmin <= 0.1: notes.append("ℹ️ Footing is experiencing partial uplift (compression-only soils active).")

        # 2. Ultimate Analysis (Strength)
        ult_data, ult_notes = self._run_opensees_analysis(geom, loads, mat, is_service=False)

        M_x_pos = np.max(ult_data['MXX']);
        M_x_neg = abs(np.min(ult_data['MXX']))
        M_y_pos = np.max(ult_data['MYY']);
        M_y_neg = abs(np.min(ult_data['MYY']))
        V_x = np.max(np.abs(ult_data['VX']))
        V_y = np.max(np.abs(ult_data['VY']))

        # Flexure Design
        d_eff = geom.thickness - geom.cover - 20
        rho_min = 0.0018
        As_min = rho_min * 1000 * geom.thickness

        def req_as(M):
            if M <= 0: return As_min
            A = self.phi_factors['flexure'] * mat.fy ** 2 / (2 * 0.85 * mat.fc_prime * 1000)
            B = -self.phi_factors['flexure'] * mat.fy * d_eff
            C = M * 1e6
            disc = B ** 2 - 4 * A * C
            if disc < 0: return As_min * 2  # Fallback
            return max((-B - math.sqrt(disc)) / (2 * A), As_min)

        bx, sx = self._select_rebar(req_as(max(M_x_pos, M_x_neg)), 1000, geom.thickness)
        by, sy = self._select_rebar(req_as(max(M_y_pos, M_y_neg)), 1000, geom.thickness)

        # Shear Checks
        phi_vc = self.phi_factors['shear'] * 0.17 * math.sqrt(mat.fc_prime) * 1000 * d_eff / 1000
        one_way_ratio = max(V_x, V_y) / phi_vc if phi_vc > 0 else 99.9
        one_way_ok = one_way_ratio <= 1.0
        if not one_way_ok: notes.append(
            f"⚠️ 1-Way Shear inadequate. Max FEA shear {max(V_x, V_y):.1f} kN/m > capacity {phi_vc:.1f} kN/m.")

        two_way_ok, two_way_ratio = self.check_two_way_shear(geom, loads, mat)
        if not two_way_ok: notes.append(f"⚠️ 2-Way (Punching) Shear inadequate. DCR = {two_way_ratio:.2f}.")

        # Generate Visualizations
        plots = self.generate_contour_plots(geom, ult_data)
        plots['soil_pressure'] = self.generate_contour_plots(geom, srv_data)[
            'soil_pressure']  # Swap with service pressure

        reinf = FootingReinforcement(bx, sx, by, sy, 'None', 0.0, 'None', 0.0,
                                     self.aci.calculate_development_length(bx, mat.fc_prime, mat.fy), 'D20', 600.0)

        dcr = max(qmax / soil.bearing_capacity, one_way_ratio, two_way_ratio)

        return FootingAnalysisResult(
            qmax, qmin, bearing_ok, one_way_ok, two_way_ok, reinf, dcr, list(set(notes)),
            max(M_x_pos, M_x_neg), max(M_y_pos, M_y_neg), V_x, V_y, plots
        )

    def calculate_qto(self, geom: FootingGeometry, res: FootingAnalysisResult) -> dict:
        vol = (geom.length / 1000.0) * (geom.width / 1000.0) * (geom.thickness / 1000.0)
        fw = 2 * (geom.length / 1000.0 + geom.width / 1000.0) * (geom.thickness / 1000.0)

        def bar_wt(size, sp, L1, L2):
            db = float(size.replace('D', ''))
            qty = math.ceil(L1 / sp)
            length = (L2 - 2 * geom.cover) / 1000.0
            return qty * length * (db ** 2 / 162.0)

        wt_x = bar_wt(res.reinforcement.bottom_bars_x, res.reinforcement.bottom_spacing_x, geom.width, geom.length)
        wt_y = bar_wt(res.reinforcement.bottom_bars_y, res.reinforcement.bottom_spacing_y, geom.length, geom.width)

        return {'volume': vol, 'formwork': fw, 'weight': wt_x + wt_y}