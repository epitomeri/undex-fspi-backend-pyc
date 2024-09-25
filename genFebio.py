import xml.etree.ElementTree as ET
import xml.dom.minidom
import re
import os

class FebioConfigGenerator():
    def __init__(self) -> None:
        pass

    def generate_xml(self, data, userid, projectid, meshPath, boundaryPath):

        def safe_attrib(value):
            """Ensures that the attribute value is a string and not None."""
            return str(value) if value is not None else ""

        def find_surface_names(mesh_content):
            """Find all surface names in mesh content."""
            return re.findall(r'<Surface\s+name="([^"]+)"', mesh_content)

        febio_spec = ET.Element("febio_spec", version="4.0")

        module = ET.SubElement(febio_spec, "Module", type=safe_attrib("solid"))

        materials = ET.SubElement(febio_spec, "Material")

        for i, material in enumerate(data['material']['materials']):
            material1 = ET.SubElement(materials, "material", id=safe_attrib(i + 1), name=safe_attrib(material['name']), type=safe_attrib(material['type']))
            density1 = ET.SubElement(material1, "density")
            density1.text = safe_attrib(material['density'])
            E1 = ET.SubElement(material1, "E")
            E1.text = safe_attrib(material['young'])
            v1 = ET.SubElement(material1, "v")
            v1.text = safe_attrib(material['poisson'])

        # Write the initial tree to string
        xml_str = ET.tostring(febio_spec, encoding='utf-8').decode('utf-8')

        # Read the content of mesh.feb
        with open(meshPath, 'r') as mesh_file:
            mesh_content = mesh_file.read()

        # Insert the content of mesh.feb right after the </Material> tag
        insertion_point = xml_str.find('</Material>')
        xml_str = xml_str[:insertion_point + len('</Material>')] + '\n' + mesh_content + xml_str[insertion_point + len('</Material>'):]

        # Read the content of bcfile.txt (boundary file)
        with open(boundaryPath, 'r') as boundary_file:
            boundary_content = boundary_file.read()

        # Insert the content of bcfile.txt right after the mesh content
        insertion_point = xml_str.find('</Mesh>')
        xml_str = xml_str[:insertion_point + len('</Mesh>')] + '\n' + boundary_content + xml_str[insertion_point + len('</Mesh>'):]

        # Parse the updated string back into an XML structure
        febio_spec = ET.fromstring(xml_str)

        # Extract surface names from mesh content
        surface_names = find_surface_names(mesh_content)
        print("Surface names found in mesh:", surface_names)

        # Add MeshData and SurfaceData
        mesh_data = ET.SubElement(febio_spec, "MeshData")
        if data['dataMapped']['type'] == "pressure":
            surface_data = ET.SubElement(mesh_data, "SurfaceData", name="Pressure", type="const", data_type="scalar", surface="LungsFSI")
            surface_value = ET.SubElement(surface_data, "value")
            surface_value.text = "0.0"

        # Check if the node_set exists in mesh.feb content
        node_set_name = "exampleNodeSet"
        if node_set_name in mesh_content:
            # Add Boundary only if node_set_name exists in mesh.feb content
            boundary = ET.SubElement(febio_spec, "Boundary")
            bc1 = ET.SubElement(boundary, "bc", name=safe_attrib(node_set_name), type=safe_attrib("fix"), node_set=safe_attrib(node_set_name))
            dofs1 = ET.SubElement(bc1, "dofs")
            dofs1.text = "x,y,z"

            bc2 = ET.SubElement(boundary, "bc", name=safe_attrib(node_set_name), type=safe_attrib("fix"), node_set=safe_attrib(node_set_name))
            dofs2 = ET.SubElement(bc2, "dofs")
            dofs2.text = "sx,sy,sz"

        load_data = ET.SubElement(febio_spec, "LoadData")

        for i, load in enumerate(data['loadController']['loadControllers']):
            load_controller = ET.SubElement(load_data, "load_controller", id=safe_attrib(i + 1), type=safe_attrib(load['type'].lower()))
            interpolate = ET.SubElement(load_controller, "interpolate")
            interpolate.text = safe_attrib(load['interpolation'].upper())

            points = ET.SubElement(load_controller, "points")
            firstPoint = ET.SubElement(points, "point")
            firstPoint.text = safe_attrib(load['firstPoint'])

            secondPoint = ET.SubElement(points, "point")
            secondPoint.text = safe_attrib(load['secondPoint'])

        output = ET.SubElement(febio_spec, "Output")

        if data['step']['steps'][0]['loads'][0]['loadType'] == "pressure":
            plotfile = ET.SubElement(output, "plotfile", type="febio")
            var1 = ET.SubElement(plotfile, "var", type="displacement")
            var2 = ET.SubElement(plotfile, "var", type="shell strain")
            var3 = ET.SubElement(plotfile, "var", type="shell thickness")
            var4 = ET.SubElement(plotfile, "var", type="stress")
            # Only include valid output variables
            # Remove or comment out the invalid output variable
            # var5 = ET.SubElement(plotfile, "var", type="parameter['fem.surface_load[0].pressure']=Pressure")

        steps = ET.SubElement(febio_spec, "Step")

        for i, step in enumerate(data['step']['steps']):
            step_block = ET.SubElement(steps, "step", id=safe_attrib(i + 1), name=safe_attrib(step["name"]))

            control = ET.SubElement(step_block, "Control")
            analysis = ET.SubElement(control, "analysis")
            analysis.text = safe_attrib(step['analysisType'].upper())

            time_steps = ET.SubElement(control, "time_steps")
            time_steps.text = safe_attrib(step['timeSteps'])

            step_size = ET.SubElement(control, "step_size")
            step_size.text = safe_attrib(step['stepSize'])

            if step['analysisType'] == "dynamic":
                if step['moduleType'] == 'explicit':
                    solver = ET.SubElement(control, "solver", type="explicit-solid")
                else:
                    solver = ET.SubElement(control, "solver", type="solid")

                mass_lumping = ET.SubElement(solver, "mass_lumping")
                mass_lumping.text = safe_attrib(step['massLumping'])

                dyn_damping = ET.SubElement(solver, "dyn_damping")
                dyn_damping.text = safe_attrib(step['dynamicLumping'])

            plot_stride = ET.SubElement(control, "plot_stride")
            plot_stride.text = safe_attrib(step['plotStride'])

            loads = ET.SubElement(step_block, "Loads")
            for j, load in enumerate(step['loads']):
                if load['loadType'] == "pressure":
                    # Find the correct surface name
                    surface_name = "Solid"  # Default value
                    if surface_names:
                        surface_name = surface_names[0]  # Use the first found surface name

                    surface_load = ET.SubElement(loads, "surface_load", name=safe_attrib(load['pressureLabel']), type=safe_attrib(load['loadType'].lower()), surface=surface_name)

                    if load['pressureValType'] == "numeric":
                        pressure = ET.SubElement(surface_load, "pressure", lc=safe_attrib(i + 1))
                        pressure.text = safe_attrib(load['pressure'])
                    elif load['pressureValType'] == "expression":
                        pressure = ET.SubElement(surface_load, "pressure", lc=safe_attrib(i + 1), type="math")
                        pressure.text = safe_attrib(load['pressure'])
                    elif load['pressureValType'] == "map":
                        pressure = ET.SubElement(surface_load, "pressure", type="map")
                        pressure.text = "Pressure"

                    linear = ET.SubElement(surface_load, "linear")
                    linear.text = safe_attrib(load['linearParam'])
                    symmetric_stiffness = ET.SubElement(surface_load, "symmetric_stiffness")
                    symmetric_stiffness.text = safe_attrib(load['matrix'])
                    shell_bottom = ET.SubElement(surface_load, "shell_bottom")
                    shell_bottom.text = safe_attrib(load['pressureTop'])

        file_path = f'./projects${userid}/{projectid}/Solid/febio-case.feb'

        print('file_path', file_path)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write the final XML tree to file
        tree = ET.ElementTree(febio_spec)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)

        print(f"File written: {file_path}")

        return file_path

