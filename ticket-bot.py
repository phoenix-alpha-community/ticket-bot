#!/usr/bin/env python3

import discord
import discord.utils as utils
import typing
import json
import os.path
import re
from discord.ext import commands
from config import *  # imports token, description etc.
from random import randrange

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

@bot.event
async def on_raw_reaction_add(payload):
    rp = await unwrap_payload(payload)
    if rp.member == rp.guild.me:
        return
    if rp.message.author != rp.guild.me:
        return

    await emoji_handlers[rp.emoji.name](rp)


@bot.event
async def on_raw_reaction_remove(payload):
    pass


async def unwrap_payload(payload):
    rp = ReactionPayload()
    await rp._init(payload)
    return rp


async def create_ticket(rp):
    await rp.message.remove_reaction(Emojis.envelope_with_arrow, rp.member)

    title = rp.message.embeds[0].title
    pattern = r"Ticket Menu: ([^\n]+)"
    game_name = re.match(pattern, title).group(1)

    ticket_type = get_state()["ticket_types"][game_name]
    support_role = rp.guild.get_role(ticket_type["support_role_id"])

    category = rp.guild.get_channel(BOT_TICKET_CATEGORY)
    overwrites = {
        rp.guild.default_role:
            discord.PermissionOverwrite(read_messages = False,
                                        send_messages = False),
        support_role:
            discord.PermissionOverwrite(read_messages = True,
                                        send_messages = True),
        rp.guild.me:
            discord.PermissionOverwrite(read_messages = True,
                                        send_messages = True),
        rp.member:
            discord.PermissionOverwrite(read_messages = True,
                                        send_messages = True),
    }

    ticket_id = get_and_inc_ticket_counter()
    channel = await rp.guild.create_text_channel(
                                            "ticket-%04d" % (ticket_id % 10000),
                                            category      = category,
                                            overwrites    = overwrites)

    # Post starting message
    ticket = Ticket(ticket_id, game_name, rp.member, support_role, rp.guild)

    message = await channel.send("", embed = ticket.to_embed())
    await message.add_reaction(Emojis.lock)

    # Post log message
    embed = ticket.to_log_embed("Created", 0x00FF00)
    await ticket.log_channel.send("", embed = embed)


async def lock_ticket(rp):
    ticket = await Ticket.from_start_message(rp)

    # only allow reactions from support staff and the author
    if ticket.staff not in rp.member.roles \
        and ticket.author != rp.member:
            rp.message.remove_reaction(Emojis.lock, rp.member)
            return

    await rp.message.clear_reactions()

    await rp.channel.set_permissions(ticket.staff,
                               read_messages = True,
                               send_messages = False)
    await rp.channel.set_permissions(ticket.author,
                               read_messages = True,
                               send_messages = False)
    embed = discord.Embed.from_dict({
        "title"         : "Ticket closed",
        "color"         : 0xFFFF00,
        "description"   : "The ticket was closed and can only be re-opened by"\
                          + " %s." % ticket.staff.mention
    })
    embed.add_field(name = "Closed by", value = rp.member.mention, inline = True)
    message = await rp.channel.send("", embed = embed)

    # Post log message
    embed = ticket.to_log_embed("Locked", 0xFFFF00, [("Locked by", rp.member.mention)])
    await ticket.log_channel.send("", embed = embed)


async def unlock_ticket(rp):
    ticket = await Ticket.from_start_message(rp)

    # only allow reactions from support staff and the author
    if ticket.staff not in rp.member.roles:
        rp.message.remove_reaction(Emojis.lock, rp.member)
        return




@bot.command() # TODO remove
async def gib(ctx, shit):
    print(shit.encode())


@bot.command() # TODO: remove
async def cleartickets(ctx):
    for channel in ctx.guild.channels:
        if channel.name.startswith("ticket-"):
            await channel.delete()


@bot.command()
async def invite(ctx, user : discord.User):
    # TODO: restrict role
    await ctx.channel.set_permissions(user,
                                      read_messages = True,
                                      send_message = True)


@invite.error
async def invite_error(ctx, error):
    error_handlers = {
        commands.errors.MissingRequiredArgument: lambda:
            send_usage_help(ctx, "invite", "@USER"),

        commands.MissingRole: lambda:
            ctx.send("Insufficient rank permissions."),
    }
    await handle_error(ctx, error, error_handlers)


@bot.command()
@commands.has_role(BOT_TICKET_MANAGER_ROLE)
async def ticketmenu(ctx, game_name : str, category_id : int,
                     log_channel : discord.TextChannel,
                     transcript_channel : discord.TextChannel,
                     support_role : discord.Role):
    embed = discord.Embed.from_dict({
        "title"         : "Ticket Menu: %s" % game_name,
        "color"         : 0x0000FF,
        "description"   : "React with %s to create a new ticket for %s." \
                          % (Emojis.envelope_with_arrow, game_name)
    })

    state = get_state()
    state["ticket_types"][game_name] = {
        "category_id"           : category_id,
        "log_channel_id"        : log_channel.id,
        "transcript_channel_id" : transcript_channel.id,
        "support_role_id"       : support_role.id,
    }
    write_state(state)

    message = await ctx.send("", embed = embed)
    await message.add_reaction(Emojis.envelope_with_arrow)


@ticketmenu.error
async def ticketmenu_error(ctx, error):
    error_handlers = {
        commands.errors.MissingRequiredArgument: lambda:
            send_usage_help(ctx, "ticketmenu", "GAME_NAME CATEGORY_ID"\
                                                + " #LOG_CHANNEL"\
                                                + " #TRANSCRIPT_CHANNEL"\
                                                + " @SUPPORT_ROLE"),

        commands.MissingRole: lambda:
            ctx.send("Insufficient rank permissions."),
    }
    await handle_error(ctx, error, error_handlers)


async def handle_error(ctx, error, error_handlers):
    for error_type, handler in error_handlers.items():
        if isinstance(error, error_type):
            await handler()
            return

    await send_error_unknown(ctx)
    raise error


################################################################################
## Utility functions and classes
################################################################################

##############################
# Author: Tim | w4rum
# DateCreated: 11/13/2019
# Purpose: Send an error message to the current chat
###############################
def send_error_unknown(ctx):
    return send_error(ctx, "Unknown error. Tell someone from the programming" \
                      + " team to check the logs.")


##############################
# Author: Tim | w4rum
# DateCreated: 11/13/2019
# Purpose: Send an error message to the current chat
###############################
def send_error(ctx, text):
    return ctx.send("[ERROR] " + text)


##############################
# Author: Tim | w4rum
# DateCreated: 11/13/2019
# Purpose: Send a usage help to the current chat
###############################
def send_usage_help(ctx, function_name, argument_structure):
    return ctx.send("Usage: `%s%s %s`" \
                    % (BOT_CMD_PREFIX, function_name, argument_structure))


class Ticket():
    def __init__(self, ticket_id, game_name, author, staff, guild):
        self.id = ticket_id
        self.game = game_name
        self.author = author
        self.staff = staff
        log_channel_id\
            = get_state()["ticket_types"][self.game]["log_channel_id"]
        self.log_channel = guild.get_channel(log_channel_id)
        transcript_channel_id\
            = get_state()["ticket_types"][self.game]["transcript_channel_id"]
        self.transcript_channel = guild.get_channel(transcript_channel_id)

    async def from_start_message(rp):
        embed = rp.message.embeds[0]

        # fucking kill me please this is horrible coding
        for f in embed.fields:
            if f.name == Strings.field_id: ticket_id = int(f.value)
            if f.name == Strings.field_game: game = f.value
            if f.name == Strings.field_author:
                author_id = int(f.value[2:-1])
                author = await rp.guild.fetch_member(author_id)
            if f.name == Strings.field_staff:
                staff_id = int(f.value[3:-1])
                staff = rp.guild.get_role(staff_id)

        return Ticket(ticket_id, game, author, staff, rp.guild)

    def to_embed(self):
        embed = discord.Embed.from_dict({
            "title"         : "Ticket ID: %d" % self.id,
            "color"         : 0x00FF00,
            "description"   : "If your issue has been resovled, you can close"\
                              + " this ticket with %s." % Emojis.lock
        })
        embed.add_field(name = Strings.field_id, value = self.id, inline = True)
        embed.add_field(name = Strings.field_game, value = self.game, inline = True)
        embed.add_field(name = Strings.field_author,
                        value = self.author.mention, inline = True)
        embed.add_field(name = Strings.field_staff,
                        value = self.staff.mention, inline = True)
        return embed

    def to_log_embed(self, log_prefix, color, additional_fields=[]):
        embed = discord.Embed.from_dict({
            "title"         : "%s: Ticket %d" % (log_prefix, self.id),
            "color"         : color,
        })
        embed.add_field(name = "Game", value = self.game, inline = True)
        embed.add_field(name = "Ticket author", value = self.author.mention, inline = True)
        for name, value in additional_fields:
            embed.add_field(name = name, value = value, inline = True)

        return embed


class ReactionPayload():

    # this might be a bit heavy on the API
    async def _init(self, payload):
        self.guild = bot.get_guild(payload.guild_id)
        self.member = await self.guild.fetch_member(payload.user_id)
        self.emoji = payload.emoji
        self.channel = bot.get_channel(payload.channel_id)
        self.message = await self.channel.fetch_message(payload.message_id)


class Emojis():
    envelope_with_arrow = b'\xf0\x9f\x93\xa9'.decode()
    lock                = b'\xf0\x9f\x94\x92'.decode()
    unlock              = b'\xf0\x9f\x94\x93'.decode()


class Strings():
    field_id = "ID"
    field_game = "Game"
    field_author = "Ticket author"
    field_staff = "Responsible support staff"

emoji_handlers = {
    Emojis.envelope_with_arrow  : create_ticket,
    Emojis.lock                 : lock_ticket,
}


def get_state():
    # default state
    state = json.dumps({
        "ticket_counter" : 0,
        "ticket_types" : {}
    })

    # read state
    filename = "state.txt"
    if os.path.isfile(filename):
        with open("state.txt", "r") as f:
            state = f.read()
    state = json.loads(state)
    return state


def write_state(state):
    with open("state.txt", "w") as f:
        f.write(json.dumps(state))


def get_and_inc_ticket_counter():
    state = get_state()
    state["ticket_counter"] += 1
    write_state(state)

    return state["ticket_counter"]


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
