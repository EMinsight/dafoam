#!/usr/bin/env python
"""
Run Python tests for optimization integration
"""

from mpi4py import MPI
import os
import numpy as np
from testFuncs import *

import openmdao.api as om
from mphys.multipoint import Multipoint
from dafoam.mphys.mphys_dafoam import DAFoamBuilder, DAFoamFaceCoords, DAFoamThermal

gcomm = MPI.COMM_WORLD

os.chdir("./input/CurvedCubeHexMesh")

if gcomm.rank == 0:
    os.system("rm -rf 0 processor*")
    os.system("cp -r 0.compressible 0")
    os.system("cp -r constant/turbulenceProperties.sa constant/turbulenceProperties")

# aero setup
U0 = 50.0
p0 = 101325.0
nuTilda0 = 4.5e-5
T0 = 300.0
rho0 = p0 / T0 / 287.0
A0 = 1.0

daOptions = {
    "designSurfaces": ["wallsbump"],
    "solverName": "DARhoSimpleFoam",
    "primalMinResTol": 1.0e-10,
    "objFunc": {
        "CD": {
            "part1": {
                "type": "force",
                "source": "patchToFace",
                "patches": ["wallsbump"],
                "directionMode": "fixedDirection",
                "direction": [1.0, 0.0, 0.0],
                "scale": 1.0 / (0.5 * U0 * U0 * A0),
                "addToAdjoint": True,
            }
        },
    },
    "couplingInfo": {
        "aerothermal": {
            "active": True,
            "couplingSurfaceGroups": {
                "wallGroup": ["wallsbump"],
            },
        }
    },
}

meshOptions = {
    "gridFile": os.getcwd(),
    "fileType": "OpenFOAM",
    # point and normal for the symmetry plane
    "symmetryPlanes": [],
}


class Top(Multipoint):
    def setup(self):
        dafoam_builder = DAFoamBuilder(daOptions, meshOptions, scenario="aerodynamic")
        dafoam_builder.initialize(self.comm)

        # ivc to keep the top level DVs
        self.add_subsystem("dvs", om.IndepVarComp(), promotes=["*"])

        self.solver = dafoam_builder.get_solver()

        # self.add_subsystem(
        #     "surf_coords", DAFoamFaceCoords(solver=self.solver, groupName=self.solver.couplingSurfacesGroup), promotes=["*"]
        # )

        self.add_subsystem(
            "thermal", DAFoamThermal(solver=self.solver, var_name="heatFlux"), promotes=["*"]
        )
    
    def configure(self):

        vol_Coords = self.solver.vec2Array(self.solver.xvVec)
        states = self.solver.vec2Array(self.solver.wVec)

        self.dvs.add_output("aero_vol_coords", val=vol_Coords)
        self.dvs.add_output("aero_states", val=states)


prob = om.Problem(reports=None)
prob.model = Top()
prob.setup(mode="rev")
om.n2(prob, show_browser=False, outfile="mphys.html")

prob.run_model()
prob.check_partials()
