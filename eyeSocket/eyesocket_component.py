from maya import cmds
import pymel.core as pm
from PySide6 import QtCore, QtGui, QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from mgear.core import curve, primitive, icon, transform, vector
from functools import partial
from custom import curve_tool, joint_tool, orientation_tool

def get_vertex_loop_from_selection(): #TODO move to it's own script
    selection = cmds.ls(sl=True, fl=True)
    return str(selection)
    if selection:
        vertex_list = ""
        separator = ""
        for vertex in selection:
            if vertex_list:
                separator = ","
            vertex_list = vertex_list + separator + str(vertex)
        if not vertex_list:
            pm.displayWarning("Please select first the vertex loop.")
        elif len(vertex_list.split(",")) < 4:
            pm.displayWarning("The minimun vertex count is 4")
            return vertex_list
    else:
        pm.displayWarning("Please select first the vertex loop.")

class EyeSocketComponent():
    def __init__(self, vertex_loop, inner_vertex, name_prefix, side, ctl_suffix, eye_joint, parent_node, head_joint):
        self.vertex_loop = vertex_loop
        self.inner_vertex = inner_vertex
        self.name_prefix = name_prefix
        self.side = side
        self.ctl_suffix = ctl_suffix
        self.eye_joint = eye_joint
        self.parent_node = parent_node
        self.head_joint = head_joint
        self.ctl_locs, self.control_num, self.bindCurve, self.ctlCurve, self.cvNum, self.socket_root, self.socketCrv_root, self.socketRope_root = self.create_guides()
    
    def setName(self, name, idx=None):
            namesList = [self.name_prefix, self.side, name]
            if idx is not None:
                namesList[1] = self.side + str(idx)
            name = "_".join(namesList)
            return name
    
    def create_guides(self):
        vertex_list = []
        for vertex in self.vertex_loop.split(','):
            vertex = vertex.replace("'", "")
            vertex_list.append(vertex.strip())
        vertex_list[0] = vertex_list[0].replace('[', '', 1)
        vertex_list[-1] = vertex_list[-1].replace(']', '', 1)

        #Create Root Nodes
        socket_root = primitive.addTransform(None, self.setName('socket_root'))
        socketCrv_root = primitive.addTransform(socket_root, self.setName('socketCrv_root'))
        socketRope_root = primitive.addTransform(socket_root, self.setName('socketRope_root'))
        #Create Bind Curve
        bindCurve = curve_tool.createCurve(vertex_list, self.setName('bindCurve'), start=self.inner_vertex, parent=socketCrv_root, per=True)

        control_num = 12
        cvNum = (control_num * 3) + 3 #add 3 because it's a periodic curve and 3 of the CVs are hidden
        ctlCurve = curve_tool.createCurveFromCurve(bindCurve,
                                               self.setName('ctlCurve'),
                                               nbPoints=cvNum,
                                               parent=socketCrv_root)
        ctlCVs = ctlCurve.getCVs(space="world")
        ctlCVs = ctlCVs[:-3] # Remove the last 3 elements since it's a periodic curve

        ctl_locs = []                                       
        for i, cv in enumerate(ctlCVs):
            if i % 3 == 0:
                ctlNum = int(i / 3)
                loc = cmds.spaceLocator(n=f'ctl_position_{ctlNum}')
                ctl_locs.append(loc)
                cmds.xform(loc, t=cv)
            
        # Hide curves and prevent double transformations
        cmds.setAttr(f'{socketCrv_root}.visibility', 0)
        cmds.setAttr(f'{socketRope_root}.visibility', 0)
        cmds.setAttr(f'{socketCrv_root}.inheritsTransform', 0)
        cmds.setAttr(f'{socketRope_root}.inheritsTransform', 0)
        
        return ctl_locs, control_num, bindCurve, ctlCurve, cvNum, socket_root, socketCrv_root, socketRope_root

    def build_rig(self):
        #Create Up Vector Curves
        bindCVs = self.bindCurve.getCVs(space="world")
        fn_bindCurve = curve_tool.getFnCurve(self.bindCurve)
        bind_numCVs = fn_bindCurve.numCVs - 3 #subtract 3 because it's a periodic curve and 3 of the CVs are hiddenw
        bindUpvCurve = curve_tool.createCurveFromCurve(self.bindCurve,
                                           self.setName('bindUpvCurve'),
                                           nbPoints=bind_numCVs + 3,
                                           parent=self.socketCrv_root)
        ctlUpvCurve = curve_tool.createCurveFromCurve(self.bindCurve,
                                               self.setName('ctlUpvCurve'),
                                               nbPoints=self.cvNum,
                                               parent=self.socketCrv_root)
        ctl_pos = []
        for loc in self.ctl_locs:
            pos = cmds.xform(loc, q=True, worldSpace=True, t=True)
            print(pos)
            ctl_pos.append(pos)
        bsCurve = curve_tool.createBSCurve(ctl_pos,
                                           self.setName('bsCurve'),
                                           parent=self.socketCrv_root)

        #Get the direction of the parent joint
        parentOrientation = orientation_tool.getOrientation(self.eye_joint, 'vector')
        parentZUp = parentOrientation[2]
        #Offset upv curve in the direction of the parent joint
        for upvCurve in [bindUpvCurve, ctlUpvCurve]:
            upvCvs = upvCurve.getCVs(space="world")
            fn_upvCurve = curve_tool.getFnCurve(upvCurve)
            upv_numCVs = fn_upvCurve.numCVs
            for i, cv in enumerate(upvCvs):
                offset = [cv[0] + parentZUp[0], cv[1] + parentZUp[1], cv[2] + parentZUp[2]]
                #subtract 3 because it's a periodic curve and 3 of the CVs are hidden
                if i < upv_numCVs-3:
                    upvCurve.setCV(i, offset, space='world')

        #Create Joints
        joints = []
        for i, cv in enumerate(bindCVs):
            if i < bind_numCVs:
                oTransUpV = pm.PyNode(
                    pm.createNode(
                        "transform",
                        n=self.setName("socketRopeUpv", idx=i),
                        p=self.socketRope_root,
                        ss=True))
                oTrans = pm.PyNode(
                    pm.createNode(
                        "transform",
                        n=self.setName("socketRope", idx=i),
                        p=self.socketRope_root, 
                        ss=True))

                oParam, oLength = curve.getCurveParamAtPosition(self.bindCurve, bindCVs[i])
                uLength = curve.findLenghtFromParam(self.bindCurve, oParam)
                u = oParam

                cnsUpv = curve_tool.pathCns(
                    oTransUpV, bindUpvCurve, cnsType=True, u=u, tangent=False)
                cns = curve_tool.pathCns(
                    oTrans, self.bindCurve, cnsType=True, u=u, tangent=False)

                cns.setAttr("worldUpType", 1)
                cns.setAttr("frontAxis", 0)
                cns.setAttr("upAxis", 1)

                pm.connectAttr(oTransUpV.attr("worldMatrix[0]"),
                               cns.attr("worldUpMatrix"))

                jnt = joint_tool.addJntVanilla(oTrans, noReplace=True)
                joints.append(jnt)

        # Controls lists
        controls = []
        ctlVec = []
        bsNpo = []
        ctlNpo = []
        parentCtls = []
        # controls options
        axis_list = ["sx", "sy", "sz", "ro"]
        ctlOptions = [["innerMid", "sphere", 14, .03],
                        ["innerUp", "sphere", 14, .03],
                        ["upperIn", "sphere", 14, .03],
                        ["upperMid", "sphere", 14, .03],
                        ["upperOut", "sphere", 14, .03],
                        ["outerUp", "sphere", 14, .03],
                        ["outerMid", "sphere", 14, .03],
                        ["outerLow", "sphere", 14, .03],
                        ["lowerOut", "sphere", 14, .03],
                        ["lowerMid", "sphere", 14, .03],
                        ["lowerIn", "sphere", 14, .03],
                        ["innerLow", "sphere", 14, .03]]
        if self.side == "R":
            r_ctlOptions = ctlOptions
            r_ctlOptions.reverse()
            firstCtl = r_ctlOptions.pop(-1)
            r_ctlOptions.insert(0, firstCtl)
            ctlOptions = r_ctlOptions

        params = ["tx", "ty", "tz", "rx", "ry", "rz"]

        # Create Controls
        zOffset = 0 #TODO: fix this
        if self.side == "R":
            zOffset = zOffset * -1
        iconSize = 40

        for i, pos in enumerate(ctl_pos):
            t = transform.getTransformFromPos(pos)
            t = transform.setMatrixPosition(
                transform.getTransform(pm.PyNode(self.eye_joint)), pos
            )
            temp = primitive.addTransform(
                self.socket_root, self.setName("temp"), t
            )
            temprz = temp.rz.get()
            temp.rz.set(temprz+zOffset)
            t = transform.getTransform(temp)
            pm.delete(temp)

            oName = ctlOptions[i][0]
            o_icon = ctlOptions[i][1]
            color = ctlOptions[i][2]
            wd = ctlOptions[i][3]
            
            npo = primitive.addTransform(self.socket_root,
                                         self.setName("%s_npo" % oName, self.side),
                                         t)
            ctlNpo.append(npo)
            bsCurve_npo = primitive.addTransform(npo,
                                         self.setName("bsCurve_%s_npo" % oName, self.side),
                                         t)
            bsNpo.append(bsCurve_npo)
            
            ctl = icon.create(bsCurve_npo,
                              self.setName("%s_%s" % (oName, self.ctl_suffix), self.side),
                              t,
                              icon=o_icon,
                              w=wd * iconSize,
                              d=wd * iconSize,
                              color=color)
                
            controls.append(ctl)

            upv = primitive.addTransform(ctl, self.setName("%s_upv" % oName, self.side), t)
            upv.attr("tx").set(parentZUp[0])
            upv.attr("ty").set(parentZUp[1])
            upv.attr("tz").set(parentZUp[2])
            ctlVec.append(upv)
                
            # # Parent Controls
            if i == (self.control_num/4) or i == (self.control_num/4)*3:
                if i == (self.control_num/4):
                    parentName = 'upper'
                else:
                    parentName = 'lower'
                ctl_npo = primitive.addTransform(self.socket_root,
                                 self.setName("%s_npo" % parentName, self.side),
                                 t)
                ctl = icon.create(ctl_npo,
                      self.setName("%s_%s" % (parentName, self.ctl_suffix), self.side),
                      t,
                      icon=o_icon,
                      w=wd * iconSize*3,
                      d=wd * iconSize*3,
                      color=color)
                parentCtls.append(ctl)

        # Connecting control bsNPOs with bsCurve
        bsCVs = bsCurve.getCVs(space="world")
        fn_bsCurve = curve_tool.getFnCurve(bsCurve)
        bs_numCVs = fn_bsCurve.numCVs
        for i, cv in enumerate(bindCVs):
            if i < bs_numCVs - 1:
                oParam, oLength = curve.getCurveParamAtPosition(bsCurve, bsCVs[i])
                uLength = curve.findLenghtFromParam(bsCurve, oParam)
                u = oParam

                cns = curve_tool.pathCns(
                    pm.PyNode(bsNpo[i]), bsCurve, cnsType=True, u=u, tangent=False, rot=False)

                cns.setAttr("worldUpType", 1)
                cns.setAttr("frontAxis", 0)
                cns.setAttr("upAxis", 1)
                
                transFromMat = cmds.shadingNode('translationFromMatrix', au=True)
                plusMAv = cmds.shadingNode('plusMinusAverage', au=True)
                cmds.connectAttr(f'{bsNpo[i]}.parentInverseMatrix', f'{transFromMat}.input')
                cmds.connectAttr(f'{transFromMat}.output', f'{plusMAv}.input3D[0]')
                cmds.connectAttr(f'{cns}.allCoordinates', f'{plusMAv}.input3D[1]')
                cmds.connectAttr(f'{plusMAv}.output3D', f'{bsNpo[i]}.translate', f=True)

        # Connecting control crvs with controls
        ctlCurveCvs = self.ctlCurve.getCVs(space="world")
        for i, item in enumerate(controls): #CHANGES BEGIN
            node = pm.createNode("decomposeMatrix")
            pm.connectAttr(item + ".worldMatrix[0]", node + ".inputMatrix")
            pm.connectAttr(
                node + ".outputTranslate", self.ctlCurve + ".controlPoints[%s]" % (i * 3)
            )
            pm.connectAttr(
                node + ".outputTranslate", self.ctlCurve + ".controlPoints[%s]" % (i * 3 + 1)
            )
            pm.connectAttr(
                node + ".outputTranslate", self.ctlCurve + ".controlPoints[%s]" % (i * 3 + 2)
            )
                
        # #Up socket up vectors
        for i, item in enumerate(ctlVec):
            node = pm.createNode("decomposeMatrix")
            pm.connectAttr(item + ".worldMatrix[0]", node + ".inputMatrix")
            pm.connectAttr(
                node + ".outputTranslate", ctlUpvCurve + ".controlPoints[%s]" % (i * 3)
            )
            pm.connectAttr(
                node + ".outputTranslate", ctlUpvCurve + ".controlPoints[%s]" % (i * 3 + 1)
            )
            pm.connectAttr(
                node + ".outputTranslate", ctlUpvCurve + ".controlPoints[%s]" % (i * 3 + 2)
            )

        # Connect joint curve to controls
        cmds.wire(self.bindCurve, w=self.ctlCurve, dds=[0,10])
        cmds.wire(bindUpvCurve, w=ctlUpvCurve, dds=[0,10])

        cmds.parentConstraint(self.head_joint, bsCurve, mo=True)

        for npo in ctlNpo:
            cmds.setAttr(f'{npo}.inheritsTransform', 0)

        for npo in bsNpo:
            cmds.orientConstraint(self.head_joint, npo, mo=True)
            
        for joint in joints:
            cmds.parent(joint, self.head_joint)
        cmds.parent(self.socket_root, self.parent_node)
        
        # for loc in self.ctl_locs:
        #     cmds.delete(loc)

class EyeSocketRiggerUI(MayaQWidgetDockableMixin, QtWidgets.QDialog): #TODO move to it's own script
    def __init__(self, parent=None):
        super(EyeSocketRiggerUI, self).__init__(parent)
        self.setWindowTitle("Eye Autorigger")
        self.build_ui()
        self.component = None
    
    def build_ui(self):
        self.create_controls()
        self.create_layout()
        self.create_connections()

    def create_controls(self):
        # Geometry input control
        self.geometryInput_group = QtWidgets.QGroupBox("Geometry Input")
        
        self.vertex_loop_label = QtWidgets.QLabel("Vertex Loop:")
        self.vertex_loop = QtWidgets.QLineEdit()
        self.vertex_loop_button = QtWidgets.QPushButton("<<")
        
        self.inner_vertex_label = QtWidgets.QLabel("Inner Corner Vertex:")
        self.inner_vertex = QtWidgets.QLineEdit()
        self.inner_vertex_button = QtWidgets.QPushButton("<<")

        # Name prefix input control
        self.prefix_group = QtWidgets.QGroupBox("Name Prefix")
        self.name_prefix = QtWidgets.QLineEdit()
        self.name_prefix.setText("socket")
        
        # Side infix input control
        self.side_group = QtWidgets.QGroupBox("Side")
        self.side = QtWidgets.QLineEdit()
        self.side.setText("L")

        # Control suffix input control
        self.suffix_group = QtWidgets.QGroupBox("Control Name Suffix")
        self.ctl_suffix = QtWidgets.QLineEdit()
        self.ctl_suffix.setText("anim")

        # Joint input control
        self.joints_group = QtWidgets.QGroupBox("Joint Parent")
        self.joint_parent = QtWidgets.QLineEdit()
        self.joint_parent.setText("eye_L_eye_jnt")
        self.joint_parent_button = QtWidgets.QPushButton("<<")

        # Options input controls
        self.options_group = QtWidgets.QGroupBox("Rig Parent")
        self.parent_node = QtWidgets.QLineEdit()
        self.parent_node.setText("head_M_00_jnt_customGrp")
        self.parent_button = QtWidgets.QPushButton("<<")
        self.head_joint = QtWidgets.QLineEdit()
        self.head_joint.setText("head_M_00_jnt")
        self.head_button = QtWidgets.QPushButton("<<")
        
        # Build buttons
        self.guides_button = QtWidgets.QPushButton("Build Control Guides")
        self.rig_button = QtWidgets.QPushButton("Create Controls")

    def create_layout(self):
        # Vertex Loop Layout
        vertex_loop_layout = QtWidgets.QHBoxLayout()
        vertex_loop_layout.addWidget(self.vertex_loop_label)
        vertex_loop_layout.addWidget(self.vertex_loop)
        vertex_loop_layout.addWidget(self.vertex_loop_button)
        
        # Inner Vertex Layout
        inner_vertex_layout = QtWidgets.QHBoxLayout()
        inner_vertex_layout.addWidget(self.inner_vertex_label)
        inner_vertex_layout.addWidget(self.inner_vertex)
        inner_vertex_layout.addWidget(self.inner_vertex_button)

        # Geometry Input Layout
        geometryInput_layout = QtWidgets.QVBoxLayout()
        geometryInput_layout.addLayout(vertex_loop_layout)
        geometryInput_layout.addLayout(inner_vertex_layout)
        self.geometryInput_group.setLayout(geometryInput_layout)

        #Joints Layout
        joint_parent_layout = QtWidgets.QHBoxLayout()
        joint_parent_layout.addWidget(self.joint_parent)
        joint_parent_layout.addWidget(self.joint_parent_button)
        joints_layout = QtWidgets.QVBoxLayout()
        joints_layout.addLayout(joint_parent_layout)
        self.joints_group.setLayout(joints_layout)

        # Options Layout
        parent_layout = QtWidgets.QHBoxLayout()
        parent_layout.addWidget(self.parent_node)
        parent_layout.addWidget(self.parent_button)
        head_layout = QtWidgets.QHBoxLayout()
        head_layout.addWidget(self.head_joint)
        head_layout.addWidget(self.head_button)
        options_layout = QtWidgets.QVBoxLayout()
        options_layout.addLayout(parent_layout)
        options_layout.addLayout(head_layout)
        self.options_group.setLayout(options_layout)

        # Name prefix
        name_prefix_layout = QtWidgets.QHBoxLayout()
        name_prefix_layout.addWidget(self.name_prefix)
        self.prefix_group.setLayout(name_prefix_layout)
        
        # Side
        side_layout = QtWidgets.QHBoxLayout()
        side_layout.addWidget(self.side)
        self.side_group.setLayout(side_layout)

        # Control Name Extension
        controlExtension_layout = QtWidgets.QHBoxLayout()
        controlExtension_layout.addWidget(self.ctl_suffix)
        self.suffix_group.setLayout(controlExtension_layout)

        # Main Layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.prefix_group)
        main_layout.addWidget(self.side_group)
        main_layout.addWidget(self.suffix_group)
        main_layout.addWidget(self.geometryInput_group)
        main_layout.addWidget(self.options_group)
        main_layout.addWidget(self.joints_group)
        main_layout.addWidget(self.guides_button)
        main_layout.addWidget(self.rig_button)

        self.setLayout(main_layout)

    def create_connections(self):
        self.vertex_loop_button.clicked.connect(
            partial(self.populate_edge_loop, self.vertex_loop)
        )
        self.inner_vertex_button.clicked.connect(
            partial(self.populate_element, self.inner_vertex, "vertex")
        )
        self.parent_button.clicked.connect(
            partial(self.populate_element, self.parent_node)
        )
        self.head_button.clicked.connect(
            partial(self.populate_element, self.head_joint)
        )
        self.joint_parent_button.clicked.connect(
            partial(self.populate_element, self.joint_parent, "joint")
        )
        self.guides_button.clicked.connect(self.save_component)
        self.rig_button.clicked.connect(self.rig_component)
    
    def save_component(self):
        self.component = EyeSocketComponent(
            self.vertex_loop.text(),
            self.inner_vertex.text(),
            self.name_prefix.text(),
            self.side.text(),
            self.ctl_suffix.text(),
            self.joint_parent.text(),
            self.parent_node.text(),
            self.head_joint.text()
        )
    
    def rig_component(self):
        self.component.build_rig()
        
    def populate_edge_loop(self, lineEdit):
        lineEdit.setText(get_vertex_loop_from_selection())

    def populate_element(self, lEdit, oType="transform"):
        if oType == "joint":
            oTypeInst = pm.nodetypes.Joint
        elif oType == "vertex":
            oTypeInst = pm.MeshVertex
        else:
            oTypeInst = pm.nodetypes.Transform

        oSel = pm.selected()
        if oSel:
            if isinstance(oSel[0], oTypeInst):
                lEdit.setText(oSel[0].name())
            else:
                pm.displayWarning(
                    "The selected element is not a valid %s" % oType)
        else:
            pm.displayWarning("Please select first one %s." % oType)

# ==============================================================
def main():
    autorigger = EyeSocketRiggerUI()
    autorigger.show(dockable=True)
    print("Opening Eye Autorigger")

if __name__ == "__main__":
    main()