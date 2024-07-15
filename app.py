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


@app.route("/blastfoamgen/<projectid>", methods=['POST', 'OPTIONS'])  # type: ignore
def handle_blastfoam(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        files = json.loads(request.form.get('files')) # type: ignore
        


        projects_dir = f'./projects/{projectid}'

        if not os.path.exists(projects_dir):
            os.makedirs(projects_dir)

        for case_name in request.files:
            
            mesh = request.files.get(case_name)
            if not os.path.exists(f'{projects_dir}/{mesh.name}/constant/geometry'): # type: ignore
                os.makedirs(f'{projects_dir}/{mesh.name}/constant/geometry') # type: ignore
            mesh.save(f'{projects_dir}/{mesh.name}/constant/geometry/{mesh.filename}') # type: ignore

        
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


        zip_file_name = os.path.basename(projects_dir) + '.zip'
        zip_file_path = os.path.join('./tmp', secure_filename(zip_file_name)) # type: ignore
        shutil.make_archive(base_name=zip_file_path.replace('.zip', ''), format='zip', root_dir=projects_dir)

        return send_file(zip_file_path, as_attachment=True)

@app.route('/febiogen/<projectid>', methods=['POST', 'OPTIONS']) # type: ignore
def handle_febiogen(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':

        directory_path = f'./projects/{projectid}/Solid'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        file = ''
        mesh_path = ''
        boundary_path = ''


        if not os.path.exists(f'./tmp/{projectid}/Solid/'):
            os.makedirs(f'./tmp/{projectid}/Solid/')

        if 'meshFile' in request.files:
            file = request.files['meshFile']
            file.save(f'./tmp/{projectid}/Solid/{file.filename}')
            mesh_path = f'./tmp/{projectid}/Solid/{file.filename}'
        if 'boundaryConditionsFile' in request.files:
            file = request.files['boundaryConditionsFile']
            file.save(f'./tmp/{projectid}/Solid/{file.filename}')
            boundary_path = f'./tmp/{projectid}/Solid/{file.filename}'

        solver_case_json = request.form.get('solverCase')
        data = json.loads(solver_case_json) # type: ignore
        

        generator = FebioConfigGenerator()
        

        output_file_path = generator.generate_xml(data, projectid, mesh_path, boundary_path)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)

        

        ScriptGen.gen_clean_script(projectid)
        ScriptGen.gen_solid_script(projectid)
        return send_from_directory(directory, filename, as_attachment=True) 

@app.route('/pulsegen/<projectid>', methods=['POST', 'OPTIONS']) # type: ignore
def handle_pulsegen(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()

        directory_path = f'./projects/{projectid}/Physiology'
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        if not os.path.exists(f'./tmp/{projectid}/Physiology/'):
            os.makedirs(f'./tmp/{projectid}/Physiology/')

        print('data is ', data)

        generator = PulseConfigGenerator()

        output_file_path = generator.generate_py_script(data, projectid)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)

        return send_from_directory(directory, filename, as_attachment=True)

@app.route('/precicegen/<projectid>', methods=['POST', 'OPTIONS']) # type: ignore
def handle_precice(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()

        generator = PreCICEConfigGenerator()

        output_file_path = generator.generate_xml(data, projectid)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)

        format_and_overwrite_xml_file(output_file_path)


        ScriptGen.gen_clean_script(projectid)
        return send_from_directory(directory, filename, as_attachment=True)
    
@app.route('/febio/<projectid>', methods=['POST', 'OPTIONS']) # type: ignore
def handle_febio(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part in the request', 400

        file = request.files['file']

        if file.filename == '':
            return 'No selected file', 400

        if file:
            directory_path = f'./projects/{projectid}/Solid'
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


            ScriptGen.gen_solid_script(projectid)
            return 'File uploaded successfully', 200
    

@app.route("/displacementgraph/<projectid>", methods=['GET', 'OPTIONS']) # type: ignore
def handle_displacement_graph(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        project_base_path = f'./projects/{projectid}'
        validation_path = f'{project_base_path}/validation'

        if not os.path.exists(validation_path):
            os.makedirs(validation_path)
            return 'Validation folder not found', 404

        displacement_graph_path = f'{project_base_path}/validation/blastfoam_displacement.png'

        if not os.path.exists(displacement_graph_path):
            return 'Graph not found', 404
        
        subprocess.run(['python3', project_base_path + "/validation/plot-blastfoam-cell-disp-febio-disp.py"])

        return send_file(displacement_graph_path, as_attachment=True)



@app.route('/graphfiles/<projectid>', methods=['GET', 'OPTIONS'])
def handle_getgraphfiles(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        project_base = f'./projects/{projectid}'
        displacement_graph_path = f'{project_base}/validation/blastfoam_displacement.png'
        physiology_graph_path = f'{os.getenv(
            "PULSE_INSTALL_DIR"
        )}/validation/Physiology/pulseresults.csv'


        graph_files = {
            "Displacement Response": "",
            "Pulse Graph": "",
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
                        if (file == 'pulseresults.csv'):
                            graph_files["Pulse Graph"] = f'{folder}/{file}'
                        else:
                            file_path = os.path.join(folder_path, file)
                            # Getting the path relative to project_base
                            relative_path = os.path.relpath(file_path, project_base)
                            graph_files[relative_path] = relative_path
    
    return jsonify(graph_files), 200


@app.route('/graphfile/<projectid>/', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getgraphfile(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        graphfilename = request.args.get('name') 
        if (".csv" not in graphfilename): # type: ignore
            return "Invalid file type", 400
        file_path = f'./projects/{projectid}/{graphfilename}'
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


@app.route('/raw/<projectid>/', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getrawgraphfile(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        graphfilename = request.args.get('name')
        addon = request.args.get('add')
        file_path = f'./projects/{projectid}/{graphfilename}'
        if (addon == "pulseInstall"):
            file_path = f'{os.getenv("PULSE_INSTALL_DIR")}/{graphfilename}'
        
        try:
            with open(file_path, mode='r', newline='') as file:
                reader = csv.reader(file)
                selected_lines = []
                for i, line in enumerate(reader):

                    if i % 50 == 0:
                        print(i, line[0])
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


@app.route('/logfiles/<projectid>', methods=['GET']) # type: ignore
def handle_getlogfiles(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        project_base = f'./projects/{projectid}'

        if not os.path.exists(project_base):
            os.makedirs(project_base)
    

        log_files = {
            
        }



        xml_config_path = f'{project_base}/precice-config.xml'
        log_file_name = ""

        enabled = False
        lfm = None

        if os.path.exists(xml_config_path):
            
            enabled, lfm = get_log_enabled(xml_config_path)
            log_file_name = lfm if lfm is not None else log_file_name

        for raw_case in os.listdir(project_base):
            if raw_case != "precice-run":
                case_path = os.path.join(project_base, raw_case)
                if os.path.isdir(case_path) and raw_case != 'validation':
                    log_files[raw_case] = []
                if(os.path.isdir(case_path)) and raw_case != 'validation':

                    print(os.listdir(case_path))
                    
                    for item in os.listdir(case_path):
                        if item.endswith('.log') or item.startswith('log.'):
                            log_files[raw_case].append(item)


                    if raw_case not in log_files.keys():
                        log_files[raw_case] = []
                        log_files[raw_case] = [f for f in os.listdir(case_path) if f.endswith('.log')]

                    if len(log_files[raw_case]) == 0:
                        log_files.pop(raw_case)
                
                    if enabled == 'True': # type: ignore
                        log_files[raw_case].append(log_file_name)


        print(log_files)
        return jsonify(log_files), 200


@app.route('/logfile/<projectid>/<casename>/<logfilename>', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getlogfile(projectid, casename, logfilename):

    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        file_path = f'./projects/{projectid}/{casename}/{logfilename}'

        return Response(stream_with_context(tail_file(file_path)), mimetype='text/event-stream')
        
        

@app.route('/projects/<projectid>', methods=['PATCH', 'OPTIONS']) # type: ignore
def handle_patch_project(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'PATCH':
        data = request.get_json()

        project_base = f'./projects/{projectid}'
        if not os.path.exists(project_base):
            os.makedirs(project_base)

        if 'projectName' in data:
            os.rename(project_base, f'./projects/{data["projectName"]}')

        return 'Project updated', 200


@app.route('/run/<projectid>', methods=['GET'])  # type: ignore
def handle_run(projectid):
    if request.method == 'GET':
        print("running" + projectid)
        project_base_path = f'./projects/{projectid}'
        ScriptGen.gen_run_script(projectid)

        # Check for the existence of a directory starting with 'Solid'
        solid_dir = next((d for d in os.listdir(project_base_path) if os.path.isdir(os.path.join(project_base_path, d)) and d.startswith('Solid')), None)
        if solid_dir:
            ScriptGen.gen_solid_script(projectid)

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




def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, debug=True)
