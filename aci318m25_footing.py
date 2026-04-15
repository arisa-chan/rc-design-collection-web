# -*- coding: utf-8 -*-

"""
ACI 318M-25 Footing Design Library with OpenSeesPy FEA
Building Code Requirements for Structural Concrete - Foundation Design
"""

import math
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import io
import base64
import matplotlib

matplotlib.use("Agg")
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
    mesh_nx: int = field(default=0, init=False)
    mesh_ny: int = field(default=0, init=False)

    def __post_init__(self):
        target_elem = 250.0  # mm, ~0.25 m
        self.mesh_nx = max(4, math.ceil(self.length / target_elem))
        self.mesh_ny = max(4, math.ceil(self.width / target_elem))


@dataclass
class SoilProperties:
    bearing_capacity: float  # kPa
    unit_weight: float = 18.0  # kN/m³
    soil_depth: float = 0.0  # mm, depth of soil above footing top
    friction_angle: float = 30.0  # degrees
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
    surcharge_dl: float = 0.0  # kPa, dead load surcharge on soil above footing
    surcharge_ll: float = 0.0  # kPa, live load surcharge on soil above footing


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
    overturning_ok: bool = True
    fs_overturning_x: float = 0.0
    fs_overturning_y: float = 0.0
    bearing_limit_used: float = 0.0
    detailed_calcs: Dict[str, str] = None
    fea_moment_x_pos: float = 0.0
    fea_moment_x_neg: float = 0.0
    fea_moment_y_pos: float = 0.0
    fea_moment_y_neg: float = 0.0
    one_way_shear_demand: float = 0.0
    one_way_shear_capacity: float = 0.0
    two_way_shear_demand: float = 0.0
    two_way_shear_capacity: float = 0.0


class ACI318M25FootingDesign:
    def __init__(self):
        self.aci = ACI318M25()
        self.phi_factors = {"flexure": 0.90, "shear": 0.75, "bearing": 0.65}

    def _run_opensees_analysis(
        self,
        geom: FootingGeometry,
        loads: FootingLoads,
        soil: SoilProperties,
        mat_props: MaterialProperties,
        is_service: bool = False,
    ) -> Tuple[dict, List[str]]:
        notes = []
        if not OPENSEES_AVAILABLE:
            raise ImportError("OpenSeesPy is required.")

        ops.wipe()
        ops.model("basic", "-ndm", 3, "-ndf", 6)

        Ec = mat_props.ec
        nu = 0.2
        h = geom.thickness

        # ShellMITC4 — fine mesh for accuracy (40x40 = 1600 elements)
        ops.nDMaterial("ElasticIsotropic", 1, Ec, nu)
        ops.section("ElasticMembranePlateSection", 1, Ec, nu, h, 0.0)

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

        # ShellMITC4 elements
        eleTag = 1
        eleTags = {}  # (i,j) -> eleTag for force extraction
        for i in range(nx):
            for j in range(ny):
                n1 = nodeTags[(i, j)]
                n2 = nodeTags[(i + 1, j)]
                n3 = nodeTags[(i + 1, j + 1)]
                n4 = nodeTags[(i, j + 1)]
                ops.element("ShellMITC4", eleTag, n1, n2, n3, n4, 1)
                eleTags[(i, j)] = eleTag
                eleTag += 1

        # Compression-only Soil Springs
        ks_mpa_mm = geom.soil_modulus * 1e-6  # Convert kN/m³ to N/mm³ (MPa/mm)
        matTag_spring = 100

        for i in range(nx + 1):
            for j in range(ny + 1):
                ax = dx if (0 < i < nx) else dx / 2.0
                ay = dy if (0 < j < ny) else dy / 2.0
                trib_area = ax * ay  # mm²

                k_spring = ks_mpa_mm * trib_area  # N/mm
                if k_spring < 1e-9:
                    continue

                spring_mat = matTag_spring + nodeTags[(i, j)]
                ops.uniaxialMaterial("ENT", spring_mat, k_spring)

                support_tag = nodeTags[(i, j)] + 10000
                ops.node(support_tag, i * dx - Lx / 2.0, j * dy - Ly / 2.0, 0.0)
                ops.fix(support_tag, 1, 1, 1, 1, 1, 1)

                ops.element(
                    "zeroLength",
                    eleTag,
                    support_tag,
                    nodeTags[(i, j)],
                    "-mat",
                    spring_mat,
                    "-dir",
                    3,
                )
                eleTag += 1

        # Torsional stability constraint
        ops.fix(nodeTags[(nx // 2, ny // 2)], 1, 1, 0, 0, 0, 1)

        # Apply Column Loads via Rigid Spider
        col_x, col_y = geom.ecc_x, geom.ecc_y
        master_node = 99999
        ops.node(master_node, col_x, col_y, 0.0)

        cw, cd = geom.column_width, geom.column_depth
        footprint_nodes = []
        for (i, j), tag in nodeTags.items():
            x = i * dx - Lx / 2.0
            y = j * dy - Ly / 2.0
            if abs(x - col_x) <= cw / 2.0 and abs(y - col_y) <= cd / 2.0:
                footprint_nodes.append(tag)

        if not footprint_nodes:
            min_dist, best_node = float("inf"), None
            for (i, j), tag in nodeTags.items():
                x = i * dx - Lx / 2.0
                y = j * dy - Ly / 2.0
                d = math.hypot(x - col_x, y - col_y)
                if d < min_dist:
                    min_dist, best_node = d, tag
            footprint_nodes.append(best_node)

        for fn in footprint_nodes:
            ops.rigidLink("beam", master_node, fn)

        # Apply Loads
        P = loads.service_axial if is_service else loads.axial_force
        Mx = loads.service_moment_x if is_service else loads.moment_x
        My = loads.service_moment_y if is_service else loads.moment_y

        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        ops.load(master_node, 0.0, 0.0, -P * 1000.0, Mx * 1e6, My * 1e6, 0.0)

        # Self-weight of footing
        w_sw = 24e-6 * h  # N/mm²
        factor = 1.0 if is_service else 1.2
        for (i, j), tag in nodeTags.items():
            ax = dx if (0 < i < nx) else dx / 2.0
            ay = dy if (0 < j < ny) else dy / 2.0
            ops.load(tag, 0.0, 0.0, -w_sw * (ax * ay) * factor, 0.0, 0.0, 0.0)

        # Soil above footing (dead load) + surcharge as uniform downward pressure
        if soil.soil_depth > 0 or loads.surcharge_dl > 0 or loads.surcharge_ll > 0:
            soil_pressure = soil.unit_weight * (soil.soil_depth / 1000.0)  # kPa
            surcharge = loads.surcharge_dl  # kPa (service-level DL surcharge)
            if not is_service:
                # Apply load factors: 1.2 for DL surcharge, 1.6 for LL surcharge
                soil_pressure *= 1.2
                surcharge = loads.surcharge_dl * 1.2 + loads.surcharge_ll * 1.6
            total_overburden = soil_pressure + surcharge  # kPa = kN/m² = 0.001 N/mm²
            overburden_n_mm2 = total_overburden * 0.001  # kPa -> N/mm²
            for (i, j), tag in nodeTags.items():
                ax = dx if (0 < i < nx) else dx / 2.0
                ay = dy if (0 < j < ny) else dy / 2.0
                ops.load(tag, 0.0, 0.0, -overburden_n_mm2 * (ax * ay), 0.0, 0.0, 0.0)

        # Analysis settings
        ops.system("UmfPack")
        ops.numberer("RCM")
        ops.constraints("Transformation")
        ops.test("NormDispIncr", 1.0e-6, 50, 0)
        ops.algorithm("Newton")
        ops.integrator("LoadControl", 0.1)
        ops.analysis("Static")

        ok = ops.analyze(10)
        if ok != 0:
            notes.append("⚠️ FEA convergence difficulty; results should be verified.")

        # Extract Results
        W = np.zeros((nx + 1, ny + 1))
        MXX = np.zeros((nx + 1, ny + 1))
        MYY = np.zeros((nx + 1, ny + 1))
        MXY = np.zeros((nx + 1, ny + 1))
        Q_SOIL = np.zeros((nx + 1, ny + 1))

        def get_w(xi, yj):
            return ops.nodeDisp(xi * (ny + 1) + yj + 1, 3)

        for i in range(nx + 1):
            for j in range(ny + 1):
                n_c = i * (ny + 1) + j + 1
                wc = ops.nodeDisp(n_c, 3)
                W[i, j] = wc

                if wc < 0:
                    Q_SOIL[i, j] = abs(wc) * ks_mpa_mm * 1000.0

        # Moments from soil pressure integration (classical footing method)
        # M at node (i,j) = integral of q * lever_arm from that point to the *nearest* edge
        # This represents the cantilever moment for the footing strip
        # Q_SOIL is in kPa (= kN/m²), dx_m/dy_m are in meters
        # Result: kN/m² * m * m = kN-m/m
        dx_m = dx / 1000.0  # mm -> m
        dy_m = dy / 1000.0

        for j in range(ny + 1):
            for i in range(nx + 1):
                # Mxx: bending in x-direction
                # Distance to left edge and right edge
                dist_to_left = i * dx_m
                dist_to_right = (nx - i) * dx_m

                if dist_to_left <= dist_to_right:
                    # Integrate to left edge (near edge)
                    mx = 0.0
                    for k in range(i, 0, -1):
                        q_avg = (Q_SOIL[k, j] + Q_SOIL[k - 1, j]) / 2.0
                        dist = (i - k + 0.5) * dx_m
                        mx += q_avg * dx_m * dist
                else:
                    # Integrate to right edge (near edge)
                    mx = 0.0
                    for k in range(i, nx):
                        q_avg = (Q_SOIL[k, j] + Q_SOIL[k + 1, j]) / 2.0
                        dist = (k - i + 0.5) * dx_m
                        mx += q_avg * dx_m * dist

                MXX[i, j] = mx

        for i in range(nx + 1):
            for j in range(ny + 1):
                # Myy: bending in y-direction
                dist_to_bot = j * dy_m
                dist_to_top = (ny - j) * dy_m

                if dist_to_bot <= dist_to_top:
                    my = 0.0
                    for k in range(j, 0, -1):
                        q_avg = (Q_SOIL[i, k] + Q_SOIL[i, k - 1]) / 2.0
                        dist = (j - k + 0.5) * dy_m
                        my += q_avg * dy_m * dist
                else:
                    my = 0.0
                    for k in range(j, ny):
                        q_avg = (Q_SOIL[i, k] + Q_SOIL[i, k + 1]) / 2.0
                        dist = (k - j + 0.5) * dy_m
                        my += q_avg * dy_m * dist

                MYY[i, j] = my

        # Twisting moment Mxy from displacement cross-curvature (plate theory)
        # Mxy = -D*(1-nu) * d²w/dxdy
        # Use the smooth FEA displacement field for this
        D_plate = (Ec * h**3) / (12.0 * (1.0 - nu**2))  # N-mm
        for i in range(1, nx):
            for j in range(1, ny):
                wbl = get_w(i - 1, j - 1)
                wbr = get_w(i + 1, j - 1)
                wtl = get_w(i - 1, j + 1)
                wtr = get_w(i + 1, j + 1)
                d2w_dxdy = (wtr - wtl - wbr + wbl) / (4.0 * dx * dy)
                MXY[i, j] = -D_plate * (1.0 - nu) * d2w_dxdy * 0.001  # N-mm -> kN-m/m

        # Extrapolate Mxy to edges
        for i in range(nx + 1):
            MXY[i, 0] = MXY[i, 1]
            MXY[i, ny] = MXY[i, ny - 1]
        for j in range(ny + 1):
            MXY[0, j] = MXY[1, j]
            MXY[nx, j] = MXY[nx - 1, j]

        # Shear from soil pressure integration (physically correct for footings)
        # Vx = integral of soil pressure from edge to section, per unit width
        # Vy = integral of soil pressure from edge to section, per unit width
        VX = np.zeros((nx + 1, ny + 1))
        VY = np.zeros((nx + 1, ny + 1))

        dx_m = dx / 1000.0  # element width in meters
        dy_m = dy / 1000.0  # element width in meters

        for j in range(ny + 1):
            vx_left = 0.0
            vx_right = 0.0
            for i in range(nx + 1):
                q = Q_SOIL[i, j]  # kPa = kN/m²
                vx_left += q * dx_m  # kN/m² * m = kN/m
                VX[i, j] = vx_left
            for i in range(nx, -1, -1):
                q = Q_SOIL[i, j]
                vx_right += q * dx_m
                VX[i, j] = max(VX[i, j], vx_right)

        for i in range(nx + 1):
            vy_bot = 0.0
            vy_top = 0.0
            for j in range(ny + 1):
                q = Q_SOIL[i, j]
                vy_bot += q * dy_m
                VY[i, j] = vy_bot
            for j in range(ny, -1, -1):
                q = Q_SOIL[i, j]
                vy_top += q * dy_m
                VY[i, j] = max(VY[i, j], vy_top)

        res_data = {
            "W": W,
            "MXX": MXX,
            "MYY": MYY,
            "MXY": MXY,
            "VX": VX,
            "VY": VY,
            "Q_SOIL": Q_SOIL,
        }
        return res_data, notes

    def generate_contour_plots(
        self,
        geom: FootingGeometry,
        grid_data: dict,
        mat: MaterialProperties = None,
        d_eff: float = None,
        keys_only: list = None,
    ) -> Dict[str, str]:
        x_lin = np.linspace(-geom.length / 2, geom.length / 2, grid_data["W"].shape[0])
        y_lin = np.linspace(-geom.width / 2, geom.width / 2, grid_data["W"].shape[1])
        X, Y = np.meshgrid(x_lin, y_lin, indexing="ij")

        MXX = grid_data["MXX"]
        MYY = grid_data["MYY"]
        MXY = grid_data.get("MXY", np.zeros_like(MXX))

        MXY_abs = np.abs(MXY)
        wa_mx = MXX + MXY_abs
        wa_my = MYY + MXY_abs
        wa_mx_top = np.minimum(MXX - MXY_abs, 0)
        wa_my_top = np.minimum(MYY - MXY_abs, 0)

        plots = {}

        def _compute_as(moment_grid):
            if mat is None or d_eff is None:
                return np.zeros_like(moment_grid)
            As = np.zeros_like(moment_grid)
            rho_min = 0.0018
            As_min = rho_min * 1000 * geom.thickness
            phi = 0.90
            for i in range(moment_grid.shape[0]):
                for j in range(moment_grid.shape[1]):
                    M = moment_grid[i, j]
                    if M <= 0:
                        As[i, j] = As_min
                        continue
                    A = phi * mat.fy**2 / (2 * 0.85 * mat.fc_prime * 1000)
                    B = -phi * mat.fy * d_eff
                    C = M * 1e6
                    disc = B**2 - 4 * A * C
                    if disc < 0:
                        As[i, j] = As_min * 2
                    else:
                        As[i, j] = max((-B - math.sqrt(disc)) / (2 * A), As_min)
            return As

        as_bot = _compute_as(np.maximum(wa_mx, wa_my)) if mat else None
        as_top = _compute_as(np.abs(np.minimum(wa_mx_top, wa_my_top))) if mat else None

        all_configs = {
            "soil_pressure": (grid_data["Q_SOIL"], "Bearing Pressure (kPa)", "YlOrRd"),
            "settlement": (grid_data["W"], "Settlement (mm)", "viridis"),
            "mxx": (MXX, "Mxx Bending (kN-m/m)", "RdBu_r"),
            "myy": (MYY, "Myy Bending (kN-m/m)", "RdBu_r"),
            "mxy": (MXY, "Mxy Twisting (kN-m/m)", "RdBu_r"),
            "vx": (grid_data["VX"], "Shear Vx (kN/m)", "coolwarm"),
            "vy": (grid_data["VY"], "Shear Vy (kN/m)", "coolwarm"),
            "wa_mx": (wa_mx, "Wood-Armer Mx* (kN-m/m)", "RdBu_r"),
            "wa_my": (wa_my, "Wood-Armer My* (kN-m/m)", "RdBu_r"),
            "as_bot": (as_bot, "Req. As Bottom (mm²/m)", "YlOrRd"),
            "as_top": (as_top, "Req. As Top (mm²/m)", "YlOrRd"),
        }

        keys_to_render = keys_only if keys_only else list(all_configs.keys())

        for key in keys_to_render:
            if key not in all_configs:
                continue
            Z, title, cmap = all_configs[key]
            if Z is None:
                continue
            plt.figure(figsize=(5, 4.5))
            cs = plt.contourf(X, Y, Z, levels=12, cmap=cmap)
            plt.colorbar(cs)

            cw, cd = geom.column_width, geom.column_depth
            cx, cy = geom.ecc_x, geom.ecc_y
            plt.plot(
                [cx - cw / 2, cx + cw / 2, cx + cw / 2, cx - cw / 2, cx - cw / 2],
                [cy - cd / 2, cy - cd / 2, cy + cd / 2, cy + cd / 2, cy - cd / 2],
                "k-",
                linewidth=2,
            )

            plt.title(title, fontsize=12, fontweight="bold", color="#111827")
            plt.xlabel("X (mm)")
            plt.ylabel("Y (mm)")
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=80)
            plt.close()
            buf.seek(0)
            plots[key] = base64.b64encode(buf.read()).decode("utf-8")
        return plots

    def check_two_way_shear(
        self,
        geom: FootingGeometry,
        loads: FootingLoads,
        mat: MaterialProperties,
        d_eff: float = None,
    ) -> Tuple[bool, float, float, float]:
        """Two-way (punching) shear check with eccentric moment transfer per ACI 318M-25 §22.6.5."""
        fc_prime = mat.fc_prime
        d = d_eff if d_eff is not None else geom.thickness - geom.cover - 20

        c1 = geom.column_width  # column dimension in x
        c2 = geom.column_depth  # column dimension in y
        b1 = c1 + d  # critical section in x
        b2 = c2 + d  # critical section in y
        bo = 2 * b1 + 2 * b2

        # Concentric shear demand
        bearing_area = geom.length * geom.width / 1e6
        qu = loads.axial_force / bearing_area
        critical_area = b1 * b2 / 1e6
        Vu = loads.axial_force - qu * critical_area

        # Concentric shear stress
        vu_concentric = Vu * 1000.0 / (bo * d) if (bo * d) > 0 else 0.0  # MPa

        # Eccentric moment transfer (ACI §8.4.4.2)
        # gamma_f = fraction transferred by flexure; gamma_v = 1 - gamma_f by eccentricity of shear
        gamma_fx = 1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b1 / b2)) if b2 > 0 else 0.5
        gamma_vx = 1.0 - gamma_fx
        gamma_fy = 1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b2 / b1)) if b1 > 0 else 0.5
        gamma_vy = 1.0 - gamma_fy

        # Polar moment property Jc for each moment direction (interior column)
        Jc_x = (d * b2**3 / 6.0) + (b2 * d**3 / 6.0) + (d * b1 * b2**2 / 2.0)
        c_AB_x = b2 / 2.0
        Jc_y = (d * b1**3 / 6.0) + (b1 * d**3 / 6.0) + (d * b2 * b1**2 / 2.0)
        c_AB_y = b1 / 2.0

        Mux = abs(loads.moment_x)  # kN-m
        Muy = abs(loads.moment_y)  # kN-m
        vu_Mx = gamma_vx * Mux * 1e6 * c_AB_x / Jc_x if Jc_x > 0 else 0.0  # MPa
        vu_My = gamma_vy * Muy * 1e6 * c_AB_y / Jc_y if Jc_y > 0 else 0.0  # MPa

        vu_max = vu_concentric + vu_Mx + vu_My  # MPa

        # Concrete shear strength (ACI Table 22.6.5.2)
        beta = max(c1, c2) / min(c1, c2)
        alphas = 40  # interior column
        vc1 = 0.17 * (1 + 2 / beta) * math.sqrt(fc_prime)
        vc2 = 0.083 * (alphas * d / bo + 2) * math.sqrt(fc_prime)
        vc3 = 0.33 * math.sqrt(fc_prime)
        vc = min(vc1, vc2, vc3)

        phi_vc = self.phi_factors["shear"] * vc  # MPa
        phi_Vn = phi_vc * bo * d / 1000.0  # kN (equivalent concentric capacity)

        # Equivalent demand and ratio (stress-based including eccentricity)
        Vu_equiv = vu_max * bo * d / 1000.0  # kN
        ratio = vu_max / phi_vc if phi_vc > 0 else 99.9
        return ratio <= 1.0, ratio, Vu_equiv, phi_Vn

    def _generate_detailed_calcs(
        self,
        geom,
        loads,
        soil,
        mat,
        is_transient,
        qmax,
        qmin,
        bearing_limit,
        bearing_ok,
        net_qa,
        M_x_pos,
        M_x_neg,
        M_y_pos,
        M_y_neg,
        V_x,
        V_y,
        bx,
        sx,
        by,
        sy,
        tx,
        stx,
        ty,
        sty,
        d_eff,
        d_eff_top,
        As_min,
        one_way_ok,
        one_way_ratio,
        phi_vc,
        two_way_ok,
        two_way_ratio,
        fs_ot_x,
        fs_ot_y,
        overturning_ok,
        ot_limit,
        W_footing,
        W_soil,
        P_total,
        sliding_resistance,
        Ka,
    ):
        calcs = {}
        L = geom.length / 1000.0
        B = geom.width / 1000.0
        h = geom.thickness
        A = L * B
        Ix = B * L**3 / 12.0
        Iy = L * B**3 / 12.0
        ex = geom.ecc_x / 1000.0
        ey = geom.ecc_y / 1000.0
        P = loads.service_axial
        Mx = loads.service_moment_x
        My = loads.service_moment_y

        calcs["bearing"] = (
            f"<h3>Soil Bearing Pressure Check</h3>"
            f"<p>Net allowable bearing pressure accounts for soil overburden:</p>"
            f"$$q_{{a,net}} = q_a - \\gamma_{{soil}} \\cdot D = {soil.bearing_capacity:.0f} - {soil.unit_weight:.1f} \\times {soil.soil_depth / 1000:.3f} = {net_qa:.1f} \\text{{ kPa}}$$"
            f"{'<p>Transient case: $q_{{a,net}} \\times 1.33 = ' + f'{bearing_limit:.1f}' + ' \\text{ kPa}$</p>' if is_transient else ''}"
            f"<p><strong>Maximum pressure (from FEA):</strong> $q_{{max}} = {qmax:.1f}$ kPa</p>"
            f"<p><strong>Minimum pressure (from FEA):</strong> $q_{{min}} = {qmin:.1f}$ kPa</p>"
            f"<p><strong>Check:</strong> $q_{{max}} = {qmax:.1f} \\leq q_{{a,net}} = {bearing_limit:.1f}$ kPa "
            f"$\\rightarrow$ <strong>{'PASS' if bearing_ok else 'FAIL'}</strong></p>"
        )

        calcs["flexure_bot"] = (
            f"<h3>Flexural Design — Bottom Reinforcement</h3>"
            f"<p>From FEA analysis, the maximum positive moments per unit width are:</p>"
            f"<ul>"
            f"<li>$M_{{x,pos}} = {M_x_pos:.2f}$ kN-m/m</li>"
            f"<li>$M_{{y,pos}} = {M_y_pos:.2f}$ kN-m/m</li>"
            f"</ul>"
            f"<p>Effective depth: $d = {d_eff:.0f}$ mm (averaged for two orthogonal bar layers)</p>"
            f"<p>Minimum reinforcement ratio (ACI 318M-25 §7.6.1.1): $\\rho_{{min}} = 0.0018$</p>"
            f"$$A_{{s,min}} = \\rho_{{min}} \\cdot b \\cdot h = 0.0018 \\times 1000 \\times {geom.thickness} = {As_min:.0f} \\text{{ mm²/m}}$$"
            f"<p>Required steel area from moment equilibrium:</p>"
            f"$$A_s = \\frac{{-B - \\sqrt{{B^2 - 4AC}}}}{{2A}}$$"
            f"<p>Where $A = \\frac{{\\phi f_y^2}}{{1.7 f'_c}}$, $B = -\\phi f_y d$, $C = M_u \\times 10^6$</p>"
            f"<p><strong>X-direction (bottom):</strong></p>"
            f"<ul>"
            f"<li>$M_u = {M_x_pos:.2f}$ kN-m/m</li>"
            f"<li>$A_{{s,req}} = $ computed from quadratic formula</li>"
            f"<li>Provided: <strong>{bx} @ {sx:.0f} mm</strong></li>"
            f"</ul>"
            f"<p><strong>Y-direction (bottom):</strong></p>"
            f"<ul>"
            f"<li>$M_u = {M_y_pos:.2f}$ kN-m/m</li>"
            f"<li>$A_{{s,req}} = $ computed from quadratic formula</li>"
            f"<li>Provided: <strong>{by} @ {sy:.0f} mm</strong></li>"
            f"</ul>"
        )

        calcs["flexure_top"] = (
            f"<h3>Flexural Design — Top Reinforcement</h3>"
            f"<p>From FEA analysis, the maximum negative moments per unit width are:</p>"
            f"<ul>"
            f"<li>$M_{{x,neg}} = {M_x_neg:.2f}$ kN-m/m</li>"
            f"<li>$M_{{y,neg}} = {M_y_neg:.2f}$ kN-m/m</li>"
            f"</ul>"
            f"<p>Effective depth (top): $d_{{top}} = {d_eff_top:.0f}$ mm</p>"
            f"<p><strong>X-direction (top):</strong></p>"
            f"<ul>"
            f"<li>$M_u = {M_x_neg:.2f}$ kN-m/m</li>"
            f"<li>Provided: <strong>{tx if tx else 'None'} @ {stx if tx else 0:.0f} mm</strong></li>"
            f"</ul>"
            f"<p><strong>Y-direction (top):</strong></p>"
            f"<ul>"
            f"<li>$M_u = {M_y_neg:.2f}$ kN-m/m</li>"
            f"<li>Provided: <strong>{ty if ty else 'None'} @ {sty if ty else 0:.0f} mm</strong></li>"
            f"</ul>"
        )

        calcs["shear_1way"] = (
            f"<h3>One-Way Shear Check</h3>"
            f"<p>From FEA, maximum shear forces per unit width:</p>"
            f"<ul>"
            f"<li>$V_x = {V_x:.1f}$ kN/m</li>"
            f"<li>$V_y = {V_y:.1f}$ kN/m</li>"
            f"</ul>"
            f"<p>Concrete shear capacity (ACI 318M-25 §22.5.5.1):</p>"
            f"$$\\phi V_c = \\phi \\cdot 0.17 \\sqrt{{f'_c}} \\cdot b \\cdot d$$"
            f"$$\\phi V_c = 0.75 \\times 0.17 \\times \\sqrt{{{mat.fc_prime}}} \\times 1000 \\times {d_eff} / 1000 = {phi_vc:.1f} \\text{{ kN/m}}$$"
            f"<p><strong>Check:</strong> $V_{{max}} = {max(V_x, V_y):.1f} \\leq \\phi V_c = {phi_vc:.1f}$ kN/m "
            f"$\\rightarrow$ <strong>{'PASS' if one_way_ok else 'FAIL'}</strong> (DCR = {one_way_ratio:.2f})</p>"
        )

        c1_2w = geom.column_width
        c2_2w = geom.column_depth
        b1_2w = c1_2w + d_eff
        b2_2w = c2_2w + d_eff
        bo = 2 * b1_2w + 2 * b2_2w
        beta = max(c1_2w, c2_2w) / min(c1_2w, c2_2w)
        bearing_area = geom.length * geom.width / 1e6
        qu = loads.axial_force / bearing_area
        critical_area = b1_2w * b2_2w / 1e6
        Vu = loads.axial_force - qu * critical_area
        vu_conc = Vu * 1000.0 / (bo * d_eff) if (bo * d_eff) > 0 else 0.0

        # Eccentric moment transfer for detailed calcs
        gamma_fx_dc = (
            1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b1_2w / b2_2w)) if b2_2w > 0 else 0.5
        )
        gamma_vx_dc = 1.0 - gamma_fx_dc
        gamma_fy_dc = (
            1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b2_2w / b1_2w)) if b1_2w > 0 else 0.5
        )
        gamma_vy_dc = 1.0 - gamma_fy_dc
        Jc_x_dc = (
            (d_eff * b2_2w**3 / 6.0)
            + (b2_2w * d_eff**3 / 6.0)
            + (d_eff * b1_2w * b2_2w**2 / 2.0)
        )
        Jc_y_dc = (
            (d_eff * b1_2w**3 / 6.0)
            + (b1_2w * d_eff**3 / 6.0)
            + (d_eff * b2_2w * b1_2w**2 / 2.0)
        )
        c_AB_x_dc = b2_2w / 2.0
        c_AB_y_dc = b1_2w / 2.0
        vu_Mx_dc = (
            gamma_vx_dc * abs(loads.moment_x) * 1e6 * c_AB_x_dc / Jc_x_dc
            if Jc_x_dc > 0
            else 0.0
        )
        vu_My_dc = (
            gamma_vy_dc * abs(loads.moment_y) * 1e6 * c_AB_y_dc / Jc_y_dc
            if Jc_y_dc > 0
            else 0.0
        )
        vu_max_dc = vu_conc + vu_Mx_dc + vu_My_dc

        vc1 = 0.17 * (1 + 2 / beta) * math.sqrt(mat.fc_prime)
        vc2 = 0.083 * (40 * d_eff / bo + 2) * math.sqrt(mat.fc_prime)
        vc3 = 0.33 * math.sqrt(mat.fc_prime)
        vc = min(vc1, vc2, vc3)
        phi_vc_2w = 0.75 * vc
        phi_Vn = phi_vc_2w * bo * d_eff / 1000

        calcs["shear_2way"] = (
            f"<h3>Two-Way (Punching) Shear Check</h3>"
            f"<p>Critical perimeter at $d/2$ from column face:</p>"
            f"$$b_o = 2(c_1 + d) + 2(c_2 + d) = 2({c1_2w} + {d_eff:.0f}) + 2({c2_2w} + {d_eff:.0f}) = {bo:.0f} \\text{{ mm}}$$"
            f"<p>Concentric shear stress:</p>"
            f"$$v_{{u,conc}} = \\frac{{V_u}}{{b_o d}} = \\frac{{{Vu * 1000:.0f}}}{{{bo:.0f} \\times {d_eff:.0f}}} = {vu_conc:.3f} \\text{{ MPa}}$$"
            f"<p>Eccentric moment transfer (ACI §8.4.4.2):</p>"
            f"$$\\gamma_{{vx}} = {gamma_vx_dc:.3f}, \\quad \\gamma_{{vy}} = {gamma_vy_dc:.3f}$$"
            f"$$v_{{u,Mx}} = \\frac{{\\gamma_{{vx}} M_{{ux}} c}}{{J_c}} = {vu_Mx_dc:.3f} \\text{{ MPa}}, \\quad v_{{u,My}} = {vu_My_dc:.3f} \\text{{ MPa}}$$"
            f"$$v_{{u,max}} = {vu_conc:.3f} + {vu_Mx_dc:.3f} + {vu_My_dc:.3f} = {vu_max_dc:.3f} \\text{{ MPa}}$$"
            f"<p>Concrete shear strength (ACI 318M-25 §22.6.5.2):</p>"
            f"$$v_{{c1}} = 0.17\\left(1 + \\frac{{2}}{{\\beta}}\\right)\\sqrt{{f'_c}} = {vc1:.3f} \\text{{ MPa}}$$"
            f"$$v_{{c2}} = 0.083\\left(\\frac{{\\alpha_s d}}{{b_o}} + 2\\right)\\sqrt{{f'_c}} = {vc2:.3f} \\text{{ MPa}}$$"
            f"$$v_{{c3}} = 0.33\\sqrt{{f'_c}} = {vc3:.3f} \\text{{ MPa}}$$"
            f"$$v_c = \\min(v_{{c1}}, v_{{c2}}, v_{{c3}}) = {vc:.3f} \\text{{ MPa}}$$"
            f"$$\\phi v_c = 0.75 \\times {vc:.3f} = {phi_vc_2w:.3f} \\text{{ MPa}}$$"
            f"<p><strong>Check:</strong> $v_{{u,max}} = {vu_max_dc:.3f} \\leq \\phi v_c = {phi_vc_2w:.3f}$ MPa "
            f"$\\rightarrow$ <strong>{'PASS' if two_way_ok else 'FAIL'}</strong> (DCR = {two_way_ratio:.2f})</p>"
        )

        H_applied_dc = math.sqrt(loads.shear_x**2 + loads.shear_y**2)
        calcs["overturning"] = (
            f"<h3>Overturning Stability Check</h3>"
            f"<p>Resisting moment from total vertical load:</p>"
            f"$$W_{{footing}} = \\gamma_c \\cdot L \\cdot B \\cdot h = 24.0 \\times {L:.2f} \\times {B:.2f} \\times {h / 1000:.3f} = {W_footing:.1f} \\text{{ kN}}$$"
            f"{'$$W_{{soil}} = \\gamma_{{soil}} \\cdot L \\cdot B \\cdot D_{{soil}} = ' + f'{soil.unit_weight:.1f} \\times {L:.2f} \\times {B:.2f} \\times {soil.soil_depth / 1000:.3f} = {W_soil:.1f}' + ' \\text{ kN}$$' if soil.soil_depth > 0 else ''}"
            f"$$P_{{total}} = P_{{service}} + W_{{footing}} {'+ W_{{soil}}' if soil.soil_depth > 0 else ''} = {P:.1f} + {W_footing:.1f}{' + ' + f'{W_soil:.1f}' if soil.soil_depth > 0 else ''} = {P_total:.1f} \\text{{ kN}}$$"
            f"<p><strong>About X-axis:</strong></p>"
            f"$$M_{{R,x}} = P_{{total}} \\cdot \\frac{{B}}{{2}} = {P_total:.1f} \\times \\frac{{{B:.2f}}}{{2}} = {P_total * B / 2:.1f} \\text{{ kN-m}}$$"
            f"$$M_{{O,x}} = |M_x| + |V_x| \\cdot h = |{loads.service_moment_x:.1f}| + |{loads.shear_x:.1f}| \\times {h / 1000:.3f} = {abs(loads.service_moment_x) + abs(loads.shear_x) * h / 1000:.1f} \\text{{ kN-m}}$$"
            f"$$FS_x = \\frac{{M_{{R,x}}}}{{M_{{O,x}}}} = \\frac{{{P_total * B / 2:.1f}}}{{{abs(loads.service_moment_x) + abs(loads.shear_x) * h / 1000:.1f}}} = {fs_ot_x:.2f}$$"
            f"<p><strong>About Y-axis:</strong></p>"
            f"$$M_{{R,y}} = P_{{total}} \\cdot \\frac{{L}}{{2}} = {P_total:.1f} \\times \\frac{{{L:.2f}}}{{2}} = {P_total * L / 2:.1f} \\text{{ kN-m}}$$"
            f"$$M_{{O,y}} = |M_y| + |V_y| \\cdot h = |{loads.service_moment_y:.1f}| + |{loads.shear_y:.1f}| \\times {h / 1000:.3f} = {abs(loads.service_moment_y) + abs(loads.shear_y) * h / 1000:.1f} \\text{{ kN-m}}$$"
            f"$$FS_y = \\frac{{M_{{R,y}}}}{{M_{{O,y}}}} = \\frac{{{P_total * L / 2:.1f}}}{{{abs(loads.service_moment_y) + abs(loads.shear_y) * h / 1000:.1f}}} = {fs_ot_y:.2f}$$"
            f"<p><strong>Required FS:</strong> {ot_limit} {'(transient)' if is_transient else '(sustained)'}</p>"
            f"<p><strong>Check:</strong> $FS_x = {fs_ot_x:.2f}$, $FS_y = {fs_ot_y:.2f}$ "
            f"$\\rightarrow$ <strong>{'PASS' if overturning_ok else 'FAIL'}</strong></p>"
            f"<h3>Sliding Check</h3>"
            f"$$K_a = \\frac{{1 - \\sin\\phi}}{{1 + \\sin\\phi}} = \\frac{{1 - \\sin({soil.friction_angle}°)}}{{1 + \\sin({soil.friction_angle}°)}} = {Ka:.3f}$$"
            f"$$F_{{resist}} = P_{{total}} \\cdot \\tan\\phi = {P_total:.1f} \\times \\tan({soil.friction_angle}°) = {sliding_resistance:.1f} \\text{{ kN}}$$"
            f"$$H_{{applied}} = \\sqrt{{V_x^2 + V_y^2}} = {H_applied_dc:.1f} \\text{{ kN}}$$"
            f"<p><strong>Sliding:</strong> $F_{{resist}} = {sliding_resistance:.1f}$ kN "
            f"{'≥' if sliding_resistance >= H_applied_dc else '<'} $H_{{applied}} = {H_applied_dc:.1f}$ kN "
            f"$\\rightarrow$ <strong>{'PASS' if sliding_resistance >= H_applied_dc else 'FAIL'}</strong></p>"
        )

        top_rows = ""
        if tx and ty:
            top_rows = (
                f"<tr><td style='padding:6px;border:1px solid #e5e7eb;'>Top X</td><td style='padding:6px;border:1px solid #e5e7eb;'>{tx}</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb;'>{stx:.0f} mm</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb;'>{max(25, self.aci.get_bar_diameter(tx)):.0f} mm</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb;'>{'OK' if stx >= max(25, self.aci.get_bar_diameter(tx)) and stx <= min(3 * geom.thickness, 450) else 'CHECK'}</td></tr>"
                f"<tr><td style='padding:6px;border:1px solid #e5e7eb;'>Top Y</td><td style='padding:6px;border:1px solid #e5e7eb;'>{ty}</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb;'>{sty:.0f} mm</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb;'>{max(25, self.aci.get_bar_diameter(ty)):.0f} mm</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb;'>{'OK' if sty >= max(25, self.aci.get_bar_diameter(ty)) and sty <= min(3 * geom.thickness, 450) else 'CHECK'}</td></tr>"
            )

        calcs["rebar_check"] = (
            f"<h3>Reinforcement Spacing Check (ACI 318M-25 §25.2)</h3>"
            f"<p>Minimum clear spacing: $\\max(25 \\text{{ mm}}, d_b)$</p>"
            f"<p>Maximum spacing: $\\min(3h, 450 \\text{{ mm}}) = \\min({3 * geom.thickness:.0f}, 450) = {min(3 * geom.thickness, 450):.0f}$ mm</p>"
            f"<table style='width:100%;border-collapse:collapse;font-size:14px;margin-top:12px;'>"
            f"<tr style='background:#f3f4f6;'><th style='padding:6px;border:1px solid #e5e7eb;'>Location</th>"
            f"<th style='padding:6px;border:1px solid #e5e7eb;'>Bar</th>"
            f"<th style='padding:6px;border:1px solid #e5e7eb;'>Spacing</th>"
            f"<th style='padding:6px;border:1px solid #e5e7eb;'>Min Clear</th>"
            f"<th style='padding:6px;border:1px solid #e5e7eb;'>Status</th></tr>"
            f"<tr><td style='padding:6px;border:1px solid #e5e7eb;'>Bottom X</td><td style='padding:6px;border:1px solid #e5e7eb;'>{bx}</td>"
            f"<td style='padding:6px;border:1px solid #e5e7eb;'>{sx:.0f} mm</td>"
            f"<td style='padding:6px;border:1px solid #e5e7eb;'>{max(25, self.aci.get_bar_diameter(bx)):.0f} mm</td>"
            f"<td style='padding:6px;border:1px solid #e5e7eb;'>{'OK' if sx >= max(25, self.aci.get_bar_diameter(bx)) and sx <= min(3 * geom.thickness, 450) else 'CHECK'}</td></tr>"
            f"<tr><td style='padding:6px;border:1px solid #e5e7eb;'>Bottom Y</td><td style='padding:6px;border:1px solid #e5e7eb;'>{by}</td>"
            f"<td style='padding:6px;border:1px solid #e5e7eb;'>{sy:.0f} mm</td>"
            f"<td style='padding:6px;border:1px solid #e5e7eb;'>{max(25, self.aci.get_bar_diameter(by)):.0f} mm</td>"
            f"<td style='padding:6px;border:1px solid #e5e7eb;'>{'OK' if sy >= max(25, self.aci.get_bar_diameter(by)) and sy <= min(3 * geom.thickness, 450) else 'CHECK'}</td></tr>"
            f"{top_rows}"
            f"</table>"
        )

        return calcs

    def _select_rebar(
        self, As_req: float, width: float, thickness: float, preferred_bar: str = None
    ) -> Tuple[str, float]:
        bar_sizes = ["D10", "D12", "D16", "D20", "D25", "D28", "D32", "D36"]
        if preferred_bar and preferred_bar in bar_sizes:
            idx = bar_sizes.index(preferred_bar)
            bar_sizes = [preferred_bar] + [
                b for i, b in enumerate(bar_sizes) if i != idx
            ]
        max_s = min(3 * thickness, 450.0)
        for bar in bar_sizes:
            area = self.aci.get_bar_area(bar)
            s = area * width / As_req
            db = self.aci.get_bar_diameter(bar)
            min_s = max(25.0, db)
            if min_s <= s <= max_s:
                return bar, math.floor(s / 10.0) * 10.0
        last_bar = bar_sizes[-1]
        last_area = self.aci.get_bar_area(last_bar)
        last_s = last_area * width / As_req
        last_db = self.aci.get_bar_diameter(last_bar)
        last_min_s = max(25.0, last_db)
        return last_bar, math.floor(max(last_min_s, last_s) / 10.0) * 10.0

    def perform_complete_design(
        self,
        geom: FootingGeometry,
        loads: FootingLoads,
        soil: SoilProperties,
        mat: MaterialProperties,
        is_transient: bool = False,
        preferred_bottom_bar: str = "D16",
        preferred_top_bar: str = "D16",
    ) -> FootingAnalysisResult:
        notes = ["FEA analysis performed using OpenSeesPy ShellMITC4 elements."]

        # Soil overburden and surcharge pressures
        soil_overburden = soil.unit_weight * (soil.soil_depth / 1000.0)  # kPa
        surcharge_total = loads.surcharge_dl + loads.surcharge_ll  # kPa (service level)
        net_qa = (
            soil.bearing_capacity - soil_overburden - surcharge_total
        )  # net allowable for column loads only

        # Lateral earth pressure coefficient (Rankine active)
        phi_rad = math.radians(soil.friction_angle)
        Ka = (1 - math.sin(phi_rad)) / (1 + math.sin(phi_rad))

        # 1. Service Analysis (Bearing Pressure)
        srv_data, srv_notes = self._run_opensees_analysis(
            geom, loads, soil, mat, is_service=True
        )
        notes.extend(srv_notes)
        qmax_total = np.max(
            srv_data["Q_SOIL"]
        )  # total soil pressure (column + soil + surcharge)
        qmin_total = np.min(srv_data["Q_SOIL"])

        # For bearing check: compare total pressure against gross allowable
        # (which already accounts for everything the soil can support)
        bearing_limit = (
            soil.bearing_capacity * 1.33 if is_transient else soil.bearing_capacity
        )
        bearing_ok = qmax_total <= bearing_limit

        # Also check net pressure from column only against net allowable
        qmax_net = qmax_total - soil_overburden - surcharge_total
        qmin_net = qmin_total - soil_overburden - surcharge_total
        net_limit = net_qa * 1.33 if is_transient else net_qa

        # Net bearing check (ACI 318M‑25 §12.2.2)
        net_bearing_ok = qmax_net <= net_limit
        if is_transient:
            notes.append(
                f"ℹ️ Transient load combination active. Gross bearing limit = {bearing_limit:.1f} kPa (1.33× qa). Net bearing limit = {net_limit:.1f} kPa."
            )
        if not bearing_ok:
            notes.append(
                f"⚠️ Total bearing pressure ({qmax_total:.1f} kPa) exceeds gross allowable ({bearing_limit:.1f} kPa)."
            )
        if not net_bearing_ok:
            notes.append(
                f"⚠️ Net bearing pressure ({qmax_net:.1f} kPa) exceeds net allowable ({net_limit:.1f} kPa)."
            )
        if qmin_total <= 0.1:
            notes.append(
                "ℹ️ Footing is experiencing partial uplift (tension ignored in soil)."
            )
        if soil_overburden > 0:
            notes.append(
                f"ℹ️ Soil overburden = {soil_overburden:.1f} kPa (γ={soil.unit_weight} kN/m³, D={soil.soil_depth} mm)."
            )
        if surcharge_total > 0:
            notes.append(
                f"ℹ️ Surcharge = {surcharge_total:.1f} kPa (DL={loads.surcharge_dl}, LL={loads.surcharge_ll})."
            )

        # 2. Ultimate Analysis (Strength)
        ult_data, ult_notes = self._run_opensees_analysis(
            geom, loads, soil, mat, is_service=False
        )

        # Design moments from soil pressure integration (classical footing method)
        MXX = ult_data["MXX"]
        MYY = ult_data["MYY"]
        MXY = ult_data.get("MXY", np.zeros_like(MXX))

        # Wood-Armer moments for design
        MXY_abs = np.abs(MXY)
        wa_mx = MXX + MXY_abs  # bottom x-direction
        wa_my = MYY + MXY_abs  # bottom y-direction
        wa_mx_top = np.minimum(MXX - MXY_abs, 0)  # top x (hogging)
        wa_my_top = np.minimum(MYY - MXY_abs, 0)  # top y (hogging)

        # For isolated footings, the critical section for flexure is at the column face
        # (ACI 318M-25 §13.2.7.1). Extract moments at nodes nearest to column faces.
        L_m = geom.length / 1000.0
        B_m = geom.width / 1000.0
        col_w_m = geom.column_width / 1000.0
        col_d_m = geom.column_depth / 1000.0
        nx_g, ny_g = MXX.shape[0] - 1, MXX.shape[1] - 1

        # Find node indices closest to column faces
        x_nodes = np.linspace(-L_m / 2, L_m / 2, nx_g + 1)
        y_nodes = np.linspace(-B_m / 2, B_m / 2, ny_g + 1)

        col_faces_x = [-col_w_m / 2, col_w_m / 2]
        col_faces_y = [-col_d_m / 2, col_d_m / 2]

        def _find_nearest(arr, val):
            return int(np.argmin(np.abs(arr - val)))

        ix_left = _find_nearest(x_nodes, col_faces_x[0])
        ix_right = _find_nearest(x_nodes, col_faces_x[1])
        iy_bot = _find_nearest(y_nodes, col_faces_y[0])
        iy_top = _find_nearest(y_nodes, col_faces_y[1])

        # Bottom moments: max at column face in each direction
        M_x_pos = max(
            np.max(wa_mx[ix_left, :]),
            np.max(wa_mx[ix_right, :]),
        )
        M_y_pos = max(
            np.max(wa_my[:, iy_bot]),
            np.max(wa_my[:, iy_top]),
        )

        # Top moments: only if there are negative (hogging) moments at column faces
        M_x_neg = max(
            abs(np.min(wa_mx_top[ix_left, :])),
            abs(np.min(wa_mx_top[ix_right, :])),
        )
        M_y_neg = max(
            abs(np.min(wa_my_top[:, iy_bot])),
            abs(np.min(wa_my_top[:, iy_top])),
        )

        # FEA shear values (from soil pressure integration)
        V_x = np.max(np.abs(ult_data["VX"]))
        V_y = np.max(np.abs(ult_data["VY"]))

        # Flexure Design
        db_bot = self.aci.get_bar_diameter(preferred_bottom_bar)
        db_top_val = self.aci.get_bar_diameter(preferred_top_bar)
        # Effective depth uses half bar diameter per ACI 318M‑25 §5.7.2.1
        d_eff = (
            geom.thickness - geom.cover - db_bot / 2.0
        )  # average d for two orthogonal layers (bottom)
        d_eff_top = geom.thickness - geom.cover - db_top_val / 2.0
        rho_min = 0.0018
        As_min = rho_min * 1000 * geom.thickness

        def req_as(M):
            if M <= 0:
                return As_min
            A = (
                self.phi_factors["flexure"]
                * mat.fy**2
                / (2 * 0.85 * mat.fc_prime * 1000)
            )
            B = -self.phi_factors["flexure"] * mat.fy * d_eff
            C = M * 1e6
            disc = B**2 - 4 * A * C
            if disc < 0:
                return As_min * 2
            return max((-B - math.sqrt(disc)) / (2 * A), As_min)

        # Required steel areas for bottom reinforcement (positive moments)
        As_req_x = req_as(max(M_x_pos, 0))
        As_req_y = req_as(max(M_y_pos, 0))

        # Bottom reinforcement (positive moments)
        bx, sx = self._select_rebar(
            As_req_x, 1000, geom.thickness, preferred_bottom_bar
        )
        by, sy = self._select_rebar(
            As_req_y, 1000, geom.thickness, preferred_bottom_bar
        )
        # Determine if top reinforcement is needed from Wood‑Armer hogging moments
        _eps = 1e-3
        has_bend = (M_x_neg > _eps) or (M_y_neg > _eps)

        # Top reinforcement (negative moments)
        def req_as_top(M):
            if M <= 0:
                return As_min
            A = (
                self.phi_factors["flexure"]
                * mat.fy**2
                / (2 * 0.85 * mat.fc_prime * 1000)
            )
            B = -self.phi_factors["flexure"] * mat.fy * d_eff_top
            C = M * 1e6
            disc = B**2 - 4 * A * C
            if disc < 0:
                return As_min * 2
            return max((-B - math.sqrt(disc)) / (2 * A), As_min)

        if has_bend:
            As_req_xtop = req_as_top(max(M_x_neg, 0))
            As_req_ytop = req_as_top(max(M_y_neg, 0))
            tx, stx = self._select_rebar(
                As_req_xtop, 1000, geom.thickness, preferred_top_bar
            )
            ty, sty = self._select_rebar(
                As_req_ytop, 1000, geom.thickness, preferred_top_bar
            )
        else:
            As_req_xtop = As_req_ytop = 0.0
            tx, stx = "", 0.0
            ty, sty = "", 0.0

        # Over‑reinforcement check (ρ ≤ 0.04) – bottom & top
        rho_bottom_x = As_req_x / (1000 * d_eff)
        rho_bottom_y = As_req_y / (1000 * d_eff)
        rho_top_x = As_req_xtop / (1000 * d_eff_top) if As_req_xtop > 0 else 0.0
        rho_top_y = As_req_ytop / (1000 * d_eff_top) if As_req_ytop > 0 else 0.0
        max_rho = max(rho_bottom_x, rho_bottom_y, rho_top_x, rho_top_y)
        over_reinf_ok = max_rho <= 0.04
        if not over_reinf_ok:
            notes.append(
                f"⚠️ Over‑reinforcement: ρ = {max_rho:.3f} exceeds 0.04. Consider larger spacing or smaller bar size."
            )

        # ── Shear Checks ──
        if d_eff < 100.0:
            notes.append(
                f"⚠️ Effective depth d = {d_eff:.0f} mm is very small. Consider increasing footing thickness."
            )
            # Do NOT clamp d_eff; keep the actual (small) value for design calculations.
        d_eff_design = d_eff  # save for detailed calcs before contour-plot reset
        L_m = geom.length / 1000.0
        B_m = geom.width / 1000.0
        d_m = d_eff / 1000.0
        col_w_m = geom.column_width / 1000.0
        col_d_m = geom.column_depth / 1000.0

        # One-way shear: use actual FEA soil pressure at critical section
        # Critical section is at distance d from column face in each direction
        # Find the node indices closest to the critical sections
        crit_x_left = -col_w_m / 2 - d_m
        crit_x_right = col_w_m / 2 + d_m
        crit_y_bot = -col_d_m / 2 - d_m
        crit_y_top = col_d_m / 2 + d_m

        ix_crit_left = _find_nearest(x_nodes, crit_x_left)
        ix_crit_right = _find_nearest(x_nodes, crit_x_right)
        iy_crit_bot = _find_nearest(y_nodes, crit_y_bot)
        iy_crit_top = _find_nearest(y_nodes, crit_y_top)

        # One-way shear at critical sections (distance d from column face)
        # Compute shear from nearest edge only (not the max of both directions)
        Q_ULT = ult_data["Q_SOIL"]  # kPa = kN/m²
        nx_g, ny_g = Q_ULT.shape[0] - 1, Q_ULT.shape[1] - 1
        dx_m = L_m / nx_g  # element width in meters
        dy_m = B_m / ny_g  # element height in meters

        # X-direction: shear at left and right critical sections
        # Left critical section: integrate from left edge to ix_crit_left
        Vu_x_left_max = 0.0
        for j in range(ny_g + 1):
            vx = 0.0
            for i in range(ix_crit_left + 1):
                vx += Q_ULT[i, j] * dx_m
            Vu_x_left_max = max(Vu_x_left_max, vx)

        # Right critical section: integrate from right edge to ix_crit_right
        Vu_x_right_max = 0.0
        for j in range(ny_g + 1):
            vx = 0.0
            for i in range(nx_g, ix_crit_right - 1, -1):
                vx += Q_ULT[i, j] * dx_m
            Vu_x_right_max = max(Vu_x_right_max, vx)

        Vu_x = max(Vu_x_left_max, Vu_x_right_max)

        # Y-direction: shear at bottom and top critical sections
        Vu_y_bot_max = 0.0
        for i in range(nx_g + 1):
            vy = 0.0
            for j in range(iy_crit_bot + 1):
                vy += Q_ULT[i, j] * dy_m
            Vu_y_bot_max = max(Vu_y_bot_max, vy)

        Vu_y_top_max = 0.0
        for i in range(nx_g + 1):
            vy = 0.0
            for j in range(ny_g, iy_crit_top - 1, -1):
                vy += Q_ULT[i, j] * dy_m
            Vu_y_top_max = max(Vu_y_top_max, vy)

        Vu_y = max(Vu_y_bot_max, Vu_y_top_max)

        # One-way shear capacity (ACI 318-25 Table 22.5.5.1) — per unit width
        phi_v = self.phi_factors["shear"]
        vc_ow = 0.17 * math.sqrt(mat.fc_prime)  # MPa = N/mm²
        phiVc_x = phi_v * vc_ow * 1000 * d_m  # MPa * mm * mm = N/mm = kN/m
        phiVc_y = phi_v * vc_ow * 1000 * d_m  # kN/m

        one_way_demand_x = Vu_x  # kN/m
        one_way_demand_y = Vu_y  # kN/m
        one_way_capacity_x = phiVc_x  # kN/m
        one_way_capacity_y = phiVc_y  # kN/m

        ratio_x = Vu_x / phiVc_x if phiVc_x > 0 else 99.9
        ratio_y = Vu_y / phiVc_y if phiVc_y > 0 else 99.9
        one_way_ratio = max(ratio_x, ratio_y)
        one_way_ok = one_way_ratio <= 1.0
        if not one_way_ok:
            notes.append(
                f"⚠️ 1-Way Shear inadequate. Max demand {max(Vu_x, Vu_y):.1f} kN/m > capacity {min(phiVc_x, phiVc_y):.1f} kN/m."
            )

        # Two-way (punching) shear
        two_way_ok, two_way_ratio, two_way_demand, two_way_cap = (
            self.check_two_way_shear(geom, loads, mat, d_eff)
        )
        if not two_way_ok:
            notes.append(
                f"⚠️ 2-Way (Punching) Shear inadequate. DCR = {two_way_ratio:.2f}."
            )

        # ── Overturning Check ──
        W_footing = 24.0 * L_m * B_m * (geom.thickness / 1000.0)
        W_soil = (
            soil.unit_weight * L_m * B_m * (soil.soil_depth / 1000.0)
            if soil.soil_depth > 0
            else 0.0
        )
        W_surcharge = surcharge_total * L_m * B_m  # kPa * m² = kN
        P_total = loads.service_axial + W_footing + W_soil + W_surcharge

        overturning_moment_x = abs(loads.service_moment_x) + abs(loads.shear_x) * (
            geom.thickness / 1000.0
        )
        overturning_moment_y = abs(loads.service_moment_y) + abs(loads.shear_y) * (
            geom.thickness / 1000.0
        )

        resisting_moment_x = P_total * B_m / 2.0
        resisting_moment_y = P_total * L_m / 2.0

        fs_ot_x = (
            resisting_moment_x / overturning_moment_x
            if overturning_moment_x > 0
            else 99.9
        )
        fs_ot_y = (
            resisting_moment_y / overturning_moment_y
            if overturning_moment_y > 0
            else 99.9
        )

        ot_limit = 1.5 if is_transient else 2.0
        overturning_ok = (fs_ot_x >= ot_limit) and (fs_ot_y >= ot_limit)

        if not overturning_ok:
            if fs_ot_x < ot_limit:
                notes.append(
                    f"⚠️ Overturning about X-axis inadequate. FS = {fs_ot_x:.2f} (min {ot_limit})."
                )
            if fs_ot_y < ot_limit:
                notes.append(
                    f"⚠️ Overturning about Y-axis inadequate. FS = {fs_ot_y:.2f} (min {ot_limit})."
                )

        # Sliding Check — compare against applied horizontal forces
        sliding_resistance = P_total * math.tan(phi_rad)
        H_applied = math.sqrt(loads.shear_x**2 + loads.shear_y**2)
        sliding_ok = sliding_resistance >= H_applied
        if H_applied > 0:
            fs_sliding = sliding_resistance / H_applied
            notes.append(
                f"ℹ️ Sliding: resistance = {sliding_resistance:.1f} kN, demand = {H_applied:.1f} kN, FS = {fs_sliding:.2f}."
            )
        if soil.soil_depth > 0:
            notes.append(
                f"ℹ️ Soil overburden provides passive resistance (not included). Ka = {Ka:.3f}."
            )

        # Generate Visualizations
        d_eff = geom.thickness - geom.cover - db_bot
        plots = self.generate_contour_plots(geom, ult_data, mat, d_eff)
        srv_plots = self.generate_contour_plots(
            geom, srv_data, keys_only=["soil_pressure", "settlement"]
        )
        for k in ["soil_pressure", "settlement"]:
            if k in srv_plots:
                plots[k] = srv_plots[k]

        reinf = FootingReinforcement(
            bx,
            sx,
            by,
            sy,
            tx,
            stx,
            ty,
            sty,
            self.aci.calculate_development_length(bx, mat.fc_prime, mat.fy),
            "D20",
            600.0,
        )

        # Overall DCR: include gross bearing, net bearing, one‑way shear, two‑way shear
        net_bearing_ratio = qmax_net / net_limit if net_limit > 0 else 0
        dcr = max(
            qmax_total / bearing_limit if bearing_limit > 0 else 0,
            net_bearing_ratio,
            one_way_ratio,
            two_way_ratio,
        )

        detailed_calcs = self._generate_detailed_calcs(
            geom,
            loads,
            soil,
            mat,
            is_transient,
            qmax_total,
            qmin_total,
            bearing_limit,
            bearing_ok,
            net_qa,
            M_x_pos,
            M_x_neg,
            M_y_pos,
            M_y_neg,
            V_x,
            V_y,
            bx,
            sx,
            by,
            sy,
            tx,
            stx,
            ty,
            sty,
            d_eff_design,
            d_eff_top,
            As_min,
            one_way_ok,
            one_way_ratio,
            min(one_way_capacity_x, one_way_capacity_y),
            two_way_ok,
            two_way_ratio,
            fs_ot_x,
            fs_ot_y,
            overturning_ok,
            ot_limit,
            W_footing,
            W_soil,
            P_total,
            sliding_resistance,
            Ka,
        )

        result = FootingAnalysisResult(
            qmax_total,
            qmin_total,
            bearing_ok,
            one_way_ok,
            two_way_ok,
            reinf,
            dcr,
            list(set(notes)),
            max(M_x_pos, M_x_neg),
            max(M_y_pos, M_y_neg),
            V_x,
            V_y,
            plots,
            overturning_ok,
            fs_ot_x,
            fs_ot_y,
            bearing_limit,
            detailed_calcs,
            max(one_way_demand_x, one_way_demand_y),
            min(one_way_capacity_x, one_way_capacity_y),
            two_way_demand,
            two_way_cap,
        )
        result.fea_moment_x_pos = M_x_pos
        result.fea_moment_x_neg = M_x_neg
        result.fea_moment_y_pos = M_y_pos
        result.fea_moment_y_neg = M_y_neg
        return result

    def calculate_qto(self, geom: FootingGeometry, res: FootingAnalysisResult) -> dict:
        vol = (geom.length / 1000.0) * (geom.width / 1000.0) * (geom.thickness / 1000.0)
        fw = (
            2 * (geom.length / 1000.0 + geom.width / 1000.0) * (geom.thickness / 1000.0)
        )

        COMMERCIAL_LENGTHS = [6000, 7500, 9000, 10500, 12000]  # mm
        LAP_SPLICE = 40  # bar diameters for lap splice
        HOOK_LEN = 12  # hook length in bar diameters

        def _bar_weight(db_mm, length_m):
            return length_m * (db_mm**2 / 162.0)

        def _optimize_cutting_stock(bar_size, spacing, L_along, L_across, label):
            if bar_size == "None" or spacing <= 0:
                return []
            db = float(bar_size.replace("D", ""))
            qty = math.ceil(L_across / spacing)
            if qty < 1:
                qty = 1
            straight_m = (L_along - 2 * geom.cover) / 1000.0
            if straight_m <= 0:
                return []

            hook_m = HOOK_LEN * db / 1000.0
            lap_m = LAP_SPLICE * db / 1000.0
            cut_len = straight_m + 2 * hook_m  # length per finished bar including hooks

            best = None
            for C_mm in COMMERCIAL_LENGTHS:
                C = C_mm / 1000.0  # commercial length in meters
                # Max pieces from one commercial bar: k*L_cut + (k-1)*L_lap <= C
                # => k <= (C + L_lap) / (L_cut + L_lap)
                if cut_len > C:
                    # Need multiple commercial bars per single finished bar
                    pieces_per_commercial = 0
                else:
                    pieces_per_commercial = int((C + lap_m) / (cut_len + lap_m))

                if pieces_per_commercial < 1:
                    continue

                n_commercial = math.ceil(qty / pieces_per_commercial)
                # Total length purchased
                total_purchased = n_commercial * C
                # Total length actually used (finished bars + splices)
                total_splices = max(0, qty - pieces_per_commercial)
                total_used = qty * cut_len + total_splices * lap_m
                waste = total_purchased - total_used

                if best is None or waste < best["waste"]:
                    best = {
                        "commercial_len_m": C,
                        "pieces_per_bar": pieces_per_commercial,
                        "n_commercial": n_commercial,
                        "waste": waste,
                    }

            if best is None:
                # Fallback: use longest commercial with splices
                C = COMMERCIAL_LENGTHS[-1] / 1000.0
                pieces_per_commercial = max(1, int((C + lap_m) / (cut_len + lap_m)))
                n_commercial = math.ceil(qty / pieces_per_commercial)
                total_purchased = n_commercial * C
                total_splices = max(0, qty - pieces_per_commercial)
                total_used = qty * cut_len + total_splices * lap_m
                best = {
                    "commercial_len_m": C,
                    "pieces_per_bar": pieces_per_commercial,
                    "n_commercial": n_commercial,
                    "waste": total_purchased - total_used,
                }

            total_purchased = best["n_commercial"] * best["commercial_len_m"]
            total_used = qty * cut_len + max(0, qty - best["pieces_per_bar"]) * lap_m
            total_weight = _bar_weight(db, total_used)

            return [
                {
                    "label": label,
                    "bar": bar_size,
                    "qty": qty,
                    "each_len_m": round(cut_len, 2),
                    "total_len_m": round(total_used, 1),
                    "weight_kg": round(total_weight, 1),
                    "splices": max(0, qty - best["pieces_per_bar"]),
                    "commercial_len_m": best["commercial_len_m"],
                    "com_bars": best["n_commercial"],
                    "waste_m": round(best["waste"], 2),
                }
            ]

        items = []
        items.extend(
            _optimize_cutting_stock(
                res.reinforcement.bottom_bars_x,
                res.reinforcement.bottom_spacing_x,
                geom.length,
                geom.width,
                "Bottom X Bars",
            )
        )
        items.extend(
            _optimize_cutting_stock(
                res.reinforcement.bottom_bars_y,
                res.reinforcement.bottom_spacing_y,
                geom.width,
                geom.length,
                "Bottom Y Bars",
            )
        )
        items.extend(
            _optimize_cutting_stock(
                res.reinforcement.top_bars_x,
                res.reinforcement.top_spacing_x,
                geom.length,
                geom.width,
                "Top X Bars",
            )
        )
        items.extend(
            _optimize_cutting_stock(
                res.reinforcement.top_bars_y,
                res.reinforcement.top_spacing_y,
                geom.width,
                geom.length,
                "Top Y Bars",
            )
        )

        total_wt = sum(it["weight_kg"] for it in items) if items else 0.0

        return {
            "volume": vol,
            "formwork": fw,
            "weight": total_wt,
            "cutting_list": items,
        }
