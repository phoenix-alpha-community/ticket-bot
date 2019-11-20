# Installation
1. Install dependencies
2. Copy `config-sample.py` to `config.py`
3. Open `config.py` and change the required settings

## Dependencies
- [discord.py](https://github.com/Rapptz/discord.py)
- pytz

You can install these via `pip install -r requirements.txt`

NOTE: You might get an error about not having `qdarkstyle<2.7` installed.
You can ignore that.

# Usage
To start, run `python3 ticket-bot.py`.

To stop, hit `CTRL+C`.

# Commands
Most of the features are activated via emoji reactions and are quite
self-explanatory.
Setup and light troubleshooting are handled via chat commands.

### Ticketmenu
`+ticketmenu GAME_NAME CATEGORY_ID #LOG_CHANNEL #TRANSCRIPT_CHANNEL
@SUPPORT_ROLE`

Creates the entry message that people can use to create tickets.
The `GAME_NAME` will be displayed in the header and description.
New tickets are moved into the category linked to `CATEGORY_ID`.
Creating, locking, unlocking and deleting tickets spawns log messages in the
`#LOG_CHANNEL`.
Locking channels also saves a transcript of the ticket channel to
`#TRANSCRIPT_CHANNEL`.
Repeatedly locking the same ticket will overwrite the transcript.
On creation, only the ticket author and members of the `@SUPPORT_ROLE` can see
the ticket channel.

### Invite
`+invite @USER`

Invite a third-party user into a ticket channel, giving them read and write
access.
Undoing this requires manually changing the channel permissions.
This command can only be used by the `@SUPPORT_ROLE`.

### Recount
`+recount`

The ticket bot keeps track of how many tickets each user has created and
ignores requests for new tickets while they're over limit.
Neither closed nor deleted tickets count towards this limit.
The tracking of the amount of open tickets breaks if a ticket channel is
deleted manually without using the ticket bot's deletion feature.
To restore the cached tickets amounts to a valid state, simply run the
`recount` command.
