"""

Lattice Planes

To insert lattice planes in structural models.
"""
from numpy.core.records import array
import bpy
from batoms.bondsetting import Setting, tuple2string
import numpy as np
from time import time
from batoms.tools import get_equivalent_indices
import bmesh

class PlaneSetting(Setting):
    """
    PlaneSetting object

    The PlaneSetting object store the polyhedra information.

    Parameters:

    label: str
        The label define the batoms object that a Setting belong to.

    """
    def __init__(self, label, no = None, plane = None) -> None:
        Setting.__init__(self, label)
        self.name = 'bplane'
        self.no = no
        if plane is not None:
            for key, data in plane.items():
                self[key] = data
    def __setitem__(self, index, setdict):
        """
        Set properties
        """
        name = tuple2string(index)
        p = self.find(name)
        if p is None:
            p = self.collection.add()
        p.indices = index
        p.name = name
        p.flag = True
        for key, value in setdict.items():
            setattr(p, key, value)
        p.label = self.label
        if p.symmetry:
            setdict = p.as_dict()
            indices = get_equivalent_indices(self.no, p.indices)
            for index in indices:
                name = tuple2string(index)
                p1 = self.find(name)
                if p1 is None:
                    p1 = self.collection.add()
                for key, value in setdict.items():
                    setattr(p1, key, value)
                p1.name = name
                p1.indices = index
                p1.label = self.label

    def add(self, indices):
        self[indices] = {'indices': indices}
    def __repr__(self) -> str:
        s = '-'*60 + '\n'
        s = 'Indices   distance  crystal   symmetry  slicing\n'
        for p in self.collection:
            s += '{0:10s}   {1:1.3f}   {2:10s}  {3:10s}  {4:10s} \n'.format(\
                p.name, p.distance, str(p.crystal), str(p.symmetry), str(p.slicing))
        s += '-'*60 + '\n'
        return s
    def get_symmetry_indices(self):
        if self.no is None: return
        for p in self:
            if p.symmetry:
                indices = get_equivalent_indices(self.no, p.indices)
                for index in indices:
                    name = tuple2string(index)
                    p1 = self.find(name)
                    if p1 is None:
                        p1 = self.collection.add()
                        setdict = p.as_dict()
                        for key, value in setdict.items():
                            setattr(p1, key, value)
                        p1.name = name
                        p1.indices = index
                        p1.label = self.label
                        p1.flag = True
    def build_crystal(self, bcell):
        """
        Build crystal

        no: Int
            spacegroup number
        """
        self.get_symmetry_indices()
        planes = {}
        for p in self:
            if not p.crystal: continue
            normal = np.dot(p.indices, bcell.reciprocal)
            normal = normal/np.linalg.norm(normal)
            point = p.distance*normal
            planes[p.name] = {
                        'indices': p.indices, 
                        'normal': normal, 
                        'point':point, 
                        'vertices': [],
                        }
        # loop all planes, find the intersection point of three plane
        keys = list(planes.keys())
        n = len(keys)
        vertices = []
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    point = threePlaneIntersection([planes[keys[i]], 
                                        planes[keys[j]], 
                                        planes[keys[k]]])
                    # remove point outside plane
                    point = convexhull(planes, point)
                    if point is not None:
                        planes[keys[i]]['vertices'].append(point)
                        planes[keys[j]]['vertices'].append(point)
                        planes[keys[k]]['vertices'].append(point)
        new_planes = {}
        for name, plane in planes.items():
            p = self[plane['indices']]
            vertices, edges, faces = faces_from_vertices(plane['vertices'], plane['normal'])
            if len(vertices) > 3:
                new_planes[p.name] = self.get_plane_data(vertices, edges, faces, p)
        return new_planes

    def build_plane(self, bcell, include_center = False):
        """
        Build vertices, edges and faces of plane.
        
        """
        from scipy.spatial import ConvexHull
        from scipy.spatial import ConvexHull
        self.get_symmetry_indices()
        cellEdges = bcell.edges
        cellVerts = bcell.verts
        planes = {}
        for p in self:
            if p.crystal: continue
            intersect_points = []
            normal = np.dot(p.indices, bcell.reciprocal)
            normal = normal/np.linalg.norm(normal)
            # get intersection point
            for edge in cellEdges:
                line = cellVerts[edge]
                point = p.distance*normal
                intersect_point = linePlaneIntersection(line, normal, point)
                if intersect_point is not None:
                    intersect_points.append(intersect_point)
                # get verts, edges, faces by Hull
            if len(intersect_points) < 3: continue
            vertices, edges, faces = faces_from_vertices(intersect_points, normal, include_center = include_center)
            planes[p.name] = self.get_plane_data(vertices, edges, faces, p)
        self.planes = planes
        return planes
    def get_plane_data(self, vertices, edges, faces, p):
        """
        build edge
        """
        plane = {}
        if len(faces) > 0:
            plane= {'vertices': vertices, 
                    'edges': edges,
                    'faces': faces,
                    'color': p.color,
                    'indices': p.indices,
                    'edges_cylinder': {'lengths': [], 'centers': [], 
                            'normals': [], 'vertices': 6,
                            'color': (0.0, 0.0, 0.0, 1.0),
                            'width': p.width,
                            'battr_inputs': {},
                            }, 
                    'battr_inputs': {'bplane': p.as_dict()},
                    'show_edge': p.show_edge,
                    'slicing': p.slicing,
                    'boundary': p.boundary,
                    }
            for edge in edges:
                center = (vertices[edge[0]] + vertices[edge[1]])/2.0
                vec = vertices[edge[0]] - vertices[edge[1]]
                length = np.linalg.norm(vec)
                nvec = vec/length
                plane['edges_cylinder']['lengths'].append(length)
                plane['edges_cylinder']['centers'].append(center)
                plane['edges_cylinder']['normals'].append(nvec)
        return plane
    def build_slicing(self, name, volume, bcell, cuts = None, cmap = 'Spectral'):
        """
        Change plane to a 2D slicing plane.
        Use vertex color
        """
        from scipy import ndimage
        from ase.cell import Cell
        from batoms.butils import object_mode
        import matplotlib
        cell = Cell(bcell.array)
        plane = bpy.data.objects.get(name)
        object_mode()
        me = plane.data
        bm = bmesh.new()
        bm.from_mesh(me)
        # get maximum cuts based on the density
        if cuts is None:
            density = bcell.length/volume.shape
            maxlength = 0
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            for edge in bm.edges:
                v = bm.verts[edge.verts[0].index].co - bm.verts[edge.verts[1].index].co
                l = np.linalg.norm(v)
                if l > maxlength:
                    maxlength = l
            cuts = maxlength/np.min(density)
            print('cuts: ', cuts)
        # make mesh by subdivided
        bmesh.ops.subdivide_edges(bm,
                                edges = bm.edges,
                                cuts = cuts,
                                use_grid_fill = True,
                                )
        bm.to_mesh(me)
        me.update()
        # vertices to coordinates
        n = len(me.vertices)
        local_positions = np.empty(n*3, dtype=np.float64)
        me.vertices.foreach_get('co', local_positions)  
        local_positions = local_positions.reshape((n, 3))
        n = len(local_positions)
        # positions (natom, 3) to (natom, 4)
        local_positions = np.append(local_positions, np.ones((n, 1)), axis = 1)
        mat= np.array(plane.matrix_world)
        positions = mat.dot(local_positions.T).T
        # (natom, 4) back to (natom, 3)
        positions = positions[:, :3] - bcell.origin
        # get scaled positions
        scaled_positions = cell.scaled_positions(positions)
        index = scaled_positions*volume.shape
        # map new value
        new_volume = ndimage.map_coordinates(volume, index.T, order=1)
        dv = np.max(new_volume) - np.min(new_volume)
        new_volume = (new_volume - np.min(new_volume))/dv
        # map value to color by colormap
        cmap = matplotlib.cm.get_cmap(cmap)
        object_mode()
        bm = bmesh.new()
        bm.from_mesh(plane.data)
        volume_layer = bm.loops.layers.color.new('volume')

        for v in bm.verts:
            for loop in v.link_loops:
                color = cmap(new_volume[v.index])
                loop[volume_layer] = color
        bm.to_mesh(plane.data)  
        plane.data.update()
        plane.data.materials[0].use_backface_culling = True
        plane.data.materials[0].show_transparent_back = False
        # add node
        node_tree = plane.data.materials[0].node_tree
        nodes = node_tree.nodes
        mat_links = node_tree.links
        bsdf = nodes.get("Principled BSDF")
        assert(bsdf)
        vcol = nodes.new(type="ShaderNodeVertexColor")
        vcol.layer_name = "volume"
        mat_links.new(vcol.outputs['Color'], bsdf.inputs['Base Color'])
        # bpy.context.view_layer.objects.active = plane
        # bpy.ops.object.mode_set(mode='VERTEX_PAINT')
            
    def build_slicing_image(self, volume, bcell):
        """
        2D slicings of volumetric data by an arbitrary plane.
        Todo: calculate size
        """
        import pylab as plt
        self.get_symmetry_indices()
        shape = volume.shape
        slicings = {}
        for p in self:
            if not p.slicing: continue
            length = bcell.length
            d = p.distance/length
            index = [int(i) for i in d*shape]
            data = []
            if p.indices[0] == 1:
                data = volume[index[0], :, :]
                positions = d*bcell.array[0] + (bcell.array[1] + bcell.array[1])/2.0
                rotation = (np.pi/2, 0, 0)
                size = (length[1], length[2], 1)
            if p.indices[1] == 1:
                data = volume[:, index[1], :]
                positions = d*bcell.array[1] + (bcell.array[0] + bcell.array[2])/2.0
                rotation = (0, np.pi/2, 0)
                size = (length[0], length[2], 1)
            if p.indices[2] == 1:
                data = volume[:, :, index[2]]
                positions = d*bcell.array[2] + (bcell.array[0] + bcell.array[1])/2.0
                rotation = (0, 0, 0)
                size = (length[0], length[1], 1)
            imagename = '%s_image_%s.png'%(self.label, p.name)
            save_image(data, imagename, interpolation = 'bicubic')
            slicings[p.name] = {'imagename': imagename,
                              'location': positions,
                              'rotation': rotation,
                              'size': size}
        return slicings
    def build_boundary(self, indices, batoms = None):
        """
        Remove vertices above the plane
        """
        p = self[indices]
        normal = np.dot(p.indices, batoms.cell.reciprocal)
        normal = normal/np.linalg.norm(normal)
        point = p.distance*normal
        # isosurface, plane
        subcollections = ['atom', 'bond', 'polyhedra', 'volume',
'ghost', 'boundary', 'skin', 'plane']

        for coll in subcollections:
            for obj in batoms.coll.children['%s_%s'%(self.label, coll)].all_objects:
                if obj.type != 'MESH': continue
                n = len(obj.data.vertices)
                vertices = np.empty(n*3, dtype=np.float64)
                obj.data.vertices.foreach_get('co', vertices)  
                vertices = vertices.reshape((n, 3))
                x1 = np.dot(vertices, normal) - np.dot(point, normal)
                x2 = np.dot(np.array([0, 0, 0]), normal) - np.dot(point, normal)
                index = np.where(x1*x2 < -1e-6)[0]
                if len(index) == 0: continue
                if obj.batom.flag:
                    batoms[obj.batom.species].scale = (0.001, 0.001, 0.001)
                else:
                    bm = bmesh.new()
                    bm.from_mesh(obj.data)
                    bm.verts.ensure_lookup_table()
                    verts_select = [bm.verts[i] for i in index] 
                    bmesh.ops.delete(bm, geom=verts_select, context='VERTS')
                    bm.to_mesh(obj.data)


def save_image(data, filename, interpolation = 'bicubic'):
    """
    """
    import pylab as plt
    import numpy as np
    data = data.T
    size = np.shape(data)     
    print('size: ', size)
    fig = plt.figure(figsize=(size[1]/size[0]*10, 10))
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(data, interpolation=interpolation)
    plt.savefig(filename, dpi = 300) 

def faces_from_vertices(vertices, normal, include_center = False):
    """
    get faces from vertices
    """
    from scipy.spatial.distance import cdist
    # remove duplicative point
    vertices = np.unique(vertices, axis = 0)
    n = len(vertices)
    if n < 3: return vertices, [], []
    center = np.mean(vertices, axis = 0)
    v1 = vertices[0] - center
    angles = [[0, 0]]
    normal = normal/(np.linalg.norm(normal) + 1e-6)
    for i in range(1, n):
        v2 = vertices[i] - center
        x = np.cross(v1, v2)
        c = np.sign(np.dot(x, normal))
        angle = np.arctan2(c, np.dot(v1, v2))
        angles.append([i, angle])
    # search convex polyhedra
    angles = sorted(angles,key=lambda l:l[1])
    if not include_center:
        faces = [[a[0] for a in angles]]
        edges = [[angles[0][0], angles[-1][0]]]
        for i in range(0, n - 1):
            edges.append([angles[i][0], angles[i + 1][0]])
    else:
        # add center to vertices
        vertices = np.append(vertices, center.reshape(1, 3), axis = 0)
        icenter = len(vertices) - 1
        faces = [[angles[0][0], angles[-1][0], icenter]]
        edges = [[angles[0][0], icenter], 
                [angles[0][0], angles[-1][0]], 
                [angles[-1][0], icenter]]
        for i in range(0, n - 1):
            faces.append([angles[i][0], angles[i + 1][0], icenter])
            edges.extend([[angles[i][0], angles[i + 1][0]],
                        [angles[i][0], icenter],
                        [angles[i + 1][0], icenter]])
    return vertices, edges, faces

def linePlaneIntersection(line, normal, point):
    """
    3D Line Segment and Plane Intersection
    - Point
    - Line contained in plane
    - No intersection
    """
    d = np.dot(point, normal)
    normalLine = line[0] - line[1]
    a = np.dot(normalLine, normal)
    # No intersection or Line contained in plane
    if np.isclose(a, 0):
        return None
    # in same side
    b = np.dot(line, normal) - d
    if b[0]*b[1] > 0:
        return None
    # Point
    v = point - line[0]
    d = np.dot(v, normal)/a
    point = np.round(line[0] + normalLine*d, 6)
    return point

def threePlaneIntersection(planes):
    """
    3D three Planes Intersection
    """
    # Condition for a single point of intersection
    mat = np.concatenate([[plane['normal']] for plane in planes], axis = 0)
    det = np.linalg.det(mat)
    if np.isclose(det, 0):
        return None
    darray = np.array([np.dot(plane['point'], plane['normal']) for plane in planes])
    point = np.zeros(3)
    for i in range(3):
        temp = mat.copy()
        temp[:, i] = darray
        point[i] = round(np.linalg.det(temp)/det, 6)
    return point
def convexhull(planes, point):
    """
    find points at the same side of origin for all planes
    Todo: '+' or '-'
    """
    Flag = True
    if point is None: return None
    for name, plane in planes.items():
        x1 = np.dot(point, plane['normal']) - np.dot(plane['point'], plane['normal'])
        x2 = np.dot(np.array([0, 0, 0]), plane['normal']) - np.dot(plane['point'], plane['normal'])
        if abs(x1) > 1e-6 and x1*x2 < -1e-6:
            flag = False
            return None
    return point
