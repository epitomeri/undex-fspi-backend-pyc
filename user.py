import re
from turtle import up
from flask import Blueprint, request, jsonify, make_response
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


user_routes = Blueprint('user', __name__)

uri = os.getenv('DB_URI')



@user_routes.route('/checkstatus', methods=['GET', 'OPTIONS']) # type: ignore
def handle_checkstatus():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':

        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        users = db['Users']
        
        params = request.args
        email = params.get('email')
        user = users.find_one({'email': email})

        client.close()

        if user:
            return jsonify({
                'status': user['status'], 
                'privileges': user['privileges'],
                'verified': user['verified']
            }), 200
        else:
            return jsonify({'status': 'invalid'}), 404
        
    
@user_routes.route('/projects', methods=['GET', 'OPTIONS']) # type: ignore
def handle_projects():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        projects = db['Projects']

        params = request.args
        email = params.get('email')
        user_projects = projects.find({'email': email})

        project_list = []
        for project in user_projects:
            del project['_id']
            project_list.append(project)

        client.close()

        return jsonify(project_list), 200



@user_routes.route('/project', methods=['GET', 'OPTIONS']) # type: ignore
def handle_project():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':

        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        projects = db['Projects']

        params = request.args
        project_id = params.get('id')
        project = projects.find_one({'id': project_id})

        client.close()

        if project:
            del project['_id']
            return jsonify(project), 200
        else:
            return jsonify({'status': 'invalid'}), 404
        

@user_routes.route('/createproject', methods=['POST', 'OPTIONS']) # type: ignore
def handle_createproject():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':

        if (request.json == None):
            return jsonify({'status': 'invalid'}), 404
        
        solvers = request.json['solvers']

        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        projects = db['Projects']


        params = request.json

        solvers = params['solvers']
        print(solvers)
        status = {}
        if ("undex" in solvers):
            solvers.remove("undex")
            status = {
                "Hydrodynamics": True,
                "Biomechanics": True,
                "Physiology": True,
                "Coupling": True
            }
        else:
            status = {key: True for key in solvers}


        project_id = str(uuid.uuid4()).replace('-', '')
        project = {
            'id': project_id,
            'name': "New Project",
            'email': params['email'],
            'lastModified': datetime.now().isoformat(),
            'createdAt': datetime.now().isoformat(),
            'status': status
        }

        projects.insert_one(project)
        del project['_id']
        client.close()

        return jsonify(project), 200
        

@user_routes.route('/deleteproject', methods=['POST', 'OPTIONS']) # type: ignore
def handle_deleteproject():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':

        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        projects = db['Projects']

        if (request.json == None):
            return jsonify({'status': 'invalid'}), 404
        

        params = request.json
        project_id = params['projectId']
        projects.delete_one({'id': project_id})

        client.close()

        return jsonify({'status': 'success'}), 200
    

@user_routes.route('/updateproject', methods=['PUT', 'OPTIONS']) # type: ignore
def handle_updateproject():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'PUT':

        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        projects = db['Projects']

        if (request.json == None):
            return jsonify({'status': 'invalid'}), 404

        params = request.json
        project_id = params['projectId']
        updated_project = params['project']
        project = projects.find_one({'id': project_id})


        if project:
            project['name'] = updated_project['name']
            project['status'] = updated_project['status']
            project['lastModified'] = datetime.now().isoformat()
            projects.update_one({'id': project_id}, {'$set': project})
            del project['_id']
            client.close()
            return jsonify(project), 200
        else:
            client.close()
            return jsonify({'status': 'invalid'}), 404


@user_routes.route('/allusers', methods=['GET', 'OPTIONS']) # type: ignore
def handle_allusers():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':

        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        users = db['Users']

        params = request.args
        email = params.get('email')

        admin_user = users.find_one({'email': email})
        if not admin_user or admin_user['status'] != 'admin':
            client.close()
            return jsonify({'status': 'invalid'}), 404

        user_list = []
        for user in users.find({'status': {'$ne': 'admin'}}):
            del user['_id']
            user_list.append(user)

        client.close()

        return jsonify(user_list), 200


@user_routes.route('/updateusers', methods=['PUT', 'OPTIONS']) # type: ignore
def handle_updateusers():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'PUT':
    
    
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        users = db['Users']

        if (request.json == None):
            return jsonify({'status': 'invalid'}), 404

        params = request.json
        print(params['users'])
        for user in params['users']:
            privileges = user['privileges']
            requests = user['requests']
            verified = bool(user['verified'])

            for solver in privileges:
                if solver in requests:
                    requests.remove(solver)


            if user['status'] != 'admin':
                users.update_one({'email': user['email']}, 
                                 {'$set': {'privileges': privileges, 'verified': verified, 'requests': requests}})
                
        client.close()
        


        return jsonify({'status': 'success'}), 200


@user_routes.route('/solverRequest', methods=['POST', 'OPTIONS']) # type: ignore
def handle_solverRequest():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'POST':

        if (request.json == None):
            return jsonify({'status': 'invalid'}), 404
        
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        users = db['Users']

        params = request.json
        email = params['email']
        requests = params['requests']

        user = users.find_one({'email': email})

        if user:
            if (requests not in user['requests']):
                user['requests'] = [requests] + user['requests']
            users.update_one({'email': email}, {'$set': user})
            client.close()
            return jsonify({'status': 'success'}), 200
        else:
            client.close()
            return jsonify({'status': 'invalid'}), 404

@user_routes.route('/allprojects', methods=['GET', 'OPTIONS']) # type: ignore
def handle_allprojects():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':

        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        projects = db['Projects']

        project_list = []
        for project in projects.find():
            del project['_id']
            project_list.append(project)

        client.close()

        return jsonify(project_list), 200

""" @user_routes.route('/deleteusersprojects', methods=['DELETE', 'OPTIONS']) # type: ignore
def handle_deleteusersprojects():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'DELETE':

        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['Data']
        projects = db['Projects']

        params = request.args
        ids =     


        client.close()

        return jsonify({'status': 'success'}), 200
 """

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response

