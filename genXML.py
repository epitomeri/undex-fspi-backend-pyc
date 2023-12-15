import xml.etree.ElementTree as ET
import xml.dom.minidom
import re
import os

from jinja2 import Undefined



class PreCICEConfigGenerator:
    def __init__(self):
        self.precice_contents = []


    def extract_values(self, text, key):
        """
        Extract values for a given key in the provided text.

        :param text: The text to search in.
        :param key: The key for which to find values (e.g., 'readData', 'writeData').
        :return: A list of extracted values for the given key.
        """
        # Regular expression to find the key and extract its values
        regex = rf"{key}\s*\(([^)]+)\)"
        matches = re.findall(regex, text)

        # Strip any leading/trailing whitespace from each extracted value
        extracted_values = [match.strip() for match in matches][0]

        return extracted_values

    def extract_participant(self, text) -> str:
        # Split the text into lines
        lines = text.split('\n')

        # Iterate over each line
        for line in lines:
            # Check if the line contains the word 'participant'
            if line.strip().startswith('participant'):
                # Split the line by spaces, remove quotes and return the name
                return line.split()[1].strip().strip(';').strip('"')

        # Return None if 'participant' is not found
        return ""

    def load_precice_contents(self):
        for toor, dirs, files in os.walk("./projects"):
            for file in files:
                if file == "preciceDict":
                    file_path = os.path.join(toor, file)

                    # Read the file and extract data
                    try:
                        with open(file_path, 'r') as f:
                            file_content = f.read()

                            self.precice_contents.append(file_content)
                    except Exception as e:
                        print(f"An error occurred while processing {file_path}: {e}")

    def generate_xml(self, data, projectid):

        projects_dir = f'./projects/{projectid}' 
        if not os.path.exists(projects_dir):
            os.makedirs(projects_dir)



        self.load_precice_contents()

        start = ET.Element("precice-configuration")


        log = ET.SubElement(start, "log", enabled=str(data["log"]["fileEnabled"]))

        sink1 = ET.SubElement(log, "sink", type="stream", output="stdout", format="Hello %Message%", filter="%Severity% > trace")
        sink1.set("enabled", "true")

        sink2 = ET.SubElement(log, "sink", type="file", output=data["log"]["fileName"], filter="%Severity% > debug")
        sink2.set("enabled", "true")

        root = ET.SubElement(start, "solver-interface", dimensions="3")

        if(data["variables"]["fluidToSolid"] ==  "Stress"):
            data_vector = ET.SubElement(root, "data:vector", name="Stress")

        for content in self.precice_contents:
            write_data = self.extract_values(content, "writeData")
            stress_inner = ET.SubElement(root, "data:vector", name=write_data)

        old_read_data = ""
        for content in self.precice_contents:
            read_data = self.extract_values(content, "readData")
            if(read_data != old_read_data):
                stress_outer = ET.SubElement(root, "data:vector", name=read_data)
                old_read_data = read_data


        for content in self.precice_contents:
            name = self.extract_participant(content)
            name += "-Nodes" # type: ignore
            read_data = self.extract_values(content, "readData")
            write_data = self.extract_values(content, "writeData")
            mesh_fluid_outer_nodes = ET.SubElement(root, "mesh", name=name)
            use_data_stress_outer_fluid = ET.SubElement(mesh_fluid_outer_nodes, "use-data", name=write_data)
            use_data_displacements0_fluid = ET.SubElement(mesh_fluid_outer_nodes, "use-data", name=read_data)



        mesh_solid = ET.SubElement(root, "mesh", name="Solid")
        if(data["variables"]["fluidToSolid"] ==  "Stress"):
            data_vector = ET.SubElement(mesh_solid, "use-data", name="Stress")

        for content in self.precice_contents:
            write_data = self.extract_values(content, "writeData")
            stress_inner = ET.SubElement(mesh_solid, "use-data", name=write_data)

        old_read_data = ""
        for content in self.precice_contents:
            read_data = self.extract_values(content, "readData")
            if(read_data != old_read_data):
                stress_outer = ET.SubElement(mesh_solid, "use-data", name=read_data)
                old_read_data = read_data



        for content in self.precice_contents:
            name = self.extract_participant(content)
            write_data = self.extract_values(content, "writeData")
            read_data = self.extract_values(content, "readData")

            participant_fluid_inner = ET.SubElement(root, "participant", name=name)
            use_mesh_fluid_inner_nodes = ET.SubElement(participant_fluid_inner, "use-mesh", name=f'{name}', provide="yes")

            attributes = {
                "name": f'{name}-Nodes',
                "from": name,
            }

            use_mesh_solid_from_febio = ET.SubElement(participant_fluid_inner, "use-mesh", attrib=attributes) # type: ignore
            read_data_fluid_inner_stress = ET.SubElement(participant_fluid_inner, "read-data", name=f'{name}-Stress', mesh='Solid')
            write_data_fluid_inner_stress = ET.SubElement(participant_fluid_inner, "write-data", name='Displacements0', mesh='Solid')

            attributes = {
                "direction": "read",
                "from": "Solid",
                "to": f'{name}-Nodes',
                "constraint": "consistent"
            }

            if(data["mapping"]["algorithm"] == "Nearest Projection"):
                mapping_nearest_projection = ET.SubElement(participant_fluid_inner, "mapping:nearest-projection", attrib=attributes) # type: ignore
            elif(data["mapping"]["algorithm"] == "Nearest Neighbor"):
                mapping_nearest_neighbor = ET.SubElement(participant_fluid_inner, "mapping:nearest-neighbor", attrib=attributes) # type: ignore
            
            if(data["log"]["vtk"]):
                export_vtk = ET.SubElement(participant_fluid_inner, "export:vtk", directory=f'preCICE-{name}-output')



        participant_febio = ET.SubElement(root, "participant", name="FEBio")
        use_mesh_solid_febio = ET.SubElement(participant_febio, "use-mesh", name="Solid", provide="yes")

        old_read_data = ""
        for content in self.precice_contents:
            name = self.extract_participant(content)
            write_data = self.extract_values(content, "writeData")

            attributes = {
                "name": f'{name}-Nodes',
                "from": name,
            }
            
            use_mesh_fluid_inner_nodes_febio = ET.SubElement(participant_febio, "use-mesh", attrib=attributes) # type: ignore
            read_data_stress_inner_febio = ET.SubElement(participant_febio, "read-data", name=write_data, mesh="Solid")

      
            

            attributes = {
                "direction": "read",
                "to": "Solid",
                "from": f'{name}-Nodes',
                "constraint": "consistent"
            }

            if(data["mapping"]["algorithm"] == "Nearest Projection"):
                mapping_nearest_projection = ET.SubElement(participant_febio, "mapping:nearest-projection", attrib=attributes) # type: ignore
            elif(data["mapping"]["algorithm"] == "Nearest Neighbor"):
                mapping_nearest_neighbor = ET.SubElement(participant_febio, "mapping:nearest-neighbor", attrib=attributes) # type: ignore
            
            if(data["log"]["vtk"]):
                export_vtk = ET.SubElement(participant_febio, "export:vtk", directory=f'preCICE-{name}-output')



        for content in self.precice_contents:
            name = self.extract_participant(content)

            attributes = {
                "from": name,
                "to": "FEBio",
                "network": "ib0",
                "exchange-directory": ".."
            }

            if(data["network"]["type"] == "ib0"):
                m2n_sockets = ET.SubElement(root, "m2n:sockets", attrib=attributes) # type: ignore
            elif(data["network"]["type"] == "eth0"):
                m2n_sockets = ET.SubElement(root, "m2n:sockets", attrib=attributes) # type: ignore


        for content in self.precice_contents:
            name = self.extract_participant(content)
            write_data = self.extract_values(content, "writeData")
            read_data = self.extract_values(content, "readData")

            coupling_scheme_parallel_explicit = ET.SubElement(root, "coupling-scheme:parallel-explicit")
            time_window_size = ET.SubElement(coupling_scheme_parallel_explicit, "time-window-size", value=data["coupling"]["timeStep"], method="fixed")
            max_time = ET.SubElement(coupling_scheme_parallel_explicit, "max-time", value=data["coupling"]["maxTime"])
            participants = ET.SubElement(coupling_scheme_parallel_explicit, "participants", first=name, second="FEBio")

            attributes = {
                "data": write_data,
                "mesh": f'{name}-Nodes',
                "from": name,
                "to": "FEBio"
            }
            exchange_stress_outer = ET.SubElement(coupling_scheme_parallel_explicit, "exchange", attrib=attributes) # type: ignore




        tree = ET.ElementTree(start)

        # Write the tree to a file
        tree.write(f'./projects/{projectid}/precice-config.xml', xml_declaration=True, encoding='utf-8')

        return f'./projects/{projectid}/precice-config.xml'
    
