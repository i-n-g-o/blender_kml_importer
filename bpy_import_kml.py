# written 2021 by Ingo Randolf
#
# inspired by 'GES_Panel', imagiscope 2020
# based on STL importer shipped with blender


# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

bl_info = {
    "name": "KML Importer",
    "description": "Import kml files",
    "author": "Ingo Randolf",
    "version": (1, 0, 0),
    "blender": (2, 81, 6),
    "location": "File > Import-Export",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Import-Export"}


"""
Import KML files
"""

import os, time
import bpy, mathutils, math, bmesh

from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
)
from bpy_extras.io_utils import (
    ImportHelper,
    orientation_helper,
    axis_conversion,
)
from bpy.types import (
    Operator,
    OperatorFileListElement,
)
from xml.dom.minidom import parse
from xml.dom.minidom import Node
from xml.etree import cElementTree as ElementTree


def load_kml(context, filepath, scale = 1, usepoints = False, curvetype = 'POLY'):
    	
    earth = 6371008.7714 # earth mean radius  in meters (IUGG) - https://en.wikipedia.org/wiki/Earth_radius
    filename = bpy.path.display_name_from_filepath(filepath)
    
    # make a new curve
    crv = bpy.data.curves.new('crv', 'CURVE')
    crv.dimensions = '3D'
    
    # make a new spline in that curve
    spline = crv.splines.new(type=curvetype)
    spline.resolution_u = 6
    spline.order_u = 12
    
    # load kml file
    filepath = bpy.path.abspath(filepath)
    domData = parse(filepath)
    coords = domData.getElementsByTagName("coordinates")

    points = []
    if coords.length != 0:
        for i in range(0, coords.length ):
            if usepoints and coords[i].parentNode.nodeName == "Point":
                points.append(list(map(float, coords[i].firstChild.nodeValue.strip().split(","))))
            elif not usepoints and coords[i].parentNode.nodeName != "Point":
                nodevalue = coords[i].firstChild.nodeValue.strip()
                # split nodevalue by spaces or whitespaces
                pts = nodevalue.split()
                for i in range(0, len(pts)-1):
                    if not pts[i]:
                        continue
                    # split on seperators
                    l = pts[i].split(',')
                    if len(l) < 2:
                        continue
                    # make sure we have altitude?
                    if len(l) < 3:
                        l.append("0")
                    # append to points    
                    points.append(list(map(float, l)))
                break
                
    if coords.length == 0 or len(points) == 0:
        # try to get points from gx:coord
        gxcoor = domData.getElementsByTagName("gx:coord")
        if gxcoor.length != 0:
            for i in range(0, gxcoor.length):
                l = gxcoor[i].firstChild.nodeValue.strip().split()
                if len(l) < 2:
                    continue
                if len(l) < 3:
                    l.append("0")
                # append to points
                points.append(list(map(float, l)))

    # check if we have some points
    if len(points) == 0:
        print("no coordinates found")
        return    
    
    
    # convert lat/lon to points in 3D space on globe
    prevx = 0
    prevy = 0
    points_cart = []
    
    for i in range(0, len(points)):
        # get gps coordinates
        lon = points[i][0]
        lat = points[i][1]
        alt = points[i][2]
        # calculate cartesian coordinates
        phi = (90 - lat) * (math.pi / 180);
        theta = (lon + 180) * (math.pi / 180);
        px = -((earth + alt) * math.sin(phi) * math.cos(theta));
        py = -((earth + alt) * math.sin(phi) * math.sin(theta));
        pz = ((earth + alt) * math.cos(phi))
        points_cart.append( [px, py, pz] )
                

    # spline origin
    ox = points_cart[0][0]
    oy = points_cart[0][1]
    oz = points_cart[0][2]
    
    # add points to spline
    if spline.type == "BEZIER":
        spline.bezier_points.add(len(points_cart)-1)
        splinepoints = spline.bezier_points
    else:
        spline.points.add(len(points_cart)-1)
        splinepoints = spline.points
        
    
    for p, new_co in zip(splinepoints, points_cart):
        px = new_co[0];
        py = new_co[1];
        pz = new_co[2];
        if spline.type == "BEZIER":
            p.co = (float((px - ox) * scale), float((py -oy) * scale), float((pz - oz) * scale))
            p.handle_left_type = 'AUTO'
            p.handle_right_type = 'AUTO'
        else:
            p.co = (float((px - ox) * scale), float((py -oy) * scale), float((pz - oz) * scale), 1.0)
        
    # create curve object
    obj = bpy.data.objects.new(filename, crv)
    bpy.data.collections['Collection'].objects.link(obj)

    # add north arrow
    bpy.ops.object.empty_add(type='SINGLE_ARROW', location=(0,0,0), rotation=(90,0,0)) # create empty container
    north = bpy.context.selected_objects[0]
    north.name = "North"
    
    # add up arrow
    bpy.ops.object.empty_add(type='SINGLE_ARROW', location=(0,0,0), rotation=(90,0,0)) # create empty container
    up = bpy.context.selected_objects[0]
    up.name = "Up"
    
    # up-vector look at first point
    q = mathutils.Vector((0, 0, 1)).rotation_difference(mathutils.Vector((ox/earth, oy/earth, oz/earth)))
    up.rotation_euler = q.to_euler()
    
    north.rotation_euler = q.to_euler()
    north.rotation_euler.rotate_axis("Y", math.radians(-90))

    # add plane axes
    bpy.ops.object.empty_add()
    axes = bpy.context.selected_objects[0]
    axes.name = "Original Axes"
    
    # parent axes to obj
    setParent(obj, axes)
    
    # parent obj and north to up 
    setParent(up, obj)
    setParent(up, north)
    
    # set up rotation
    up.rotation_euler.x = 0
    up.rotation_euler.y = 0
    up.rotation_euler.z = 0
    
    # clear parents (keep transform)
    clearParent(obj)
    clearParent(north)
    
    # apply rotation to obj
    applyRotation(obj)
    
    # re-set parents
    setParent(obj, up)
    setParent(obj, north)
    
    
def select(obj):
    # deselect all
    bpy.ops.object.select_all(action='DESELECT')
    # select object
    obj.select_set(True)
        
def applyRotation(obj):
    select(obj)
    # apply
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    
def clearParent(obj, type='CLEAR_KEEP_TRANSFORM'):
    select(obj)    
    # clear parent
    bpy.ops.object.parent_clear(type=type)
    
def setParent(parent, child, keepTransform=True):
    select(parent)
    child.select_set(True)

    # the active object will be the parent of all selected object
    bpy.context.view_layer.objects.active = parent
    
    # parent - keep transform
    bpy.ops.object.parent_set(keep_transform=keepTransform)
    
    bpy.ops.object.select_all(action='DESELECT')
    
    

@orientation_helper(axis_forward='Y', axis_up='Z')
class ImportKML(bpy.types.Operator, ImportHelper):
    
    """Load a KML file"""
    bl_idname = "import_mesh.kml"
    bl_label = "Import KML"
    bl_description = 'Importer...'
    bl_options = {'UNDO'}

    filename_ext = ".kml"
    
    filter_glob: StringProperty(
        default="*.kml",
        options={'HIDDEN'}
    )
    files: CollectionProperty(
        name="File Path",
        type=OperatorFileListElement,
    )
    directory: StringProperty(
        subtype='DIR_PATH',
    )
    global_scale: FloatProperty(
        name="Scale",
        soft_min=0.001, soft_max=1000.0,
        min=1e-6, max=1e6,
        default=1.0,
    )
    use_points: BoolProperty(
        name="Use Points",
        description="Use Points instead of path",
        default=False,
    )
    v_curve: EnumProperty(
        name="Curve",
        items=[('POLY',"Poly",""),('BEZIER', "Bezier", ""),('NURBS',"Nurbs","")]
    )

    def execute(self, context):
        import os
        from mathutils import Matrix
        
        paths = [os.path.join(self.directory, name.name)
                 for name in self.files]
                 
        if not paths:
            paths.append(self.filepath)

        for path in paths:
            load_kml(context, path, self.global_scale, self.use_points, self.v_curve)

        return {'FINISHED'}

    
def menu_import(self, context):
    self.layout.operator(ImportKML.bl_idname, text="kml (.kml)")

def register():
    bpy.utils.register_class(ImportKML)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)

def unregister():
    bpy.utils.unregister_class(ImportKML)
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)

if __name__ == "__main__":
    register()
