from beam_pdf import generate_beam_report
from beam import BeamDesignModel
from aci318m25 import MaterialProperties
from aci318m25_beam import BeamGeometry, BeamType, SeismicDesignCategory, FrameSystem
from beam import ControlledBeamDesign
from aci318m25_complete import ACI318M25MemberLibrary

import traceback

import sys

try:
    data = BeamDesignModel()
    
    mat_props = MaterialProperties(fc_prime=28, fy=420, fu=500, fyt=420, fut=500, es=200000, ec=25000, gamma_c=24, description="")
    beam_geom = BeamGeometry(length=6000, width=400, height=600, effective_depth=540, cover=40, flange_width=0, flange_thickness=0, beam_type=BeamType.RECTANGULAR, clear_span=5500, sdc=SeismicDesignCategory("D"), frame_system=FrameSystem("special"))
    custom_lib = ACI318M25MemberLibrary()
    custom_lib.beam_design = ControlledBeamDesign("D20", "D10", "D12")
    res_left = custom_lib.beam_design.perform_complete_beam_design(300, 100, 180, beam_geom, mat_props, tu=35, gravity_shear=80, is_support=True, max_as_support=1000)
    res_mid = custom_lib.beam_design.perform_complete_beam_design(50, 200, 50, beam_geom, mat_props, service_moment=60, tu=5, gravity_shear=0, is_support=False, max_as_support=1000)
    res_right = custom_lib.beam_design.perform_complete_beam_design(280, 120, 170, beam_geom, mat_props, tu=15, gravity_shear=80, is_support=True, max_as_support=1000)
    
    generate_beam_report(data, mat_props, beam_geom, res_left, res_mid, res_right)
    print("SUCCESS")
except Exception as e:
    import tempfile
    import os
    print(f"Exception: {e}")
    # Read the tex file from the exception if there's one
    # The temporary dir might be deleted, so we should edit beam_pdf to not delete or we just print the tex
    doc = None
