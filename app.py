from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
import os

from genXML import PreCICEConfigGenerator
from genBlastFOAM import BlastFoamGenerator

app = Flask(__name__)
CORS(app)

@app.route("/blastfoamgen", methods=['POST', 'OPTIONS'])  # type: ignore
def handle_blastfoam():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()
        
        blastFoamGen = BlastFoamGenerator(data)
        blastFoamGen.generate_all()

        return "Not implemented yet"

@app.route('/precicegen', methods=['POST', 'OPTIONS']) # type: ignore
def handle_precice():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':
        data = request.get_json()

        generator = PreCICEConfigGenerator()

        output_file_path = generator.generate_xml(data)

        directory = os.path.dirname(output_file_path)
        filename = os.path.basename(output_file_path)

        return send_from_directory(directory, filename, as_attachment=True)

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, debug=True)
