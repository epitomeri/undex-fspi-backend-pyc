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

import user
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


@app.before_request
def before_request():
    if not os.path.exists('./projects'):
        os.makedirs('./projects')

@app.after_request
def handle_options(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"

    return response

def update_control_dict(caseid, projectid, blastfoam_folder, userid):
    """
    Updates the controlDict file in the specified blastfoam folder to change stopAt to noWriteNow.
    """
    control_dict_path = os.path.join('./projects', userid, 'projects', projectid, caseid, blastfoam_folder, 'system', 'controlDict')

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

@app.route("/update_control_dict/<caseid>/<projectid>/<userid>/<blastfoam_folder>", methods=['GET', 'POST', 'OPTIONS']) # type: ignore
def update_control_dict_endpoint(caseid, projectid, userid, blastfoam_folder):
    """
    API endpoint to update the controlDict file's stopAt value in the specified blastfoam folder.
    """
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()

    if request.method == 'POST' or request.method == 'GET':
        # Call the function to update controlDict
        userid = process_userid_for_folder_name(userid)
        result, status_code = update_control_dict(caseid, projectid, blastfoam_folder, userid)
        return jsonify(result), status_code

def get_public_ip():
    try:
        # Use an external service to get the public IP address
        response = requests.get('https://api.ipify.org?format=json')
        ip_data = response.json()
        return ip_data['ip']
    except requests.RequestException as e:
        return "Unable to retrieve public IP"

@app.route("/pvserver/<caseid>/<projectid>/<userid>", methods=['GET', 'POST', 'DELETE', 'OPTIONS']) # type: ignore
def manage_pvserver(caseid, projectid, userid):
    global pvserver_process

    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    
    # Start the server
    elif request.method == 'POST' or request.method == 'GET':
        if pvserver_process and pvserver_process.poll() is None:
            return jsonify({"error": "PVServer is already running."}), 409

        projects_dir = f'./projects/{userid}/{projectid}/{caseid}'

        if not os.path.exists(projects_dir):
            return jsonify({"error": f"Project directory '{projectid}' does not exist."}), 404

        try:
            # Execute the pvserver command in the specified project directory
            pvserver_process = subprocess.Popen(['pvserver'], cwd=projects_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Read the output line by line to capture the connection details
            port = None
            while True:
                output = pvserver_process.stdout.readline()
                if "Connection URL" in output:
                    # Extract the port number from the output
                    port = output.split(':')[-1].strip()
                    break

            if port is None:
                return jsonify({"error": "Failed to start pvserver and retrieve port information."}), 500

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

    # Stop the server
    elif request.method == 'DELETE':
        if pvserver_process and pvserver_process.poll() is None:
            try:
                # Terminate the pvserver process
                pvserver_process.terminate()
                pvserver_process.wait()
                pvserver_process = None
                return jsonify({"message": "PVServer stopped successfully."}), 200
            except Exception as e:
                return jsonify({"error": f"Failed to stop pvserver: {str(e)}"}), 500
        else:
            return jsonify({"error": "PVServer is not running."}), 400

@app.route("/blastfoamgen/<caseid>/<projectid>/<userid>", methods=['POST', 'OPTIONS'])  # type: ignore
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
            
            if not os.path.exists(f'{projects_dir}/{case_name}/constant/geometry'): # type: ignore
                os.makedirs(f'{projects_dir}/{case_name}/constant/geometry') # type: ignore
            mesh.save(f'{projects_dir}/{case_name}/constant/geometry/{mesh.filename}') # type: ignore

        
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

@app.route('/febiogen/<caseid>/<projectid>/<userid>', methods=['POST', 'OPTIONS']) # type: ignore
def handle_febiogen(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':

        userid = process_userid_for_folder_name(userid)
        directory_path = f'./projects/{userid}/{projectid}/{caseid}/solid-FEBio/Solid'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        file = ''
        mesh_path = None
        boundary_path = None


        if not os.path.exists(f'./tmp/{projectid}/Solid/'):
            os.makedirs(f'./tmp/{projectid}/Solid/')

        if 'meshFile' in request.files:
            file = request.files['meshFile']
            file.save(f'./tmp/{projectid}/Solid/{file.filename}')
            mesh_path = f'./tmp/{projectid}/Solid/{file.filename}'
        else:
            default_bc_file = './resources/mesh.feb'

            if os.path.exists(default_bc_file):
                mesh_path = default_bc_file
            # else:
            #     return jsonify({'error': 'Default mesh file not found.'}), 401

        if 'boundaryConditionsFile' in request.files:
            file = request.files['boundaryConditionsFile']
            file.save(f'./tmp/{projectid}/Solid/{file.filename}')
            boundary_path = f'./tmp/{projectid}/Solid/{file.filename}'
        else:
            default_bc_file = './resources/bcfile.txt'
            if os.path.exists(default_bc_file):
                boundary_path = default_bc_file
            # else:
            #     return jsonify({'error': 'Default bc file not found.'}), 401

        solver_case_json = request.form.get('solverCase')
        data = json.loads(solver_case_json) # type: ignore

        generator = FebioConfigGenerator()
        output_file_path = generator.generate_xml(data, userid, projectid, caseid)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)

        ScriptGen.gen_clean_script(projectid, userid, f"{caseid}/solid-FEBio")
        ScriptGen.gen_solid_script(projectid, userid, caseid)
        print(directory, filename)
        return send_from_directory(directory, filename, as_attachment=True) 

@app.route('/pulsegen/<caseid>/<projectid>/<userid>', methods=['POST', 'OPTIONS']) # type: ignore
def handle_pulsegen(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()

        userid = process_userid_for_folder_name(userid)
        directory_path = f'./projects/{userid}/{projectid}/{caseid}/Physiology'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        if not os.path.exists(f'./tmp/{projectid}/Physiology/'):
            os.makedirs(f'./tmp/{projectid}/Physiology/')

        print('data is ', data)

        generator = PulseConfigGenerator()

        output_file_path = generator.generate_py_script(data, userid, projectid, caseid)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)


        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isdir(item_path):
                if 'Allclean' in os.listdir(item_path):
                    os.chmod(os.path.join(item_path, 'Allclean'), 0o755)
                    subprocess.run(['bash', os.path.join(item_path, 'Allclean')])

        return send_from_directory(directory, filename, as_attachment=True)

@app.route('/precicegen/<caseid>/<projectid>/<userid>', methods=['POST', 'OPTIONS']) # type: ignore
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
    
@app.route('/febio/<caseid>/<projectid>/<userid>', methods=['POST', 'OPTIONS']) # type: ignore
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
    
@app.route("/displacementgraph/<caseid>/<projectid>/<userid>", methods=['GET', 'OPTIONS']) # type: ignore
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

@app.route('/graphfiles/<caseid>/<projectid>/<userid>', methods=['GET', 'OPTIONS'])
def handle_getgraphfiles(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        project_base = f'./projects/{userid}/{projectid}/{caseid}'
        displacement_graph_path = f'{project_base}/validation/blastfoam_displacement.png'
        physiology_graph_path = f'{os.getenv("PULSE_INSTALL_DIR")}/pulseresults.csv'

        
        graph_files = {
            "Displacement Response": "",
            "Pulse Graph": physiology_graph_path,
        }


        if not os.path.exists(displacement_graph_path):
            del graph_files["Displacement Response"]
        if not os.path.exists(physiology_graph_path):
            del graph_files["Pulse Graph"]
        
        
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

@app.route('/graphfile/<caseid>/<projectid>/<userid>', methods=['GET', 'OPTIONS']) # type: ignore
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

@app.route('/raw/<caseid>/<projectid>/<userid>', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getrawgraphfile(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        graphfilename = request.args.get('name')
        addon = request.args.get('add')
        userid = process_userid_for_folder_name(userid)
        file_path = f'./projects/{userid}/{projectid}/{caseid}/{graphfilename}'
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
            return "File not found1", 404
        except Exception as e:
            return f"An error occurred: {str(e)}", 500

@app.route('/logfiles/<caseid>/<projectid>/<userid>', methods=['GET']) # type: ignore
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

        for raw_case in os.listdir(project_base): # fluid-blastFOAM level
            print(raw_case)
            if raw_case != "precice-run":
                case_path = os.path.join(project_base, raw_case)
                if os.path.isdir(case_path) and raw_case != 'validation':
                    log_files[raw_case] = []

                    for item in os.listdir(case_path): # 0-case-1 level for fluid and log level for else
                        print("\t", item)
                        item_path = os.path.join(case_path, item)
                        
                        if raw_case == 'fluid-blastFOAM' and os.path.isdir(item_path):
                            log_files[f"{raw_case}:{item}"] = []
                            for blast_case in os.listdir(item_path): # logs in blast cases level.
                                blast_case_path = os.path.join(item_path, blast_case)
                                if os.path.isfile(blast_case_path) and (blast_case.endswith('.log') or blast_case.startswith('log.')):
                                    print("Adding:", blast_case)
                                    log_files[f"{raw_case}:{item}"].append(blast_case)
                                    print("\t\t", blast_case, "<-")
                                else:
                                    print("\t\t", blast_case)
                            if len(log_files[f"{raw_case}:{item}"]) == 0:
                                log_files.pop(f"{raw_case}:{item}")
                        
                        elif os.path.isfile(item_path) and (item.endswith('.log') or item.startswith('log.')):
                            print("Adding:", item)
                            log_files[raw_case].append(item)
                    
                    # Sort log files by last modified time
                    log_files[raw_case].sort(key=lambda f: os.path.getmtime(os.path.join(case_path, f)), reverse=True)
                    
                    if enabled == 'True':  # type: ignore
                        log_files[raw_case].append(log_file_name)

                    if len(log_files[raw_case]) == 0:
                        log_files.pop(raw_case)

        return jsonify(log_files), 200

@app.route('/logfile/<caseid>/<projectid>/<userid>/<casename>/<logfilename>', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getlogfile(caseid, projectid, userid, casename: str, logfilename):

    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        userid = process_userid_for_folder_name(userid)
        if ":" in casename:
            casename = casename.replace(":", "/")
        file_path = f'./projects/{userid}/{projectid}/{caseid}/{casename}/{logfilename}'

        print("THIS IS THE FILEPATH: ", file_path)

        return Response(stream_with_context(tail_file(file_path)), mimetype='text/event-stream')

@app.route('/download/<caseid>/<projectid>/<userid>', methods=['GET', 'OPTIONS']) # type: ignore
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


@app.route('/projects/<projectid>/<userid>', methods=['POST', 'OPTIONS']) # type: ignore
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

@app.route('/rename-simulation-case/<caseid>/<projectid>/<userid>', methods=['POST', 'OPTIONS']) # type: ignore
def handle_patch_simulation(caseid, projectid, userid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()
        userid = process_userid_for_folder_name(userid)
        simulation_base = f'./projects/{userid}/{projectid}/{caseid}'
        if not os.path.exists(simulation_base):
            os.makedirs(simulation_base)

        if 'caseName' in data:
            os.rename(simulation_base, f'./projects/{userid}/{projectid}/{data["caseName"]}')

        return {"message": 'Simulation Case Folder name updated'}, 200

@app.route('/rename-case/<caseid>/<simulationcaseid>/<projectid>/<userid>', methods=['POST', 'OPTIONS']) # type: ignore
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

@app.route('/deleteproject/<projectid>/<userid>', methods=['GET', 'OPTIONS']) # type: ignore
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

@app.route('/deleteCase/<projectid>/<caseid>/<userid>', methods=['GET', 'OPTIONS']) # type: ignore
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

@app.route('/run/<caseid>/<projectid>/<userid>', methods=['GET'])  # type: ignore
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

        subprocess.run(['bash', os.path.join(project_base_path, 'run.sh')])

        return 'Simulation started', 200

@app.route('/test', methods=['GET', 'OPTIONS']) # type: ignore
def handle_test1():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        return "Hello World!"


@app.route('/sendemail', methods=['POST'])
def send_email():

    event = json.loads(request.data)['event']
    msg = Message('A new user has attempted to sign up through the Simulation webapp app.', sender = 'aiformissiledefense@gmail.com', recipients = ['satish@epitomeri.com'])
    msg.body = f'New user has signed up\n{event["user"]["email"]}\nhttps://manage.auth0.com/dashboard/us/{os.getenv("AUTH0_NAME")}/users\nPlease send the user verification message: {os.getenv("BACKEND_URL")}/verify?email={event["user"]["email"]}'
    mail.send(msg)
    return "Message sent!"

@app.route('/verify', methods=['GET'])
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

@app.route("/blastfoam/data/<caseid>/<projectid>/<userid>/<caseName>", methods=['GET', 'OPTIONS'])  # type: ignore
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

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response

def process_userid_for_folder_name(userid: str):
    return userid

if __name__ == '__main__':  
    app.run(host='0.0.0.0', port=4009, debug=True, use_reloader = False)