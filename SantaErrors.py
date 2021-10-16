""" Custom Errors for the SecSocSanta API
"""

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