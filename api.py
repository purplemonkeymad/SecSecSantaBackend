# Api for a santa "game" for assigning people and ideas automatically as we can't use a hat.

# SQL note:
#
# I'm using 2 "formats" for sql queries.  one is used by the sql connector so i used the other type
# to fill in table names. tables names use a fromat like: {basename} and values %(valuename)s
# sql queries should be .format ed when created so that they choose dev/prod as needed.

import os
# for REST like api
import json
# flask to provide http layer
from flask import Flask, request, Response
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
    if os.environ.get('IS_PROD',0) == 1:
        table_prefix = "prod"
    else:
        table_prefix = "dev"
    realm_name = "santa"
    return "{}_{}_{}".format(table_prefix,realm_name,tablename)

# wrapper for sending error messages
def json_error(message):
    result = {
        "status": 'error',
        "statusdetail": message
    }
    resp = Response(json.dumps(result))
    resp.headers['Access-Control-Allow-Origin'] = os.environ.get('XSS-Origin','*')
    resp.headers['Content-Type'] = 'application/json'
    return resp

# return data with success code
def json_ok(data_dict):
    data_dict['status'] = 'ok'
    resp = Response(json.dumps(data_dict))
    resp.headers['Access-Control-Allow-Origin'] = os.environ.get('XSS-Origin','*')
    resp.headers['Content-Type'] = 'application/json'
    return resp

# check a list into n length parts
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def run_game(id):
    # game has two parts, ideas, santas
    # each user is given another user to be santa of
    # each user is also given two unique ideas from the idea pool
    
    #all users
    user_query = "SELECT id,name,game FROM {users} WHERE game = %(gameid)s;".format(users=true_tablename('users'))
    dbCursor.execute(user_query,{'gameid':id})
    all_users = dbCursor.fetchall()
    if len(all_users) < 2:
        raise Exception("game requires at least 2 users to run.")

    # get ideas
    idea_query = "SELECT id,idea,game FROM {ideas} WHERE game = %(gameid)s;".format(ideas=true_tablename('ideas'))
    dbCursor.execute(idea_query,{'gameid':id})
    all_ideas = dbCursor.fetchall()
    if len(all_ideas) < len(all_users) * 2:
        raise Exception("game requires at least 2 ideas per user")

    # assing users to santa's
    random.shuffle(all_users)
    user_update_query = "UPDATE {users} SET santa = %(santa)s WHERE id = %(userid)s;".format(users=true_tablename('users'))
    try:
        last_user = all_users[-1]
        for user in all_users:
            dbCursor.execute(user_update_query,{'userid':user['id'], 'santa': last_user['id']})
            last_user = user
    except Exception as e:
        print("Gamerun: User update failure: {}".format(e))
        raise Exception("Unable to assign santas")

    random.shuffle(all_ideas)
    idea_chunks = list(chunks(all_ideas,2))
    idea_update_query = "UPDATE {ideas} SET userid = %(userid)s WHERE id = %(ideaid)s;".format(ideas=true_tablename('ideas'))
    try:
        for i in range(0, len(all_users)):
            for j in idea_chunks[i]:
                dbCursor.execute(idea_update_query,{'userid': all_users[i]['id'],'ideaid':j['id'] })
    except Exception as e:
        print("Gamerun: Idea update failure: {}".format(e))
        raise Exception("Unable to assign ideas")

    # if we are here we should have committed all the above.
    dbConn.commit()

# get game info from the code.
# the function raises exceptions as a way of providing error failures.
def get_game(code):
    get_code = code
    if not get_code:
        raise Exception('Property code is missing or empty.')
    query = "SELECT name,state,id FROM {} WHERE code = %(code)s;".format(true_tablename('games'))
    dbCursor.execute(query, {'code': get_code} )
    if dbCursor.rowcount == 0:
        raise Exception("Not Found")
    try:
        db_game = dbCursor.fetchone()
    except:
        raise Exception("Error fetching games")
    else:
        return db_game

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
            game_result = get_game(request.args.get('code'))
            # id is internal so we should remove it from a public response.
            if 'id' in game_result:
                del game_result['id']
            return json_ok( game_result )
        except Exception as e:
            return json_error(str(e))
    # post to update a game status.
    if request.method == 'POST':
        post_data = request.get_json(force=True)
        if len(post_data) == 0:
            return json_error("No Data sent in request")
        try:
            if 'state' in post_data:
                if not 'secret' in post_data:
                    return json_error("need secret to modify game")
                # states 0 = open; 1 = run; 2 = closed
                get_query = "SELECT state,code,id FROM {games} WHERE secret = %(secret)s AND code = %(code)s;".format(games=true_tablename('games'))
                try:
                    dbCursor.execute(get_query, {'code': post_data['code'], 'secret': post_data['secret']} )
                    if dbCursor.rowcount == 0:
                        dbConn.cancel()
                        return json_error("not found")
                    current_state = dbCursor.fetchone()
                except:
                    dbConn.cancel()
                    return json_error("failed to get game")

                new_state = post_data['state']

                # set to open
                if post_data['state'] == 0:
                    if current_state['state'] != 0:
                        return json_error("Cannot re-open a game, create a new one.")
                # set to run
                if post_data['state'] == 1:
                    if current_state['state'] != 0:
                        return json_error("Can only run open games.")
                    else:
                        try:
                            run_game(current_state['id'])
                        except Exception as e:
                            new_state = current_state['state']
                            print("Error running game: {}".format(e))
                            return json_error("Error running game: {}".format(e))
                # set to closed
                # no error to throw atm

                query = "UPDATE {} SET state = %(state)s WHERE secret = %(secret)s AND code = %(code)s;".format(true_tablename('games'))
                dbCursor.execute(query, {'state': new_state, 'code': post_data['code'], 'secret': post_data['secret']} )
                if dbCursor.rowcount == 0:
                    dbConn.cancel()
                    return json_error("not updated")
                else:
                    dbConn.commit()
                    return json_ok( {'state':new_state} )
            elif 'auth' in post_data:
                # not making a change just want to authenticate
                if not 'secret' in post_data:
                    return json_error("need secret to authenticate")
                
                # get info:
                get_query = """
                SELECT {games}.state,{games}.name,
                (
                    SELECT COUNT({users}.game) From {users} WHERE {users}.game = {games}.id
                ) As santas,
                (
                    SELECT COUNT({ideas}.game) From {ideas} WHERE {ideas}.game = {games}.id
                ) AS ideas
                FROM {games}
                WHERE {games}.secret = %(secret)s AND {games}.code = %(code)s;
                """.format(games=true_tablename('games'),users=true_tablename('users'),ideas=true_tablename('ideas'))
                try:
                    dbCursor.execute(get_query, {'code': post_data['code'], 'secret': post_data['secret']} )
                    if dbCursor.rowcount == 0:
                        dbConn.cancel()
                        return json_error("not found")
                    current_state = dbCursor.fetchone()
                except Exception as e:
                    dbConn.cancel()
                    print("Game get auth game: {}".format(e))
                    return json_error("failed to get game")

                return json_ok(current_state)
            else:
                return json_error("no update key specified")
        except KeyError as e:
            return json_error("missing key: {}".format(e.args[0]))
    
    # we shouldn't get here, but return a message just incase we do
    return json_error("No sure what to do")

# submit ideas
# submit ideas for a game to allow for the draw.
# POST
#    {"code":<gamepubcode>,"idea":<ideatext>}
@app.route('/idea', methods=['POST'])
def idea():
    try:
        post_data = request.get_json(force=True)
        required_field = ['code','idea']
        if all(property in post_data for property in required_field):
            # Existence check is built into the sql query
            insert_query = """INSERT into {ideas}(game,idea) 
            SELECT {games}.id,%(idea)s 
            FROM {games} 
            WHERE {games}.code=%(code)s and 
            exists(SELECT id FROM {games} WHERE {games}.code=%(code)s);""".format(ideas=true_tablename('ideas'),games=true_tablename('games'))
            try:
                dbCursor.execute(insert_query,{'idea': post_data['idea'], 'code': post_data['code']})
                if dbCursor.rowcount == 0:
                    dbConn.cancel()
                    return json_error("Game not found.")
                dbConn.commit()
                return json_ok( {} )
            except Exception as e:
                print("Idea insert error: {}".format(e))
                return json_error("Error adding idea")

    except:
        return json_error("POST data was not json or malformed.")

# user register and game results
@app.route('/user',methods=['POST','GET'])
def user():
    # post is considered registering for a game
    if request.method == 'POST':
        try:
            post_data = request.get_json(force=True)
            if all (property in post_data for property in ('name','code')):
                # in code check, let me know if you know a way to do it in sql.
                check_query = """SELECT {users}.name,code FROM {users} 
                INNER JOIN {games} ON {users}.game={games}.id 
                WHERE {users}.name = %(name)s AND {games}.code = %(code)s;""".format(users=true_tablename('users'),games=true_tablename('games'))
                try:
                    dbCursor.execute(check_query,{'name':post_data['name'],'code':post_data['code']})
                    if not dbCursor.rowcount == 0:
                        return json_error("Already Registered, try another name.")
                    else:
                        register_query = """INSERT INTO {users}(game,name)
                        SELECT {games}.id,%(name)s
                        FROM {games}
                        WHERE {games}.code = %(code)s AND
                        NOT EXISTS (Select {users}.name,code FROM {users} INNER JOIN {games} ON {users}.game={games}.id WHERE {users}.name = %(name)s AND {games}.code = %(code)s);
                        """.format(games=true_tablename('games'),users=true_tablename('users'))
                        dbCursor.execute(register_query, {'name':post_data['name'], 'code':post_data['code']})
                        dbConn.commit()
                        if dbCursor.rowcount == 0:
                            return json_error("Game not found")
                        else:
                            return json_ok ({})
                except Exception as e:
                    print("check user error: {}".format(e))
                    dbConn.cancel()
                    return json_error("Internal error occured")
            else:
                return json_error("name and code is required to register")
        except:
            return json_error("POST data was not json or malformed.")
    # get considered getting your results
    if request.method == 'GET':
        get_code = request.args.get('code')
        get_name = request.args.get('name')
        try: 
            game_result = get_game(get_code)
        except Exception as e:
            return json_error(e)
        
        # 0 = open
        if game_result['state'] == 0:
            return json_error("Santas not yet assigned")
        
        # 1 = run
        if game_result['state'] == 1:
            # get santa info
            get_santainfo_query = """
            SELECT santa.name as name,giftees.name as giftee
                FROM {users} as santa
                INNER JOIN {users} as giftees ON santa.santa = giftees.id
                WHERE santa.name = %(username)s AND santa.game = %(gameid)s;
            """.format(users=true_tablename('users'))
            try:
                dbCursor.execute(get_santainfo_query,{'username': get_name, 'gameid':game_result['id'] })
                if dbCursor.rowcount == 0:
                    return json_error("Name not found in pool")
                santa_data = dbCursor.fetchone()
            except Exception as e:
                print("Santa info get failed: {}".format(e))
                return json_error("failed to get giftee information")

            # get idea list
            get_idea_query = """
            SELECT idea FROM {ideas} 
                INNER JOIN {users} ON {ideas}.userid = {users}.id
                WHERE {users}.name = %(username)s AND {users}.game = %(gameid)s;
            """.format(users=true_tablename('users'),ideas=true_tablename('ideas'))

            try:
                dbCursor.execute(get_idea_query,{'username': get_name, 'gameid':game_result['id']})
                if dbCursor.rowcount == 0:
                    return json_error("Name not found in pool of ideas")
                idea_data = dbCursor.fetchall()
            except Exception as e:
                print("Santa ideas info get failed: {}".format(e))
                return json_error("failed to get your ideas")

            idea_list = []
            for idea in idea_data:
                idea_list.append(idea['idea'])

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

# create a new group/game
# POST
#    {"name":<gameDisplayName>}
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

            # we need to check the pub code does not exist already.
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
                    'drop table IF EXISTS {};'.format(true_tablename('games')),
                    'drop table IF EXISTS {};'.format(true_tablename('ideas')),
                    'drop table IF EXISTS {};'.format(true_tablename('users'))
                ]
                create_list = [
                    'create table {} (id serial,name varchar(200),secret varchar(64),code varchar(8),state int);'.format(true_tablename('games')),
                    'create table {} (id serial,game int,idea varchar(260),userid int DEFAULT -1);'.format(true_tablename('ideas')),
                    'create table {} (id serial,game int,name varchar(30),santa int DEFAULT -1);'.format(true_tablename('users'))
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
    except Exception as e:
        dbConn.cancel()
        print("Reset error: {}".format(e))
        return json_error("")
    # due to the nature of the interface no error messages are currently returned.
    return json_error("Not Implemented")


# For dev local runs, start flask in python process.
if __name__ == '__main__':
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port)