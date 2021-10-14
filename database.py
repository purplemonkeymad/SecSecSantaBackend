# Interface for SQL calls,

""" Database wrapper for db calls, allows calling db as code instead of having
other code mess with sql.
"""

# SQL note:
#
# I'm using 2 "formats" for sql queries.  one is used by the sql connector so i used the other type
# to fill in table names. tables names use a fromat like: {basename} and values %(valuename)s
# sql queries should be .format ed when created so that they choose dev/prod as needed.

import os
# database
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor

import SantaErrors

# db setup


urllib.parse.uses_netloc.append('postgres')
# heroku puts db info in this env
if "DATABASE_URL" in os.environ:
    __dburl = urllib.parse.urlparse(os.environ['DATABASE_URL'])
    __dbConn = psycopg2.connect( database=__dburl.path[1:], user=__dburl.username, password=__dburl.password, host=__dburl.hostname, port=__dburl.port)
    __dbCursor = __dbConn.cursor(cursor_factory=RealDictCursor)
else:
    print("DATABASE_URL not set any database connections will fail!")


# state setup

if os.environ.get('IS_PROD',0) == '1':
    __table_prefix = "prod"
else:
    __table_prefix = "dev"
__realm_name = "santa"

###############################
# internal funcs
###############################

def true_tablename(tablename):
    """Convert a basic table name to one with realm and env names

    :param tablename: Short name to convert to actual name
    """
    return "{}_{}_{}".format(__table_prefix,__realm_name,tablename)

def __stringlist_to_sql_columns(columns:list) -> str:
    """Convert a list of strings to column definitions in sql
    """
    return ','.join(columns)

def __assert_dict_columns(query:dict,valid_list:list):
    """Tests for invalid columns in a dict use for requests.
    """
    invalid_properties = [x for x in query.keys() if x not in valid_list]
    if (invalid_properties):
        raise KeyError("Invalid query property {props} for database query. The valid list of columns are: {valid}".format(props=invalid_properties,valid=valid_list))
    return 0

def __assert_columns(wanted:list,valid_list:list):
    """Tests for invalid column names in a list.
    """
    invalid_properties = [x for x in wanted if x not in valid_list]
    if (invalid_properties):
        raise KeyError("Invalid properties {props} for database query. The valid list of properties are: {valid}".format(props=invalid_properties,valid=valid_list))
    return 0

def __assert_admin_key(admin_key:str):
    """Test if the admin key matches configured key.
    """
    if 'AdminSecret' not in os.environ:
        raise SantaErrors.ConfigurationError("Admin Secret not set, admin functions cannot be used until set.")
    if len(os.environ['AdminSecret']) < 10:
        raise SantaErrors.ConfigurationError("Admin Secret too short, admin functions cannot be used until set.")
    if admin_key == os.environ['AdminSecret']:
        return 0
    raise SantaErrors.AuthorizationError("Not Authorized.")

def __assert_can_do_major_db_changes():
    """
    Checks that table changes and resets are enabled sys vars
    """
    if 'AllowTableTruncates' not in os.environ:
        raise SantaErrors.AuthorizationError("Table Truncation setting missing, default is disabled.")
    if len(os.environ['AllowTableTruncates']) == 0:
        raise SantaErrors.AuthorizationError("Table Truncation setting empty, default is disabled.")
    if os.environ['AllowtableTruncates'] == 'AllowTruncates':
        return 0
    raise SantaErrors.AuthorizationError("table Truncation settings is not 'AllowTruncates', value is disabled.")

def __get_new_cursor():
    """Gets a new cursor, needed for atomic operations that use multiple sql commands
    """
    return __dbConn.cursor(cursor_factory=RealDictCursor)

def __get_simple_table(table_name:str,columns_to_get:list,column_query:dict,valid_columns:list):
    """Does a simple lookup against a single table.
    This is for basic 'Select column From table Where column = value;' queries.
    It creates a parameterized query to prevent injection attacks.
    """
    # prevent a get all of table without a query
    if (len(column_query) == 0):
        raise KeyError("Simple database lookup requires at least one column lookup.")

    # whitelist column names to prevent injection attack.
    __assert_columns(columns_to_get,valid_columns)
    __assert_dict_columns(column_query,valid_columns)

    query_keys = ' AND '.join( [ " {key} = %({key})s ".format(key=k) for k in column_query.keys() ] )
    user_query = "SELECT {props} FROM {table} WHERE {query_string};".format(table=true_tablename(table_name),props=__stringlist_to_sql_columns(columns_to_get),query_string=query_keys)
    __dbCursor.execute(user_query,column_query)
    return __dbCursor.fetchall()

#######################
# external funcs
#######################

def get_users(query:dict, properties:list = ['id','name','game'] ):
    """ Gets a user from a game by id,game etc.
    """
    # valid properties
    valid_properties = ['id','name','game','santa']
    return __get_simple_table('users',properties,query,valid_properties)

def get_user_giftee(user_name:str,game_id:int):
    """ Gets the assigned recipient of a select user
    """
    if len(user_name) == 0:
        raise ValueError("Name is empty.")
    if game_id < 1:
        raise ValueError("Game code is empty.")

    get_santainfo_query = """
    SELECT santa.name as name,giftees.name as giftee
    FROM {users} as santa
    INNER JOIN {users} as giftees ON santa.santa = giftees.id
    WHERE TRIM(from santa.name) = %(username)s AND santa.game = %(gameid)s;
    """.format(users=true_tablename('users'))

    # we should trim the name at this point
    clean_name = user_name.strip()

    __dbCursor.execute(get_santainfo_query,{'username': clean_name, 'gameid':game_id })
    return __dbCursor.fetchall()

def get_user_ideas(user_name:str,game_id:int):
    """ Gets the ideas assigned to a user
    """

    if len(user_name) == 0:
        raise ValueError("Name is empty.")
    if game_id < 1:
        raise ValueError("Game id is empty")
    
    get_idea_query = """
    SELECT idea FROM {ideas} 
    INNER JOIN {users} ON {ideas}.userid = {users}.id
    WHERE TRIM(from {users}.name) = %(username)s AND {users}.game = %(gameid)s;
    """.format(users=true_tablename('users'),ideas=true_tablename('ideas'))
    
    # we should trim the name at this point
    clean_name = user_name.strip()

    __dbCursor.execute(get_idea_query,{'username': clean_name, 'gameid': game_id })
    return __dbCursor.fetchall()

def set_user_santa(user_id:str,santa_id:str,game_code:str,game_secret:str):
    """
    Sets the santa of a user.
    """
    update_query = """
    WITH gameinfo AS (
        -- Get game by code and secret
        SELECT {games}.id as gameid
        FROM {games} 
        WHERE {games}.code = %(code)s AND {games}.secret = %(secret)s
    )
    UPDATE {users} 
    SET santa = %(santaid)s 
    FROM gameinfo
    WHERE {users}.id = %(userid)s
    AND {users}.game = gameinfo.gameid;
    """.format(users=true_tablename('users'),games=true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(update_query,{
            'code':game_code,
            'secret':game_secret,
            'userid':user_id,
            'santaid':santa_id,
        })
        if cursor.rowcount == 0:
            raise FileNotFoundError("Unable to update user, one or more keys were wrong.")
        elif not cursor.rowcount == 1:
            __dbConn.rollback()
            raise RuntimeError("Database attempted to make multiple changes to single item action.")
        else:
            # exactly one
            __dbConn.commit()
            return


def get_game(query:dict, properties:list = ['id','name','code','state'] ):
    """ Gets a game from id/code etc.
    """
    # valid properties
    valid_properties = ['id','name','secret','code','state']
    return __get_simple_table('games',properties,query,valid_properties)

def get_game_ideas(pubkey:str,privkey:str):
    """
    Gets ideas from a game code.
    """
    if len(pubkey) == 0:
        raise ValueError("Code is empty.")
    if len(privkey) == 0:
        raise ValueError("Secret is empty")

    get_idea_query = """
    SELECT {ideas}.id,idea,game
    FROM {ideas} 
        INNER JOIN {games} 
        ON {games}.id = {ideas}.game
    WHERE {games}.code = %(code)s
    AND {games}.secret = %(secret)s;
    """.format(games=true_tablename('games'),ideas=true_tablename('ideas'))

    __dbCursor.execute(get_idea_query,{
        'code': pubkey,
        'secret': privkey
    })
    return __dbCursor.fetchall()

def new_game(name:str,privkey:str,pubkey:str):
    """ Inserts a new game into the database.
    """
    query = "INSERT INTO {} VALUES(DEFAULT,%(name)s,%(privkey)s,%(pubkey)s,0) RETURNING id,name,code,state,secret ;".format(true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query,{'name':name,'privkey':privkey,'pubkey':pubkey})
        return cursor.fetchall()

def join_game(user_name:str,pubkey:str):
    """ Inserts a new name into a game
    """
    ## updated query needs updated db settings, TODO this later.
    query = """
        INSERT INTO {users} (game,name)
            SELECT {games}.id,%(name)s
                FROM {games} WHERE {games}.code = %(code)s
        ON CONFLICT("name") DO NOTHING
        RETURNING {users}.id,{users}.name,{users}.game
    """.format(users=true_tablename('users'),games=true_tablename('games'))

    check_query = """
        SELECT {users}.name,code 
        FROM {users}
            INNER JOIN {games} ON {users}.game={games}.id 
        WHERE {users}.name = %(name)s AND {games}.code = %(code)s;""".format(users=true_tablename('users'),games=true_tablename('games'))
    register_query = """
        INSERT INTO {users}(game,name)
            SELECT {games}.id,%(name)s
            FROM {games}
            WHERE {games}.code = %(code)s AND
            NOT EXISTS (
                Select {users}.name,code FROM {users} 
                    INNER JOIN {games} 
                    ON {users}.game={games}.id 
                WHERE {users}.name = %(name)s AND {games}.code = %(code)s
            )
        RETURNING {users}.id,{users}.name,{users}.game;
    """.format(games=true_tablename('games'),users=true_tablename('users'))
                        

    # we should trim the name at this point
    clean_name = user_name.strip()

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(check_query,{
            'name':clean_name,
            'code':pubkey,
        })
        result = cursor.fetchall()
        if len(result) == 0:
            # no matching item insert item
            cursor.execute(register_query,{
                'name':clean_name,
                'code':pubkey,
            })
            return cursor.fetchall()
        else:
            raise FileExistsError("Name already registered.")

def get_idea(query:dict, properties:list = ['id','game','idea']):
    """ Gets ideas from game/id
    """
    valid_properties = ['id','game','idea','userid']
    return __get_simple_table('ideas',properties,query,valid_properties)

def new_idea(pubkey:str,idea:str):
    """
    Add a new idea to a game
    """
    query = """
        INSERT into {ideas}(game,idea) 
        SELECT {games}.id,%(idea)s 
        FROM {games} 
        WHERE {games}.code=%(code)s and 
        exists(
            SELECT id FROM {games} WHERE {games}.code=%(code)s
        )
        RETURNING {ideas}.id,{ideas}.idea,{ideas}.game;
    """.format(ideas=true_tablename('ideas'),games=true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query,{
            'idea':idea,
            'code':pubkey,
        })
        result = cursor.fetchall()
        if len(result) == 0:
            raise FileNotFoundError("Game not found.")
        return result

def set_idea_user(idea_id:str,user_id:str,game_code:str,game_secret:str):
    """
    Sets the idea of a user.
    """
    update_query = """
    WITH gameinfo AS (
        -- Get game by code and secret
        SELECT {games}.id as gameid
        FROM {games} 
        WHERE {games}.code = %(code)s AND {games}.secret = %(secret)s
    )
    UPDATE {ideas} 
    SET userid = %(userid)s 
    FROM gameinfo
    WHERE {ideas}.id = %(ideaid)s
    AND {ideas}.game = gameinfo.gameid;
    """.format(ideas=true_tablename('ideas'),games=true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(update_query,{
            'code':game_code,
            'secret':game_secret,
            'userid':user_id,
            'ideaid':idea_id,
        })
        if cursor.rowcount == 0:
            raise FileNotFoundError("Unable to update idea assignment, one or more keys were wrong.")
        elif not cursor.rowcount == 1:
            __dbConn.rollback()
            raise RuntimeError("Database attempted to make multiple changes to single item action.")
        else:
            # exactly one
            __dbConn.commit()
            return

#########################################################
# owner funcs
# all funcs should check the game secret is correct.
#########################################################

def get_game_sum(code:str,secret:str):
    """ Gets a summary of at game, can be used to check
    authentication.
    """

    if (len(code) == 0 or len(secret) ==0 ):
        raise ValueError("Gameid or Secret are empty, both values are required.")

    get_summary_query = """
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

    __dbCursor.execute(get_summary_query,{
        'code':code,
        'secret':secret,
    })
    return __dbCursor.fetchall()

def get_users_in_game(code:str,secret:str):
    """List of users that have joined a game
    """

    if (len(code) == 0 or len(secret) ==0 ):
        raise ValueError("Gameid or Secret are empty, both values are required.")

    get_userlist_query = """
    SELECT {users}.id,game,{users}.name FROM {users} INNER JOIN {games} ON {games}.id = {users}.game WHERE {games}.code = %(code)s AND {games}.secret = %(secret)s;
    """.format(users=true_tablename('users'),games=true_tablename('games'))

    __dbCursor.execute(get_userlist_query,{'code':code,'secret':secret})
    return __dbCursor.fetchall()

def set_game_state(code:str,secret:str,new_state:int):
    """
    Updates the stored state value of a game.
    """

    if (len(code) == 0 or len(secret) ==0 ):
        raise ValueError("Gameid or Secret are empty, both values are required.")
    
    query = """
    UPDATE {games} SET state = %(state)s 
    WHERE secret = %(secret)s AND code = %(code)s
    RETURNING {games}.code,{games}.state;
    """.format(games=true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query,{
            'state': new_state,
            'code': code,
            'secret': secret,
        })
        result = cursor.fetchall()
        if len(result) == 0:
            raise FileNotFoundError("Game not found.")
        return result

###########################################
# admin funcs
# all method should check for an admin_key
###########################################

def get_all_games(admin_key:str):
    __assert_admin_key(admin_key)
    properties = ['id','name','code','state']
    user_query = "SELECT {props} FROM {table};".format(table=true_tablename('games'),props=__stringlist_to_sql_columns(properties))
    __dbCursor.execute(user_query,{})
    return __dbCursor.fetchall()

def get_all_open_games(admin_key:str):
    __assert_admin_key(admin_key)
    properties = ['id','name','code','state']
    user_query = "SELECT {props} FROM {table} WHERE state = 0;".format(table=true_tablename('games'),props=__stringlist_to_sql_columns(properties))
    __dbCursor.execute(user_query,{})
    return __dbCursor.fetchall()

def get_all_complete_games(admin_key:str):
    __assert_admin_key(admin_key)
    properties = ['id','name','code','state']
    user_query = "SELECT {props} FROM {table} WHERE state = 1;".format(table=true_tablename('games'),props=__stringlist_to_sql_columns(properties))
    __dbCursor.execute(user_query,{})
    return __dbCursor.fetchall()

def get_all_closed_games(admin_key:str):
    __assert_admin_key(admin_key)
    properties = ['id','name','code','state']
    user_query = "SELECT {props} FROM {table} WHERE state = 2;".format(table=true_tablename('games'),props=__stringlist_to_sql_columns(properties))
    __dbCursor.execute(user_query,{})
    return __dbCursor.fetchall()

def reset_all_tables(admin_key:str):
    __assert_admin_key(admin_key)
    __assert_can_do_major_db_changes()
    table_list = [
        true_tablename('games'),
        true_tablename('ideas'),
        true_tablename('users'),
    ]
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        for table in table_list:
            table_truncate = "TRUNCATE TABLE {};".format(table)
            cursor.execute(table_truncate,{})
        __dbConn.commit()
        return {'resetstatus':'ok'}

def init_tables(admin_key:str):
    __assert_admin_key(admin_key)
    __assert_can_do_major_db_changes()
    table_definition = [
        # initial 1.0 tables
        'CREATE TABLE IF NOT EXISTS {} (id serial,name varchar(200),secret varchar(64),code varchar(8),state int);'.format(true_tablename('games')),
        'create unique index if not exists {}_code on {} using btree (code);'.format(true_tablename('games')),
        'CREATE TABLE IF NOT EXISTS {} (id serial,game int,idea varchar(260),userid int DEFAULT -1);'.format(true_tablename('ideas')),
        'CREATE TABLE IF NOT EXISTS {} (id serial,game int,name varchar(30),santa int DEFAULT -1);'.format(true_tablename('users')),
        # tables for user auth
        'create extension if not exists pgcrypto;',
        'Create Table If Not Exists {identity} (id serial PRIMARY KEY, email varchar(255), name varchar(30),register_date timestamp Not Null Default NOW(), verify_date timestamp);'.format(identity=true_tablename('identities')),
        """
        Create Table If Not Exists {session} (
            id uuid, 
            verify_hash text,
            secret_hash text,
            identity_id not null,
            last_date date Default NOW(),
            CONSTRAINT fk_identity_id
                FOREIGN KEY(identity_id)
                REFERENCES {identity}(id)
                ON DELETE CASCADE
        );
        """.format(session=true_tablename('sessions'),identity=true_tablename('identities')),
        'create unique index if not exists {session}_uuid on {session} using btree (uuid);'.format(session=true_tablename('sessions')),
    ]
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        for table in table_definition:
            cursor.execute(table,{})
        __dbConn.commit()
        return {'initstatus':'ok'}

###################################
# Login funcs
###################################

def new_session(uuid:str, email:str, verify_code:str):
    """
    Create a new session for a user
    """

    new_session_query = """
    INSERT INTO {session} (id,verify_hash,secret_hash,identity_id,last_date)
        SELECT %(uuid)s,crypt(%(code)s, gen_salt('bf')),NULL,{identity}.id,NOW()
        FROM {identity} WHERE {identity}.email = %(email)s
    RETURNING {session}.id,{session}.last_date,{identity}.email;
    """.format(session=true_tablename('sessions'),identity=true_tablename('identities'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(new_session_query,{'uuid':uuid,'email':email,'code':verify_code})
        return cursor.fetchall()


def register_user(email:str,name:str):
    """
    Create an identity for an email so new session can be created.
    """

    new_user = """
    INSERT into {identity}(id,email,name,register_date) 
    Values (DEFAULT,%(email)s,%(name)s,NOW())
    RETURNING id,email,name;
    """.format(session=true_tablename('sessions'),identity=true_tablename('identities'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(new_user,{'name':name,'email':email})
        return cursor.fetchall()