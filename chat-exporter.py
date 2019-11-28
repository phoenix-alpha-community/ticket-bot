################################################################################
#
#                               !!! WARNING !!!
# The following code is a highly concentrated mixture of all known forms of
# cancerous tumors. It started off as a quick-fix for a missing python-based
# chat export function and then underwent heavy refactoring in an attempt to
# make it acceptable. Which kind of failed. Proceed at your own risk.
#
################################################################################

##############################
# Author: Tim | w4rum
# Social and emotional support and a few good ones: Matt | Mahtoid
# DateCreated: 11/20/2019
# Purpose: Generate a transcript from a channel
#          Output based on the C# Discord chat exporter by Tyrrrz
#          https://github.com/Tyrrrz/DiscordChatExporter
##############################

import html
from pytz import timezone
import re
import discord
from ticket_bot import FakeMember

eastern = timezone("US/Eastern")
utc     = timezone("UTC")

async def generate_transcript(channel, ticket):
    guild = channel.guild
    messages = await channel.history(limit=None, oldest_first=True).flatten()

    messages_html = ""
    for m in messages:
        time_format = "%b %d, %Y %I:%M %p"
        time_string_created = utc.localize(m.created_at).astimezone(eastern)
        time_string_created = time_string_created.strftime(time_format)
        if m.edited_at != None:
            time_string_edited = utc.localize(m.edited_at).astimezone(eastern)
            time_string_edited = time_string_edited.strftime(time_format)
            time_string_final = "%s (edited %s)"\
                          % (time_string_created, time_string_edited)
        else:
            time_string_edited = "never"
            time_string_final = time_string_created

        embeds = ""
        for e in m.embeds:
            fields = ""
            for f in e.fields:
                cur_field = await fill_out(channel, msg_embed_field, [
                        ("EMBED_FIELD_NAME", f.name),
                        ("EMBED_FIELD_VALUE", f.value),
                ])
                fields += cur_field


            # default values for embeds need explicit setting because
            # Embed.empty breaks just about everything
            title = e.title \
                if e.title != discord.Embed.Empty \
                else ""
            r, g, b = (e.colour.r, e.colour.g, e.colour.b) \
                if e.colour != discord.Embed.Empty \
                else (0x20, 0x22, 0x25) # default colour
            desc = e.description \
                if e.description != discord.Embed.Empty \
                else ""

            cur_embed = await fill_out(channel, msg_embed, [
                ("EMBED_R", str(r)),
                ("EMBED_G", str(g)),
                ("EMBED_B", str(b)),
                ("EMBED_TITLE", title),
                ("EMBED_DESC", desc, PARSE_MODE_MARKDOWN),
                ("EMBED_FIELDS", fields, []),

            ])
            embeds += cur_embed

        attachments = ""
        for a in m.attachments:
            cur_attach = await fill_out(channel, msg_attachment, [
                ("ATTACH_URL", a.url),
                ("ATTACH_URL_THUMB", a.url),
            ])
            attachments += cur_attach

        if m.author.bot:
            ze_bot_tag = bot_tag
        else:
            ze_bot_tag = ""
        cur_msg = await fill_out(channel, msg, [
            ("AVATAR_URL", str(m.author.avatar_url)),
            ("NAME_TAG", "%s#%s" % (m.author.name, m.author.discriminator)),
            ("NAME", m.author.name),
            ("BOT_TAG", ze_bot_tag, PARSE_MODE_NONE),
            ("TIMESTAMP", time_string_final),
            ("MESSAGE_ID", str(m.id)),
            ("MESSAGE_CONTENT", m.content),
            ("EMBEDS", embeds, PARSE_MODE_NONE),
            ("ATTACHMENTS", attachments, PARSE_MODE_NONE),
        ])

        messages_html += cur_msg

    transcript = await fill_out(channel, total, [
        ("SERVER_NAME", guild.name),
        ("SERVER_AVATAR_URL", str(guild.icon_url), PARSE_MODE_NONE),
        ("CHANNEL_NAME", "Ticket %d" % ticket.id),
        ("MESSAGE_COUNT", str(len(messages))),
        ("MESSAGES", messages_html, PARSE_MODE_NONE),
    ])

    return transcript


REGEX_ROLES     = r"<@&([0-9]+)>"
REGEX_MEMBERS   = r"<@!?([0-9]+)>"
REGEX_CHANNELS  = r"<#([0-9]+)>"
REGEX_EMOJIS    = r"<a?(:[^\n:]+:)[0-9]+>"

ESCAPE_LT       = "______lt______"
ESCAPE_GT       = "______gt______"
ESCAPE_AMP      = "______amp______"

async def escape_mentions(content, guild):
    for match in re.finditer("(%s|%s|%s|%s)" \
                             % (REGEX_ROLES, REGEX_MEMBERS, REGEX_CHANNELS,
                                REGEX_EMOJIS), content):
        pre_content     = content[:match.start()]
        post_content    = content[match.end():]
        match_content   = content[match.start():match.end()]

        match_content   = match_content.replace("<", ESCAPE_LT)
        match_content   = match_content.replace(">", ESCAPE_GT)
        match_content   = match_content.replace("&", ESCAPE_AMP)

        content         = pre_content + match_content + post_content

    return content


async def unescape_mentions(content, guild):
    content   = content.replace(ESCAPE_LT, "<")
    content   = content.replace(ESCAPE_GT, ">")
    content   = content.replace(ESCAPE_AMP, "&")
    return content


async def parse_mentions(content, guild):
    # parse mentions
    # channels
    offset = 0
    for match in re.finditer(REGEX_CHANNELS, content):
        id = int(match.group(1))
        channel = guild.get_channel(id)
        replacement = '<span class="mention" title="%s">#%s</span>' \
                      % (channel.name, channel.name)
        content = content.replace(content[match.start()+offset:match.end()+offset],
                                  replacement)
        offset += len(replacement) - (match.end() - match.start())
    # roles
    offset = 0
    for match in re.finditer(REGEX_ROLES, content):
        role_id = int(match.group(1))
        role = guild.get_role(role_id)
        replacement = '<span style="color: #%02x%02x%02x;">@%s</span>' \
                      % (role.color.r, role.color.g, role.color.b, role.name)
        content = content.replace(content[match.start()+offset:match.end()+offset],
                                  replacement)
        offset += len(replacement) - (match.end() - match.start())

    # members
    offset = 0
    for match in re.finditer(REGEX_MEMBERS, content):
        id = int(match.group(1))
        member = guild.get_member(id) or FakeMember(id, guild)
        replacement = '<span class="mention" title="%s">@%s</span>' \
                      % (member, member.nick or member.name)
        content = content.replace(content[match.start()+offset:match.end()+offset],
                                  replacement)
        offset += len(replacement) - (match.end() - match.start())

    # custom emoji
    offset = 0
    for match in re.finditer(REGEX_EMOJIS, content):
        name = match.group(1)
        replacement = name
        content = content.replace(content[match.start()+offset:match.end()+offset],
                                  replacement)
        offset += len(replacement) - (match.end() - match.start())

    return content


async def escape_html(content, guild):
    return html.escape(content)


async def parse_markdown(content, guild):
    # We know of markdown.markdown but that thing has more features than
    # Discord markdown (inserting <p> on encountering multiple breaks), which
    # can not be disabled.

    # __underline__
    for match in re.finditer(r"__([^<>]+)__", content):
        affected_text = match.group(1)
        content = content.replace(content[match.start():match.end()],
                                  '<span style="text-decoration: underline">%s</span>' % affected_text)
    # *italic*
    for match in re.finditer(r"\*\*([^<>]+)\*\*", content):
        affected_text = match.group(1)
        content = content.replace(content[match.start():match.end()],
                                  '<strong>%s</strong>' % affected_text)
    # **bold**
    for match in re.finditer(r"\*([^<>]+)\*", content):
        affected_text = match.group(1)
        content = content.replace(content[match.start():match.end()],
                                  '<em>%s</em>' % affected_text)
    # ~~strikethrough~~
    for match in re.finditer(r"~~([^<>]+)~~", content):
        affected_text = match.group(1)
        content = content.replace(content[match.start():match.end()],
                                  '<span style="text-decoration: line-through">%s</span>' % affected_text)
    return content

PARSE_MODE_NONE         = 0
PARSE_MODE_NO_MARKDOWN  = 1
PARSE_MODE_MARKDOWN     = 2

async def fill_out(channel, base, replacements):
    for r in replacements:
        if len(r) == 2: # default case
            k, v = r
            r = (k, v, PARSE_MODE_MARKDOWN)

        k, v, mode = r
        parser = [escape_mentions, escape_mentions,
                    unescape_mentions, parse_mentions]

        if mode == PARSE_MODE_MARKDOWN:
            parser.append(parse_markdown)
        elif mode == PARSE_MODE_NONE:
            parser = []

        for p in parser:
            v = await p(v, channel.guild)

        base = base.replace("{{" + k + "}}", v)

    return base


def read_file(filename):
    s = ""
    with open(filename, "r") as f:
        s = f.read()
    return s


total           = read_file("chat-exporter-resources/base.html")
msg             = read_file("chat-exporter-resources/message.html")
bot_tag         = read_file("chat-exporter-resources/bot-tag.html")
msg_embed       = read_file("chat-exporter-resources/message-embed.html")
msg_embed_field = read_file("chat-exporter-resources/message-embed-field.html")
msg_attachment  = read_file("chat-exporter-resources/message-attachment.html")

