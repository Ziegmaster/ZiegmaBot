import os
import dotenv
import requests
import json
import hikari
from hikari import Color
import lightbulb
from miru.ext import nav

dotenv.load_dotenv()

twitch_plugin = lightbulb.Plugin('twitch_plugin', 'Plugin for custom twitch integration')

def init_ws_routes():
                
    async def ws_route_stream(websocket, message):
        if message['command'] == 'online':
            await stream_notifiy(message['data']['title'], message['data']['category_id'], message['data']['category'])
    
    if twitch_plugin.bot.get_plugin('websocket_server'):
        twitch_plugin.bot.d.wish_subscribe_pool = set()
        twitch_plugin.bot.d.ws_routes['/stream'] = ws_route_stream

async def stream_notifiy(title, category_id, category_name) -> None:
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
    await twitch_plugin.bot.rest.create_message(os.environ['TEXT_CHANNEL_ANNOUNCE'], content='@everyone Ziegmaster запустил прямую трансляцию!', embed=embed, mentions_everyone=True)

def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(twitch_plugin)
    init_ws_routes()