import os
import json
from flask import Flask, request
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# db setup

urllib.parse.uses_netloc.append('postgres')
# heroku puts db info in this env
url = urllib.parse.urlparse(os.environ['DATABASE_URL'])
dbConn = psycopg2.connect( database=url.path[1:], user=url.username, password=url.password, host=url.hostname, port=url.port)
dbCursor = dbConn.cursor(cursor_factory=RealDictCursor)

# helper functions

# wrapper for sending error messages
def json_error(message):
    result = {
        "status": 'Error',
        "statusdetail": message
    }
    return json.dumps(result)

# endpoints

# /game  :
# retrive the status of a game or set a status
# GET /game?name=<name>
#   Return details of the named game or an error mesage if it does not exist.
# POST /game
#    {name: <name>,secret: <key>,status: <0-3>}
#    Sets the game <name> to selected status, uses the secret to authenticate.
@app.route('/game', methods=['GET','POST'])
def game():
    if request.method == 'GET':
        get_code = request.args.get('code')
        if not get_code:
            return json_error('Property code is missing or empty.') 
    return 'hello'
# For dev local runs, start flask in python process.

if __name__ == '__main__':
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port)