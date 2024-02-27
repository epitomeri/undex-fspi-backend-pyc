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

    def load_precice_contents(self, directory):
        for toor, dirs, files in os.walk(directory):
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



        self.load_precice_contents(projects_dir)

        print(self.precice_contents)

        start = ET.Element("precice-configuration")


        log = ET.SubElement(start, "log", enabled=str(data["log"]["fileEnabled"]))

        sink1 = ET.SubElement(log, "sink", type="stream", output="stdout", format="Hello %Message%", filter="%Severity% > trace")
        sink1.set("enabled", "true")

        sink2 = ET.SubElement(log, "sink", type="file", output=data["log"]["fileName"], filter="%Severity% > debug")
        sink2.set("enabled", "true")

        root = ET.SubElement(start, "solver-interface", dimensions="3")

        dataType = ""
        if (data["variables"]["fluidToSolid"] == "Stress"):
            dataType = "data:vector"
        elif (data["variables"]["fluidToSolid"] == "Pressure"):
            dataType = "data:scalar"

        fluid_solid_type = ""
        if (data["variables"]["fluidToSolid"] == "Stress"):
            fluid_solid_type = "Stress"
        elif (data["variables"]["fluidToSolid"] == "Pressure"):
            fluid_solid_type = "Pressure"


        data_vector = ET.SubElement(root, dataType, name=data["variables"]["fluidToSolid"])



        for content in self.precice_contents:
            write_data = self.extract_values(content, "writeData")
            stress_inner = ET.SubElement(root, dataType, name=write_data)

        old_read_data = ""
        for content in self.precice_contents:
            read_data = self.extract_values(content, "readData")
            if(read_data != old_read_data):
                stress_outer = ET.SubElement(root, dataType, name=read_data)
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
        mesh_fluid_solid = ET.SubElement(mesh_solid, "use-data", name=data["variables"]["fluidToSolid"])
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
            use_mesh_fluid_inner_nodes = ET.SubElement(participant_fluid_inner, "use-mesh", name=f'{name}-Nodes', provide="yes")

            attributes = {
                "name": 'Solid',
                "from": "FEBio",
            }

            use_mesh_solid_from_febio = ET.SubElement(participant_fluid_inner, "use-mesh", attrib=attributes) # type: ignore

            write_data_fluid_inner_stress = ET.SubElement(participant_fluid_inner, "write-data", name=write_data, mesh=f'{name}-Nodes')
            write_data_fluid_inner_stress = ET.SubElement(participant_fluid_inner, "read-data", name='Displacements0', mesh=f'{name}-Nodes')

            attributes = {
                "direction": "read",
                "from": "Solid",
                "to": f'{name}-Nodes',
                "constraint": "consistent"
            }


            mapping = ET.SubElement(participant_fluid_inner, f'mapping:{data["mapping"]["algorithm"]}', attrib=attributes) # type: ignore


            
            if(data["log"]["vtk"]):
                export_vtk = ET.SubElement(participant_fluid_inner, "export:vtk", directory=f'preCICE-{name}-output')



        participant_febio = ET.SubElement(root, "participant", name="FEBio")
        use_mesh_solid_febio = ET.SubElement(participant_febio, "use-mesh", name="Solid", provide="yes")

        for content in self.precice_contents:
            name = self.extract_participant(content)
            write_data = self.extract_values(content, "writeData")

            attributes = {
                "name": f'{name}-Nodes',
                "from": name,
            }
            
            use_mesh_fluid_inner_nodes_febio = ET.SubElement(participant_febio, "use-mesh", attrib=attributes) # type: ignore
        
        for content in self.precice_contents:
            name = self.extract_participant(content)
            write_data = self.extract_values(content, "writeData")

            attributes = {
                "name": write_data,
                "mesh": 'Solid'
            }
            
            use_mesh_fluid_inner_nodes_febio = ET.SubElement(participant_febio, "read-data", attrib=attributes) # type: ignore
        

        attributes = {
            "name": 'Displacements0',
            "mesh": 'Solid',
        }
        use_mesh_fluid_inner_nodes_febio = ET.SubElement(participant_febio, "write-data", attrib=attributes) # type: ignore


        action_summation = ET.SubElement(participant_febio, "action:summation", timing="read-mapping-post", mesh="Solid")
            
        for content in self.precice_contents:
            name = self.extract_participant(content)
            write_data = self.extract_values(content, "writeData")
        
            source_data1 = ET.SubElement(action_summation, "source-data", name=write_data)
        
        target_data = ET.SubElement(action_summation, "target-data", name=data["variables"]["fluidToSolid"])

        
        read_data_name = ET.SubElement(participant_febio, "read-data", name=data["variables"]["fluidToSolid"], mesh="Solid") # type: ignore

        for content in self.precice_contents:
            name = self.extract_participant(content)

            attributes = {
                "direction": "read",
                "to": "Solid",
                "from": f'{name}-Nodes',
                "constraint": "consistent"
            }

            mapping = ET.SubElement(participant_febio, f'mapping:{data["mapping"]["algorithm"]}', attrib=attributes) # type: ignore


        old_read_data = ""
        for content in self.precice_contents:
            name = self.extract_participant(content)
            write_data = self.extract_values(content, "writeData")

            

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
            export_vtk = ET.SubElement(participant_febio, "export:vtk", directory=f'preCICE-FEBio-output')



        for content in self.precice_contents:
            name = self.extract_participant(content)

            attributes = {
                "from": name,
                "to": "FEBio",
                "network": str(data["network"]["type"]),
                "exchange-directory": ".."
            }

            if(data["network"]["type"] == "default"): del attributes["network"]
            m2n_sockets = ET.SubElement(root, "m2n:sockets", attrib=attributes) # type: ignore


        for content in self.precice_contents:
            name = self.extract_participant(content)
            write_data = self.extract_values(content, "writeData")
            read_data = self.extract_values(content, "readData")

            coupling_scheme_parallel_explicit = ET.SubElement(root, f'coupling-scheme:{data["coupling"]["scheme"]}')

            if (data["coupling"]["scheme"] == "parallel-explicit"):
                time_window_size = ET.SubElement(coupling_scheme_parallel_explicit, "time-window-size", value=data["coupling"]["timeStep"], method="fixed")
                
            elif (data["coupling"]["scheme"] == "serial-explicit"):
                time_window_size = ET.SubElement(coupling_scheme_parallel_explicit, "time-window-size", value="-1", method="first-participant")

            max_time = ET.SubElement(coupling_scheme_parallel_explicit, "max-time", value=data["coupling"]["maxTime"])
            participants = ET.SubElement(coupling_scheme_parallel_explicit, "participants", first="FEBio", second=name)


            attributes = {
                "data": write_data,
                "mesh": f'{name}-Nodes',
                "from": name,
                "to": "FEBio"
            }
            exchange_stress_outer = ET.SubElement(coupling_scheme_parallel_explicit, "exchange", attrib=attributes) # type: ignore

            attributes = {
                "data": "Displacements0",
                "mesh": "Solid",
                "from": "FEBio",
                "to": name
            }

            exchange_stress_outer = ET.SubElement(coupling_scheme_parallel_explicit, "exchange", attrib=attributes) # type: ignore




        tree = ET.ElementTree(start)

        # Write the tree to a file
        tree.write(f'./projects/{projectid}/precice-config.xml', xml_declaration=True, encoding='utf-8')

        return f'./projects/{projectid}/precice-config.xml'
    
