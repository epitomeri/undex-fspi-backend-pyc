from math import log
from flask import Flask, request, jsonify, make_response, send_from_directory, send_file, Response, stream_with_context
from flask_cors import CORS
import os
import shutil
from werkzeug.utils import secure_filename
import zipfile
import subprocess
import xml.etree.ElementTree as ET

from genXML import PreCICEConfigGenerator
from genBlastFOAM import BlastFoamGenerator
from scriptGen import ScriptGen

from utils.formatXML import format_and_overwrite_xml_file
from utils.fileParse import get_log_enabled, tail_file

app = Flask(__name__)
cors = CORS(app, resource={
    r"/*":{
        "origins":"*"
    }
})


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
        data = request.get_json()
        
        blastFoamGen = BlastFoamGenerator(data, projectid)
        output_folder_path = blastFoamGen.generate_all()

        zip_file_name = os.path.basename(output_folder_path) + '.zip'
        zip_file_path = os.path.join('./tmp', secure_filename(zip_file_name)) # type: ignore
        shutil.make_archive(base_name=zip_file_path.replace('.zip', ''), format='zip', root_dir=output_folder_path)

        ScriptGen.gen_clean_script(projectid)
        ScriptGen.gen_explosive_script(data, projectid)
        ScriptGen.gen_validation(projectid)
        return send_file(zip_file_path, as_attachment=True)

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
                case_path = os.path.join(project_base, raw_case)
                if(os.path.isdir(case_path)) and raw_case != 'validation':
                    
                    if os.path.isdir(case_path) and 'system' in os.listdir(case_path):
                        log_files[raw_case] = []
                        log_files[raw_case].append('decomposePar')
                        log_files[raw_case].append('rotateConservativeFields')
                        log_files[raw_case].append('blastFoam')
                    
                    if raw_case == "Solid":
                        log_files[raw_case] = []
                
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

        subprocess.run(['bash', f'{project_base_path}/Allclean'])
        subprocess.run(['bash', f'{project_base_path}/run'])

        return 'Simulation started', 200

@app.route('/test', methods=['GET', 'OPTIONS']) # type: ignore
def handle_test():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        return "Hello World!"

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, debug=True)
