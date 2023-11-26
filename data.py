oldData = {

    "Log": {
        "enabled": True,
        "output": "debug.log",
    },
    "Variables Tranferred": {
            "fluidToSolid": "Stress"
    },
    "Mapping": {
        "algorithm": "Nearest Projection",
        "constraint": "Conservative",
        "vtk": True
    },
    "Network": {
        "type": "Infiniband"
    },
    "Coupling Scheme": {
        "timeWindowSize": "1e-5",
        "maxTimeValue": "8e-5"
    }

}

data = {'name': 'New Case', 'participantName': 'New_Case', 'log': {'fileEnabled': True, 'fileName': 'test.log', 'vtk': False}, 'variables': {'fluidToSolid': 'Stress', 'solidToFluid': 'Displacement', 'fluidToSolidOptions': [{'value': 'Stress', 'disabled': True, 'label': 'Stress'}, {'value': 'Force', 'disabled': True, 'label': 'Force'}]}, 'mapping': {'algorithm': 'Nearest Projection', 'constraint': 'Consistent'}, 'network': {'type': 'ib0'}, 'coupling': {'scheme': 'Parallel Explicit', 'timeStep': '1e-5', 'maxTime': '5e-2'}}