import xml.etree.ElementTree as ET
import xml.dom.minidom
import re
import os

def dict_to_xml(tag, d):
    """Convert a dictionary to an XML Element."""
    elem = ET.Element(tag)
    if tag == "febio_spec":
        keys = ["@version", "Module",  "Globals", "Material", "Mesh", "MeshDomains", "MeshData", "Boundary", "Rigid", "Loads", "Step", "LoadData", "Output"]
    else:
        keys = d.keys()
    for key in keys:
        if key not in d.keys():
            continue
        val = d[key]
        if key == "#value":
            # If the key is '#value', set the text content of the current element
            elem.text = str(val)
        elif isinstance(val, dict):
            # Recursive call for sub-dictionaries
            child = dict_to_xml(key, val)
            elem.append(child)
        elif isinstance(val, list):
            # Handle lists by creating multiple child elements with the same tag
            for sub_val in val:
                child = dict_to_xml(key, sub_val)
                elem.append(child)
        else:
            # Handle attributes if the key starts with "@", otherwise treat it as a child element
            if key.startswith('@'):
                elem.set(key[1:], str(val))  # Attribute
            else:
                child = ET.Element(key)  # Regular child element
                child.text = str(val)
                elem.append(child)
    return elem

def json_to_xml_string(json_obj, root_tag="root"):
    """Convert JSON object to an XML string."""
    root = dict_to_xml(root_tag, json_obj)
    # return ET.tostring(root, encoding="unicode")
    return root

def json_to_febio_template(febio_form, xml_object):

    xml_object["MeshData"]["SurfaceData"]["@name"] = febio_form["dataMapped"]["type"]

    for i in range(len(xml_object["Material"]["material"])):
        if i >= len(febio_form["material"]["materials"]):
            continue
        material = febio_form["material"]["materials"][i]
        xml_object["Material"]["material"][i].update({
            "@name": material["name"],
            "@type": material["type"],
            "density": {
                "#value": material["density"]
            },
            "v": {
                "#value": material["poisson"]
            },
            "E": {
                "#value": material["young"]
            }
        })

    # Convert load controllers back to XML format
    if("LoadData" in xml_object.keys()):
        for i in range(len(xml_object["LoadData"]["load_controller"])):
            if i >= len(febio_form["loadController"]["loadControllers"]):
                continue
            load_controller = febio_form["loadController"]["loadControllers"][i]
            xml_object["LoadData"]["load_controller"][i].update({
                "@type": load_controller["type"],
                "interpolate": {
                    "#value": load_controller["interpolation"]
                },
                "points": {
                    "pt": [
                        {"#value": load_controller["firstPoint"]},
                        {"#value": load_controller["secondPoint"]}
                    ]
                }
            })

    # Convert steps back to XML format
    for i in range(len(xml_object["Step"]["step"])):
        if i >= len(febio_form["step"]["steps"]):
            continue
        step = febio_form["step"]["steps"][i]
        step_data = {
            "@name": step["name"],
            "Control": {
                "solver": {
                    "@type": step["moduleType"],
                    "mass_lumping": {
                        "#value": step.get("massLumping", "")
                    },
                    "dyn_damping": {
                        "#value": step.get("dynamicLumping", "")
                    }
                },
                "analysis": {
                    "#value": step["analysisType"]
                },
                "time_steps": {
                    "#value": step["timeSteps"]
                },
                "step_size": {
                    "#value": step["stepSize"]
                },
                "plot_stride": {
                    "#value": step["plotStride"]
                }
            },
            "Loads": {
                "surface_load": []
            }
        }

        # Convert loads back to XML format
        for load in step["loads"]:
            surface_load = {
                "@name": load["pressureLabel"],
                "pressure": {
                    "@lc": load["loadController"],
                    "#value": load["pressure"]
                },
                "linear": {
                    "#value": load["linearParam"]
                },
                "symmetric_stiffness": {
                    "#value": load["matrix"]
                },
                "shell_bottom": {
                    "#value": load["pressureTop"]
                },
                "@surface": load["surfaceName"],
                "@type": load["loadType"]
            }
            step_data["Loads"]["surface_load"].append(surface_load)

        xml_object["Step"]["step"][i].update(step_data)

    return xml_object

class FebioConfigGenerator():
    def __init__(self) -> None:
        pass

    def generate_xml_(self, data, userid, projectid, caseid, meshPath, boundaryPath, meshValue={}, boundaryValue={}):

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
        if meshPath:
            with open(meshPath, 'r') as mesh_file:
                mesh_content = mesh_file.read()
        else:
            print("else")
            mesh_content = json_to_xml_string(meshValue, "Mesh")

        # Insert the content of mesh.feb right after the </Material> tag
        insertion_point = xml_str.find('</Material>')
        print(mesh_content)
        xml_str = xml_str[:insertion_point + len('</Material>')] + '\n' + mesh_content + xml_str[insertion_point + len('</Material>'):]

        # Read the content of bcfile.txt (boundary file)
        if boundaryPath:
            with open(boundaryPath, 'r') as boundary_file:
                boundary_content = boundary_file.read()
        else:
            boundary_content = json_to_xml_string(boundaryValue, "Boundary")

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

        file_path = f'./projects/{userid}/{projectid}/{caseid}/solid-FEBio/Solid/febio-case.feb'

        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write the final XML tree to file
        tree = ET.ElementTree(febio_spec)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)

        return file_path

    def generate_xml(self, data, userid, projectid, caseid):
        
        data["template"] = json_to_febio_template(data, data["template"])
        
        file_path = f'./projects/{userid}/{projectid}/{caseid}/solid-FEBio/Solid/febio-case.feb'

        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write the final XML tree to file
        tree = ET.ElementTree(json_to_xml_string(data["template"], "febio_spec"))
        tree.write(file_path, encoding="utf-8", xml_declaration=True)

        return file_path