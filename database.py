# Interface for SQL calls,

import os
# database
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor

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

if os.environ.get('IS_PROD',0) == 1:
    __table_prefix = "prod"
else:
    __table_prefix = "dev"
__realm_name = "santa"

# internal funcs

def true_tablename(tablename):
    return "{}_{}_{}".format(__table_prefix,__realm_name,tablename)

def __stringlist_to_sql_columns(columns:list) -> str:
    return ','.join(columns)


def __get_simple_table(table_name:str,columns_to_get:list,column_query:dict,valid_columns:list):
    # prevent a get all of table without a query
    if (len(column_query) == 0):
        raise KeyError("Simple database lookup requires at least one column lookup.")

     # whitelist good property names
    invalid_properties = [x for x in columns_to_get if x not in valid_columns]
    if (invalid_properties):
        raise KeyError("Invalid properties {props} for database query. The valid list of properties are: {valid}".format(props=invalid_properties,valid=valid_columns))

    # whitelist good query names
    invalid_query_names = [x for x in column_query.keys() if x not in valid_columns]
    if (invalid_query_names):
        raise KeyError("Invalid query column {props} for database query. The valid list of columns are: {valid}".format(props=invalid_query_names,valid=valid_columns))

    query_keys = ' AND '.join( [ " {key} = %({key})s ".format(key=k) for k in column_query.keys() ] )
    user_query = "SELECT {props} FROM {table} WHERE {query_string};".format(table=true_tablename(table_name),props=__stringlist_to_sql_columns(columns_to_get),query_string=query_keys)
    __dbCursor.execute(user_query,column_query)
    return __dbCursor.fetchall()


# external funcs

def get_users(query:dict, properties:list = ['id','name','game','santa'] ):

    # valid properties
    valid_properties = ['id','name','game','santa']
    return __get_simple_table('users',properties,query,valid_properties)

def get_game(query:dict, properties:list = ['id','name','code','state'] ):

    # valid properties
    valid_properties = ['id','name','secret','code','state']
    return __get_simple_table('games',properties,query,valid_properties)
