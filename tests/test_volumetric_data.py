import bpy
import pytest
from batoms.batoms import Batoms
from batoms.bio.bio import read
import numpy as np
from time import time

try:
    from _common_helpers import has_display, set_cycles_res

    use_cycles = not has_display()
except ImportError:
    use_cycles = False

extras = dict(engine="cycles") if use_cycles else {}


def test_settings():
    """key search"""
    from batoms.batoms import Batoms
    from ase.io.cube import read_cube_data
    volume, atoms = read_cube_data("../tests/datas/h2o-homo.cube")
    bpy.ops.batoms.delete()
    h2o = Batoms('h2o', from_ase = atoms, volume = {'homo': volume})
    assert h2o.volumetric_data.bpy_setting['homo'].shape[:] == volume.shape
    assert h2o.volumetric_data['homo'].shape == volume.shape
    assert len(h2o.volumetric_data) == 1
    h2o.volumetric_data["electrostatic"] = volume + 1
    assert len(h2o.volumetric_data) == 2
    assert h2o.volumetric_data.find("homo") is not None
    assert h2o.volumetric_data.find("electrostatic") is not None
    h2o.volumetric_data.remove("homo")
    assert h2o.volumetric_data.find("homo") is None
