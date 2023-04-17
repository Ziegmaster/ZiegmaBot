import os
import asyncio 
import websockets
import dotenv
import requests
import json
import hikari
from hikari import Color
import lightbulb
from lightbulb.ext import tasks
import miru

dotenv.load_dotenv()

class ZiegmaBot(lightbulb.BotApp):

    def __init__(self):
        super().__init__(os.environ['TOKEN'], prefix='z!', default_enabled_guilds=int(os.environ['DEFAULT_GUILD_ID']), help_class=None, intents=hikari.Intents.ALL)
        self.d.wish_subscribe_pool = set()
        self.d.music_subscribe_pool = set()
        miru.install(self)
        tasks.load(self)
        self.load_extensions('ext.music_plugin', 'ext.twitch_accounts')

    async def ws_response(self, websocket, path):
        async for message in websocket: 
            message = json.loads(message) 
            if path == '/wish':
                if message['command'] == 'subscribe':
                    self.d.wish_subscribe_pool.add(websocket)
                elif message['command'] == 'make':
                    response = requests.post('http://localhost/api/gacha/store', json=message['data'])
                    if response.status_code == 200:
                        closed_connections = set()
                        for ws_client in self.d.wish_subscribe_pool:
                            try:
                                await ws_client.send(response.text)
                            except:
                                closed_connections.add(ws_client)
                        for conn in closed_connections:
                            self.d.wish_subscribe_pool.remove(conn)
            if path == '/stream':
                if message['command'] == 'online':
                    await self.stream_notifiy(message['data']['title'], message['data']['category_id'], message['data']['category'])
            if path == '/music':
                if message['command'] == 'subscribe':
                    self.d.music_subscribe_pool.add(websocket)
                

    async def stream_notifiy(self, title, category_id, category_name) -> None:
        embed = hikari.Embed(
            title=title,
            description=category_name,
            url = 'https://twitch.tv/ziegmaster',
            color = Color.from_hex_code('#772CE8'),
        )
        if requests.get(f'https://static-cdn.jtvnw.net/ttv-boxart/{category_id}-144x192.jpg').url != 'https://static-cdn.jtvnw.net/ttv-static/404_boxart-144x192.jpg':
            category_thumb = f'https://static-cdn.jtvnw.net/ttv-boxart/{category_id}-144x192.jpg'
        else:
            category_thumb = f'https://static-cdn.jtvnw.net/ttv-boxart/{category_id}_IGDB-144x192.jpg'
        embed.set_thumbnail(category_thumb)
        #embed.set_image('https://static-cdn.jtvnw.net/previews-ttv/live_user_ziegmaster-1920x1080.jpg?width=1193&height=671')
        await self.rest.create_message(os.environ['TEXT_CHANNEL_ANNOUNCE'], content='@everyone Ziegmaster запустил прямую трансляцию!', embed=embed, mentions_everyone=True)

def run() -> None:
    bot = ZiegmaBot()
    ws_server = websockets.serve(bot.ws_response, '0.0.0.0', '8000')
    asyncio.get_event_loop().run_until_complete(ws_server)
    bot.run(activity=hikari.Activity(name='Version 1.8.4', type=hikari.ActivityType.COMPETING))