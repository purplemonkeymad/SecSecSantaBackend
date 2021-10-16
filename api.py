# Api for a santa "game" for assigning people and ideas automatically as we can't use a hat.


import os
import traceback
# for REST like api
import json
from types import TracebackType
# flask to provide http layer
from flask import Flask, request, Response
# cheap keygen
import string
import random

# localdb

import database
import santalogic
import SantaErrors

app = Flask(__name__)

# db setup

# helper functions

# keygen for secrets
password_pool = list( string.ascii_letters + string.digits )
def new_password(length=8):
    temp_pass = random.choices(password_pool,k=length)
    return ''.join(temp_pass)

# get true table name
def true_tablename(tablename):
    if os.environ.get('IS_PROD',0) == 1:
        table_prefix = "prod"
    else:
        table_prefix = "dev"
    realm_name = "santa"
    return "{}_{}_{}".format(table_prefix,realm_name,tablename)

# wrapper for sending error messages
def json_error(message,internal_message=''):
    """Generate an error object for api return, and log the error.
    """
    result = {
        "status": 'error',
        "statusdetail": message
    }
    if (internal_message == ''):
        internal_message = message
    print("{ip},{agent},{url},{method},{error}".format(ip=request.remote_addr, url=request.url, agent=request.user_agent, method=request.method, error=internal_message))
    resp = Response(json.dumps(result))
    resp.headers['Access-Control-Allow-Origin'] = os.environ.get('XSS-Origin','*')
    resp.headers['Content-Type'] = 'application/json'
    return resp

# return data with success code
def json_ok(data_dict):
    print("{ip},{agent},{url},{method},{error}".format(ip=request.remote_addr, url=request.url, agent=request.user_agent, method=request.method, error='ok'))
    data_dict['status'] = 'ok'
    resp = Response(json.dumps(data_dict))
    resp.headers['Access-Control-Allow-Origin'] = os.environ.get('XSS-Origin','*')
    resp.headers['Content-Type'] = 'application/json'
    return resp

def exception_as_string(exception) -> str:
    return traceback.format_exception(etype=type(exception), value=exception, tb=exception.__traceback__)

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
        try: 
            game_result = santalogic.get_game(request.args.get('code'))
            # id is internal so we should remove it from a public response.
            if 'id' in game_result:
                del game_result['id']
            return json_ok( game_result )
        except Exception as e:
            return json_error(str(e))
    # post to update a game status.
    if request.method == 'POST':
        try:
            post_data = request.get_json(force=True)
        except:
            return json_error("invalid json data.")
        if len(post_data) == 0:
            return json_error("No Data sent in request")
        try:
            if 'state' in post_data:
                if not 'secret' in post_data:
                    return json_error("need secret to modify game")
                if not 'code' in post_data:
                    return json_error("need code to modify game")

                try:
                    santalogic.update_game_state(post_data['code'],post_data['secret'],post_data['state'])
                    return json_ok({})
                except SantaErrors.GameChangeStateError as e:
                    return json_error(str(e))
                except SantaErrors.GameStateError as e:
                    return json_error("Internal State Error","Game State issue: {game} , {exception}".format(exception=str(e),game=post_data['code']))
                except Exception as e:
                    return json_error("Internal Error","Internal error on state change {}".format(exception_as_string(e)))

            elif 'auth' in post_data:
                # not making a change just want to authenticate
                if not 'secret' in post_data:
                    return json_error("need secret to authenticate")
                if not 'code' in post_data:
                    return json_error("need code to modify game")

                # get info:
                try:
                    results = database.get_game_sum(post_data['code'],post_data['secret'])
                    if len(results) == 0:
                        return json_error("Not found, or bad secret.")
                    
                    return json_ok(results[0])
                except Exception as e:
                    return json_error("failed to get game","Error getting game: {}".format(exception_as_string(e)))
            else:
                return json_error("no update key specified")
        except KeyError as e:
            return json_error("missing key: {}".format(e.args[0]))
        except Exception as e:
            return json_error("Internal Error","Internal error on game: {}".format(exception_as_string(e)))
    
    # we shouldn't get here, but return a message just incase we do
    return json_error("No sure what to do")

# submit ideas
# submit ideas for a game to allow for the draw.
# POST
#    {"code":<gamepubcode>,"idea":<ideatext>}
@app.route('/idea', methods=['POST','GET'])
def idea():
    if request.method == 'POST':
        # this is to add new ideas/suggestions to the group.
        try:
            try:
                post_data = request.get_json(force=True)
            except:
                return json_error("POST data was not json or malformed.")
            
            required_field = ['code','idea']
            if all(property in post_data for property in required_field):
                try:
                    database.new_idea(post_data['code'],post_data['idea'])
                    return json_ok( {} )
                except FileNotFoundError as e:
                    return json_error(str(e))
                except Exception as e:
                    return json_error("Error adding idea","Idea Error: {}".format(exception_as_string(e)))

        except:
            return json_error("Internal Error.","Idea POST error: {}".format(exception_as_string(e)))
    if request.method == 'GET':
        # this is to retrive the left over list.
        # not sure that it makes sense to restrict this to creators.
        get_code = request.args.get('code')
        try: 
            game_result = santalogic.get_game(get_code)
        except Exception as e:
            return json_error(str(e))

        # test if group is "rolled"
        if game_result['state'] == 1:
            try:
                idea_results = database.get_idea({
                    'game': game_result['id'],
                    'userid': -1,
                },properties=['idea'])

                if len(idea_results) == 0:
                    return json_ok({'ideas':['All ideas were used!']})

                return json_ok({'ideas':[ x['idea'] for x in idea_results]})
            except Exception as e:
                return json_error("Error getting ideas.","Error getting ideas: {}".format(str(e)))
        
        # state is not 1
        else:
            return json_error("Group has not been rolled yet, nothing to get.")
    return json_error("Not sure what to do.")

# user register and game results
@app.route('/user',methods=['POST','GET'])
def user():
    # post is considered registering for a game
    #
    # POST /user
    #     {"code":<gamecode>,"name":<yourname>}
    if request.method == 'POST':
        try:
            try:
                post_data = request.get_json(force=True)
            except:
                return json_error("POST data was not json or malformed.")
            if all (property in post_data for property in ('name','code')):
                try:
                    database.join_game(post_data['name'],post_data['code'])
                    return json_ok ({})
                except FileExistsError as e:
                    return json_error("{}".format(str(e)))
                except Exception as e:
                    return json_error("Internal error occurred","Register Error: {}".format(exception_as_string(e)))
            else:
                return json_error("Name and code is required to register.")
        except Exception as e:
            return json_error("Internal Error Has Occurred.","Internal Error: {}".format(exception_as_string(e)))
    # get considered getting your results
    #
    # GET /user?code=<gamecode>&name=<name>
    #
    if request.method == 'GET':
        get_code = request.args.get('code')
        get_name = request.args.get('name')
        try: 
            game_result = santalogic.get_game(get_code)
        except Exception as e:
            return json_error(str(e))
        
        # 0 = open
        if game_result['state'] == 0:
            return json_error("Santas not yet assigned")
        
        # 1 = run
        if game_result['state'] == 1:
            # get santa info
            try:
                santa_data = database.get_user_giftee(get_name,game_result['id'])[0]
                if len(santa_data) == 0:
                    return json_error("Name or Giftee not found.")
            except Exception as e:
                return json_error("failed to get giftee information","Failed to get giftee information: {}".format(str(e)))

            # get idea list
            try:
                idea_data = database.get_user_ideas(get_name,game_result['id'])
                if len(idea_data) == 0:
                    return json_error("Name or Ideas not found.")
            except Exception as e:
                return json_error("failed to get your ideas","Failed to get ideas: {}".format(str(e)))

            idea_list = [x['idea'] for x in idea_data]

            return json_ok({
                'name': santa_data['name'],
                'giftee': santa_data['giftee'],
                'ideas': idea_list
            })
        # 2 = closed
        if game_result['state'] == 2:
            return json_error("group is closed")

        return json_error("Not implemented")
    # we shouldn't get here, but return a message just incase we do
    return json_error("No sure what to do")

# admin endpoints

# get a list of users in your game
# POST /list_user
#   {"code":<gamecode>,"secret":<gamesecret>}
#
@app.route('/list_user',methods=['POST'])
def list_user():
    try:
        post_data = request.get_json(force=True)
        if not 'code' in post_data:
            return json_error("Parameter 'code' is missing.")
        get_code = post_data['code']
        if not 'secret' in post_data:
            return json_error("Parameter 'secret' is missing.")
        get_secret = post_data['secret']
        if len(get_code) == 0 or len(get_secret) == 0:
            return json_error("Parameters 'code' and 'secret' cannot be empty.")
        try:
            user_list = database.get_users_in_game(get_code,get_secret,['name'])
            if len(user_list) == 0:
                return json_error("No results, or code or secret is wrong.")

            # convert to list
            flat_list = [user['name'] for user in user_list]           
            return json_ok({'users': flat_list})
        except Exception as e:
            return json_error("Unable to retrive user list.")
    except Exception as e:
        return json_error("Internal Error")

# create a new group/game
# POST
#    {"name":<gameDisplayName>}
@app.route('/new', methods=['POST'])
def new():
    try:
        try:
            post_data = request.get_json(force=True)
        except:
            return json_error("POST data was not json or malformed.")
        if 'name' in post_data:
            if len(post_data['name']) > 0:
                try:
                    game_sig = santalogic.create_game(post_data['name'])
                    if len(game_sig) == 0:
                        return json_error("No game returned")
                    else:
                        return json_ok( game_sig )
                except Exception as e:
                    return json_error( "Unable to generate unique game, please try again.",internal_message="New Failed: {}".format(exception_as_string(e)))
            else:
                json_error( "Game name must not be empty." )
        else:
            # no name in data
            return json_error( "'name' is a required value." )
    except Exception as e:
        return json_error("An Internal error occurred",internal_message="Uncaught Exception: {}".format(exception_as_string(e)))


# List games in the database, admin only
# needs post for authentication
# POST
#   {"admin_key": <globalsecret>}

@app.route('/get_games',methods=['POST'])
def get_games():
    """ API endpoint, list all games.
    """
    try:
        try:
            post_data = request.get_json(force=True)
        except:
            return json_error("Post Data malformed")
        # check we have required keys
        required_keys = ['admin_key']
        missing_keys = [x for x in required_keys if x not in post_data]
        if (len(missing_keys) > 0):
            return json_error("","A required Key is missing {}".format(missing_keys))
        else:
            if 'view' in post_data:
                ## prebuild views
                if post_data['view'] == 'open':
                    gamelist = database.get_all_open_games(post_data['admin_key'])
                elif post_data['view'] == 'complete':
                    gamelist = database.get_all_complete_games(post_data['admin_key'])
                elif post_data['view'] == 'closed':
                    gamelist = database.get_all_closed_games(post_data['admin_key'])
                else:
                    return json_error("","Unknown view: {}".format(post_data['view']))
            else:
                gamelist = database.get_all_games(post_data['admin_key'])
            return json_ok({'gamelist':gamelist})
    except Exception as e:
        return json_error("",internal_message="Get_Games Error: {}".format(str(e)))

# reset/create db
# resets the databases, it's important that you keep the globalsecret safe and long.
# POST
#    {"admin_key": <globalsecret>}
@app.route('/reset', methods=['POST'])
def reset():
    # clear and create a new db set
    try:
        try:
            post_data = request.get_json(force=True)
        except Exception as e:
            return json_error("Post Data malformed.")
        if 'admin_key' in post_data:
            reset_result = database.reset_all_tables(post_data['admin_key'])
            return json_ok( reset_result )
        else:
            return json_error("",internal_message="Opportunistic reset attempt")
    except Exception as e:
        return json_error("",internal_message="Reset Error: {}".format(exception_as_string(e)))
    # due to the nature of the interface no error messages are currently returned.
    return json_error("Not Implemented")

# create/update database schema
# POST
#    {"admin_key": <globalsecret>}
@app.route('/init_db_tables', methods=['POST'])
def init_db_tables():
    try:
        try:
            post_data = request.get_json(force=True)
        except Exception as e:
            return json_error("Post Data malformed.")
        if 'admin_key' in post_data:
            init_result = database.init_tables(post_data['admin_key'])
            return json_ok( init_result )
        else:
            return json_error("",internal_message="Opportunistic init attempt")
    except Exception as e:
        return json_error("",internal_message="Init Error: {}".format(exception_as_string(e)))
    # due to the nature of the interface no error messages are currently returned.
    return json_error("Not Implemented")


#########################
# Login endpoints
#########################

# email registration
@app.route('/auth/register',methods=['POST'])
def auth_register():
    """
    API endpoint for email sign-up
    """
    try:
        try:
            post_data = request.get_json(force=True)
        except Exception as e:
            return json_error("Post Data malformed.")
        # check we have required keys
        required_keys = ['email','name']
        missing_keys = [x for x in required_keys if x not in post_data]
        if (len(missing_keys) > 0):
            return json_error("A required Key is missing {}".format(missing_keys))
        
        # try registration
        try:
            trim_name = post_data['name'].strip()
            trim_email = post_data['email'].strip()

            result = santalogic.register_new_user(trim_email,trim_name)
            if len(result) == 0:
                return json_error("Unable to register.",internal_message="Registration Failure: no results from function.")
            return json_ok(result)
        except SantaErrors.SessionError as e:
            return json_error("Unable to register {}".format(str(e)))
        except Exception as e:
            return json_error("Unable to register, internal error.","Registration Error: {}".format(exception_as_string(e)))
    except Exception as e:
        return json_error("Internal Error",internal_message="Registration Error: {}".format(exception_as_string(e)))

# email registration
@app.route('/auth/new_session',methods=['POST'])
def auth_new_session():
    """
    API endpoint for starting a sign in
    """
    try:
        try:
            post_data = request.get_json(force=True)
        except Exception as e:
            return json_error("Post Data malformed.")
        # check we have required keys
        required_keys = ['email']
        missing_keys = [x for x in required_keys if x not in post_data]
        if (len(missing_keys) > 0):
            return json_error("","A required Key is missing {}".format(missing_keys))
        
        # try registration
        try:
            trim_email = post_data['email'].strip()

            result = santalogic.new_session(trim_email)
            if len(result) == 0:
                return json_error("Unable to sign-in.",internal_message="New Session Failure: no results from function.")
            return json_ok(result[0])
        except SantaErrors.SessionError as e:
            return json_error("Unable to sign-in {}".format(str(e)))
        except Exception as e:
            return json_error("unable to sign-in, internal error.","New Session Failure: {}".format(exception_as_string(e)))
    except Exception as e:
        return json_error("Internal Error",internal_message="New Session Error: {}".format(exception_as_string(e)))
    

#########################
# Init
#########################

# For dev local runs, start flask in python process.
if __name__ == '__main__':
    port = int(os.environ.get('PORT',5000))
    try: 
        from waitress import serve
        print("using waitress as server.")
        serve(app, host="0.0.0.0", port=port)
    except ImportError as e:
        print("waitress not found using flask as server.")
        app.run(host='0.0.0.0', port=port)