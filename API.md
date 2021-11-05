# API usage reference

The API passes JSON data over HTTP with the request path determining the function to use.
No additional headers are needed to make the requests,
but some methods do require credentials to also be passed.

All GET request use uri requests keys to provide parameters.
All POST requests use a json body to provide parameters.

All requests should return json. They will also return a property `status` that will indicate success. If the value is `ok` the call worked and you
might be provided more information by other parameters. If the value is `error` you can check the property `errordetail` for an exception message.

## methods

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

* state: the new state, this should be the same as the input on a successful run.

### get your results

`/user?code=<pubkey>&name=<registrationName>` GET

This allows register people to get their results of the draw. It will only provide results if the code matches a game that is in state `1` (has ran).

Result:

* name: provided user name
* giftee: Name of person that user should buy for.
* ideas[]: list of ideas provided from the pool.


### Check a game exists

`/game?code=<pubkey>` GET

This allows you to get the same of the game if it exists.

Result:

* name: Name of the group originally set by `/new`