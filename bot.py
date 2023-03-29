from os import getenv

from discord import Intents, Embed, Activity, ActivityType, Message
from discord.ext import commands, tasks
from discord.ext.commands import Context
from dotenv import load_dotenv
from typing import List
import datetime
import json
import collections
import aiohttp

# opens env file with tokens
load_dotenv("dis.env")
TOKEN = getenv("DISCORD_TOKEN")
BS_TOKEN = getenv("BS_API_TOKEN")

BS_API = "https://api.brawlstars.com/v1"

# settings for bot
activity = Activity(type=ActivityType.watching, name="Scrims")
intents = Intents.default()
intents.guilds = True
intents.message_content = True
bot = commands.Bot(
    command_prefix="d!", activity=activity, case_insensitive=True, intents=intents, help_command=None)

# opening all json files
# for servers and its players
with open('servers.json', 'r+') as jsonfile:
    SERVERS: dict = json.load(jsonfile)

# for emotes for brawlers
with open('brawlers.json', 'r+') as jsonfile:
    BRAWLER_EMOTES: dict = json.load(jsonfile)

# for statistics (playrate and winrate)
with open('stats.json', 'r+') as jsonfile:
    STATS: dict = json.load(jsonfile)

# all needed global variables
# maps we want to see matches from
MAPS_GEM_GRAB: tuple = ("Hard Rock Mine", "Gem Fort", "Crystal Arcade")
MAPS_BRAWL_BALL: tuple = ("Backyard Bowl", "Pinhole Punt", "Field Goal")
MAPS_BOUNTY: tuple = ("Shooting Star", "Dry Season", "Layer Cake")
MAPS_HEIST: tuple = ("Hot Potato", "Safe Zone", "Safe Zone")
MAPS_KNOCKOUT: tuple = ("Goldarm Gulch", "Out in the Open", "Flaring Phoenix")
MAPS_HOT_ZONE: tuple = ("Ring of Fire", "Parallel Plays", "Split")

# variables to display mobile version of embed
MESSAGES_STATS: List = []
EMBEDS_MOBILE: List = []
EMBEDS_PC: List = []


# object for creating and saving Power Matches (Best of 3)
class PowerMatch:
    def __init__(self, playername: str, player1, player2, player3, player4, player5, player6, brawler1, brawler2, brawler3, brawler4, brawler5, brawler6, gamemode, bsmap, result: str, channel, bstype: str) -> None:
        self.__players = [player1, player2, player3, player4, player5, player6]
        self.__brawlers = [brawler1, brawler2,
                           brawler3, brawler4, brawler5, brawler6]
        self.__results = [result]
        self.__gamemode = gamemode
        self.__bstype = bstype
        self.__map = bsmap
        self.__playername = playername
        self.__channel = channel

    # creating embed to send as a message
    def create_embed(self, result: str) -> Embed:
        color = 0xffffff
        if result == "Victory":
            color = 0x00ff33
        elif result == "Defeat":
            color = 0xff0000
        emotes: List = []
        for brawler in self.__brawlers:
            if brawler in BRAWLER_EMOTES:
                emotes.append(BRAWLER_EMOTES[brawler])
            else:
                emotes.append("")
        mode_emote: str = get_mode_emote(self.__gamemode)

        results: str = '\n'.join(self.__results)
        embed = Embed(
            title=f"**{self.__playername}** played a new {self.__bstype} game!", description="\n", color=color)
        embed.add_field(name=f"__**Match Info**__",
                        value=f"**Mode:** {self.__gamemode} {mode_emote}\n**Map:** {self.__map}", inline=False)
        embed.add_field(name=f"__**Team Composition**__",
                        value=f"**{emotes[0]} {self.__brawlers[0]}** ({self.__players[0]})\n**{emotes[1]} {self.__brawlers[1]}** ({self.__players[1]})\n**{emotes[2]} {self.__brawlers[2]}** ({self.__players[2]})", inline=True)
        embed.add_field(name=f"**--VS--**", value="-------", inline=True)
        embed.add_field(name=f"__**Enemy Composition**__",
                        value=f"**{emotes[3]} {self.__brawlers[3]}** ({self.__players[3]})\n**{emotes[4]} {self.__brawlers[4]}** ({self.__players[4]})\n**{emotes[5]} {self.__brawlers[5]}** ({self.__players[5]})", inline=True)
        embed.add_field(name=f"**Results**", value=f"{results}", inline=False)
        return embed

    # getting pickrate statistics from this match
    def pickrate_stats(self) -> None:
        server_id = str(self.__channel.guild.id)
        if server_id not in STATS:
            STATS[server_id] = {}
        if self.__map not in STATS[server_id]:
            STATS[server_id][self.__map] = {}
        for brawler in self.__brawlers:
            if brawler not in STATS[server_id][self.__map]:
                STATS[server_id][self.__map][brawler] = {}
            if "PICKS" not in STATS[server_id][self.__map][brawler]:
                STATS[server_id][self.__map][brawler]["PICKS"] = 0
            STATS[server_id][self.__map][brawler]["PICKS"] += 1
        with open('stats.json', 'w') as jsonfile:
            json.dump(STATS, jsonfile, indent=4)
            jsonfile.truncate()

    # getting winrate statistics from this match
    def winrate_stats(self, won: bool) -> None:
        server_id = str(self.__channel.guild.id)
        if server_id not in STATS:
            STATS[server_id] = {}
        if self.__map not in STATS[server_id]:
            STATS[server_id][self.__map] = {}
        for brawler in self.__brawlers:
            if brawler not in STATS[server_id][self.__map]:
                STATS[server_id][self.__map][brawler] = {}
            if "VICTORIES" not in STATS[server_id][self.__map][brawler]:
                STATS[server_id][self.__map][brawler]["VICTORIES"] = 0
        if won == True:
            STATS[server_id][self.__map][self.__brawlers[0]]["VICTORIES"] += 1
            STATS[server_id][self.__map][self.__brawlers[1]]["VICTORIES"] += 1
            STATS[server_id][self.__map][self.__brawlers[2]]["VICTORIES"] += 1
        else:
            STATS[server_id][self.__map][self.__brawlers[3]]["VICTORIES"] += 1
            STATS[server_id][self.__map][self.__brawlers[4]]["VICTORIES"] += 1
            STATS[server_id][self.__map][self.__brawlers[5]]["VICTORIES"] += 1
        with open('stats.json', 'w') as jsonfile:
            json.dump(STATS, jsonfile, indent=4)
            jsonfile.truncate()

    # set the result of the played match, if the is one result twice then it has ended (Best of 3)
    async def set_result(self, result: str, channel) -> bool:
        if result in self.__results and (result == "Victory" or result == "Defeat"):
            self.__results.append(result)
            self.pickrate_stats()
            if result == "Victory":
                self.winrate_stats(True)
            elif result == "Defeat":
                self.winrate_stats(False)
            embed: Embed = self.create_embed(result)
            await channel.send(embed=embed)
            return True
        else:
            self.__results.append(result)
            return False

    # switch positions of players in the player list, so the team of the main player is always displayed as the first one
    def switch_players(self, playername: str) -> None:
        if playername == self.__players[3] or playername == self.__players[4] or playername == self.__players[5]:
            self.__players[0], self.__players[3] = switch(
                self.__players[0], self.__players[3])
            self.__players[1], self.__players[4] = switch(
                self.__players[1], self.__players[4])
            self.__players[2], self.__players[5] = switch(
                self.__players[2], self.__players[5])
            self.__brawlers[0], self.__brawlers[3] = switch(
                self.__brawlers[0], self.__brawlers[3])
            self.__brawlers[1], self.__brawlers[4] = switch(
                self.__brawlers[1], self.__brawlers[4])
            self.__brawlers[2], self.__brawlers[5] = switch(
                self.__brawlers[2], self.__brawlers[5])

    def get_playername(self) -> str:
        return self.__playername

    # check if the match belongs to this Power Match
    def is_the_same_match(self, players: List, brawlers: List, gamemode: str, bsmap: str, playername: str, channel) -> int:
        if collections.Counter(self.__players) == collections.Counter(players):
            if collections.Counter(self.__brawlers) == collections.Counter(brawlers):
                if self.__gamemode == gamemode and self.__map == bsmap and self.__channel == channel:
                    if self.__playername == playername:
                        return 1
                    else:
                        return 2
        if self.__playername == playername:
            return 3
        return 0


# list of matches which aren´t done yet
POWER_MATCHES: List[PowerMatch] = []

# list of old matches, so the aren´t any duplicates
OLD_MATCHES: List[PowerMatch] = []


async def send_help(ctx: Context) -> None:
    message: str = f"""__**SCRIMS BOT**__
Spectating all scrims of professional players of your choice! Also sends weekly statistics on what are the most played brawlers!
    
**d!help**: Displays the list of available commands
**d!set_room [room_id]**: Sets the room where the bot will send all played scrims
**d!set_stats_room [room_id]**: Sets the room where the bot will post the weekly statistics
**d!add_player [player_tag]**: Adds a player to the list of tracked players for friendly games
**d!remove_player [player_tag]**: Removes a player from the list of tracked players for scrims
**d!player_list**: Displays the list of tracked players for scrims
**d!get_stats [mode]:** Displays the weekly statistics for the specified game mode. Supported game modes are: Gem Grab, Brawl Ball, Bounty, Heist, Knockout and Hot Zone
**d!set_stats_count [number]:** Changes number of brawlers to show stats of (15 without setting, mobile capped at 20). 
"""
    await ctx.send(message)


# get in-game name of a player from Brawl Stars API by his game tag
async def get_playername(playertag: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BS_API}/players/%23{playertag}", headers={"authorization": BS_TOKEN}) as response:
            if response.status == 200:
                data = await response.json()
                return str(data["name"])
            else:
                return "error"


# returns better text of gamemodes do display
def mode_name(mode: str) -> str:
    if mode == "gemGrab":
        return "Gem Grab"
    elif mode == "brawlBall":
        return "Brawl Ball"
    elif mode == "heist":
        return "Heist"
    elif mode == "bounty":
        return "Bounty"
    elif mode == "knockout":
        return "Knockout"
    elif mode == "hotZone":
        return "Hot Zone"
    else:
        return mode


# checks for gamemode emote
def get_mode_emote(mode: str) -> str:
    if mode == "Gem Grab":
        return "<:GEMGRAB:1084821494506475560>"
    elif mode == "Brawl Ball":
        return "<:BRAWLBALL:1084821493277523969>"
    elif mode == "Heist":
        return "<:HEIST:1084821486478573619>"
    elif mode == "Bounty":
        return "<:BOUNTY:1084821491742421082>"
    elif mode == "Knockout":
        return "<:KNOCKOUT:1084821485153173584>"
    elif mode == "Hot Zone":
        return "<:HOTZONE:1084821488860934166>"
    else:
        return ""


# checks if the map is from the maps we want
def get_map_mode(map: str) -> int:
    if map in MAPS_GEM_GRAB:
        return "Gem Grab"
    elif map in MAPS_BRAWL_BALL:
        return "Brawl Ball"
    elif map in MAPS_BOUNTY:
        return "Bounty"
    elif map in MAPS_HEIST:
        return "Heist"
    elif map in MAPS_KNOCKOUT:
        return "Knockout"
    elif map in MAPS_HOT_ZONE:
        return "Hot Zone"
    else:
        return ""


def switch(p1: str, p2: str):
    pom: str = p1
    p1 = p2
    p2 = pom
    return p1, p2


# gets one battle and sends it to object Power Match
async def send_battle(battle: dict, playername: str, channel) -> None:
    brawlers: List[str] = []
    brawlers.append(battle["battle"]["teams"][0][0]["brawler"]["name"])
    brawlers.append(battle["battle"]["teams"][0][1]["brawler"]["name"])
    brawlers.append(battle["battle"]["teams"][0][2]["brawler"]["name"])
    brawlers.append(battle["battle"]["teams"][1][0]["brawler"]["name"])
    brawlers.append(battle["battle"]["teams"][1][1]["brawler"]["name"])
    brawlers.append(battle["battle"]["teams"][1][2]["brawler"]["name"])
    players: List[str] = []
    players.append(battle["battle"]["teams"][0][0]["name"])
    players.append(battle["battle"]["teams"][0][1]["name"])
    players.append(battle["battle"]["teams"][0][2]["name"])
    players.append(battle["battle"]["teams"][1][0]["name"])
    players.append(battle["battle"]["teams"][1][1]["name"])
    players.append(battle["battle"]["teams"][1][2]["name"])
    mode: str = mode_name(battle["battle"]["mode"])
    result: str = battle["battle"]["result"].capitalize()
    bsmap: str = battle['event']['map']
    if get_map_mode(bsmap) != "":
        for power_match in POWER_MATCHES:
            is_the_same: int = power_match.is_the_same_match(
                players, brawlers, mode, bsmap, playername, channel)
            if is_the_same == 1:
                # the match is already being played
                if await power_match.set_result(result, channel) == True:
                    OLD_MATCHES.append(power_match)
                    POWER_MATCHES.remove(power_match)
                    return
            elif is_the_same == 2:
                # the match is already being played but from another player
                return
            elif is_the_same == 3:
                # its wasnt a Power Match (not played 2 matches)
                POWER_MATCHES.remove(power_match)
        for match in OLD_MATCHES:
            if match.is_the_same_match(players, brawlers, mode, bsmap, playername, channel) == 2:
                return
        # creating new Power Match object
        power_match = PowerMatch(playername, players[0], players[1], players[2], players[3], players[4], players[5], brawlers[0],
                                 brawlers[1], brawlers[2], brawlers[3], brawlers[4], brawlers[5], mode, bsmap, result, channel, battle["battle"]["type"])
        power_match.switch_players(playername)
        POWER_MATCHES.append(power_match)
        return
    return


# checks battle log and sends every mode played not more than 10 minutes ago to send_battle()
async def scanning_friendly_games(battle_logs: dict, timestamp_now):
    OLD_MATCHES.clear()
    for playername, data in battle_logs.items():
        for battle in reversed(data[0]["items"]):
            if "type" in battle["battle"]:
                if (battle["battle"]["type"] == "friendly" or battle["battle"]["type"] == "tournament") and "teams" in battle["battle"]:
                    if type(battle["battle"]["teams"]) == list and len(battle["battle"]["teams"]) == 2:
                        if len(battle["battle"]["teams"][0]) == 3 and len(battle["battle"]["teams"][1]) == 3:
                            date = battle["battleTime"]
                            year = int(date[0:4])
                            month = int(date[4:6])
                            day = int(date[6:8])
                            hour = int(date[9:11])
                            minute = int(date[11:13])
                            sec = int(date[13:15])
                            time_of_battle = datetime.datetime(
                                year, month, day, hour, minute, sec)
                            timestamp_of_battle = datetime.datetime.timestamp(
                                time_of_battle)
                            if (timestamp_now - timestamp_of_battle) < 600:
                                await send_battle(battle, playername, data[1])


# gets battle log of a certain played
async def get_battle_logs(server_id, players: dict, channel) -> dict:
    battle_logs: dict = {}
    for player in players:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BS_API}/players/%23{player}/battlelog", headers={"authorization": BS_TOKEN}) as response:
                if response.status == 200:
                    data = await response.json()
                    playername: str = await get_playername(player)
                    if playername != "error":
                        SERVERS[server_id]["players"][player] = playername
                    battle_logs[playername] = (data, channel)
                else:
                    print(await response.json())
    return battle_logs


# calculates and creates a message of statistics (pickrate and winrate)
async def get_stats(channel, mode: str) -> None:
    server_id = str(channel.guild.id)
    mode_emote = get_mode_emote(mode)
    if mode_emote == "":
        await channel.send("Wrong gamemode.")
        return
    if server_id in STATS and mode_emote != "":
        if "COUNT" not in STATS[server_id]:
            STATS[server_id]["COUNT"] = 15
        embed = Embed(title=f"**BRAWLERS STATS**",
                      description="Pickrates and Winrates", color=0x5900ff)
        # for mobile version of discord (normal embed is not showing correctly)
        embed_mobile = Embed(title=f"**BRAWLERS STATS**",
                             description="Pickrates and Winrates", color=0x5900ff)
        embed.add_field(
            name=f"__**{mode}**__ {mode_emote}", value=f"\n", inline=False)
        embed_mobile.add_field(
            name=f"__**{mode}**__ {mode_emote}", value=f"\n", inline=False)
        for map in STATS[server_id]:
            if get_map_mode(map) == mode:
                message_brawlers: str = ""
                message_pickrate: str = ""
                message_winrate: str = ""
                message_mobile: str = ""
                brawlers_stats: dict = {}
                winrate: float = 0
                picks: float = 0
                victories: float = 0
                for brawler, brawler_info in STATS[server_id][map].items():
                    if "PICKS" in brawler_info:
                        picks += float(brawler_info["PICKS"])
                    if "VICTORIES" in brawler_info:
                        victories += float(brawler_info["VICTORIES"])
                for brawler, brawler_info in STATS[server_id][map].items():
                    brawler_picks: float = float(brawler_info["PICKS"])
                    brawler_victories: float = float(brawler_info["VICTORIES"])
                    if brawler_picks > 0:
                        # calculating the statistics
                        pickrate: float = (brawler_picks/(picks/6))*100
                        winrate: float = (brawler_victories/brawler_picks)*100
                        brawlers_stats[brawler] = {
                            "WINRATE": winrate, "PICKRATE": pickrate}
                count: int = int(STATS[server_id]["COUNT"])
                count_mobile: int = 20
                # sorting the dictionary by pickrate
                sorteddict: dict = collections.OrderedDict(
                    sorted(brawlers_stats.items(), key=lambda t: t[1]["PICKRATE"]))
                for brawler, brawler_stats in reversed(sorteddict.items()):
                    if count > 0:
                        emote: str
                        if brawler in BRAWLER_EMOTES:
                            emote = BRAWLER_EMOTES[brawler]
                        else:
                            emote = ""
                        message_brawlers = message_brawlers + \
                            f"{emote} {brawler}\n"
                        message_pickrate = message_pickrate + \
                            f"{int(brawler_stats['PICKRATE'])} %\n"
                        message_winrate = message_winrate + \
                            f"{int(brawler_stats['WINRATE'])} %\n"
                        if count_mobile > 0:
                            message_mobile = message_mobile + \
                                f"{emote} {brawler} {int(brawler_stats['PICKRATE'])} % {int(brawler_stats['WINRATE'])} %\n"
                            count_mobile -= 1
                        count -= 1
                embed.add_field(
                    name=f"{map}", value=f"{message_brawlers}", inline=True)
                embed.add_field(
                    name=f"-PR-", value=f"{message_pickrate}", inline=True)
                embed.add_field(
                    name=f"-WR-", value=f"{message_winrate}", inline=True)
                embed.add_field(name=f"", value=f"", inline=False)
                embed_mobile.add_field(
                    name=f"{map}", value=f"{message_mobile}", inline=False)
        msg: Message = await channel.send(embed=embed)
        await msg.add_reaction("📱")
        MESSAGES_STATS.append(msg)
        EMBEDS_MOBILE.append(embed_mobile)
        EMBEDS_PC.append(embed)


@bot.event
async def on_ready():
    loop_scan.start()
    loop_stats.start()


@bot.event
async def on_server_join(guild):
    SERVERS[guild.id] = {}
    print(f"Joined {guild.id}")

# when someone reacts to statistics message with mobile phone emote then the message changes to mobile version of it, works both ways


@bot.event
async def on_reaction_add(reaction, user):
    i: int = 0
    for message in MESSAGES_STATS:
        if reaction.message == message and user.bot == False:
            if str(reaction.emoji) == "📱":
                await reaction.message.edit(embed=EMBEDS_MOBILE[i])
                await reaction.message.clear_reactions()
                await reaction.message.add_reaction("🖥️")
            elif str(reaction.emoji) == "🖥️":
                await reaction.message.edit(embed=EMBEDS_PC[i])
                await reaction.message.clear_reactions()
                await reaction.message.add_reaction("📱")
            else:
                reaction.remove(user)
        i += 1


@bot.event
async def on_server_leave(guild):
    SERVERS.pop(guild.id, None)


@bot.command(name="help")
async def helps(ctx: Context) -> None:
    await send_help(ctx)


# sets room where the scrims should be sent
@bot.command(name="set_room")
async def set_room(ctx: Context, room: str) -> None:
    channel = ctx.guild.get_channel(int(room))
    if channel == None:
        await ctx.send(f"Wrong room id.")
    else:
        guild: str = str(ctx.guild.id)
        if guild not in SERVERS:
            SERVERS[guild] = {}
        SERVERS[guild]["room"] = int(room)
        await ctx.send(f"Room set to {channel.name}.")
        with open('servers.json', 'w') as jsonfile:
            json.dump(SERVERS, jsonfile, indent=4)
            jsonfile.truncate()


# sets room where the statistics should be sent
@bot.command(name="set_stats_room")
async def set_room(ctx: Context, room: str) -> None:
    channel = ctx.guild.get_channel(int(room))
    if channel == None:
        await ctx.send(f"Wrong room id.")
    else:
        guild: str = str(ctx.guild.id)
        if guild not in STATS:
            STATS[guild] = {}
        STATS[guild]["stats_room"] = int(room)
        await ctx.send(f"Stats room set to {channel.name}.")
        with open('stats.json', 'w') as jsonfile:
            json.dump(STATS, jsonfile, indent=4)
            jsonfile.truncate()


# adds a player by his id to json file of players to spectate
@bot.command(name="add_player")
async def add(ctx: Context, playertag: str) -> None:
    playername: str = await get_playername(playertag)
    if playername != "error":
        guild: str = str(ctx.guild.id)
        if guild not in SERVERS:
            SERVERS[guild] = {}
        if "players" not in SERVERS[guild]:
            SERVERS[guild]["players"] = {}
        if playertag not in SERVERS[guild]["players"]:
            SERVERS[guild]["players"][playertag] = playername
            await ctx.send(f"Player {playername} added.")
            with open('servers.json', 'w') as jsonfile:
                json.dump(SERVERS, jsonfile, indent=4)
                jsonfile.truncate()
        else:
            await ctx.send(f"Player {playername} was already added.")
    else:
        await ctx.send(f"Player with Tag {playertag} couldn't be added.\nCheck for errors in Player Tag.")


# removes a player from the json file
@bot.command(name="remove_player")
async def remove(ctx: Context, playertag: str) -> None:
    guild: str = str(ctx.guild.id)
    if guild not in SERVERS:
        SERVERS[guild] = {}
    if "players" not in SERVERS[guild]:
        SERVERS[guild]["players"] = {}
        print(SERVERS[str(guild)]["players"])
    if playertag in SERVERS[guild]["players"]:
        playername: str = SERVERS[guild]["players"][playertag]
        SERVERS[guild]["players"].pop(playertag, None)
        await ctx.send(f"Player {playername} deleted.")
    else:
        await ctx.send(f"Player with playertag {playertag} is not in your player list.")


# displays the list of players we want to spectate
@bot.command(name="player_list")
async def player_list(ctx: Context) -> None:
    guild: str = str(ctx.guild.id)
    if guild not in SERVERS:
        SERVERS[guild] = {}
    if "players" not in SERVERS[guild]:
        SERVERS[guild]["players"] = {}
    if len(SERVERS[guild]["players"]) == 0:
        await ctx.send(f"No players.")
    else:
        message: str = "**Players:**\n"
        for playertag, playername in SERVERS[guild]["players"].items():
            message = message + str(playername) + ": " + str(playertag) + "\n"
        await ctx.send(message)


# shows statistics from last week
@bot.command(name="get_stats")
async def stats(ctx: Context, *, mode: str) -> None:
    channel = ctx.channel
    await get_stats(channel, mode)


# sets number of brawlers to display when showing stats
@bot.command(name="set_stats_count")
async def stats(ctx: Context, count: int) -> None:
    if count <= 25:
        server_id = str(ctx.guild.id)
        if server_id not in STATS:
            STATS[server_id] = {}
        STATS[server_id]["COUNT"] = count
        await ctx.send(f"Number of brawlers to show stats of set to {count}.")
        with open('stats.json', 'w') as jsonfile:
            json.dump(STATS, jsonfile, indent=4)
            jsonfile.truncate()
    else:
        await ctx.send(f"ERROR\nNumber of brawlers to show stats of must be 25 or lower.")


# loop every 10 minutes, shows every match that has been played in those 10 minutes
@tasks.loop(minutes=10)
async def loop_scan() -> None:
    now = datetime.datetime.now()
    timestamp_now = datetime.datetime.timestamp(now)
    battle_logs: dict = {}
    for server_id, server_info in SERVERS.items():
        if "room" in server_info and "players" in server_info:
            channel = bot.get_guild(
                int(server_id)).get_channel(server_info["room"])
            if channel != None:
                battle_logs[server_id] = await get_battle_logs(server_id, server_info["players"], channel)
    for server in battle_logs:
        await scanning_friendly_games(battle_logs[server], timestamp_now)

    with open('servers.json', 'w') as jsonfile:
        json.dump(SERVERS, jsonfile, indent=4)
        jsonfile.truncate()


# loop every 7 days, shows statistics of all gamemodes
@tasks.loop(hours=168)
async def loop_stats() -> None:
    if loop_stats.current_loop != 0:
        if STATS != {}:
            for server_id, stats_info in STATS.items():
                if "stats_room" in stats_info:
                    channel = bot.get_guild(int(server_id)).get_channel(
                        stats_info["stats_room"])
                    if channel != None:
                        await get_stats(channel, "Gem Grab")
                        await get_stats(channel, "Brawl Ball")
                        await get_stats(channel, "Bounty")
                        await get_stats(channel, "Heist")
                        await get_stats(channel, "Knockout")
                        await get_stats(channel, "Hot Zone")
        # clears every list to save some space
        STATS.clear()
        MESSAGES_STATS.clear()
        EMBEDS_MOBILE.clear()
        EMBEDS_PC.clear()
        with open('stats.json', 'w') as jsonfile:
            json.dump(STATS, jsonfile, indent=4)
            jsonfile.truncate()


bot.run(TOKEN)
