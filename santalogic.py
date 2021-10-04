"""
More complex functions for the Santa, contains logic for more
that just reading a writting the database. Ie new game/triggering a draw etc.
"""

import database

import string
import random

__password_pool = list( string.ascii_letters + string.digits )
def __new_password(length=8):
    temp_pass = random.choices(__password_pool,k=length)
    return ''.join(temp_pass)

def create_pubkey():
    """A new Short key
    """
    newkey = __new_password(length=8)
    failcounts = 6
    while len(database.get_game({'code':newkey},properties=['id','code'])) != 0 and failcounts > 1:
        newkey = __new_password(length=8)
        failcounts = failcounts - 1
    if failcounts == 0:
        raise TimeoutError("Unable to create a new ID")
    return newkey

def create_privkey():
    """Get a new long key.
    """
    return __new_password(length=64)

def create_game(name:str):
    """Generate a new game
    """
    game_code = create_pubkey()
    game_secret = create_privkey()

    game = database.new_game(name,game_secret,game_code)[0]
    # db and api have different key names.
    return {'name':game['name'],'privkey':game['secret'],'pubkey':game['code']}