import os
# for REST like api
import json
# flask to provide http layer
from flask import Flask, request
# database
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor
# cheap keygen
import string
import random

app = Flask(__name__)

# db setup

urllib.parse.uses_netloc.append('postgres')
# heroku puts db info in this env
url = urllib.parse.urlparse(os.environ['DATABASE_URL'])
dbConn = psycopg2.connect( database=url.path[1:], user=url.username, password=url.password, host=url.hostname, port=url.port)
dbCursor = dbConn.cursor(cursor_factory=RealDictCursor)

# helper functions

# keygen for secrets
password_pool = list( string.ascii_letters + string.digits )
def new_password(length=8):
    temp_pass = random.choices(password_pool,k=length)
    return ''.join(temp_pass)

# get true table name
def true_tablename(tablename):
    if os.environ.get('IS_PROD',0):
        table_prefix = "prod"
    else:
        table_prefix = "dev"
    realm_name = "santa"
    return "{}_{}_{}".format(table_prefix,realm_name,tablename)

# wrapper for sending error messages
def json_error(message):
    result = {
        "status": 'Error',
        "statusdetail": message
    }
    return json.dumps(result)

# return data with success code
def json_ok(data_dict):
    data_dict['status'] = 'ok'
    return json.dumps(data_dict)

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
    # get for getting info about game
    if request.method == 'GET':
        get_code = request.args.get('code')
        if not get_code:
            return json_error('Property code is missing or empty.')
        query = "SELECT name,state FROM {} WHERE code = %(code)s;".format(true_tablename('games'))
        dbCursor.execute(query, {'code': get_code} )
        if dbCursor.rowcount == 0:
            return json_error("Not Found")
        try:
            db_game = dbCursor.fetchone()
        except:
            return json_error("Error fetching games")
        else:
            return json_ok(db_game)
    # post to update a game status.
    if request.method == 'POST':
        post_data = request.get_json(force=True)
        if len(post_data) == 0:
            return json_error("No Data sent in request")
        try:
            if 'state' in post_data:
                query = "UPDATE {} SET state = %(state)s WHERE secret = %(secret)s AND code = %(code)s;".format(true_tablename('games'))
                dbCursor.execute(query, {'state': post_data['state'], 'code': post_data['code'], 'secret': post_data['secret']} )
                if dbCursor.rowcount == 0:
                    dbConn.cancel()
                    return json_error("not found")
                else:
                    dbConn.commit()
                    return json_ok( {} )
        except KeyError as e:
            return json_error("missing key: {}".format(e.args[0]))
        return post_data
    
    # we shouldn't get here, but return a message just incase we do
    return json_error("No sure what to do")

# admin endpoints

@app.route('/new', methods=['POST'])
def new():
    try:
        post_data = request.get_json(force=True)
        if 'name' in post_data:
            # sql statements
            check_query = "SELECT name FROM {} Where code=%(pubkey)s;".format(true_tablename('games'))
            insert_query = "INSERT INTO {} VALUES(DEFAULT,%(name)s,%(privkey)s,%(pubkey)s,0);".format(true_tablename('games'))
            # generate keys
            pubkey = new_password(length=8)
            privkey = new_password(length=64)
            game_sig = {'name': post_data['name'], 'privkey': privkey, 'pubkey': pubkey}

            try:
                dbCursor.execute(check_query,  { 'pubkey': pubkey} )
                if dbCursor.rowcount == 0:
                    dbCursor.execute(insert_query,  game_sig)
                    dbConn.commit()
                    return json_ok( game_sig )
                else:
                    return json_error( "Unable to generate unique game, try again." )
            except Exception as e:
                print("sql error on /new: {}".format(e))
                return json_error("An internal error occurred.")
        else:
            # no name in data
            return json_error( "'name' is a required value." )
    except:
        return json_error("POST data was not json or malformed.")

# reset/create db
# resets the databases, it's important that you keep the globalsecret safe and long.
# POST
#    {"admin_key": <globalsecret>}
@app.route('/reset', methods=['POST'])
def reset():
    # clear and create a new db set
    try:
        post_data = request.get_json(force=True)
        if 'admin_key' in post_data:
            if post_data['admin_key'] == os.environ['AdminSecret']:
                drop_list = [
                    'drop table {};'.format(true_tablename('games'))
                ]
                create_list = [
                    'create table {} (id serial,name varchar(200),secret varchar(64),code varchar(8),state int);'.format(true_tablename('games'))
                ]
                for query in drop_list:
                    dbCursor.execute(query)
                for query in create_list:
                    dbCursor.execute(query)
                dbConn.commit()
                return json_ok( {} )
            else:
                return json_error("")
        else:
            return json_error("")
    except:
        return json_error("")
    # due to the nature of the interface no error messages are currently returned.
    return json_error("Not Implemented")


# For dev local runs, start flask in python process.
if __name__ == '__main__':
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port)