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

4. Set configuration values key:

        heroku config:set AdminSecret=<yourlongsecretkey>
        heroku config:set DATABASE_URL=<postgresql-dburl>
        heroku config:set SENDGRIDAPIKEY=<sendgridkey>

5. Init the databases:

        heroku config:set AllowTableTruncates=AllowTruncates
        PS> Invoke-RestMethod -Method POST -UseBasicParsing -URI https://your-app-name.herokuapp.com/init_db_tables -Body '{"admin_key": "<yourlongsecretkey>"}'
        heroku config:set AllowTableTruncates=NoTruncates

(or your rest api client of choice)

If you get a status of ok, then the databases should be created. An you can point the frontend at your site or use the api as below.
