import bpy
import pytest
from batoms.batoms import Batoms
from ase.io import read
from ase.build import molecule
import numpy as np

try:
    from _common_helpers import has_display, set_cycles_res

    use_cycles = not has_display()
except ImportError:
    use_cycles = False

extras = dict(engine="cycles") if use_cycles else {}

def test_polyhedra_species():
    """
    This is an example to show different polyhedras for the same element, but different species. 
    """
    from batoms.bio import read
    bpy.ops.batoms.delete()
    # First, we read a TiO2 structure from file.
    tio2 = read("../tests/datas/tio2.cif")
    assert len(tio2.polyhedras.setting) == 1
    # We set the first one to a new species Ti_1.
    tio2.replace([0], 'Ti_1')
    tio2.bonds.setting
    tio2.model_style = 2
    assert len(tio2.polyhedras) == 6
    # add a bond between Ti_1 and O
    tio2.bonds.setting.add(('Ti_1', 'O'))
    tio2.bonds.setting
    # In the Bondpair Ti_1-O, the Polyhedra is False, we can set it to True by:
    tio2.bonds.setting[('Ti_1', 'O')].polyhedra = True
    tio2.bonds.setting
    # Also add Ti_1 to polyhedras.
    tio2.polyhedras.setting.add('Ti_1')
    assert len(tio2.polyhedras.setting) == 2
    # To make the polyhedra different from another Ti species, we change its color.
    tio2.polyhedras.setting['Ti_1'].color = (0, 1, 1, 0.8)
    tio2.polyhedras.setting
    tio2.model_style = 2
    assert len(tio2.polyhedras) == 12


def test_polyhedra_molecule():
    bpy.ops.batoms.delete()
    ch4 = molecule("CH4")
    mh4 = ch4.copy()
    mh4.translate([2, 2, 0])
    mh4[0].symbol = "N"
    ch4 = ch4 + mh4
    ch4 = Batoms("ch4", from_ase=ch4)
    ch4.model_style = 2
    ch4.bonds.setting[("C", "H")].polyhedra = True
    ch4.model_style = 1


def test_polyhedra_crystal():
    from ase.io import read
    bpy.ops.batoms.delete()
    tio2 = read("../tests/datas/tio2.cif")
    tio2 = Batoms("tio2", from_ase=tio2)
    tio2.model_style = 2
    tio2 = tio2 * [3, 3, 3]
    tio2.pbc = False
    tio2.model_style = 2


def test_polyhedra_setting():
    bpy.ops.batoms.delete()
    ch4 = Batoms("ch4", from_ase=molecule("CH4"))
    ch4.bonds.setting[("C", "H")].polyhedra = True
    ch4.model_style = 2
    ch4.pbc = True
    ch4.cell = [3, 3, 3]
    ch4 = ch4 * [2, 1, 1]
    sel1 = ch4.selects.add("sel1", [0, 1, 2, 3, 4])
    sel1.model_style = 1
    ch4.polyhedras.setting.remove("C")
    assert len(ch4.polyhedras.setting) == 1
    ch4.polyhedras.setting.add("C")
    assert len(ch4.polyhedras.setting) == 2
    ch4.polyhedras.setting["C"] = {"color": [0.8, 0.1, 0.3, 0.3]}
    ch4.model_style = 2
    ch4.render.engine = "workbench"
    if use_cycles:
        set_cycles_res(ch4)
    ch4.get_image([1, 1, 0], output="polyhedras.png", **extras)


if __name__ == "__main__":
    test_polyhedra_species()
    test_polyhedra_molecule()
    test_polyhedra_crystal()
    test_polyhedra_setting()
    print("\n Polyhedra: All pass! \n")
