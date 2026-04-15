# -*- coding: utf-8 -*-

"""
ACI 318M-25 Slab Design Library using OpenSeesPy FEA
"""

import math
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum
from aci318m25 import ACI318M25, MaterialProperties

import numpy as np
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

try:
    import openseespy.opensees as ops

    OPENSEES_AVAILABLE = True
except ImportError:
    OPENSEES_AVAILABLE = False


class EdgeSupport(Enum):
    WALL = "wall"
    BEAM = "beam"
    COLUMN = "column"
    NONE = "none"


class EdgeContinuity(Enum):
    CONTINUOUS = "continuous"
    DISCONTINUOUS = "discontinuous"


class SlabType(Enum):
    FEA_MODEL = "fea_model"


class LoadPattern(Enum):
    UNIFORM = "uniform"


@dataclass
class EdgeCondition:
    support: EdgeSupport
    continuity: EdgeContinuity
    wall_t: float = 0.0
    beam_b: float = 0.0
    beam_h: float = 0.0
    col_cx: float = 0.0
    col_cy: float = 0.0


@dataclass
class SlabGeometry:
    length_x: float
    length_y: float
    thickness: float
    cover: float
    effective_depth_x: float
    effective_depth_y: float
    edge_left: EdgeCondition
    edge_right: EdgeCondition
    edge_bottom: EdgeCondition
    edge_top: EdgeCondition


@dataclass
class SlabLoads:
    self_weight: float
    superimposed_dead: float
    live_load: float
    load_pattern: LoadPattern
    load_factors: Dict[str, float]


@dataclass
class SlabReinforcement:
    main_bars_x: str
    main_spacing_x: float
    main_bars_y: str
    main_spacing_y: float
    shrinkage_bars: str
    shrinkage_spacing: float
    top_bars_x: str
    top_spacing_x: float
    top_bars_y: str
    top_spacing_y: float


@dataclass
class SlabMoments:
    moment_x_positive: float
    moment_x_negative: float
    moment_y_positive: float
    moment_y_negative: float


@dataclass
class SlabAnalysisResult:
    behavior_type: SlabType
    moments: SlabMoments
    reinforcement: SlabReinforcement
    deflection_live: float
    deflection_long: float
    utilization_ratio: float
    design_notes: List[str]
    contours: Dict[str, str] = None


class ACI318M25SlabDesign:

    def __init__(self):
        self.aci = ACI318M25()
        self.phi_factors = {'flexure': 0.90, 'shear': 0.75}

    def _run_opensees_analysis(self, geom: SlabGeometry, mat_props: MaterialProperties, load_mpa: float,
                               is_service: bool = False) -> Tuple[SlabMoments, float, List[str], dict]:
        notes = []
        if not OPENSEES_AVAILABLE:
            raise ImportError("OpenSeesPy is required. Run `pip install openseespy`.")

        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)

        Ec = mat_props.ec
        nu = 0.2
        h = geom.thickness

        mod_slab = 1.0 if is_service else 0.25
        mod_beam = 1.0 if is_service else 0.35

        Ec_slab = Ec * mod_slab
        ops.nDMaterial('ElasticIsotropic', 1, Ec_slab, nu)
        ops.section('ElasticMembranePlateSection', 1, Ec_slab, nu, h, 0.0)

        nx, ny = 12, 12
        dx, dy = geom.length_x / nx, geom.length_y / ny

        for i in range(nx + 1):
            for j in range(ny + 1):
                nodeTag = i * (ny + 1) + j + 1
                ops.node(nodeTag, i * dx, j * dy, 0.0)

        eleTag = 1
        for i in range(nx):
            for j in range(ny):
                n1 = i * (ny + 1) + j + 1
                n2 = (i + 1) * (ny + 1) + j + 1
                n3 = (i + 1) * (ny + 1) + (j + 1) + 1
                n4 = i * (ny + 1) + (j + 1) + 1
                ops.element('ShellMITC4', eleTag, n1, n2, n3, n4, 1)
                eleTag += 1

        ops.geomTransf('Linear', 1, 0.0, 1.0, 0.0)
        ops.geomTransf('Linear', 2, -1.0, 0.0, 0.0)

        beam_eleTag = 100000

        def add_beam_elements(node_list, b, depth, is_x_dir):
            nonlocal beam_eleTag
            if b <= 0 or depth <= 0: return
            A = b * depth
            Iz = mod_beam * (b * depth ** 3) / 12.0
            Iy = mod_beam * (depth * b ** 3) / 12.0
            a_dim, c_dim = max(b, depth), min(b, depth)
            J = mod_beam * (a_dim * c_dim ** 3 * (
                        1.0 / 3.0 - 0.21 * (c_dim / a_dim) * (1.0 - (c_dim ** 4) / (12.0 * a_dim ** 4))))
            G = Ec / (2.0 * (1.0 + nu))
            transfTag = 1 if is_x_dir else 2
            for idx in range(len(node_list) - 1):
                ops.element('elasticBeamColumn', beam_eleTag, node_list[idx], node_list[idx + 1], A, Ec, G, J, Iy, Iz,
                            transfTag)
                beam_eleTag += 1

        edge_left_nodes = [j + 1 for j in range(ny + 1)]
        edge_right_nodes = [nx * (ny + 1) + j + 1 for j in range(ny + 1)]
        edge_bot_nodes = [i * (ny + 1) + 1 for i in range(nx + 1)]
        edge_top_nodes = [i * (ny + 1) + ny + 1 for i in range(nx + 1)]

        if geom.edge_bottom.support == EdgeSupport.BEAM: add_beam_elements(edge_bot_nodes, geom.edge_bottom.beam_b,
                                                                           geom.edge_bottom.beam_h, True)
        if geom.edge_top.support == EdgeSupport.BEAM: add_beam_elements(edge_top_nodes, geom.edge_top.beam_b,
                                                                        geom.edge_top.beam_h, True)
        if geom.edge_left.support == EdgeSupport.BEAM: add_beam_elements(edge_left_nodes, geom.edge_left.beam_b,
                                                                         geom.edge_left.beam_h, False)
        if geom.edge_right.support == EdgeSupport.BEAM: add_beam_elements(edge_right_nodes, geom.edge_right.beam_b,
                                                                          geom.edge_right.beam_h, False)

        node_constraints = {i: [0, 0, 0, 0, 0, 0] for i in range(1, (nx + 1) * (ny + 1) + 1)}

        def apply_edge_bcs(node_list, condition, is_x_edge):
            for n in node_list:
                if condition.support == EdgeSupport.WALL: node_constraints[n][2] = 1
                if condition.continuity == EdgeContinuity.CONTINUOUS:
                    if not is_x_edge: node_constraints[n][3] = 1
                    if is_x_edge: node_constraints[n][4] = 1

        apply_edge_bcs(edge_left_nodes, geom.edge_left, True)
        apply_edge_bcs(edge_right_nodes, geom.edge_right, True)
        apply_edge_bcs(edge_bot_nodes, geom.edge_bottom, False)
        apply_edge_bcs(edge_top_nodes, geom.edge_top, False)

        supported_types = [EdgeSupport.WALL, EdgeSupport.BEAM, EdgeSupport.COLUMN]
        if geom.edge_left.support in supported_types or geom.edge_bottom.support in supported_types:
            node_constraints[1][2] = 1
        if geom.edge_left.support in supported_types or geom.edge_top.support in supported_types:
            node_constraints[ny + 1][2] = 1
        if geom.edge_right.support in supported_types or geom.edge_bottom.support in supported_types:
            node_constraints[nx * (ny + 1) + 1][2] = 1
        if geom.edge_right.support in supported_types or geom.edge_top.support in supported_types:
            node_constraints[(nx + 1) * (ny + 1)][2] = 1

        node_constraints[1][0] = 1
        node_constraints[1][1] = 1
        node_constraints[1][5] = 1

        for n, dofs in node_constraints.items():
            if any(dofs): ops.fix(n, *dofs)

        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        for i in range(nx + 1):
            for j in range(ny + 1):
                nTag = i * (ny + 1) + j + 1
                ax = dx if (0 < i < nx) else dx / 2.0
                ay = dy if (0 < j < ny) else dy / 2.0
                ops.load(nTag, 0.0, 0.0, -load_mpa * (ax * ay), 0.0, 0.0, 0.0)

        ops.system('BandSPD')
        ops.numberer('RCM')
        ops.constraints('Plain')
        ops.integrator('LoadControl', 1.0)
        ops.algorithm('Linear')
        ops.analysis('Static')
        if ops.analyze(1) != 0: raise Exception("OpenSees FEA Model failed to converge.")

        # Post-Processing
        W = np.zeros((nx + 1, ny + 1))
        MXX = np.zeros((nx + 1, ny + 1))
        MYY = np.zeros((nx + 1, ny + 1))
        MXY = np.zeros((nx + 1, ny + 1))
        MX_WA = np.zeros((nx + 1, ny + 1))
        MY_WA = np.zeros((nx + 1, ny + 1))

        m_x_pos, m_x_neg, m_y_pos, m_y_neg = 0.0, 0.0, 0.0, 0.0
        D = mod_slab * (Ec * h ** 3) / (12.0 * (1.0 - nu ** 2))

        def get_w(xi, yj):
            return ops.nodeDisp(xi * (ny + 1) + yj + 1, 3)

        def dw_dy(xi, yj):
            if yj == 0: return (get_w(xi, 1) - get_w(xi, 0)) / dy
            if yj == ny: return (get_w(xi, ny) - get_w(xi, ny - 1)) / dy
            return (get_w(xi, yj + 1) - get_w(xi, yj - 1)) / (2 * dy)

        for i in range(nx + 1):
            for j in range(ny + 1):
                n_c = i * (ny + 1) + j + 1
                wc = ops.nodeDisp(n_c, 3)
                W[i, j] = wc

                # Correct boundary curvature mirroring
                if i == 0:
                    wr = ops.nodeDisp(1 * (ny + 1) + j + 1, 3)
                    wl = wr if geom.edge_left.continuity == EdgeContinuity.CONTINUOUS else (2 * wc - wr)
                elif i == nx:
                    wl = ops.nodeDisp((nx - 1) * (ny + 1) + j + 1, 3)
                    wr = wl if geom.edge_right.continuity == EdgeContinuity.CONTINUOUS else (2 * wc - wl)
                else:
                    wl = ops.nodeDisp((i - 1) * (ny + 1) + j + 1, 3)
                    wr = ops.nodeDisp((i + 1) * (ny + 1) + j + 1, 3)

                if j == 0:
                    wt = ops.nodeDisp(i * (ny + 1) + 1 + 1, 3)
                    wb = wt if geom.edge_bottom.continuity == EdgeContinuity.CONTINUOUS else (2 * wc - wt)
                elif j == ny:
                    wb = ops.nodeDisp(i * (ny + 1) + (ny - 1) + 1, 3)
                    wt = wb if geom.edge_top.continuity == EdgeContinuity.CONTINUOUS else (2 * wc - wb)
                else:
                    wb = ops.nodeDisp(i * (ny + 1) + (j - 1) + 1, 3)
                    wt = ops.nodeDisp(i * (ny + 1) + (j + 1) + 1, 3)

                d2w_dx2 = (wl - 2 * wc + wr) / (dx ** 2)
                d2w_dy2 = (wb - 2 * wc + wt) / (dy ** 2)

                if i == 0:
                    w_xy = (dw_dy(1, j) - dw_dy(0, j)) / dx
                elif i == nx:
                    w_xy = (dw_dy(nx, j) - dw_dy(nx - 1, j)) / dx
                else:
                    w_xy = (dw_dy(i + 1, j) - dw_dy(i - 1, j)) / (2 * dx)

                mxx = D * (d2w_dx2 + nu * d2w_dy2) * 0.001
                myy = D * (d2w_dy2 + nu * d2w_dx2) * 0.001
                mxy = D * (1.0 - nu) * w_xy * 0.001

                MXX[i, j] = mxx
                MYY[i, j] = myy
                MXY[i, j] = mxy

                mx_bot, my_bot = mxx + abs(mxy), myy + abs(mxy)
                if myy < -abs(mxy) and myy != 0: mx_bot, my_bot = mxx + abs(mxy ** 2 / myy), 0.0
                if mxx < -abs(mxy) and mxx != 0: my_bot, mx_bot = myy + abs(mxy ** 2 / mxx), 0.0

                mx_top, my_top = mxx - abs(mxy), myy - abs(mxy)
                if myy > abs(mxy) and myy != 0: mx_top, my_top = mxx - abs(mxy ** 2 / myy), 0.0
                if mxx > abs(mxy) and mxx != 0: my_top, mx_top = myy - abs(mxy ** 2 / mxx), 0.0

                MX_WA[i, j] = mx_bot
                MY_WA[i, j] = my_bot

                if mx_bot > 0: m_x_pos = max(m_x_pos, mx_bot)
                if my_bot > 0: m_y_pos = max(m_y_pos, my_bot)
                if mx_top < 0: m_x_neg = max(m_x_neg, abs(mx_top))
                if my_top < 0: m_y_neg = max(m_y_neg, abs(my_top))

        # Compute Shears via Finite Difference (dx and dy converted to meters)
        VX = np.zeros((nx + 1, ny + 1))
        VY = np.zeros((nx + 1, ny + 1))
        dx_m, dy_m = dx / 1000.0, dy / 1000.0

        for i in range(nx + 1):
            for j in range(ny + 1):
                dMxx_dx = (MXX[min(i + 1, nx), j] - MXX[max(i - 1, 0), j]) / (dx_m if i == 0 or i == nx else 2 * dx_m)
                dMxy_dy = (MXY[i, min(j + 1, ny)] - MXY[i, max(j - 1, 0)]) / (dy_m if j == 0 or j == ny else 2 * dy_m)
                VX[i, j] = dMxx_dx + dMxy_dy

                dMyy_dy = (MYY[i, min(j + 1, ny)] - MYY[i, max(j - 1, 0)]) / (dy_m if j == 0 or j == ny else 2 * dy_m)
                dMxy_dx = (MXY[min(i + 1, nx), j] - MXY[max(i - 1, 0), j]) / (dx_m if i == 0 or i == nx else 2 * dx_m)
                VY[i, j] = dMyy_dy + dMxy_dx

        max_def = np.max(np.abs(W))
        grid_data = {'W': W, 'MXX': MXX, 'MYY': MYY, 'MXY': MXY, 'MX_WA': MX_WA, 'MY_WA': MY_WA, 'VX': VX, 'VY': VY}
        return SlabMoments(m_x_pos, m_x_neg, m_y_pos, m_y_neg), max_def, notes, grid_data

    def generate_contour_plots(self, geom: SlabGeometry, grid_data: dict) -> Dict[str, str]:
        x_lin = np.linspace(0, geom.length_x, grid_data['W'].shape[0])
        y_lin = np.linspace(0, geom.length_y, grid_data['W'].shape[1])
        X, Y = np.meshgrid(x_lin, y_lin, indexing='ij')

        plots = {}
        configs = [
            ('deflection', 'W', 'Deflection (mm)', 'viridis'),
            ('mxx', 'MXX', 'Mxx Bending (kN-m/m)', 'RdBu_r'),
            ('myy', 'MYY', 'Myy Bending (kN-m/m)', 'RdBu_r'),
            ('mxy', 'MXY', 'Mxy Twisting (kN-m/m)', 'PiYG'),
            ('mx_wa', 'MX_WA', 'Wood-Armer Mx Bot (kN-m/m)', 'Reds'),
            ('my_wa', 'MY_WA', 'Wood-Armer My Bot (kN-m/m)', 'Reds'),
            ('vx', 'VX', 'Shear Vx (kN/m)', 'coolwarm'),
            ('vy', 'VY', 'Shear Vy (kN/m)', 'coolwarm'),
        ]

        for key, grid_key, title, cmap in configs:
            Z = grid_data[grid_key]
            if key == 'deflection': Z = np.abs(Z)

            plt.figure(figsize=(5, 4.5))
            cs = plt.contourf(X, Y, Z, levels=20, cmap=cmap)
            plt.colorbar(cs)
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

    def design_flexural_reinforcement(self, moment: float, effective_depth: float, thickness: float,
                                      material_props: MaterialProperties, notes: List[str], label: str,
                                      preferred_bar: str = None) -> Tuple[str, float]:
        fc_prime, fy = material_props.fc_prime, material_props.fy
        width = 1000.0
        Mu = moment * 1e6

        rho_temp = 0.0020 if fy <= 420 else (0.0018 if fy <= 520 else max(0.0014, 0.0018 * 420.0 / fy))
        As_min = rho_temp * width * thickness

        if Mu <= 0: return self._select_slab_reinforcement(As_min, width, fy, thickness, preferred_bar)

        phi = self.phi_factors['flexure']
        A = phi * fy ** 2 / (2 * 0.85 * fc_prime * width)
        B = -phi * fy * effective_depth
        C = Mu

        discriminant = B ** 2 - 4 * A * C
        if discriminant < 0:
            notes.append(
                f"CRITICAL: {label} section is inadequate for applied moment ({moment:.1f} kN·m/m). Increase slab thickness.")
            As_required = -B / (2 * A)
        else:
            As_required = max((-B - math.sqrt(discriminant)) / (2 * A), As_min)

        return self._select_slab_reinforcement(As_required, width, fy, thickness, preferred_bar)

    def _select_slab_reinforcement(self, As_required: float, width: float, fy: float, thickness: float,
                                   preferred_bar: str = None) -> Tuple[str, float]:
        bar_sizes = ['D10', 'D12', 'D16', 'D20', 'D25', 'D28', 'D32', 'D36']
        if preferred_bar and preferred_bar in bar_sizes:
            bar_sizes = [preferred_bar] + [b for b in bar_sizes if b != preferred_bar]
        max_spacing = min(3 * thickness, 450.0)
        for bar_size in bar_sizes:
            bar_area = self.aci.get_bar_area(bar_size)
            spacing = bar_area * width / As_required
            db = self.aci.get_bar_diameter(bar_size)
            if (max(25.0, db) + db) <= spacing <= max_spacing:
                return bar_size, math.floor(spacing / 10.0) * 10.0
        if As_required > (self.aci.get_bar_area('D10') * width / max_spacing):
            bar = bar_sizes[-1]
            spacing = self.aci.get_bar_area(bar) * width / As_required
            return bar, max(40.0, math.floor(spacing / 10.0) * 10.0)
        else:
            return 'D10', math.floor(max_spacing / 10.0) * 10.0

    def calculate_cracked_deflection(self, gross_def_grid: np.ndarray, moments: SlabMoments, geometry: SlabGeometry,
                                     mat_props: MaterialProperties,
                                     reinforcement: Optional[SlabReinforcement] = None) -> Tuple[float, np.ndarray]:
        Ig = (1000.0 * geometry.thickness ** 3) / 12.0
        Mcr = (0.62 * math.sqrt(mat_props.fc_prime)) * Ig / (geometry.thickness / 2.0)
        # Using Positive moments to represent mid-span cracking driving deflection
        Ma = max(moments.moment_x_positive, moments.moment_y_positive) * 1e6

        if Ma <= Mcr: return np.max(np.abs(gross_def_grid)), gross_def_grid

        As = self._get_provided_as(reinforcement, geometry, mat_props.fy)
        rho = As / (1000.0 * geometry.effective_depth_x)
        n = 200000.0 / mat_props.ec
        k = math.sqrt(2 * rho * n + (rho * n) ** 2) - rho * n
        Icr = (1000.0 * k ** 3 * geometry.effective_depth_x ** 3) / 3.0 + n * As * (geometry.effective_depth_x * (1.0 - k)) ** 2

        # ACI 318M-25 §24.2.3.5
        if Ma <= (2.0 / 3.0) * Mcr:
            Ie = Ig
        else:
            factor_m = ((2.0 / 3.0) * Mcr / Ma) ** 2
            Ie = Icr / (1.0 - factor_m * (1.0 - Icr / Ig))
            Ie = max(Icr, min(Ie, Ig))
        cracked_grid = gross_def_grid * (Ig / Ie)
        return np.max(np.abs(cracked_grid)), cracked_grid

    def _calculate_minimum_slab_reinforcement(self, width: float, thickness: float, fy: float) -> float:
        rho_temp = 0.0020 if fy <= 420 else (0.0018 if fy <= 520 else max(0.0014, 0.0018 * 420.0 / fy))
        return rho_temp * width * thickness

    def _get_provided_as(self, reinforcement: Optional[SlabReinforcement], geometry: SlabGeometry, fy: float) -> float:
        """Return the governing bottom As (mm²/m) for deflection Icr calculation."""
        if reinforcement is not None:
            As_x = self.aci.get_bar_area(reinforcement.main_bars_x) * 1000.0 / reinforcement.main_spacing_x
            As_y = self.aci.get_bar_area(reinforcement.main_bars_y) * 1000.0 / reinforcement.main_spacing_y
            return max(As_x, As_y)
        # Fallback to minimum if reinforcement not yet designed
        return self._calculate_minimum_slab_reinforcement(1000, geometry.thickness, fy)

    def perform_complete_slab_design(self, geometry: SlabGeometry, loads: SlabLoads,
                                     material_props: MaterialProperties,
                                     preferred_bottom_bar: str = "D12",
                                     preferred_top_bar: str = "D12") -> SlabAnalysisResult:
        design_notes = ["Analysis performed using OpenSeesPy ShellMITC4 3D finite element model."]

        w_u_mpa = ((loads.self_weight + loads.superimposed_dead) * loads.load_factors.get('D',
                                                                                          1.2) + loads.live_load * loads.load_factors.get(
            'L', 1.6)) / 1000.0
        w_dead_mpa = (loads.self_weight + loads.superimposed_dead) / 1000.0
        w_sus_mpa = (loads.self_weight + loads.superimposed_dead + 0.5 * loads.live_load) / 1000.0
        w_tot_mpa = (loads.self_weight + loads.superimposed_dead + loads.live_load) / 1000.0

        # RUN 1: Ultimate Load
        moments, _, fea_notes, ult_grid = self._run_opensees_analysis(geometry, material_props, w_u_mpa,
                                                                      is_service=False)
        design_notes.extend(fea_notes)

        # RUN 2-4: Service Load Cases (dead, sustained, total)
        moments_d, _, _, d_grid = self._run_opensees_analysis(geometry, material_props, w_dead_mpa, is_service=True)
        moments_sus, _, _, sus_grid = self._run_opensees_analysis(geometry, material_props, w_sus_mpa, is_service=True)
        moments_tot, _, _, tot_grid = self._run_opensees_analysis(geometry, material_props, w_tot_mpa, is_service=True)

        # Design reinforcement BEFORE deflection check so Icr uses actual provided As
        bx, sx = self.design_flexural_reinforcement(moments.moment_x_positive, geometry.effective_depth_x,
                                                    geometry.thickness, material_props, design_notes, "+Mxx (Span X)",
                                                    preferred_bottom_bar)
        by, sy = self.design_flexural_reinforcement(moments.moment_y_positive, geometry.effective_depth_y,
                                                    geometry.thickness, material_props, design_notes, "+Myy (Span Y)",
                                                    preferred_bottom_bar)
        bxt, sxt = self.design_flexural_reinforcement(moments.moment_x_negative, geometry.effective_depth_x,
                                                      geometry.thickness, material_props, design_notes,
                                                      "-Mxx (Support X)", preferred_top_bar)
        byt, syt = self.design_flexural_reinforcement(moments.moment_y_negative, geometry.effective_depth_y,
                                                      geometry.thickness, material_props, design_notes,
                                                      "-Myy (Support Y)", preferred_top_bar)
        bsh, ssh = self._select_slab_reinforcement(
            self._calculate_minimum_slab_reinforcement(1000, geometry.thickness, material_props.fy), 1000,
            material_props.fy, geometry.thickness)

        reinf = SlabReinforcement(bx, sx, by, sy, bsh, ssh, bxt, sxt, byt, syt)

        # Deflection checks using actual provided reinforcement for Icr
        def_dead, _ = self.calculate_cracked_deflection(d_grid['W'], moments_d, geometry, material_props, reinf)
        def_sus, _ = self.calculate_cracked_deflection(sus_grid['W'], moments_sus, geometry, material_props, reinf)
        def_tot, cracked_def_grid = self.calculate_cracked_deflection(tot_grid['W'], moments_tot, geometry,
                                                                      material_props, reinf)

        def_live = max(0.0, def_tot - def_dead)
        def_long = def_live + 2.0 * def_sus

        # Override the ultimate W grid with cracked service deflection grid for the visual contour
        ult_grid['W'] = cracked_def_grid
        contour_b64s = self.generate_contour_plots(geometry, ult_grid)

        def calc_dcr(mu, b_bar, s_bar, d):
            if mu <= 0: return 0.0
            As = self.aci.get_bar_area(b_bar) * 1000 / s_bar
            a = (As * material_props.fy) / (0.85 * material_props.fc_prime * 1000.0)
            phi_mn = self.phi_factors['flexure'] * As * material_props.fy * (d - a / 2) / 1e6
            return mu / phi_mn if phi_mn > 0 else 99.9

        max_dcr = max(calc_dcr(moments.moment_x_positive, bx, sx, geometry.effective_depth_x),
                      calc_dcr(moments.moment_y_positive, by, sy, geometry.effective_depth_y),
                      calc_dcr(moments.moment_x_negative, bxt, sxt, geometry.effective_depth_x),
                      calc_dcr(moments.moment_y_negative, byt, syt, geometry.effective_depth_y))

        return SlabAnalysisResult(
            SlabType.FEA_MODEL, moments, reinf,
            def_live, def_long, max_dcr, design_notes, contour_b64s
        )

    def calculate_qto(self, geom: SlabGeometry, res: SlabAnalysisResult) -> dict:
        vol = (geom.length_x / 1000.0) * (geom.length_y / 1000.0) * (geom.thickness / 1000.0)
        fw = (geom.length_x / 1000.0) * (geom.length_y / 1000.0)

        COMMERCIAL_LENGTHS = [6000, 7500, 9000, 10500, 12000]
        LAP_SPLICE = 40
        HOOK_LEN = 12

        def _bar_weight(db_mm, length_m):
            return length_m * (db_mm ** 2 / 162.0)

        def _optimize_cutting_stock(bar_size, spacing, L_along, L_across, label):
            if bar_size == 'None' or spacing <= 0:
                return []
            db = float(bar_size.replace('D', ''))
            qty = math.ceil(L_across / spacing)
            if qty < 1:
                qty = 1
            straight_m = (L_along - 2 * geom.cover) / 1000.0
            if straight_m <= 0:
                return []

            hook_m = HOOK_LEN * db / 1000.0
            lap_m = LAP_SPLICE * db / 1000.0
            cut_len = straight_m + 2 * hook_m

            best = None
            for C_mm in COMMERCIAL_LENGTHS:
                C = C_mm / 1000.0
                if cut_len > C:
                    pieces_per_commercial = 0
                else:
                    pieces_per_commercial = int((C + lap_m) / (cut_len + lap_m))

                if pieces_per_commercial < 1:
                    continue

                n_commercial = math.ceil(qty / pieces_per_commercial)
                total_purchased = n_commercial * C
                total_splices = max(0, qty - pieces_per_commercial)
                total_used = qty * cut_len + total_splices * lap_m
                waste = total_purchased - total_used

                if best is None or waste < best['waste']:
                    best = {
                        'commercial_len_m': C,
                        'pieces_per_bar': pieces_per_commercial,
                        'n_commercial': n_commercial,
                        'waste': waste,
                    }

            if best is None:
                C = COMMERCIAL_LENGTHS[-1] / 1000.0
                pieces_per_commercial = max(1, int((C + lap_m) / (cut_len + lap_m)))
                n_commercial = math.ceil(qty / pieces_per_commercial)
                total_purchased = n_commercial * C
                total_splices = max(0, qty - pieces_per_commercial)
                total_used = qty * cut_len + total_splices * lap_m
                best = {
                    'commercial_len_m': C,
                    'pieces_per_bar': pieces_per_commercial,
                    'n_commercial': n_commercial,
                    'waste': total_purchased - total_used,
                }

            total_purchased = best['n_commercial'] * best['commercial_len_m']
            total_used = qty * cut_len + max(0, qty - best['pieces_per_bar']) * lap_m
            total_weight = _bar_weight(db, total_used)

            return [{
                'label': label,
                'bar': bar_size,
                'qty': qty,
                'each_len_m': round(cut_len, 2),
                'total_len_m': round(total_used, 1),
                'weight_kg': round(total_weight, 1),
                'splices': max(0, qty - best['pieces_per_bar']),
                'commercial_len_m': best['commercial_len_m'],
                'com_bars': best['n_commercial'],
                'waste_m': round(best['waste'], 2),
            }]

        items = []
        items.extend(_optimize_cutting_stock(
            res.reinforcement.main_bars_x, res.reinforcement.main_spacing_x,
            geom.length_x, geom.length_y, "Bottom X Bars"))
        items.extend(_optimize_cutting_stock(
            res.reinforcement.main_bars_y, res.reinforcement.main_spacing_y,
            geom.length_y, geom.length_x, "Bottom Y Bars"))
        items.extend(_optimize_cutting_stock(
            res.reinforcement.top_bars_x, res.reinforcement.top_spacing_x,
            geom.length_x, geom.length_y, "Top X Bars (Supports)"))
        items.extend(_optimize_cutting_stock(
            res.reinforcement.top_bars_y, res.reinforcement.top_spacing_y,
            geom.length_y, geom.length_x, "Top Y Bars (Supports)"))
        items.extend(_optimize_cutting_stock(
            res.reinforcement.shrinkage_bars, res.reinforcement.shrinkage_spacing,
            geom.length_x, geom.length_y, "Shrinkage Bars"))

        total_wt = sum(it['weight_kg'] for it in items) if items else 0.0

        return {'volume': vol, 'formwork': fw, 'weight': total_wt, 'cutting_list': items}