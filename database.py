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
from re import S
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
    if os.environ['AllowTableTruncates'] == 'AllowTruncates':
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
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(user_query,column_query)
        return __dbCursor.fetchall()

def __lowercase_email(email:str):
    return email.lower()

#######################
# external funcs
#######################

#######################
# *User*
#######################

def get_users(query:dict, properties:list = ['id','name','game'] ):
    """ Gets a user from a game by id,game etc.
    """
    # valid properties
    valid_properties = ['id','name','game','santa']
    return __get_simple_table('users',properties,query,valid_properties)

def get_user_giftee(user_id:int,game_code:str):
    """ Gets the assigned recipient of a select user
    """

    if len(game_code) == 0:
        raise ValueError("Game code is empty.")

    get_santainfo_query = """
    SELECT santa.name as name,giftees.name as giftee
    FROM {users} as santa
        INNER JOIN {users} as giftees ON santa.santa = giftees.id
        INNER JOIN {games} as game On santa.game = game.id
    WHERE santa.account_id = %(userid)s AND game.code = %(gameid)s;
    """.format(users=true_tablename('users'),games=true_tablename('games'))

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(get_santainfo_query,{'userid': user_id, 'gameid':game_code })
        return __dbCursor.fetchall()

def get_user_ideas(user_id:int,game_code:str):
    """ Gets the ideas assigned to a user
    """

    if len(game_code) == 0:
        raise ValueError("Game code is empty.")
    
    get_idea_query = """
    SELECT idea FROM {ideas} 
        INNER JOIN {users} ON {ideas}.userid = {users}.id
        INNER JOIN {games} ON {users}.game = {games}.id
    WHERE {users}.account_id = %(userid)s AND {games}.code = %(gameid)s;
    """.format(users=true_tablename('users'),ideas=true_tablename('ideas'),games=true_tablename('games'))

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(get_idea_query,{'userid': user_id, 'gameid': game_code })
        return __dbCursor.fetchall()

def set_user_santa(user_id:str,santa_id:str,game_code:str,sessionid:str,sessionpassword:str):
    """
    Sets the santa of a user.
    """
    
    ## get logged on user details
    owner = __authenticate_user(sessionid,sessionpassword)

    if (len(game_code) == 0):
        raise ValueError("Gameid is empty.")
    
    update_query = """
    WITH gameinfo AS (
        -- Get game by code and secret
        SELECT {games}.id as gameid
        FROM {games} 
        WHERE {games}.code = %(code)s AND {games}.ownerid = %(ownerid)s
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
            'ownerid':owner['id'],
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

#######################
# *Game*
#######################


def get_game(query:dict, properties:list = ['id','name','code','state'] ):
    """ Gets a game from id/code etc.
    """
    # valid properties
    valid_properties = ['id','name','code','state','ownerid']
    return __get_simple_table('games',properties,query,valid_properties)

def get_game_ideas(pubkey:str,sessionid:str,sessionpassword:str):
    """
    Gets ideas from a game code.
    """

    ## get logged on user details
    user = __authenticate_user(sessionid,sessionpassword)

    if (len(pubkey) == 0):
        raise ValueError("Gameid is empty.")

    get_idea_query = """
    SELECT {ideas}.id,idea,game
    FROM {ideas} 
        INNER JOIN {games} 
        ON {games}.id = {ideas}.game
    WHERE {games}.code = %(code)s
    AND {games}.ownerid = %(userid)s;
    """.format(games=true_tablename('games'),ideas=true_tablename('ideas'))

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(get_idea_query,{
            'code': pubkey,
            'userid': user['id']
        })
        return __dbCursor.fetchall()

def new_game(name:str,pubkey:str,sessionid:str,sessionpassword:str):
    """ Inserts a new game into the database.
    """
    user = __authenticate_user(sessionid,sessionpassword)

    query = "INSERT INTO {} (id,name,secret,code,state,ownerid) VALUES(DEFAULT,%(name)s,null,%(pubkey)s,0,%(userid)s) RETURNING id,name,code,state,ownerid ;".format(true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query,{'name':name,'userid':user['id'],'pubkey':pubkey})
        return cursor.fetchall()

def join_game(user_name:str,pubkey:str,sessionid:str,sessionpassword:str):
    """ Inserts a new name into a game
    """

    ## get logged on user details
    user = __authenticate_user(sessionid,sessionpassword)

    register_query = """
    WITH r As(
        Insert Into {users}(game,name,account_id)
        Select {games}.id,%(name)s,%(userid)s
        From {games}
        WHERE {games}.code = %(code)s AND state IN (0)
        On Conflict("game","account_id") Do Nothing
        Returning {users}.id,{users}.name,{users}.game,{users}.account_id,'New'::text AS Status
    ), s As(
        SELECT * From r
        Union
            Select {users}.id,{users}.name,{users}.game,{users}.account_id,'Existing'::text As Status
            From {users}
            INNER Join {games} On {games}.id = {users}.game
            Where {games}.code = %(code)s AND state IN (0) And {users}.account_id = %(userid)s
    )
    SELECT s.*,{games}.name as gamename From s
        Inner Join {games}
        On {games}.id = s.game;
    """.format(games=true_tablename('games'),users=true_tablename('users'))
    
    # we should trim the name at this point
    clean_name = user_name.strip()
    if len(clean_name) == 0:
        clean_name = user['name']

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(register_query,{
            'name':clean_name,
            'code':pubkey,
            'userid':user['id'],
        })
        return cursor.fetchall()

def list_user_games(sessionid:str,sessionpassword:str):
    """
    Allows a user to get the list of joined groups
    """

    ## get logged on user details
    user = __authenticate_user(sessionid,sessionpassword)

    list_query = """
    SELECT games.name,games.code,games.state,users.name as joinname
    FROM {games} as games
        INNER JOIN {users} as users
        ON games.id = users.game
    WHERE users.account_id = %(userid)s AND games.state IN (0,1);
    """.format(games=true_tablename('games'),users=true_tablename('users'))

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(list_query,{
            'userid':user['id'],
        })
        return __dbCursor.fetchall()

def list_owned_games(sessionid:str,sessionpassword:str):
    """
    get a list of groups owned by the user.
    """

    ## get logged on user details
    user = __authenticate_user(sessionid,sessionpassword)

    list_query = """
    SELECT name,code,state 
    FROM {games} as games
    Where games.ownerid = %(userid)s;
    """.format(games=true_tablename('games'))

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(list_query,{
            'userid':user['id'],
        })
        return __dbCursor.fetchall()


#######################
# *idea*
#######################

def get_idea(query:dict, properties:list = ['id','game','idea']):
    """ Gets ideas from game/id
    """
    valid_properties = ['id','game','idea','userid']
    return __get_simple_table('ideas',properties,query,valid_properties)

def new_idea(pubkey:str,idea:str,sessionid:str,sessionpassword:str):
    """
    Add a new idea to a game
    """

    ## get logged on user details
    user = __authenticate_user(sessionid,sessionpassword)

    unique_idea_query ="""
    WITH r As(
        -- insert query
        Insert Into {ideas}(game,idea,account_id)
        Select {games}.id,%(idea)s,%(userid)s
        From {games}
        WHERE {games}.code = %(code)s AND state IN (0)
        On Conflict("idea","account_id") Do Nothing
        Returning {ideas}.id,{ideas}.idea,{ideas}.game,{ideas}.account_id,'New'::text AS Status
    ), s As(
        -- union here will get existing records, if the row existed then r is empty and we fill with exiting data.
        SELECT * From r
        Union
            Select {ideas}.id,{ideas}.idea,{ideas}.game,{ideas}.account_id,'Existing'::text As Status
            From {ideas}
            INNER Join {games} On {games}.id = {ideas}.game
            Where {games}.code = %(code)s AND state IN (0) And {ideas}.account_id = %(userid)s And {ideas}.idea = %(idea)s
    )
    -- join whatever result we just got with the games take to return the name, not the game internal id.
    SELECT s.*,{games}.name as gamename From s
        Inner Join {games}
        On {games}.id = s.game;
    """.format(ideas=true_tablename('ideas'),games=true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(unique_idea_query,{
            'idea':idea,
            'code':pubkey,
            'userid':user['id'],
        })
        result = cursor.fetchall()
        if len(result) == 0:
            raise SantaErrors.NotFound("Group not found.")
        return result

def set_idea_user(idea_id:str,user_id:str,game_code:str,sessionid:str,sessionpassword:str):
    """
    Sets the idea of a user.
    """

    ## get logged on user details
    owner = __authenticate_user(sessionid,sessionpassword)

    if (len(game_code) == 0):
        raise SantaErrors.EmptyValue("Group id is empty.")

    update_query = """
    WITH gameinfo AS (
        -- Get game by code and secret
        SELECT {games}.id as gameid
        FROM {games} 
        WHERE {games}.code = %(code)s AND {games}.ownerid = %(ownerid)s
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
            'ownerid':owner['id'],
            'userid':user_id,
            'ideaid':idea_id,
        })
        if cursor.rowcount == 0:
            raise SantaErrors.DatabaseChangeError("Unable to update idea assignment, one or more keys were wrong.")
        elif not cursor.rowcount == 1:
            __dbConn.rollback()
            raise SantaErrors.DatabaseChangeError("Database attempted to make multiple changes to single item action.")
        else:
            # exactly one
            __dbConn.commit()
            return

#########################################################
# owner funcs
# all funcs should check the game secret is correct.
#########################################################

def get_game_sum(code:str,sessionid:str,sessionpassword:str):
    """ Gets a summary of at game, can be used to check
    authentication.
    """

    ## get logged on user details
    user = __authenticate_user(sessionid,sessionpassword)

    get_summary_query = """
    SELECT {games}.state,{games}.name,
    (
        SELECT COUNT({users}.game) From {users} WHERE {users}.game = {games}.id
    ) As santas,
    (
        SELECT COUNT({ideas}.game) From {ideas} WHERE {ideas}.game = {games}.id
    ) AS ideas
    FROM {games}
    WHERE {games}.ownerid = %(userid)s AND {games}.code = %(code)s;
    """.format(games=true_tablename('games'),users=true_tablename('users'),ideas=true_tablename('ideas'))

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(get_summary_query,{
            'code':code,
            'userid':user['id'],
        })
        return __dbCursor.fetchall()

def get_users_in_game(code:str,sessionid:str,sessionpassword:str):
    """List of users that have joined a game
    """

    ## get logged on user details
    user = __authenticate_user(sessionid,sessionpassword)

    if (len(code) == 0):
        raise SantaErrors.EmptyValue("Group id is empty.")

    get_userlist_query = """
    SELECT {users}.id,game,{users}.name FROM {users} INNER JOIN {games} ON {games}.id = {users}.game WHERE {games}.code = %(code)s AND {games}.ownerid = %(userid)s;
    """.format(users=true_tablename('users'),games=true_tablename('games'))

    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(get_userlist_query,{'code':code,'userid':user['id']})
        return __dbCursor.fetchall()

def set_game_state(code:str,sessionid:str,sessionpassword:str,new_state:int):
    """
    Updates the stored state value of a game.
    """

    ## get logged on user details
    user = __authenticate_user(sessionid,sessionpassword)

    if (len(code) == 0):
        raise SantaErrors.EmptyValue("Group id is empty.")
    
    query = """
    UPDATE {games} SET state = %(state)s 
    WHERE ownerid = %(ownerid)s AND code = %(code)s
    RETURNING {games}.code,{games}.state;
    """.format(games=true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query,{
            'state': new_state,
            'code': code,
            'ownerid': user['id'],
        })
        result = cursor.fetchall()
        if len(result) == 0:
            raise SantaErrors.NotFound("Group not found.")
        return result

###########################################
# admin funcs
# all method should check for an admin_key
###########################################

def get_all_games(admin_key:str):
    __assert_admin_key(admin_key)
    properties = ['id','name','code','state','ownerid']
    user_query = "SELECT {props} FROM {table};".format(table=true_tablename('games'),props=__stringlist_to_sql_columns(properties))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(user_query,{})
        return __dbCursor.fetchall()

def get_all_open_games(admin_key:str):
    __assert_admin_key(admin_key)
    properties = ['id','name','code','state','ownerid']
    user_query = "SELECT {props} FROM {table} WHERE state = 0;".format(table=true_tablename('games'),props=__stringlist_to_sql_columns(properties))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(user_query,{})
        return __dbCursor.fetchall()

def get_all_complete_games(admin_key:str):
    __assert_admin_key(admin_key)
    properties = ['id','name','code','state','ownerid']
    user_query = "SELECT {props} FROM {table} WHERE state = 1;".format(table=true_tablename('games'),props=__stringlist_to_sql_columns(properties))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
        __dbCursor.execute(user_query,{})
        return __dbCursor.fetchall()

def get_all_closed_games(admin_key:str):
    __assert_admin_key(admin_key)
    properties = ['id','name','code','state','ownerid']
    user_query = "SELECT {props} FROM {table} WHERE state = 2;".format(table=true_tablename('games'),props=__stringlist_to_sql_columns(properties))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as __dbCursor:
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
        'create unique index if not exists {games}_code on {games} using btree (code);'.format(games=true_tablename('games')),
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
            identity_id int not null,
            last_date timestamp Default NOW(),
            CONSTRAINT fk_identity_id
                FOREIGN KEY(identity_id)
                REFERENCES {identity}(id)
                ON DELETE CASCADE
        );
        """.format(session=true_tablename('sessions'),identity=true_tablename('identities')),
        'create unique index if not exists {session}_uuid on {session} using btree (id);'.format(session=true_tablename('sessions')),
        # upgrade 1.0 tables with user columns
        """
        ALTER TABLE {games}
        Add Column If Not Exists ownerid int default null;
        """.format(games=true_tablename('games'),identity=true_tablename('identities')),
        """
        -- no if not exists for constraints
        DO $$
        begin
            if not exists (select constraint_name 
                        from information_schema.constraint_column_usage 
                        where table_name = '{identity}' and constraint_name = '{games}_ownerid' ) then
                ALTER TABLE {games}
                ADD CONSTRAINT {games}_ownerid FOREIGN KEY (ownerid) REFERENCES {identity} (id);
            end if;
        end $$;
        """.format(games=true_tablename('games'),identity=true_tablename('identities')),
        """
        ALTER TABLE {users}
        Add Column If Not Exists account_id int default null;
        """.format(users=true_tablename('users'),identity=true_tablename('identities')),
        """
        -- no if not exists for constraints
        DO $$
        begin
            if not exists (select constraint_name 
                        from information_schema.constraint_column_usage 
                        where table_name = '{identity}' and constraint_name = '{users}_account_id' ) then
                ALTER TABLE {users}
                Add Constraint {users}_account_id Foreign Key (account_id) References {identity} (id);
            end if;
        end $$;
        """.format(users=true_tablename('users'),identity=true_tablename('identities')),
        "create unique index if not exists {users}_game_account on {users} using btree (game,account_id);".format(users=true_tablename('users')),
        ## upgrade ideas to include submitter so that duplication can be detected.
            #add column
        """
        ALTER TABLE {ideas}
        Add Column If Not Exists account_id int default null;
        """.format(ideas=true_tablename('ideas'),identity=true_tablename('identities')),
            # add constraint
        """
        -- no if not exists for constraints
        DO $$
        begin
            if not exists (select constraint_name 
                        from information_schema.constraint_column_usage 
                        where table_name = '{identity}' and constraint_name = '{ideas}_account_id' ) then
                ALTER TABLE {ideas}
                Add Constraint {ideas}_account_id Foreign Key (account_id) References {identity} (id);
            end if;
        end $$;
        """.format(ideas=true_tablename('ideas'),identity=true_tablename('identities')),
            # add index for faster lookups
        "create unique index if not exists {ideas}_game_account on {ideas} using btree (account_id,idea);".format(ideas=true_tablename('ideas')),

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
    WITH user_ident AS (
        SELECT id,email,name
        FROM {identity} WHERE {identity}.email = %(email)s
    )
    INSERT INTO {session} (id,verify_hash,secret_hash,identity_id,last_date)
        SELECT %(uuid)s,crypt(%(code)s, gen_salt('bf')),NULL,{identity}.id,NOW()
        FROM {identity} WHERE {identity}.email = %(email)s
    RETURNING {session}.id,{session}.last_date,
        (SELECT email FROM user_ident),
        (SELECT name FROM user_ident);
    """.format(session=true_tablename('sessions'),identity=true_tablename('identities'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(new_session_query,{
            'uuid':uuid,
            'email': __lowercase_email(email),
            'code':verify_code,
            })
        return cursor.fetchall()

def confirm_session(uuid:str, verify_code:str, new_secret:str):
    """
    Check and update the session to verify that the session is
    good to use.
    """

    verify_session_query = """
    UPDATE {session}
    SET secret_hash = crypt(%(secret)s,gen_salt('bf')) , verify_hash = NULL , last_date = NOW()
    WHERE id = %(uuid)s AND verify_hash = crypt(%(code)s,verify_hash)
    RETURNING id,identity_id,last_date;
    """.format(session=true_tablename('sessions'))
    update_verify_date = """
    UPDATE {identity}
    SET verify_date = NOW()
    WHERE {identity}.id = %(ident)s
    """.format(identity=true_tablename('identities'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(verify_session_query,{'uuid':uuid,'secret':new_secret,'code':verify_code})
        session_data = cursor.fetchall()
        if type(session_data) == list:
            if len(session_data) == 0:
                return session_data # nothing done, so just return nothing
            session_data = session_data[0]
        cursor.execute(update_verify_date,{'ident':session_data['identity_id']})
        return session_data
        
def remove_session(uuid:str, secret:str):
    """
    Log out a session by removing it from the db.
    """
    # only authed users can logout!
    __authenticate_user(uuid,secret)

    remove_session_query = """
    DELETE FROM {session}
    WHERE id = %(uuid)s AND secret_hash = crypt(%(password)s,secret_hash)
    RETURNING id;
    """.format(session=true_tablename('sessions'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(remove_session_query,{'uuid':uuid,'password':secret})
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
        cursor.execute(new_user,{
            'name':name,
            'email':__lowercase_email(email),
            })
        return cursor.fetchall()

def get_registered_user(email:str):
    """
    Check the id of a user from an email.
    """
    valid_columns = ['id','email','register_date','verify_date']
    return __get_simple_table('identities',valid_columns=valid_columns,columns_to_get=valid_columns,column_query={'email':email})

def __authenticate_user(sessionid:str,sessionpassword:str):
    """
    Check user session is authenticated and get user.
    """

    get_user = """
    SELECT {identity}.id,{identity}.name,{identity}.email
    FROM {identity}
        INNER JOIN {session}
        ON {session}.identity_id = {identity}.id
        WHERE {session}.id = %(uuid)s AND secret_hash = crypt(%(password)s,secret_hash)
    """.format(identity=true_tablename('identities'),session=true_tablename('sessions'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(get_user,{'uuid':sessionid,'password':sessionpassword})
        if cursor.rowcount == 0:
            raise SantaErrors.SessionError("Session not found or wrong password.")
        return cursor.fetchone()
    
def get_authenticated_user(sessionid:str,sessionpassword:str):
    """
    get info about session user
    """
    return __authenticate_user(sessionid,sessionpassword)
