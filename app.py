from math import log
from flask import Flask, request, jsonify, make_response, send_from_directory, send_file, Response, stream_with_context
from flask_cors import CORS
from flask_mail import Mail, Message
import os
import shutil
from werkzeug.utils import secure_filename
import zipfile
import subprocess
import xml.etree.ElementTree as ET
import json
from dotenv import load_dotenv

from auth0_api import auth0_api

from genXML import PreCICEConfigGenerator
from genBlastFOAM import BlastFoamGenerator
from genFebio import FebioConfigGenerator
from scriptGen import ScriptGen

from utils.formatXML import format_and_overwrite_xml_file
from utils.fileParse import get_log_enabled, tail_file

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
        displacement_graph_path = f'{project_base_path}/validation/blastfoam_displacement.png'

        if not os.path.exists(displacement_graph_path):
            return 'Graph not found', 404
        
        subprocess.run(['python3', project_base_path + "/validation/plot-blastfoam-cell-disp-febio-disp.py"])

        return send_file(displacement_graph_path, as_attachment=True)


@app.route('/graphfiles/<projectid>', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getgraphfiles(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        project_base = f'./projects/{projectid}'
        graph_files = {}


        if os.path.exists(project_base):
            for folder in os.listdir(project_base):
                folder_path = os.path.join(project_base, folder)
                if os.path.isdir(folder_path):
                    for file in os.listdir(folder_path):
                        if file.endswith('.csv'):
                            file_path = os.path.join(folder_path, file)
                            graph_files[file] = file_path
                
        
        
        return jsonify(graph_files), 200


@app.route('/logfiles/<projectid>', methods=['GET']) # type: ignore
def handle_getlogfiles(projectid):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        project_base = f'./projects/{projectid}'
    

        log_files = {
            
        }



        xml_config_path = f'{project_base}/precice-config.xml'
        log_file_name = ""

        if os.path.exists(xml_config_path):
            
            enabled, lfm = get_log_enabled(xml_config_path)
            log_file_name = lfm if lfm is not None else log_file_name

            for raw_case in os.listdir(project_base):
                if raw_case != "precice-run":
                    case_path = os.path.join(project_base, raw_case)
                    if(os.path.isdir(case_path)) and raw_case != 'validation':
                        
                        if os.path.isdir(case_path) and 'system' in os.listdir(case_path):
                            log_files[raw_case] = []
                            log_files[raw_case].append('log.blockMesh')
                            log_files[raw_case].append('log.snappyHexMesh')
                            log_files[raw_case].append('log.decomposePar')
                            log_files[raw_case].append('log.surfaceFeatures')
                            log_files[raw_case].append('log.rotateConservativeFields')
                            log_files[raw_case].append('log.blastFoam')

                        
                        if raw_case == "Solid":
                            log_files[raw_case] = []
                            log_files[raw_case].append('febio-precice.log')
                    
                        if enabled == 'True': # type: ignore
                            log_files[raw_case].append(log_file_name)
            
        return jsonify(log_files), 200


@app.route('/logfile/<projectid>/<casename>/<logfilename>', methods=['GET', 'OPTIONS']) # type: ignore
def handle_getlogfile(projectid, casename, logfilename):

    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        file_path = f'./projects/{projectid}/{casename}/{logfilename}'

        return Response(stream_with_context(tail_file(file_path)), mimetype='text/event-stream')
        
        """ project_base = f'./projects/{projectid}'

        cases = [f for f in os.listdir(project_base) if os.path.isdir(os.path.join(project_base, f))]
        cases.remove('validation')

        if(logfilename in cases):

            xml_config_path = f'{project_base}/precice-config.xml'
            _, case_log_filename = get_log_enabled(xml_config_path)

            
            case_log_path = f'{project_base}/{logfilename}/{case_log_filename}'
            return Response(stream_with_context(tail_file(case_log_path)), mimetype='text/event-stream')

        elif (logfilename == 'Biomechanics'):
            case_log_path = f'{project_base}/Solid/febio-precice.log'
            return Response(stream_with_context(tail_file(case_log_path)), mimetype='text/event-stream')

        else:
            case_log_path = f'{project_base}/log.{logfilename}'
            return Response(stream_with_context(tail_file(case_log_path)), mimetype='text/event-stream') """
        


@app.route('/run/<projectid>', methods=['GET']) # type: ignore
def handle_run(projectid):
    if request.method == 'GET':
        print("running" + projectid)
        project_base_path = f'./projects/{projectid}'
        ScriptGen.gen_run_script(projectid)

        ScriptGen.gen_solid_script(projectid)
        ScriptGen.gen_fluid_script(projectid)

        subprocess.run(['bash', f'{project_base_path}/Allclean'])
        subprocess.run(['bash', f'{project_base_path}/run.sh'])

        return 'Simulation started', 200

@app.route('/test', methods=['GET', 'OPTIONS']) # type: ignore
def handle_test():
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
