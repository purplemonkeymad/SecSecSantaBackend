""" Custom Errors for the SecSocSanta API
"""

import traceback

class PublicError(Exception):
    """
    Class used to indicate that the exception message is ok for public display. Ie error is a nice message.
    """

class PrivateError(Exception):
    """
    Class used to indicate that the exception message is not ok for public display. These are internal state errors or
    errors that might contain stack traces.
    """

class AuthorizationError(PublicError):
    pass

class ConfigurationError(PrivateError):
    """ Used to indicated errors due to the current
    configuration of the application.
    """
    pass

class GameStateError(PrivateError):
    """
    Indicates issues with the current state of a 
    game.
    """
    pass

class GameChangeStateError(PublicError):
    """
    Indicates error when changing the state of a game.
    """

class SessionError(PublicError):
    """
    Errors for Session management.
    """

class NotFound(PublicError):
    """
    A generic not found class for public messages about missing objects, i.e. bad group ids etc.
    """

def exception_as_string(exception) -> str:
    return traceback.format_exception(etype=type(exception), value=exception, tb=exception.__traceback__)