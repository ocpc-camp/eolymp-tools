This is a script that will send a message to the development Discord server
whenever someone asks a question on Eolymp.

This script should be kept running in a server, for example, by running

```
python pinger.py > pinger.log &
```

Before that though, you need to set up the .env file. The template for that
is in the .env.sample file. Make the necessary changes and save it as .env

The following changes need to be made:

EOLYMP_SPACE should be the short name of the Eolymp space for your event.

EOLYMP_TOKEN should be the access token. Because this script will be running
through the entire camp, you should create an access key, which you can do
at https://developer.eolymp.com/. Give it the following scopes:

```
helpdesk:ticket:read helpdesk:ticket:write judge:contest:read judge:contest:write
```

HOOK_URL should be the webhook URL that you can create in Discord settings;
DISCORD_ROLE is the numeric ID of the role that should receive pings.