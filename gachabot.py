### Gacha Bot for War of Gama
### Created by pianosuki
### https://github.com/pianosuki
### For use by Catheon only
branch_name = "War of GAMA"
bot_version = "1.9"
debug_mode  = False

import config, dresource
from database import Database
import discord, re, time, random, json, math, hashlib, urllib.parse, pandas
from discord.ext import commands
from datetime import datetime
import numpy as np
from collections import Counter
from os.path import exists as file_exists
from os import makedirs

intents                 = discord.Intents.default()
intents.message_content = True
intents.members         = True
bot                     = commands.Bot(command_prefix = "!" if debug_mode else config.prefix, intents = intents)

# Gacha
GachaDB = Database("gachadata.db")
GachaDB.execute("CREATE TABLE IF NOT EXISTS userdata (user_id INTEGER PRIMARY KEY UNIQUE, gacha_tickets INTEGER, gacha_fragments INTEGER, total_rolls INTEGER)")
GachaDB.execute("CREATE TABLE IF NOT EXISTS prizehistory (prize_id TEXT PRIMARY KEY UNIQUE, user_id INTEGER, date TEXT, tickets_spent TEXT, tier TEXT, capsule TEXT, prize TEXT)")
GachaDB.execute("CREATE TABLE IF NOT EXISTS backstock (prize TEXT PRIMARY KEY UNIQUE, current_stock INTEGER, times_rolled INTEGER, max_limit INTEGER)")

# Market
MarketDB = Database("marketdata.db")
MarketDB.execute("CREATE TABLE IF NOT EXISTS userdata (user_id INTEGER PRIMARY KEY UNIQUE, ryou INTEGER)")

# User Items
ItemsDB = Database("useritems.db")

# Activity
ActivityDB = Database("activity.db")
ActivityDB.execute("CREATE TABLE IF NOT EXISTS quests (user_id INTEGER PRIMARY KEY UNIQUE, last_activity INTEGER)")
ActivityDB.execute("CREATE TABLE IF NOT EXISTS dungeons (user_id INTEGER PRIMARY KEY UNIQUE, last_activity INTEGER)")
ActivityDB.execute("CREATE TABLE IF NOT EXISTS chat (user_id INTEGER PRIMARY KEY UNIQUE, last_activity INTEGER)")

# Quests
QuestsDB = Database("quests.db")
QuestsDB.execute("CREATE TABLE IF NOT EXISTS quests (user_id INTEGER PRIMARY KEY UNIQUE, quest TEXT)")

# Dungeons
DungeonsDB = Database("dungeons.db")
DungeonsDB.execute("CREATE TABLE IF NOT EXISTS clears (clear_id TEXT PRIMARY KEY UNIQUE, user_id INTEGER, date TEXT, dungeon TEXT, mode INTEGER, clear_time TEXT, seed TEXT)")

# Player Data
PlayerDB = Database("playerdata.db")
PlayerDB.execute("CREATE TABLE IF NOT EXISTS userdata (user_id INTEGER PRIMARY KEY UNIQUE, exp INTEGER, energy INTEGER, last_refresh INTEGER)")
# PlayerDB.execute("ALTER TABLE userdata ADD COLUMN energy INTEGER")
# PlayerDB.execute("ALTER TABLE userdata ADD COLUMN last_refresh INTEGER")

# Player Stat Points
StatsDB = Database("playerstats.db")
StatsDB.execute("CREATE TABLE IF NOT EXISTS userdata (user_id INTEGER PRIMARY KEY UNIQUE, points INTEGER, hp INTEGER, atk INTEGER, def INTEGER)")

# Objects
Prizes      = json.load(open("prizes.json")) # Load list of prizes for the gacha to pull from
Products    = json.load(open("products.json")) # Load list of products for shop to sell
Graphics    = json.load(open("graphics.json")) # Load list of graphical assets to build Resource with
Quests      = json.load(open("quests.json")) # Load list of quests for the questing system
Dungeons    = json.load(open("dungeons.json")) # Load list of dungeons for the dungeon system
Tables      = json.load(open("tables.json")) # Load tables for systems to use constants from
Resource    = dresource.resCreate(Graphics) # Generate discord file attachment resource
Icons       = {**config.custom_emojis, **config.mode_emojis, **config.element_emojis, **config.nigiri_emojis}

# Names
coin_name = config.coin_name

@bot.event
async def on_ready():
    # Go Online
    await bot.change_presence(status = discord.Status.online, activity = discord.Game(f"{config.prefix}roll to spin the Gacha!"))
    print(f"Logged in as {bot.user} | Version: {bot_version}")

# @bot.event
# async def on_message(ctx):
#     if ctx.author.bot:
#         return
#     if ctx.channel.id in config.channels["chat_earn"]:
#         user_id = ctx.author.id
#         level = getPlayerLevel(user_id)
#         ryou_earn_range = config.chat_ryou_earn
#         chat_earn_wait = config.chat_earn_wait
#         last_chat = getLastChat(user_id)
#         now = int(time.time())
#         if now >= last_chat:
#             marketdata = getUserMarketInv(user_id)
#             ryou = marketdata.ryou
#             ryou_earned = random.randint(ryou_earn_range[0], ryou_earn_range[1]) * level
#             MarketDB.execute("UPDATE userdata SET ryou = ? WHERE user_id = ?", (ryou + ryou_earned, user_id))
#             ActivityDB.execute("UPDATE chat SET last_activity = ? WHERE user_id = ?", (now + chat_earn_wait, user_id))
#             await ctx.add_reaction(Icons["ryou"])
#     await bot.process_commands(ctx)

### Functions
def checkChannel(ctx):
    command = str(ctx.command)
    if ctx.channel.id in config.channels[command] or checkAdmin(ctx):
        return True

def checkAdmin(ctx):
    if ctx.author.id in config.admin_list:
        return True
    admin_role = discord.utils.get(ctx.guild.roles, name = config.admin_role)
    if admin_role in ctx.author.roles:
        return True

def convertMentionToId(target):
    return int(target[1:][:len(target)-2].replace("@","").replace("&",""))

async def waitForReaction(ctx, message, e, emojis, modmsg = True):
    for emoji in emojis:
        await message.add_reaction(emoji)

    def checkReaction(reaction, user):
        return user != bot.user and reaction.message == message and user == ctx.author and str(reaction.emoji) in emojis

    # Wait for user to react
    try:
        reaction, user = await bot.wait_for("reaction_add", check = checkReaction, timeout = 120)
    except Exception as error:
        # Operation timed out
        await message.clear_reactions()
        if modmsg:
            e.description = "Operation timed out!"
            e.color = 0xe3e6df
        await message.edit(embed = e)
        return None, None
    return reaction, user

async def addRole(ctx, role_name):
    role = discord.utils.get(ctx.author.guild.roles, name = role_name)
    user_roles = [role.name for role in ctx.author.roles]
    if role_name not in user_roles:
        await ctx.author.add_roles(role)
        await ctx.send(f"🎉 Added role `@{role_name}` to {ctx.author.mention}!")

def getUserGachaInv(user_id):
    GachaDB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values (%s, '0', '0', '0')" % str(user_id))
    inventory = GachaDB.userdata[user_id]
    return inventory

def getUserMarketInv(user_id):
    MarketDB.execute("INSERT OR IGNORE INTO userdata (user_id, ryou) VALUES (%s, '0')" % str(user_id))
    inventory = MarketDB.userdata[user_id]
    return inventory

def getUserItemInv(user_id):
    ItemsDB.execute("CREATE TABLE IF NOT EXISTS user_%s (item TEXT PRIMARY KEY UNIQUE, quantity INTEGER)" % str(user_id))
    inventory = ItemsDB.query("SELECT * FROM user_%s" % str(user_id))
    return inventory

def getLastQuest(user_id):
    ActivityDB.execute("INSERT OR IGNORE INTO quests (user_id, last_activity) VALUES (%s, '0')" % str(user_id))
    last_quest = ActivityDB.quests[user_id].last_activity
    return last_quest

def getLastDungeon(user_id):
    ActivityDB.execute("INSERT OR IGNORE INTO dungeons (user_id, last_activity) VALUES (%s, '0')" % str(user_id))
    last_dungeon = ActivityDB.dungeons[user_id].last_activity
    return last_dungeon

def getLastChat(user_id):
    ActivityDB.execute("INSERT OR IGNORE INTO chat (user_id, last_activity) VALUES (%s, '0')" % str(user_id))
    last_chat = ActivityDB.chat[user_id].last_activity
    return last_chat

def getPlayerData(user_id):
    PlayerDB.execute("INSERT OR IGNORE INTO userdata (user_id, exp, energy, last_refresh) VALUES (%s, '0', '0', '0')" % str(user_id))
    playerdata = PlayerDB.query(f"SELECT * FROM userdata WHERE user_id = '{user_id}'")
    return playerdata

def getPlayerExp(user_id):
    PlayerDB.execute("INSERT OR IGNORE INTO userdata (user_id, exp, energy, last_refresh) VALUES (%s, '0', '0', '0')" % str(user_id))
    exp = PlayerDB.query(f"SELECT exp FROM userdata WHERE user_id = '{user_id}'")[0][0]
    return exp

def getPlayerRyou(user_id):
    MarketDB.execute("INSERT OR IGNORE INTO userdata (user_id, ryou) VALUES (%s, '0')" % str(user_id))
    ryou = MarketDB.query(f"SELECT ryou FROM userdata WHERE user_id = '{user_id}'")[0][0]
    return ryou

def getPlayerEnergy(user_id):
    PlayerDB.execute("INSERT OR IGNORE INTO userdata (user_id, exp, energy, last_refresh) VALUES (%s, '0', '0', '0')" % str(user_id))
    updatePlayerEnergy(user_id)
    energy = PlayerDB.query(f"SELECT energy FROM userdata WHERE user_id = '{user_id}'")[0][0]
    return energy

def getPlayerMaxEnergy(user_id):
    player_level = getPlayerLevel(user_id)
    max_energy = player_level if player_level > 50 else 50
    return max_energy

def getPlayerLastRefresh(user_id):
    PlayerDB.execute("INSERT OR IGNORE INTO userdata (user_id, exp, energy, last_refresh) VALUES (%s, '0', '0', '0')" % str(user_id))
    last_refresh = PlayerDB.query(f"SELECT last_refresh FROM userdata WHERE user_id = '{user_id}'")[0][0]
    return last_refresh

def updatePlayerEnergy(user_id):
    now = int(time.time())
    max_energy = getPlayerMaxEnergy(user_id)
    cold_energy = PlayerDB.query(f"SELECT energy FROM userdata WHERE user_id = '{user_id}'")[0][0]
    cold_energy = cold_energy if not cold_energy is None else 0
    last_refresh = PlayerDB.query(f"SELECT last_refresh FROM userdata WHERE user_id = '{user_id}'")[0][0]
    last_refresh = last_refresh if not last_refresh is None else 0
    seconds_passed = now - last_refresh
    minutes_passed = math.floor(seconds_passed / 60)
    remainder = seconds_passed - (minutes_passed * 60)
    energy_refilled = math.floor(minutes_passed / 6)
    hot_energy = cold_energy + energy_refilled if not cold_energy + energy_refilled > max_energy else max_energy
    if minutes_passed >= 6:
        PlayerDB.execute("UPDATE userdata SET energy = ?, last_refresh = ? WHERE user_id = ?", (hot_energy, now - remainder, user_id))
    return

def addPlayerEnergy(user_id, energy_reward):
    energy      = getPlayerEnergy(user_id)
    max_energy  = getPlayerMaxEnergy(user_id)
    if energy + energy_reward > max_energy:
        energy_reward -= (energy + energy_reward - max_energy)
    PlayerDB.execute("UPDATE userdata SET energy = ? WHERE user_id = ?", (energy + energy_reward, user_id))
    return energy_reward

def addPlayerExp(user_id, exp_reward):
    ExpTable = Tables["ExpTable"]
    exp = getPlayerExp(user_id)
    max_exp = ExpTable[config.level_cap - 1][1]
    if exp + exp_reward > max_exp:
        exp_reward -= (exp + exp_reward - max_exp)
    PlayerDB.execute("UPDATE userdata SET exp = ? WHERE user_id = ?", (exp + exp_reward, user_id))
    return exp_reward

def addPlayerRyou(user_id, ryou_reward):
    ryou = getPlayerRyou(user_id)
    MarketDB.execute("UPDATE userdata SET ryou = ? WHERE user_id = ?", (ryou + ryou_reward, user_id))
    return ryou_reward

def getPlayerLevel(user_id):
    ExpTable = Tables["ExpTable"]
    exp = getPlayerExp(user_id)
    for row in ExpTable:
        if exp >= row[1]:
            continue
        else:
            level = row[0] - 1
            break
    return level

def getPlayerStatPoints(user_id, stats_query: str = None):
    stats_query = stats_query.lower() if not stats_query is None else None
    level = getPlayerLevel(user_id)
    default_points = level - 1
    StatsDB.execute("INSERT OR IGNORE INTO userdata (user_id, points, hp, atk, def) VALUES ({}, {}, '0', '0', '0')".format(user_id, default_points))
    if stats_query in ["ponts", "hp", "atk", "def"]:
        stat_points = StatsDB.query(f"SELECT {stats_query} FROM userdata WHERE user_id = '{user_id}'")[0][0]
    else:
        points = StatsDB.query(f"SELECT points FROM userdata WHERE user_id = '{user_id}'")[0][0]
        hp_stat = StatsDB.query(f"SELECT hp FROM userdata WHERE user_id = '{user_id}'")[0][0]
        atk_stat = StatsDB.query(f"SELECT atk FROM userdata WHERE user_id = '{user_id}'")[0][0]
        def_stat = StatsDB.query(f"SELECT def FROM userdata WHERE user_id = '{user_id}'")[0][0]
        stat_sum = hp_stat + atk_stat + def_stat
        if stat_sum != level - 1 or points < 0:
            points = (level - 1) - stat_sum
            StatsDB.execute(f"UPDATE userdata SET points = ? WHERE user_id = ?", (points, user_id))
        stat_points = {"points": points, "hp": hp_stat, "atk": atk_stat, "def": def_stat}
    return stat_points

def getPlayerHP(user_id):
    level = getPlayerLevel(user_id)
    hp_stat = getPlayerStatPoints(user_id, "hp")
    HP = ((level * 100) + (level ** 2)) + (math.floor(((hp_stat * 5) ** 2)))
    return HP

def getPlayerATK(user_id):
    level = getPlayerLevel(user_id)
    atk_stat = getPlayerStatPoints(user_id, "atk")
    ATK = (level * 10) + (math.floor((atk_stat * 5)))
    return ATK

def getPlayerDEF(user_id):
    level = getPlayerLevel(user_id)
    def_stat = getPlayerStatPoints(user_id, "def")
    DEF = (level * 10) + (math.floor((def_stat * 5)))
    return DEF

def addPlayerStatPoints(user_id, stats_query, amount):
    stats_query = str(stats_query).lower()
    stat_points = getPlayerStatPoints(user_id)
    if stats_query in stat_points:
        if stat_points["points"] > 0 or stats_query == "points":
            new_total = stat_points[stats_query] + amount
            StatsDB.execute(f"UPDATE userdata SET {stats_query} = ? WHERE user_id = ?", (new_total, user_id))
            return new_total
    return None

def getUserBoost(ctx):
    role_boosts = config.role_boosts
    user = ctx.author
    user_roles = [role.name for role in user.roles]
    boost = 0
    for role in user_roles:
        if role in role_boosts:
            boost += role_boosts[role]
    return boost

def getPlayerQuest(user_id):
    QuestsDB.execute("INSERT OR IGNORE INTO quests (user_id, quest) VALUES (%s, '')" % str(user_id))
    quest = QuestsDB.query(f"SELECT quest FROM quests WHERE user_id = '{user_id}'")[0][0]
    return quest

def getPlayerDungeonClears(user_id):
    dungeon_clears = DungeonsDB.query(f"SELECT * FROM clears WHERE user_id = '{user_id}'")
    return dungeon_clears

def addPlayerDungeonClear(user_id, dg):
    dungeon_clears = getPlayerDungeonClears(user_id)
    total_clears = len(dungeon_clears)
    clear_id = str(user_id) + str("{:05d}".format(total_clears + 1))
    date = str(dg.Cache.end_time)
    dungeon = dg.dungeon
    mode = dg.mode
    clear_time = dg.Cache.clear_time
    seed = dg.seed
    DungeonsDB.execute("INSERT INTO clears (clear_id, user_id, date, dungeon, mode, clear_time, seed) VALUES (?, ?, ?, ?, ?, ?, ?)", (clear_id, user_id, date, dungeon, mode, clear_time, seed))
    return

def getUserItemQuantity(user_id, product):
    items_inv = getUserItemInv(user_id)
    if not items_inv:
        return None
    for item in items_inv:
        if item[0] == product:
            item_quantity = item[1]
            break
        else:
            item_quantity = None
    return item_quantity

def getPlayerDungeonRecord(user_id, dungeon, mode):
    clears = getPlayerDungeonClears(user_id)
    clear_times = []
    for clear in clears:
        if clear[3] == dungeon and clear[4] == mode:
            clear_times.append(datetime.strptime(clear[5], "%H:%M:%S.%f"))
    clear_times.sort()
    if clear_times:
        best_time = clear_times[0].strftime("%H:%M:%S.%f")
    else:
        best_time = "None"
    return best_time

def getPlayerExpToNextLevel(user_id):
    ExpTable = Tables["ExpTable"]
    exp = getPlayerExp(user_id)
    level = getPlayerLevel(user_id)
    next_level = ExpTable[level][1]
    exp_to_next = next_level - exp
    return exp_to_next

def randomWeighted(list, weights):
    weights = np.array(weights, dtype=np.float64)
    weights_sum = weights.sum()
    np.multiply(weights, 1 / weights_sum, weights)
    cum_weights = weights.cumsum()
    x = random.random()
    for i in range(len(cum_weights)):
        if x < cum_weights[i]:
            return list[i]

def rebalanceWeights(cold_weights):
    total = 0
    relevant_length = 0
    for i in cold_weights:
        total += i
        if i > 0:
            relevant_length += 1
    if total < 100:
        # Calculate how much is missing to make weights sum to 100 then distribute that amount evenly to add into each weight
        refill = (100 - total) / relevant_length
        index = 0
        hot_weights = cold_weights
        for i in hot_weights:
            if i > 0:
                hot_weights[index] = i + refill
            index +=1
        return hot_weights
    elif total > 100:
        # Calculate the proportional weights and downscale to them with that ratio so everything sums to 100
        index = 0
        hot_weights = cold_weights
        for i in hot_weights:
            if i > 0:
                cross = i * 100
                proportion = cross / total
                hot_weights[index] = proportion
            index +=1
        return hot_weights
    else:
        return cold_weights

def generateFileObject(object, path):
    Resource[object][1] = discord.File(path)
    return Resource[object][1]

def getMaxItemWidth(array, min_width = 0):
    max_width = min_width
    for item in array:
        match item:
            case str() | list() | dict():
                item_length = len(item)
            case int():
                item_length = item
            case _:
                item_length = 0
        max_width = item_length if item_length > max_width else max_width
    return max_width

def boxifyArray(array, padding = 1, min_width = 0, spacer_character = "-"):
    if type(array) is dict:
        array = list(array.keys())

    boxified_string = ""
    border_width = getMaxItemWidth(array, min_width)

    # Build the box
    for index, item in enumerate(array):
        item_length = len(item)
        negative_space = border_width - item_length
        spacer1 = spacer2 = ""

        # Add extra padding if any
        for _ in range(padding):
            spacer1 += spacer_character
            spacer2 += spacer_character

        # Center the item by alternating adding padding on both sides to fill in negative space
        for i in range(negative_space):
            if (i + 1) % 2 == 0:
                spacer1 += spacer_character
            else:
                spacer2 += spacer_character

        boxified_string += f"║{spacer1}{item}{spacer2}║\n"

    # Set top and bottom borders
    border = ""
    for _ in range(border_width + (padding * 2)):
        border += "═"

    # Add top and bottom borders
    boxified_string = "".join((f"```╔{border}╗\n",boxified_string,f"╚{border}╝```"))

    # Return fully-assembled boxified string
    return boxified_string

### User Commands
# @bot.command(aliases = ["dungeon", "dg", "dung", "run", "warding", "wardings"])
# @commands.check(checkChannel)
# async def dungeons(ctx, *input):
#     ''' | Usage: +dungeons '''
#     user_id                 = ctx.author.id
#     user_name               = ctx.author.name
#     default_color           = config.default_color
#     numbers                 = config.numbers
#     mode_mapping            = config.mode_mapping
#     mode_mapping_inverse    = config.mode_mapping_inverse
#     mode_multipliers        = config.mode_multipliers
#     mode_divisors           = config.mode_divisors
#
#     class DungeonInstance:
#
#         # Mutable Cache
#         class DungeonCache:
#             def __init__(self):
#                 self.floor = 0
#                 self.room = 0
#                 self.mobs = 0
#                 self.goldarumas = 0
#                 self.chests = 0
#                 self.mobs_killed = 0
#                 self.cleared = False
#                 self.start_time = None
#                 self.end_time = None
#                 self.clear_time = None
#
#         class PlayerState:
#             def __init__(self):
#                 self.name = user_name
#                 self.HP = getPlayerHP(user_id)
#                 self.ATK = getPlayerATK(user_id)
#                 self.DEF = getPlayerDEF(user_id)
#                 self.level = getPlayerLevel(user_id)
#
#         class YokaiState:
#             def __init__(self):
#                 self.name = ""
#                 self.HP = 0
#                 self.ATK = 0
#                 self.DEF = 0
#
#         class BossState:
#             def __init__(self):
#                 self.name = ""
#                 self.HP = 0
#                 self.ATK = 0
#                 self.DEF = 0
#                 self.phase = 1
#
#         def __init__(self, dungeon, mode, seed):
#             # Immutable
#             self.dungeon = dungeon
#             self.mode = mode
#             self.mode_name = mode_mapping[self.mode]
#             self.multiplier = mode_multipliers[self.mode]
#             self.properties = Dungeons[dungeon]["Difficulties"][self.mode_name]
#             self.icon = getDungeonModes(type = "array")[self.mode]
#             self.level = Dungeons[dungeon]["Level_Required"]
#             self.floors = Dungeons[dungeon]["Floors"]
#             self.rooms = 0 # Accumulated via Blueprint
#             self.yokai = Dungeons[dungeon]["Yokai"]
#             self.boss = Dungeons[dungeon]["Boss"]
#             self.rewards = Dungeons[dungeon]["Rewards"]
#             self.energy = getDungeonEnergy(dungeon)[self.mode]
#             self.rooms_range = self.properties["rooms_range"] if "rooms_range" in self.properties else config.default_rooms_range
#             self.mob_spawnrate = self.properties["mob_spawnrate"] if "mob_spawnrate" in self.properties else config.default_mob_spawnrate
#             self.goldaruma_spawnrate = self.properties["goldaruma_spawnrate"] if "goldaruma_spawnrate" in self.properties else config.goldaruma_spawnrate
#             self.goldaruma_spawnrate /= 100.
#             self.chest_loot = self.properties["chest_loot"] if "chest_loot" in self.properties else config.default_chest_loot
#
#             # Seed
#             if seed is None:
#                 self.seed = hashlib.md5(str(random.getrandbits(128)).encode("utf-8")).hexdigest()
#             elif re.match("^[a-f0-9]{32}$", seed):
#                 self.seed = seed
#             else:
#                 self.seed = hashlib.md5(seed.encode("utf-8")).hexdigest()
#             self.salt = self.dungeon
#             self.pepper = self.mode_name
#
#             # Initialize Cache
#             self.Cache = self.DungeonCache()
#
#             # Initialize Agents
#             self.Player = self.PlayerState()
#             self.Yokai = self.YokaiState()
#             self.Boss = self.BossState()
#
#             # Initialize Dungeon Blueprint
#             self.Blueprint = {}
#
#         def clearCache(self):
#             self.Cache = self.DungeonCache()
#
#         def dungeonGenesis(self):
#             now = datetime.utcnow()
#             self.Blueprint.update({"header": {"Dungeon": self.dungeon, "Difficulty": self.mode_name, "Seed": self.seed}, "blueprint": {"floors": []}, "footer": {"Founder": user_id, "Discovered": f"{now} (UTC)"}})
#             for _ in range(self.floors):
#                 floor_schematic = self.renderFloor()
#                 self.Blueprint["blueprint"]["floors"].append(floor_schematic)
#             return self.Blueprint
#
#         def renderFloor(self):
#             floor_schematic = {}
#             self.Cache.floor += 1
#             seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
#             salt = "renderFloor"
#             pepper = str(self.Cache.floor)
#             f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8") + pepper.encode("utf-8")).hexdigest()
#             random.seed(f_seed)
#             if self.Cache.floor < self.floors:
#                 floor_schematic.update({"type": "Floor", "rooms": []})
#                 rooms = random.randint(self.rooms_range[0], self.rooms_range[1])
#                 self.rooms += rooms
#                 for _ in range(rooms):
#                     room_schematic = self.renderRoom()
#                     floor_schematic["rooms"].append(room_schematic)
#             else:
#                 floor_schematic.update({"type": "Boss", "boss": {}})
#                 boss_schematic = self.renderBoss()
#                 floor_schematic["boss"].update(boss_schematic)
#             return floor_schematic
#
#         def renderRoom(self):
#             room_schematic = {}
#             self.Cache.room += 1
#             seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
#             salt = "renderRoom"
#             pepper = str(self.Cache.room)
#             f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8") + pepper.encode("utf-8")).hexdigest()
#             random.seed(f_seed)
#             population = random.randint(self.mob_spawnrate[0], self.mob_spawnrate[1])
#             mobs = self.spawnMobs(population)
#             if mobs:
#                 room_schematic.update({"type": "Normal", "yokai": []})
#                 room_schematic["yokai"] = mobs
#             else:
#                 self.Cache.chests += 1
#                 chest = self.spawnChest()
#                 room_schematic.update({"type": "Chest", "loot": []})
#                 room_schematic["loot"] = chest
#             return room_schematic
#
#         def renderBoss(self):
#             boss_schematic = {}
#             boss_schematic.update(Dungeons[self.dungeon]["Boss"])
#             base_hp = Dungeons[self.dungeon]["Boss"]["HP"]
#             scaled_hp = math.floor((base_hp * 0.75) + (base_hp / 4 * self.multiplier))
#             boss_schematic.update({"HP": scaled_hp})
#             return boss_schematic
#
#         def spawnMobs(self, population):
#             seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
#             salt = "spawnMobs"
#             pepper = str(self.Cache.room)
#             f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8") + pepper.encode("utf-8")).hexdigest()
#             random.seed(f_seed)
#             mobs = []
#             if population > 0:
#                 for _ in range(population):
#                     self.Cache.mobs += 1
#                     if random.random() <= self.goldaruma_spawnrate:
#                         is_goldaruma = True
#                         self.Cache.goldarumas += 1
#                     else:
#                         is_goldaruma = False
#                     mobs.append(random.choice(self.yokai) if not is_goldaruma else "Gold Daruma")
#             else:
#                 pass
#             return mobs
#
#         def spawnChest(self):
#             seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
#             salt = "spawnChest"
#             pepper = str(self.Cache.room)
#             f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8") + pepper.encode("utf-8")).hexdigest()
#             random.seed(f_seed)
#             loot_pools = []
#             loot_weights = []
#             for table in self.chest_loot:
#                 pool = table["pool"]
#                 weight = table["rate"]
#                 loot_pools.append(pool)
#                 loot_weights.append(weight)
#             if sum(loot_weights) < 100 or sum(loot_weights) > 100:
#                 loot_weights = rebalanceWeights(loot_weights)
#             random_pool = randomWeighted(loot_pools, loot_weights)
#             chest = {}
#             for key, value in random_pool.items():
#                 loot_name = key
#                 range = value
#                 amount_pulled = random.randint(range[0], range[1])
#                 if not loot_name in chest:
#                     chest.update({loot_name: amount_pulled})
#                 else:
#                     chest.update({loot_name: chest[loot_name] + amount_pulled})
#             return chest
#
#     async def menuDungeons(ctx, message):
#         dungeons_length = len(Dungeons)
#         level = getPlayerLevel(user_id)
#         banner = generateFileObject("Oni-Dungeons", Graphics["Banners"]["Oni-Dungeons"][0])
#         e = discord.Embed(title = "⛩️  ─  Dungeon Listing  ─  ⛩️", description = f"Which dungeon will you be running today?\n**Your level:** {Icons['level']}**{level}**", color = 0x9575cd)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
#
#         # unlocked_dungeons = []
#         # for dungeon in Dungeons:
#         #     if level >= dungeon_level:
#         #         unlocked_dungeons.append(dungeon)
#         #
#         # unlocked_length = len(unlocked_dungeons)
#
#         # Set offset to 0 (page 1) and begin bidirectional page system
#         offset = 0
#         flag = True
#         while flag:
#             counter = 0
#             # Iterate through dungeons in groups of 10
#             for index, dungeon in enumerate(Dungeons):
#                 if index < offset:
#                     # Skipping to next entry until arriving at the proper page/offset
#                     continue
#                 dungeon_level = Dungeons[dungeon]["Level_Required"]
#                 dungeon_emoji = numbers[counter]
#                 unlocked_emoji = "🔓" if level >= dungeon_level else "🔒"
#                 crossout = "~~" if not level >= dungeon_level else ""
#                 bold_or_italics = "**" if not level >= dungeon_level else "*"
#                 e.add_field(name = f"{dungeon_emoji}  ─  __{crossout}{dungeon}{crossout}__", value = f"{unlocked_emoji}  **─**  {bold_or_italics}Level Required:{bold_or_italics} {Icons['level']}**{dungeon_level}**\n`{config.prefix}dungeon {dungeon}`", inline = True)
#                 if not counter % 2 == 0:
#                     e.add_field(name = "\u200b", value = "\u200b", inline = True)
#                 counter += 1
#                 # Once a full page is assembled, print it
#                 if counter == 10 or index + 1 == dungeons_length:
#                     message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
#                     if index + 1 > 10 and index + 1 < dungeons_length:
#                         # Is a middle page
#                         emojis = ["⏪", "⏩", "❌"]
#                     elif index + 1 < dungeons_length:
#                         # Is the first page
#                         emojis = ["⏩", "❌"]
#                     elif dungeons_length > 10:
#                         # Is the last page
#                         emojis = ["⏪", "❌"]
#                     else:
#                         # Is the only page
#                         emojis = ["❌"]
#                     reaction, user = await waitForReaction(ctx, message, e, emojis)
#                     if reaction is None:
#                         flag = False
#                         break
#                     match str(reaction.emoji):
#                         case "⏩":
#                             # Tell upcomming re-iteration to skip to the next page's offset
#                             offset += 10
#                             await message.clear_reactions()
#                             e.clear_fields()
#                             break
#                         case "⏪":
#                             # Tell upcomming re-iteration to skip to the previous page's offset
#                             offset -= 10
#                             await message.clear_reactions()
#                             e.clear_fields()
#                             break
#                         case "❌":
#                             await message.clear_reactions()
#                             flag = False
#                             break
#
#     async def selectDungeon(ctx, message, dungeon, mode, seed):
#         banner = generateFileObject("Oni-Dungeons", Graphics["Banners"]["Oni-Dungeons"][0])
#         flag = True
#         while flag:
#             if mode == -1:
#                 dungeon_level   = Dungeons[dungeon]["Level_Required"]
#                 dungeon_floors  = Dungeons[dungeon]["Floors"]
#                 dungeon_yokai   = Dungeons[dungeon]["Yokai"]
#                 dungeon_energy  = getDungeonEnergy(dungeon)
#                 e = discord.Embed(title = f"⛩️  ─  __{dungeon}__  ─  ⛩️", description = f"Which difficulty will you enter this dungeon on?", color = 0x9575cd)
#                 e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#                 e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
#                 e.add_field(name = "Level required", value = f"{Icons['level']}**{dungeon_level}**", inline = True)
#                 e.add_field(name = "Energy cost", value = f"{Icons['energy']}**{dungeon_energy[0]} - {dungeon_energy[3]}**", inline = True)
#                 e.add_field(name = "Floors", value = f"{Icons['dungeon']}**{dungeon_floors}**", inline = True)
#                 e.add_field(name = "Yokai found here:", value = boxifyArray(dungeon_yokai), inline = True)
#                 e.add_field(name = "Difficulty selection:\n────────────", value = getDungeonModes(), inline = True)
#                 e.add_field(name = "Seed initializer:", value = (f"`{seed}`" if not seed is None else "*Randomized*"), inline = False)
#                 message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
#                 emojis = getDungeonModes(type = "array")
#                 emojis.append("❌")
#                 reaction, user = await waitForReaction(ctx, message, e, emojis)
#                 if reaction is None:
#                     break
#                 match str(reaction.emoji):
#                     case x if x == Icons["normal"]:
#                         mode = 0
#                     case x if x == Icons['hard']:
#                         mode = 1
#                     case x if x == Icons['hell']:
#                         mode = 2
#                     case x if x == Icons['oni']:
#                         mode = 3
#                     case "❌":
#                         await message.clear_reactions()
#                         break
#                 await message.clear_reactions()
#             message, flag, mode = await confirmDungeon(ctx, message, flag, dungeon, mode, seed, banner)
#         return
#
#     async def confirmDungeon(ctx, message, flag, dungeon, mode, seed, banner):
#         try:
#             dg = DungeonInstance(dungeon, mode, seed)
#             e = discord.Embed(title = f"{dg.icon}  ─  __{dg.dungeon}__  ─  {dg.icon}", description = f"Enter this dungeon on *__{mode_mapping[mode]}__* mode?", color = 0x9575cd)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
#             e.add_field(name = "Level required", value = f"{Icons['level']} **{dg.level}**", inline = True)
#             e.add_field(name = "Energy cost", value = f"{Icons['energy']} **{dg.energy}**", inline = True)
#             e.add_field(name = "Floors", value = f"{Icons['dungeon']} **{dg.floors}**", inline = True)
#             e.add_field(name = "Your level", value = f"{Icons['level']} **{getPlayerLevel(user_id)}**", inline = True)
#             e.add_field(name = "Your energy", value = f"{Icons['energy']} **{getPlayerEnergy(user_id)}**", inline = True)
#             e.add_field(name = "Best time", value = f"⏱️ __{getPlayerDungeonRecord(user_id, dungeon, mode)}__", inline = True)
#             e.add_field(name = "Boss stats:", value = formatBossStats(dg.boss, dg.mode), inline = True)
#             e.add_field(name = "Rewards:", value = formatDungeonRewards(dg.rewards, dg.mode), inline = True)
#             e.add_field(name = "Instance seed:", value = (f"`{dg.seed}`" if not seed is None else "*Randomized*"), inline = False)
#             message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
#             emojis = [Icons["door_open"], "↩️"]
#             reaction, user = await waitForReaction(ctx, message, e, emojis)
#             if reaction is None:
#                 flag = False
#                 return message, flag, mode
#             match str(reaction.emoji):
#                 case x if x == Icons["door_open"]:
#                     await message.clear_reactions()
#                     if dg.Player.level >= dg.level:
#                         energy = getPlayerEnergy(user_id)
#                         if energy >= dg.energy:
#                             addPlayerEnergy(user_id, -dg.energy)
#                             message, flag = await dungeonEntry(ctx, message, flag, dg, seed)
#                             flag = False
#                         else:
#                             await ctx.send(f"⚠️ **You don't have enough energy to enter this dungeon!** You need `{dg.energy - energy}` more.")
#                     else:
#                         await ctx.send(f"⚠️ **You are not high enough level to access __{dungeon}__!** Need `{dg.level - dg.Player.level}` more levels!")
#                         flag = False
#                 case "↩️":
#                     await message.clear_reactions()
#                     mode = -1
#         except IndexError:
#             await ctx.send(f"⚠️ **Invalid difficulty mode specified:** Dungeon `{dungeon}` has no mode `{mode}`")
#             flag = False
#         return message, flag, mode
#
#     async def dungeonEntry(ctx, message, flag, dg, seed):
#         Blueprint = dg.dungeonGenesis()
#         dg.clearCache()
#         random.seed(None)
#         ### START TIMER ###
#         dg.Cache.start_time = datetime.utcnow()
#         ###################
#         e = discord.Embed(title = f"{dg.icon}  ─  __{dg.dungeon}__  ─  {dg.icon}", color = 0x9575cd)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.add_field(name = "Floor", value = "Placeholder", inline = True) # Field 0
#         e.add_field(name = "Room", value = "Placeholder", inline = True) # Field 1
#         e.add_field(name = "Contents", value = "Placeholder", inline = True) # Field 2
#         for floor in Blueprint["blueprint"]["floors"]:
#             dg.Cache.floor += 1
#             e.set_field_at(0, name = "Current Floor", value = f"{Icons['dungeon']} **{dg.Cache.floor} / {dg.floors}**")
#             if floor["type"] == "Floor":
#                 for index, room in enumerate(floor["rooms"]):
#                     dg.Cache.room += 1
#                     e.set_field_at(1, name = "Current Room", value = f"🎬 **{index + 1} / {len(floor['rooms'])}**")
#                     if room["type"] == "Normal":
#                         mobs = room["yokai"]
#                         population = len(mobs)
#                         for index, mob in enumerate(mobs):
#                             e.set_field_at(2, name = "Yokai", value = f"{Icons['yokai']} **{index + 1} / {population}**")
#                             message, flag = await fightMob(ctx, message, flag, dg, mob, e)
#                             if not flag:
#                                 return message, flag
#                     elif room["type"] == "Chest":
#                         e.set_field_at(2, name = "Chests", value = f"{Icons['chest']} **1 / 1**")
#                         chest = room["loot"]
#                         message, flag = await openChest(ctx, message, flag, dg, chest, e)
#                         if not flag:
#                             return message, flag
#             elif floor["type"] == "Boss":
#                 e.set_field_at(1, name = "Current Room", value = f"👹 ***Boss Room***")
#                 e.set_field_at(2, name = "Boss HP", value = f"🩸 **{'{:,}'.format(floor['boss']['HP'])} / {'{:,}'.format(floor['boss']['HP'])}**")
#                 boss = floor["boss"]
#                 message, flag, clear_rewards = await fightBoss(ctx, message, flag, dg, boss, e)
#                 if not flag:
#                     return message, flag
#         # Exit
#         if dg.Cache.cleared:
#             ### END TIMER ###
#             dg.Cache.end_time = datetime.utcnow()
#             #################
#             dg.Cache.clear_time = str(dg.Cache.end_time - dg.Cache.start_time)
#             dg.Blueprint["footer"].update({"Discovered": f"{dg.Cache.end_time} (UTC)"})
#             addPlayerDungeonClear(user_id, dg)
#             context = await bot.get_context(message)
#             file, founder = writeBlueprint(dg.Blueprint, dg.dungeon, dg.mode_name)
#             congrats = ""
#             congrats += f"🎊 {ctx.author.mention} Congratulations on clearing __**{dg.dungeon}**__ on __*{dg.mode_name}*__ mode!\n"
#             if clear_rewards:
#                 congrats += f"🎁 You were rewarded with {Icons['ryou']} **{'{:,}'.format(clear_rewards['ryou'])} Ryou**, and {Icons['exp']} **{'{:,}'.format(clear_rewards['exp'])} EXP!**\n"
#             congrats += f"⏱️ Your clear time was: `{dg.Cache.clear_time}`\n\n"
#             if founder:
#                 congrats += f"🔍 You are the first player to discover the seed `{seed if not seed is None else dg.seed}` for this mode!\n"
#                 congrats += "Here is a blueprint of the unique dungeon properties you discovered with that seed:"
#             else:
#                 congrats += f"The seed `{seed if not seed is None else dg.seed}` was already discovered for this mode.\n"
#                 congrats += f"So here is the blueprint the original founder generated:"
#             await context.reply(file = file, content = congrats)
#         return message, flag
#
#     async def deathScreen(message, e, condition):
#         e.add_field(name = "💀  ─  You have died!  ─  💀", value = f"Cause of death: __{condition}__")
#         e.description = "Player failed to clear the dungeon."
#         message = await message.edit(embed = e)
#         return message
#
#     async def consumeNigiri(message, flag, e, console, turn, atk_gauge, def_gauge, dg, printToConsole):
#         result = False
#
#         def formatConsumables(consumables, user_items):
#             avail_consumables = ""
#             for key, value in consumables.items():
#                 if key in user_items:
#                     avail_consumables += f"{Icons[key.lower().replace(' ', '_')]} **{key}**: +{value}HP\n"
#             return avail_consumables if not avail_consumables == "" else "None"
#
#         consumables = config.consumables
#         user_items = []
#         inventory = getUserItemInv(user_id)
#         for item in inventory:
#             user_items.append(item[0])
#         avail_consumables = []
#         for key in list(consumables.keys()):
#             if key in user_items:
#                 avail_consumables.append(Icons[key.lower().replace(' ', '_')])
#         e.add_field(name = "Consumables Menu:", value = formatConsumables(consumables, user_items), inline = False) # Field 6
#         await message.edit(embed = e)
#         emojis = []
#         for nigiri_emoji in avail_consumables:
#             emojis.append(nigiri_emoji)
#         emojis.append("↩️")
#         reaction, user = await waitForReaction(ctx, message, e, emojis)
#         if reaction is None:
#             flag = False
#         else:
#             product = ""
#             match str(reaction.emoji):
#                 case x if x == Icons["tuna_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Tuna Nigiri"
#                 case x if x == Icons["salmon_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Salmon Nigiri"
#                 case x if x == Icons["anago_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Anago Nigiri"
#                 case x if x == Icons["squid_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Squid Nigiri"
#                 case x if x == Icons["octopus_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Octopus Nigiri"
#                 case x if x == Icons["ootoro_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Ootoro Nigiri"
#                 case x if x == Icons["kinmedai_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Kinmedai Nigiri"
#                 case x if x == Icons["crab_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Crab Nigiri"
#                 case x if x == Icons["lobster_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Lobster Nigiri"
#                 case x if x == Icons["shachihoko_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Shachihoko Nigiri"
#                 case x if x == Icons["shenlong_nigiri"]:
#                     await message.clear_reactions()
#                     product = "Shenlong Nigiri"
#                 case "↩️":
#                     await message.clear_reactions()
#                     e.remove_field(6)
#                     await message.edit(embed = e)
#                     return message, flag, result
#             if product in user_items:
#                 heal = consumables[product]
#                 item_quantity = getUserItemQuantity(user_id, product)
#                 ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity - 1, product))
#                 if item_quantity - 1 == 0:
#                     ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(user_id), product))
#                 base_player_hp = getPlayerHP(user_id)
#                 heal_amount = heal if not dg.Player.HP + heal > base_player_hp else base_player_hp - dg.Player.HP
#                 dg.Player.HP = dg.Player.HP + heal if not dg.Player.HP + heal > base_player_hp else base_player_hp
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You ate some tasty {product}!")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(healed for {'{:,}'.format(heal_amount)})")
#                 result = True
#         e.remove_field(6)
#         await message.edit(embed = e)
#         return message, flag, result
#
#     async def fightMob(ctx, message, flag, dg, mob, e):
#
#         async def updateEmbed(e, yokai_state, player_state, console, turn, atk_gauge, def_gauge):
#             f"Turn: **#{turn}**"
#             e.set_field_at(3, name = "Turn:", value = f"#️⃣ **{turn}**")
#             e.set_field_at(4, name = "ATK Ougi Gauge:", value = f"{Icons['supercharge']} **{atk_gauge} / 5**")
#             e.set_field_at(5, name = "DEF Ougi Gauge:", value = f"{Icons['evade']} **{def_gauge} / 5**")
#             e.set_field_at(6, name = "Yokai stats:", value = boxifyArray(yokai_state, padding = 2))
#             e.set_field_at(7, name = "Player stats:", value = boxifyArray(player_state, padding = 2))
#             e.set_field_at(8, name = "Console:", value = boxifyArray(console[-7:], padding = 2, min_width = 33), inline = False)
#
#         def updateAgents():
#             yokai_state = ["", f"{dg.Yokai.name}", "", f"Yokai HP: {dg.Yokai.HP}", f"Yokai ATK: {dg.Yokai.ATK}", f"Yokai DEF: {dg.Yokai.DEF}", ""]
#             player_state = ["", f"{dg.Player.name}", f"Level: {dg.Player.level}", "", f"Player HP: {dg.Player.HP}", f"Player ATK: {dg.Player.ATK}", f"Player DEF: {dg.Player.DEF}", ""]
#             return yokai_state, player_state
#
#         async def printToConsole(message, e, console, turn, atk_gauge, def_gauge, input):
#             time.sleep(0.2)
#             console.append(str(input))
#             yokai_state, player_state = updateAgents()
#             await updateEmbed(e, yokai_state, player_state, console, turn, atk_gauge, def_gauge)
#             await message.edit(embed = e)
#             return message
#
#         async def loadYokaiEncounter(message, e, mob):
#             e.add_field(name = "Yokai Encountered!", value = f"Name: __{mob}__", inline = True) # Field 3
#             e.set_image(url = Resource[f"{mob}-1"][0].replace(" ", "%20"))
#             e.description = "🔄 **Loading Combat Engine** 🔄"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Combat Engine** 🔄 ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Combat Engine** 🔄 ▫️ ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Combat Engine** 🔄 ▫️ ▫️ ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.remove_field(3)
#             e.description = None
#             e.set_image(url = None)
#             return message
#
#         async def playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = False):
#             # time.sleep(0.5)
#             damage, is_critical = damageCalculator(dg.Player, dg.Yokai)
#             if is_supercharging:
#                 damage *= 2
#             dg.Yokai.HP = dg.Yokai.HP - damage if not dg.Yokai.HP - damage < 0 else 0
#             if not is_supercharging:
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Dealt {damage} damage to {mob}!")
#             else:
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Dealt {damage} supercharged damage to {mob}!")
#             if is_critical:
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
#             # message = await printToConsole(message, e, console, "")
#             return message
#
#         async def playerDefend(message, e, console, turn, atk_gauge, def_gauge):
#             # time.sleep(0.5)
#             dg.Player.DEF *= 3
#             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You fortified your defences!")
#             # message = await printToConsole(message, e, console, "")
#             return message
#
#         async def yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending = False, is_evading = False):
#             damage, is_critical = damageCalculator(dg.Yokai, dg.Player)
#             if is_charging and not is_defending:
#                 damage *= 2
#             # time.sleep(0.5)
#             if not is_evading:
#                 dg.Player.HP = dg.Player.HP - damage if not dg.Player.HP - damage < 0 else 0
#                 if not is_charging:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Took {damage} damage from {dg.Yokai.name}!")
#                 else:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Took {damage} heavy damage from {dg.Yokai.name}!")
#                 if is_critical:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
#             else:
#                 if not is_charging:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Evaded {damage} damage from {dg.Yokai.name}!")
#                 else:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Evaded {damage} heavy damage from {dg.Yokai.name}!")
#                 if is_critical:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical evaded!)")
#             # message = await printToConsole(message, e, console, "")
#             return message
#
#         async def yokaiDefend(message, e, console, turn, atk_gauge, def_gauge):
#             # time.sleep(0.5)
#             dg.Yokai.DEF *= 2
#             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{mob} fortified its defences!")
#             # message = await printToConsole(message, e, console, "")
#             return message
#
#         # Loading screen
#         message = await loadYokaiEncounter(message, e, mob)
#
#         # Begin Combat Engine
#         e.add_field(name = "Turn", value = "Placeholder", inline = True) # Field 3
#         e.add_field(name = "ATK Ougi", value = "Placeholder", inline = True) # Field 4
#         e.add_field(name = "DEF Ougi", value = "Placeholder", inline = False) # Field 5
#         e.add_field(name = "Yokai", value = "Placeholder", inline = True) # Field 6
#         e.add_field(name = "Player", value = "Placeholder", inline = True) # Field 7
#         e.add_field(name = "Console", value = "Placeholder", inline = False) # Field 8
#         console = [""]
#         yokai_action = ""
#         player_action = ""
#         dg.Yokai.name = mob
#         # dg.Yokai.HP = dg.level * dg.multiplier * random.randint(10, 50) + (math.floor((dg.level ** 3) / 4))
#         # dg.Yokai.ATK = dg.level * dg.multiplier * random.randint(5, 15) + (math.floor((dg.level ** 2) / 4))
#         # dg.Yokai.DEF = dg.level * dg.multiplier * random.randint(5, 15) + (math.floor((dg.level ** 2) / 4))
#         base_yokai_hp = math.floor((dg.level * random.randint(20, 50)) + (dg.level * dg.multiplier))
#         base_yokai_atk = math.floor((dg.level * random.uniform(5, 8.5)) + (dg.level * dg.multiplier))
#         base_yokai_def = math.floor((dg.level * random.uniform(5.5, 9)) + (dg.level * dg.multiplier))
#         dg.Yokai.HP = base_yokai_hp
#         dg.Yokai.ATK = base_yokai_atk
#         dg.Yokai.DEF = base_yokai_def
#         base_player_hp = getPlayerHP(user_id)
#         base_player_atk = getPlayerATK(user_id)
#         base_player_def = getPlayerDEF(user_id)
#         if getPlayerLevel(user_id) > dg.Player.level:
#             dg.Player.level = getPlayerLevel(user_id)
#             dg.Player.HP = getPlayerHP(user_id)
#         #     dg.Player.ATK = getPlayerATK(user_id)
#         #     dg.Player.DEF = getPlayerDEF(user_id)
#         atk_gauge = 0
#         def_gauge = 0
#         turn = 0
#         while flag:
#             yokai_state, player_state = updateAgents()
#             yokai_killed = False if dg.Yokai.HP > 0 else True
#             player_killed = False if dg.Player.HP > 0 else True
#             if not yokai_killed and not player_killed:
#                 turn += 1
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Turn: #{turn}")
#                 dg.Yokai.ATK = base_yokai_atk
#                 dg.Yokai.DEF = base_yokai_def
#                 dg.Player.ATK = base_player_atk
#                 dg.Player.DEF = base_player_def
#                 is_charging = True if random.random() < 0.1 else False
#                 if is_charging:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({mob} is charging a heavy attack!)")
#                 is_defending = False
#                 is_evading = False
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "Choose an action to perform")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Attack | Defend | Leave Dungeon)")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#
#                 while True:
#                     emojis = [Icons["attack"], Icons["defend"], Icons["riceball"]]
#                     if atk_gauge == 5:
#                         emojis.append(Icons["supercharge"])
#                     if def_gauge == 5:
#                         emojis.append(Icons["evade"])
#                     emojis.append(Icons["exit"])
#                     reaction, user = await waitForReaction(ctx, message, e, emojis)
#                     if reaction is None:
#                         flag = False
#                     else:
#                         is_player_turn = bool(random.getrandbits(1))
#                         yokai_action = "Attack" if bool(random.getrandbits(1)) or is_charging else "Defend"
#                         player_action = ""
#                         match str(reaction.emoji):
#                             case x if x == Icons["attack"]:
#                                 await message.clear_reactions()
#                                 if is_player_turn:
#                                     if yokai_action == "Defend":
#                                         message = await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                     message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge)
#                                     if not dg.Yokai.HP > 0:
#                                         message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                         break
#                                     if yokai_action == "Attack":
#                                         message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
#                                 else:
#                                     message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                     if not dg.Player.HP > 0:
#                                         message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                         break
#                                     message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge)
#                                 atk_gauge = atk_gauge + 1 if atk_gauge + 1 <= 5 else 5
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             case x if x == Icons["defend"]:
#                                 await message.clear_reactions()
#                                 player_action = "Defend"
#                                 message = await playerDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                 is_defending = True
#                                 message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                 if yokai_action == "Attack":
#                                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Suppressed)")
#                                 def_gauge = def_gauge + 1 if def_gauge + 1 <= 5 else 5
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             case x if x == Icons["riceball"]:
#                                 await message.clear_reactions()
#                                 message, flag, result = await consumeNigiri(message, flag, e, console, turn, atk_gauge, def_gauge, dg, printToConsole)
#                                 if result:
#                                     message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                 else:
#                                     continue
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             case x if x == Icons["supercharge"] and atk_gauge == 5:
#                                 await message.clear_reactions()
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Activated Ougi skill: Supercharge ATK)")
#                                 atk_gauge = 0
#                                 if is_player_turn:
#                                     if yokai_action == "Defend":
#                                         message = await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                     message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = True)
#                                     if not dg.Yokai.HP > 0:
#                                         message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                         break
#                                     if yokai_action == "Attack":
#                                         message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
#                                 else:
#                                     message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                     if not dg.Player.HP > 0:
#                                         message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                         break
#                                     message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = True)
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             case x if x == Icons["evade"] and def_gauge == 5:
#                                 await message.clear_reactions()
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Activated Ougi skill: Perfect Dodge)")
#                                 is_evading = True
#                                 def_gauge = 0
#                                 continue
#                             case x if x == Icons["exit"]:
#                                 await message.clear_reactions()
#                                 e.description = "Player aborted the dungeon!"
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Aborting dungeon)")
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                 flag = False
#                     break
#
#             elif yokai_killed:
#                 ExpTable = Tables["ExpTable"]
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You have defeated {mob}!")
#                 if mob == "Gold Daruma":
#                     random_amount = random.randint(10000, 100000)
#                     ryou_amount = math.floor(((random_amount / 5) * dg.level) + ((random_amount / 10) * dg.level * dg.multiplier))
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({mob} dropped {ryou_amount} Ryou!")
#                     await reward(ctx, ctx.author.mention, "ryou", ryou_amount)
#                 exp_row = ExpTable[dg.level - 1][1]
#                 exp_amount = round((random.randint(10, 20) * dg.level) + ((exp_row / 500) * dg.multiplier))
#                 exp_reward = addPlayerExp(user_id, exp_amount)
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {exp_reward} EXP!)")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "Choose an action to perform")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Proceed | Leave Dungeon)")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                 emojis = ["⏭️", Icons["exit"]]
#                 reaction, user = await waitForReaction(ctx, message, e, emojis)
#                 if reaction is None:
#                     flag = False
#                 else:
#                     match str(reaction.emoji):
#                         case "⏭️":
#                             await message.clear_reactions()
#                             e.remove_field(8)
#                             e.remove_field(7)
#                             e.remove_field(6)
#                             e.remove_field(5)
#                             e.remove_field(4)
#                             e.remove_field(3)
#                             message = await message.edit(embed = e)
#                             break
#                         case x if x == Icons["exit"]:
#                             await message.clear_reactions()
#                             e.description = "Player aborted the dungeon!"
#                             message = await printToConsole(message, e, turn, atk_gauge, def_gauge, console, f"(Aborting dungeon)")
#                             message = await printToConsole(message, e, turn, atk_gauge, def_gauge, console, "")
#                             flag = False
#             elif player_killed:
#                 message = await printToConsole(message, e, turn, atk_gauge, def_gauge, console, f"{mob} has killed you!")
#                 message = await printToConsole(message, e, turn, atk_gauge, def_gauge, console, f"(Aborting dungeon)")
#                 message = await printToConsole(message, e, turn, atk_gauge, def_gauge, console, "")
#                 time.sleep(1)
#                 message = await deathScreen(message, e, mob)
#                 flag = False
#         return message, flag
#
#     async def openChest(ctx, message, flag, dg, chest, e):
#
#         async def formatLoot(chest):
#             loot = []
#             loot.append("")
#             for key, value in chest.items():
#                 loot.append(f"{key}: {value}")
#             loot.append("")
#             return loot
#
#         async def rewardLoot(ctx, chest):
#             for key, value in chest.items():
#                 match key:
#                     case "Ryou":
#                         addPlayerRyou(user_id, value)
#                     case "EXP":
#                         addPlayerExp(user_id, value)
#                     case "Gacha Fragment" | "Gacha Fragments":
#                         fragments = GachaDB.query("SELECT gacha_fragments FROM userdata WHERE user_id = {}".format(user_id))[0][0]
#                         GachaDB.execute("UPDATE userdata SET gacha_fragments = ? WHERE user_id = ?", (fragments + value, user_id))
#                     case product if product in Products:
#                         item_quantity = getUserItemQuantity(user_id, product)
#                         if item_quantity == None:
#                             ItemsDB.execute("INSERT INTO {} (item, quantity) VALUES ('{}', {})".format(f"user_{user_id}", product, value))
#                         else:
#                             ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity + value, product))
#
#         async def loadNextRoom(message, e):
#             e.description = "🔄 **Loading Next Room** 🔄"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Next Room** 🔄 ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Next Room** 🔄 ▫️ ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Next Room** 🔄 ▫️ ▫️ ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.remove_field(4)
#             e.remove_field(3)
#             e.description = None
#             e.set_image(url = None)
#             await message.edit(embed = e)
#             return message
#
#         e.add_field(name = "Chest Discovered!", value = f"Will you open it?", inline = True) # Field 3
#         e.set_image(url = Resource["Chest"][0])
#         message = await message.edit(embed = e)
#         emojis = [Icons["chest"], "⏭️", Icons["exit"]]
#         reaction, user = await waitForReaction(ctx, message, e, emojis)
#         if reaction is None:
#             flag = False
#         else:
#             match str(reaction.emoji):
#                 case x if x == Icons["chest"]:
#                     await message.clear_reactions()
#                     loot = await formatLoot(chest)
#                     e.set_field_at(3, name = "Loot obtained:", value = boxifyArray(loot, padding = 2), inline = True) # Field 4
#                     await message.edit(embed = e)
#                     await rewardLoot(ctx, chest)
#                     message = await loadNextRoom(message, e)
#                 case "⏭️":
#                     await message.clear_reactions()
#                     message = await loadNextRoom(message, e)
#                 case x if x == Icons["exit"]:
#                     await message.clear_reactions()
#                     e.description = "Player aborted the dungeon!"
#                     flag = False
#         return message, flag
#
#     async def fightBoss(ctx, message, flag, dg, boss, e):
#         clear_rewards = {}
#         dg.Boss.name = boss["Name"]
#         base_boss_hp = boss["HP"]
#         base_boss_atk = math.floor((dg.level * random.uniform(8, 9)) + (dg.level * dg.multiplier))
#         base_boss_def = math.floor((dg.level * random.uniform(8, 9)) + (dg.level * dg.multiplier))
#         dg.Boss.HP = base_boss_hp
#         dg.Boss.ATK = base_boss_atk
#         dg.Boss.DEF = base_boss_def
#         base_player_hp = getPlayerHP(user_id)
#         base_player_atk = getPlayerATK(user_id)
#         base_player_def = getPlayerDEF(user_id)
#         if getPlayerLevel(user_id) > dg.Player.level:
#             dg.Player.level = getPlayerLevel(user_id)
#             dg.Player.HP = getPlayerHP(user_id)
#         #     dg.Player.ATK = getPlayerATK(user_id)
#         #     dg.Player.DEF = getPlayerDEF(user_id)
#
#         async def updateEmbed(e, boss_state, player_state, console, turn, atk_gauge, def_gauge):
#             e.set_field_at(2, name = "Boss HP", value = f"🩸 **{'{:,}'.format(dg.Boss.HP)} / {'{:,}'.format(boss['HP'])}**")
#             e.set_field_at(3, name = "Turn:", value = f"#️⃣ **{turn}**")
#             e.set_field_at(4, name = "ATK Ougi Gauge:", value = f"{Icons['supercharge']} **{atk_gauge} / 5**")
#             e.set_field_at(5, name = "DEF Ougi Gauge:", value = f"{Icons['evade']} **{def_gauge} / 5**")
#             e.set_field_at(6, name = "Boss stats:", value = boxifyArray(boss_state, padding = 2))
#             e.set_field_at(7, name = "Player stats:", value = boxifyArray(player_state, padding = 2))
#             e.set_field_at(8, name = "Console:", value = boxifyArray(console[-7:], padding = 2, min_width = 33), inline = False)
#
#         def updateAgents():
#             boss_state = ["", f"{dg.Boss.name}", f"Phase: {dg.Boss.phase}", "", f"Boss HP: {dg.Boss.HP}", f"Boss ATK: {dg.Boss.ATK}", f"Boss DEF: {dg.Boss.DEF}", ""]
#             player_state = ["", f"{dg.Player.name}", f"Level: {dg.Player.level}", "", f"Player HP: {dg.Player.HP}", f"Player ATK: {dg.Player.ATK}", f"Player DEF: {dg.Player.DEF}", ""]
#             return boss_state, player_state
#
#         async def printToConsole(message, e, console, turn, atk_gauge, def_gauge, input):
#             time.sleep(0.2)
#             console.append(str(input))
#             boss_state, player_state = updateAgents()
#             await updateEmbed(e, boss_state, player_state, console, turn, atk_gauge, def_gauge)
#             await message.edit(embed = e)
#             return message
#
#         async def loadBossEncounter(message, e, name):
#             e.add_field(name = "Boss Encountered!", value = f"Name: __{name}__", inline = True) # Field 3
#             e.set_image(url = Resource[f"{name}-2"][0].replace(" ", "%20"))
#             e.description = "🔄 **Loading Combat Engine** 🔄"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Combat Engine** 🔄 ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Combat Engine** 🔄 ▫️ ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.description = "🔄 **Loading Combat Engine** 🔄 ▫️ ▫️ ▫️"
#             await message.edit(embed = e)
#             time.sleep(0.5)
#             e.remove_field(3)
#             e.description = None
#             e.set_image(url = None)
#             return message
#
#         async def playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = False):
#             # time.sleep(0.5)
#             damage, is_critical = damageCalculator(dg.Player, dg.Boss)
#             if is_supercharging:
#                 damage *= 2
#             dg.Boss.HP = dg.Boss.HP - damage if not dg.Boss.HP - damage < 0 else 0
#             if not is_supercharging:
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Dealt {damage} damage to {dg.Boss.name}!")
#             else:
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Dealt {damage} supercharged damage to {dg.Boss.name}!")
#             if is_critical:
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
#             # message = await printToConsole(message, e, console, "")
#             return message
#
#         async def playerDefend(message, e, console, turn, atk_gauge, def_gauge):
#             # time.sleep(0.5)
#             dg.Player.DEF *= 3
#             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You fortified your defences!")
#             # message = await printToConsole(message, e, console, "")
#             return message
#
#         async def bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending = False, is_evading = False):
#             damage, is_critical = damageCalculator(dg.Boss, dg.Player)
#             if is_charging and not is_defending:
#                 damage *= 2
#             # time.sleep(0.5)
#             if not is_evading:
#                 dg.Player.HP = dg.Player.HP - damage if not dg.Player.HP - damage < 0 else 0
#                 if not is_charging:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Took {damage} damage from {dg.Boss.name}!")
#                 else:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Took {damage} heavy damage from {dg.Boss.name}!")
#                 if is_critical:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
#             else:
#                 if not is_charging:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Evaded {damage} damage from {dg.Boss.name}!")
#                 else:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Evaded {damage} heavy damage from {dg.Boss.name}!")
#                 if is_critical:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical evaded!)")
#             # message = await printToConsole(message, e, console, "")
#             return message
#
#         async def bossDefend(message, e, console, turn, atk_gauge, def_gauge):
#             # time.sleep(0.5)
#             dg.Boss.DEF *= 2
#             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} fortified its defences!")
#             # message = await printToConsole(message, e, console, "")
#             return message
#
#         # Loading screen
#         message = await loadBossEncounter(message, e, dg.Boss.name)
#
#         # Begin Combat Engine
#         e.add_field(name = "Turn", value = "Placeholder", inline = True) # Field 3
#         e.add_field(name = "ATK Ougi", value = "Placeholder", inline = True) # Field 4
#         e.add_field(name = "DEF Ougi", value = "Placeholder", inline = False) # Field 5
#         e.add_field(name = "Boss", value = "Placeholder", inline = True) # Field 6
#         e.add_field(name = "Player", value = "Placeholder", inline = True) # Field 7
#         e.add_field(name = "Console", value = "Placeholder", inline = False) # Field 8
#         console = [""]
#         boss_action = ""
#         player_action = ""
#         atk_gauge = 0
#         def_gauge = 0
#         turn = 0
#         phase = 1
#         while flag:
#             boss_state, player_state = updateAgents()
#             boss_killed = False if dg.Boss.HP > 0 else True
#             player_killed = False if dg.Player.HP > 0 else True
#             if not boss_killed and not player_killed:
#                 turn += 1
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Turn: #{turn}")
#                 dg.Boss.ATK = base_boss_atk
#                 dg.Boss.DEF = base_boss_def
#                 dg.Player.ATK = base_player_atk
#                 dg.Player.DEF = base_player_def
#                 is_charging = True if random.random() < 0.25 else False
#                 if is_charging:
#                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({dg.Boss.name} is charging a heavy attack!)")
#                 is_defending = False
#                 is_evading = False
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "Choose an action to perform")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Attack | Defend | Leave Dungeon)")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#
#                 while True:
#                     emojis = [Icons["attack"], Icons["defend"], Icons["riceball"]]
#                     if atk_gauge == 5:
#                         emojis.append(Icons["supercharge"])
#                     if def_gauge == 5:
#                         emojis.append(Icons["evade"])
#                     emojis.append(Icons["exit"])
#                     reaction, user = await waitForReaction(ctx, message, e, emojis)
#                     if reaction is None:
#                         flag = False
#                     else:
#                         is_player_turn = bool(random.getrandbits(1))
#                         boss_action = "Attack" if bool(random.getrandbits(1)) or is_charging else "Defend"
#                         player_action = ""
#                         match str(reaction.emoji):
#                             case x if x == Icons["attack"]:
#                                 await message.clear_reactions()
#                                 if is_player_turn:
#                                     if boss_action == "Defend":
#                                         message = await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                     message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge)
#                                     if not dg.Boss.HP > 0:
#                                         message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                         break
#                                     if boss_action == "Attack":
#                                         message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
#                                 else:
#                                     message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                     if not dg.Player.HP > 0:
#                                         message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                         break
#                                     message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge)
#                                 atk_gauge = atk_gauge + 1 if atk_gauge + 1 <= 5 else 5
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             case x if x == Icons["defend"]:
#                                 await message.clear_reactions()
#                                 player_action = "Defend"
#                                 message = await playerDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                 is_defending = True
#                                 message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                 if boss_action == "Attack":
#                                     message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Suppressed)")
#                                 def_gauge = def_gauge + 1 if def_gauge + 1 <= 5 else 5
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             case x if x == Icons["riceball"]:
#                                 await message.clear_reactions()
#                                 message, flag, result = await consumeNigiri(message, flag, e, console, turn, atk_gauge, def_gauge, dg, printToConsole)
#                                 if result:
#                                     message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                 else:
#                                     continue
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             case x if x == Icons["supercharge"] and atk_gauge == 5:
#                                 await message.clear_reactions()
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Activated Ougi skill: Supercharge ATK)")
#                                 atk_gauge = 0
#                                 if is_player_turn:
#                                     if boss_action == "Defend":
#                                         message = await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                     message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = True)
#                                     if not dg.Boss.HP > 0:
#                                         message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                         break
#                                     if boss_action == "Attack":
#                                         message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
#                                 else:
#                                     message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
#                                     if not dg.Player.HP > 0:
#                                         message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                         break
#                                     message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = True)
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             case x if x == Icons["evade"] and def_gauge == 5:
#                                 await message.clear_reactions()
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Activated Ougi skill: Perfect Dodge)")
#                                 is_evading = True
#                                 def_gauge = 0
#                                 continue
#                             case x if x == Icons["exit"]:
#                                 await message.clear_reactions()
#                                 e.description = "Player aborted the dungeon!"
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Aborting dungeon)")
#                                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                                 flag = False
#                         if phase == 1 and dg.Boss.HP <= math.trunc(boss["HP"] / 2) and dg.Boss.HP > 0:
#                             dg.Boss.phase = 2
#                         if phase == 1 and dg.Boss.phase == 2:
#                             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} has augmented to Phase 2!")
#                             base_boss_atk = math.floor(base_boss_atk * random.uniform(1.1, 1.2))
#                             base_boss_def = math.floor(base_boss_def * random.uniform(1.1, 1.2))
#                             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(ATK and DEF buffed)")
#                             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             phase = 2
#                         if phase == 2 and dg.Boss.HP <= math.trunc(boss["HP"] / 4) and dg.Boss.HP > 0:
#                             dg.Boss.phase = 3
#                         if phase == 2 and dg.Boss.phase == 3:
#                             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} has augmented to Phase 3!")
#                             base_boss_atk = math.floor(base_boss_atk * random.uniform(1.1, 1.2))
#                             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(ATK buffed)")
#                             message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                             phase = 3
#                     break
#
#             elif boss_killed:
#                 ryou0 = math.floor((dg.rewards["Ryou"]['range'][0] * 0.75) + (dg.rewards["Ryou"]['range'][0] / 4) * dg.multiplier)
#                 ryou1 = math.floor((dg.rewards["Ryou"]['range'][1] * 0.75) + (dg.rewards["Ryou"]['range'][1] / 4) * dg.multiplier)
#                 exp0 = math.floor((dg.rewards["EXP"]['range'][0] * 0.75) + (dg.rewards["EXP"]['range'][0] / 4) * dg.multiplier)
#                 exp1 = math.floor((dg.rewards["EXP"]['range'][1] * 0.75) + (dg.rewards["EXP"]['range'][1] / 4) * dg.multiplier)
#                 ryou_range = [ryou0, ryou1]
#                 exp_range = [exp0, exp1]
#                 ryou_amount = addPlayerRyou(user_id, random.randint(ryou_range[0], ryou_range[1]))
#                 exp_amount = addPlayerExp(user_id, random.randint(exp_range[0], exp_range[1]))
#                 clear_rewards.update({"ryou": ryou_amount, "exp": exp_amount})
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You have defeated {dg.Boss.name}!")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {ryou_amount} Ryou!)")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {exp_amount} EXP!)")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                 dg.Cache.cleared = True
#                 break
#             elif player_killed:
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} has killed you!")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Aborting dungeon)")
#                 message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
#                 time.sleep(1)
#                 message = await deathScreen(message, e, dg.Boss.name)
#                 flag = False
#         return message, flag, clear_rewards
#
#     def writeBlueprint(Blueprint, dungeon, difficulty):
#         json_blueprint = json.dumps(Blueprint, indent=4)
#         path = f"Blueprints/{dungeon}/{difficulty}"
#         makedirs(path, exist_ok = True)
#         json_filename = f"{path}/{Blueprint['header']['Seed']}.json"
#         if not file_exists(json_filename):
#             founder = True
#             with open(json_filename, "w") as outfile:
#                 outfile.write(json_blueprint)
#         else:
#             founder = False
#         file = discord.File(json_filename)
#         return file, founder
#
#     def damageCalculator(attacker, defender):
#         is_critical = True if random.random() < 0.1 else False
#         damage = math.floor(attacker.ATK / (defender.DEF / attacker.ATK))
#         variance = round(damage / 10)
#         var_roll = random.randint(-variance, variance)
#         damage += var_roll
#         damage *= 2 if is_critical else 1
#         return damage, is_critical
#
#     def getDungeonEnergy(dungeon):
#         dungeon_metric = Dungeons[dungeon]["Energy_Metric"]
#         dungeon_energy = []
#         for mode in Dungeons[dungeon]["Difficulties"]:
#             match mode:
#                 case "Normal":
#                     energy_divisor = mode_divisors[0]
#                 case "Hard":
#                     energy_divisor = mode_divisors[1]
#                 case "Hell":
#                     energy_divisor = mode_divisors[2]
#                 case "Oni":
#                     energy_divisor = mode_divisors[3]
#             dungeon_energy.append(math.floor(dungeon_metric / energy_divisor))
#         return dungeon_energy
#
#     def getDungeonModes(type = "string"):
#         default_string = f"{Icons['normal']}\n{Icons['hard']}\n{Icons['hell']}\n{Icons['oni']}"
#         default_array = [Icons["normal"], Icons["hard"], Icons["hell"], Icons["oni"]]
#         default_dict = {"Normal": Icons["normal"], "Hard": Icons["hard"], "Hell": Icons["hell"], "Oni": Icons["oni"]}
#         match type:
#             case "string":
#                 formatted_string = ""
#                 for key, value in default_dict.items():
#                     formatted_string += f"\n{value} ─ __{key}__ ─ {value}\n"
#                 return formatted_string
#             case "array":
#                 return default_array
#             case "dict":
#                 return default_dict
#
#     def formatBossStats(stats, mode):
#         multiplier          = mode_multipliers[mode]
#         boss_name           = stats["Name"]
#         base_hp             = stats["HP"]
#         scaled_hp           = math.floor((base_hp * 0.75) + (base_hp / 4 * multiplier))
#         boss_resistances    = stats["Resistances"]
#         boss_weaknesses     = stats["Weaknesses"]
#         resistance_emojis   = getElementEmojis(boss_resistances)
#         weakness_emojis     = getElementEmojis(boss_weaknesses)
#
#         formatted_string = ""
#         formatted_string += f"───────────────\n"
#         formatted_string += f"👹 ─ Boss: **__{boss_name}__**\n"
#         formatted_string += f"───────────────\n"
#         formatted_string += f"🩸 ─ HP: `{'{:,}'.format(scaled_hp)}`\n"
#         formatted_string += f"───────────────\n"
#         formatted_string += f"🛡️ ─ Resistances\n"
#         formatted_string += f" ╰──  {resistance_emojis}\n"
#         formatted_string += f"───────────────\n"
#         formatted_string += f"⚔️ ─ Weaknesses\n"
#         formatted_string += f" ╰──  {weakness_emojis}\n"
#
#         ### <TO-DO>
#         ### Use text rendering modules to determine width of content
#         ### Wrap content in a pretty box to display to the end-user
#
#         # from matplotlib import rcParams
#         # import os.path
#         # string = "Hello there"
#         # spacer_character    = " "
#         # border_character    = "─"
#         # border_character    = "-"
#
#         # fields = [len(str(boss_name)), len(str('{:,}'.format(boss_hp))), len(boss_resistances), len(boss_weaknesses)]
#         # max_width = getMaxItemWidth(fields, min_width = 0)
#         # print(max_width)
#
#         # border_width = max_width + 18
#         # border = ""
#         # for _ in range(border_width):
#         #     border += border_character
#         # formatting_array = []
#         # formatting_array.append(f"╓{border}╖\n")
#         # formatting_array.append(f"║👹 ─ Boss: **__{boss_name}__**\n")
#         # formatting_array.append(f"╟{border}╢\n")
#         # formatting_array.append(f"║🩸 ─ HP: `{'{:,}'.format(boss_hp)}`\n")
#         # formatting_array.append(f"╟{border}╢\n")
#         # formatting_array.append(f"║🛡️ ─ Resistances\n")
#         # formatting_array.append(f"║ ╰──  {resistance_emojis}\n")
#         # formatting_array.append(f"╟{border}╢\n")
#         # formatting_array.append(f"║⚔️ ─ Weaknesses\n")
#         # formatting_array.append(f"║ ╰──  {weakness_emojis}\n")
#         # formatting_array.append(f"╙{border}╜\n")
#
#         ### </TO-DO>
#
#         return formatted_string
#
#     def formatDungeonRewards(dungeon_rewards, mode):
#         multiplier = mode_multipliers[mode]
#         formatted_string = ""
#         index = 0
#         for key, value in dungeon_rewards.items():
#             match key:
#                 case "Ryou":
#                     icon = Icons["ryou"]
#                 case "EXP":
#                     icon = Icons["exp"]
#                 case _:
#                     icon = Icons["material_common"]
#             formatted_string += "───────────────\n"
#             value0 = math.floor((value["range"][0] * 0.75) + (value["range"][0] / 4) * multiplier)
#             value1 = math.floor((value["range"][1] * 0.75) + (value["range"][1] / 4) * multiplier)
#             formatted_string += f"{icon} ─ {key}: `{'{:,}'.format(value0)} - {'{:,}'.format(value1)}`\n"
#             formatted_string += f" ╰──  *Drop rate:* **{value['rate']}%**\n"
#             index += 1
#         return formatted_string
#
#     def getElementEmojis(array):
#         emoji_string = ""
#         for element in array:
#             emoji_string += Icons[element]
#         return emoji_string if not emoji_string == "" else "None"
#
#     # main()
#     message = None
#     mode = None
#     seed = None
#     if input:
#         # User provided arguments
#         try:
#             # Assume both dungeon name string and mode were provided
#             dg_query = list(input)
#             for index, arg in enumerate(dg_query):
#                 # Check if user provided the -seed argument
#                 if arg == "-seed" or arg == "-s":
#                     seed = dg_query.pop(index + 1)
#                     dg_query.pop(index)
#                     break
#             mode_test = dg_query.pop()
#             dg_string = ' '.join(dg_query)
#             modes = ["Normal", "Hard", "Hell", "Oni"]
#             if len(mode_test) == 1:
#                 # Try to get mode as integer
#                 mode = int(mode_test)
#                 if mode > 3 or mode < 0:
#                     # User tried to access a protected or non-existant dungeon mode
#                     await ctx.send(f"⚠️ **Invalid Mode ID:** `{mode}`")
#                     return
#             else:
#                 # Try to get mode as string
#                 modes = ["Normal", "Hard", "Hell", "Oni"]
#                 for mode_name in modes:
#                     if mode_test.casefold() == mode_name.casefold():
#                         mode = mode_mapping_inverse[mode_name]
#                         break
#                 if mode == None:
#                     # There was no matching string found
#                     raise ValueError
#         except ValueError:
#             # Conlude that mode wasn't provided
#             dg_query = list(input)
#             for index, arg in enumerate(dg_query):
#                 # Check if user provided the -seed argument
#                 if arg == "-seed" or arg == "-s":
#                     seed = dg_query.pop(index + 1)
#                     dg_query.pop(index)
#                     break
#             dg_string = ' '.join(dg_query)
#             mode = -1
#         for dungeon in Dungeons:
#             # Check if the provided dungeon argument is an existing dungeon
#             if dg_string.casefold() == dungeon.casefold():
#                 # A match was found! Proceed to load the dungeon
#                 if mode == -1:
#                     # Mode wasn't provided so let the user select it by hand
#                     await selectDungeon(ctx, message, dungeon, mode, seed)
#                 else:
#                     # Mode was provided so shortcut straight to the entry screen
#                     await selectDungeon(ctx, message, dungeon, mode, seed)
#                 # User finished the dungeon, exit now
#                 return
#             else:
#                 continue
#         # Checks failed; therefore, user must have mistyped the dungeon name
#         await ctx.send(f"⚠️ **There doesn't exist any dungeons with the name:** `{dg_string}`")
#         return
#     else:
#         # Conclude that neither dungeon name nor mode was provided
#         # Show the user a list of dungeons they have unlocked
#         await menuDungeons(ctx, message)

# @bot.command(aliases = ["quest", "questing", "subquest", "subquests", "sidequest", "sidequests", "mission", "missions"])
# @commands.check(checkChannel)
# async def quests(ctx, arg: str = None):
#     ''' | Usage: +quests [collect]'''
#     user_id         = ctx.author.id
#     default_color   = config.default_color
#     last_quest      = getLastQuest(user_id)
#     wait            = 0 if checkAdmin(ctx) and debug_mode else config.quest_wait
#     now             = int(time.time())
#
#     def chooseRandomQuest():
#         while True:
#             choice = random.choice(list(Quests))
#             level = getPlayerLevel(user_id)
#             if Quests[choice]["Level_Required"] > level:
#                 continue
#             else:
#                 break
#         return choice
#
#     async def promptQuest(ctx, message, flag, quest):
#         banner = generateFileObject("Oni-Quests", Graphics["Banners"]["Oni-Quests"][0])
#         npc = Quests[quest]["NPC"]
#         lvl = Quests[quest]["Level_Required"]
#         conditions = getConditions(quest)
#         rewards = getRewards(quest)
#         boost = getUserBoost(ctx)
#         dialogue = getDialogue(quest)
#         e = discord.Embed(title = "🗺️ Quest found!", description = "Will you accept this quest?", color = default_color)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
#         e.add_field(name = "📜 Title", value = f"`{quest}`", inline = True)
#         e.add_field(name = "🧍 NPC", value = f"`{npc}`", inline = True)
#         e.add_field(name = "⚙️ Level Required", value = f"`{lvl}`", inline = True)
#         e.add_field(name = "📌 Clearing Conditions:", value = conditions, inline = True)
#         e.add_field(name = f"🎁 Rewards:{'  ─  (+' + str(boost) + '%)' if boost > 0 else ''}", value = rewards, inline = True)
#         e.add_field(name = "💬 Dialogue:", value = "```" + dialogue + "```", inline = False)
#         message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
#         emojis = ["✅", "❌"]
#         reaction, user = await waitForReaction(ctx, message, e, emojis)
#         if reaction is None:
#             flag = False
#             return message, flag
#         match str(reaction.emoji):
#             case "✅":
#                 now = int(time.time())
#                 last_quest = getLastQuest(user_id)
#                 if now >= last_quest + wait or checkAdmin(ctx):
#                     await message.clear_reactions()
#                     message, flag = await startQuest(ctx, message, flag, quest, e)
#                 else:
#                     hours = math.floor((last_quest + wait - now) / 60 / 60)
#                     minutes = math.floor((last_quest + wait - now) / 60 - (hours * 60))
#                     seconds = (last_quest + wait - now) % 60
#                     await ctx.send(f"There are currently no quests, please check back in ⌛ **{hours} hours**, **{minutes} minutes**, and **{seconds} seconds**.")
#                 return message, flag
#             case "❌":
#                 await message.clear_reactions()
#                 flag = False
#                 return message, flag
#         return message, flag
#
#     async def startQuest(ctx, message, flag, quest, e):
#         current_quest = getPlayerQuest(user_id)
#         if current_quest == "":
#             QuestsDB.execute("UPDATE quests SET quest = ? WHERE user_id = ?", (quest, user_id))
#             e = discord.Embed(title = "🧭 Quest accepted!", description = f"*You set off to complete the conditions.*\n**Type **`{config.prefix}quest collect` **to collect the rewards.**", color = default_color)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
#             await ctx.send(embed = e)
#         else:
#             e = discord.Embed(title = "❌ Failed to accept quest!", description = "You already have a quest in progress.", color = 0xef5350)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
#             e.add_field(name = f"Current Quest: `{current_quest}`", value = f"Type `{config.prefix}quest collect` to complete this quest first.")
#             await ctx.send(embed = e)
#         return message, flag
#
#     async def completeQuest(ctx, message, flag, quest):
#         marketdata = getUserMarketInv(user_id)
#         ryou = marketdata.ryou
#         exp = getPlayerExp(user_id)
#         boost = getUserBoost(ctx)
#         now = int(time.time())
#         rewards_list = Quests[quest]["Rewards"]
#         ryou_range = rewards_list["Ryou"] if "Ryou" in rewards_list else [0, 0]
#         exp_range = rewards_list["EXP"] if "EXP" in rewards_list else [0, 0]
#         ryou_random = random.randint(ryou_range[0], ryou_range[1])
#         ryou_reward = ryou_random + math.floor(ryou_random * (boost / 100.))
#         exp_random = random.randint(exp_range[0], exp_range[1])
#         exp_reward = exp_random + math.floor(exp_random * (boost / 100.))
#         MarketDB.execute("UPDATE userdata SET ryou = ? WHERE user_id = ?", (ryou + ryou_reward, user_id))
#         exp_reward = addPlayerExp(user_id, exp_reward)
#         ActivityDB.execute("UPDATE quests SET last_activity = ? WHERE user_id = ?", (now, user_id))
#         QuestsDB.execute("UPDATE quests SET quest = ? WHERE user_id = ?", ("", user_id))
#         e = discord.Embed(title = f"🎊 Quest Completed  ─  `{quest}`", description = "Recieved the following rewards:", color = 0x4caf50)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["Kinka_Mei-4"][0])
#         e.add_field(name = f"Ryou{'  ─  (+' + str(boost) + '%)' if boost > 0 else ''}", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou_reward)}`", inline = True)
#         e.add_field(name = f"EXP{'  ─  (+' + str(boost) + '%)' if boost > 0 else ''}", value = f"{Icons['exp']} x {'`{:,}`'.format(exp_reward) if exp_reward != 0 else '`0` *(Level cap reached)*'}", inline = True)
#         message = await ctx.send(embed = e)
#         return message, flag
#
#     def getConditions(quest):
#         conditions_list = Quests[quest]["Conditions"]
#         conditions = ""
#         for condition in conditions_list:
#             for key, value in condition.items():
#                 match key:
#                     case "Defeat":
#                         conditions += f"**{key}**" + ": " + str(f"*{value[1]}*") + " " + f"__{value[0]}__" + "\n"
#                     case "Clear":
#                         match value[1]:
#                             case -1:
#                                 difficulty = "Any"
#                             case 0:
#                                 difficulty = "Normal"
#                             case 1:
#                                 difficulty = "Hard"
#                             case 2:
#                                 difficulty = "Hell"
#                             case 3:
#                                 difficulty = "Oni"
#                         conditions += f"**{key}**" + ": " + f"__{value[0]}__" + " - " + f"*{difficulty}*" + "\n"
#         return conditions
#
#     def getRewards(quest):
#         rewards_list = Quests[quest]["Rewards"]
#         rewards = ""
#         for key, value in rewards_list.items():
#             match key:
#                 case "Ryou":
#                     rewards += "**Ryou range**" + ": " + Icons["ryou"] + " __" + '{:,}'.format(value[0]) + " - " + '{:,}'.format(value[1]) + "__\n"
#                 case "EXP":
#                     rewards += "**EXP range**" + ": " + Icons["exp"] + " __" + '{:,}'.format(value[0]) + " - " + '{:,}'.format(value[1]) + "__\n"
#         rewards = "None" if rewards == "" else rewards
#         return rewards
#
#     def getDialogue(quest):
#         dialogue = ""
#         for line in Quests[quest]["Dialogue"]:
#             dialogue += line + " "
#         return dialogue
#
#     # main()
#     current_quest = getPlayerQuest(user_id)
#     message = None
#     flag = True
#     if arg == "collect" and current_quest != "":
#         quest = getPlayerQuest(user_id)
#         await completeQuest(ctx, message, flag, quest)
#         return
#     if now >= last_quest + wait or checkAdmin(ctx):
#         quest = chooseRandomQuest()
#         message, flag = await promptQuest(ctx, message, flag, quest)
#     else:
#         hours = math.floor((last_quest + wait - now) / 60 / 60)
#         minutes = math.floor((last_quest + wait - now) / 60 - (hours * 60))
#         seconds = (last_quest + wait - now) % 60
#         await ctx.send(f"There are currently no quests, please check back in ⌛ **{hours} hours**, **{minutes} minutes**, and **{seconds} seconds**.")

# @bot.command(aliases = ["market", "buy", "sell", "trade", "shop", "store"])
# @commands.check(checkChannel)
# async def tavern(ctx):
#     ''' | Usage: +market | Use reactions to navigate the menus '''
#     user_id         = ctx.author.id
#     menu_top        = config.menu_top
#     menu_separator  = config.menu_separator
#     menu_bottom     = config.menu_bottom
#     default_color   = config.default_color
#     numbers         = config.numbers
#     coin_name       = config.coin_name
#     conv_rate       = config.conv_rate
#     conv_rates      = [
#         f"{Icons['ryou']} x `{'{:,}'.format(conv_rate[0])}` *{coin_name}*  =  {Icons['ticket']} x `{'{:,}'.format(conv_rate[1])}` *Gacha Tickets*",
#         f"{Icons['ticket']} x `{'{:,}'.format(conv_rate[1])}` *Gacha Tickets*  =  {Icons['ryou']} x `{'{:,}'.format(int(conv_rate[0] / 10))}` *{coin_name}*"
#     ]
#
#     async def menuMain(ctx, message, flag):
#         banner = generateFileObject("GAMA-Market", Graphics["Banners"]["GAMA-Market"][0])
#         e = discord.Embed(title = f"Welcome to the {branch_name} Tavern!", description = "What would you like to do today?", color = default_color)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#         e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#         e.add_field(name = "▷ ⚖️  ──────  Trade  ───────  ⚖️ ◁", value = menu_separator, inline = False)
#         e.add_field(name = "▷ 🛒 ─────── Buy ──────── 🛒 ◁", value = menu_separator, inline = False)
#         e.add_field(name = "▷ ❌ ─────  Exit  Menu  ─────  ❌ ◁", value = menu_bottom, inline = False)
#         message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
#         emojis = ["⚖️", "🛒", "❌"]
#         reaction, user = await waitForReaction(ctx, message, e, emojis)
#         if reaction is None:
#             flag = False
#             return message, flag
#         match str(reaction.emoji):
#             case "⚖️":
#                 e.set_field_at(1, name = "►⚖️  ──────  Trade  ───────  ⚖️ ◄", value = menu_separator, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 message, flag = await tradeEntry(ctx, message, flag)
#                 return message, flag
#             case "🛒":
#                 e.set_field_at(2, name = "►🛒 ─────── Buy ──────── 🛒 ◄", value = menu_separator, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 message, flag = await shopEntry(ctx, message, flag)
#                 return message, flag
#             case "❌":
#                 e.set_field_at(3, name = "►❌ ─────  Exit  Menu  ─────  ❌ ◄", value = menu_bottom, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 flag = False
#                 return message, flag
#
#     async def tradeEntry(ctx, message, flag):
#         while flag:
#             inv_gacha   = getUserGachaInv(user_id)
#             inv_market  = getUserMarketInv(user_id)
#             tickets     = inv_gacha.gacha_tickets
#             fragments   = inv_gacha.gacha_fragments
#             total_rolls = inv_gacha.total_rolls
#             ryou        = inv_market.ryou
#             e = discord.Embed(title = f"Welcome to the {branch_name} Exchange!", description = "Exchange between *{coin_name}* and *Gacha Tickets*!", color = default_color)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#             e.add_field(name = "Conversion Rates:", value = conv_rates[0] + "\n" + conv_rates[1], inline = False)
#             e.add_field(name = f"Your {coin_name}:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
#             e.add_field(name = "Your Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
#             e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#             e.add_field(name = f"▷ {Icons['ticket']} ─ {coin_name} ─> Tickets ─  {Icons['ticket']} ◁", value = menu_separator, inline = False)
#             e.add_field(name = f"▷ {Icons['ryou']} ─ Tickets ─> {coin_name} ─  {Icons['ryou']} ◁", value = menu_separator, inline = False)
#             e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
#             await message.edit(embed = e)
#             emojis = [Icons['ticket'], Icons['ryou'], "↩️"]
#             reaction, user = await waitForReaction(ctx, message, e, emojis)
#             if reaction is None:
#                 flag = False
#                 return message, flag
#             match str(reaction.emoji):
#                 case x if x == Icons['ticket']:
#                     e.set_field_at(4, name = f"►{Icons['ticket']} ─ {coin_name} ─> Tickets ─  {Icons['ticket']} ◄", value = menu_separator, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     message, flag = await ryouToTickets(ctx, message, flag)
#                 case x if x == Icons['ryou']:
#                     e.set_field_at(5, name = f"►{Icons['ryou']} ─ Tickets ─> {coin_name} ─  {Icons['ryou']} ◄", value = menu_separator, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     message, flag = await ticketsToRyou(ctx, message, flag)
#                 case "↩️":
#                     e.set_field_at(6, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     return message, flag
#             if flag:
#                 continue
#             else:
#                 return message, flag
#
#     async def ryouToTickets(ctx, message, flag):
#         inv_gacha   = getUserGachaInv(user_id)
#         inv_market  = getUserMarketInv(user_id)
#         tickets     = inv_gacha.gacha_tickets
#         fragments   = inv_gacha.gacha_fragments
#         total_rolls = inv_gacha.total_rolls
#         ryou        = inv_market.ryou
#         if ryou >= conv_rate[0]:
#             e = discord.Embed(title = f"Welcome to the {branch_name} Exchange!", description = f"Trade your *{coin_name}* into *Gacha Tickets*", color = default_color)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#             e.add_field(name = "Conversion Rates:", value = conv_rates[0] + "\n" + conv_rates[1], inline = False)
#             e.add_field(name = f"Your {coin_name}:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
#             e.add_field(name = "Bulk Gacha Ticket yield:", value = f"{Icons['ticket']} x `{'{:,}'.format(math.floor(ryou / conv_rate[0]))}`", inline = True)
#             e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#             e.add_field(name = "▷ 1️⃣  ──── Exchange  One ────  1️⃣ ◁", value = menu_separator, inline = False)
#             e.add_field(name = "▷ *️⃣  ──── Exchange  Bulk ────  *️⃣ ◁", value = menu_separator, inline = False)
#             e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
#             await message.edit(embed = e)
#             emojis = ["1️⃣", "*️⃣", "↩️"]
#             reaction, user = await waitForReaction(ctx, message, e, emojis)
#             if reaction is None:
#                 flag = False
#                 return message, flag
#             match str(reaction.emoji):
#                 case "1️⃣":
#                     e.set_field_at(4, name = "►1️⃣  ──── Exchange  One ────  1️⃣ ◄", value = menu_separator, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     ryou_traded = int(conv_rate[0])
#                     tickets_traded = int(conv_rate[1])
#                 case "*️⃣":
#                     e.set_field_at(5, name = "►*️⃣  ──── Exchange  Bulk ────  *️⃣ ◄", value = menu_separator, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     ryou_traded = int(math.floor(ryou / conv_rate[0]) * conv_rate[0])
#                     tickets_traded = int(math.floor(ryou / conv_rate[0]) * conv_rate[1])
#                 case "↩️":
#                     e.set_field_at(6, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     return message, flag
#             e = discord.Embed(title = "Trade Result", description = f"✅ Successfully Exchanged *{coin_name}* into *Gacha Tickets*!", color = 0x4caf50)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#             e.add_field(name = f"Traded *{coin_name}*:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou_traded)}`", inline = True)
#             e.add_field(name = "Obtained *Gacha Tickets*:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets_traded)}`", inline = True)
#             e.add_field(name = f"You now have this many *{coin_name}* left:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou - ryou_traded)}`", inline = False)
#             e.add_field(name = "Your total *Gacha Tickets* are now:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets + tickets_traded)}`", inline = False)
#             message = await ctx.send(embed = e)
#             MarketDB.userdata[user_id] = {"ryou": ryou - ryou_traded}
#             GachaDB.userdata[user_id] = {"gacha_tickets": tickets + tickets_traded, "gacha_fragments": fragments, "total_rolls": total_rolls}
#             flag = False
#             return message, flag
#         else:
#             e = discord.Embed(title = "Trade Result", description = "❌ Exchange Failed!", color = 0xef5350)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#             e.add_field(name = f"You have insufficient *{coin_name}*.", value =  f"Need {Icons['ryou']} x `{'{:,}'.format(conv_rate[0] - ryou)}` more!", inline = False)
#             message = await ctx.send(embed = e)
#             flag = False
#             return message, flag
#
#     async def ticketsToRyou(ctx, message, flag):
#         inv_gacha   = getUserGachaInv(user_id)
#         inv_market  = getUserMarketInv(user_id)
#         tickets     = inv_gacha.gacha_tickets
#         fragments   = inv_gacha.gacha_fragments
#         total_rolls = inv_gacha.total_rolls
#         ryou        = inv_market.ryou
#         if tickets >= conv_rate[1]:
#             e = discord.Embed(title = f"Welcome to the {branch_name} Exchange!", description = f"Trade your *Gacha Tickets* into *{coin_name}*", color = default_color)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#             e.add_field(name = "Conversion Rates:", value = conv_rates[0] + "\n" + conv_rates[1], inline = False)
#             e.add_field(name = "Your Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
#             e.add_field(name = f"Bulk {coin_name} yield:", value = f"{Icons['ryou']} x `{'{:,}'.format(math.floor(tickets * (conv_rate[0] / 10)))}`", inline = True)
#             e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#             e.add_field(name = "▷ 1️⃣  ──── Exchange  One ────  1️⃣ ◁", value = menu_separator, inline = False)
#             e.add_field(name = "▷ *️⃣  ──── Exchange  Bulk ────  *️⃣ ◁", value = menu_separator, inline = False)
#             e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
#             await message.edit(embed = e)
#             emojis = ["1️⃣", "*️⃣", "↩️"]
#             reaction, user = await waitForReaction(ctx, message, e, emojis)
#             if reaction is None:
#                 flag = False
#                 return message, flag
#             match str(reaction.emoji):
#                 case "1️⃣":
#                     e.set_field_at(4, name = "►1️⃣  ──── Exchange  One ────  1️⃣ ◄", value = menu_separator, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     ryou_traded = int(conv_rate[0] / 10)
#                     tickets_traded = int(conv_rate[1])
#                 case "*️⃣":
#                     e.set_field_at(5, name = "►*️⃣  ──── Exchange  Bulk ────  *️⃣ ◄", value = menu_separator, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     ryou_traded = int(math.floor(tickets / conv_rate[1]) * (conv_rate[0] / 10))
#                     tickets_traded = int(tickets)
#                 case "↩️":
#                     e.set_field_at(6, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     return message, flag
#             e = discord.Embed(title = "Trade Result", description = f"✅ Successfully Exchanged *Gacha Tickets* into *{coin_name}*!", color = 0x4caf50)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#             e.add_field(name = "Traded *Gacha Tickets*:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets_traded)}`", inline = True)
#             e.add_field(name = f"Obtained *{coin_name}*:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou_traded)}`", inline = True)
#             e.add_field(name = "You now have this many *Gacha Tickets* left:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets - tickets_traded)}`", inline = False)
#             e.add_field(name = f"Your total *{coin_name}* are now:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou + ryou_traded)}`", inline = False)
#             message = await ctx.send(embed = e)
#             GachaDB.userdata[user_id] = {"gacha_tickets": tickets - tickets_traded, "gacha_fragments": fragments, "total_rolls": total_rolls}
#             MarketDB.userdata[user_id] = {"ryou": ryou + ryou_traded}
#             flag = False
#             return message, flag
#         else:
#             e = discord.Embed(title = "Trade Result", description = "❌ Exchange Failed!", color = 0xef5350)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#             e.add_field(name = "You have insufficient *Gacha Tickets*.", value =  f"Need {Icons['ticket']} x `{'{:,}'.format(conv_rate[1] - tickets)}` more!", inline = False)
#             message = await ctx.send(embed = e)
#             flag = False
#             return message, flag
#
#     async def shopEntry(ctx, message, flag):
#         products_length = len(Products)
#         e = discord.Embed(title = f"Welcome to the {branch_name} Shop!", description = "Select a product to purchase:", color = default_color)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#         # Set offset to 0 (page 1) and begin bidirectional page system
#         offset = 0
#         while flag:
#             counter = 0
#             emojis = []
#             # Iterate through products in groups of 5
#             for index, product in enumerate(Products):
#                 if index < offset:
#                     # Skipping to next entry until arriving at the proper page/offset
#                     continue
#                 e.add_field(name = f"{numbers[counter]}  -  ***{product}***", value = f"╰ Price: {Icons['ryou']} x `{'{:,}'.format(Products[product]['Price'])}`", inline = True)
#                 emojis.append(numbers[counter])
#                 counter +=1
#                 # Once a full page is assembled, print it
#                 if counter == 6 or index + 1 == products_length:
#                     await message.edit(embed = e)
#                     if index + 1 > 6 and index + 1 < products_length:
#                         # Is a middle page
#                         emojis[:0] = ["⏪", "⏩", "❌"]
#                     elif index + 1 < products_length:
#                         # Is the first page
#                         emojis[:0] = ["⏩", "❌"]
#                     elif products_length > 6:
#                         # Is the last page
#                         emojis[:0] = ["⏪", "❌"]
#                     else:
#                         # Is the only page
#                         emojis[:0] = ["❌"]
#                     reaction, user = await waitForReaction(ctx, message, e, emojis)
#                     if reaction is None:
#                         flag = False
#                         return message, flag
#                     match str(reaction.emoji):
#                         case "⏩":
#                             # Tell upcomming re-iteration to skip to the next page's offset
#                             offset += 6
#                             await message.clear_reactions()
#                             e.clear_fields()
#                             break
#                         case "⏪":
#                             # Tell upcomming re-iteration to skip to the previous page's offset
#                             offset -= 6
#                             await message.clear_reactions()
#                             e.clear_fields()
#                             break
#                         case "❌":
#                             await message.clear_reactions()
#                             return message, flag
#                         case number_emoji if number_emoji in numbers:
#                             await message.clear_reactions()
#                             product_index = getProductIndex(number_emoji, offset)
#                             product = getProduct(product_index)
#                             if product is None:
#                                 await ctx.send("The product you chose could not be loaded!")
#                                 flag = False
#                             else:
#                                 e.clear_fields()
#                                 message, flag = await selectProduct(ctx, message, flag, product)
#                                 if flag:
#                                     break
#                                 else:
#                                     return message, flag
#                     if flag:
#                         continue
#                     else:
#                         return message, flag
#
#     async def selectProduct(ctx, message, flag, product):
#         stock = getProductStock(product)
#         attributes = getProductAttributes(product)
#         e = discord.Embed(title = f"Cart Checkout", description = f"Properties of product selected:", color = default_color)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#         e.add_field(name = "Product name", value = f"🏷️ **{product}**", inline = True)
#         e.add_field(name = "Price", value = f"{Icons['ryou']} x `{'{:,}'.format(Products[product]['Price'])}`", inline = True)
#         e.add_field(name = "Current stock", value = f"🏦 `{stock}`", inline = True)
#         e.add_field(name = "Type", value = f"🔧 `{Products[product]['Type']}`", inline = True)
#         e.add_field(name = "Stacks in inventory?", value = f"🗃️ `{str(Products[product]['Stackable'])}`", inline = True)
#         e.add_field(name = f"📍 Attributes ({len(Products[product]['Attributes'])}):", value = "None" if not attributes else f"```{attributes}```", inline = False)
#         e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#         e.add_field(name = "▷ ✅   ─────   Purchase   ─────    ✅ ◁", value = menu_separator, inline = False)
#         e.add_field(name = "▷ 🚫  ──────   Cancel   ──────  🚫 ◁", value = menu_bottom, inline = False)
#         await message.edit(embed = e)
#         emojis = ["✅", "🚫"]
#         reaction, user = await waitForReaction(ctx, message, e, emojis)
#         if reaction is None:
#             flag = False
#             return message, flag
#         match str(reaction.emoji):
#             case "✅":
#                 e.set_field_at(7, name = "►✅   ─────   Purchase   ─────    ✅ ◄", value = menu_separator, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 message, flag = await buyProduct(ctx, message, flag, product)
#                 flag = False
#                 return message, flag
#             case "🚫":
#                 e.set_field_at(8, name = "►🚫  ──────   Cancel   ──────  🚫 ◄", value = menu_bottom, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 return message, flag
#
#     async def buyProduct(ctx, message, flag, product):
#         inv_gacha       = getUserGachaInv(user_id)
#         inv_market      = getUserMarketInv(user_id)
#         inv_items       = getUserItemInv(user_id)
#         item_quantity   = getUserItemQuantity(user_id, product)
#         requirements    = getProductRequirements(product)
#         stock           = getProductStock(product)
#         tickets         = inv_gacha.gacha_tickets
#         fragments       = inv_gacha.gacha_fragments
#         total_rolls     = inv_gacha.total_rolls
#         ryou            = inv_market.ryou
#         price           = Products[product]["Price"]
#         stackable       = Products[product]['Stackable']
#         if stock == "Unlimited" or stock > 0:
#             if checkMeetsItemRequirements(user_id, product):
#                 if ryou >= price:
#                     if stackable or not stackable and item_quantity == None:
#                         if not updateProductStock(product):
#                             await ctx.send("‼️ Critical Error: Could not complete transaction. ‼️")
#                             flag = False
#                             return message, flag
#                         if item_quantity == None:
#                             ItemsDB.execute("INSERT INTO {} (item, quantity) VALUES ('{}', {})".format(f"user_{user_id}", product, 1))
#                         else:
#                             ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity + 1, product))
#                         MarketDB.execute("UPDATE userdata SET ryou = ? WHERE user_id = ?", (ryou - price, user_id))
#                         e = discord.Embed(title = "Checkout Result", description = f"✅ Purchase was successful!", color = 0x4caf50)
#                         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#                         e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#                         e.add_field(name = f"Spent *{coin_name}*:", value = f"{Icons['ryou']} x `{'{:,}'.format(price)}`", inline = True)
#                         e.add_field(name = "Obtained *Item*:", value = f"🏷️ ***{product}***", inline = True)
#                         e.add_field(name = f"You now have this many *{coin_name}* left:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou - price)}`", inline = False)
#                         await ctx.send(embed = e)
#                         if product in config.role_boosts:
#                             await addRole(ctx, product)
#                     else:
#                         e = discord.Embed(title = "Checkout Result", description = "❌ Purchase Failed!", color = 0xef5350)
#                         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#                         e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#                         e.add_field(name = "This item is not stackable!", value =  "You already have one of this item.", inline = False)
#                         await ctx.send(embed = e)
#                 else:
#                     e = discord.Embed(title = "Checkout Result", description = "❌ Purchase Failed!", color = 0xef5350)
#                     e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#                     e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#                     e.add_field(name = f"You have insufficient *{coin_name}*.", value =  f"Need {Icons['ryou']} x `{'{:,}'.format(price - ryou)}` more!", inline = False)
#                     await ctx.send(embed = e)
#             else:
#                 e = discord.Embed(title = "Checkout Result", description = "❌ Purchase Failed!", color = 0xef5350)
#                 e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#                 e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#                 e.add_field(name = "You do not meet the product requirements.", value =  f"Check your {config.prefix}inv to compare your items to the requirements above.", inline = False)
#                 await ctx.send(embed = e)
#         else:
#             e = discord.Embed(title = "Checkout Result", description = "❌ Purchase Failed!", color = 0xef5350)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["GAMA-Market_TN"][0])
#             e.add_field(name = "This product is out of stock!", value = "Sorry! Please come again~", inline = False)
#             await ctx.send(embed = e)
#         return message, flag
#
#     def getProductIndex(number_emoji, offset = 0):
#         for n, emoji in enumerate(numbers):
#             if number_emoji == emoji:
#                 product_index = n + offset
#         return product_index
#
#     def getProduct(product_index):
#         product_array = list(Products.items())
#         for p in Products:
#             if p == product_array[product_index][0]:
#                 product = p
#                 break
#             else:
#                 product = None
#         return product
#
#     def getProductAttributes(product):
#         attributes = Products[product]["Attributes"]
#         attributes_formatted = ""
#         for attribute in attributes:
#             border = ""
#             for _ in attribute:
#                 border += "═"
#             attributes_formatted += f"╔{border}╗\n║{attribute}║\n╚{border}╝\n"
#         return attributes_formatted
#
#     def getProductRequirements(product):
#         requirements = Products[product]["Requirements"]
#         return requirements
#
#     def checkMeetsItemRequirements(user_id, product):
#             inv_items = getUserItemInv(user_id)
#             requirements = getProductRequirements(product)
#             if not requirements:
#                 meets_requirements = True
#             elif not inv_items:
#                     meets_requirements = False
#             else:
#                 for requirement, quantity in requirements.items():
#                     for item in inv_items:
#                         if item[0] == requirement and item[1] >= quantity:
#                             meets_requirements = True
#                             break
#                         else:
#                             meets_requirements = False
#                             continue
#             return meets_requirements
#
#     def getProductStock(product):
#         data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{product}'")
#         if data:
#             stock = GachaDB.backstock[product]
#             current_stock = stock.current_stock
#             return current_stock
#         else:
#             return "Unlimited"
#
#     def updateProductStock(product):
#         data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{product}'")
#         if data:
#             stock = GachaDB.backstock[product]
#             current_stock = stock.current_stock
#             times_rolled = stock.times_rolled
#             max_limit = stock.max_limit
#             if times_rolled < max_limit and current_stock > 0:
#                 GachaDB.backstock[product] = {"current_stock": current_stock - 1, "times_rolled": times_rolled + 1, "max_limit": max_limit}
#                 return True
#             else:
#                 return False
#         else:
#             return True
#
#     # main()
#     message = None
#     flag = True
#     while flag:
#         message, flag = await menuMain(ctx, message, flag)

@bot.command(aliases = ["gacha", "spin"])
@commands.check(checkChannel)
async def roll(ctx, skip=None):
    ''' | Usage: +roll | Use reactions to navigate the menus '''
    user_id         = ctx.author.id
    menu_top        = config.menu_top
    menu_separator  = config.menu_separator
    menu_bottom     = config.menu_bottom
    default_color   = config.default_color
    colors          = config.colors
    capsules        = config.capsules
    capsule_colors  = config.capsule_colors
    progressbar     = config.progressbar

    if skip == "skip":
        skip = True
    else:
        skip = False

    async def loadProgressBar(ctx, message, e):
        for step, color in enumerate(colors):
            e.color = color
            e.set_field_at(1, name = progressbar[step + 1], value = menu_bottom, inline = False)
            await message.edit(embed = e)
            time.sleep(0.5)

    async def updateStock(ctx, sub_prize):
        data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{sub_prize}'")
        if data:
            stock = GachaDB.backstock[sub_prize]
            current_stock = stock.current_stock
            times_rolled = stock.times_rolled
            max_limit = stock.max_limit
            if times_rolled < max_limit and current_stock > 0:
                GachaDB.backstock[sub_prize] = {"current_stock": current_stock - 1, "times_rolled": times_rolled + 1, "max_limit": max_limit}
                return True
            else:
                await ctx.send(f"Prize **'{sub_prize}'** is out of stock!")
                return False
        else:
            return True

    async def rewardPrize(ctx, tier, capsule):
        prize_array     = Prizes[tier]["prizes"][capsule]
        user_id         = ctx.author.id
        member          = ctx.author
        inventory       = getUserGachaInv(user_id)
        tickets         = inventory.gacha_tickets
        fragments       = inventory.gacha_fragments
        total_rolls     = inventory.total_rolls
        grand_prize_string = f"1 {branch_name} NFT"
        for sub_prize in prize_array:
            match sub_prize:
                case "VIP Pass":
                    wl_role = discord.utils.get(ctx.guild.roles, name = config.wl_role)
                    if not wl_role in ctx.author.roles:
                        if await updateStock(ctx, sub_prize):
                            await member.add_roles(wl_role)
                            await ctx.send(f"🎉 Rewarded {ctx.author.mention} with __Whitelist__ Role: **{config.wl_role}**!")
                        else:
                            continue
                    else:
                        amount = config.role_consolation
                        GachaDB.userdata[user_id] = {"gacha_tickets": tickets + amount, "gacha_fragments": fragments, "total_rolls": total_rolls}
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with consolation prize: **{amount} Gacha Ticket(s)**! User now has a total of `{tickets + amount}`.")
                # case "GOLD PASS":
                #     gold_pass_role = discord.utils.get(ctx.guild.roles, name = config.gold_pass_role)
                #     if not gold_pass_role in ctx.author.roles:
                #         if await updateStock(ctx, sub_prize):
                #             await member.add_roles(gold_pass_role)
                #             await ctx.send(f"🎉 Rewarded {ctx.author.mention} with GOLD PASS Role: **{config.gold_pass_role}**!")
                #         else:
                #             continue
                case "OG":
                    og_role = discord.utils.get(ctx.guild.roles, name = config.og_role)
                    if not og_role in ctx.author.roles:
                        if await updateStock(ctx, sub_prize):
                            await member.add_roles(og_role)
                            await ctx.send(f"🎉 Rewarded {ctx.author.mention} with __OG__ Role: **{config.og_role}**!")
                        else:
                            continue
                    else:
                        amount = config.role_consolation
                        GachaDB.userdata[user_id] = {"gacha_tickets": tickets + amount, "gacha_fragments": fragments, "total_rolls": total_rolls}
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with consolation prize: **{amount} Gacha Ticket(s)**! User now has a total of `{tickets + amount}`.")
                case "Safe from purge":
                    safe_role = discord.utils.get(ctx.guild.roles, name = config.safe_role)
                    if not safe_role in ctx.author.roles:
                        if await updateStock(ctx, sub_prize):
                            await member.add_roles(safe_role)
                            await ctx.send(f"🎉 Rewarded {ctx.author.mention} with __Safe From Purge__ Role: **{config.safe_role}**!")
                        else:
                            continue
                    else:
                        amount = config.role_consolation
                        GachaDB.userdata[user_id] = {"gacha_tickets": tickets + amount, "gacha_fragments": fragments, "total_rolls": total_rolls}
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with consolation prize: **{amount} Gacha Ticket(s)**! User now has a total of `{tickets + amount}`.")
                # case x if x.endswith("EXP"):
                #     exp = int(x.rstrip(" EXP"))
                #     # channel = bot.get_channel(config.channels["exp"])
                #     # role_id = config.gacha_mod_role
                #     # if await updateStock(ctx, sub_prize):
                #     #     if not checkAdmin(ctx):
                #     #         await channel.send(f"<@&{role_id}> | {ctx.author.mention} has won {exp} EXP from the Gacha! Please paste this to reward them:{chr(10)}`!give-xp {ctx.author.mention} {exp}`")
                #     #     await ctx.send(f"🎉 Reward sent for reviewal: {ctx.author.mention} with **{exp} EXP**!")
                #     if await updateStock(ctx, sub_prize):
                #         exp_reward = addPlayerExp(user_id, exp)
                #         await ctx.send(f"🎉 Rewarded {ctx.author.mention} with **{'{:,}'.format(exp_reward)} EXP**!")
                #     else:
                #         continue
                # case x if x.endswith(f"{coin_name}"):
                #     ryou = int(x.rstrip(f" {coin_name}"))
                #     if await updateStock(ctx, sub_prize):
                #         ryou_reward = addPlayerRyou(user_id, ryou)
                #         await ctx.send(f"🎉 Rewarded {ctx.author.mention} with **{'{:,}'.format(ryou_reward)} {coin_name}**!")
                #     else:
                #         continue
                case x if x.endswith("Fragment") or x.endswith("Fragments"):
                    amount = int(x.split(" ")[0])
                    if await updateStock(ctx, sub_prize):
                        GachaDB.userdata[user_id] = {"gacha_tickets": tickets, "gacha_fragments": fragments + amount, "total_rolls": total_rolls}
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with prize: **{amount} Gacha Fragment(s)**! User now has a total of `{fragments + amount}`.")
                    else:
                        continue
                case x if x.endswith("Ticket") or x.endswith("Tickets"):
                    amount = int(x.split(" ")[0])
                    if await updateStock(ctx, sub_prize):
                        GachaDB.userdata[user_id] = {"gacha_tickets": tickets + amount, "gacha_fragments": fragments, "total_rolls": total_rolls}
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with prize: **{amount} Gacha Ticket(s)**! User now has a total of `{tickets + amount}`.")
                    else:
                        continue
                # case x if x.endswith("Energy Restores"):
                #     product = "Energy Restore"
                #     amount = int(x.rstrip(" Energy Restores"))
                #     if await updateStock(ctx, product):
                #         item_quantity = getUserItemQuantity(user_id, product)
                #         if item_quantity == None:
                #             ItemsDB.execute("INSERT INTO {} (item, quantity) VALUES ('{}', {})".format(f"user_{user_id}", product, 1))
                #         else:
                #             ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity + 1, product))
                #         await ctx.send(f"🎉 Rewarded {ctx.author.mention} with **{sub_prize}**!")
                #     else:
                #         continue
                case x if x.endswith(f"{Icons['ryou']} WOG"):
                    amount = int(x.split(" ")[0])
                    channel = bot.get_channel(config.channels["reward"])
                    role_id = config.gacha_mod_role
                    if await updateStock(ctx, sub_prize):
                        await channel.send(f"<@&{role_id}> | {ctx.author.mention} has won __{amount} {Icons['ryou']} WOG__ from the Gacha! Please paste this to reward them:{chr(10)}`.give-rewards {ctx.author.mention} {amount}`")
                        await ctx.send(f"🎉 Reward sent for reviewal: {ctx.author.mention} with **__{amount} {Icons['ryou']} WOG__**!")
                    else:
                        continue
                case x if x == grand_prize_string:
                    role_id = config.gacha_mod_role
                    if await updateStock(ctx, sub_prize):
                        await ctx.send(f"<@&{role_id}> | 🎉 {ctx.author.mention} has just won the grand prize! 🏆 Congratulations! 🎊")
                    else:
                        continue

    def getPrize(tier, capsule, filter = True):
        prize_array = Prizes[tier]["prizes"][capsule]
        prize_length = len(prize_array)
        full_prize = ""
        prize_counter = 0
        for sub_prize in prize_array:
            # Build full string with all prizes in array
            prize_counter += 1
            data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{sub_prize}'")
            if data:
                # Check backstock of sub prize
                stock = GachaDB.backstock[sub_prize]
                current_stock = stock.current_stock
                times_rolled = stock.times_rolled
                max_limit = stock.max_limit
                if not times_rolled < max_limit and not current_stock > 0:
                    # Prize is out of stock, skip it
                    if filter:
                        continue
            full_prize += sub_prize
            if prize_counter < prize_length:
                # Add separator between prizes in the string
                full_prize += " + "
        # Ensure not empty string
        if full_prize == "":
            full_prize = " "
        return full_prize

    async def raffleEntry(ctx, message, e, tier, skip):
        inventory       = getUserGachaInv(user_id)
        tickets         = inventory.gacha_tickets
        fragments       = inventory.gacha_fragments
        total_rolls     = inventory.total_rolls
        name            = Prizes[tier]["name"]
        symbol          = Prizes[tier]["symbol"]
        cost            = Prizes[tier]["tickets_required"]
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Spin to win!", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
        e.add_field(name = f"{name} Raffle", value = symbol, inline = True)
        e.add_field(name = "Admission:", value = f"🎟️ x {cost} ticket(s)", inline = True)
        e.add_field(name = "Your current tickets:", value = tickets, inline = False)
        if tickets >= cost:
            e.add_field(name = "Tickets after spinning:", value = tickets - cost, inline = False)
            e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
            e.add_field(name = "▷ 🎲 ────  Spin the Gacha  ──── 🎲 ◁", value = menu_separator, inline = False)
            e.add_field(name = "▷ ↩️  ──  Select another Raffle  ──  ↩️ ◁", value = menu_bottom, inline = False)
            await message.edit(embed = e)
            emojis = ["🎲", "↩️"]
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                return message, e, False
            match str(reaction.emoji):
                case "🎲":
                    e.set_field_at(5, name = "►🎲 ────  Spin the Gacha  ──── 🎲 ◄", value = menu_separator, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    message, e = await rollGacha(ctx, message, e, tier, name, cost, symbol, tickets, fragments, total_rolls, skip)
                    return message, e, True
                case "↩️":
                    e.set_field_at(6, name = "►↩️  ──  Select another Raffle  ──  ↩️ ◄", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    return message, e, False
        else:
            e.add_field(name = "You need this many more tickets to spin:", value = cost - tickets, inline = False)
            e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
            e.add_field(name = "▷ ↩️  ──  Select another Raffle  ──  ↩️ ◁", value = menu_bottom, inline = False)
            await message.edit(embed = e)
            emojis = ["↩️"]
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                return message, e, False
            match str(reaction.emoji):
                case "↩️":
                    e.set_field_at(5, name = "►↩️  ──  Select another Raffle  ──  ↩️ ◄", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    return message, e, False

    async def rollGacha(ctx, message, e, tier, name, cost, symbol, tickets, fragments, total_rolls, skip):
        # Subtract ticket(s) from user's inventory, increment roll count, then roll the gacha
        GachaDB.userdata[user_id] = {"gacha_tickets": tickets - cost, "gacha_fragments": fragments, "total_rolls": total_rolls + 1}
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Good luck!", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
        e.add_field(name = f"Spinning the {name} Raffle:", value = menu_top, inline = False)
        e.add_field(name = progressbar[0], value = menu_bottom, inline = False)
        await message.edit(embed = e)
        if not skip:
            await loadProgressBar(ctx, message, e)
        message, e = await pullCapsule(ctx, message, e, tier, name, cost, symbol, tickets, fragments, total_rolls)
        return message, e

    async def pullCapsule(ctx, message, e, tier, name, cost, symbol, tickets, fragments, total_rolls):
        cold_weights = config.weights[tier]

        # Nullify chances to roll a capsule if its prize array is empty
        for index, category in enumerate(Prizes[tier]["prizes"]):
            if not Prizes[tier]["prizes"][category]:
                cold_weights[index] = 0

        # Rebalance weights to ensure they add up to 100
        cold_weights = rebalanceWeights(cold_weights)

        if Prizes[tier]["regulated"]:
            # Modify probability for regulated prize
            regulated_prize = getPrize(tier, "platinum", filter = False)
            GachaDB.execute(f"INSERT OR IGNORE INTO backstock (prize, current_stock, times_rolled, max_limit) values ('{regulated_prize}', '0', '0', '0')")
            stock = GachaDB.backstock[regulated_prize]
            current_stock = stock.current_stock
            times_rolled = stock.times_rolled
            max_limit = stock.max_limit
            if times_rolled < max_limit and current_stock > 0:
                # Max limit hasn't been reached, allow platinum to be rolled
                which_mod = times_rolled
                mod = config.weight_mods[which_mod]
            else:
                # Nullify chance to roll platinum
                mod = cold_weights[5]
            hot_weights = [cold_weights[0] + mod / 5, cold_weights[1] + mod / 5, cold_weights[2] + mod / 5, cold_weights[3] + mod / 5, cold_weights[4] + mod / 5, cold_weights[5] - mod]
            # Use modified probabilities
            capsule = randomWeighted(capsules, hot_weights)
        else:
            # Use unmodified probabilities
            capsule = randomWeighted(capsules, cold_weights)
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = f"🎉 Congratulations {ctx.author.mention}! 🎊")
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        match capsule:
            case "blue":
                e.color = capsule_colors[0]
                e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                e.set_image(url = Resource["Blue"][0])
            case "green":
                e.color = capsule_colors[1]
                e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                e.set_image(url = Resource["Green"][0])
            case "red":
                e.color = capsule_colors[2]
                e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                e.set_image(url = Resource["Red"][0])
            case "silver":
                e.color = capsule_colors[3]
                e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                e.set_image(url = Resource["Silver"][0])
            case "gold":
                e.color = capsule_colors[4]
                e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                e.set_image(url = Resource["Gold"][0])
            case "platinum":
                e.color = capsule_colors[5]
                e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                e.set_image(url = Resource["Platinum"][0])
        prize = getPrize(tier, capsule)
        e.add_field(name = "Raffle Spun:", value = f"{symbol} {name} {symbol}", inline = True)
        e.add_field(name = "You Won:", value = f"🎁 {prize} 🎁", inline = True)
        # Add record of prize to database
        prize_id = str(user_id) + str("{:05d}".format(total_rolls + 1))
        now = datetime.utcnow()
        GachaDB.prizehistory[prize_id] = {"user_id": user_id, "date": now, "tickets_spent": cost, "tier": tier, "capsule": capsule, "prize": prize}
        e.set_footer(text = f"Prize ID: {prize_id}")
        # Reward prizes if applicable
        await rewardPrize(ctx, tier, capsule)
        await message.edit(embed = e)
        return message, e

    # main()
    exit_flag = edit_flag = False
    while not (exit_flag):
        prev_flag = False
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Test your luck for amazing prizes!", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
        e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
        e.add_field(name = "▷ 📜 ─────  Prize  List  ────── 📜 ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ 🎰 ──── Select  a  Raffle ──── 🎰 ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ 📦 ── View your inventory ─── 📦 ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ ❌ ─────  Exit  Menu  ─────  ❌ ◁", value = menu_bottom, inline = False)
        if not edit_flag:
            message = await ctx.send(embed = e)
        else:
            await message.edit(embed = e)
        emojis = ["📜", "🎰", "📦", "❌"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            break
        match str(reaction.emoji):
            case "📜":
                def formatPrizeList(tier):
                    formatted_prize_list = f"\
                        🔵  ─  *Blue*  ─  {config.encouragement[tier][0]}%\n  └ **__{getPrize(tier, 'blue')}__**\n\
                        🟢  ─  *Green*  ─  {config.encouragement[tier][1]}%\n  └ **__{getPrize(tier, 'green')}__**\n\
                        🔴  ─  *Red*  ─  {config.encouragement[tier][2]}%\n  └ **__{getPrize(tier, 'red')}__**\n\
                        ⚪  ─  *Silver*  ─  {config.encouragement[tier][3]}%\n  └ **__{getPrize(tier, 'silver')}__**\n\
                        🟡  ─  *Gold*  ─  {config.encouragement[tier][4]}%\n  └ **__{getPrize(tier, 'gold')}__**\n\
                        🟣  ─  *Platinum*  ─  {config.encouragement[tier][5]}%\n  └ **__{getPrize(tier, 'platinum')}__**\n\
                    "
                    return formatted_prize_list

                e.set_field_at(1, name = "►📜 ─────  Prize  List  ────── 📜 ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Here are today's prize pools:", color = default_color)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                # e.add_field(name = f"Tier 1: {Prizes['tier_1']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_1']['tickets_required']}", value = formatPrizeList("tier_1"), inline = True)
                # e.add_field(name = f"Tier 2: {Prizes['tier_2']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_2']['tickets_required']}", value = formatPrizeList("tier_2"), inline = True)
                # e.add_field(name = "\u200b", value = "\u200b", inline = True)
                # e.add_field(name = f"Tier 3: {Prizes['tier_3']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_3']['tickets_required']}", value = formatPrizeList("tier_3"), inline = True)
                e.add_field(name = f"__{Prizes['tier_4']['name']}__: {Prizes['tier_4']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_4']['tickets_required']}", value = formatPrizeList("tier_4"), inline = True)
                e.add_field(name = "\u200b", value = "\u200b", inline = True)
                e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
                e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                emojis = ["↩️"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                if reaction is None:
                    break
                match str(reaction.emoji):
                    case "↩️":
                        prev_flag = edit_flag = True
                        e.set_field_at(3, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                        await message.edit(embed = e)
                        await message.clear_reactions()
            case "🎰":
                e.set_field_at(2, name = "►🎰 ──── Select  a  Raffle ──── 🎰 ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                while not (exit_flag or prev_flag):
                    e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Select a Gacha Unit to spin!", color = default_color)
                    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                    e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                    e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
                    # e.add_field(name = "▷ 🥉 ───── Tier 1 Raffle ───── 🥉 ◁", value = menu_separator, inline = False)
                    # e.add_field(name = "▷ 🥈 ───── Tier 2 Raffle ───── 🥈 ◁", value = menu_separator, inline = False)
                    # e.add_field(name = "▷ 🥇 ───── Tier 3 Raffle ───── 🥇 ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ 🏅 ────  GAMA   Raffle  ──── 🏅 ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    # emojis = ["🥉", "🥈", "🥇", "🏅", "↩️"]
                    emojis = ["🏅", "↩️"]
                    reaction, user = await waitForReaction(ctx, message, e, emojis)
                    if reaction is None:
                        exit_flag = True
                        break
                    match str(reaction.emoji):
                        # case "🥉":
                        #     tier = "tier_1"
                        #     e.set_field_at(1, name = "►🥉 ───── Tier 1 Raffle ───── 🥉 ◄", value = menu_separator, inline = False)
                        #     await message.edit(embed = e)
                        #     await message.clear_reactions()
                        #     message, e, status = await raffleEntry(ctx, message, e, tier, skip)
                        #     if status:
                        #         rolled_flag = True
                        #     else:
                        #         rolled_flag = False
                        # case "🥈":
                        #     tier = "tier_2"
                        #     e.set_field_at(2, name = "►🥈 ───── Tier 2 Raffle ───── 🥈 ◄", value = menu_separator, inline = False)
                        #     await message.edit(embed = e)
                        #     await message.clear_reactions()
                        #     message, e, status = await raffleEntry(ctx, message, e, tier, skip)
                        #     if status:
                        #         rolled_flag = True
                        #     else:
                        #         rolled_flag = False
                        # case "🥇":
                        #     tier = "tier_3"
                        #     e.set_field_at(3, name = "►🥇 ───── Tier 3 Raffle ───── 🥇 ◄", value = menu_separator, inline = False)
                        #     await message.edit(embed = e)
                        #     await message.clear_reactions()
                        #     message, e, status = await raffleEntry(ctx, message, e, tier, skip)
                        #     if status:
                        #         rolled_flag = True
                        #     else:
                        #         rolled_flag = False
                        case "🏅":
                            tier = "tier_4"
                            e.set_field_at(1, name = "►🏅 ────  GAMA   Raffle  ──── 🏅 ◄", value = menu_separator, inline = False)
                            await message.edit(embed = e)
                            await message.clear_reactions()
                            message, e, status = await raffleEntry(ctx, message, e, tier, skip)
                            if status:
                                rolled_flag = True
                            else:
                                rolled_flag = False
                        case "↩️":
                            prev_flag = edit_flag = True
                            e.set_field_at(2, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                            await message.edit(embed = e)
                            await message.clear_reactions()
                            break
                    if rolled_flag:
                        time.sleep(0.3)
                        emojis = ["🔁", "❌"]
                        reaction, user = await waitForReaction(ctx, message, e, emojis, False)
                        if reaction is None:
                            exit_flag = True
                            break
                        match str(reaction.emoji):
                            case "🔁":
                                await message.clear_reactions()
                                exit_flag = edit_flag = False
                                prev_flag = True
                            case "❌":
                                await message.clear_reactions()
                                exit_flag = True
            case "📦":
                inv_gacha   = getUserGachaInv(user_id)
                inv_market  = getUserMarketInv(user_id)
                tickets     = inv_gacha.gacha_tickets
                fragments   = inv_gacha.gacha_fragments
                total_rolls = inv_gacha.total_rolls
                ryou        = inv_market.ryou
                exp         = getPlayerExp(user_id)
                level       = getPlayerLevel(user_id)
                e.set_field_at(3, name = "►📦 ── View your inventory ─── 📦 ◄", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Your inventory:", color = default_color)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.set_thumbnail(url = Resource["GAMA-Gacha_TN"][0])
                e.add_field(name = "Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
                e.add_field(name = "Gacha Fragments:", value = f"{Icons['fragment']} x `{'{:,}'.format(fragments)}`", inline = True)
                e.add_field(name = "Total roll count:", value = f"🎲 x `{'{:,}'.format(total_rolls)}`", inline = True)
                # e.add_field(name = f"{coin_name}:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
                # e.add_field(name = "EXP:", value = f"{Icons['exp']} x `{'{:,}'.format(exp)}`", inline = True)
                # e.add_field(name = "Level:", value = f"{Icons['level']} `{'{:,}'.format(level)}`", inline = True)
                e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
                e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                emojis = ["↩️"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                if reaction is None:
                    break
                match str(reaction.emoji):
                    case "↩️":
                        prev_flag = edit_flag = True
                        e.set_field_at(4, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                        await message.edit(embed = e)
                        await message.clear_reactions()
            case "❌":
                e.set_field_at(4, name = "►❌ ─────  Exit  Menu  ─────  ❌ ◄", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                return

# @bot.command(aliases = ["use", "item", "energy", "refill", "recharge"])
# @commands.check(checkChannel)
# async def restore(ctx):
#     ''' | Usage: +restore '''
#     user_id = ctx.author.id
#     energy = getPlayerEnergy(user_id)
#     max_energy = getPlayerMaxEnergy(user_id)
#     product = "Energy Restore"
#     item_quantity = getUserItemQuantity(user_id, product)
#     if not item_quantity is None and item_quantity > 0:
#         e = discord.Embed(title = "Energy Restoration", description = "Will you use 1 Energy Restore to recover your energy?")
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
#         e.add_field(name = "Current Energy", value = f"{Icons['energy']} **{energy}**")
#         e.add_field(name = "Energy after restoring", value = f"{Icons['energy']} **{max_energy}**")
#         message = await ctx.send(embed = e)
#         emojis = ["✅", "❌"]
#         reaction, user = await waitForReaction(ctx, message, e, emojis)
#         if reaction is None:
#             return
#         match str(reaction.emoji):
#             case "✅":
#                 await message.clear_reactions()
#                 ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity - 1, product))
#                 if item_quantity - 1 == 0:
#                     ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(user_id), product))
#                 addPlayerEnergy(user_id, max_energy)
#                 await ctx.send(f"{ctx.author.mention} used 1 **{product}** to fully restore their energy!")
#                 return
#             case "❌":
#                 await message.clear_reactions()
#                 return
#     else:
#         await ctx.send(f"You do not have any **{product}s** to use!")
#         return

# @bot.command(aliases = ["stat", "level", "levelup", "lvl", "lvlup", "allocate"])
# @commands.check(checkChannel)
# async def stats(ctx, target = None):
#     ''' | Usage: +stats [@user] | Check and allocate stat points '''
#
#     def formatPlayerStats(user_id):
#         HP = getPlayerHP(user_id)
#         ATK = getPlayerATK(user_id)
#         DEF = getPlayerDEF(user_id)
#         player_stats = ["", f"{user.name}", f"Total HP: {HP}", f"Total ATK: {ATK}", f"Total DEF: {DEF}", ""]
#         return player_stats
#
#     def formatPlayerPoints(user_id):
#         stat_points = getPlayerStatPoints(user_id)
#         player_points = ["", f"Points: {stat_points['points']}", f"HP Points: {stat_points['hp']}", f"ATK Points: {stat_points['atk']}", f"DEF Points: {stat_points['def']}", ""]
#         return player_points
#
#     # main()
#     if target is None:
#         target = ctx.author.mention
#     if re.match(r"<(@|@&)[0-9]{18,19}>", target):
#         flag = True
#         message = None
#         while flag:
#             user_id         = convertMentionToId(target)
#             user            = await bot.fetch_user(user_id)
#             default_color   = config.default_color
#             exp             = getPlayerExp(user_id)
#             level           = getPlayerLevel(user_id)
#             exp_to_next     = getPlayerExpToNextLevel(user_id)
#             player_stats    = formatPlayerStats(user_id)
#             player_points   = formatPlayerPoints(user_id)
#             stat_points     = getPlayerStatPoints(user_id)
#             points = stat_points["points"]
#             e = discord.Embed(title = "Viewing stats of user:", description = target, color = default_color)
#             e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#             e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
#             e.add_field(name = "Current Level", value = f"{Icons['level']} **{level}**", inline = True)
#             e.add_field(name = "Current EXP", value = f"{Icons['exp']} **{'{:,}'.format(exp)}**", inline = True)
#             e.add_field(name = "EXP to next level", value = f"{Icons['exp']} **{'{:,}'.format(exp_to_next)}**", inline = True)
#             e.add_field(name = "📊 Player Stats:", value = boxifyArray(player_stats, padding = 2), inline = True)
#             e.add_field(name = "🧮 Allocated Stat Points:", value = boxifyArray(player_points, padding = 2), inline = True)
#             e.add_field(name = "\u200b", value = "────────────────────────────────", inline = False)
#             message = await ctx.send(embed = e) if message == None else await message.edit(embed = e)
#             if target == ctx.author.mention and points > 0:
#                 e.add_field(name = f"You have `{points}` unallocated stat points!", value = "Choose a Stat to increment:", inline = True)
#                 e.add_field(name = "│ Stat options:", value = "**│** 🩸 ─ **HP**\n**│** ⚔️ ─ **ATK**\n**│** 🛡️ ─ **DEF**", inline = True)
#                 await message.edit(embed = e)
#                 emojis = ["🩸", "⚔️", "🛡️", Icons["statsreset"], "❌"]
#                 reaction, user = await waitForReaction(ctx, message, e, emojis)
#                 if reaction is None:
#                     return
#                 match str(reaction.emoji):
#                     case "🩸":
#                         await message.clear_reactions()
#                         addPlayerStatPoints(user_id, "hp", 1)
#                         addPlayerStatPoints(user_id, "points", -1)
#                     case "⚔️":
#                         await message.clear_reactions()
#                         addPlayerStatPoints(user_id, "atk", 1)
#                         addPlayerStatPoints(user_id, "points", -1)
#                     case "🛡️":
#                         await message.clear_reactions()
#                         addPlayerStatPoints(user_id, "def", 1)
#                         addPlayerStatPoints(user_id, "points", -1)
#                     case x if x == Icons["statsreset"]:
#                         await message.clear_reactions()
#                         product = "Stats Reset"
#                         item_quantity = getUserItemQuantity(user_id, product)
#                         e.description = "Will you reset your stats?"
#                         e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
#                         e.add_field(name = f"{Icons['statsreset']} Confirmation: Will you reset your stat points?", value = f"(You have `{item_quantity if not item_quantity is None else 0}` Stats Reset uses.)", inline = False) # Field 8
#                         await message.edit(embed = e)
#                         emojis = ["✅", "❌"]
#                         reaction, user = await waitForReaction(ctx, message, e, emojis)
#                         if reaction is None:
#                             return
#                         match str(reaction.emoji):
#                             case "✅":
#                                 await message.clear_reactions()
#                                 if not item_quantity is None and item_quantity > 0:
#                                     StatsDB.execute(f"DELETE FROM userdata WHERE user_id = {user_id}")
#                                     ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity - 1, product))
#                                     if item_quantity - 1 == 0:
#                                         ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(user_id), product))
#                                     e.add_field(name = "✅ Success!", value = "Your points have been successfuly reset.", inline = False) # Field 9
#                                     await message.edit(embed = e)
#                                     time.sleep(4)
#                                     e.remove_field(9)
#                                     e.remove_field(8)
#                                 else:
#                                     e.add_field(name = "❌ Failure!", value = "You don't have any Stats Reset uses, you can buy one from the Market.", inline = False) # Field 9
#                                     await message.edit(embed = e)
#                                     time.sleep(4)
#                                     e.remove_field(8)
#                             case "❌":
#                                 await message.clear_reactions()
#                                 e.remove_field(8)
#                     case "❌":
#                         await message.clear_reactions()
#                         return
#             else:
#                 flag = False
#     else:
#         await ctx.send("Please **@ mention** a valid user to check their stats (+help stats)")

@bot.command(aliases = ["inventory"])
@commands.check(checkChannel)
async def inv(ctx, target = None):
    ''' | Usage: +inv [@user] | Check the inventory of a user '''
    if target is None:
        target = ctx.author.mention
    # Ensure valid discord ID
    if re.match(r"<(@|@&)[0-9]{18,19}>", target):
        user_id         = convertMentionToId(target)
        inv_gacha       = getUserGachaInv(user_id)
        inv_market      = getUserMarketInv(user_id)
        inv_items       = getUserItemInv(user_id)
        playerdata      = getPlayerData(user_id)
        tickets         = inv_gacha.gacha_tickets
        fragments       = inv_gacha.gacha_fragments
        total_rolls     = inv_gacha.total_rolls
        ryou            = inv_market.ryou
        exp             = getPlayerExp(user_id)
        level           = getPlayerLevel(user_id)
        energy          = getPlayerEnergy(user_id)
        total_clears    = len(getPlayerDungeonClears(user_id))
        e = discord.Embed(title = "Viewing inventory of user:", description = target, color = 0xfdd835)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.add_field(name = "Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
        e.add_field(name = "Gacha Fragments:", value = f"{Icons['fragment']} x `{'{:,}'.format(fragments)}`", inline = True)
        e.add_field(name = "Total roll count:", value = f"🎲 x `{'{:,}'.format(total_rolls)}`", inline = True)
        # e.add_field(name = f"{coin_name}:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
        # e.add_field(name = "EXP:", value = f"{Icons['exp']} x `{'{:,}'.format(exp)}`", inline = True)
        # e.add_field(name = "Level:", value = f"{Icons['level']} `{'{:,}'.format(level)}`", inline = True)
        # e.add_field(name = "Energy:", value = f"{Icons['energy']} `{'{:,}'.format(energy)}`", inline = True)
        # e.add_field(name = "Dungeons cleared:", value = f"{Icons['dungeon']} `{'{:,}'.format(total_clears)}`", inline = True)
        for slot, item in enumerate(inv_items):
            border = ""
            for _ in item[0]:
                border += "═"
            e.add_field(name = f"📍 Slot {slot + 1}  ─  (x{item[1]})", value = f"```╔{border}╗\n║{item[0]}║\n╚{border}╝```", inline = False)
        await ctx.send(embed = e)
    else:
        await ctx.send("Please **@ mention** a valid user to check their inventory (+help inv)")

@bot.command()
@commands.check(checkChannel)
async def craft(ctx, amount:str = "1"):
    ''' | Usage: +craft [integer or "all"] | Craft a Gacha Ticket from 4 Gacha Pieces '''
    menu_top        = "┌───────────────────────┐"
    menu_separator  = "├───────────────────────┤"
    menu_bottom     = "└───────────────────────┘"
    user_id = convertMentionToId(ctx.author.mention)
    GachaDB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values ("+str(user_id)+", '0', '0', '0')")
    inventory   = GachaDB.userdata[user_id]
    tickets     = inventory.gacha_tickets
    fragments   = inventory.gacha_fragments
    total_rolls = inventory.total_rolls

    if amount == "all":
        # Calculate maximum number of tickets user can craft with their current fragments
        craft_amount = math.trunc(fragments / 4)
        if craft_amount == 0:
            # Assume user is trying to craft at least 1 ticket
            craft_amount += 1
    else:
        try:
            craft_amount = int(amount)
            if craft_amount == 0:
                raise ValueError
        except ValueError:
            await ctx.send("Please enter a valid amount of tickets to craft! (**integer** or **\"all\"**)")
            return

    e = discord.Embed(title = "Crafting Menu", description = "Turn your Gacha Ticket Fragments into Gacha Tickets!", color = 0x00897b)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
    e.add_field(name = "Conversion Rate:", value = "`🧩 x 4 Pieces  =  🎟️ x 1 Gacha Ticket`", inline = False)
    e.add_field(name = "Your Gacha Fragments:", value = f"🧩 x {fragments} piece(s)", inline = True)
    e.add_field(name = "Tickets to craft:", value = f"🎟️ x {craft_amount} ticket(s)", inline = True)
    e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
    e.add_field(name = "▷ ⚒️  ── Craft Gacha Ticket(s) ──  ⚒️ ◁", value = menu_separator, inline = False)
    e.add_field(name = "▷ ❌ ─────  Exit  Menu  ─────  ❌ ◁", value = menu_bottom, inline = False)
    message = await ctx.send(embed = e)
    emojis = ["⚒️", "❌"]
    reaction, user = await waitForReaction(ctx, message, e, emojis)
    if reaction is None:
        return
    match str(reaction.emoji):
        case "⚒️":
            e.set_field_at(4, name = "►⚒️ ─── Craft Gacha Ticket ─── ⚒️ ◄", value = menu_separator, inline = False)
            await message.edit(embed = e)
            await message.clear_reactions()
            if fragments >= craft_amount * 4:
                e = discord.Embed(title = "Crafting Result", description = f"✅ Successfully crafted {craft_amount} Gacha Ticket(s)!", color = 0x00897b)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.add_field(name = "Used fragments:", value = f"🧩 x {craft_amount * 4}", inline = False)
                e.add_field(name = "You now have this many Gacha Tickets:", value = f"🎟️ x {tickets + craft_amount}", inline = False)
                await ctx.send(embed = e)
                # Add crafted tickets to and subtract used fragments from database
                GachaDB.userdata[user_id] = {"gacha_tickets": tickets + craft_amount, "gacha_fragments": fragments - craft_amount * 4, "total_rolls": total_rolls}
            else:
                e = discord.Embed(title = "Crafting Result", description = "❌ Craft failed!", color = 0x00897b)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.add_field(name = "You have insufficient ticket pieces.", value =  f"Need 🧩 x {craft_amount * 4 - fragments} more!", inline = False)
                await ctx.send(embed = e)
        case "❌":
            e.set_field_at(5, name = "►❌ ─────  Exit  Menu  ─────  ❌ ◄", value = menu_bottom, inline = False)
            await message.edit(embed = e)
            await message.clear_reactions()

@bot.command()
@commands.check(checkChannel)
async def history(ctx, target = None):
    ''' | Usage: +history [@user] | View prize history of a user '''
    if target is None:
        target = ctx.author.mention
    if not checkAdmin(ctx):
        target = ctx.author.mention
    else:
        if not re.match(r"<(@|@&)[0-9]{18,19}>", target):
            await ctx.send("Admin-only: Please **@ mention** a valid user to view prize history of")
            return
    user_id = convertMentionToId(target)
    history = GachaDB.query(f"SELECT * FROM prizehistory WHERE user_id = '{user_id}'")
    history.reverse()
    history_length = len(history)
    e = discord.Embed(title = "View Prize History", description = f"History of {target}", color = 0xd81b60)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
    exit_flag = edit_flag = False
    if history_length == 0:
        e.add_field(name = "User has not rolled any prizes yet!", value = f"Try `{config.prefix}roll` to change that", inline = False)
        await ctx.send(embed = e)
        return
    # Set offset to 0 (page 1) and begin bidirectional page system
    offset = 0
    while not exit_flag:
        counter = 0
        # Iterate through history in groups of 5
        for index, entry in enumerate(history):
            if index < offset:
                # Skipping to next entry until arriving at the proper page/offset
                continue
            prize_id = entry[0]
            prize_user = entry[1]
            prize_date = entry[2]
            prize_tickets = entry[3]
            prize_tier = entry[4]
            prize_capsule = entry[5]
            prize_prize = entry[6]
            match prize_capsule:
                case "blue":
                    circle = "🔵"
                case "green":
                    circle = "🟢"
                case "red":
                    circle = "🔴"
                case "silver":
                    circle = "⚪"
                case "gold":
                    circle = "🟡"
                case "platinum":
                    circle = "🟣"
            e.add_field(name = f"{index + 1}  ─  {circle} {prize_prize}", value = f"Prize ID: `{prize_id}`", inline = False)
            counter += 1
            # Once a full page is assembled, print it
            if counter == 5 or index + 1 == history_length:
                if not edit_flag:
                    message = await ctx.send(embed = e)
                    edit_flag = True
                else:
                    await message.edit(embed = e)
                if index + 1 > 5 and index + 1 < history_length:
                    # Is a middle page
                    emojis = ["⏪", "⏩", "❌"]
                elif index + 1 < history_length:
                    # Is the first page
                    emojis = ["⏩", "❌"]
                elif history_length > 5:
                    # Is the last page
                    emojis = ["⏪", "❌"]
                else:
                    # Is the only page
                    emojis = ["❌"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                if reaction is None:
                    exit_flag = True
                    break
                match str(reaction.emoji):
                    case "⏩":
                        # Tell upcomming re-iteration to skip to the next page's offset
                        offset += 5
                        await message.clear_reactions()
                        e.clear_fields()
                        break
                    case "⏪":
                        # Tell upcomming re-iteration to skip to the previous page's offset
                        offset -= 5
                        await message.clear_reactions()
                        e.clear_fields()
                        break
                    case "❌":
                        exit_flag = True
                        await message.clear_reactions()
                        break

@bot.command(aliases = ["lb", "top", "richest"])
@commands.check(checkChannel)
async def leaderboard(ctx):
    ''' | Usage: +leaderboard | Shows top 10 richest users '''
    default_color   = config.default_color

    def sortSecond(val):
        return val[1]

    marketdata = MarketDB.query("SELECT * from userdata")
    marketdata.sort(key=sortSecond, reverse=True)

    e = discord.Embed(title = f"Top eight {Icons['ryou']} ballers", description = f"Leader: <@{marketdata[0][0]}>", color = default_color)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
    for index, account in enumerate(marketdata):
        if index == 8:
            break
        user_id = account[0]
        ryou = account[1]
        e.add_field(name = f"#{index + 1}  ─  User:", value = f"<@{user_id}>", inline = True)
        e.add_field(name = f"{coin_name}:", value = f"{Icons['ryou']}  ─  `{'{:,}'.format(ryou) if ryou != 0 else 0}`", inline = True)
        e.add_field(name = "\u200b", value = "\u200b", inline = True)
    await ctx.send(embed = e)

### Admin Commands
@bot.command()
@commands.check(checkAdmin)
async def reward(ctx, target: str, item: str, quantity):
    ''' | Usage: +reward <@user> <item> <quantity> | Items: "ticket", "fragment", "ryou", "exp", "energy" '''
    # Ensure valid discord ID
    if re.match(r"<(@|@&)[0-9]{18,19}>", target):
        # Ensure integer
        try:
            quantity    = int(quantity)
            if quantity == 0:
                return
            user_id     = convertMentionToId(target)
            inv_gacha   = getUserGachaInv(user_id)
            inv_market  = getUserMarketInv(user_id)
            inv_items   = getUserItemInv(user_id)
            tickets     = inv_gacha.gacha_tickets
            fragments   = inv_gacha.gacha_fragments
            total_rolls = inv_gacha.total_rolls
            ryou        = inv_market.ryou
            # Add the respective reward on top of what the user already has
            match item:
                case "ticket" | "tickets":
                    GachaDB.userdata[user_id] = {"gacha_tickets": tickets + quantity, "gacha_fragments": fragments, "total_rolls": total_rolls}
                    await ctx.send(f"Rewarded {target} with {Icons['ticket']} `{quantity}` **Gacha Ticket(s)**! User now has a total of `{tickets + quantity}`.")
                case "fragment" | "fragments":
                    GachaDB.userdata[user_id] = {"gacha_tickets": tickets, "gacha_fragments": fragments + quantity, "total_rolls": total_rolls}
                    await ctx.send(f"Rewarded {target} with {Icons['fragment']} `{quantity}` **Gacha Ticket Fragment(s)**! User now has a total of `{fragments + quantity}`.")
                case "ryou" | "coins":
                    MarketDB.userdata[user_id] = {"ryou": ryou + quantity}
                    await ctx.send(f"Rewarded {target} with {Icons['ryou']} `{quantity}` **{coin_name}**! User now has a total of `{ryou + quantity}`.")
                case "exp" | "xp":
                    exp = getPlayerExp(user_id)
                    exp_reward = addPlayerExp(user_id, quantity)
                    await ctx.send(f"Rewarded {target} with {Icons['exp']} `{exp_reward}` **Experience Points**! User now has a total of `{exp + exp_reward}`.")
                case "energy":
                    energy = getPlayerEnergy(user_id)
                    energy_reward = addPlayerEnergy(user_id, quantity)
                    await ctx.send(f"Rewarded {target} with {Icons['energy']} `{energy_reward}` **Energy**! User now has a total of `{energy + energy_reward}`.")
                case x if x in Products:
                    item_quantity = getUserItemQuantity(user_id, x)
                    if item_quantity == None:
                        if quantity < 0:
                            return
                        else:
                            ItemsDB.execute("INSERT INTO user_{} (item, quantity) VALUES ('{}', {})".format(str(user_id), x, quantity))
                    elif item_quantity + quantity > 0:
                        ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity + quantity, x))
                    else:
                        ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(user_id), x))
                        await ctx.send(f"Removed item from {target}: **{x}**")
                        return
                    await ctx.send(f"Rewarded {target} with `{quantity}` of item: **{x}**")
                    if x in config.role_boosts:
                        await addRole(ctx, x)
                case _:
                    await ctx.send(f"Please enter a **valid item** to reward ({config.prefix}help reward)")
        except ValueError:
            await ctx.send(f"Please enter an **integer** of item(s) to reward ({config.prefix}help reward)")
    else:
        await ctx.send(f"Please **@ mention** a valid user to reward ({config.prefix}help reward)")

@bot.command()
@commands.check(checkAdmin)
async def simulate(ctx, tier, n: int = -1, which_mod: int = 0):
    ''' | Usage: +simulate <tier_X> <Simulations> '''
    capsules = ["blue", "green", "red", "silver", "gold", "platinum"]
    outcomes = []
    # Argument checking
    try:
        cold_weights = config.weights[tier]

        # Nullify chances to roll a capsule if its prize array is empty
        for index, category in enumerate(Prizes[tier]["prizes"]):
            if not Prizes[tier]["prizes"][category]:
                cold_weights[index] = 0

        # Rebalance weights to ensure they add up to 100
        cold_weights = rebalanceWeights(cold_weights)

    except KeyError:
        tiers = []
        for key in config.weights:
            tiers.append(f"`{key}`")
        tiers = str(tiers).replace("'", "")
        await ctx.send(f"Tier '`{tier}`' does not exist! Possible values: {tiers}")
        return
    if n == -1:
        await ctx.send("Please provide an amount of simulations to roll.")
        return
    if which_mod != -1:
        if Prizes[tier]["regulated"]:
            # Set and apply the weight mod
            try:
                mod = config.weight_mods[which_mod]
                hot_weights = [cold_weights[0] + mod / 5, cold_weights[1] + mod / 5, cold_weights[2] + mod / 5, cold_weights[3] + mod / 5, cold_weights[4] + mod / 5, cold_weights[5] - mod]
                weights = hot_weights
            except IndexError:
                possible_values = {}
                index = 0
                for item in config.weight_mods:
                    possible_values.update({f"`{index}`": f"*{item}*"})
                    index +=1
                possible_values = str(possible_values).replace("'", "")
                await ctx.send(f"Weight mod `{which_mod}` does not exist! Possible values: {possible_values}")
                return
        else:
            # Use unmodified weights
            weights = cold_weights
    else:
        # Use unmodified weights
        weights = cold_weights
    for _ in range(n):
        # Roll the gacha n times
        outcomes.append(randomWeighted(capsules, weights))
    c = Counter(outcomes)
    e = discord.Embed(title = "Roll simulation", color = 0x3949ab)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
    e.add_field(name = f"│ {Prizes[tier]['symbol']} Tier", value = f"│ {Prizes[tier]['name']}", inline = True)
    e.add_field(name = "│ 🎲 Rolls", value = f"│ {n}x", inline = True)
    e.add_field(name = "│ 🔵 Blue", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ 🟢 Green", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ 🔴 Red", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ ⚪ Silver", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ 🟡 Gold", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ 🟣 Platinum", value = "│  └  0x   ─   0%", inline = False)
    for key in c:
        # Set the results of the simulation accordingly
        match key:
            case "blue":
                e.set_field_at(2, name = f"│ 🔵 Blue - {Prizes[tier]['prizes']['blue']}", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "green":
                e.set_field_at(3, name = f"│ 🟢 Green - {Prizes[tier]['prizes']['green']}", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "red":
                e.set_field_at(4, name = f"│ 🔴 Red - {Prizes[tier]['prizes']['red']}", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "silver":
                e.set_field_at(5, name = f"│ ⚪ Silver - {Prizes[tier]['prizes']['silver']}", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "gold":
                e.set_field_at(6, name = f"│ 🟡 Gold - {Prizes[tier]['prizes']['gold']}", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "platinum":
                e.set_field_at(7, name = f"│ 🟣 Platinum - {Prizes[tier]['prizes']['platinum']}", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
    await ctx.send(embed = e)
    await ctx.send(f"Weights used: `{weights}`")

@bot.command()
@commands.check(checkAdmin)
async def restock(ctx, prize: str, stock: int, max_limit: int = -1, reset: int = -1):
    ''' | Usage: +restock <"Prize name"> <Stock> [Maximum roll limit] [Reset "times_rolled" counter? (-1: Reset, 0: Don't reset, n: Set counter to n) ] '''
    data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{prize}'")
    match reset:
        case -1:
            times_rolled = 0
            reset_option = "Reset counter to 0"
        case 0:
            times_rolled = GachaDB.backstock[prize].times_rolled
            reset_option = "Leave counter unchanged"
        case x if x > 0:
            times_rolled = x
            reset_option = f"Set counter to {x}"
    if max_limit == -1:
        max_limit = stock
    if data:
        e = discord.Embed(title = "Restock Prize Database", description = "Confirm the following:", color = 0xc0ca33)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.add_field(name = f"Stock of '{prize}' will be set to:", value = stock, inline = False)
        e.add_field(name = f"With a maximum limit of:", value = max_limit, inline = False)
        e.add_field(name = "Reset 'Times Rolled' counter:", value = reset_option, inline = False)
        message = await ctx.send(embed = e)
        emojis = ["✅", "❌"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            return
        match str(reaction.emoji):
            case "✅":
                GachaDB.backstock[prize] = {"current_stock": stock, "times_rolled": times_rolled, "max_limit": max_limit}
            case "❌":
                await ctx.send("❌ Aborted")
                return
    else:
        e = discord.Embed(title = "Restock Prize Database", description = "Confirm the following:", color = 0xc0ca33)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.add_field(name = f"Prize '{prize}' Does not exist in database.", value = "Add it now?", inline = False)
        message = await ctx.send(embed = e)
        emojis = ["✅", "❌"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            return
        match str(reaction.emoji):
            case "✅":
                await message.clear_reactions()
                e = discord.Embed(title = "Restock Prize Database", description = "Confirm the following:", color = 0xc0ca33)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.add_field(name = f"Stock of '{prize}' will be set to:", value = stock, inline = False)
                e.add_field(name = f"With a maximum limit of:", value = max_limit, inline = False)
                e.add_field(name = "Reset 'Times Rolled' counter:", value = reset, inline = False)
                await message.edit(embed = e)
                emojis = ["✅", "❌"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                match str(reaction.emoji):
                    case "✅":
                        GachaDB.execute(f"INSERT OR IGNORE INTO backstock (prize, current_stock, times_rolled, max_limit) values ('{prize}', '0', '0', '0')")
                        GachaDB.backstock[prize] = {"current_stock": stock, "times_rolled": times_rolled, "max_limit": max_limit}
                    case "❌":
                        await ctx.send("❌ Aborted")
                        return
            case "❌":
                await ctx.send("❌ Aborted")
                return
    await ctx.send(f"✅ Set stock of **{prize}** to `{stock}` with a maximum roll limit of `{max_limit}`.")

@bot.command(aliases = ["dashboard", "database"])
@commands.check(checkAdmin)
async def db(ctx):
    ''' | Usage: +db | View current statistics of the database '''

    def accumulateEntries(data):
        return len(data)

    userdata = GachaDB.query("SELECT * FROM userdata")
    prizehistory = GachaDB.query("SELECT * FROM prizehistory")
    backstock = GachaDB.backstock[f"1 {branch_name} NFT"]
    total_users = accumulateEntries(userdata)
    total_rolls = accumulateEntries(prizehistory)
    if backstock:
        nft_stock = backstock.current_stock
        nft_rolls = backstock.times_rolled
        nft_limit = backstock.max_limit
    else:
        nft_stock = 0
        nft_rolls = 0
        nft_limit = 0

    e = discord.Embed(title = f"{branch_name} Gacha  ─  Admin Dashboard", description = "Database statistics:", color = 0xe53935)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
    e.add_field(name = "──────────────────────────────────────────", value = "──────────────────────────────────────────", inline = False)
    e.add_field(name = "│ 🤖 Bot version", value = f"│  └  `{bot_version}`", inline = True)
    e.add_field(name = "│ 🧍 Accumulated users", value = f"│  └  `{total_users}`", inline = True)
    e.add_field(name = "│ 🎲 Rolls performed", value = f"│  └  `{total_rolls}`", inline = True)
    e.add_field(name = "│ 🏦 NFTs in stock", value = f"│  └  `{nft_stock}`", inline = True)
    e.add_field(name = "│ 🛡️ NFT roll limit", value = f"│  └  `{nft_limit}`", inline = True)
    e.add_field(name = "│ 🎉 NFT rolls", value = f"│  └  `{nft_rolls}`", inline = True)
    e.add_field(name = "──────────────────────────────────────────", value = "──────────────────────────────────────────", inline = False)
    await ctx.send(embed = e)

@bot.command()
@commands.check(checkAdmin)
async def verify(ctx, prize_id):
    ''' | Usage: +verify | Query all metadata of a Prize ID  '''
    if re.match(r"^[0-9]{23,24}$", prize_id):
        prize_info      = GachaDB.prizehistory[prize_id]
        prize_user      = prize_info.user_id
        prize_date      = prize_info.date
        prize_tickets   = prize_info.tickets_spent
        prize_tier      = prize_info.tier
        prize_capsule   = prize_info.capsule
        prize_prize     = prize_info.prize
        tier_name       = Prizes[prize_tier]["name"]
        tier_symbol     = Prizes[prize_tier]["symbol"]
        match prize_capsule:
            case "blue":
                circle = "🔵"
            case "green":
                circle = "🟢"
            case "red":
                circle = "🔴"
            case "silver":
                circle = "⚪"
            case "gold":
                circle = "🟡"
            case "platinum":
                circle = "🟣"

        e = discord.Embed(title = "Prize Info", description = f"Viewing metadata of prize: `{prize_id}`", color = 0x8e24aa)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.add_field(name = "──────────────────────────────────────────", value = "──────────────────────────────────────────", inline = False)
        e.add_field(name = f"│ 🧍 User", value = f"│  └  <@{prize_user}>", inline = True)
        e.add_field(name = f"│ 📆 Date (UTC)", value = f"│  └  {prize_date}", inline = True)
        e.add_field(name = f"│ 🎟️ Cost", value = f"│  └  {prize_tickets}", inline = True)
        e.add_field(name = f"│ {tier_symbol} Tier", value = f"│  └  {tier_name}", inline = True)
        e.add_field(name = f"│ {circle} Capsule", value = f"│  └  {prize_capsule.capitalize()}", inline = True)
        e.add_field(name = f"│ 🎉 Prize", value = f"│  └  ***{prize_prize}***", inline = True)
        e.add_field(name = "──────────────────────────────────────────", value = "──────────────────────────────────────────", inline = False)
        await ctx.send(embed = e)
    else:
        await ctx.send("Please provide a valid 23/24-digit Prize ID")

@bot.command()
@commands.check(checkAdmin)
async def backstock(ctx):
    ''' | Usage: +backstock | View current backstock of limited prizes '''
    stock = GachaDB.query(f"SELECT * FROM backstock")
    stock_length = len(stock)
    e = discord.Embed(title = "View Backstock", color = 0xe53935)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
    exit_flag = edit_flag = False
    if stock_length == 0:
        await ctx.send("There are no entries to show in backstock!")
        return
    # Set offset to 0 (page 1) and begin bidirectional page system
    offset = 0
    while not exit_flag:
        counter = 0
        # Iterate through stock in groups of 5
        for index, entry in enumerate(stock):
            if index < offset:
                # Skipping to next entry until arriving at the proper page/offset
                continue

            prize = entry[0]
            current_stock = entry[1]
            times_rolled = entry[2]
            max_limit = entry[3]
            e.add_field(name = f"Prize: {prize}", value = f"Stock: `{current_stock}` | Limit: `{max_limit}` | Rolled: `{times_rolled}`", inline = False)
            counter += 1
            # Once a full page is assembled, print it
            if counter == 5 or index + 1 == stock_length:
                if not edit_flag:
                    message = await ctx.send(embed = e)
                    edit_flag = True
                else:
                    await message.edit(embed = e)
                if index + 1 > 5 and index + 1 < stock_length:
                    # Is a middle page
                    emojis = ["⏪", "⏩", "❌"]
                elif index + 1 < stock_length:
                    # Is the first page
                    emojis = ["⏩", "❌"]
                elif stock_length > 5:
                    # Is the last page
                    emojis = ["⏪", "❌"]
                else:
                    # Is the only page
                    emojis = ["❌"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                if reaction is None:
                    exit_flag = True
                    break
                match str(reaction.emoji):
                    case "⏩":
                        # Tell upcomming re-iteration to skip to the next page's offset
                        offset += 5
                        await message.clear_reactions()
                        e.clear_fields()
                        break
                    case "⏪":
                        # Tell upcomming re-iteration to skip to the previous page's offset
                        offset -= 5
                        await message.clear_reactions()
                        e.clear_fields()
                        break
                    case "❌":
                        exit_flag = True
                        await message.clear_reactions()
                        break

@bot.command()
@commands.check(checkAdmin)
async def resetstats(ctx, target = ""):
    if re.match(r"<(@|@&)[0-9]{18,19}>", target):
        user_id = convertMentionToId(target)
        StatsDB.execute(f"DELETE FROM userdata WHERE user_id = {user_id}")
    else:
        await ctx.send("Please **@ mention** a valid user to reset their stats.")

# @bot.command()
# @commands.check(checkAdmin)
# async def leaderboard(ctx):
#     user_id = ctx.author.id
#     msg = []
#     data = GachaDB.query(f"SELECT * FROM userdata")
#     to_sort = {}
#     for entry in data:
#         tickets = entry[1]
#         user = entry[0]
#         to_sort[str(user)] = tickets
#     sorted_dict = sorted(to_sort.items(), key=lambda x: x[1], reverse = True)
#     for counter, entry in enumerate(sorted_dict):
#         if counter > 20:
#             break
#         msg.append(str(entry))
#     await ctx.send(str(msg))

@bot.command()
@commands.is_owner()
async def compensate(ctx):
    data = DungeonsDB.query("SELECT * FROM clears")
    users = []
    for entry in data:
        user_id = entry[1]
        if not user_id in users:
            users.append(user_id)

    for user_id in users:
        # user = await bot.fetch_user(user_id)
        product = "Octopus Nigiri"
        amount = 5
        item_quantity = getUserItemQuantity(user_id, product)
        if item_quantity == None:
            ItemsDB.execute("INSERT INTO {} (item, quantity) VALUES ('{}', {})".format(f"user_{user_id}", product, amount))
        else:
            ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity + amount, product))
        await ctx.send(f"Rewarded <@{user_id}> with **{amount} __{product}__**!")

@bot.command()
@commands.is_owner()
async def dmtest(ctx):
    user = ctx.author
    msg = """
    Hi Adventurer, here is your __Serial Number__ for **War of GAMA**!

    ⛓ `(input code here)`

    ***!Pay Attention!***
    Our system will be sending "Serial Numbers" for you to redeem in game during the CBT!
    ✅ Check our website or Discord for how to use your Serial Number!
    ❌ The team will **not** DM you any links, only __"Serial Number"__!
    ❌ The team will **not** be asking for your private information!

    **Note:**
    *This code was sent to you automatically due to you having the WL or OG role*
    *Any DMs you receive claiming to be us that do not follow the rules above are fake and likely scams!*
    *Thanks for supporting War of GAMA, please enjoy the Beta!*
    """
    await user.send(msg)

@bot.command()
@commands.is_owner()
async def sendcodes(ctx, day: int = 0):

    async def sendCode(user, code, day):
        msg = f"""
        Hi {user.mention}, here is your __Serial Number__ for **War of GAMA**!

        ⛓ **Day {day} Serial Number:** `{code}`

        ***!Pay Attention!***
        Our system will be sending "Serial Numbers" for you to redeem in game during the CBT!
        ✅ Check our website or Discord for how to use your Serial Number!
        ❌ The team will **not** DM you any links, only __"Serial Number"__!
        ❌ The team will **not** be asking for your private information!

        **Note:**
        *This code was sent to you automatically due to you having the WL or OG role, keep it safe.*
        *Any DMs you receive claiming to be us that do not follow the rules above are fake and likely scams!*
        *Thanks for supporting War of GAMA, please enjoy the Beta!*
        """
        await user.send(msg)
        return True

    if not type(day) is int or day < 1 or day > 7:
        await ctx.send("⚠️ Please provide a day (must be a number from 1 to 7)")
        return

    match day:
        case 1:
            codes_column = "Unnamed: 1"
        case 2:
            codes_column = "Unnamed: 4"
        case 3:
            codes_column = "Unnamed: 7"
        case 4:
            codes_column = "Unnamed: 10"
        case 5:
            codes_column = "Unnamed: 13"
        case 6:
            codes_column = "Unnamed: 16"
        case 7:
            codes_column = "Unnamed: 19"
    guild = bot.get_guild(989407410504495154)
    roles = ["VIP WL PASS (Silver)", "o🇬 (500)"]
    wl_id = 993343740565540944
    og_id = 993341080567283752
    staff_announcements = bot.get_channel(989407412094119979)
    public_announcements = bot.get_channel(989407416506548250)
    Codes = pandas.read_excel(r"codes.xlsx", engine = "openpyxl")
    UserCodes = {}
    FailedUsers = {}

    makedirs("output", exist_ok = True)
    message = await public_announcements.send(f"<@&{wl_id}> <@&{og_id}>\n🔄 Starting **Day {day}** __Serial Number__ code distribution...")

    codes_sent = 0
    for member in guild.members:
        code = Codes[codes_column].iloc[2 + codes_sent]
        user_roles = [role.name for role in member.roles]
        if roles[0] in user_roles or roles[1] in user_roles:
            try:
                await sendCode(member, code, day)
                UserCodes.update({member.id: code})
                with open(f"output/day-{day}.json", "w") as outfile:
                    json_object = json.dumps(UserCodes, indent = 4)
                    outfile.write(json_object)
                codes_sent += 1
            except discord.errors.Forbidden:
                FailedUsers.update({member.id: member.mention})
                with open(f"output/day-{day}_failed-users.json", "w") as outfile:
                    json_object = json.dumps(FailedUsers, indent = 4)
                    outfile.write(json_object)
        await message.edit(content = f"<@&{wl_id}> <@&{og_id}>\n🔄 Starting **Day {day}** __Serial Number__ code distribution...\n\n⛓️ Codes sent progress: `{codes_sent}`\n⚠️ Failed users: `{len(FailedUsers)}`")
    if UserCodes:
        await public_announcements.send(content = f"✅ Finished **Day {day}** __Serial Number__ code distribution! *~Check your DMs~*")
        await staff_announcements.send(file = discord.File(f"output/day-{day}.json"), content = f"✅ Finished **Day {day}** Mass-DM code distribution!\nHere is the resulting list of users with the codes rewarded to them respectively:")
    if FailedUsers:
        await staff_announcements.send(file = discord.File(f"output/day-{day}_failed-users.json"), content = "🚫 List of users failed to send a code to:")


@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await bot.close()

# @bot.command()
# @commands.is_owner()
# async def forceconvert(ctx):
#     data = GachaDB.query(f"SELECT * FROM userdata")
#     for entry in data:
#         user_id = entry[0]
#         tickets = entry[1]
#         GachaDB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values (%s, '0', '0', '0')" % str(user_id))
#         MarketDB.execute("INSERT OR IGNORE INTO userdata (user_id, ryou) VALUES (%s, '0')" % str(user_id))
#         ryou = tickets * 10000
#         GachaDB.execute("UPDATE userdata SET gacha_tickets = ? WHERE user_id = ?", (0, user_id))
#         MarketDB.execute("UPDATE userdata SET ryou = ? WHERE user_id = ?", (ryou, user_id))
#         await ctx.send(f"Converted for <@{user_id}> | {tickets} Tickets -> {ryou} Ryou")

bot.run(config.discord_token)
