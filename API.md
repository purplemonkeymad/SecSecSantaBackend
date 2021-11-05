# API usage reference

The API passes JSON data over HTTP with the request path determining the function to use.
No additional headers are needed to make the requests,
but some methods do require credentials to also be passed.

All GET request use uri requests keys to provide parameters.
All POST requests use a json body to provide parameters.

All requests should return json. They will also return a property `status` that will indicate success. If the value is `ok` the call worked and you
might be provided more information by other parameters. If the value is `error` you can check the property `errordetail` for an exception message.

## Login and Registration Methods

### Register for account

`/auth/register` POST

Register for an account to login. Will automatically start the login process as well, see the `/auth/new_session` method for more info.
A successful login is counted as verifying that the account is valid.

Required Keys:

* `email`: Email address to register with (use for login verification.)
* `name`: Display Name for your account (will be used as the default join name.)

Example Body: `{"email":"myname@example.com","name":"John Doe"}`

Result:

* session: Logon session id for this device.

### Login to an account

`/auth/new_session` POST

Start the login process for a registered account.
This only takes an email as each logon event is verified using an email send to the registered address.
The api will provide you with a session id that will be used for any authenticated calls to api methods.
Sessions will need to be verified before they can be used for other api methods, see the `/auth/verify_session` method.

Required Keys:

* `email`: Email address to logon to.

Example Body: `{"email":"myname@example.com"}`

Result:

* session: Logon session id for this device.

### Verify a logon

`/auth/verify_session` POST

Verify a logon using a verify code that was sent via email.
This also required a password that will be used to authenticate this session to the API.
Each logon session should have a unique password, this should be stored locally on the device and does not need to be known by the account holder.

Required Keys:

* `session`: Session id that was provided at the beginning of the login process or at registration.
* `code`: Verify code that was send by email for this specific session.
* `secret`: A new random secret that this device can use to authenticate itself.

Example Body: `{"session":"af2276be-839a-47e9-9c2e-11aa895936e2","code":"000000",secret=<long random letters>}`

Result:

* session: Id of session that was just authenticated.

### Logout

`/auth/end_session` POST

Logout and destroy the current session.

Required Keys:

* `session`: Session id that identifies this session (the current device.)
* `secret`: The stored secret first created during the verify stage.

Example Body: `{"session":"af2276be-839a-47e9-9c2e-11aa895936e2",secret=<long random letters>}`

Result:

* session: Id of session that was logged out.

## Group management

Groups are referred to games a lot of the time within the code,
if there is any references to a game, this is the same as a Group.

### Create a new group

`/new` POST

Create a new group.
Each group is a pool of people and ideas that will be drawn for the secret santa.

Required Keys:

* `name`: Display Name of the group, visible to everyone.
* `session`: Session id that identifies this session (the current device.) The owner of this session will become the owner of the Group.
* `secret`: The stored secret first created during the verify stage.

Example Body: `{"Name":"Example Group Name","session":"<session id>",secret=<long random letters>}`

Result:

* name: Display Name of group
* pubkey: A short code to share with people to join the group, it is also used to identify this group to other API methods.

### List owned groups

`/game/owned` POST

List all of the groups that your account is an owner of.

Required Keys:

* `session`: Session id that identifies this session (the current device.) The owner of this session will be used as the target account to get groups for.
* `secret`: The stored secret first created during the verify stage.

Result:

* grouplist: A list of group objects. Each object will have the following properties:

    * name: Display Name of the group
    * code: Join code of this group
    * state: Current state of the game, 0=Open,1=Resolved,2=Closed

### List group summary

`/game_sum` POST

List a few owner privileged values about the group given.

Required Keys:

* `code`: Join code for the group that you want to retrieve summary info for.
* `session`: Session id that identifies this session (the current device.) The owner of this session will be used as the target account to get groups for.
* `secret`: The stored secret first created during the verify stage.

Result:

* name: Display Name of the requested group.
* state: Current State of the group, 0=Open, 1=Resolved, 2=Closed.
* santas: The current number of people joined to the group.
* ideas: The current number of submitted gift suggestions to the group.

### Roll or Close a group

`/game` POST

Update the status of a group.
The available states depend on the current state.
Open groups can be moved to Rolled or closed. Rolled groups can be moved to closed.

Required Keys:

* `code`: Join code for the group that you want to retrieve summary info for.
* `state`: New state for the group to transition to, 1=Rolled, 2=Closed.
* `session`: Session id that identifies this session (the current device.) The owner of this session will be used as the target account to get groups for.
* `secret`: The stored secret first created during the verify stage.

Result:

* code: Join code of the group.
* state: New State of the group, 0=Open, 1=Resolved, 2=Closed.

## User Group actions

### Join a Group

`/join_game` POST

Join a Group with a particular Group join code. Joining adds an account to the pool of Santas.

Required Keys:

* `code`: Join code for the group that you want to retrieve summary info for.
* `name`: Display Name to join as to the group. Field is required, but an empty value will cause the group to be join using the default display name given during registration.
* `session`: Session id that identifies this session (the current device.) The owner of this session will be used as the target account to join as.
* `secret`: The stored secret first created during the verify stage.

Result:

* name: Display Name of the user that joined.
* code: Join code of the group that was joined.
* gamename: Display Name of the group that was joined.
* join_status: Status of Joining, will be `New` if user joined as a results of this call, will be `Existing` if they were already joined.

### List joined Groups

`/game/joined` POST

list the groups that the current session owner has joined.

Required Keys:

* `session`: Session id that identifies this session (the current device.) The owner of this session will be used as the target account.
* `secret`: The stored secret first created during the verify stage.

Result:

* grouplist: A list of group objects. Each object will have the following properties:

    * name: Display Name of the group
    * code: Join code of this group
    * state: Current state of the game, 0=Open,1=Resolved,2=Closed

### Submit a gift idea

`/idea` POST

Submit a gift suggestion to the specified group.

Required Keys:

* `code`: Join code for the group that you want to retrieve summary info for.
* `idea`: The idea that should be submitted. Max length of 260 ascii chars.
* `session`: Session id that identifies this session (the current device.) The owner of this session will be used as the target account for the action.
* `secret`: The stored secret first created during the verify stage.

Result:

* idea: The idea submitted
* gamename: The name of the group the idea was added.
* ideastatus: Status of idea addition, will be `New` if idea added as a result of this call, will be `Existing` if it already was submitted.


### get your results

`/results` POST

This allows people to get their results of the draw. It will only provide results if the code matches a game that is in state `1` (Rolled).

Required Keys:

* `code`: Join code for the group that you want to target.
* `session`: Session id that identifies this session (the current device.) The owner of this session will be used as the target account for the action.
* `secret`: The stored secret first created during the verify stage.

Result:

* code: Group join code of the results.
* giftee: Name of person that user should buy for.
* ideas[]: list of ideas provided from the pool.

## Public

These Api methods do not required any authenticated session.

### Check a game exists

`/game?code=<pubkey>` GET

This allows you to get the same of the game if it exists.

Result:

* name: Name of the group originally set by `/new`
