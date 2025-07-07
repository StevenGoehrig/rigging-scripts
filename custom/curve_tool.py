import maya.cmds as cmds
import maya.api.OpenMaya as om2
import pymel.core as pm
from mgear.core import curve
import json

import sys

def getDagPath(obj):
    if not isinstance(obj, str):
        objName = cmds.ls(obj)[0]
    sel = om2.MSelectionList()
    sel.add(objName)
    dag_path = sel.getDagPath(0)
    return dag_path
    
def getFnCurve(obj):
    dag_path = getDagPath(obj)
    fn_curve = om2.MFnNurbsCurve(dag_path)
    return fn_curve

def mayaSelRange(vals):
    """Convert maya cmds.ls() component selection list into indices

    Arguments:
        vals (list): A list of components like what you get out of cmds.ls(sl=True)

    Returns:
        list: A list of integer indices
    """
    out = []
    for val in vals:
        nn = val.split('[')[1][:-1].split(':')
        nn = list(map(int, nn))
        out.extend(range(nn[0], nn[-1] + 1))
    return out


def buildNeighborDict(vertColl):
    """ Parse vertices into a dictionary of neighbors, limited to the original vertex set

    Arguments:
        vertColl (list):  A list of verts like what you get out of cmds.ls(sl=True)

    Returns:
        dict: A dictionary formatted like {vertIndex: [neighborVertIdx, ...], ...}
    """
    # Get the object name
    obj = vertColl[0]
    objName = obj.split('.')[0]
    verts = set(mayaSelRange(vertColl))
    neighborDict = {}
    for v in verts:
        vname = f'{objName}.vtx[{v}]'
        edges = cmds.polyListComponentConversion(vname, fromVertex=True, toEdge=True)
        neighbors = cmds.polyListComponentConversion(
            edges, fromEdge=True, toVertex=True
        )
        neighbors = set(mayaSelRange(neighbors))
        neighbors.remove(v)
        neighborDict[v] = list(neighbors & verts)
    return neighborDict, objName


def sortLoops(neighborDict):
    """Sort vertex loop neighbors into individual loops

    Arguments:
        neighborDict (dict):  A dictionary formatted like {vertIndex: [neighborVertIdx, ...], ...}

    Returns:
        list of lists: A list of lists containing ordered vertex loops.
            Only if the loop is closed, the first and last element will be the same.
    """
    neighborDict = dict(neighborDict)  # work on a copy of the dict so I don't destroy the original
    loops = []

    # If it makes it more than 1000 times through this code, something is probably wrong
    # This way I don't get stuck in an infinite loop like I could with while(neighborDict)
    for _ in range(1000):
        if not neighborDict:
            break
        vertLoop = [list(neighborDict.keys())[0]]
        vertLoop.append(neighborDict[vertLoop[-1]][0])

        # Loop over this twice: Once forward, and once backward
        # This handles loops that don't connect back to themselves
        for i in range(2):
            vertLoop = vertLoop[::-1]
            while vertLoop[0] != vertLoop[-1]:
                nextNeighbors = neighborDict[vertLoop[-1]]
                if len(nextNeighbors) == 1:
                    break
                elif nextNeighbors[0] == vertLoop[-2]:
                    vertLoop.append(nextNeighbors[1])
                else:
                    vertLoop.append(nextNeighbors[0])

        # Remove vertices I've already seen from the dict
        # Don't remove the same vert twice if the first and last items are the same
        start = 0
        if vertLoop[0] == vertLoop[-1]:
            start = 1
        for v in vertLoop[start:]:
            del neighborDict[v]
        loops.append(vertLoop)
    else:
        raise RuntimeError("You made it through 1000 loops, and you still aren't done?  Something must be wrong")
    return loops
    
def getMinZVert(loop):
    minZ = None
    minZVert = None
    for vert in loop:
        pos = vert.getPosition(space="world")
        if minZ is None or pos[2] < minZ:
            minZ = pos[2]
            minZVert = vert
    return minZVert

def zSortLoop(loop):
    loop = loop[:-1]
    minZVert = getMinZVert(loop)
    index = loop.index(minZVert)
    zSortedLoop = loop[index:] + loop[:index] + [minZVert]
    return zSortedLoop
    
def vertSortLoop(loop, per, first_vert):
    if per:
        loop = loop[:-1]
    print(loop)
    index = loop.index(pm.PyNode(first_vert))
    if per:
        vSortedLoop = loop[index:] + loop[:index] + [pm.PyNode(first_vert)]
    else:
        vSortedLoop = loop[index:] + loop[:index]
    return vSortedLoop

def fillVertexNames(objName, sorted_loop):
    sorted_named_loop = []
    for vertex in sorted_loop:
        sorted_named_loop.append(f'{objName}.vtx[{vertex}]')
    return sorted_named_loop

def getVertexPositions(vertex_loop, per, start='z'):
    print(vertex_loop)
    neighborDict, objName = buildNeighborDict(vertex_loop)
    sorted_loop = sortLoops(neighborDict)[0]
    sorted_named_loop = fillVertexNames(objName, sorted_loop)
    vertex_nodes = [pm.PyNode(vertex) for vertex in sorted_named_loop]
    if start == 'z':
        reSortedLoop = zSortLoop(vertex_nodes)
    else:
        print(vertex_nodes)
        reSortedLoop = vertSortLoop(vertex_nodes, per, start)
        print(reSortedLoop)
    vertex_positions = [vertex_node.getPosition(space="world") for vertex_node in reSortedLoop]
    return (vertex_positions)

def createCurve(selection, name, start='z', parent=None, per=False):
    vertex_positions = getVertexPositions(selection, per, start)
    print(vertex_positions)
    if per:
        if vertex_positions[0] == vertex_positions[-1]:
            vertex_positions = vertex_positions[:-1]
    new_curve = curve.addCurve(parent, name, vertex_positions, degree=3, close=per)
    return new_curve

def createCurveFromCurve(srcCrv, name, nbPoints, parent=None, per=True):
    """Create a curve from a curve
 
    Arguments:
        srcCrv (curve): The source curve.
        name (str): The new curve name.
        nbPoints (int): Number of control points for the new curve.
        parent (dagNode): Parent of the new curve.

    Returns:
        dagNode: The newly created curve.
    """
    param = getParamPositionsOnCurve(srcCrv, nbPoints)

    crv = curve.addCurve(parent, name, param, close=per, degree=3)
    return crv
    
def createBSCurve(cvPositions, name, parent=None, per=False):
    """Create a curve from a curve
 
    Arguments:
        srcCrv (curve): The source curve.
        name (str): The new curve name.
        nbPoints (int): Number of control points for the new curve.
        parent (dagNode): Parent of the new curve.

    Returns:
        dagNode: The newly created curve.
    """
    # srcCurveCVs = srcCrv.getCVs(space="world")
    # cvPositions = []
    # for i, cv in enumerate(srcCurveCVs):
    #     if i % 3 == 0:
    #         cvPositions.append(cv)
    # if per:
    #     cvPositions = cvPositions[:-1]

    crv = curve.addCurve(parent, name, cvPositions, close=per, degree=1)
    return crv

def getParamPositionsOnCurve(srcCrv, nbPoints):
    """get param position on curve

    Arguments:
        srcCrv (curve): The source curve.
        nbPoints (int): Number of points to return.

    Returns:
        tuple: world positions.
    """
    fn_curve = getFnCurve(srcCrv)
    length = fn_curve.length()
    parL = fn_curve.findParamFromLength(length)
    param = []
    increment = parL / (nbPoints - 1)
    p = 0.0
    for x in range(nbPoints):
        # we need to check that the param value never exceed the parL
        if p > parL:
            p = parL
        if fn_curve.isParamOnCurve(p):
            pos = fn_curve.getPointAtParam(p, space=om2.MSpace.kWorld)
            param.append(pos)
        p += increment

    return param

def pathCns(obj, curve, cnsType=False, u=0, tangent=False, rot=True):
    """
    Apply a path constraint or curve constraint.

    Arguments:
        obj (dagNode): Constrained object.
        curve (Nurbscurve): Constraining Curve.
        cnsType (int): 0 for Path Constraint, 1 for Curve
            Constraint (Parametric).
        u (float): Position of the object on the curve (from 0 to 100 for path
            constraint, from 0 to 1 for Curve cns).
        tangent (bool): Keep tangent orientation option.

    Returns:
        pyNode: The newly created constraint.
    """
    node = pm.PyNode(pm.createNode("motionPath"))
    node.setAttr("uValue", u)
    node.setAttr("fractionMode", not cnsType)
    node.setAttr("follow", tangent)

    curve_shape = pm.listRelatives(curve, shapes=True)[0]
    pm.connectAttr(curve_shape.attr("worldSpace"), node.attr("geometryPath"))
    pm.connectAttr(node.attr("allCoordinates"), obj.attr("translate"))
    if rot == True:
        pm.connectAttr(node.attr("rotate"), obj.attr("rotate"))
        pm.connectAttr(node.attr("rotateOrder"), obj.attr("rotateOrder"))
    pm.connectAttr(node.attr("message"), obj.attr("specifiedManipLocation"))

    return node