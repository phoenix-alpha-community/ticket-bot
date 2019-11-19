import html
from pytz import timezone
import re
import discord

eastern = timezone("US/Eastern")
utc     = timezone("UTC")

async def generate_transcript(channel, ticket):
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
            ("BOT_TAG", ze_bot_tag, False),
            ("TIMESTAMP", time_string_final),
            ("MESSAGE_ID", str(m.id)),
            ("MESSAGE_CONTENT", m.content),
            ("EMBEDS", embeds, False),
            ("ATTACHMENTS", attachments, False),
        ])

        messages_html += cur_msg

    transcript = await fill_out(channel, total, [
        ("SERVER_NAME", channel.guild.name),
        ("CHANNEL_NAME", "Ticket %d" % ticket.id),
        ("MESSAGE_COUNT", str(len(messages))),
        ("MESSAGES", messages_html, False)
    ])

    return transcript

async def fill_out(channel, base, pairs):
    for p in pairs:
        if len(p) == 2:
            k, v = p
            should_escape = True
        else:
            k, v, should_escape = p

        # parse mentions
        # roles
        for match in re.finditer("<@&([0-9]+)>", v):
            role_id = int(match.group(1))
            role = channel.guild.get_role(role_id)
            v = v.replace(v[match.start():match.end()], "@%s" % role.name)
        # members
        for match in re.finditer("<@!?([0-9]+)>", v):
            id = int(match.group(1))
            member = await channel.guild.fetch_member(id)
            v = v.replace(v[match.start():match.end()], "@%s" % member)
        # channels
        for match in re.finditer("<#([0-9]+)>", v):
            id = int(match.group(1))
            channel = channel.guild.get_channel(id)
            v = v.replace(v[match.start():match.end()], "#%s" % channel)
        # custom emoji
        for match in re.finditer("<a?(:[^\n:]+:)[0-9]+>", v):
            name = match.group(1)
            v = v.replace(v[match.start():match.end()], name)

        # html escape
        if should_escape:
            #v = markdown(v) # don't, will fuck with linebreaks
            v = html.escape(v)

        base = base.replace("{{" + k + "}}", v)

    return base



total = r"""
<!DOCTYPE html>
<html lang="en">

<head>
    <title>{{SERVER_NAME}} - {{CHANNEL_NAME}}</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width" />

    <style>
        /* === GENERAL === */

@font-face {
    font-family: Whitney;
    src: url(https://discordapp.com/assets/6c6374bad0b0b6d204d8d6dc4a18d820.woff);
    font-weight: 300;
}

@font-face {
    font-family: Whitney;
    src: url(https://discordapp.com/assets/e8acd7d9bf6207f99350ca9f9e23b168.woff);
    font-weight: 400;
}

@font-face {
    font-family: Whitney;
    src: url(https://discordapp.com/assets/3bdef1251a424500c1b3a78dea9b7e57.woff);
    font-weight: 500;
}

@font-face {
    font-family: Whitney;
    src: url(https://discordapp.com/assets/be0060dafb7a0e31d2a1ca17c0708636.woff);
    font-weight: 600;
}

@font-face {
    font-family: Whitney;
    src: url(https://discordapp.com/assets/8e12fb4f14d9c4592eb8ec9f22337b04.woff);
    font-weight: 700;
}

body {
    font-family: "Whitney", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 17px;
}

a {
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

img {
    object-fit: contain;
}

.markdown {
    white-space: pre-wrap;
    line-height: 1.3;
    overflow-wrap: break-word;
}

.spoiler {
    border-radius: 3px;
}

.quote {
    border-left: 4px solid;
    border-radius: 3px;
    margin: 8px 0;
    padding-left: 10px;
}

.pre {
    font-family: "Consolas", "Courier New", Courier, monospace;
}

.pre--multiline {
    margin-top: 4px;
    padding: 8px;
    border: 2px solid;
    border-radius: 5px;
}

.pre--inline {
    padding: 2px;
    border-radius: 3px;
    font-size: 85%;
}

.mention {
    font-weight: 500;
}

.emoji {
    width: 1.45em;
    height: 1.45em;
    margin: 0 1px;
    vertical-align: -0.4em;
}

.emoji--small {
    width: 1rem;
    height: 1rem;
}

.emoji--large {
    width: 2rem;
    height: 2rem;
}

/* === INFO === */

.info {
    display: flex;
    max-width: 100%;
    margin: 0 5px 10px 5px;
}

.info__guild-icon-container {
    flex: 0;
}

.info__guild-icon {
    max-width: 88px;
    max-height: 88px;
}

.info__metadata {
    flex: 1;
    margin-left: 10px;
}

.info__guild-name {
    font-size: 1.4em;
}

.info__channel-name {
    font-size: 1.2em;
}

.info__channel-topic {
    margin-top: 2px;
}

.info__channel-message-count {
    margin-top: 2px;
}

.info__channel-date-range {
    margin-top: 2px;
}

/* === CHATLOG === */

.chatlog {
    max-width: 100%;
    margin-bottom: 24px;
}

.chatlog__message-group {
    display: flex;
    margin: 0 10px;
    padding: 15px 0;
    border-top: 1px solid;
}

.chatlog__author-avatar-container {
    flex: 0;
    width: 40px;
    height: 40px;
}

.chatlog__author-avatar {
    border-radius: 50%;
    height: 40px;
    width: 40px;
}

.chatlog__messages {
    flex: 1;
    min-width: 50%;
    margin-left: 20px;
}

.chatlog__author-name {
    font-size: 1em;
    font-weight: 500;
}

.chatlog__timestamp {
    margin-left: 5px;
    font-size: .75em;
}

.chatlog__message {
    padding: 2px 5px;
    margin-right: -5px;
    margin-left: -5px;
    background-color: transparent;
    transition: background-color 1s ease;
}

.chatlog__content {
    font-size: .9375em;
    word-wrap: break-word;
}

.chatlog__edited-timestamp {
    margin-left: 3px;
    font-size: .8em;
}

.chatlog__attachment-thumbnail {
    margin-top: 5px;
    max-width: 50%;
    max-height: 500px;
    border-radius: 3px;
}

.chatlog__embed {
    margin-top: 5px;
    display: flex;
    max-width: 520px;
}

.chatlog__embed-color-pill {
    flex-shrink: 0;
    width: 4px;
    border-top-left-radius: 3px;
    border-bottom-left-radius: 3px;
}

.chatlog__embed-content-container {
    display: flex;
    flex-direction: column;
    padding: 8px 10px;
    border: 1px solid;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

.chatlog__embed-content {
    width: 100%;
    display: flex;
}

.chatlog__embed-text {
    flex: 1;
}

.chatlog__embed-author {
    display: flex;
    align-items: center;
    margin-bottom: 5px;
}

.chatlog__embed-author-icon {
    width: 20px;
    height: 20px;
    margin-right: 9px;
    border-radius: 50%;
}

.chatlog__embed-author-name {
    font-size: .875em;
    font-weight: 600;
}

.chatlog__embed-title {
    margin-bottom: 4px;
    font-size: .875em;
    font-weight: 600;
}

.chatlog__embed-description {
    font-weight: 500;
    font-size: 14px;
}

.chatlog__embed-fields {
    display: flex;
    flex-wrap: wrap;
}

.chatlog__embed-field {
    flex: 0;
    min-width: 100%;
    max-width: 506px;
    padding-top: 10px;
}

.chatlog__embed-field--inline {
    flex: 1;
    flex-basis: auto;
    min-width: 150px;
}

.chatlog__embed-field-name {
    margin-bottom: 4px;
    font-size: .875em;
    font-weight: 600;
}

.chatlog__embed-field-value {
    font-size: .875em;
    font-weight: 500;
}

.chatlog__embed-thumbnail {
    flex: 0;
    margin-left: 20px;
    max-width: 80px;
    max-height: 80px;
    border-radius: 3px;
}

.chatlog__embed-image-container {
    margin-top: 10px;
}

.chatlog__embed-image {
    max-width: 500px;
    max-height: 400px;
    border-radius: 3px;
}

.chatlog__embed-footer {
    margin-top: 10px;
}

.chatlog__embed-footer-icon {
    margin-right: 4px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    vertical-align: middle;
}

.chatlog__embed-footer-text {
    font-weight: 500;
    font-size: .75em;
}

.chatlog__reactions {
    display: flex;
}

.chatlog__reaction {
    display: flex;
    align-items: center;
    margin: 6px 2px 2px 2px;
    padding: 3px 6px;
    border-radius: 3px;
}

.chatlog__reaction-count {
    min-width: 9px;
    margin-left: 6px;
    font-size: .875em;
}

.chatlog__bot-tag {
    margin-left: 0.3em;
    background: #7289da;
    color: #ffffff;
    font-size: 0.625em;
    padding: 1px 2px;
    border-radius: 3px;
    vertical-align: middle;
    line-height: 1.3;
    position: relative;
    top: -.2em;
}
    </style>
    <style>
        /* === GENERAL === */

body {
    background-color: #36393e;
    color: #dcddde;
}

a {
    color: #0096cf;
}

.spoiler {
    background-color: rgba(255, 255, 255, 0.1);
}

.quote {
    border-color: #4f545c;
}

.pre {
    background-color: #2f3136 !important;
}

.pre--multiline {
    border-color: #282b30 !important;
    color: #839496 !important;
}

.mention {
    color: #7289da;
}

/* === INFO === */

.info__guild-name {
    color: #ffffff;
}

.info__channel-name {
    color: #ffffff;
}

.info__channel-topic {
    color: #ffffff;
}

/* === CHATLOG === */

.chatlog__message-group {
    border-color: rgba(255, 255, 255, 0.1);
}

.chatlog__author-name {
    color: #ffffff;
}

.chatlog__timestamp {
    color: rgba(255, 255, 255, 0.2);
}

.chatlog__message--highlighted {
    background-color: rgba(114, 137, 218, 0.2) !important;
}

.chatlog__message--pinned {
    background-color: rgba(249, 168, 37, 0.05);
}

.chatlog__edited-timestamp {
    color: rgba(255, 255, 255, 0.2);
}

.chatlog__embed-content-container {
    background-color: rgba(46, 48, 54, 0.3);
    border-color: rgba(46, 48, 54, 0.6);
}

.chatlog__embed-author-name {
    color: #ffffff;
}

.chatlog__embed-author-name-link {
    color: #ffffff;
}

.chatlog__embed-title {
    color: #ffffff;
}

.chatlog__embed-description {
    color: rgba(255, 255, 255, 0.6);
}

.chatlog__embed-field-name {
    color: #ffffff;
}

.chatlog__embed-field-value {
    color: rgba(255, 255, 255, 0.6);
}

.chatlog__embed-footer {
    color: rgba(255, 255, 255, 0.6);
}

.chatlog__reaction {
    background-color: rgba(255, 255, 255, 0.05);
}

.chatlog__reaction-count {
    color: rgba(255, 255, 255, 0.3);
}
    </style>

    <script>
        function scrollToMessage(event, id) {
            var element = document.getElementById('message-' + id);

            if (element !== null && element !== undefined) {
                event.preventDefault();

                element.classList.add('chatlog__message--highlighted');

                window.scrollTo({
                    top: element.getBoundingClientRect().top - document.body.getBoundingClientRect().top - (window.innerHeight / 2),
                    behavior: 'smooth'
                });

                window.setTimeout(function() {
                    element.classList.remove('chatlog__message--highlighted');
                }, 2000);
            }
        }
    </script>

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/9.15.6/styles/solarized-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/9.15.6/highlight.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('.pre--multiline').forEach((block) => {
                hljs.highlightBlock(block);
            });
        });
    </script>
</head>
<body>

<div class="info">
    <div class="info__guild-icon-container">
        <img class="info__guild-icon" src="https://cdn.discordapp.com/icons/643983215056519178/44da9984d788eeb0fadf17f824dd81eb.png" />
    </div>
    <div class="info__metadata">
        <div class="info__guild-name">{{SERVER_NAME}}</div>
        <div class="info__channel-name">{{CHANNEL_NAME}}</div>


        <div class="info__channel-message-count">{{MESSAGE_COUNT}} messages</div>

    </div>
</div>

<div class="chatlog">
{{MESSAGES}}
</div>

</body>
</html>
    """

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

