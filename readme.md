# Secret Santa Backend

This is the back end api to manage secret Santas.

## Infra

The setup idea is a Heroku app with a postgres database behind it. The database can also be run on Heroku.
It is a python script using flask as the HTTP middleware.

Part of the idea was an api that could be run on the free tier of Heroku accounts.

## Setup

You can run this on your own Heroku by doing the following

1. Clone this repo:

        git clone https://

2. Login to Heroku:

        heroku login

3. Create a app and database:

        heroku create
        heroku addons:create heroku-postgresql:hobby-dev

4. Set a admin key:

        heroku config:set AdminSecret=<yourlongsecretkey>

5. Init the databases:

        PS> Invoke-RestMethod -Method POST -UseBasicParsing -URI https://your-app-name.herokuapp.com/reset -Body '{"admin_key": "<yourlongsecretkey>"}'

(or your rest api client of choice)

If you get a status of ok, then the databases should be created. An you can point the frontend at your site or use the api as below.

## Usage

All GET request use uri requests keys to provide parameters.
All POST requests use a json body to provide parameters.

All requests should return json. They will also return a property `status` that will indicate success. If the value is `ok` the call worked and you
might be provided more information by other parameters. If the value is `error` you can check the property `errordetail` for an exception message.

### a new game

`/new` POST

Body: `{"name":"Game Display Name"}`

Call this endpoint to create a new game that people can submit ideas to and join.

Result:
* name: Display Name of group
* privkey: A Secret key to managed the group (keep this to yourself)
* pubkey: A short key to share with people to join the group, they use this to submit ideas, register, and to get their results.

### register a user for a game

`/user` POST

Body: `{"name":"Someone's Name", "code": "<pubkey>"}`

Call this endpoint to register yourself as a person in the secret santa pool. Make sure you keep your name, as it is also your retrieval key.

Result:
* None status only.

### submit an gift idea

`/idea` POST

Body: `{"idea":"Your idea text","code": "<pubkey>"}`

Call this endpoint to add a new gift idea to the pool of ideas for each santa.

Result:
* None status only.

### do the draw

`/game` POST

Body: `{"code":"<pubkey>", "secret": "<privkey>, "state": <0|1|2>}`

This allows you to manage the current state of the group. The default state is `0`, this is open for registrations and ideas.
Moving to state 1 will run the selection, at this point users can retrieve their giftees and ideas.
Moving to state 2 will close the group and remove and ideas and users. You will have to register a new group if it is moved to state 2.

All actions need the privkey that was sent as the results of calling `/new` if you don't have it you can't admin the game.

Result:
* TBD