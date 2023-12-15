from cmath import phase
from email.errors import UndecodableBytesDefect
import os

from blastFOAMGen.constant import ConstantGenerator
from blastFOAMGen.zero import ZeroGenerator
from blastFOAMGen.system import SystemGenerator

class BlastFoamGenerator:
    def __init__(self, data, projectid):
        self.projectid = projectid
        self.data = data

    def generate_constant(self):
        constant_generator = ConstantGenerator()

        projects_dir = f'./projects/{self.projectid}/{self.data["participantName"]}' 
        constant_dir = os.path.join(projects_dir, "constant")

        if not os.path.exists(constant_dir):
            os.makedirs(constant_dir)


        patchName = ""
        if(len(self.data["mesh"]["geometries"]) > 0):
            patchName = self.data["mesh"]["geometries"][0]["patchName"]
        else: 
            patchName = "none"
        dynamic_mesh_content = constant_generator.generate_dynamic_mesh_dict(self.data["mesh"]["geometries"], patchName)
        dynamic_mesh_file_path = os.path.join(constant_dir, "dynamicMeshDict")
        with open(dynamic_mesh_file_path, 'w') as file:
            file.write(dynamic_mesh_content)
            print(f"File created: {dynamic_mesh_file_path}")

        g_content = constant_generator.generate_g()
        g_file_path = os.path.join(constant_dir, "g")
        with open(g_file_path, 'w') as file:
            file.write(g_content)
            print(f"File created: {g_file_path}")

        momentum_transport_content = constant_generator.generate_momentum_transport()
        momentum_transport_file_path = os.path.join(constant_dir, "momentumTransport")
        with open(momentum_transport_file_path, 'w') as file:
            file.write(momentum_transport_content)
            print(f"File created: {momentum_transport_file_path}")

        phase_properties = self.data["phaseProperties"]
        phase_properties_content = constant_generator.generate_phase_properties(phase_properties["explosive"], phase_properties["water"], phase_properties["air"], phase_properties["ambient"])
        phase_properties_file_path = os.path.join(constant_dir, "phaseProperties")
        with open(phase_properties_file_path, 'w') as file:
            file.write(phase_properties_content)
            print(f"File created: {phase_properties_file_path}")


    def generate_zero(self):
        zero_generator = ZeroGenerator()
        projects_dir = f'./projects/{self.projectid}/{self.data["participantName"]}' 
        zero_dir = os.path.join(projects_dir, "0")

        if not os.path.exists(zero_dir):
            os.makedirs(zero_dir)

        explosive_active = self.data["phaseProperties"]["explosive"]["active"]

        u_file_content = zero_generator.generate_u(self.data["mesh"]["geometries"][0]["patchName"], explosive_active)
        u_file_path = os.path.join(zero_dir, "U.orig")
        with open(u_file_path, 'w') as file:
            file.write(u_file_content)
            print(f"File created: {u_file_path}")

        p_file_content = zero_generator.generate_p(self.data["phaseProperties"]["ambient"], self.data["mesh"]["geometries"][0]["patchName"], explosive_active)
        p_file_path = os.path.join(zero_dir, "p.orig")
        with open(p_file_path, 'w') as file:
            file.write(p_file_content)
            print(f"File created: {p_file_path}")

        t_file_content = zero_generator.generate_t(explosive_active)
        t_file_path = os.path.join(zero_dir, "T.orig")
        with open(t_file_path, 'w') as file:
            file.write(t_file_content)
            print(f"File created: {t_file_path}")

        point_displacement_content = zero_generator.generate_point(self.data["mesh"]["geometries"][0]["patchName"], explosive_active)
        point_displacement_file_path = os.path.join(zero_dir, "pointDisplacement.orig")
        with open(point_displacement_file_path, 'w') as file:
            file.write(point_displacement_content)
            print(f"File created: {point_displacement_file_path}")


        files = zero_generator.get_filenames(self.data["phaseProperties"])
        for file in files:
            phase = file[0]
            file = file[1]
            split = file.split(".")
            fileType = split[0]
            phase_name = split[1]


            if(fileType == "rho"):
                rho0 = 1.225
                if("coefficients" in self.data["phaseProperties"][phase].keys()):

                    rho0 = self.data["phaseProperties"][phase]["coefficients"]["rho0"] 
            
                file_content = zero_generator.generate_rho(phase_name, self.data["mesh"]["geometries"], explosive_active, rho0)
                file_path = os.path.join(zero_dir, file)
                with open(file_path, 'w') as file:
                    file.write(file_content)
                    print(f"File created: {file_path}")
            
            elif(fileType == "alpha"):
                file_content = zero_generator.generate_alpha(fileType, phase_name, self.data["mesh"]["geometries"])
                file_path = os.path.join(zero_dir, file)
                with open(file_path, 'w') as file:
                    file.write(file_content)
                    print(f"File created: {file_path}")
            
                
    def generate_system(self):
        system_generator = SystemGenerator()
        projects_dir = f'./projects/{self.projectid}/{self.data["participantName"]}' 
        system_dir = os.path.join(projects_dir, "system")

        if not os.path.exists(system_dir):
            os.makedirs(system_dir)

        block_mesh_content = system_generator.generate_block_mesh()
        block_mesh_file_path = os.path.join(system_dir, "blockMeshDict")
        with open(block_mesh_file_path, 'w') as file:
            file.write(block_mesh_content)
            print(f"File created: {block_mesh_file_path}")

        control_dict_content = system_generator.generate_control_dict(self.data["systemSettings"]["endTime"], self.data["systemSettings"]["adjustTimestep"], self.data["systemSettings"]["writeInterval"], self.data["systemSettings"]["adjustTimestep"], self.data["systemSettings"]["maxCourantNumber"], self.data["outputControls"]["probe"], self.data["mesh"]["geometries"][0]["patchName"])
        control_dict_file_path = os.path.join(system_dir, "controlDict")
        with open(control_dict_file_path, 'w') as file:
            file.write(control_dict_content)
            print(f"File created: {control_dict_file_path}")
        
        decompose_content = system_generator.generate_decompose(self.data["systemSettings"]["numberOfProcessors"])
        decompose_file_path = os.path.join(system_dir, "decomposeParDict")
        with open(decompose_file_path, 'w') as file:
            file.write(decompose_content)
            print(f"File created: {decompose_file_path}")

        fv_scheme_content = system_generator.generate_fv_schemes(self.data["phaseProperties"]["explosive"])
        fv_scheme_file_path = os.path.join(system_dir, "fvSchemes")
        with open(fv_scheme_file_path, 'w') as file:
            file.write(fv_scheme_content)
            print(f"File created: {fv_scheme_file_path}")

        fv_solution_content = system_generator.generate_fv_solution()
        fv_solution_file_path = os.path.join(system_dir, "fvSolution")
        with open(fv_solution_file_path, 'w') as file:
            file.write(fv_solution_content)
            print(f"File created: {fv_solution_file_path}")

        precice_dict_content = system_generator.generate_precice_dict(self.data["participantName"], self.data["mesh"]["geometries"], self.data["mesh"]["geometries"][0]["patchName"])
        precice_dict_file_path = os.path.join(system_dir, "preciceDict")
        with open(precice_dict_file_path, 'w') as file:
            file.write(precice_dict_content)
            print(f"File created: {precice_dict_file_path}")
        
        setfields_content = system_generator.generate_setfields(self.data["phaseProperties"]["air"], self.data["phaseProperties"]["water"], self.data["phaseProperties"]["explosive"])
        setfields_file_path = os.path.join(system_dir, "setFieldsDict")
        with open(setfields_file_path, 'w') as file:
            file.write(setfields_content)
            print(f"File created: {setfields_file_path}")

        snappy_hex_content = system_generator.generate_snappy_hex(self.data["mesh"]["snapping"], self.data["mesh"]["geometries"], self.data["mesh"]["pointInsideMesh"], self.data["mesh"]["geometries"][0]["patchName"])
        snappy_hex_file_path = os.path.join(system_dir, "snappyHexMeshDict")
        with open(snappy_hex_file_path, 'w') as file:
            file.write(snappy_hex_content)
            print(f"File created: {snappy_hex_file_path}")

        surface_feautures_content = system_generator.generate_surface_features(self.data["mesh"]["geometries"])
        surface_feautures_file_path = os.path.join(system_dir, "surfaceFeaturesDict")
        with open(surface_feautures_file_path, 'w') as file:
            file.write(surface_feautures_content)
            print(f"File created: {surface_feautures_file_path}")


    def generate_clean(self):
        projects_dir = f'./projects/{self.projectid}/{self.data["participantName"]}' 
        system_dir = os.path.join(projects_dir)

        if not os.path.exists(system_dir):
            os.makedirs(system_dir)

        clean_content = """#!/bin/sh
cd ${0%/*} || exit 1    # run from this directory

# Source tutorial clean functions
. $WM_PROJECT_DIR/bin/tools/CleanFunctions

cleanCase
        """
        clean_file_path = os.path.join(system_dir, "Allclean")
        with open(clean_file_path, 'w') as file:
            file.write(clean_content)
            print(f"File created: {clean_file_path}")

        
    def generate_all(self): 
        projects_dir = f'./projects/{self.projectid}' 
        participant_dir = os.path.join(projects_dir, self.data["participantName"])

        if not os.path.exists(participant_dir):
            os.makedirs(participant_dir)


        self.generate_constant()
        self.generate_zero()
        self.generate_system()
        self.generate_clean()

        return participant_dir