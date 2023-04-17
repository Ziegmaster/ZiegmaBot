import os
import dotenv
import requests
import json
import hikari
from hikari import Color
import lightbulb
from miru.ext import nav

dotenv.load_dotenv()

twitch_accounts = lightbulb.Plugin('twitch_plugin', 'Plugin for custom twitch integration')

@twitch_accounts.command()
@lightbulb.command('account', 'Команды для взаимодействия с учетной записью пользователя')
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def account(ctx: lightbulb.SlashContext) -> None: ...

@account.child()
@lightbulb.command('gacha_characters', 'Получить данные по персонажу на аккаунте', auto_defer = True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def gacha_characters(ctx: lightbulb.SlashContext) -> None:
    twitch_id = await get_user_twitch_id(ctx.author.id)
    if not twitch_id:
        await ctx.respond('Подключите интеграцию с Twitch в настройках своей учетной записи Discord!')
        return
    print(twitch_id)
    response = requests.post('http://localhost/api/characters/owned/show', json = {
        'twitch_id' : twitch_id,
    })
    if response.status_code == 200:
        data = response.json()
        if len(data) == 0:
            await ctx.respond('Ничего не найдено.')
        else:
            navigator_pages = []
            for index, character in enumerate(data):
                try:
                    embed = navigator_pages[index//10]
                except:
                    embed = hikari.Embed(title=f'Список персонажей')
                    navigator_pages.append(embed)
                finally:
                    embed.add_field(f'{character["character_name"]}\t\t{"".join([":star:"]*character["rarity"])}', f'Количество: {character["tier"]}')
            if len(navigator_pages) > 1:
                navigator_buttons = [nav.FirstButton(), nav.PrevButton(), nav.IndicatorButton(), nav.NextButton(), nav.LastButton()]
                navigator_buttons[0].disabled = True
                navigator_buttons[1].disabled = True
                navigator_buttons[2].label = f'1/{len(navigator_pages)}'
            else: navigator_buttons = []
            navigator = nav.NavigatorView(
                pages=navigator_pages,
                buttons=navigator_buttons,
                timeout=120,
            )
            navigator_msg = await ctx.respond(**navigator._get_page_payload(navigator.pages[0]))
            if len(navigator_buttons) > 0: await navigator.start(navigator_msg)
            await navigator.wait()
            await navigator_msg.delete()
    else:
        await ctx.respond('Серверная ошибка.')

@account.child()
@lightbulb.command('gacha_weapons', 'Получить данные по оружию на аккаунте', auto_defer = True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def gacha_weapons(ctx: lightbulb.SlashContext) -> None:
    twitch_id = await get_user_twitch_id(ctx.author.id)
    if not twitch_id:
        await ctx.respond('Подключите интеграцию с Twitch в настройках своей учетной записи Discord!')
        return
    response = requests.post('http://localhost/api/weapons/owned/show', json = {
        'twitch_id' : twitch_id,
    })
    if response.status_code == 200:
        data = response.json()
        if len(data) == 0:
            await ctx.respond('Ничего не найдено.')
        else:
            navigator_pages = []
            for index, weapon in enumerate(data):
                try:
                    embed = navigator_pages[index//10]
                except:
                    embed = hikari.Embed(title=f'Список оружия')
                    navigator_pages.append(embed)
                finally:
                    embed.add_field(f'{weapon["weapon_name"]}\t\t{"".join([":star:"]*weapon["rarity"])}', f'Количество: {weapon["tier"]}')
            if len(navigator_pages) > 1:
                navigator_buttons = [nav.FirstButton(), nav.PrevButton(), nav.IndicatorButton(), nav.NextButton(), nav.LastButton()]
                navigator_buttons[0].disabled = True
                navigator_buttons[1].disabled = True
                navigator_buttons[2].label = f'1/{len(navigator_pages)}'
            else: navigator_buttons = []
            navigator = nav.NavigatorView(
                pages=navigator_pages,
                buttons=navigator_buttons,
                timeout=120,
            )
            navigator_msg = await ctx.respond(**navigator._get_page_payload(navigator.pages[0]))
            if len(navigator_buttons) > 0: await navigator.start(navigator_msg)
            await navigator.wait()
            await navigator_msg.delete()
    else:
        await ctx.respond('Серверная ошибка.')

async def get_user_twitch_id(discord_id) -> str:
    response = requests.get(f'https://discord.com/api/v9/users/{discord_id}/profile?with_mutual_guilds=false&with_mutual_friends_count=false', headers={
        'Authorization' : os.environ['SELFBOT_API_TOKEN']
    })
    if response.status_code == 200:
        data = response.json()
        connections = data['connected_accounts']
        for conn in connections:
            if conn['type'] == 'twitch' and conn['verified'] == True:
                return conn['id']
    return None

async def ws_route_wish(websocket, message):
    if message['command'] == 'subscribe':
        twitch_accounts.bot.d.wish_subscribe_pool.add(websocket)
    elif message['command'] == 'make':
        response = requests.post('http://localhost/api/gacha/store', json=message['data'])
        if response.status_code == 200:
            closed_connections = set()
            for ws_client in twitch_accounts.bot.d.wish_subscribe_pool:
                try:
                    await ws_client.send(response.text)
                except:
                    closed_connections.add(ws_client)
            for conn in closed_connections:
                twitch_accounts.bot.d.wish_subscribe_pool.remove(conn)
                
async def ws_route_stream(websocket, message):
    if message['command'] == 'online':
        await stream_notifiy(message['data']['title'], message['data']['category_id'], message['data']['category'])

def init_ws_routes():
    if twitch_accounts.bot.get_plugin('WebsocketServer'):
        twitch_accounts.bot.d.wish_subscribe_pool = set()
        twitch_accounts.bot.d.ws_routes['/wish'] = ws_route_wish
        twitch_accounts.bot.d.ws_routes['/stream'] = ws_route_stream
            
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

def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(twitch_accounts)
    init_ws_routes()