### Export Rig ###
import os
from maya import cmds, mel
from path_lib.path_utils import get_publish_dir

def export_rig():
    # Rename and save the scene
    # Otherwise errors might break the source file
    scenePath= cmds.file(q=True, sn=True)
    sceneName = scenePath[0:-3]
    cmds.file(rn=f'{sceneName}_export')
    cmds.file(s=True)

    # Import references
    all_ref_paths = cmds.file(q=True, reference=True) or []
    for ref_path in all_ref_paths:
        if cmds.referenceQuery(ref_path, isLoaded=True):
            cmds.file(ref_path, importReference=True)

    # Delete namespaces
    namespaces = []
    namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
    for ns in reversed([ns for ns in namespaces if ns not in ['UI', 'shared']]):
        try:
            cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
        except RuntimeError:
            print(f"Could not remove namespace: {ns}")

    # Unparent Bones and Geo
    cmds.parent('god_M_root_jnt', world=True)
    cmds.select(clear=True)
    cmds.select('god_M_root_jnt', hi=True)
    shapeList = cmds.ls(typ='mesh')
    transformList = cmds.listRelatives(shapeList, parent=True, fullPath=True)
    cmds.select(transformList)
    cmds.parent(w=True)

    # Bake animation and disconnect from rig
    min_time = cmds.playbackOptions(q=True, min=True)
    max_time = cmds.playbackOptions(q=True, max=True)
    cmds.bakeResults(simulation=True, t=(min_time, max_time),
                     disableImplicitControl=True,
                     preserveOutsideKeys=True)
    cmds.delete(cmds.ls(type='constraint'))

    # Save the scene again for easy re-export
    cmds.file(s=True)

    # Select Export Selection
    transformList = cmds.listRelatives(shapeList, parent=True, fullPath=True)
    cmds.select(transformList)
    cmds.select('god_M_root_jnt', hi=True, add=True)

    # Set FBX export options
    mel.eval("FBXResetExport")
    mel.eval("FBXExportSmoothingGroups -v true")
    mel.eval("FBXExportSmoothMesh -v true")
    mel.eval("FBXExportSkins -v true")
    mel.eval("FBXExportShapes -v true")
    mel.eval("FBXExportInputConnections -v false")
    mel.eval("FBXExportConstraints -v false")
    mel.eval("FBXExportBakeComplexAnimation -v true")
    mel.eval(f"FBXExportBakeComplexStart -v {cmds.playbackOptions(q=True, min=True)}")
    mel.eval(f"FBXExportBakeComplexEnd -v {cmds.playbackOptions(q=True, max=True)}")
    mel.eval("FBXExportBakeResampleAnimation -v true")

    layer_scene_name = os.path.basename(scenePath).split(".")[0]
    publish_dir = get_publish_dir(scenePath)
    fbx_dir = os.path.join(publish_dir, "fbx_export")
    if not os.path.exists(fbx_dir):
        os.makedirs(fbx_dir)
    export_path = os.path.join(fbx_dir, f"{layer_scene_name}.fbx").replace("\\", "/")
    
    sel = cmds.ls(selection=True)
    if not sel:
        raise RuntimeError("Nothing is selected for FBX export.")

    # Perform the export
    mel.eval(f'FBXExport -f "{export_path}" -s')
    
if __name__ == '__main__':
    if not cmds.pluginInfo('fbxmaya', query=True, loaded=True):
        try:
            cmds.loadPlugin('fbxmaya')
        except Exception as e:
            raise RuntimeError(f"Failed to load FBX plugin: {e}")
    export_rig()