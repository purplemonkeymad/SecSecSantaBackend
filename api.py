import os
from flask import Flask, request

app = Flask(__name__)

# helper functions

# endpoints

# /game  :
# retrive the status of a game or set a status
# GET /game?name=<name>
#   Return details of the named game or an error mesage if it does not exist.

# POST /game
#    {name: <name>,secret: <key>,status: <0-3>}
#    Sets the game <name> to selected status, uses the secret to authenticate.
@app.route('/game', methods=['GET','POST'])
def game():
    return 'hello'
# For dev local runs, start flask in python process.

if __name__ == '__main__':
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port)