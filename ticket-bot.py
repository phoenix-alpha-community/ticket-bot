#!/usr/bin/env python3

import discord
import discord.utils as utils
import typing
from discord.ext import commands
from config import *  # imports token, description etc.

bot = commands.Bot(command_prefix=BOT_CMD_PREFIX, description=BOT_DESCRIPTION)


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


################################################################################
## Bot commands
################################################################################


################################################################################
## Utility functions and classes
################################################################################

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
