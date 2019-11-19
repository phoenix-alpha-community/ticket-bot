import html
from pytz import timezone
import re
import discord
from markdown import markdown

eastern = timezone("US/Eastern")
utc     = timezone("UTC")

no_parser = []

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

            desc = e.description
            if desc == discord.Embed.Empty:
                desc = ""
            cur_embed = await fill_out(channel, msg_embed, [
                ("EMBED_R", str(e.colour.r)),
                ("EMBED_G", str(e.colour.g)),
                ("EMBED_B", str(e.colour.b)),
                ("EMBED_TITLE", e.title),
                ("EMBED_DESC", desc),
                ("EMBED_FIELDS", fields, False),

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
            ("BOT_TAG", ze_bot_tag, no_parser),
            ("TIMESTAMP", time_string_final),
            ("MESSAGE_ID", str(m.id)),
            ("MESSAGE_CONTENT", m.content),
            ("EMBEDS", embeds, no_parser),
            ("ATTACHMENTS", attachments, no_parser),
        ])

        messages_html += cur_msg

    transcript = await fill_out(channel, total, [
        ("SERVER_NAME", guild.name),
        ("SERVER_AVATAR_URL", guild.icon, no_parser)
        ("CHANNEL_NAME", "Ticket %d" % ticket.id),
        ("MESSAGE_COUNT", str(len(messages))),
        ("MESSAGES", messages_html, no_parser),
    ])

    return transcript

async def mentions_pre_parser(content, guild):
    pass # TODO

async def mentions_post_parser(content, guild):
    # parse mentions
    # roles
    for match in re.finditer("<@&([0-9]+)>", content):
        role_id = int(match.group(1))
        role = guild.get_role(role_id)
        content = content.replace(content[match.start():match.end()], "@%s" % role.name)
    # members
    for match in re.finditer("<@!?([0-9]+)>", content):
        id = int(match.group(1))
        member = await guild.fetch_member(id)
        content = content.replace(content[match.start():match.end()], "@%s" % member)
    # channels
    for match in re.finditer("<#([0-9]+)>", content):
        id = int(match.group(1))
        channel = guild.get_channel(id)
        content = content.replace(content[match.start():match.end()], "#%s" % channel)
    # custom emoji
    for match in re.finditer("<a?(:[^\n:]+:)[0-9]+>", content):
        name = match.group(1)
        content = content.replace(content[match.start():match.end()], name)

    return content

async def fill_out(channel, base, replacements):
    for r in replacements:
        if len(p) == 2: # default case: html escape only
            k, v = r
            v = html.escape(v)
        else:
            k, v, parser = r
            for p in parser:
                v = p(v)


        base = base.replace("{{" + k + "}}", v)

    return base


def read_file(filename):
    s = ""
    with open(filename, "r") as f:
        s = f.read()
    return s


total = read_file("chat-exporter-resources/base.html")

msg = r"""
        <div class="chatlog__message-group">
            <div class="chatlog__author-avatar-container">
                <img class="chatlog__author-avatar" src="{{AVATAR_URL}}" />
            </div>
            <div class="chatlog__messages">
                <span class="chatlog__author-name" title="{{NAME_TAG}}" data-user-id="644128496469147658">{{NAME}}</span>

                {{BOT_TAG}}

                <span class="chatlog__timestamp">{{TIMESTAMP}}</span>

                    <div class="chatlog__message " data-message-id="{{MESSAGE_ID}}" id="message-{{MESSAGE_ID}}">
                        <div class="chatlog__content">
                            <span class="markdown">{{MESSAGE_CONTENT}}</span>

                        </div>

                        {{EMBEDS}}

                        {{ATTACHMENTS}}

                    </div>
            </div>
        </div>
    """

bot_tag = """<span class="chatlog__bot-tag">BOT</span>"""


msg_embed = r"""
            <div class=chatlog__embed>
                <div class=chatlog__embed-color-pill style=background-color:rgba({{EMBED_R}},{{EMBED_G}},{{EMBED_B}},1)></div>
                <div class=chatlog__embed-content-container>
                    <div class=chatlog__embed-content>
                        <div class=chatlog__embed-text>
                            <div class="chatlog__embed-title">
                                    <span class="markdown">{{EMBED_TITLE}}</span>
                            </div>
                            <div class=chatlog__embed-description><span class=markdown>{{EMBED_DESC}}</span></div>
                            {{EMBED_FIELDS}}
                        </div>
                    </div>
                </div>
            </div>"""

msg_embed_field = r"""
<div class="chatlog__embed-fields">
        <div class="chatlog__embed-field  chatlog__embed-field--inline ">
                <div class="chatlog__embed-field-name"><span class="markdown">{{EMBED_FIELD_NAME}}</span></div>
                <div class="chatlog__embed-field-value"><span class="markdown">{{EMBED_FIELD_VALUE}}</span></div>
        </div>
</div>"""


msg_attachment = r"""
<div class=chatlog__attachment>
    <a href={{ATTACH_URL}}><img class=chatlog__attachment-thumbnail src={{ATTACH_URL_THUMB}}></a>
</div>
"""

