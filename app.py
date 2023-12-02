import re
from flask import Flask, request, jsonify, make_response, send_from_directory, send_file
from flask_cors import CORS
import os
import shutil
from werkzeug.utils import secure_filename
import zipfile
import subprocess

from genXML import PreCICEConfigGenerator
from genBlastFOAM import BlastFoamGenerator
from scriptGen import ScriptGen

app = Flask(__name__)
CORS(app)


@app.before_request
def before_request():
    if not os.path.exists('./projects'):
        os.makedirs('./projects')

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

        ScriptGen.gen_clean_script(projectid)
        ScriptGen.gen_validation(projectid)
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


            if file.filename.endswith('.zip'): # type: ignore
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(directory_path)
                os.remove(file_path)  

            ScriptGen.gen_solid_script(projectid)
            return 'File uploaded successfully', 200
    

@app.route('/run/<projectid>', methods=['GET']) # type: ignore
def handle_run(projectid):
    if request.method == 'GET':
        project_base_path = f'./projects/{projectid}'
        ScriptGen.gen_run_script(projectid)

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
