#!/usr/bin/python3.10
import os
import dotenv
import asyncio
import uvloop
import hikari
from hikari import Color
import lightbulb
from lightbulb.ext import tasks
import miru

dotenv.load_dotenv()

class ZiegmaBot(lightbulb.BotApp):
    
    def __init__(self):
        super().__init__(os.environ['TOKEN'], help_class=None, intents=hikari.Intents.ALL)
        miru.install(self)
        tasks.load(self)
        self.load_extensions('ext.websocket_server',
                             #'ext.music_plugin',
                             'ext.twitch_plugin')

    async def remove_commands(guild_id=hikari.UNDEFINED):

        rest = hikari.RESTApp()
        await rest.start()
        
        async with rest.acquire(os.environ['TOKEN'], hikari.TokenType.BOT) as client:
            application = await client.fetch_application()
            await client.set_application_commands(application.id, (), guild=os.environ['SERVER_GUILD_ID'])

if __name__ == '__main__':
    uvloop.install()
    bot = ZiegmaBot()
    #asyncio.run(bot.remove_commands())
    bot.run(activity=hikari.Activity(name='Version 1.8.4', type=hikari.ActivityType.COMPETING))