#!/usr/bin/env python3

import discord
import discord.utils as utils
import typing
import json
import os.path
import re
import io
from discord.ext import commands
from config import *  # imports token, description etc.
from random import randrange
from tempfile import TemporaryFile
from importlib import import_module

ce = import_module("chat-exporter")

bot = commands.Bot(command_prefix=BOT_CMD_PREFIX, description=BOT_DESCRIPTION)


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


###############################################################################
## Bot commands
###############################################################################

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


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Handles creation of tickets on reactions to the ticketmenu
##############################
async def create_ticket(rp):
    await rp.message.remove_reaction(Emojis.envelope_with_arrow, rp.member)

    # check if user is over ticket limit
    count = get_user_ticket_count(rp.member)
    if count >= BOT_TICKET_MAX_PER_USER:
        await rp.member.send("You're over ticket limit: %i/%i" \
                             % (count, BOT_TICKET_MAX_PER_USER))
        return
    else:
        inc_user_ticket_count(rp.member)

    title = rp.message.embeds[0].title
    pattern = r"Ticket Menu: ([^\n]+)"
    game_name = re.match(pattern, title).group(1)

    ticket_type = get_state()["ticket_types"][game_name]
    support_role = rp.guild.get_role(ticket_type["support_role_id"])

    category = rp.guild.get_channel(BOT_TICKET_CATEGORY)
    overwrites = {
        rp.guild.default_role:
            discord.PermissionOverwrite(read_messages=False,
                                        send_messages=False),
        support_role:
            discord.PermissionOverwrite(read_messages=True,
                                        send_messages=True),
        rp.guild.me:
            discord.PermissionOverwrite(read_messages=True,
                                        send_messages=True),
        rp.member:
            discord.PermissionOverwrite(read_messages=True,
                                        send_messages=True),
    }

    ticket_id = get_and_inc_ticket_counter()
    channel = await rp.guild.create_text_channel(
        "ticket-%04d" % (ticket_id % 10000),
        category=category,
        overwrites=overwrites)

    # Post starting message
    ticket = Ticket(ticket_id, game_name, rp.member,
                    support_role, rp.guild)

    message = await channel.send(rp.member.mention, embed=ticket.to_embed())
    await message.add_reaction(Emojis.lock)

    # Post log message
    embed = ticket.to_log_embed("Created", 0x00FF00)
    await ticket.log_channel.send("", embed=embed)


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Locks tickets, removing write access from everyone
##############################
async def lock_ticket(rp):
    ticket = await Ticket.from_start_message(rp.message)

    # only allow reactions from support staff and the author
    if ticket.staff not in rp.member.roles \
            and ticket.author != rp.member:
        await rp.message.remove_reaction(rp.emoji, rp.member)
        return

    dec_user_ticket_count(ticket.author)

    # Update reactions
    await rp.message.clear_reactions()
    await rp.message.add_reaction(Emojis.unlock)
    await rp.message.add_reaction(Emojis.no_entry_sign)

    # Update permissions
    await rp.channel.set_permissions(ticket.staff,
                                     read_messages=True,
                                     send_messages=False)
    await rp.channel.set_permissions(ticket.author,
                                     read_messages=True,
                                     send_messages=False)
    for add_members in ticket.additional_members:
        await rp.channel.set_permissions(add_members,
                                         read_messages=True,
                                         send_messages=False)

    # Post closing message
    embed = discord.Embed.from_dict({
        "title": "Ticket closed",
        "color": 0xFFFF00,
        "description": "The ticket was closed and can only be re-opened by" \
                       + " %s." % ticket.staff.mention
    })
    embed.add_field(name="Closed by", value=rp.member.mention, inline=True)
    embed.add_field(name="Transcript saved to",
                    value=ticket.transcript_channel.mention, inline=True)
    message = await rp.channel.send("", embed=embed)

    # Delete previous transcripts
    async for m in ticket.transcript_channel.history(limit=None):
        for e in m.embeds:
            match = re.match(r"Transcript: Ticket ([0-9]+)", e.title)
            if match != None and int(match.group(1)) == ticket.id:
                await m.delete()

    # Save transcript
    embed = ticket.to_log_embed("Transcript", 0xFF5E00, [("Saved by", rp.member.mention)])
    transcript = await ce.generate_transcript(rp.channel, ticket)
    f = discord.File(io.BytesIO(transcript.encode()),
                     filename="transcript-%04d.html" % ticket.id)
    await ticket.transcript_channel.send("", embed=embed, file=f)

    # Post log message
    embed = ticket.to_log_embed("Locked", 0xFF5E00, [("Locked by", rp.member.mention)])
    await ticket.log_channel.send("", embed=embed)


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Unlocks tickets, granting write access to the appropriate members
##############################
async def unlock_ticket(rp):
    ticket = await Ticket.from_start_message(rp.message)

    inc_user_ticket_count(ticket.author)

    # only allow reactions from support staff
    if ticket.staff not in rp.member.roles:
        await rp.message.remove_reaction(rp.emoji, rp.member)
        return

    # Update reactions
    await rp.message.clear_reactions()
    await rp.message.add_reaction(Emojis.lock)

    # Update permissions
    await rp.channel.set_permissions(ticket.staff,
                                     read_messages=True,
                                     send_messages=True)
    await rp.channel.set_permissions(ticket.author,
                                     read_messages=True,
                                     send_messages=True)
    for add_members in ticket.additional_members:
        await rp.channel.set_permissions(add_members,
                                         read_messages=True,
                                         send_messages=True)

    # Post closing message
    embed = discord.Embed.from_dict({
        "title": "Ticket re-opened",
        "color": 0xFFFF00,
    })
    embed.add_field(name="Re-opened by", value=rp.member.mention, inline=True)
    message = await rp.channel.send("", embed=embed)

    # Post log message
    embed = ticket.to_log_embed("Unlocked", 0xFFD900, [("Unlocked by", rp.member.mention)])
    await ticket.log_channel.send("", embed=embed)


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Makes tickets more like what happened at Tiananmen square
##############################
async def delete_ticket(rp):
    ticket = await Ticket.from_start_message(rp.message)

    # only allow reactions from support staff and the author
    if ticket.staff not in rp.member.roles:
        await rp.message.remove_reaction(rp.emoji, rp.member)
        return

    await rp.message.remove_reaction(rp.emoji, rp.member)
    await rp.message.add_reaction(Emojis.negative_squared_cross_mark)
    await rp.message.add_reaction(Emojis.white_check_mark)


async def delete_confirm(rp):
    ticket = await Ticket.from_start_message(rp.message)

    # only allow reactions from support staff and the author
    if ticket.staff not in rp.member.roles:
        await rp.message.remove_reaction(rp.emoji, rp.member)
        return

    await rp.channel.delete()

    # Post log message
    embed = ticket.to_log_embed("Deleted", 0xFF0000, [("Deleted by", rp.member.mention)])
    await ticket.log_channel.send("", embed=embed)


async def delete_abort(rp):
    ticket = await Ticket.from_start_message(rp.message)

    # only allow reactions from support staff and the author
    if ticket.staff not in rp.member.roles:
        await rp.message.remove_reaction(rp.emoji, rp.member)
        return

    await rp.message.remove_reaction(rp.emoji, rp.member)
    await rp.message.remove_reaction(Emojis.negative_squared_cross_mark, rp.guild.me)
    await rp.message.remove_reaction(Emojis.white_check_mark, rp.guild.me)


# @bot.command() # TODO emoji
# async def gib(ctx, shit):
#    print(shit.encode())


# @bot.command() # TODO: cleartickets
# async def cleartickets(ctx):
#    for channel in ctx.guild.channels:
#        if channel.name.startswith("ticket-"):
#            await channel.delete()


# @bot.command() # TODO: bullshit
# async def dump(ctx):
#    start_message = (await ctx.channel.history(limit=1, oldest_first=True).flatten())[0]
# #    ticket = await Ticket.from_start_message(start_message)
# #    with open("test.html", "w") as f:
#        f.write(await ce.generate_transcript(ctx.channel, ticket))


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Recounts all users' tickets, possibly fixing limit issues
##############################
@bot.command()
@commands.has_role(BOT_TICKET_MANAGER_ROLE)
async def recount(ctx):
    old_counts = get_state()["user_ticket_count"]
    counts = {}
    for channel in ctx.guild.channels:
        if channel.name.startswith("ticket-"):
            start_message = (await channel.history(limit=1, oldest_first=True).flatten())[0]
            ticket = await Ticket.from_start_message(start_message)
            if str(ticket.author.id) not in counts:
                counts[str(ticket.author.id)] = 0
            counts[str(ticket.author.id)] += 1

    state = get_state()
    state["user_ticket_count"] = counts
    write_state(state)

    fixes = 0
    description = "\n"
    for id, c in old_counts.items():
        difference = 0
        if id not in counts and c != 0:
            fixes += 1
            difference = c
        elif id in counts and c != counts[id]:
            fixes += 1
            difference = c - counts[id]

        if difference > 0:
            description += "- Fixed %s: %d\n" \
                           % (await ctx.guild.fetch_member(int(id)), difference)

    if fixes == 0:
        description += "No changes."

    embed = discord.Embed.from_dict({
        "title": "Recount finished",
        "color": 0x00FFFF,
        "description": description,
    })
    await ctx.send("", embed=embed)


@recount.error
async def recount_error(ctx, error):
    error_handlers = {
        commands.errors.MissingRequiredArgument: lambda:
        send_usage_help(ctx, "recount", ""),

        commands.MissingRole: lambda:
        ctx.send("Insufficient rank permissions."),
    }
    await handle_error(ctx, error, error_handlers)


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Invites a third-party member to the ticket
##############################
@bot.command()
async def invite(ctx, user: discord.User):
    if not ctx.channel.name.startswith("ticket-"):
        raise WrongChannelError()

    start_message = (await ctx.channel.history(limit=1, oldest_first=True).flatten())[0]
    ticket = await Ticket.from_start_message(start_message)

    # only allow reactions from support staff and the author
    if ticket.staff not in ctx.author.roles:
        raise commands.MissingRole(ticket.staff.name)

    await ctx.channel.set_permissions(user,
                                      read_messages=True,
                                      send_messages=True)
    await ticket.add_members(user, start_message)
    await ctx.send("Added %s to this ticket." % user.mention)

    # Post log message
    embed = ticket.to_log_embed("Invite", 0xce0fce,
                                [("Inviter", ctx.author.mention),
                                 ("Invitee", user.mention)])
    await ticket.log_channel.send("", embed=embed)


@invite.error
async def invite_error(ctx, error):
    error_handlers = {
        commands.errors.MissingRequiredArgument: lambda:
        send_usage_help(ctx, "kick", "@USER"),
        commands.errors.BadArgument: lambda:
        send_usage_help(ctx, "kick", "@USER"),
        commands.MissingRole: lambda:
        ctx.send("Insufficient rank permissions."),
        WrongChannelError: lambda:
        ctx.send("Command used in wrong channel"),
    }
    await handle_error(ctx, error, error_handlers)


##############################
# Author: Matt | Mahtoid
# DateCreated: 11/17/2019
# Purpose: Kicks a third-party member to the ticket
##############################
@bot.command()
async def kick(ctx, user: discord.User):
    if not ctx.channel.name.startswith("ticket-"):
        raise WrongChannelError()
    start_message = (await ctx.channel.history(limit=1, oldest_first=True).flatten())[0]
    ticket = await Ticket.from_start_message(start_message)

    # only allow reactions from support staff and the author
    if ticket.staff not in ctx.author.roles:
        raise commands.MissingRole(ticket.staff.name)

    if user not in ticket.additional_members:
        raise UserNotInTicketError()
    await ctx.channel.set_permissions(user,
                                      read_messages=False,
                                      send_messages=False)
    await ticket.remove_members(user, start_message)
    await ctx.send("Kicked %s from this ticket." % user.mention)

    # Post log message
    embed = ticket.to_log_embed("Kick", 0x9c0f9c,
                                [("Kicker", ctx.author.mention),
                                 ("Kickee", user.mention)])
    await ticket.log_channel.send("", embed=embed)


@kick.error
async def kick_error(ctx, error):
    error_handlers = {
        commands.errors.MissingRequiredArgument: lambda:
        send_usage_help(ctx, "kick", "@USER"),
        commands.errors.BadArgument: lambda:
        send_usage_help(ctx, "kick", "@USER"),
        UserNotInTicketError: lambda:
        ctx.send("User not in ticket."),
        WrongChannelError: lambda:
        ctx.send("Command used in wrong channel"),
        commands.MissingRole: lambda:
        ctx.send("Insufficient rank permissions."),
    }
    await handle_error(ctx, error, error_handlers)


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Creates a new ticket menu
##############################
@bot.command()
@commands.has_role(BOT_TICKET_MANAGER_ROLE)
async def ticketmenu(ctx, game_name: str, category_id: int,
                     log_channel: discord.TextChannel,
                     transcript_channel: discord.TextChannel,
                     support_role: discord.Role):
    embed = discord.Embed.from_dict({
        "title": "Ticket Menu: %s" % game_name,
        "color": 0x0000FF,
        "description": "React with %s to create a new ticket for %s." \
                       % (Emojis.envelope_with_arrow, game_name)
    })

    state = get_state()
    state["ticket_types"][game_name] = {
        "category_id": category_id,
        "log_channel_id": log_channel.id,
        "transcript_channel_id": transcript_channel.id,
        "support_role_id": support_role.id,
    }
    write_state(state)

    message = await ctx.send("", embed=embed)
    await message.add_reaction(Emojis.envelope_with_arrow)


@ticketmenu.error
async def ticketmenu_error(ctx, error):
    error_handlers = {
        commands.errors.MissingRequiredArgument: lambda:
        send_usage_help(ctx, "ticketmenu", "GAME_NAME CATEGORY_ID" \
                        + " #LOG_CHANNEL" \
                        + " #TRANSCRIPT_CHANNEL" \
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


###############################################################################
## Utility functions and classes
###############################################################################

##############################
# Author: Tim | w4rum
# DateCreated: 11/13/2019
# Purpose: Send an error message to the current chat
##############################
def send_error_unknown(ctx):
    return send_error(ctx, "Unknown error. Tell someone from the programming" \
                      + " team to check the logs.")


##############################
# Author: Tim | w4rum
# DateCreated: 11/13/2019
# Purpose: Send an error message to the current chat
##############################
def send_error(ctx, text):
    return ctx.send("[ERROR] " + text)


##############################
# Author: Tim | w4rum
# DateCreated: 11/13/2019
# Purpose: Send a usage help to the current chat
##############################
def send_usage_help(ctx, function_name, argument_structure):
    return ctx.send("Usage: `%s%s %s`" \
                    % (BOT_CMD_PREFIX, function_name, argument_structure))


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Class representing basic information of a ticket
#          Can be used to create the starting message embed and can be
#          reconstructed from that embed.
##############################
class Ticket():
    def __init__(self, ticket_id, game_name, author,
                 staff, guild, additional_members=set()):
        self.id = ticket_id
        self.game = game_name
        self.author = author
        self.staff = staff
        log_channel_id \
            = get_state()["ticket_types"][self.game]["log_channel_id"]
        self.log_channel = guild.get_channel(log_channel_id)
        transcript_channel_id \
            = get_state()["ticket_types"][self.game]["transcript_channel_id"]
        self.transcript_channel = guild.get_channel(transcript_channel_id)
        self.additional_members = additional_members

    async def from_start_message(message):
        embed = message.embeds[0]

        # fucking kill me please this is horrible coding
        add_members = set()
        for f in embed.fields:
            if f.name == Strings.field_id: ticket_id = int(f.value)
            if f.name == Strings.field_game: game = f.value
            if f.name == Strings.field_author:
                if f.value[2] == "!":
                    author_id = int(f.value[3:-1])
                else:
                    author_id = int(f.value[2:-1])
                author = await message.guild.fetch_member(author_id)
            if f.name == Strings.field_staff:
                staff_id = int(f.value[3:-1])
                staff = message.guild.get_role(staff_id)
            if f.name == Strings.field_additional_members:
                add_members = f.value.split(" ")
                add_members = [await message.guild.fetch_member(id[2:-1])
                               for id in add_members]
                add_members = set(add_members)

        return Ticket(ticket_id, game, author, staff,
                      message.guild, add_members)


    def to_embed(self):
        embed = discord.Embed.from_dict({
            "title": "Ticket ID: %d" % self.id,
            "color": 0x00FF00,
            "description": "If your issue has been resolved, you can close" \
                           + " this ticket with %s." % Emojis.lock
        })
        embed.add_field(name=Strings.field_id, value=self.id, inline=True)
        embed.add_field(name=Strings.field_game, value=self.game, inline=True)
        embed.add_field(name=Strings.field_author,
                        value=self.author.mention, inline=True)
        embed.add_field(name=Strings.field_staff,
                        value=self.staff.mention, inline=True)
        if len(self.additional_members) > 0:
            s = " ".join([x.mention for x in self.additional_members])
            embed.add_field(name=Strings.field_additional_members,
                            value=s, inline=True)

        return embed

    def to_log_embed(self, log_prefix, color, additional_fields=[]):
        embed = discord.Embed.from_dict({
            "title": "%s: Ticket %d" % (log_prefix, self.id),
            "color": color,
        })
        embed.add_field(name="Game", value=self.game, inline=True)
        embed.add_field(name="Ticket author", value=self.author.mention, inline=True)
        for name, value in additional_fields:
            embed.add_field(name=name, value=value, inline=True)

        return embed

    async def add_members(self, user, message):
        self.additional_members.add(user)
        await message.edit(embed=self.to_embed())

    async def remove_members(self, user, message):
        self.additional_members.remove(user)
        await message.edit(embed=self.to_embed())


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Compensates for having to use on_raw_reaction_add
##############################
class ReactionPayload():
    # this might be a bit heavy on the API
    async def _init(self, payload):
        self.guild = bot.get_guild(payload.guild_id)
        self.member = await self.guild.fetch_member(payload.user_id)
        self.emoji = payload.emoji
        self.channel = bot.get_channel(payload.channel_id)
        self.message = await self.channel.fetch_message(payload.message_id)


async def unwrap_payload(payload):
    rp = ReactionPayload()
    await rp._init(payload)
    return rp


class Emojis():
    envelope_with_arrow = b'\xf0\x9f\x93\xa9'.decode()
    lock = b'\xf0\x9f\x94\x92'.decode()
    unlock = b'\xf0\x9f\x94\x93'.decode()
    flag_eu = b'\xf0\x9f\x87\xaa\xf0\x9f\x87\xba'.decode()
    white_check_mark = b'\xe2\x9c\x85'.decode()
    negative_squared_cross_mark = b'\xe2\x9d\x8e'.decode()
    no_entry_sign = b'\xf0\x9f\x9a\xab'.decode()


class Strings():
    field_id = "ID"
    field_game = "Game"
    field_author = "Ticket author"
    field_staff = "Responsible support staff"
    field_additional_members = "Additional members"


emoji_handlers = {
    Emojis.envelope_with_arrow: create_ticket,
    Emojis.lock: lock_ticket,
    Emojis.unlock: unlock_ticket,
    Emojis.no_entry_sign: delete_ticket,
    Emojis.white_check_mark: delete_confirm,
    Emojis.negative_squared_cross_mark: delete_abort,
}


##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/13/2019
# Purpose: Handles persistent storage
##############################
def get_state():
    # default state
    state = json.dumps({
        "ticket_counter": 0,
        "ticket_types": {},
        "user_ticket_count": {},
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


def get_user_ticket_count(user):
    state = get_state()
    counts = state["user_ticket_count"]
    if str(user.id) not in counts:
        counts[str(user.id)] = 0
    c = counts[str(user.id)]
    write_state(state)

    return c


def inc_user_ticket_count(user):
    state = get_state()
    state["user_ticket_count"][str(user.id)] += 1
    write_state(state)


def dec_user_ticket_count(user):
    state = get_state()
    state["user_ticket_count"][str(user.id)] -= 1
    write_state(state)


class UserNotInTicketError(commands.CommandError):
    pass


class WrongChannelError(commands.CommandError):
    pass

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

