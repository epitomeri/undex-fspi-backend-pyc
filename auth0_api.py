from flask import Blueprint, request
import json, requests
from requests.exceptions import RequestException, HTTPError, URLRequired
import http.client
from dotenv import load_dotenv
import os
import json

load_dotenv()
auth0_api = Blueprint('auth0_api', __name__)



@auth0_api.route('/roles', methods=['POST'])
def get_roles():

    
    
    user_id = json.loads(request.data)['user_id']

    #return "[{\"id\":\"rol_7e6WaqZDJK36HaJp1\",\"name\":\"Admin\",\"description\":\"Administrator role\",\"global\":true},{\"id\":\"rol_0987654321\",\"name\":\"User\",\"description\":\"User role\",\"global\":false}]"
    
    
    
    #user_id = 'google-oauth2|112059094626463487825'

    url = f'https://{os.getenv('AUTH0_DOMAIN')}/oauth/token'

    payload = {
        'client_id': os.getenv('AUTH0_CLIENT_ID'), 
        'client_secret': os.getenv('AUTH0_CLIENT_SECRET'), 
        'audience': f'https://{os.getenv("AUTH0_DOMAIN")}/api/v2/', 
        'grant_type': 'client_credentials'
    }
    
    print(os.getenv('AUTH0_CLIENT_SECRET'))

    data = requests.post(f'https://{os.getenv("AUTH0_DOMAIN")}/oauth/token', json=payload)



    access_token = json.loads(data.text)['access_token']

    headers = { 'authorization': "Bearer " + access_token }

    url = f'https://{os.getenv("AUTH0_DOMAIN")}/api/v2/users/' + user_id + "/roles"
    data = requests.get(url, headers=headers)

    print(data.text)
    return data.text



