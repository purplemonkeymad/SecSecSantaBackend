"""
Module for sending emails on sign-in etc.
"""

import os

# sendgrid module
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import SantaErrors

#templating
import jinja2

jin_env = jinja2.Environment(loader=jinja2.FileSystemLoader('EmailTemplates/'))

if 'SENDGRIDAPIKEY' not in os.environ:
    print("SendGrid API key missing, email attempts will fail.")

def __get_sendgrid_api_key():
    if 'SENDGRIDAPIKEY' not in os.environ:
        raise SantaErrors.ConfigurationError("No Mail API Key.")
    key = os.environ.get('SENDGRIDAPIKEY','')
    if len(key) == 0:
        raise SantaErrors.ConfigurationError("Mail API Key empty or missing.")
    return key

def __send_mail_message(message:Mail):
    try:
        api_client = SendGridAPIClient(__get_sendgrid_api_key())
        result = api_client.send(message)
        print("Email Send: {} {}".format(result.status_code,result.body))
    except Exception as e:
        print("Email Send Error: {}".format(SantaErrors.exception_as_string(e)))
        raise SantaErrors.SessionError("Unable to login at this time.")

def resolve_template_file(filename:str,**template_values):
    """
    resolve a template file with only a specific set of
    values
    """
    real_filename = "{}.html".format(filename)
    template = jin_env.get_template(real_filename)
    return template.render(**template_values)

def resolve_template(string:str,**template_values):
    """
    resolve a template from a string, with only a specific set of values
    """
    template = jin_env.from_string(string)
    return template.render(**template_values)

def send_email(to:str,subject:str,template_name:str,**template_values):
    """
    send an email to an address given, using the given template settings
    """
    new_email = Mail(
        from_email='secret-santa@em5031.santa.brettle.org.uk',
        to_emails=to,
        subject=subject,
        html_content=resolve_template_file(template_name,**template_values)
    )
    __send_mail_message(new_email)

def send_logon_email(email:str,display_name:str,code:str):
    """
    Send a logon email with the verification code.
    """

    send_email(email,"New Logon request for Secret Santa.",'Newlogin',name=display_name,code=code)