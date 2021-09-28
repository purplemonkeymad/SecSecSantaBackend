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
    __dbCursor.execute(user_query,query)
    return __dbCursor.fetchall()
