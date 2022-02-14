"""
"""
from turtle import position
import numpy as np
from time import time
from ase.geometry import wrap_positions
from pandas import array

def RemovePbc(species0, positions0, cell, pbc, cutoffs):
    """
    convert atoms with pbc to non-pbc by adding boundary atoms within max cutoff
    """
    maxCutoff = np.array([x for x in cutoffs.values()]).max()
    boundary = np.ones((3, 2))*maxCutoff
    array = build_boundary(species0, positions0, 
            cell, pbc, boundary, include_self = True)
    return array

def neighbor_kdtree_boundary(quantities, array1, array2, cell, 
                    cutoffs, self_interaction=False):
    """
    wrap to pbc structure with boundary

    """
    i, j, distances = neighbor_kdtree('ijd', 
            array1, array2, cell, cutoffs)
    offsets_i = array1['offsets'][i]
    offsets_j = array2['offsets'][j]
    i = array1['indices'][i]
    j = array2['indices'][j]
    # Remove all self-interaction.
    if not self_interaction:
        mask = np.where((i == j) & \
                ((offsets_i == offsets_j).all(axis = 1)), 
                False, True)
        # print(mask)
        i = i[mask]
        j = j[mask]
        distances = distances[mask]
        offsets_i = offsets_i[mask]
        offsets_j = offsets_j[mask]
    retvals = []
    for q in quantities:
        if q == 'i':
            retvals += [i]
        elif q == 'j':
            retvals += [j]
        elif q == 'd':
            retvals += [distances]
        elif q == 'S':
            retvals += [offsets_i, offsets_j]
        else:
            raise ValueError('Unsupported quantity specified.')
    if len(retvals) == 1:
        return retvals[0]
    else:
        return tuple(retvals)

def neighbor_kdtree_pbc(quantities, species0, positions0, cell, pbc,
                    cutoffs, self_interaction=False):
    """
    wrap to pbc structure

    """
    natom = len(positions0)
    # orignal atoms
    array1 = {
            'positions': positions0,
            'species': species0,
            'indices': np.arange(natom),
            'offsets': np.zeros((natom, 3)),
            }
    # atoms added with boundary
    array2 = RemovePbc(species0, positions0, cell, pbc, cutoffs)
    # i, j, d, offsets_i, offsets_j = neighbor_kdtree('ijdS', 
            # array1, array2, cell, cutoffs2)
    i, j, distances = neighbor_kdtree('ijd', 
            array1, array2, cell, cutoffs)
    """
    # remove bothways for same species, e.g. ('C', 'C')
    mask = np.where((array1['species'][i] == array2['species'][j]) &
        (i > j) & ((array1['offsets'][i] == array2['offsets'][j]).all(axis = 1)), False, True)
    i = i[mask]
    j = j[mask]
    distances = distances[mask]
    """
    offsets_i = array1['offsets'][i]
    offsets_j = array2['offsets'][j]
    i = array1['indices'][i]
    j = array2['indices'][j]
    # Remove all self-interaction.
    if not self_interaction:
        mask = np.where((i == j) & \
                ((array1['offsets'][i] == array2['offsets'][j]).all(axis = 1)), 
                False, True)
        # print(mask)
        i = i[mask]
        j = j[mask]
        distances = distances[mask]
        offsets_i = offsets_i[mask]
        offsets_j = offsets_j[mask]
    retvals = []
    for q in quantities:
        if q == 'i':
            retvals += [i]
        elif q == 'j':
            retvals += [j]
        elif q == 'd':
            retvals += [distances]
        elif q == 'S':
            retvals += [offsets_j]
        else:
            raise ValueError('Unsupported quantity specified.')
    if len(retvals) == 1:
        return retvals[0]
    else:
        return tuple(retvals)

def neighbor_kdtree(quantities, array1, array2, cell,
                    cutoffs, self_interaction=False):
    """
    build bond lists between atoms1 and atoms2. 
    atoms1 and atoms2 could be the same, in this case, non-pbc
    in pbc case, atoms2 is atoms1 + boundary atoms
    """
    tstart = time()
    # print('build boundary: {:1.2f}'.format(time() - tstart1))
    #
    i = []
    j = []
    i_b = []
    j_b = []
    # positions_b = np.dot(scaled_positions_b, cell)
    for pair, cutoff in cutoffs.items():
        indices_i = np.where(array1['species'] == pair[0])[0]
        indices_j = np.where(array2['species'] == pair[1])[0]
        if len(indices_i) == 0 or len(indices_j) == 0: continue
        indices_min = None
        # qurey the less one is faster, flip is needed
        flip = False
        if len(indices_i) > len(indices_j):
            flip = True
            tmp = indices_i
            indices_i = indices_j
            indices_j = tmp
        p1 = array1['positions'][indices_i]
        p2 = array2['positions'][indices_j]
        # find max
        indices_max = primitive_neighbor_kdtree(p1, 
            p2, cutoff = cutoff[1], parallel = 1)
        # find min
        if cutoff[0] > 1e-6:
            indices_min = primitive_neighbor_kdtree(p1, 
                p2, cutoff = cutoff[0], parallel = 1)
        #
        n = len(p1)
        j1 = []
        i1 = []
        if indices_min is not None:
            for k in range(n):
                indices_mid = set(indices_max[k]) - set(indices_min[k])
                m = len(indices_mid)
                if m ==0: continue
                i1.extend([indices_i[k]]*m)
                j1.extend(indices_j[indices_mid])
        else:
            for k in range(n):
                # offsets1 = offsets[indices[k]]
                m = len(indices_max[k])
                i1.extend([indices_i[k]]*m)
                j1.extend(indices_j[indices_max[k]])
        # map indices to original atoms, and the boudary atoms
        if flip:
            tmp = j1
            j1 = i1
            i1 = tmp
        i_b.extend(i1)
        j_b.extend(j1)
        """
        i.extend(indices[i1])
        j.extend(indices[j1])
        """
    # Compute distance vectors.
    # print(indices3[i1][:, 0])
    tstart1 = time()
    distance_vector = array1['positions'][i_b] - array2['positions'][j_b]
    # distance_vectors.append(distance_vector)
    distances = np.sqrt(np.sum(distance_vector*distance_vector, axis = 1))
    """
    offsets_i = offsets[i_b]
    offsets_j = offsets[j_b]
    """
    # print('Build distances: {:1.2f}'.format(time() - tstart))
    #=====================================
    retvals = []
    for q in quantities:
        if q == 'i':
            retvals += [i_b]
        elif q == 'j':
            retvals += [j_b]
        elif q == 'D':
            retvals += [distance_vector]
        elif q == 'd':
            retvals += [distances]
        
        else:
            raise ValueError('Unsupported quantity specified.')
        """
        elif q == 'S':
            retvals += [offsets_i, offsets_j]
        """
    print('Build bondlist: {:1.2f}'.format(time() - tstart))
    if len(retvals) == 1:
        return retvals[0]
    else:
        return tuple(retvals)

def primitive_neighbor_kdtree(positions1, positions2, 
                cutoff = 1.0, parallel = 2):
    """
    """
    from scipy.spatial import KDTree
    #
    tstart = time()
    tree = KDTree(positions2)
    indices = tree.query_ball_point(positions1, r = cutoff, workers=parallel)
    # print('KDTree: {:1.2f}'.format(time() - tstart))
    return indices

def cellPlanes(cell, origin = np.array([0, 0, 0])):
    """
    build six planes for the six faces of a cell
    """
    c1, c2, c3 = cell
    normals = np.zeros((6, 3))
    points = np.zeros((6, 3))
    normals[0] = np.cross(c2, c3)
    normals[1] = -normals[0]
    normals[2] = np.cross(c3, c1)
    normals[3] = -normals[2]
    normals[4] = np.cross(c1, c2)
    normals[5] = -normals[4]
    norm = np.linalg.norm(normals, axis=1) + 1e-8
    normals = normals/norm[:, None]
    points[0] = origin
    points[1] = origin + c1
    points[2] = origin
    points[3] = origin + c2
    points[4] = origin
    points[5] = origin + c3
    planes = []
    for i in range(3):
        plane = [{'normals': normals[2*i], 'points': points[2*i]},
                 {'normals': normals[2*i + 1], 'points': points[2*i + 1]}]
        planes.append(plane)
    return planes

def pointCellDistance(points, cell, origin = np.zeros(3)):
    """
    get distance between point and the six faces of a cell.
    """
    planes = cellPlanes(cell, origin = origin)
    distances = []
    npoint = len(points)
    distances = np.zeros((3, 2, npoint))
    for i in range(3):
        for j in range(2):
            vec = points - planes[i][j]['points']
            distances[i, j, :] = np.dot(vec, planes[i][j]['normals'])
    return distances

def build_boundary(species, positions, cell, pbc, boundary, include_self = False):
    """
    find region outside cell for periodic caculation, supercell 
    
    todo: boundary > 1
    """
    from functools import reduce
    tstart = time()
    wraped_positions = wrap_positions(positions, cell, pbc=pbc)
    distances = pointCellDistance(wraped_positions, cell)
    ib = np.array([[0, 1], [0, 1], [0, 1]])
    natom = len(positions)
    ind = np.arange(natom)
    # find atoms close to cell face with distance of r
    indices = [[], [], []]
    nb = 0
    for i in range(3):
        if not pbc[i]: continue
        ind0 =  np.where((distances[i, 0, :] < boundary[i, 1]))[0]
        ind1 =  np.where((distances[i, 1, :] < boundary[i, 0]))[0]
        indices[i] = [ind0, ind1]
        nb += len(ind0) + len(ind1)
    # print(indices)
    # init
    # repeat the scaled_positions so that it completely covers the boundary
    positions_b = np.zeros((27*nb, 3))
    offsets_b = np.zeros((27*nb, 3), dtype=int)
    indices_b = np.zeros(27*nb, dtype=int)
    species_b = np.zeros(27*nb, dtype = 'U20')
    # build face
    offset = [1, -1]
    nb1 = 0
    nb2 = 0
    for c in range(3):
        if not pbc[i]: continue
        for i in range(2):
            nb2 = nb1 + len(indices[c][i])
            indices_b[nb1:nb2] = indices[c][i]
            positions_b[nb1:nb2] = positions[indices[c][i]]
            offsets_b[nb1:nb2][:, c] = offset[i]
            nb1 = nb2
    # build edge
    for c in [[0, 1], [0, 2], [1, 2]]:
        if not pbc[c[0]] and not pbc[c[1]]: continue
        for i in range(2):
            for j in range(2):
                indices_j = np.intersect1d(indices[c[0]][i], indices[c[1]][j])
                nb2 = nb1 + len(indices_j)
                indices_b[nb1:nb2] = indices_j
                positions_b[nb1:nb2] = positions[indices_j]
                offsets_b[nb1:nb2][:, c[0]] = offset[i]
                offsets_b[nb1:nb2][:, c[1]] = offset[j]
                nb1 = nb2
    # build corner
    if pbc[0] and pbc[1] and pbc[2]:
        for i in range(2):
            for j in range(2):
                for k in range(2):
                    indices3 = reduce(np.intersect1d, 
                            (indices[0][i], indices[1][j], indices[2][k]))
                    nb2 = nb1 + len(indices3)
                    indices_b[nb1:nb2] = indices3
                    positions_b[nb1:nb2] = positions[indices3]
                    offsets_b[nb1:nb2][:, 0] = offset[i]
                    offsets_b[nb1:nb2][:, 1] = offset[j]
                    offsets_b[nb1:nb2][:, 2] = offset[k]
                    nb1 = nb2
    positions_b = positions_b[0:nb2]
    indices_b = indices_b[0:nb2]
    species_b = species[indices_b]
    offsets_b = offsets_b[0:nb2]
    positions_b = positions_b + np.dot(offsets_b, cell)
    if include_self:
            positions_b = np.append(positions, positions_b, axis = 0)
            indices_b = np.append(np.arange(natom), indices_b)
            species_b = np.append(species, species_b)
            offsets_b = np.append(np.zeros((natom, 3)), offsets_b, axis = 0)

    # print('build boundary: {:1.2f}'.format(time() - tstart))
    boundary_data = {
        'positions': positions_b,
        'indices': indices_b,
        'species': species_b,
        'offsets': offsets_b,
    }
    return boundary_data

def test_kdtree(atoms, cutoffs1, cutoffs2):
    
    tstart = time()
    i, j, d, S = neighbor_list('ijdS', atoms, cutoffs1)
    print('time %s'%(time() - tstart))
    if len(i) < 50:
        print(i, j, d)
    tstart = time()
    cell = atoms.get_cell(complete=True)
    species0 = np.array(atoms.get_chemical_symbols())
    positions0 = atoms.positions
    i, j, d, offsets_i, offsets_j = neighbor_kdtree_pbc('ijdS', 
            species0, positions0, cell, atoms.pbc, cutoffs2)
    # i, j, d = neighbor_kdtree('ijd', 
            # array1, array2, cell, cutoffs2)
    print('time %s'%(time() - tstart))
    if len(i) < 50:
        print(i, j, d)

def test_pointCellDistance():
    from ase.io import read, write
    from ase.build import molecule, bulk
    from ase.visualize import view
    atoms = molecule('H2O')
    # atoms.center(3)
    # atoms = bulk('Pt', cubic=True)
    atoms.pbc = True
    positions = atoms.positions
    distances = pointCellDistance(positions, atoms.cell)
    print(distances)

def test_buildBoundary(atoms, cutoffs):
    maxCutoff = np.array([x for x in cutoffs.values()]).max()
    positions = atoms.positions
    species = np.array(atoms.get_chemical_symbols())
    positions_b, indices_b, species_b, offsets_b =  \
            build_boundary(species, positions, atoms.cell, atoms.pbc, maxCutoff)
    face = Atoms(species_b, positions_b)
    # face = Atoms(['O']*len(species_b), positions_b + np.dot(offsets_b, atoms.cell))
    # print(face)
    # view(atoms + face)

if __name__ == "__main__":
    from ase.io import read, write
    from ase.build import molecule, bulk
    from ase.visualize import view
    from ase import Atom, Atoms
    from ase.neighborlist import neighbor_list
    atoms = molecule('H2O')
    atoms.pbc = True
    atoms.center(0.5)
    # atoms = bulk('Au', cubic = True)
    # atoms.cell = [4, 7, 5]
    # atoms = read('/home/xing/batoms/datas/mof-5.cif')
    atoms = read('/home/xing/batoms/datas/atp.pdb')
    print(atoms.pbc)
    # atoms = atoms*[4, 4, 4]
    # atoms = read('/home/xing/batoms/datas/1tim.pdb')
    print(len(atoms))
    # view(atoms)
    cutoffs1 = {
        ('O', 'H'): 1.261, 
        ('C', 'H'): 1.261, 
        ('C', 'C'): 1.261, 
            ('Au', 'Au'):3.0,
                }
    cutoffs2 = {
        ('O', 'H')  : [0.000, 1.261],
        ('C', 'H')  : [0.000, 1.261],
        ('C', 'C')  : [0.000, 1.261],
        # (79, 79): [0, 3.0],
        # (1, 8)  : [1.200, 2.100],
        }
    # test_buildBoundary(atoms, cutoffs2)
    test_kdtree(atoms, cutoffs1, cutoffs2)