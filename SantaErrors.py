""" Custom Errors for the SecSocSanta API
"""

import traceback

class AuthorizationError(Exception):
    pass

class ConfigurationError(Exception):
    """ Used to indicated errors due to the current
    configuration of the application.
    """
    pass

class GameStateError(Exception):
    """
    Indicates issues with the current state of a 
    game.
    """
    pass

class GameChangeStateError(Exception):
    """
    Indicates error when changing the state of a game.
    """

class SessionError(Exception):
    """
    Errors for Session management.
    """

def exception_as_string(exception) -> str:
    return traceback.format_exception(etype=type(exception), value=exception, tb=exception.__traceback__)