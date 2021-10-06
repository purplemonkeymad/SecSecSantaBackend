"""
More complex functions for the Santa, contains logic for more
that just reading a writting the database. Ie new game/triggering a draw etc.
"""

import database

import string
import random

import SantaErrors

import traceback

__password_pool = list( string.ascii_letters + string.digits )
def __new_password(length=8):
    temp_pass = random.choices(__password_pool,k=length)
    return ''.join(temp_pass)

def __chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def __exception_as_string(exception) -> str:
    return traceback.format_exception(etype=type(exception), value=exception, tb=exception.__traceback__)

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

# get game info from the code.
# the function raises exceptions as a way of providing error failures.
def get_game(code):
    """ provides a safe way to get a game, with errors thrown for common issues.
    """
    if not code:
        raise Exception('Property code is missing or empty.')
    
    try:
        game_list =  database.get_game({'code':code},properties=['name','state','id'])
    except Exception as e:
        print("get_game error, {}".format(e))
        raise Exception("Error fetching games")
    else:
        if len(game_list) == 0:
            raise Exception("Not Found")
        return game_list[0]

def update_game_state(code:str,secret:str,new_state:int):
    """
    Change the state of a game, moving it forward.
    """
    current_game = database.get_game({'code':code,'secret':secret})[0]
    current_state = current_game['state']

    if current_state == 2:
        # closed
        if new_state == 2:
            raise SantaErrors.GameChangeStateError("Game Already closed")
        else:
            raise SantaErrors.GameChangeStateError("Games cannot be reopened.")
    
    elif current_state == 1:
        # a run game
        if new_state == 2:
            return database.set_game_state(code,secret,new_state)
        elif new_state == 1:
            raise SantaErrors.GameChangeStateError("Game already resolved.")
        else:
            raise SantaErrors.GameChangeStateError("Game cannot be un-run")
    
    elif current_state == 0:
        # is a new game
        if new_state == 2:
            return database.set_game_state(code,secret,new_state)
        elif new_state == 0:
            raise SantaErrors.GameChangeStateError("Game already open.")
        elif new_state == 1:
            return __run_game(code,secret)
    else:
        raise SantaErrors.GameStateError("Game in unknown state {}, cannot change state.".format(str(current_state)))

def __run_game(code:str,secret:str):
    # game has two parts, ideas, santas
    # each user is given another user to be santa of
    # each user is also given two unique ideas from the idea pool
    
    #all users
    all_users = database.get_users_in_game(code,secret)
    if len(all_users) < 2:
        raise SantaErrors.GameChangeStateError("game requires more than 2 users to run.")

    # get ideas
    all_ideas = database.get_game_ideas(code,secret)
    if len(all_ideas) < len(all_users) * 2:
        raise SantaErrors.GameChangeStateError("game requires at least 2 ideas per user")

    # assing users to santa's
    random.shuffle(all_users)
    try:
        last_user = all_users[-1]
        for user in all_users:
            database.set_user_santa(user['id'], last_user['id'],code,secret)
            last_user = user
    except Exception as e:
        print("Gamerun: {gameid}, User update failure: {exception}".format(gameid=code,exception=__exception_as_string(e)))
        raise SantaErrors.GameChangeStateError("Unable to assign santas.")

    random.shuffle(all_ideas)
    idea_chunks = list(__chunks(all_ideas,2))
    try:
        for i in range(0, len(all_users)):
            for j in idea_chunks[i]:
                database.set_idea_user(j['id'],all_users[i]['id'],code,secret)
    except Exception as e:
        print("Gamerun: {gameid}, Idea update failure: {exception}".format(gameid=code,exception=__exception_as_string(e)))
        raise SantaErrors.GameChangeStateError("Unable to assign ideas")
    
    database.set_game_state(code,secret,1)

    print("Gamerun: {gameid}, Complete".format(gameid=code))