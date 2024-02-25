import xml.etree.ElementTree as ET
import xml.dom.minidom
import re
import os
import shutil

from jinja2 import Undefined
from utils.formatXML import format_and_overwrite_xml_file

class FebioConfigGenerator():
    def __init__(self) -> None:
        pass

    def generate_xml(self, data, projectid, meshPath, boundaryPath):


        febio_spec = ET.Element("febio_spec", version="3.0")

        if(data['moduleType']['type'] == "implicit"):
            module = ET.SubElement(febio_spec, "Module", type="solid")
        else:
            module = ET.SubElement(febio_spec, "Module", type="explicit-solid")

        materials = ET.SubElement(febio_spec, "Material")
        
        for i, material in enumerate(data['material']['materials']):
            material1 = ET.SubElement(materials, "material", id=f'{i + 1}', name=material['name'], type=material['type'])
            density1 = ET.SubElement(material1, "density")
            density1.text = material['density']
            E1 = ET.SubElement(material1, "E")
            E1.text = material['young']
            v1 = ET.SubElement(material1, "v")
            v1.text = material['poisson']


        

        if(data['dataMapped']['type'] == "pressure"):
                surface_data = ET.SubElement(febio_spec, "SurfaceData", name="Pressure", generator="const", datatype="scalar", surface="Solid")

                surface_value = ET.SubElement(surface_data, "value")
                surface_value.text = "0.0"

        boundary = ET.SubElement(febio_spec, "Boundary")
        node_set_name = next((line.split('name="')[1].split('"')[0] for line in open(boundaryPath) if '<NodeSet name="' in line), None)
        bc1 = ET.SubElement(boundary, "bc",name=node_set_name, type = "fix", node_set=node_set_name) # type: ignore
        dofs1 = ET.SubElement(bc1, "dofs")
        dofs1.text = "x,y,z"

        bc2 = ET.SubElement(boundary, "bc", name=node_set_name, type = "fix", node_set=node_set_name) # type: ignore
        dofs2 = ET.SubElement(bc2, "dofs")
        dofs2.text = "sx,sy,sz"



        load_data = ET.SubElement(febio_spec, "LoadData")
        
        for i, load in enumerate(data['loadController']['loadControllers']):
            load_controller = ET.SubElement(load_data, "load_controller", id=str(i + 1), type=load['type'].lower())
            interpolate = ET.SubElement(load_controller, "interpolate")
            interpolate.text = load['interpolation'].upper()

            points = ET.SubElement(load_controller, "points")
            firstPoint = ET.SubElement(points, "point")
            firstPoint.text = load['firstPoint']

            secondPoint = ET.SubElement(points, "point")
            secondPoint.text = load['secondPoint']
        


        output = ET.SubElement(febio_spec, "Output")

        if(data['step']['steps'][0]['loads'][0]['loadType'] == "pressure"):
            plotfile = ET.SubElement(output, "plotfile", type="febio")
            var1 = ET.SubElement(plotfile, "var", type="displacement")
            var2 = ET.SubElement(plotfile, "var", type="shell strain")
            var3 = ET.SubElement(plotfile, "var", type="shell thickness")
            var4 = ET.SubElement(plotfile, "var", type="stress")
            var5 = ET.SubElement(plotfile, "var", type="parameter['fem.surface_load[0].pressure']=Pressure")


        steps = ET.SubElement(febio_spec, "Step")

        for i, step in enumerate(data['step']['steps']):
            step_block = ET.SubElement(steps, "step", id=f'{i + 1}', name = step["name"])

            control = ET.SubElement(step_block, "Control")
            analysis = ET.SubElement(control, "analysis")
            analysis.text = step['analysisType'].upper()

            time_steps = ET.SubElement(control, "time_steps")
            time_steps.text = str(step['timeSteps'])

            step_size = ET.SubElement(control, "step_size")
            step_size.text = step['stepSize']

            if(step['analysisType'] == "dynamic"):
                solver = ET.SubElement(control, "solver")
                
                mass_lumping = ET.SubElement(solver, "mass_lumping")
                mass_lumping.text = step['massLumping']

                dyn_dumping = ET.SubElement(solver, "dyn_dumping")
                dyn_dumping.text = step['dynamicLumping']

            plot_stride = ET.SubElement(control, "plot_stride")
            plot_stride.text = str(step['plotStride'])

            loads = ET.SubElement(step_block, "Loads")

            for j, load in enumerate(step['loads']):
                if(load['loadType'] == "pressure"):
                    surface_load = ET.SubElement(loads, "surface_load", name=load[
                        'pressureLabel'], type=load['loadType'].lower(), surface="Solid")

                    if(load['pressureValType'] == "numeric"):
                        pressure = ET.SubElement(surface_load, "pressure", lc=f'{i + 1}')
                        pressure.text = load['pressure']
                    elif(load['pressureValType'] == "expression"):
                        pressure = ET.SubElement(surface_load, "pressure", lc=f'{i + 1}', type="math")
                        pressure.text = load['pressure']
                    elif(load['pressureValType'] == "map"):
                        pressure = ET.SubElement(surface_load, "pressure", type="map")
                        pressure.text = "Pressure"


                    linear = ET.SubElement(surface_load, "linear")
                    linear.text = load['linearParam']
                    symmetric_stiffness = ET.SubElement(surface_load, "symmetric_stiffness")
                    symmetric_stiffness.text = load['matrix']
                    shell_bottom = ET.SubElement(surface_load, "shell_bottom")
                    shell_bottom.text = load['pressureTop']




            




        #Writing to tree

        tree = ET.ElementTree(febio_spec)

        tree.write(f'./projects/{projectid}/febio-config.xml', xml_declaration=True, encoding='utf-8')
        
        format_and_overwrite_xml_file(f'./projects/{projectid}/febio-config.xml')


        

        #Inserting boundary into mesh
        source_file_path = boundaryPath 
        target_file_path = meshPath 
        temp_file_path = target_file_path + '.tmp'  

        insert_tag = '<Surface name="'

        with open(source_file_path, 'r') as source_file:
            source_content = source_file.readlines()

        with open(temp_file_path, 'w') as temp_file, open(target_file_path, 'r') as target_file:
            inserted = False
            for line in target_file:
                if not inserted and insert_tag in line:
                    temp_file.writelines(source_content)  
                    inserted = True
                temp_file.write(line) 
        shutil.move(temp_file_path, target_file_path)


        #Inserting boundary data into febio-config.xml
        source_file_path = meshPath
        target_file_path = f'./projects/{projectid}/febio-config.xml'
        temp_file_path = target_file_path + '.tmp'

        insert_tag = '<SurfaceData name="'

        # Read the source file content, excluding the </MeshData> tag
        with open(source_file_path, 'r') as source_file:
            source_content = [line for line in source_file if '</MeshData>' not in line]
        mesh_data_end_tag = '</MeshData>\n'  # Prepare the </MeshData> tag to be inserted later

        # Process the target file and insert the source content and the </MeshData> tag appropriately
        with open(temp_file_path, 'w') as temp_file, open(target_file_path, 'r') as target_file:
            inserted = False
            surface_data_closed = False
            for line in target_file:
                # Insert the source content before the insert_tag
                if not inserted and insert_tag in line:
                    temp_file.writelines(source_content)
                    inserted = True
                # Check if the current line is the closing </SurfaceData> tag
                if '</SurfaceData>' in line:
                    surface_data_closed = True
                temp_file.write(line)
                # If we've inserted the source content and just wrote the closing </SurfaceData> tag,
                # it's time to insert the </MeshData> tag
                if inserted and surface_data_closed:
                    temp_file.write(mesh_data_end_tag)
                    # Reset the flag if you expect multiple </SurfaceData> sections
                    surface_data_closed = False
                    inserted = False  # Reset inserted if needed to handle multiple insertions

        # Replace the original file with the modified content
        shutil.move(temp_file_path, target_file_path)




        
        return f'./projects/{projectid}/Solid/febio-config.xml'
            


