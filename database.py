# Interface for SQL calls,

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

# internal funcs

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


# external funcs

def get_users(query:dict, properties:list = ['id','name','game'] ):
    """ Gets a user from a game by id,game etc.
    """
    # valid properties
    valid_properties = ['id','name','game','santa']
    return __get_simple_table('users',properties,query,valid_properties)

def get_game(query:dict, properties:list = ['id','name','code','state'] ):
    """ Gets a game from id/code etc.
    """
    # valid properties
    valid_properties = ['id','name','secret','code','state']
    return __get_simple_table('games',properties,query,valid_properties)

def new_game(name:str,privkey:str,pubkey:str):
    """ Inserts a new game into the database.
    """
    query = "INSERT INTO {} VALUES(DEFAULT,%(name)s,%(privkey)s,%(pubkey)s,0) RETURNING id,name,code,state,secret ;".format(true_tablename('games'))
    with __dbConn, __dbConn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query,{'name':name,'privkey':privkey,'pubkey':pubkey})
        return cursor.fetchall()

def get_idea(query:dict, properties:list = ['id','game','idea']):
    """ Gets ideas from game/id
    """
    valid_properties = ['id','game','idea','userid']
    return __get_simple_table('ideas',properties,query,valid_properties)

# owner funcs
# all funcs should check the game secret is correct.

def get_users_in_game(code:str,secret:str,properties:list = ['id','name','game']):
    """List of users that have joined a game
    """

    # not all properties here so game owners can't see info about relations
    valid_properties = ['id','name','game']
    # test for bad properties
    __assert_columns(properties,valid_properties)

    if (len(code) == 0 or len(secret) ==0 ):
        raise ValueError("Gameid or Secret are empty, both values are required.")

    get_userlist_query = """
    SELECT {users}.name FROM {users} INNER JOIN {games} ON {games}.id = {users}.game WHERE {games}.code = %(code)s AND {games}.secret = %(secret)s;
    """.format(users=true_tablename('users'),games=true_tablename('games'))

    __dbCursor.execute(get_userlist_query,{'code':code,'secret':secret})
    return __dbCursor.fetchall()

# admin funcs

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