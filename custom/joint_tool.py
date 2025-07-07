import pymel.core as pm
import maya.cmds as cmds
from mgear.core import primitive, transform
import maya.api.OpenMaya as om2

def addJntVanilla(
    obj=False, parent=False, noReplace=False, grp=None, jntName=None, *args
):
    """Create one joint for each selected object.

    Args:
        obj (bool or dagNode, optional): The object to drive the new
            joint. If False will use the current selection.
        parent (bool or dagNode, optional): The parent for the joint.
            If False will try to parent to jnt_org. If jnt_org doesn't
            exist will parent the joint under the obj
        noReplace (bool, optional): If True will add the extension
            "_jnt" to the new joint name
        grp (pyNode or None, optional): The set to add the new joint.
            If none will use "rig_deformers_grp"
        *args: Maya's dummy

    Returns:
        pyNode: The New created joint.

    """
    if not obj:
        oSel = pm.selected()
    else:
        oSel = [obj]

    for obj in oSel:
        if not parent:
            try:
                oParent = pm.PyNode("jnt_org")
            except TypeError:
                oParent = obj
        else:
            oParent = parent
        if not jntName:
            if noReplace:
                jntName = "_".join(obj.name().split("_")) + "_jnt"
            else:
                jntName = "_".join(obj.name().split("_")[:-1]) + "_jnt"
        mtx = om2.MMatrix(cmds.xform(obj.name(), q=True, worldSpace=True, m=True))
        t_mtx = om2.MTransformationMatrix(mtx)
        jnt = primitive.addJoint(oParent, jntName, t_mtx)

        if grp:
            grp.add(jnt)
        else:
            try:
                defSet = pm.PyNode("rig_deformers_grp")
                pm.sets(defSet, add=jnt)
            except TypeError:
                pm.sets(n="rig_deformers_grp")
                defSet = pm.PyNode("rig_deformers_grp")
                pm.sets(defSet, add=jnt)

        jnt.setAttr("segmentScaleCompensate", False)
        jnt.setAttr("jointOrient", 0, 0, 0)

        pm.parentConstraint(obj, jnt)

    return jnt