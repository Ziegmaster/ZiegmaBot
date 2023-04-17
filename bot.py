#!/usr/bin/python3.10
import os
import dotenv
import uvloop
import hikari
from hikari import Color
import lightbulb
from lightbulb.ext import tasks
import miru

dotenv.load_dotenv()

class ZiegmaBot(lightbulb.BotApp):
    
    def __init__(self):
        super().__init__(os.environ['TOKEN'], prefix='z!', default_enabled_guilds=int(os.environ['DEFAULT_GUILD_ID']), help_class=None, intents=hikari.Intents.ALL)
        miru.install(self)
        tasks.load(self)
        self.load_extensions('ext.websocket_server',
                             'ext.music_plugin',
                             'ext.twitch_plugin')
        self.run(activity=hikari.Activity(name='Version 1.8.4', type=hikari.ActivityType.COMPETING))

if __name__ == '__main__':
    uvloop.install()
    bot = ZiegmaBot()