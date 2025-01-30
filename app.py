from math import log
from flask import Flask, request, jsonify, make_response, send_from_directory, send_file, Response, stream_with_context, Blueprint
from flask_cors import CORS
from flask_mail import Mail, Message
import os
import shutil
from requests import get
from werkzeug.utils import secure_filename
import zipfile
import subprocess
import xml.etree.ElementTree as ET
import json
from dotenv import load_dotenv
import csv
import requests

import re
import socket


from auth0_api import auth0_api

from genXML import PreCICEConfigGenerator
from genBlastFOAM import BlastFoamGenerator
from genFebio import FebioConfigGenerator
from genPulse import PulseConfigGenerator
from scriptGen import ScriptGen

from utils.formatXML import format_and_overwrite_xml_file
from utils.fileParse import get_log_enabled, tail_file

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)

# Store the running pvserver process
pvserver_process = None

app.register_blueprint(auth0_api)
cors = CORS(app, resource={
    r"/*":{
        "origins":"*"
    }
})


load_dotenv()
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_ADDRESS')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)
INSTANCE_NAME = os.getenv('INSTANCE_NAME')

backend_routes = Blueprint('user', __name__, url_prefix=INSTANCE_NAME)

@backend_routes.before_request
def before_request():
    if not os.path.exists('./projects'):
        os.makedirs('./projects')

@backend_routes.after_request
def handle_options(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"

    return response

def update_control_dict(caseid, projectid, blastfoam_folder, userid):
    """
    Updates the controlDict file in the specified blastfoam folder to change stopAt to noWriteNow.
    """
    control_dict_path = os.path.join('./projects', userid, projectid, caseid, blastfoam_folder, 'system', 'controlDict')
    print(control_dict_path)

    # Check if the file exists
    if not os.path.exists(control_dict_path):
        return {"error": "controlDict file does not exist."}, 404

    # Read and update the controlDict file
    try:
        with open(control_dict_path, 'r') as file:
            lines = file.readlines()

        # Update stopAt value
        with open(control_dict_path, 'w') as file:
            for line in lines:
                if line.strip().startswith("stopAt"):
                    file.write("stopAt          noWriteNow;\n")
                else:
                    file.write(line)

        return {"message": "controlDict updated successfully."}, 200

    except Exception as e:
        return {"error": f"Failed to update controlDict: {str(e)}"}, 500

@backend_routes.route("/<caseid>/<projectid>/<userid>/<blastfoam_folder>/update_control_dict", methods=['GET', 'POST', 'OPTIONS']) # type: ignore
def update_control_dict_endpoint(caseid, projectid, userid, blastfoam_folder):
    """
    API endpoint to update the controlDict file's stopAt value in the specified blastfoam folder.
    """
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()

    if request.method == 'POST' or request.method == 'GET':
        # Call the function to update controlDict
        userid = process_userid_for_folder_name(userid)
        result, status_code = update_control_dict(caseid, projectid, f'fluid-blastFOAM/{blastfoam_folder}', userid)
        return jsonify(result), status_code

def get_public_ip():
    try:
        # Use an external service to get the public IP address
        response = requests.get('https://api.ipify.org?format=json')
        ip_data = response.json()
        return ip_data['ip']
    except requests.RequestException as e:
        return "Unable to retrieve public IP"

def find_available_port(starting_port=11111):
    port = starting_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
            port += 1

def find_pvserver_process(projects_dir):
    try:
        # Get the list of PIDs running in the projects_dir with pvserver as the command
        result = subprocess.run(f"lsof +D {projects_dir} | grep '^pvserver' | awk '{{print $2}}'", shell=True, capture_output=True, text=True)
        if result.stdout:
            pids = result.stdout.split()
            for pid in pids:
                # Get the port number for each PID
                port_result = subprocess.run(f"lsof -Pan -p {pid} -i | grep LISTEN", shell=True, capture_output=True, text=True)
                if port_result.stdout:
                    for line in port_result.stdout.splitlines():
                        parts = line.split()
                        print(parts)
                        for part in parts:
                            if '*:' in part:
                                port = int(part.split(':')[-1])
                                print(f"Found pvserver process with PID {pid} and port {port}") 
                                return int(pid), port
    except Exception as e:
        print(f"Error finding pvserver process: {e}")
    return None, None

@backend_routes.route("/<caseid>/<projectid>/<userid>/pvserver", methods=['GET', 'POST', 'DELETE', 'OPTIONS']) # type: ignore
def manage_pvserver(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    
    projects_dir = f'./projects/{userid}/{projectid}/{caseid}'

    if not os.path.exists(projects_dir):
        return jsonify({"error": f"Project directory '{projectid}' does not exist."}), 404

    if request.method == 'POST' or request.method == 'GET':
        pvserver_pid, pvserver_port = find_pvserver_process(projects_dir)
        if pvserver_pid:
            # Get the public IP address of the server
            public_ip = get_public_ip()

            # Construct the response data with the correct public information
            response_data = {
                "message": "PVServer is already running.",
                "connection_url": f"cs://{public_ip}:{pvserver_port}",
                "port": pvserver_port,
                "ip_address": public_ip
            }
            return jsonify(response_data), 200

        try:
            port = find_available_port(starting_port=11111)

             # Define the log file path
            log_file_path = os.path.join(projects_dir, 'pvserver.log')

            # Open the log file in append mode
            with open(log_file_path, 'a') as log_file:
                # Execute the pvserver command in the specified project directory
                subprocess.Popen(['pvserver', f'--server-port={port}'], cwd=projects_dir, stdout=log_file, stderr=log_file, text=True)

            # Get the public IP address of the server
            public_ip = get_public_ip()

            # Construct the response data with the correct public information
            response_data = {
                "message": "PVServer started successfully.",
                "connection_url": f"cs://{public_ip}:{port}",
                "port": port,
                "ip_address": public_ip
            }

            return jsonify(response_data), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif request.method == 'DELETE':
        pvserver_pid, _ = find_pvserver_process(projects_dir)
        if pvserver_pid:
            try:
                # Terminate the pvserver process
                os.kill(pvserver_pid, 15)  # 15 is the signal number for SIGTERM
                return jsonify({"message": "PVServer stopped successfully."}), 200
            except Exception as e:
                return jsonify({"error": f"Failed to stop pvserver: {str(e)}"}), 500
        else:
            return jsonify({"error": "PVServer is not running."}), 400

@backend_routes.route("/<caseid>/<projectid>/<userid>/blastfoamgen", methods=['POST', 'OPTIONS'])  # type: ignore
def handle_blastfoam(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        files = json.loads(request.form.get('files')) # type: ignore
        
        userid = process_userid_for_folder_name(userid)
        projects_dir = f'./projects/{userid}/{projectid}/{caseid}'
        
        if not os.path.exists(projects_dir):
            os.makedirs(projects_dir)

        for mesh_key in request.files:
            
            mesh = request.files.get(mesh_key)
            # {casename}_{patchname}
            case_name = mesh_key.split('#')[0]
            # print(mesh.name)
            # print(case_name)
            
            if not os.path.exists(f'{projects_dir}/fluid-blastFOAM/{case_name}/constant/geometry'): # type: ignore
                os.makedirs(f'{projects_dir}/fluid-blastFOAM/{case_name}/constant/geometry') # type: ignore
            mesh.save(f'{projects_dir}/fluid-blastFOAM/{case_name}/constant/geometry/{mesh.filename}') # type: ignore

        
        for blastfoam_file in files:
            file_path = blastfoam_file['filePath']
            file_directory = f'{projects_dir}/{os.path.dirname(file_path)}'
            if not os.path.exists(file_directory):
                os.makedirs(file_directory)
            
            content = blastfoam_file['content']
            
            with open(f'{projects_dir}/{file_path}', 'w') as file:
                file.write(content)
                if 'Allclean' in file_path or 'Allrun' in file_path:
                    os.chmod(f'{projects_dir}/{file_path}', 0o777)

        for item in os.listdir(projects_dir):
            item_path = os.path.join(projects_dir, item)
            if os.path.isdir(item_path):
                if 'Allclean' in os.listdir(item_path):
                    os.chmod(os.path.join(item_path, 'Allclean'), 0o755)
                    subprocess.run(['bash', os.path.join(item_path, 'Allclean')])

        zip_file_name = os.path.basename(projects_dir) + '.zip'
        zip_file_path = os.path.join('./tmp', secure_filename(zip_file_name)) # type: ignore
        shutil.make_archive(base_name=zip_file_path.replace('.zip', ''), format='zip', root_dir=projects_dir)

        return send_file(zip_file_path, as_attachment=True)

@backend_routes.route('/<caseid>/<projectid>/<userid>/febiogen', methods=['POST', 'OPTIONS']) # type: ignore
def handle_febiogen(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        userid = process_userid_for_folder_name(userid)
        directory_path = f'./projects/{userid}/{projectid}/{caseid}/solid-FEBio/Solid'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        if not os.path.exists(f'./tmp/{projectid}/Solid/'):
            os.makedirs(f'./tmp/{projectid}/Solid/')

        solver_case_json = request.form.get('solverCase')
        templateUrl = request.form.get('templateLink')
        data = json.loads(solver_case_json) # type: ignore
        data['template'] = fetch_feb_file_from_database(templateUrl)
        if data['template']:
            print(data['template'].keys())

        generator = FebioConfigGenerator()
        output_file_path = generator.generate_xml(data, userid, projectid, caseid)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)

        ScriptGen.gen_clean_script(projectid, userid, f"{caseid}/solid-FEBio")
        ScriptGen.gen_solid_script(projectid, userid, caseid)
        print(directory, filename)
        return send_from_directory(directory, filename, as_attachment=True) 
    
@backend_routes.route('/<caseid>/<projectid>/<userid>/lsdynagen', methods=['POST', 'OPTIONS']) # type: ignore
def handle_lsdynagen(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        userid = process_userid_for_folder_name(userid)
        directory_path = f'./projects/{userid}/{projectid}/{caseid}/hydro-LSDYNA/'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        solver_case_json = request.form.get('solverCase')
        serverLink = request.form.get('serverLink')
        data = json.loads(solver_case_json) # type: ignore
        for file_data in data["files"]:
            file_url = file_data["url"]
            file_content = fetch_file_from_database(f"{serverLink}{file_url}")  # Assuming this returns binary content
            file_name = file_data["name"]

            # Save file in the directory
            file_path = os.path.join(directory_path, file_name)
            with open(file_path, 'wb') as f:
                f.write(file_content)

         # Create the zip file in the ./tmp directory
        zip_file_name = secure_filename(os.path.basename(directory_path.rstrip('/'))) + '.zip'
        tmp_dir = f'./tmp/{caseid}'
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        
        zip_file_path = os.path.join(tmp_dir, zip_file_name)
        shutil.make_archive(base_name=zip_file_path.replace('.zip', ''), format='zip', root_dir=directory_path)

        # Send the zip file to the client
        return send_file(zip_file_path, as_attachment=True, mimetype='application/zip')

@backend_routes.route('/<caseid>/<projectid>/<userid>/pulsegen', methods=['POST', 'OPTIONS']) # type: ignore
def handle_pulsegen(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()

        userid = process_userid_for_folder_name(userid)
        directory_path = f'./projects/{userid}/{projectid}/{caseid}/physiology-pulse'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        if not os.path.exists(f'./tmp/{projectid}/physiology-pulse/'):
            os.makedirs(f'./tmp/{projectid}/physiology-pulse/')

        generator = PulseConfigGenerator()

        # Get the absolute path of app.py
        app_dir = os.path.dirname(os.path.abspath(__file__))

        output_file_path = generator.generate_py_script(data, userid, projectid, caseid, app_dir)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)


        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isdir(item_path):
                if 'Allclean' in os.listdir(item_path):
                    os.chmod(os.path.join(item_path, 'Allclean'), 0o755)
                    subprocess.run(['bash', os.path.join(item_path, 'Allclean')])

        return send_from_directory(directory, filename, as_attachment=True)

@backend_routes.route('/<caseid>/<projectid>/<userid>/precicegen', methods=['POST', 'OPTIONS']) # type: ignore
def handle_precice(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()

        generator = PreCICEConfigGenerator()

        output_file_path = generator.generate_xml(data, projectid, userid, caseid)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)

        format_and_overwrite_xml_file(output_file_path)


        ScriptGen.gen_clean_script(projectid, userid, f"{caseid}/coupling-preCICE")
        print(directory, filename)
        return send_from_directory(directory, filename, as_attachment=True)
    
@backend_routes.route('/<caseid>/<projectid>/<userid>/febio', methods=['POST', 'OPTIONS']) # type: ignore
def handle_febio(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part in the request', 400

        file = request.files['file']

        if file.filename == '':
            return 'No selected file', 400

        if file:
            userid = process_userid_for_folder_name(userid)
            directory_path = f'./projects/{userid}/{projectid}/{caseid}/solid-FEBio/Solid'
            if not os.path.exists(directory_path):
                os.makedirs(directory_path)
                
            file_path = os.path.join(directory_path, file.filename) # type: ignore
            file.save(file_path)


            if file.filename.endswith('.zip'): #type: ignore
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    root_folder = next(x for x in zip_ref.namelist() if x.endswith('/'))

                    for item in zip_ref.namelist():
                        if item.startswith(root_folder) and not item.endswith('/'):
                            target_file_path = os.path.join(directory_path, os.path.relpath(item, root_folder))

                            os.makedirs(os.path.dirname(target_file_path), exist_ok=True)

                            with zip_ref.open(item) as source, open(target_file_path, 'wb') as target:
                                shutil.copyfileobj(source, target)

                os.remove(file_path)


            ScriptGen.gen_solid_script(projectid, userid, caseid)
            return 'File uploaded successfully', 200
    
@backend_routes.route("/<caseid>/<projectid>/<userid>/displacementgraph", methods=['GET', 'OPTIONS']) # type: ignore
def handle_displacement_graph(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base_path = f'./projects/{userid}/{projectid}/{caseid}'
        validation_path = f'{project_base_path}/validation'

        if not os.path.exists(validation_path):
            os.makedirs(validation_path)
            return 'Validation folder not found', 404

        displacement_graph_path = f'{project_base_path}/validation/blastfoam_displacement.png'

        if not os.path.exists(displacement_graph_path):
            return 'Graph not found', 404
        
        subprocess.run(['python3', project_base_path + "/validation/plot-blastfoam-cell-disp-febio-disp.py"])

        return send_file(displacement_graph_path, as_attachment=True)

@backend_routes.route('/<caseid>/<projectid>/<userid>/graphfiles', methods=['GET', 'OPTIONS'])
def handle_getgraphfiles(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base = f'./projects/{userid}/{projectid}/{caseid}'
        displacement_graph_path = f'{project_base}/validation/blastfoam_displacement.png'
        # physiology_graph_path = f'{os.getenv("PULSE_INSTALL_DIR")}/pulseresults.csv'
        physiology_graph_path = f'./projects/{userid}/{projectid}/{caseid}/physiology-pulse/pulseresults.csv'

        
        graph_files = {
            "Displacement Response": "",
            "Pulse Data Visualization": physiology_graph_path,
        }


        if not os.path.exists(displacement_graph_path):
            del graph_files["Displacement Response"]
        if not os.path.exists(physiology_graph_path):
            del graph_files["Pulse Data Visualization"]
        
        
    if os.path.exists(project_base):
        for folder in os.listdir(project_base):
            folder_path = os.path.join(project_base, folder)
            if os.path.isdir(folder_path):
                for file in os.listdir(folder_path):
                    if file.endswith('.csv'):
                        if file != 'pulseresults.csv':

                            file_path = os.path.join(folder_path, file)
                            # Getting the path relative to project_base
                            relative_path = os.path.relpath(file_path, project_base)
                            graph_files[relative_path] = relative_path
    
    return jsonify(graph_files), 200

@backend_routes.route('/<caseid>/<projectid>/<userid>/graphfile', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getgraphfile(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        graphfilename = request.args.get('name') 
        if (".csv" not in graphfilename): # type: ignore
            return "Invalid file type", 400

        userid = process_userid_for_folder_name(userid)
        file_path = f'./projects/{userid}/{projectid}/{caseid}/{graphfilename}'
        try:
            with open(file_path, mode='r', newline='') as file:
                reader = csv.reader(file)
                title = next(reader)
                headers = next(reader)  
                xvals, yvals = [], []
                for row in reader:
                    if len(row) >= 2:  
                        xvals.append(row[0])
                        yvals.append(row[1])
                
                result = {
                    "title": title[0] if len(title) > 0 else "Graph",
                    "xgraph": headers[0] if len(headers) > 0 else "X",
                    "ygraph": headers[1] if len(headers) > 1 else "Y",
                    "xvals": xvals,
                    "yvals": yvals
                }
                return result
            

        except FileNotFoundError:
            return "File not found", 404
        except Exception as e:
            return f"An error occurred: {str(e)}", 500

@backend_routes.route('/<caseid>/<projectid>/<userid>/raw', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getrawgraphfile(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        graphfilename = request.args.get('name')
        addon = request.args.get('add')
        userid = process_userid_for_folder_name(userid)
        file_path = f'./projects/{userid}/{projectid}/{caseid}/physiology-pulse/{graphfilename}'
        if (addon == "pulseInstall"):
            file_path = f'{os.getenv("PULSE_INSTALL_DIR")}/{graphfilename}'
        
        try:
            with open(file_path, mode='r', newline='') as file:
                reader = csv.reader(file)
                selected_lines = []
                for i, line in enumerate(reader):

                    if i % 50 == 0:
                        # print(i, line[0])
                        #print(line)
                        selected_lines.append(line)
                    if len(selected_lines) >= 20:
                        break

                response = jsonify(selected_lines)
                return response

        except FileNotFoundError:
            return "File not found", 404
        except Exception as e:
            return f"An error occurred: {str(e)}", 500

@backend_routes.route('/<caseid>/<projectid>/<userid>/logfiles', methods=['GET']) # type: ignore
def handle_getlogfiles(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base = f'./projects/{userid}/{projectid}/{caseid}'

        if not os.path.exists(project_base):
            os.makedirs(project_base)
    
        log_files = {}
        xml_config_path = f'{project_base}/coupling-preCICE/precice-config.xml'
        log_file_name = ""

        enabled = False
        lfm = None

        if os.path.exists(xml_config_path):
            enabled, lfm = get_log_enabled(xml_config_path)
            log_file_name = lfm if lfm is not None else log_file_name

        log_files = find_log_files(project_base)

        return jsonify(log_files), 200

@backend_routes.route('/<caseid>/<projectid>/<userid>/inputFiles', methods=['GET']) # type: ignore
def handle_getinputFiles(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base = f'./projects/{userid}/{projectid}/{caseid}'

        if not os.path.exists(project_base):
            return jsonify({"error": "Project path does not exist"}), 404

        # Define the folder and file structure to search
        search_structure = {
            "fluid-blastFOAM": {
                "0": "ALL",
                "constant": [
                    "dynamicMeshDict",
                    "g",
                    "momentumTransport",
                    "phaseProperties"
                ],
                "system": [
                    "blockMeshDict",
                    "controlDict",
                    "decomposeParDict",
                    "fvSchemes",
                    "fvSolution",
                    "preciceDict",
                    "setFieldsDict",
                    "snappyHexMeshDict",
                    "surfaceFeaturesDict"
                ]
            },
            "solid-FEBio": {
                "Solid": ["febio-case.feb"]
            },
            "coupling-preCICE": ["precice-config.xml"],
            "physiology-pulse": ["runPulse.py"]
        }

        def find_files_by_structure(base_dir, folder_structure, current_path=""):
            """
            Recursively searches for files matching the structure and returns them in a dictionary
            with relative paths as keys and lists of filenames as values.
            """
            result_files = {}

            for folder, contents in folder_structure.items():
                folder_path = os.path.join(base_dir, current_path, folder)
                if folder == "fluid-blastFOAM":
                    # Special handling for fluid-blastFOAM: recursively search all subfolders
                    case_base_path = os.path.join(base_dir, current_path, folder)
                    if os.path.exists(case_base_path):
                        for case_folder in os.listdir(case_base_path):
                            case_path = os.path.join(case_base_path, case_folder)
                            if os.path.isdir(case_path):
                                # Only look for 0, constant, or system directly under case_path
                                for subfolder, subcontents in contents.items():
                                    specific_path = os.path.join(case_path, subfolder)
                                    relative_path = os.path.relpath(specific_path, base_dir).replace(os.sep, ":")
                                    if os.path.exists(specific_path):
                                        if subcontents == "ALL":
                                            # Add all files in this folder
                                            all_files = [
                                                f for f in os.listdir(specific_path)
                                                if os.path.isfile(os.path.join(specific_path, f))
                                            ]
                                            if all_files:
                                                result_files[relative_path] = all_files
                                        else:
                                            # Match specific files case-insensitively
                                            matched_files = [
                                                f for f in os.listdir(specific_path)
                                                if os.path.isfile(os.path.join(specific_path, f)) and
                                                f.lower() in map(str.lower, subcontents)
                                            ]
                                            if matched_files:
                                                result_files[relative_path] = matched_files
                else:
                    # General case for other folders
                    if os.path.exists(folder_path):
                        relative_path = os.path.join(current_path, folder).replace(os.sep, ":")
                        if isinstance(contents, dict):
                            # Traverse subdirectories
                            nested_files = find_files_by_structure(base_dir, contents, os.path.join(current_path, folder))
                            result_files.update(nested_files)
                        elif contents == "ALL":
                            # Add all files in this folder
                            all_files = [
                                f for f in os.listdir(folder_path)
                                if os.path.isfile(os.path.join(folder_path, f))
                            ]
                            if all_files:
                                result_files[relative_path] = all_files
                        else:
                            # Add specific files, matching case-insensitively
                            matched_files = [
                                f for f in os.listdir(folder_path)
                                if os.path.isfile(os.path.join(folder_path, f)) and
                                f.lower() in map(str.lower, contents)
                            ]
                            if matched_files:
                                result_files[relative_path] = matched_files

            return result_files

        # Start searching for files
        matched_files = find_files_by_structure(project_base, search_structure)

        # Return the results
        return jsonify(matched_files), 200

@backend_routes.route('/<caseid>/<projectid>/<userid>/<filename>/inputFile', methods=['GET']) # type: ignore
def handle_getinputFile(caseid, projectid, userid, filename):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        filename = filename.replace(":", "/")
        project_base = f'./projects/{userid}/{projectid}/{caseid}'

        if not os.path.exists(project_base):
            return jsonify({"error": "Project path does not exist"}), 404

        file_path = os.path.join(project_base, filename)

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        try:
            with open(file_path, 'r') as file:
                content = file.read()
            return jsonify({"content": content}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

def find_log_files(root_dir):
    log_files = {}
    for dirpath, _, filenames in os.walk(root_dir):
        # Find .log files in the current directory
        current_log_files = [f for f in filenames if f.endswith(".log") or f.startswith("log.")]
        if current_log_files:
            # Sort files by modification time (latest first)
            current_log_files.sort(
                key=lambda f: os.path.getmtime(os.path.join(dirpath, f)),
                reverse=True
            )
            # Remove root_dir from path and replace '/' with ':'
            relative_path = dirpath.replace(root_dir, "").replace(os.sep, ":").lstrip(":")
            log_files[relative_path] = current_log_files
    return log_files

@backend_routes.route('/<caseid>/<projectid>/<userid>/<casename>/<logfilename>/logfile', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getlogfile(caseid, projectid, userid, casename: str, logfilename):
    # Handle preflight CORS request
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()

    # Handle GET request
    elif request.method == 'GET':
        # Process the userid for folder name if necessary
        userid = process_userid_for_folder_name(userid)

        # Replace colon with a slash in casename to avoid filesystem issues
        if ":" in casename:
            casename = casename.replace(":", "/")

        # Construct the file path
        file_path = f'./projects/{userid}/{projectid}/{caseid}/{casename}/{logfilename}'

        try:
            # Check if the file exists and is accessible (optional but recommended for safety)
            with open(file_path, 'r') as f:
                # Streaming the file content using 'tail_file' function
                return Response(stream_with_context(tail_file(file_path)), mimetype='text/event-stream')

        except FileNotFoundError:
            # Return an error response if the file does not exist
            return Response(f"File {logfilename} not found.", status=404)

        except Exception as e:
            # Handle other errors, like permission issues or unexpected errors
            return Response(f"Error reading log file: {str(e)}", status=500)

@backend_routes.route('/<caseid>/<projectid>/<userid>/download', methods=['GET', 'OPTIONS']) # type: ignore
def handle_download(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base = f'./projects/{userid}/{projectid}/{caseid}'


        args = request.args
        filename = args.get('filename')

        if not filename:
            return "No filename provided", 400

        # return the file as an attachment

        return send_from_directory(project_base, filename, as_attachment=True)


@backend_routes.route('/<projectid>/<userid>/projects', methods=['POST', 'OPTIONS']) # type: ignore
def handle_patch_project(projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()
        userid = process_userid_for_folder_name(userid)
        project_base = f'./projects/{userid}/{projectid}'
        if not os.path.exists(project_base):
            os.makedirs(project_base)

        if 'projectName' in data:
            os.rename(project_base, f'./projects/{userid}/{data["projectName"]}')

        return {"message": 'Project updated'}, 200

@backend_routes.route('/<caseid>/<projectid>/<userid>/rename-simulation-case', methods=['POST', 'OPTIONS']) # type: ignore
def handle_patch_simulation(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()
        userid = process_userid_for_folder_name(userid)
        simulation_base = f'./projects/{userid}/{projectid}/{caseid}'
        if not os.path.exists(simulation_base):
            os.makedirs(simulation_base)

        if 'simulationName' in data:
            os.rename(simulation_base, f'./projects/{userid}/{projectid}/{data["simulationName"]}')

        return {"message": 'Simulation Case Folder name updated'}, 200

@backend_routes.route('/<caseid>/<simulationcaseid>/<projectid>/<userid>/rename-case', methods=['POST', 'OPTIONS']) # type: ignore
def handle_patch_case(caseid, simulationcaseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()
        userid = process_userid_for_folder_name(userid)
        case_base = f'./projects/{userid}/{projectid}/{simulationcaseid}/fluid-blastFOAM/{caseid}'
        if not os.path.exists(case_base):
            # os.makedirs(case_base)
            return {"message": "Case folder doesn't exist"}, 404

        if 'caseName' in data:
            os.rename(case_base, f'./projects/{userid}/{projectid}/{simulationcaseid}/fluid-blastFOAM/{data["caseName"]}')

        return {"message": 'Case Folder name updated'}, 200

def delete_directory(path):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            os.remove(file_path)
        for name in dirs:
            dir_path = os.path.join(root, name)
            os.rmdir(dir_path)
    os.rmdir(path)

@backend_routes.route('/<projectid>/<userid>/deleteproject', methods=['GET', 'OPTIONS']) # type: ignore
def handle_delete_project(projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base = f'./projects/{userid}/{projectid}'
        if os.path.exists(project_base):
            delete_directory(project_base)
            return {"message": 'Project deleted'}, 200
        else:
            return {"message": 'Project not found'}, 404

@backend_routes.route('/<projectid>/<caseid>/<userid>/deleteCase', methods=['GET', 'OPTIONS']) # type: ignore
def handle_deleteCase(projectid, caseid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base = f'./projects/{userid}/{projectid}/{caseid}'
        if os.path.exists(project_base):
            delete_directory(project_base)
            return {"message": 'Case deleted'}, 200
        else:
            return {"message": 'Case not found'}, 404

@backend_routes.route('/<caseid>/<projectid>/<userid>/run', methods=['GET'])  # type: ignore
def handle_run(caseid, projectid, userid):
    if request.method == 'GET':
        print("running", caseid, projectid)
        userid = process_userid_for_folder_name(userid)
        project_base_path = f'./projects/{userid}/{projectid}/{caseid}'
        ScriptGen.gen_run_script(caseid, projectid, userid)

        # Check for the existence of a directory starting with 'Solid'
        solid_dir = next((d for d in os.listdir(project_base_path) if os.path.isdir(os.path.join(project_base_path, d)) and d.startswith('Solid')), None)
        if solid_dir:
            ScriptGen.gen_solid_script(caseid, projectid, userid)

        try:
            result = subprocess.run(
                ['bash', os.path.join(project_base_path, 'run.sh')],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,  # Ensures output is captured as a string
                check=True  # Raises an exception if the command fails
            )
            # print("STDOUT:")
            # print(result.stdout)  # Logs the standard output
            # print("STDERR:")
            # print(result.stderr)  # Logs the standard error (if any)
        except subprocess.CalledProcessError as e:
            print("An error occurred while running the script.")
            print("Return Code:", e.returncode)
            # print("STDOUT:", e.stdout)
            # print("STDERR:", e.stderr)

        return 'Simulation started', 200

@backend_routes.route('/<caseid>/<projectid>/<userid>/isRunning', methods=['GET'])  # type: ignore
def handle_is_running(caseid, projectid, userid):
    if request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base_path = f'./projects/{userid}/{projectid}/{caseid}'
        command = f"lsof +D {project_base_path} | grep 'mpirun' | awk '{{print $2}}'"

        try:
            # Run the command and capture the output
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(result.stdout)
            # Check if there are any processes
            if result.stdout.strip():  # If output is not empty
                return {"success": True, "running": True}, 200
            else:
                return {"success": True, "running": False}, 200
        except subprocess.CalledProcessError as e:
            # If command fails (e.g., directory doesn't exist or permission issues)
            print(f"Error running command: {e}")
            return {"success": False, "running": False}, 200
        except Exception as e:
            # Handle any other exceptions
            print(f"Unexpected error: {e}")
            return {"success": False, "running": False}, 200

@backend_routes.route('/test', methods=['GET', 'OPTIONS']) # type: ignore
def handle_test1():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        return "Hello World!"

@backend_routes.route('/alive', methods=['GET', 'OPTIONS']) # type: ignore
def handle_alive():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        return jsonify({"alive": True})

@backend_routes.route('/sendemail', methods=['POST'])
def send_email():

    event = json.loads(request.data)['event']
    msg = Message('A new user has attempted to sign up through the Simulation webapp app.', sender = 'aiformissiledefense@gmail.com', recipients = ['satish@epitomeri.com'])
    msg.body = f'New user has signed up\n{event["user"]["email"]}\nhttps://manage.auth0.com/dashboard/us/{os.getenv("AUTH0_NAME")}/users\nPlease send the user verification message: {os.getenv("BACKEND_URL")}/verify?email={event["user"]["email"]}'
    mail.send(msg)
    return "Message sent!"

@backend_routes.route('/verify', methods=['GET'])
def verify():
    verify_email = request.args.get('email')

    msg = Message('Your account has been verified', sender = 'aiformissiledefense@gmail.com', recipients = [verify_email])
    msg.body = 'You may now access the Simulation webapp.\nhttps://undexfspi.com'
    mail.send(msg)
    return "User verification email has been sent!"


#TODO: FIX THIS


def parse_other_file(filename, content):
    probes = {}
    
    # Split the content into lines
    lines = content.splitlines()
    
    # Parse the probe locations
    for line in lines:
        if line.startswith("# Probe"):
            match = re.match(r"# Probe (\d+) \(([-\d.]+) ([-\d.]+) ([-\d.]+)\)", line)
            if match:
                probe_id = f"Probe {match.group(1)}"
                location = [float(match.group(2)), float(match.group(3)), float(match.group(4))]
                probes[probe_id] = {'Location': location, 'Data': {}}
    
    # Find the header line and the starting index for time values
    header_line_index = None
    for i, line in enumerate(lines):
        if "Time" in line.strip():
            header_line_index = i
            break
    
    if header_line_index is None:
        raise ValueError("Header line not found")
    
    # Parse the time values from the line following the header
    for line in lines[header_line_index + 1:]:
        if line.startswith("#") or line.strip() == '':
            continue
        values = line.strip().split()
        time = values[0]
        value_list = [float(value) for value in values[1:]]
        
        for probe_id in probes:
            index = int(probe_id.split()[1])
            probes[probe_id]['Data'][time] = value_list[index]
    
    # Construct the final output format
    probe_indices = tuple(int(probe.split()[1]) for probe in probes.keys())
    result = {
        'Name of File': filename,
        'Probe Indices': probe_indices,
        'Data': probes
    }
    
    return result

@backend_routes.route("/<caseid>/<projectid>/<userid>/<caseName>/blastfoam/data", methods=['GET', 'OPTIONS'])  # type: ignore
def fetch_blastfoam_data(caseid, projectid, userid, caseName):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base_path = f'./projects/{userid}/{projectid}/{caseid}'
        project_base = f'{project_base_path}/fluid-blastFOAM/{caseName}/postProcessing/probes/0'

        data_files = ['cellDisplacement', 'p', 'U', 'rho']
        response_data = []

        # Check if the base directory exists
        if not os.path.exists(project_base):
            print(f"Project directory does not exist: {project_base}")
            return jsonify({"error": "Project directory does not exist"}), 404

        for subdir, dirs, files in os.walk(project_base):
            for file in files:
                if file in data_files:
                    file_path = os.path.join(subdir, file)
                    with open(file_path, 'r') as f:
                        content = f.read()

                    if file == 'cellDisplacement' or file == 'U':
                    # Parse content to get the required data format
                        parsed_content = parse_file_content(content, file)
                    else:
                        parsed_content = parse_other_file(file, content)
                    
                    response_data.append({
                        'subfolder': os.path.relpath(subdir, project_base),
                        'filename': file,
                        'content': parsed_content
                    })

        if not response_data:
            print("No data files found")
            return jsonify({"message": "No data files found"}), 200

        return jsonify(response_data), 200

def parse_file_content(content, filename):
    probes = {}
    
    # Split the content into lines
    lines = content.splitlines()
 
    # Parse the probe locations
    for line in lines:
        if line.startswith("# Probe"):
            match = re.match(r"# Probe (\d+) \(([-\d.]+) ([-\d.]+) ([-\d.]+)\)", line)
            if match:
                probe_id = f"Probe {match.group(1)}"
                location = [float(match.group(2)), float(match.group(3)), float(match.group(4))]
                probes[probe_id] = {'Location': location, 'Data': {}}
    
    # Find the header line and the starting index for time values
    header_line_index = None
    for i, line in enumerate(lines):
        if "Time" in line.strip():
            header_line_index = i
            break
    
    if header_line_index is None:
        raise ValueError("Header line not found")
    
    # Parse the header line
    header_line = lines[header_line_index].strip().split()
    
    # Parse the time values from the line following the header
    for line in lines[header_line_index + 1:]:
        if line.startswith("#") or line.strip() == '':
            continue
        values = line.strip().split()
        time = values[0]
        coord_values = values[1:]
        
        final_coords = []
        for i in range(0, len(coord_values), 3):
            # Remove parentheses and convert strings to integers
            list_coordinates  = [float(coord_values[i].strip('()')), float(coord_values[i+1].strip('()')), float(coord_values[i+2].strip('()'))]
            final_coords.append(list_coordinates)
        
        for probe_id in probes:
            index = int(probe_id.split()[1])
            probes[probe_id]['Data'][time] = final_coords[index]
    
    # Construct the final output format
    probe_indices = tuple(int(probe.split()[1]) for probe in probes.keys())
    result = {
        'Name of File': filename,
        'Probe Indices': probe_indices,
        'Data': probes
    }
    
    return result

def fetch_feb_file_from_database(url):
    try:
        
        # Make the GET request
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
        
        # Save response content as JSON
        feb_data = response.json()
        return feb_data
    
    except requests.exceptions.RequestException as e:
        print(f"Error occurred: {e}")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON. Ensure the API returns a valid JSON.")
        return None
    
def fetch_file_from_database(file_url: str) -> bytes:
    try:
        response = requests.get(file_url, timeout=10)

        # Check if the request was successful
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch file from URL: {file_url}. HTTP Status: {response.status_code}")

        # Return the binary content of the file
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching file from URL: {file_url}. Error: {e}")
        raise

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response

def process_userid_for_folder_name(userid: str):
    return userid

app.register_blueprint(backend_routes, url_prefix=INSTANCE_NAME)

if __name__ == '__main__':  
    app.run(host='0.0.0.0', port=int(os.getenv('PORT')), debug=True, use_reloader = False)