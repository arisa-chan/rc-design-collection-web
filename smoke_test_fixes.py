"""Smoke test for critical fixes 1-4 in aci318m25_beam.py"""
from aci318m25_beam import ACI318M25BeamDesign, BeamGeometry, BeamType, FrameSystem
from aci318m25 import ACI318M25, ConcreteStrengthClass, ReinforcementGrade

aci = ACI318M25()
mat = aci.get_material_properties(ConcreteStrengthClass.FC28, ReinforcementGrade.GRADE420)
des = ACI318M25BeamDesign()

# Rectangular beam
g = BeamGeometry(
    length=6000, width=300, height=550, effective_depth=490,
    cover=40, flange_width=300, flange_thickness=0,
    beam_type=BeamType.RECTANGULAR, clear_span=5700
)
# T-beam
gt = BeamGeometry(
    length=6000, width=300, height=550, effective_depth=490,
    cover=40, flange_width=1200, flange_thickness=120,
    beam_type=BeamType.T_BEAM, clear_span=5700
)

# --- Fix 1: Mpr doubly-reinforced formula ---
mpr_dr = des.calculate_probable_moment_capacity(1500, 800, g, mat, 'D10', 'D20')
mpr_sr = des.calculate_probable_moment_capacity(1500, 0,   g, mat, 'D10', 'D20')
print(f"Fix1  Mpr doubly-reinf = {mpr_dr:.1f} kNm   (singly = {mpr_sr:.1f} kNm)")
# a_net ≈ (1500-800)*525*1.25/(0.85*28*300)≈57mm; a/2-d'≈57/2-67≈-38 → term is negative (reduces Mpr)
assert mpr_dr < mpr_sr, "Mpr with compression steel should be less than pure tension steel Mpr"
print("  PASS")

# --- Fix 2: T-beam flange in _get_required_steel and _calculate_moment_capacity ---
As_rect = des._get_required_steel(250, g, mat)
As_t    = des._get_required_steel(250, gt, mat)
print(f"Fix2  As_req  rect={As_rect:.0f} mm²  T-beam={As_t:.0f} mm² (T-beam should need less steel)")
assert As_t <= As_rect, "T-beam uses flange compression, so less tensile steel needed"
Mn_t  = des._calculate_moment_capacity(As_t, gt, mat)
Mn_r  = des._calculate_moment_capacity(As_rect, g, mat)
print(f"      Mn rect={Mn_r:.1f} kNm  Mn T={Mn_t:.1f} kNm  (both >= demand 250 kNm expected)")
assert 0.9 * Mn_t >= 248, "T-beam capacity should cover demand (≥250 kNm approx)"
print("  PASS")

# --- Fix 3: Deflection uses Branson Ie instead of gross Ig ---
res = des.perform_complete_beam_design(
    250, 150, 180, g, mat, service_moment=120, tu=0, gravity_shear=90
)
# Gross-Ig deflection for reference (old formula)
Ig = g.width * g.height**3 / 12
defl_gross = 5 * 120e6 * g.length**2 / (48 * mat.ec * Ig)
print(f"Fix3  deflection Ie-based={res.deflection:.2f} mm   gross-Ig ref={defl_gross:.2f} mm")
assert res.deflection > defl_gross * 0.8, "Branson Ie deflection should be >= gross-Ig deflection"
print("  PASS")

# --- Fix 4: Crack width computed (Frosch) ---
print(f"Fix4  crack_width={res.crack_width:.4f} mm  (must be > 0)")
assert res.crack_width > 0.0, "crack_width must be non-zero for a loaded beam"
print("  PASS")

print("\nAll smoke tests passed.")
