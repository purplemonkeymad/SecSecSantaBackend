""" Custom Errors for the SecSocSanta API
"""

class AuthorizationError(Exception):
    pass

class ConfigurationError(Exception):
    """ Used to indicated errors due to the current
    configuration of the application.
    """
    pass