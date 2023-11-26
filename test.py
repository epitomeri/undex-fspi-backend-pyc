from blastFOAMGen import zero
from blastFOAMGen.zero import ZeroGenerator

data = {
  "name": "New Case",
  "participantName": "New_Case",
  "mesh": {
    "units": "SI",
    "scale": 2,
    "snapping": True,
    "edgeLength": "1e-3",
    "pointInsideMesh": {
      "x": 0,
      "y": 0,
      "z": 0
    },
    "geometries": [
      {
        "patchName": "",
        "refinementLevel": 1,
        "min": {
          "x": -1,
          "y": -1,
          "z": -1
        },
        "max": {
          "x": 1,
          "y": 1,
          "z": 1
        },
        "radius": 1,
        "height": 2,
        "position": {
          "x": 0,
          "y": 0,
          "z": 0
        },
        "scale": 1,
        "coupled": False,
        "geoType": "box",
        "name": "Helio"
      }
    ]
  },
  "phaseProperties": {
    "explosive": {
      "active": True,
      "phaseName": "Explosive",
      "equationOfState": "JWL",
      "type": "tnt",
      "chargeMass": 0,
      "position": {
        "x": 0,
        "y": 0,
        "z": 0
      },
      "coefficients": {
        "rho0": 1601,
        "A": "371.21e9",
        "B": "3.23e9",
        "R1": 4.15,
        "R2": 0.95,
        "Omega": 0.3,
        "detonationEnergy": "9e9",
        "detonationVelocity": "7183"
      }
    },
    "air": {
      "active": True,
      "phaseName": "Air",
      "air": "idealGas",
      "gamma": 1.4,
      "Cv": 718
    },
    "water": {
      "active": True,
      "phaseName": "Water",
      "water": "tilloston",
      "coefficients": {
        "p0": "1e5",
        "rho0": 1000,
        "e0": "3.542e5",
        "Omega": 0.28,
        "A": "2.2e9",
        "B": "9.94e9",
        "C": "14.57e9",
        "pCav": 5000
      }
    },
    "ambient": {
      "pressure": 101325,
      "temperature": 293.15,
      "waterLine": 0
    }
  },
  "outputControls": {
    "probe": {
      "selected": False,
      "fields": {
        "p": False,
        "u": False,
        "rho": False,
        "impulse": False
      },
      "locations": []
    },
    "impulse": {
      "selected": False
    },
    "fieldsMax": {
      "selected": False,
      "fields": {
        "p": False,
        "u": False,
        "rho": False,
        "impulse": False
      }
    }
  },
  "systemSettings": {
    "numberOfProcessors": 1,
    "endTime": 30,
    "writeInterval": 0.1,
    "adjustTimestep": False,
    "timestepSize": 1e-7,
    "maxCourantNumber": 0.5
  }
}

zero_generator = ZeroGenerator()
print(zero_generator.get_filenames(data["phaseProperties"]))