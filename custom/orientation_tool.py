import pymel.core as pm

def getOrientation(obj, returnType='point'):
    '''
    Get an objects orientation.

    args:
        obj (str)(obj) = The object to get the orientation of.
        returnType (str) = The desired returned value type. (valid: 'point', 'vector')(default: 'point')

    returns:
        (tuple)
    '''
    obj = pm.ls(obj)[0]

    world_matrix = pm.xform(obj, q=True, m=True, ws=True)
    rAxis = pm.getAttr(obj.rotateAxis)
    if any((rAxis[0], rAxis[1], rAxis[2])):
        print('# Warning: {} has a modified .rotateAxis of {} which is included in the result. #'.format(obj, rAxis))

    if returnType is 'vector':
        from maya.api.OpenMaya import MVector

        result = (
            MVector(world_matrix[0:3]),
            MVector(world_matrix[4:7]),
            MVector(world_matrix[8:11])
        )

    else:
        result = (
            world_matrix[0:3],
            world_matrix[4:7],
            world_matrix[8:11]
        )


    return result