"""
More complex functions for the Santa, contains logic for more
that just reading a writting the database. Ie new game/triggering a draw etc.
"""

import database

import string
import random
import uuid
import re

import SantaErrors
from SantaErrors import exception_as_string
import santamail

import traceback

__password_pool = list( string.ascii_letters + string.digits )
def __new_password(length=8):
    temp_pass = random.choices(__password_pool,k=length)
    return ''.join(temp_pass)

__verify_pool = list( string.digits )
def __new_verify(length=6):
    temp_pass = random.choices(__verify_pool,k=length)
    return ''.join(temp_pass)

def __chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def create_pubkey():
    """A new Short key
    """
    newkey = __new_password(length=8)
    failcounts = 6
    while len(database.get_game({'code':newkey},properties=['id','code'])) != 0 and failcounts > 1:
        newkey = __new_password(length=8)
        failcounts = failcounts - 1
    if failcounts == 0:
        raise SantaErrors.Exists("Unable to create a new ID")
    return newkey

def create_privkey():
    """Get a new long key.
    """
    return __new_password(length=64)

def create_game(name:str,sessionid:str,sessionpassword:str):
    """Generate a new game
    """
    game_code = create_pubkey()

    game = database.new_game(name,game_code,sessionid,sessionpassword)
    if isinstance(game,list):
        game = game[0]
    # db and api have different key names.
    return {'name':game['name'],'pubkey':game['code']}

# get game info from the code.
# the function raises exceptions as a way of providing error failures.
def get_game(code):
    """ provides a safe way to get a game, with errors thrown for common issues.
    """
    if not code:
        raise SantaErrors.EmptyValue('Property code is missing or empty.')
    
    game_list =  database.get_game({'code':code},properties=['name','state','id'])
    if len(game_list) == 0:
        raise SantaErrors.NotFound("Group id was Not Found.")
    if isinstance(game_list,list):
        game_list = game_list[0]
    return game_list

def update_game_state(code:str,sessionid:str,sessionpassword:str,new_state:int):
    """
    Change the state of a game, moving it forward.
    """

    owner = database.get_authenticated_user(sessionid,sessionpassword)

    current_game = database.get_game({'code':code,'ownerid':owner['id']})
    if len(current_game) == 0:
        raise SantaErrors.GameChangeStateError("Game not found or not owned.")
    if isinstance(current_game,list):
        current_game = current_game[0]
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
            return database.set_game_state(code,sessionid,sessionpassword,new_state)
        elif new_state == 1:
            raise SantaErrors.GameChangeStateError("Game already resolved.")
        else:
            raise SantaErrors.GameChangeStateError("Game cannot be un-run")
    
    elif current_state == 0:
        # is a new game
        if new_state == 2:
            return database.set_game_state(code,sessionid,sessionpassword,new_state)
        elif new_state == 0:
            raise SantaErrors.GameChangeStateError("Game already open.")
        elif new_state == 1:
            return __run_game(code,sessionid,sessionpassword)
    else:
        raise SantaErrors.GameStateError("Game in unknown state {}, cannot change state.".format(str(current_state)))

def __run_game(code:str,sessionid:str,sessionpassword:str):
    # game has two parts, ideas, santas
    # each user is given another user to be santa of
    # each user is also given two unique ideas from the idea pool
    
    owner = database.get_authenticated_user(sessionid,sessionpassword)

    #all users
    all_users = database.get_users_in_game(code,sessionid,sessionpassword)
    if len(all_users) < 2:
        raise SantaErrors.GameChangeStateError("game requires more than 2 users to run.")

    # get ideas
    all_ideas = database.get_game_ideas(code,sessionid,sessionpassword)
    if len(all_ideas) < len(all_users) * 2:
        raise SantaErrors.GameChangeStateError("game requires at least 2 ideas per user")

    # assing users to santa's
    random.shuffle(all_users)
    try:
        last_user = all_users[-1]
        for user in all_users:
            database.set_user_santa(user['id'], last_user['id'],code,sessionid,sessionpassword)
            last_user = user
    except Exception as e:
        print("Gamerun: {gameid}, User update failure: {exception}".format(gameid=code,exception=exception_as_string(e)))
        raise SantaErrors.GameChangeStateError("Unable to assign santas.")

    random.shuffle(all_ideas)
    idea_chunks = list(__chunks(all_ideas,2))
    try:
        for i in range(0, len(all_users)):
            for j in idea_chunks[i]:
                database.set_idea_user(j['id'],all_users[i]['id'],code,sessionid,sessionpassword)
    except Exception as e:
        print("Gamerun: {gameid}, Idea update failure: {exception}".format(gameid=code,exception=exception_as_string(e)))
        raise SantaErrors.GameChangeStateError("Unable to assign ideas")
    
    database.set_game_state(code,sessionid,sessionpassword,1)

    print("Gamerun: {gameid}, Complete".format(gameid=code))


def join_game(user_name:str,code:str,sessionid:str,sessionpassword:str):
    """
    Join a game as a user.
    """
    join_game = database.join_game(user_name,code,sessionid,sessionpassword)

    if len(join_game) == 0:
        raise SantaErrors.NotFound("Unable to locate game.")

    if isinstance(join_game,list):
        join_game = join_game[0]

    return {
        'name':join_game['name'],
        'code':code,
        'join_status':join_game['status'],
    }

def get_game_sum(code:str,sessionid:str,sessionpassword:str):
    """
    Get a summary of a group status.
    """

    if (len(code) == 0):
        raise SantaErrors.EmptyValue("Group code is empty.")

    result = database.get_game_sum(code,sessionid,sessionpassword)
    return result

def get_game_results(code:str,sessionid:str,sessionpassword:str):
    """
    Get the assigned santa and ideas for a given game
    """

    if (len(code) == 0):
        raise SantaErrors.EmptyValue("Group code is empty.")
    
    game = database.get_game({'code':code},['state'])
    if isinstance(game,list):
        game = game[0]
    
    if game['state'] == 0:
        raise SantaErrors.GameStateError("Game not rolled, can't get results yet.")

    if game['state'] == 1:
        user = database.get_authenticated_user(sessionid,sessionpassword)

        giftee = database.get_user_giftee(user['id'],code)
        if isinstance(giftee,list):
            giftee = giftee[0]
        
        ideas = database.get_user_ideas(user['id'],code)
        idea_list = [x['idea'] for x in ideas]
        if len(idea_list) == 0:
            SantaErrors.GameStateError("No ideas assigned.")

        return {
            'giftee': giftee['giftee'],
            'ideas': idea_list,
            'code': code,
        }

    if game['state'] == 2:
        raise SantaErrors.GameStateError("Game is closed.")
    
    print("Error: Game {} in invalid game state {}".format(code,game['state']))
    raise SantaErrors.GameStateError("Unknown game state.")


#####################
# login logic
#####################

def new_session(email:str):
    """
    create a new session id an verify code from an email address
    will error if user not registered
    """

    verify_code = __new_verify()
    session_id = str(uuid.uuid4())
    new_session_data = database.new_session(session_id,email,verify_code)
    if len(new_session_data) == 0:
        raise SantaErrors.SessionError("Need registration")
    if isinstance(new_session_data,list):
        new_session_data = new_session_data[0]
    
    # need to both send session id back to 
    # web client & send code via email

    santamail.send_logon_email(email,new_session_data['name'],verify_code)

    return {
        'session':session_id,
    }

def register_new_user(email:str,name:str):
    """
    Create a new user id and attempt a logon
    """

    # if has an at sign and at least one char each side, could be an email, accept it.
    if re.search('.+@.+',email) == None:
        # fails to match
        raise SantaErrors.SessionError("Not a valid email address.")
    
    # error if already registered
    check_user = database.get_registered_user(email)
    if len(check_user) > 0:
        raise SantaErrors.SessionError("Already registered.")

    database.register_user(email,name)
    return new_session(email)
    
def verify_session(sessionid:str,code:str,new_secret:str):
    """
    Verify the session with the sent code, a new secret
    is needs for future use of this session.
    """
    if len(code) != 6:
        raise SantaErrors.SessionError("Verify codes must be 6 charaters long.")
    if len(new_secret) < 16:
        raise SantaErrors.SessionError("New Secrets must be at least 16 charaters.")
    try:
        uuid.UUID(sessionid)
    except ValueError as e:
        raise SantaErrors.SessionError("Session ids must be a uuid format")

    results = database.confirm_session(sessionid,code,new_secret)
    if len(results) == 0:
        raise SantaErrors.SessionError("Session id or verify code was not found.")
    if isinstance(results,list):
        results = results[0]
    return {
        'session':results['id'],
    }
    