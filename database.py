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
    dburl = urllib.parse.urlparse(os.environ['DATABASE_URL'])
    dbConn = psycopg2.connect( database=dburl.path[1:], user=dburl.username, password=dburl.password, host=dburl.hostname, port=dburl.port)
    dbCursor = dbConn.cursor(cursor_factory=RealDictCursor)
else:
    print("DATABASE_URL not set any database connections will fail!")


# state setup

if os.environ.get('IS_PROD',0) == 1:
    table_prefix = "prod"
else:
    table_prefix = "dev"
realm_name = "santa"

# internal funcs

def true_tablename(tablename):
    return "{}_{}_{}".format(table_prefix,realm_name,tablename)

# external funcs

def get_users(query:dict, properties:list = ['id','name','game','state'] ):

    # valid properties
    valid_properties = ['id','name','game','state']
    # whitelist good property names
    invalid_properties = [x for x in properties if x not in valid_properties]
    if (invalid_properties):
        raise KeyError("Invalid properties {props} called to get_users. The valid list of properties are: {valid}".format(props=invalid_properties,valid=valid_properties))

    # whitelist good query names
    invalid_query_names = [x for x in query.keys() if x not in valid_properties]
    if (invalid_query_names):
        raise KeyError("Invalid query column {props} called to get_users. The valid list of columns are: {valid}".format(props=invalid_query_names,valid=valid_properties))

    # convert querykeys to string
    query_keys = ' AND '.join( [ " {key} = %({key})s ".format(key=k) for k in query.keys() ] )
    user_query = "SELECT {props} FROM {users} WHERE {query_string};".format(users=true_tablename('users'),props=properties,query_string=query_keys)
    dbCursor.execute(user_query,{'gameid':query})
    return dbCursor.fetchall()
