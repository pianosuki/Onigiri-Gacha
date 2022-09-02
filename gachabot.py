### Gacha Bot for Onigiri
### Created by pianosuki
### https://github.com/pianosuki
### For use by Catheon only
branch_name = "Onigiri"
bot_version = "1.9"
debug_mode  = False

import config, dresource
from database import Database
import discord, re, time, random, json, math, hashlib, urllib.parse
from discord.ext import commands
from datetime import datetime
import numpy as np
from collections import Counter
from os.path import exists as file_exists
from os import makedirs
from functools import reduce

intents                 = discord.Intents.default()
intents.message_content = True
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

# Player Stat Points
StatsDB = Database("playerstats.db")
StatsDB.execute("CREATE TABLE IF NOT EXISTS userdata (user_id INTEGER PRIMARY KEY UNIQUE, points INTEGER, hp INTEGER, atk INTEGER, def INTEGER)")

# User Whitelists
WhitelistDB = Database("whitelists.db")

# Equipment
EquipmentDB = Database("equipment.db")
EquipmentDB.execute("CREATE TABLE IF NOT EXISTS equipment (user_id INTEGER PRIMARY KEY UNIQUE, weapon TEXT, magatama_1 TEXT, magatama_2 TEXT, magatama_3 TEXT, magatama_4 TEXT)")
EquipmentDB.execute("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER PRIMARY KEY UNIQUE, weapons TEXT, magatamas TEXT)")

# Seeds
SeedsDB = Database("seeds.db")
SeedsDB.execute("CREATE TABLE IF NOT EXISTS seeds (id INTEGER PRIMARY KEY, seed TEXT, user_id TEXT, dungeon TEXT, mode INTEGER, note TEXT)")

# Objects
Prizes      = json.load(open("prizes.json")) # Load list of prizes for the gacha to pull from
Products    = json.load(open("products.json")) # Load list of products for shop to sell
Graphics    = json.load(open("graphics.json")) # Load list of graphical assets to build Resource with
Quests      = json.load(open("quests.json")) # Load list of quests for the questing system
Dungeons    = json.load(open("dungeons.json")) # Load list of dungeons for the dungeon system
Tables      = json.load(open("tables.json")) # Load tables for systems to use constants from
Weapons     = json.load(open("weapons.json")) # Load weapons dictionary
Magatamas   = json.load(open("magatamas.json")) # Load magatamas dictionary
Resource    = dresource.resCreate(Graphics) # Generate discord file attachment resource
Icons       = {**config.custom_emojis, **config.mode_emojis, **config.element_emojis, **config.nigiri_emojis, **config.weapon_emojis, **config.magatama_emojis, **config.rarity_emojis}

# Names
coin_name = config.coin_name

@bot.event
async def on_ready():
    # Go Online
    await bot.change_presence(status = discord.Status.online, activity = discord.Game(f"{config.prefix}roll to spin the Gacha!"))
    print(f"Logged in as {bot.user} | Version: {bot_version}")

@bot.event
async def on_message(ctx):
    if ctx.author.bot:
        return
    if ctx.channel.id in config.channels["chat_earn"]:
        user_id = ctx.author.id
        level = getPlayerLevel(user_id)
        ryou_earn_range = config.chat_ryou_earn
        chat_earn_wait = config.chat_earn_wait
        last_chat = getLastChat(user_id)
        now = int(time.time())
        if now >= last_chat:
            marketdata = getUserMarketInv(user_id)
            ryou = marketdata.ryou
            ryou_earned = random.randint(ryou_earn_range[0], ryou_earn_range[1]) * level
            MarketDB.execute("UPDATE userdata SET ryou = ? WHERE user_id = ?", (ryou + ryou_earned, user_id))
            ActivityDB.execute("UPDATE chat SET last_activity = ? WHERE user_id = ?", (now + chat_earn_wait, user_id))
            await ctx.add_reaction(Icons["ryou"])
    await bot.process_commands(ctx)

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

async def waitForReaction(ctx, message, e, emojis, modmsg = True, user_override = None):
    for emoji in emojis:
        await message.add_reaction(emoji)

    def checkReaction(reaction, user):
        if user_override is None:
            return user != bot.user and reaction.message == message and user == ctx.author and str(reaction.emoji) in emojis
        else:
            return user != bot.user and reaction.message == message and user == user_override and str(reaction.emoji) in emojis

    # Wait for user to react
    try:
        reaction, user = await bot.wait_for("reaction_add", check = checkReaction, timeout = 300)
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

def getUserWhitelist(user_id):
    WhitelistDB.execute("CREATE TABLE IF NOT EXISTS user_%s (user_id INTEGER PRIMARY KEY UNIQUE, percent INTEGER)" % str(user_id))
    whitelist = WhitelistDB.query("SELECT * FROM user_%s" % str(user_id))
    return whitelist

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

def getAllDungeonClears():
    dungeon_clears = DungeonsDB.query(f"SELECT * FROM clears")
    return dungeon_clears

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

def getDungeonRecords(dungeon):
    records = DungeonsDB.query(f"SELECT * FROM clears WHERE dungeon = '{dungeon}'")
    return records

def getPlayerExpToNextLevel(user_id):
    ExpTable = Tables["ExpTable"]
    exp = getPlayerExp(user_id)
    level = getPlayerLevel(user_id)
    next_level = ExpTable[level][1]
    exp_to_next = next_level - exp
    return exp_to_next

def getPlayerWeaponsInv(user_id):
    EquipmentDB.execute("INSERT OR IGNORE INTO inventory (user_id, weapons, magatamas) VALUES (%s, 'Oni Dagger', '')" % str(user_id))
    inventory = EquipmentDB.query(f"SELECT weapons FROM inventory WHERE user_id = '{user_id}'")
    return inventory[0][0]

def getPlayerMagatamasInv(user_id):
    EquipmentDB.execute("INSERT OR IGNORE INTO inventory (user_id, weapons, magatamas) VALUES (%s, 'Oni Dagger', '')" % str(user_id))
    inventory = EquipmentDB.query(f"SELECT magatamas FROM inventory WHERE user_id = '{user_id}'")
    return inventory[0][0]

def getPlayerEquipment(user_id):
    EquipmentDB.execute("INSERT OR IGNORE INTO equipment (user_id, weapon, magatama_1, magatama_2, magatama_3, magatama_4) VALUES (%s, 'Oni Dagger', '', '', '', '')" % str(user_id))
    weapon = EquipmentDB.query(f"SELECT weapon FROM equipment WHERE user_id = '{user_id}'")[0][0]
    magatama_1 = EquipmentDB.query(f"SELECT magatama_1 FROM equipment WHERE user_id = '{user_id}'")[0][0]
    magatama_2 = EquipmentDB.query(f"SELECT magatama_2 FROM equipment WHERE user_id = '{user_id}'")[0][0]
    magatama_3 = EquipmentDB.query(f"SELECT magatama_3 FROM equipment WHERE user_id = '{user_id}'")[0][0]
    magatama_4 = EquipmentDB.query(f"SELECT magatama_4 FROM equipment WHERE user_id = '{user_id}'")[0][0]
    equipment = {}
    equipment.update({"weapon": weapon, "magatamas": [magatama_1, magatama_2, magatama_3, magatama_4]})
    return equipment

def equipWeapon(user_id, weapon):
    EquipmentDB.execute("INSERT OR IGNORE INTO equipment (user_id, weapon, magatama_1, magatama_2, magatama_3, magatama_4) VALUES (%s, 'Oni Dagger', '', '', '', '')" % str(user_id))
    EquipmentDB.execute("UPDATE equipment SET weapon = ? WHERE user_id = ?", (weapon, user_id))
    return

def equipMagatama(user_id, magatama, slot):
    EquipmentDB.execute("INSERT OR IGNORE INTO equipment (user_id, weapon, magatama_1, magatama_2, magatama_3, magatama_4) VALUES (%s, 'Oni Dagger', '', '', '', '')" % str(user_id))
    EquipmentDB.execute("UPDATE equipment SET magatama_%s = ? WHERE user_id = ?" % str(slot), (magatama, user_id))
    return

def givePlayerWeapon(user_id, weapon):
    weapons = getPlayerWeaponsInv(user_id)
    weapons = weapons + f", {weapon}" if weapons != "" else weapon
    EquipmentDB.execute("UPDATE inventory SET weapons = ? WHERE user_id = ?", (weapons, user_id))
    return

def givePlayerMagatama(user_id, magatama):
    magatamas = getPlayerMagatamasInv(user_id)
    magatamas = magatamas + f", {magatama}" if magatamas != "" else magatama
    EquipmentDB.execute("UPDATE inventory SET magatamas = ? WHERE user_id = ?", (magatamas, user_id))
    return

def getPlayerChakra(user_id):
    equipment = getPlayerEquipment(user_id)
    chakra = 0
    equipped = equipment["magatamas"]
    magatamas = []
    for magatama in equipped:
        magatamas.append((magatama, Magatamas[magatama]) if magatama != "" else ())
    for slot, magatama in enumerate(magatamas):
        if magatama:
            chakra += magatamas[slot][1]["Chakra"]
    return chakra

def clearPlayerEquipment(user_id):
    EquipmentDB.execute("UPDATE equipment SET magatama_1 = '' WHERE user_id = %s" % str(user_id))
    EquipmentDB.execute("UPDATE equipment SET magatama_2 = '' WHERE user_id = %s" % str(user_id))
    EquipmentDB.execute("UPDATE equipment SET magatama_3 = '' WHERE user_id = %s" % str(user_id))
    EquipmentDB.execute("UPDATE equipment SET magatama_4 = '' WHERE user_id = %s" % str(user_id))
    return

def getPlayerSkillForce(user_id):
    equipment = getPlayerEquipment(user_id)
    sf = 0
    equipped_weap = equipment["weapon"]
    equipped_mags = equipment["magatamas"]
    magatamas = []
    for magatama in equipped_mags:
        magatamas.append((magatama, Magatamas[magatama]) if magatama != "" else ())
    for slot, magatama in enumerate(magatamas):
        if magatama and Magatamas[magatamas[slot][0]]["Type"] == Weapons[equipped_weap]["Type"] and "Skill Force" in Magatamas[magatamas[slot][0]]["Effects"]:
            sf += magatamas[slot][1]["Effects"]["Skill Force"]
    return sf

def getPlayerCriticalRate(user_id):
    equipment = getPlayerEquipment(user_id)
    critical = config.default_critical_rate
    equipped_weap = equipment["weapon"]
    equipped_mags = equipment["magatamas"]
    magatamas = []
    for magatama in equipped_mags:
        magatamas.append((magatama, Magatamas[magatama]) if magatama != "" else ())
    for slot, magatama in enumerate(magatamas):
        if magatama and "Critical" in Magatamas[magatamas[slot][0]]["Effects"]:
            mag_crit = magatamas[slot][1]["Effects"]["Critical"]
            critical = critical + mag_crit if critical + mag_crit <= 100 else 100
    return critical

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
@bot.command(aliases = ["dungeon", "dg", "dung", "run", "warding", "wardings"])
@commands.check(checkChannel)
async def dungeons(ctx, *input):
    ''' | Usage: +dungeons '''
    user_id                 = ctx.author.id
    user_name               = ctx.author.name
    default_color           = config.default_color
    numbers                 = config.numbers
    mode_mapping            = config.mode_mapping
    mode_mapping_inverse    = config.mode_mapping_inverse
    mode_multipliers        = config.mode_multipliers
    mode_divisors           = config.mode_divisors

    class DungeonInstance:

        # Mutable Cache
        class DungeonCache:
            def __init__(self):
                self.floor = 0
                self.room = 0
                self.mobs = 0
                self.goldarumas = 0
                self.chests = 0
                self.mobs_killed = 0
                self.cleared = False
                self.start_time = None
                self.end_time = None
                self.clear_time = None
                self.pool = 0
                self.tax_rate = 50
                self.tax = 0
                self.weapon_rewards = []
                self.magatama_rewards = []

        class PlayerState:
            def __init__(self, user_id, user_name):
                self.id = user_id
                self.name = user_name
                self.HP = getPlayerHP(user_id)
                self.ATK = getPlayerATK(user_id)
                self.DEF = getPlayerDEF(user_id)
                self.level = getPlayerLevel(user_id)
                self.weapon = getPlayerEquipment(user_id)["weapon"]
                self.weapon_atk = Weapons[self.weapon]["Attack"] if self.weapon != "" else 0
                self.magatamas = getPlayerEquipment(user_id)["magatamas"]
                self.magatamas_def = sum([property for property in [Magatamas[magatama]["Defence"] for magatama in self.magatamas if magatama]])

        class YokaiState:
            def __init__(self):
                self.name = ""
                self.HP = 0
                self.ATK = 0
                self.DEF = 0

        class BossState:
            def __init__(self):
                self.name = ""
                self.HP = 0
                self.ATK = 0
                self.DEF = 0
                self.phase = 1

        def __init__(self, dungeon, mode, seed, Party):
            # Immutable
            self.dungeon = dungeon
            self.mode = mode
            self.mode_name = mode_mapping[self.mode]
            self.multiplier = mode_multipliers[self.mode]
            self.properties = Dungeons[dungeon]["Difficulties"][self.mode_name]
            self.icon = getDungeonModes(type = "array")[self.mode]
            self.level = Dungeons[dungeon]["Level_Required"]
            self.floors = Dungeons[dungeon]["Floors"]
            self.rooms = 0 # Accumulated via Blueprint
            self.yokai = Dungeons[dungeon]["Yokai"]
            self.boss = Dungeons[dungeon]["Boss"]
            self.rewards = Dungeons[dungeon]["Rewards"]
            self.energy = getDungeonEnergy(dungeon)[self.mode]
            self.rooms_range = self.properties["rooms_range"] if "rooms_range" in self.properties else config.default_rooms_range
            self.mob_spawnrate = self.properties["mob_spawnrate"] if "mob_spawnrate" in self.properties else config.default_mob_spawnrate
            self.max_population = self.properties["max_population"] if "max_population" in self.properties else config.default_max_population
            self.goldaruma_spawnrate = self.properties["goldaruma_spawnrate"] if "goldaruma_spawnrate" in self.properties else config.default_goldaruma_spawnrate
            self.goldaruma_spawnrate /= 100.
            self.chest_loot = self.properties["chest_loot"] if "chest_loot" in self.properties else config.default_chest_loot
            self.yokai_modulations = config.default_modulations.copy()
            self.yokai_modulations.update(self.properties["yokai_modulations"] if "yokai_modulations" in self.properties else config.default_modulations.copy())
            self.boss_modulations = config.default_modulations.copy()
            self.boss_modulations.update(self.properties["boss_modulations"] if "boss_modulations" in self.properties else config.default_modulations.copy())

            # Seed
            if seed is None:
                self.seed = hashlib.md5(str(random.getrandbits(128)).encode("utf-8")).hexdigest()
            elif re.match("^[a-f0-9]{32}$", seed):
                self.seed = seed
            else:
                self.seed = hashlib.md5(seed.encode("utf-8")).hexdigest()
            self.salt = self.dungeon
            self.pepper = self.mode_name

            # Initialize Cache
            self.Cache = self.DungeonCache()

            # Initialize Agents
            if Party is None:
                self.Player = self.PlayerState(user_id, user_name)
            else:
                self.Player = None
                self.Player1 = self.PlayerState(Party["Player_1"]["ID"], Party["Player_1"]["Name"])
                self.Player2 = self.PlayerState(Party["Player_2"]["ID"], Party["Player_2"]["Name"])
            self.Yokai = self.YokaiState()
            self.Boss = self.BossState()

            # Initialize Dungeon Blueprint
            self.Blueprint = {}
            self.founder = 0

        def clearCache(self):
            self.Cache = self.DungeonCache()

        def dungeonGenesis(self):
            now = datetime.utcnow()
            self.Blueprint.update({"header": {"Dungeon": self.dungeon, "Difficulty": self.mode_name, "Seed": self.seed}, "blueprint": {"floors": []}, "footer": {"Founder": user_id, "Discovered": f"{now} (UTC)"}})
            for _ in range(self.floors):
                floor_schematic = self.renderFloor()
                self.Blueprint["blueprint"]["floors"].append(floor_schematic)

            if file_exists(f"Blueprints/{self.dungeon}/{self.mode_name}/{self.Blueprint['header']['Seed']}.json"):
                temp_blueprint = json.load(open(f"Blueprints/{self.dungeon}/{self.mode_name}/{self.Blueprint['header']['Seed']}.json"))
                self.founder = temp_blueprint["footer"]["Founder"]
            else:
                self.founder = user_id

            return self.Blueprint

        def renderFloor(self):
            floor_schematic = {}
            self.Cache.floor += 1
            seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
            salt = "renderFloor"
            pepper = str(self.Cache.floor)
            f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8") + pepper.encode("utf-8")).hexdigest()
            random.seed(f_seed)
            if self.Cache.floor < self.floors:
                floor_schematic.update({"type": "Floor", "rooms": []})
                rooms = random.randint(self.rooms_range[0], self.rooms_range[1])
                self.rooms += rooms
                for _ in range(rooms):
                    room_schematic = self.renderRoom()
                    floor_schematic["rooms"].append(room_schematic)
            else:
                floor_schematic.update({"type": "Boss", "boss": {}})
                boss_schematic = self.renderBoss()
                floor_schematic["boss"].update(boss_schematic)
            return floor_schematic

        def renderRoom(self):
            room_schematic = {}
            self.Cache.room += 1
            seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
            salt = "renderRoom"
            pepper = str(self.Cache.room)
            f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8") + pepper.encode("utf-8")).hexdigest()
            random.seed(f_seed)
            population = random.randint(self.mob_spawnrate[0], self.mob_spawnrate[1])
            population = population if population <= self.max_population else self.max_population
            mobs = self.spawnMobs(population)
            if mobs:
                room_schematic.update({"type": "Normal", "yokai": []})
                room_schematic["yokai"] = mobs
            else:
                self.Cache.chests += 1
                chest = self.spawnChest()
                room_schematic.update({"type": "Chest", "loot": []})
                room_schematic["loot"] = chest
            return room_schematic

        def renderBoss(self):
            boss_schematic = {}
            seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
            salt = "renderBoss"
            f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8")).hexdigest()
            random.seed(f_seed)
            boss_schematic.update(Dungeons[self.dungeon]["Boss"])
            if type(Dungeons[self.dungeon]["Boss"]["Name"]) is list:
                boss_schematic.update({"Name": random.choice(Dungeons[self.dungeon]["Boss"]["Name"])})
            base_hp = Dungeons[self.dungeon]["Boss"]["HP"]
            scaled_hp = math.floor((base_hp * 0.75) + (base_hp / 4 * self.multiplier))
            boss_schematic.update({"HP": scaled_hp})
            return boss_schematic

        def spawnMobs(self, population):
            seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
            salt = "spawnMobs"
            pepper = str(self.Cache.room)
            f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8") + pepper.encode("utf-8")).hexdigest()
            random.seed(f_seed)
            mobs = []
            if population > 0:
                for _ in range(population):
                    self.Cache.mobs += 1
                    if random.random() <= self.goldaruma_spawnrate:
                        is_goldaruma = True
                        self.Cache.goldarumas += 1
                    else:
                        is_goldaruma = False
                    mobs.append(random.choice(self.yokai) if not is_goldaruma else "Gold Daruma")
            else:
                pass
            return mobs

        def spawnChest(self):
            seed = hashlib.md5(self.seed.encode("utf-8") + self.salt.encode("utf-8") + self.pepper.encode("utf-8")).hexdigest()
            salt = "spawnChest"
            pepper = str(self.Cache.room)
            f_seed = hashlib.md5(seed.encode("utf-8") + salt.encode("utf-8") + pepper.encode("utf-8")).hexdigest()
            random.seed(f_seed)
            loot_pools = []
            loot_weights = []
            for table in self.chest_loot:
                pool = table["pool"]
                weight = table["rate"]
                loot_pools.append(pool)
                loot_weights.append(weight)
            if sum(loot_weights) < 100 or sum(loot_weights) > 100:
                loot_weights = rebalanceWeights(loot_weights)
            random_pool = randomWeighted(loot_pools, loot_weights)
            chest = {}
            for key, value in random_pool.items():
                loot_name = key
                range = value
                amount_pulled = random.randint(range[0], range[1])
                if not loot_name in chest:
                    chest.update({loot_name: amount_pulled})
                else:
                    chest.update({loot_name: chest[loot_name] + amount_pulled})
            return chest

    async def menuDungeons(ctx, message):
        dungeons_length = len(Dungeons)
        level = getPlayerLevel(user_id)
        banner = generateFileObject("Oni-Dungeons", Graphics["Banners"]["Oni-Dungeons"][0])
        e = discord.Embed(title = "⛩️  ─  Dungeon Listing  ─  ⛩️", description = f"Which dungeon will you be running today?\n**Your level:** {Icons['level']}**{level}**", color = 0x9575cd)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])

        # unlocked_dungeons = []
        # for dungeon in Dungeons:
        #     if level >= dungeon_level:
        #         unlocked_dungeons.append(dungeon)
        #
        # unlocked_length = len(unlocked_dungeons)

        # Set offset to 0 (page 1) and begin bidirectional page system
        offset = 0
        flag = True
        while flag:
            counter = 0
            # Iterate through dungeons in groups of 10
            for index, dungeon in enumerate(Dungeons):
                if index < offset:
                    # Skipping to next entry until arriving at the proper page/offset
                    continue
                dungeon_level = Dungeons[dungeon]["Level_Required"]
                dungeon_emoji = numbers[counter]
                unlocked_emoji = "🔓" if level >= dungeon_level else "🔒"
                crossout = "~~" if not level >= dungeon_level else ""
                bold_or_italics = "**" if not level >= dungeon_level else "*"
                e.add_field(name = f"{dungeon_emoji}  ─  __{crossout}{dungeon}{crossout}__", value = f"{unlocked_emoji}  **─**  {bold_or_italics}Level Required:{bold_or_italics} {Icons['level']}**{dungeon_level}**\n`{config.prefix}dungeon {dungeon}`", inline = True)
                if not counter % 2 == 0:
                    e.add_field(name = "\u200b", value = "\u200b", inline = True)
                counter += 1
                # Once a full page is assembled, print it
                if counter == 10 or index + 1 == dungeons_length:
                    message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
                    if index + 1 > 10 and index + 1 < dungeons_length:
                        # Is a middle page
                        emojis = ["⏪", "⏩", "❌"]
                    elif index + 1 < dungeons_length:
                        # Is the first page
                        emojis = ["⏪", "⏩", "❌"]
                    elif dungeons_length > 10:
                        # Is the last page
                        emojis = ["⏪", "❌"]
                    else:
                        # Is the only page
                        emojis = ["❌"]
                    reaction, user = await waitForReaction(ctx, message, e, emojis)
                    if reaction is None:
                        flag = False
                        break
                    match str(reaction.emoji):
                        case "⏩":
                            # Tell upcomming re-iteration to skip to the next page's offset
                            offset += 10
                            await message.clear_reactions()
                            e.clear_fields()
                            break
                        case "⏪":
                            # Tell upcomming re-iteration to skip to the previous page's offset
                            if offset >= 10:
                                offset -= 10
                            else:
                                # Skip to the last page
                                offset = dungeons_length - (10 - (math.floor(dungeons_length / 10)))
                            await message.clear_reactions()
                            e.clear_fields()
                            break
                        case "❌":
                            await message.clear_reactions()
                            flag = False
                            break

    async def selectDungeon(ctx, message, dungeon, mode, seed, Party):
        banner = generateFileObject("Oni-Dungeons", Graphics["Banners"]["Oni-Dungeons"][0])
        flag = True
        while flag:
            if mode == -1:
                dungeon_level   = Dungeons[dungeon]["Level_Required"]
                dungeon_floors  = Dungeons[dungeon]["Floors"]
                dungeon_yokai   = Dungeons[dungeon]["Yokai"]
                dungeon_energy  = getDungeonEnergy(dungeon)
                e = discord.Embed(title = f"⛩️  ─  __{dungeon}__  ─  ⛩️", description = "Which difficulty will you enter this dungeon on?", color = 0x9575cd)
                if not Party is None: e.description = f"Which difficulty will you enter this dungeon on?\n**Party: <@{Party['Player_1']['ID']}>, <@{Party['Player_2']['ID']}>**"
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
                e.add_field(name = "Level required", value = f"{Icons['level']}**{dungeon_level}**", inline = True)
                if Party is None:
                    e.add_field(name = "Energy cost", value = f"{Icons['energy']}**{dungeon_energy[0]} - {dungeon_energy[3]}**", inline = True)
                else:
                    e.add_field(name = "Energy cost", value = f"{Icons['energy']}**{math.floor(dungeon_energy[0] / 2)} - {math.floor(dungeon_energy[3] / 2)}**", inline = True)
                e.add_field(name = "Floors", value = f"{Icons['dungeon']}**{dungeon_floors}**", inline = True)
                e.add_field(name = "Yokai found here:", value = boxifyArray(dungeon_yokai), inline = True)
                e.add_field(name = "Difficulty selection:\n────────────", value = getDungeonModes(), inline = True)
                e.add_field(name = "Seed initializer:", value = (f"`{seed}`" if not seed is None else "*Randomized*"), inline = False)
                message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
                emojis = getDungeonModes(type = "array")
                emojis.append("❌")
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                if reaction is None:
                    break
                match str(reaction.emoji):
                    case x if x == Icons["normal"]:
                        mode = 0
                    case x if x == Icons['hard']:
                        mode = 1
                    case x if x == Icons['hell']:
                        mode = 2
                    case x if x == Icons['oni']:
                        mode = 3
                    case "❌":
                        await message.clear_reactions()
                        break
                await message.clear_reactions()
            message, flag, mode = await confirmDungeon(ctx, message, flag, dungeon, mode, seed, banner, Party)
        return

    async def confirmDungeon(ctx, message, flag, dungeon, mode, seed, banner, Party):
        try:
            dg = DungeonInstance(dungeon, mode, seed, Party)
            e = discord.Embed(title = f"{dg.icon}  ─  __{dg.dungeon}__  ─  {dg.icon}", description = f"Enter this dungeon on *__{mode_mapping[mode]}__* mode?", color = 0x9575cd)
            if not Party is None: e.description = f"Enter this dungeon on *__{mode_mapping[mode]}__* mode?\n**Party: <@{Party['Player_1']['ID']}>, <@{Party['Player_2']['ID']}>**"
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            # e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
            e.add_field(name = "Level required", value = f"{Icons['level']} **{dg.level}**", inline = True)
            if Party is None:
                e.add_field(name = "Energy cost", value = f"{Icons['energy']} **{dg.energy}**", inline = True)
            else:
                e.add_field(name = "Energy cost", value = f"{Icons['energy']} **{math.floor(dg.energy / 2)}**", inline = True)
            e.add_field(name = "Floors", value = f"{Icons['dungeon']} **{dg.floors}**", inline = True)
            e.add_field(name = "Your level", value = f"{Icons['level']} **{getPlayerLevel(user_id)}**", inline = True)
            e.add_field(name = "Your energy", value = f"{Icons['energy']} **{getPlayerEnergy(user_id)}**", inline = True)
            e.add_field(name = "Best time", value = f"⏱️ __{getPlayerDungeonRecord(user_id, dungeon, mode)}__", inline = True)
            e.add_field(name = "Boss stats:", value = formatBossStats(dg.boss, dg.mode), inline = True)
            e.add_field(name = "Rewards:", value = formatDungeonRewards(ctx, dg.rewards, dg.mode), inline = True)
            e.add_field(name = "Instance seed:", value = (f"`{dg.seed}`" if not seed is None else "*Randomized*"), inline = False)
            message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
            emojis = [Icons["door_open"], "🎁", "↩️"]
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                flag = False
                return message, flag, mode
            match str(reaction.emoji):
                case x if x == Icons["door_open"]:
                    await message.clear_reactions()
                    if Party is None:
                        if dg.Player.level >= dg.level:
                            energy = getPlayerEnergy(user_id)
                            if energy >= dg.energy:
                                addPlayerEnergy(user_id, -dg.energy)
                                message, flag = await dungeonEntry(ctx, message, flag, dg, seed, Party)
                                flag = False
                            else:
                                await ctx.send(f"⚠️ **You don't have enough energy to enter this dungeon!** You need `{dg.energy - energy}` more.")
                        else:
                            await ctx.send(f"⚠️ **You are not high enough level to access __{dungeon}__!** Need `{dg.level - dg.Player.level}` more levels!")
                            flag = False
                    else:
                        if dg.Player1.level >= dg.level and dg.Player2.level >= dg.level:
                            energy_1 = getPlayerEnergy(Party["Player_1"]["ID"])
                            energy_2 = getPlayerEnergy(Party["Player_2"]["ID"])
                            if energy_1 >= math.floor(dg.energy / 2) and energy_2 >= math.floor(dg.energy / 2):
                                addPlayerEnergy(Party["Player_1"]["ID"], - math.floor(dg.energy / 2))
                                addPlayerEnergy(Party["Player_2"]["ID"], - math.floor(dg.energy / 2))
                                message, flag = await dungeonEntry(ctx, message, flag, dg, seed, Party)
                                flag = False
                            else:
                                await ctx.send(f"⚠️ **You don't have enough energy to enter this dungeon!** You need `{dg.energy - min(energy_1, energy_2)}` more.")
                        else:
                            await ctx.send(f"⚠️ **You are not high enough level to access __{dungeon}__!** Need `{dg.level - min(dg.Player1.level, dg.Player2.level)}` more levels!")
                            flag = False
                case "🎁":
                    await message.clear_reactions()
                    e = discord.Embed(title = f"{dg.icon}  ─  __{dg.dungeon}__  ─  {dg.icon}", description = f"Extended dungeon rewards list for mode: __{dg.mode_name}__", color = 0x9575cd)
                    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                    # e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
                    e.add_field(name = "⚔️ ─ Weapons Pool ─ ⚔️", value = formatWeaponRewards(dg.rewards, dg.multiplier), inline = True)
                    e.add_field(name = f"{Icons['magatama']} ─ Magatamas Pool ─ {Icons['magatama']}", value = formatMagatamaRewards(dg.rewards, dg.multiplier), inline = True)

                    d = e.to_dict()

                    if len(d["fields"][0]["value"]) > 1024:
                        weapons_list = formatWeaponRewards(dg.rewards, dg.multiplier).split("\n")
                        weapons_1 = ""
                        weapons_2 = ""
                        for index, line in enumerate(weapons_list):
                            if index <= math.floor(len(weapons_list) / 2):
                                weapons_1 += line + "\n"
                            else:
                                weapons_2 += line + "\n"
                        e.set_field_at(0, name = "⚔️ ─ Weapons Pool ─ ⚔️", value = weapons_1, inline = True)
                        e.add_field(name = "⚔️ ─ Weapons Pool ─ ⚔️", value = weapons_2, inline = False)

                    if len(d["fields"][1]["value"]) > 1024:
                        magatamas_list = formatMagatamaRewards(dg.rewards, dg.multiplier).split("\n")
                        magatamas_1 = ""
                        magatamas_2 = ""
                        for index, line in enumerate(magatamas_list):
                            if index <= math.floor(len(magatamas_list) / 2):
                                magatamas_1 += line + "\n"
                            else:
                                magatamas_2 += line + "\n"
                        e.set_field_at(1, name = f"{Icons['magatama']} ─ Magatamas Pool ─ {Icons['magatama']}", value = magatamas_1, inline = True)
                        e.add_field(name = f"{Icons['magatama']} ─ Magatamas Pool ─ {Icons['magatama']}", value = magatamas_2, inline = False)

                    # if len(d["fields"][1]["value"]) > 1024:
                    #     magatamas_list = formatMagatamaRewards(dg.rewards, dg.multiplier).split("\n")
                    #     magatamas_1 = ""
                    #     magagatams_2 = ""
                    #     for index, line in enumerate(magatamas_list):
                    #         if index <= math.floor(len(magatamas_list) / 2):
                    #             magatamas_1 += line + "\n"
                    #         else:
                    #             magagatams_2 += line + "\n"
                    #     e.set_field_at(1, name = f"{Icons['magatama']} ─ Magatamas Pool ─ {Icons['magatama']}", value = magatamas_1, inline = True)
                    #     e.add_field(name = f"{Icons['magatama']} ─ Magatamas Pool ─ {Icons['magatama']}", value = magagatams_2, inline = True)

                    await message.edit(embed = e)
                    emojis = ["↩️"]
                    reaction, user = await waitForReaction(ctx, message, e, emojis)
                    if reaction is None:
                        flag = False
                        return message, flag, mode
                    match str(reaction.emoji):
                        case "↩️":
                            await message.clear_reactions()
                case "↩️":
                    await message.clear_reactions()
                    mode = -1
        except IndexError:
            await ctx.send(f"⚠️ **Invalid difficulty mode specified:** Dungeon `{dungeon}` has no mode `{mode}`")
            flag = False
        del dg
        return message, flag, mode

    async def dungeonEntry(ctx, message, flag, dg, seed, Party):
        Blueprint = dg.dungeonGenesis()
        dg.clearCache()
        random.seed(None)
        if not Party is None:
            dg.Player = dg.Player1
            Party.update({"Current": 1})
        ### START TIMER ###
        dg.Cache.start_time = datetime.utcnow()
        ###################
        e = discord.Embed(title = f"{dg.icon}  ─  __{dg.dungeon}__  ─  {dg.icon}", color = 0x9575cd)
        if Party is None:
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        else:
            e.description = f"**Party: <@{Party['Player_1']['ID']}>, <@{Party['Player_2']['ID']}>**"
            e.set_author(name = Party[f"Player_{Party['Current']}"]["Name"], icon_url = Party[f"Player_{Party['Current']}"]["Member"].display_avatar)
        e.add_field(name = "Floor", value = "Placeholder", inline = True) # Field 0
        e.add_field(name = "Room", value = "Placeholder", inline = True) # Field 1
        e.add_field(name = "Contents", value = "Placeholder", inline = True) # Field 2
        for floor in Blueprint["blueprint"]["floors"]:
            dg.Cache.floor += 1
            e.set_field_at(0, name = "Current Floor", value = f"{Icons['dungeon']} **{dg.Cache.floor} / {dg.floors}**")
            if floor["type"] == "Floor":
                for index, room in enumerate(floor["rooms"]):
                    dg.Cache.room += 1
                    e.set_field_at(1, name = "Current Room", value = f"🎬 **{index + 1} / {len(floor['rooms'])}**")
                    if room["type"] == "Normal":
                        mobs = room["yokai"]
                        population = len(mobs)
                        for index, mob in enumerate(mobs):
                            e.set_field_at(2, name = "Yokai", value = f"{Icons['yokai']} **{index + 1} / {population}**")
                            message, flag = await fightMob(ctx, message, flag, dg, mob, e, Party)
                            if not flag:
                                return message, flag
                    elif room["type"] == "Chest":
                        e.set_field_at(2, name = "Chests", value = f"{Icons['chest']} **1 / 1**")
                        chest = room["loot"]
                        message, flag = await openChest(ctx, message, flag, dg, chest, e, Party)
                        if not flag:
                            return message, flag
            elif floor["type"] == "Boss":
                e.set_field_at(1, name = "Current Room", value = f"👹 ***Boss Room***")
                e.set_field_at(2, name = "Boss HP", value = f"🩸 **{'{:,}'.format(floor['boss']['HP'])} / {'{:,}'.format(floor['boss']['HP'])}**")
                boss = floor["boss"]
                message, flag, clear_rewards = await fightBoss(ctx, message, flag, dg, boss, e, Party)
                if not flag:
                    return message, flag
        # Exit
        if dg.Cache.cleared:
            ### END TIMER ###
            dg.Cache.end_time = datetime.utcnow()
            #################
            dg.Cache.clear_time = str(dg.Cache.end_time - dg.Cache.start_time)
            dg.Blueprint["footer"].update({"Discovered": f"{dg.Cache.end_time} (UTC)"})
            addPlayerDungeonClear(user_id, dg)
            context = await bot.get_context(message)
            file, founder = writeBlueprint(dg.Blueprint, dg.dungeon, dg.mode_name)
            congrats = ""
            if Party is None:
                congrats += f"🎊 {ctx.author.mention} Congratulations on clearing __**{dg.dungeon}**__ on __*{dg.mode_name}*__ mode!\n"
            else:
                congrats += f"🎊 {'💀' if not Party['Player_1']['Alive'] else ''}{Party['Player_1']['Member'].mention} & {'💀' if not Party['Player_2']['Alive'] else ''}{Party['Player_2']['Member'].mention} Congratulations on clearing __**{dg.dungeon}**__ on __*{dg.mode_name}*__ mode!\n"
            if clear_rewards:
                congrats += f"🎁 You were rewarded with {Icons['ryou']} **{'{:,}'.format(clear_rewards['ryou'])} Ryou**, and {Icons['exp']} **{'{:,}'.format(clear_rewards['exp'])} EXP!**\n"
                if dg.Cache.pool > 0:
                    if dg.founder != user_id:
                        congrats += f"💰 Dungeon pool came out to a total of {Icons['ryou']} **{'{:,}'.format(dg.Cache.pool)} Ryou!**\n"
                        congrats += f"💸 Paid tax ({dg.Cache.tax_rate}%) of {Icons['ryou']} **{'{:,}'.format(dg.Cache.tax)} Ryou** from pool to seed founder: <@{dg.founder}>\n"
                    else:
                        congrats += f"💰 Dungeon pool came out to a total of {Icons['ryou']} **{'{:,}'.format(dg.Cache.pool)} Ryou!**\n"
            congrats += f"⏱️ Your clear time was: `{dg.Cache.clear_time}`\n\n"
            if dg.Cache.weapon_rewards:
                weapons_string = ""
                for index, weapon in enumerate(dg.Cache.weapon_rewards):
                    weapons_string += f" └──  {Icons[Weapons[weapon]['Type'].lower().replace(' ', '_')]} __*{weapon}*__ {Icons['rarity_' + Weapons[weapon]['Rarity'].lower()]}\n"
                congrats += f"⚔️ Found the following weapon(s):\n{weapons_string}\n"
            if dg.Cache.magatama_rewards:
                magatamas_string = ""
                for index, magatama in enumerate(dg.Cache.magatama_rewards):
                    magatamas_string += f" └──  {Icons['magatama_' + Magatamas[magatama]['Type'].lower().replace(' ', '_')]} __*{magatama}*__\n"
                congrats += f"{Icons['magatama']} Found the following magatama(s):\n{magatamas_string}\n"
            if founder:
                congrats += f"🔍 You are the first player to discover the seed `{seed if not seed is None else dg.seed}` for this mode!\n"
                congrats += "Here is a blueprint of the unique dungeon properties you discovered with that seed:"
            else:
                congrats += f"The seed `{seed if not seed is None else dg.seed}` was already discovered for this mode.\n"
                congrats += f"So here is the blueprint the original founder generated:"
            await context.reply(file = file, content = congrats)
        return message, flag

    async def deathScreen(message, e, condition):
        e.add_field(name = "💀  ─  You have died!  ─  💀", value = f"Cause of death: __{condition}__")
        e.description = "Player failed to clear the dungeon."
        message = await message.edit(embed = e)
        return message

    async def consumeNigiri(message, flag, e, console, turn, atk_gauge, def_gauge, dg, printToConsole, Party):
        result = False

        def formatConsumables(consumables, user_items):
            avail_consumables = ""
            for key, value in consumables.items():
                if key in user_items:
                    avail_consumables += f"{Icons[key.lower().replace(' ', '_')]} **{key}**: +{value}HP\n"
            return avail_consumables if not avail_consumables == "" else "None"

        consumables = config.consumables
        user_items = []
        if Party is None:
            inventory = getUserItemInv(user_id)
        else:
            inventory = getUserItemInv(Party[f"Player_{Party['Current']}"]["ID"])
        for item in inventory:
            user_items.append(item[0])
        avail_consumables = []
        for key in list(consumables.keys()):
            if key in user_items:
                avail_consumables.append(Icons[key.lower().replace(' ', '_')])
        e.add_field(name = "Consumables Menu:", value = formatConsumables(consumables, user_items), inline = False) # Field 9
        await message.edit(embed = e)
        emojis = []
        for nigiri_emoji in avail_consumables:
            emojis.append(nigiri_emoji)
        emojis.append("↩️")
        if Party is None:
            reaction, user = await waitForReaction(ctx, message, e, emojis)
        else:
            reaction, user = await waitForReaction(ctx, message, e, emojis, user_override = Party[f"Player_{Party['Current']}"]["Member"])
        if reaction is None:
            flag = False
        else:
            product = ""
            match str(reaction.emoji):
                case x if x == Icons["tuna_nigiri"]:
                    await message.clear_reactions()
                    product = "Tuna Nigiri"
                case x if x == Icons["salmon_nigiri"]:
                    await message.clear_reactions()
                    product = "Salmon Nigiri"
                case x if x == Icons["anago_nigiri"]:
                    await message.clear_reactions()
                    product = "Anago Nigiri"
                case x if x == Icons["squid_nigiri"]:
                    await message.clear_reactions()
                    product = "Squid Nigiri"
                case x if x == Icons["octopus_nigiri"]:
                    await message.clear_reactions()
                    product = "Octopus Nigiri"
                case x if x == Icons["ootoro_nigiri"]:
                    await message.clear_reactions()
                    product = "Ootoro Nigiri"
                case x if x == Icons["kinmedai_nigiri"]:
                    await message.clear_reactions()
                    product = "Kinmedai Nigiri"
                case x if x == Icons["crab_nigiri"]:
                    await message.clear_reactions()
                    product = "Crab Nigiri"
                case x if x == Icons["lobster_nigiri"]:
                    await message.clear_reactions()
                    product = "Lobster Nigiri"
                case x if x == Icons["shachihoko_nigiri"]:
                    await message.clear_reactions()
                    product = "Shachihoko Nigiri"
                case x if x == Icons["shenlong_nigiri"]:
                    await message.clear_reactions()
                    product = "Shenlong Nigiri"
                case "↩️":
                    await message.clear_reactions()
                    e.remove_field(9)
                    await message.edit(embed = e)
                    return message, flag, result
            if product in user_items:
                heal = consumables[product]
                if Party is None:
                    item_quantity = getUserItemQuantity(user_id, product)
                    ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity - 1, product))
                    if item_quantity - 1 == 0:
                        ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(user_id), product))
                    base_player_hp = getPlayerHP(user_id)
                else:
                    item_quantity = getUserItemQuantity(Party[f"Player_{Party['Current']}"]["ID"], product)
                    ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(Party[f"Player_{Party['Current']}"]["ID"]), item_quantity - 1, product))
                    if item_quantity - 1 == 0:
                        ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(Party[f"Player_{Party['Current']}"]["ID"]), product))
                    base_player_hp = getPlayerHP(Party[f"Player_{Party['Current']}"]["ID"])
                heal_amount = heal if not dg.Player.HP + heal > base_player_hp else base_player_hp - dg.Player.HP
                dg.Player.HP = dg.Player.HP + heal if not dg.Player.HP + heal > base_player_hp else base_player_hp
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You ate some tasty {product}!")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(healed for {'{:,}'.format(heal_amount)})")
                result = True
        e.remove_field(9)
        await message.edit(embed = e)
        return message, flag, result

    async def exitDungeon(message, flag, e, field, Party):
        result = False
        e.add_field(name = "Exit Dungeon?", value = "✅  /  ❌", inline = False)
        await message.edit(embed = e)
        emojis = ["✅", "❌"]
        if Party is None:
            reaction, user = await waitForReaction(ctx, message, e, emojis)
        else:
            reaction, user = await waitForReaction(ctx, message, e, emojis, user_override = Party[f"Player_{Party['Current']}"]["Member"])
        if reaction is None:
            flag = False
        else:
            match str(reaction.emoji):
                case "✅":
                    await message.clear_reactions()
                    result = True
                    flag = False
                case "❌":
                    await message.clear_reactions()
        e.remove_field(field)
        await message.edit(embed = e)
        return message, flag, result

    async def fightMob(ctx, message, flag, dg, mob, e, Party):

        async def updateEmbed(e, yokai_state, player_state, console, turn, atk_gauge, def_gauge):
            if Party is None:
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            else:
                e.set_author(name = Party[f"Player_{Party['Current']}"]["Name"], icon_url = Party[f"Player_{Party['Current']}"]["Member"].display_avatar)
            e.set_field_at(3, name = "Turn:", value = f"#️⃣ **{turn}**")
            e.set_field_at(4, name = "ATK Ougi Gauge:", value = f"{Icons['supercharge']} **{atk_gauge} / 5**")
            e.set_field_at(5, name = "DEF Ougi Gauge:", value = f"{Icons['evade']} **{def_gauge} / 5**")
            e.set_field_at(6, name = "Yokai stats:", value = boxifyArray(yokai_state, padding = 2))
            e.set_field_at(7, name = "Player stats:", value = boxifyArray(player_state, padding = 2))
            e.set_field_at(8, name = "Console:", value = boxifyArray(console[-7:], padding = 2, min_width = 33), inline = False)

        def updateAgents():
            yokai_state = ["", f"{dg.Yokai.name}", "", f"Yokai HP: {'{:,}'.format(dg.Yokai.HP)}", f"Yokai ATK: {'{:,}'.format(dg.Yokai.ATK)}", f"Yokai DEF: {'{:,}'.format(dg.Yokai.DEF)}", ""]
            player_state = ["", f"{dg.Player.name}", f"Level: {dg.Player.level}", f"⚔ {dg.Player.weapon} ⚔", "", f"Player HP: {'{:,}'.format(dg.Player.HP)}", f"Player ATK: {'{:,}'.format(dg.Player.ATK)}", f"Player DEF: {'{:,}'.format(dg.Player.DEF)}", ""]
            return yokai_state, player_state

        async def printToConsole(message, e, console, turn, atk_gauge, def_gauge, input):
            time.sleep(0.2)
            console.append(str(input))
            yokai_state, player_state = updateAgents()
            await updateEmbed(e, yokai_state, player_state, console, turn, atk_gauge, def_gauge)
            await message.edit(embed = e)
            return message

        async def loadYokaiEncounter(message, e, mob):
            e.add_field(name = "Yokai Encountered!", value = f"Name: __{mob}__", inline = True) # Field 3
            e.set_image(url = Resource[f"{mob}-1"][0].replace(" ", "%20"))
            e.description = "🔄 **Loading Combat Engine** 🔄"
            await message.edit(embed = e)
            time.sleep(0.5)
            e.description = "🔄 **Loading Combat Engine** 🔄 ▫️"
            await message.edit(embed = e)
            time.sleep(0.5)
            e.description = "🔄 **Loading Combat Engine** 🔄 ▫️ ▫️"
            await message.edit(embed = e)
            time.sleep(0.5)
            e.description = "🔄 **Loading Combat Engine** 🔄 ▫️ ▫️ ▫️"
            await message.edit(embed = e)
            time.sleep(0.5)
            e.remove_field(3)
            if Party is None:
                e.description = None
            else:
                e.description = f"**Party: <@{Party['Player_1']['ID']}>, <@{Party['Player_2']['ID']}>**"
            e.set_image(url = None)
            return message

        async def playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = False):
            damage, is_critical = damageCalculator(dg.Player, dg.Yokai, Party)
            if is_supercharging:
                damage *= 2
            dg.Yokai.HP = dg.Yokai.HP - damage if not dg.Yokai.HP - damage < 0 else 0
            if not is_supercharging:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Dealt {'{:,}'.format(damage)} damage to {mob}!")
            else:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Dealt {'{:,}'.format(damage)} supercharged damage to {mob}!")
            if is_critical:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
            return message

        async def playerDefend(message, e, console, turn, atk_gauge, def_gauge):
            dg.Player.DEF *= 3
            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You fortified your defences!")
            return message

        async def yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending = False, is_evading = False):
            damage, is_critical = damageCalculator(dg.Yokai, dg.Player, Party)
            if is_charging and not is_defending:
                damage *= 2
            if not is_evading:
                dg.Player.HP = dg.Player.HP - damage if not dg.Player.HP - damage < 0 else 0
                if not is_charging:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Took {'{:,}'.format(damage)} damage from {dg.Yokai.name}!")
                else:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Took {'{:,}'.format(damage)} heavy damage from {dg.Yokai.name}!")
                if is_critical:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
            else:
                if not is_charging:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Evaded {'{:,}'.format(damage)} damage from {dg.Yokai.name}!")
                else:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Evaded {'{:,}'.format(damage)} heavy damage from {dg.Yokai.name}!")
                if is_critical:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical evaded!)")
            return message

        async def yokaiDefend(message, e, console, turn, atk_gauge, def_gauge):
            dg.Yokai.DEF *= 2
            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{mob} fortified its defences!")
            return message

        async def healPartyMember(message, e, console, turn, atk_gauge, def_gauge):
            heal, is_critical = healCalculator(dg.Player, Party)
            if Party["Current"] == "1":
                dg.Player2.HP = dg.Player2.HP + heal if not dg.Player2.HP + heal > getPlayerHP(Party["Player_2"]["ID"]) else getPlayerHP(Party["Player_2"]["ID"])
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Healed {'{:,}'.format(heal)} HP to {Party['Player_2']['Name']}!")
            else:
                dg.Player1.HP = dg.Player1.HP + heal if not dg.Player1.HP + heal > getPlayerHP(Party["Player_1"]["ID"]) else getPlayerHP(Party["Player_1"]["ID"])
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Healed {'{:,}'.format(heal)} HP to {Party['Player_1']['Name']}!")
            if is_critical:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
            return message

        # Loading screen
        message = await loadYokaiEncounter(message, e, mob)

        # Begin Combat Engine
        e.add_field(name = "Turn", value = "Placeholder", inline = True) # Field 3
        e.add_field(name = "ATK Ougi", value = "Placeholder", inline = True) # Field 4
        e.add_field(name = "DEF Ougi", value = "Placeholder", inline = False) # Field 5
        e.add_field(name = "Yokai", value = "Placeholder", inline = True) # Field 6
        e.add_field(name = "Player", value = "Placeholder", inline = True) # Field 7
        e.add_field(name = "Console", value = "Placeholder", inline = False) # Field 8
        console = [""]
        yokai_action = ""
        player_action = ""
        dg.Yokai.name = mob
        # dg.Yokai.HP = dg.level * dg.multiplier * random.randint(10, 50) + (math.floor((dg.level ** 3) / 4))
        # dg.Yokai.ATK = dg.level * dg.multiplier * random.randint(5, 15) + (math.floor((dg.level ** 2) / 4))
        # dg.Yokai.DEF = dg.level * dg.multiplier * random.randint(5, 15) + (math.floor((dg.level ** 2) / 4))
        base_yokai_hp = math.floor((dg.level * random.randint(20, 50)) + (dg.level * dg.multiplier)) + dg.yokai_modulations["HP"]
        base_yokai_atk = math.floor((dg.level * random.uniform(5, 8.5)) + (dg.level * dg.multiplier)) + dg.yokai_modulations["ATK"]
        base_yokai_def = math.floor((dg.level * random.uniform(5.5, 9)) + (dg.level * dg.multiplier)) + dg.yokai_modulations["DEF"]
        dg.Yokai.HP = base_yokai_hp
        dg.Yokai.ATK = base_yokai_atk
        dg.Yokai.DEF = base_yokai_def
        if Party is None:
            base_player_hp = getPlayerHP(user_id)
            base_player_atk = getPlayerATK(user_id) + dg.Player.weapon_atk
            base_player_atk = config.stats_cap if base_player_atk > config.stats_cap else base_player_atk
            base_player_def = getPlayerDEF(user_id)
            if getPlayerLevel(user_id) > dg.Player.level:
                dg.Player.level = getPlayerLevel(user_id)
                dg.Player.HP = getPlayerHP(user_id)
        else:
            base_player_1_hp = getPlayerHP(Party["Player_1"]["ID"])
            base_player_1_atk = getPlayerATK(Party["Player_1"]["ID"]) + dg.Player1.weapon_atk
            base_player_1_atk = config.stats_cap if base_player_1_atk > config.stats_cap else base_player_1_atk
            base_player_1_def = getPlayerDEF(Party["Player_1"]["ID"])
            if getPlayerLevel(Party["Player_1"]["ID"]) > dg.Player1.level:
                dg.Player1.level = getPlayerLevel(Party["Player_1"]["ID"])
                dg.Player1.HP = getPlayerHP(Party["Player_1"]["ID"])

            base_player_2_hp = getPlayerHP(Party["Player_2"]["ID"])
            base_player_2_atk = getPlayerATK(Party["Player_2"]["ID"]) + dg.Player2.weapon_atk
            base_player_2_atk = config.stats_cap if base_player_2_atk > config.stats_cap else base_player_2_atk
            base_player_2_def = getPlayerDEF(Party["Player_2"]["ID"])
            if getPlayerLevel(Party["Player_2"]["ID"]) > dg.Player2.level:
                dg.Player2.level = getPlayerLevel(Party["Player_2"]["ID"])
                dg.Player2.HP = getPlayerHP(Party["Player_2"]["ID"])
        atk_gauge = 0
        def_gauge = 0
        turn = 0
        while flag:
            yokai_state, player_state = updateAgents()
            yokai_killed = False if dg.Yokai.HP > 0 else True
            player_killed = False if dg.Player.HP > 0 else True
            if not Party is None:
                player_1_killed = False if dg.Player1.HP > 0 else True
                player_2_killed = False if dg.Player2.HP > 0 else True
                if player_killed:
                    if not player_1_killed or not player_2_killed:
                        player_killed = False
                        if player_1_killed and Party["Player_1"]["Alive"]:
                            dg.Player = dg.Player2
                            Party.update({"Current": 2})
                            Party["Player_1"].update({"Alive": False})
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{mob} has slain {Party['Player_1']['Name']}")
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                        elif player_2_killed and Party["Player_2"]["Alive"]:
                            dg.Player = dg.Player1
                            Party.update({"Current": 1})
                            Party["Player_2"].update({"Alive": False})
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{mob} has slain {Party['Player_2']['Name']}")
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
            if not yokai_killed and not player_killed:
                turn += 1
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Turn: #{turn}")
                dg.Yokai.ATK = base_yokai_atk
                dg.Yokai.DEF = base_yokai_def
                if Party is None:
                    dg.Player.ATK = base_player_atk
                    dg.Player.DEF = base_player_def
                else:
                    if Party["Current"] == 1:
                        e.set_author(name = Party[f"Player_1"]["Name"], icon_url = Party[f"Player_1"]["Member"].display_avatar)
                        dg.Player.ATK = base_player_1_atk
                        dg.Player.DEF = base_player_1_def
                    else:
                        e.set_author(name = Party[f"Player_2"]["Name"], icon_url = Party[f"Player_2"]["Member"].display_avatar)
                        dg.Player.ATK = base_player_2_atk
                        dg.Player.DEF = base_player_2_def
                is_charging = True if random.random() < 0.1 else False
                if is_charging:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({mob} is charging a heavy attack!)")
                is_defending = False
                is_evading = False
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "Choose an action to perform")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Attack | Defend | Leave Dungeon)")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")

                while True:
                    emojis = [Icons["attack"], Icons["defend"], Icons["riceball"]]
                    if atk_gauge == 5: emojis.append(Icons["supercharge"])
                    if def_gauge == 5: emojis.append(Icons["evade"])
                    if Weapons[dg.Player.weapon]["Type"] == "Staff" and not Party is None and Party["Player_1"]["Alive"] and Party["Player_2"]["Alive"]: emojis.append(Icons["heal"])
                    if not Party is None and (not player_1_killed and not player_2_killed): emojis.append("🔀")
                    emojis.append(Icons["exit"])
                    if Party is None:
                        reaction, user = await waitForReaction(ctx, message, e, emojis)
                    else:
                        reaction, user = await waitForReaction(ctx, message, e, emojis, user_override = Party[f"Player_{Party['Current']}"]["Member"])
                    if reaction is None:
                        flag = False
                    else:
                        is_player_turn = bool(random.getrandbits(1))
                        yokai_action = "Attack" if bool(random.getrandbits(1)) or is_charging else "Defend"
                        player_action = ""
                        match str(reaction.emoji):
                            case x if x == Icons["attack"]:
                                await message.clear_reactions()
                                if is_player_turn:
                                    if yokai_action == "Defend":
                                        message = await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Yokai.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    if yokai_action == "Attack":
                                        message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
                                else:
                                    message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Player.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge)
                                atk_gauge = atk_gauge + 1 if atk_gauge + 1 <= 5 else 5
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case x if x == Icons["defend"]:
                                await message.clear_reactions()
                                player_action = "Defend"
                                message = await playerDefend(message, e, console, turn, atk_gauge, def_gauge)
                                is_defending = True
                                message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                if yokai_action == "Attack":
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Suppressed)")
                                def_gauge = def_gauge + 1 if def_gauge + 1 <= 5 else 5
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case x if x == Icons["riceball"]:
                                await message.clear_reactions()
                                message, flag, result = await consumeNigiri(message, flag, e, console, turn, atk_gauge, def_gauge, dg, printToConsole, Party)
                                if result:
                                    message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                else:
                                    continue
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case x if x == Icons["supercharge"] and atk_gauge == 5:
                                await message.clear_reactions()
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Activated Ougi skill: Supercharge ATK)")
                                atk_gauge = 0
                                if is_player_turn:
                                    if yokai_action == "Defend":
                                        message = await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = True)
                                    if not dg.Yokai.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    if yokai_action == "Attack":
                                        message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
                                else:
                                    message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Player.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = True)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case x if x == Icons["evade"] and def_gauge == 5:
                                await message.clear_reactions()
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Activated Ougi skill: Perfect Dodge)")
                                is_evading = True
                                def_gauge = 0
                                continue
                            case x if x == Icons["heal"]:
                                await message.clear_reactions()
                                if is_player_turn:
                                    if yokai_action == "Defend":
                                        message = await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    message = await healPartyMember(message, e, console, turn, atk_gauge, def_gauge)
                                    if yokai_action == "Attack":
                                        message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
                                else:
                                    message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Player.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    message = await healPartyMember(message, e, console, turn, atk_gauge, def_gauge)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case "🔀":
                                await message.clear_reactions()
                                if not is_player_turn:
                                    message = await yokaiAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if yokai_action == "Attack" else await yokaiDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Player.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                if Party["Current"] == 1:
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Swapping to {Party['Player_2']['Name']})")
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                    dg.Player = dg.Player2
                                    Party.update({"Current": 2})
                                    break
                                else:
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Swapping to {Party['Player_1']['Name']})")
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                    dg.Player = dg.Player1
                                    Party.update({"Current": 1})
                                    break
                            case x if x == Icons["exit"]:
                                await message.clear_reactions()
                                message, flag, result = await exitDungeon(message, flag, e, field = 9, Party = Party)
                                if result:
                                    e.description = "**Player aborted the dungeon!**"
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Aborting dungeon)")
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                    flag = False
                                else:
                                    continue
                    break

            elif yokai_killed:
                ExpTable = Tables["ExpTable"]
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You have defeated {mob}!")
                if mob == "Gold Daruma":
                    random_amount = random.randint(1000, 10000)
                    ryou_amount = round(((random_amount * dg.level) / 3) + ((random_amount * dg.level * dg.multiplier) / 6))
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({mob} dropped {'{:,}'.format(math.floor(ryou_amount))} Ryou)")
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Half taken, half added to dungeon pool)")
                    if Party is None:
                        await reward(ctx, ctx.author.mention, "ryou", math.floor(ryou_amount / 2))
                    else:
                        if Party["Player_1"]["Alive"]: await reward(ctx, Party["Player_1"]["Member"].mention, "ryou", math.floor(ryou_amount / (4 if Party["Player_2"]["Alive"] else 2)))
                        if Party["Player_2"]["Alive"]: await reward(ctx, Party["Player_2"]["Member"].mention, "ryou", math.floor(ryou_amount / (4 if Party["Player_1"]["Alive"] else 2)))
                    dg.Cache.pool += math.floor(ryou_amount / 2)
                exp_row = ExpTable[dg.level - 1][1]
                exp_amount = round((random.uniform(10, 20) * dg.level) + ((exp_row / 3000) * dg.multiplier))
                if Party is None:
                    exp_reward = addPlayerExp(user_id, exp_amount)
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {'{:,}'.format(exp_reward)} EXP!)")
                else:
                    if Party["Player_1"]["Alive"]: exp_reward_1 = addPlayerExp(Party["Player_1"]["ID"], math.floor(exp_amount / (2 if Party["Player_2"]["Alive"] else 1)))
                    if Party["Player_2"]["Alive"]: exp_reward_2 = addPlayerExp(Party["Player_2"]["ID"], math.floor(exp_amount / (2 if Party["Player_1"]["Alive"] else 1)))
                    if Party["Player_1"]["Alive"]: message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({Party['Player_1']['Name']} Gained {'{:,}'.format(exp_reward_1)} EXP!)")
                    if Party["Player_2"]["Alive"]: message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({Party['Player_2']['Name']} Gained {'{:,}'.format(exp_reward_2)} EXP!)")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "Choose an action to perform")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Proceed | Leave Dungeon)")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                emojis = ["⏭️", Icons["exit"]]
                if Party is None:
                    reaction, user = await waitForReaction(ctx, message, e, emojis)
                else:
                    reaction, user = await waitForReaction(ctx, message, e, emojis, user_override = Party[f"Player_{Party['Current']}"]["Member"])
                if reaction is None:
                    flag = False
                else:
                    match str(reaction.emoji):
                        case "⏭️":
                            await message.clear_reactions()
                            e.remove_field(8)
                            e.remove_field(7)
                            e.remove_field(6)
                            e.remove_field(5)
                            e.remove_field(4)
                            e.remove_field(3)
                            message = await message.edit(embed = e)
                            break
                        case x if x == Icons["exit"]:
                            await message.clear_reactions()
                            e.description = "Player aborted the dungeon!"
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Aborting dungeon)")
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            flag = False
            elif player_killed:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{mob} has killed you!")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Aborting dungeon)")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                time.sleep(1)
                message = await deathScreen(message, e, mob)
                flag = False
        return message, flag

    async def openChest(ctx, message, flag, dg, chest, e, Party):

        async def formatLoot(chest):
            loot = []
            loot.append("")
            for key, value in chest.items():
                loot.append(f"{key}: {value}")
            loot.append("")
            return loot

        async def rewardLoot(ctx, chest, random_user):
            for key, value in chest.items():
                match key:
                    case "Ryou":
                        if Party is None:
                            addPlayerRyou(user_id, value)
                        else:
                            if Party["Player_1"]["Alive"]: addPlayerRyou(Party["Player_1"]["ID"], math.floor(value / (2 if Party["Player_2"]["Alive"] else 1)))
                            if Party["Player_2"]["Alive"]: addPlayerRyou(Party["Player_2"]["ID"], math.floor(value / (2 if Party["Player_1"]["Alive"] else 1)))
                    case "EXP":
                        if Party is None:
                            addPlayerExp(user_id, value)
                        else:
                            if Party["Player_1"]["Alive"]: addPlayerExp(Party["Player_1"]["ID"], math.floor(value / (2 if Party["Player_2"]["Alive"] else 1)))
                            if Party["Player_2"]["Alive"]: addPlayerExp(Party["Player_2"]["ID"], math.floor(value / (2 if Party["Player_1"]["Alive"] else 1)))
                    case "Gacha Fragment" | "Gacha Fragments":
                        if Party is None:
                            fragments = GachaDB.query("SELECT gacha_fragments FROM userdata WHERE user_id = {}".format(user_id))[0][0]
                            GachaDB.execute("UPDATE userdata SET gacha_fragments = ? WHERE user_id = ?", (fragments + value, user_id))
                        else:
                            fragments = GachaDB.query("SELECT gacha_fragments FROM userdata WHERE user_id = {}".format(random_user))[0][0]
                            GachaDB.execute("UPDATE userdata SET gacha_fragments = ? WHERE user_id = ?", (fragments + value, random_user))
                    case product if product in Products:
                        if Party is None:
                            item_quantity = getUserItemQuantity(user_id, product)
                            if item_quantity == None:
                                ItemsDB.execute("INSERT INTO {} (item, quantity) VALUES ('{}', {})".format(f"user_{user_id}", product, value))
                            else:
                                ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity + value, product))
                        else:
                            item_quantity = getUserItemQuantity(random_user, product)
                            if item_quantity == None:
                                ItemsDB.execute("INSERT INTO {} (item, quantity) VALUES ('{}', {})".format(f"user_{random_user}", product, value))
                            else:
                                ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(random_user), item_quantity + value, product))

        async def loadNextRoom(message, e):
            e.description = "🔄 **Loading Next Room** 🔄"
            await message.edit(embed = e)
            time.sleep(0.5)
            e.description = "🔄 **Loading Next Room** 🔄 ▫️"
            await message.edit(embed = e)
            time.sleep(0.5)
            e.description = "🔄 **Loading Next Room** 🔄 ▫️ ▫️"
            await message.edit(embed = e)
            time.sleep(0.5)
            e.description = "🔄 **Loading Next Room** 🔄 ▫️ ▫️ ▫️"
            await message.edit(embed = e)
            time.sleep(0.5)
            e.remove_field(4)
            e.remove_field(3)
            if Party is None:
                e.description = None
            else:
                e.description = f"**Party: <@{Party['Player_1']['ID']}>, <@{Party['Player_2']['ID']}>**"
            e.set_image(url = None)
            await message.edit(embed = e)
            return message

        e.add_field(name = "Chest Discovered!", value = f"Will you open it?", inline = True) # Field 3
        e.set_image(url = Resource["Chest"][0])
        await message.edit(embed = e)
        while flag:
            emojis = [Icons["chest"], "⏭️"]
            if not Party is None: emojis.append("🔀")
            emojis.append(Icons["exit"])
            if Party is None:
                reaction, user = await waitForReaction(ctx, message, e, emojis)
            else:
                e.set_author(name = Party[f"Player_{Party['Current']}"]["Name"], icon_url = Party[f"Player_{Party['Current']}"]["Member"].display_avatar)
                await message.edit(embed = e)
                reaction, user = await waitForReaction(ctx, message, e, emojis, user_override = Party[f"Player_{Party['Current']}"]["Member"])
            if reaction is None:
                flag = False
            else:
                match str(reaction.emoji):
                    case x if x == Icons["chest"]:
                        await message.clear_reactions()
                        loot = await formatLoot(chest)
                        if not Party is None:
                            random_user = random.choice([Party["Player_1"]["ID"], Party["Player_2"]["ID"]]) if Party["Player_1"]["Alive"] and Party["Player_2"]["Alive"] else Party[f"Player_{Party['Current']}"]["ID"]
                            for key, value in chest.items():
                                if key != "Ryou" and key != "EXP":
                                    await ctx.send(f"Randomly chose <@{random_user}> to receive: **{value} {key}**")
                            e.set_field_at(3, name = "Loot obtained: (Split any Ryou or EXP 50/50)", value = boxifyArray(loot, padding = 2), inline = True) # Field 4
                        else:
                            random_user = None
                            e.set_field_at(3, name = "Loot obtained:", value = boxifyArray(loot, padding = 2), inline = True) # Field 4
                        await message.edit(embed = e)
                        await rewardLoot(ctx, chest, random_user)
                        message = await loadNextRoom(message, e)
                        break
                    case "⏭️":
                        await message.clear_reactions()
                        message = await loadNextRoom(message, e)
                        break
                    case "🔀":
                        await message.clear_reactions()
                        if Party["Current"] == 1:
                            dg.Player = dg.Player2
                            Party.update({"Current": 2})
                            continue
                        else:
                            dg.Player = dg.Player1
                            Party.update({"Current": 1})
                            continue
                    case x if x == Icons["exit"]:
                        await message.clear_reactions()
                        message, flag, result = await exitDungeon(message, flag, e, field = 4, Party = Party)
                        if result:
                            e.description = "**Player aborted the dungeon!**"
                            await message.edit(embed = e)
                            flag = False
                        else:
                            continue
        return message, flag

    async def fightBoss(ctx, message, flag, dg, boss, e, Party):
        clear_rewards = {}
        dg.Boss.name = boss["Name"]
        base_boss_hp = boss["HP"] + dg.boss_modulations["HP"]
        base_boss_atk = math.floor((dg.level * random.uniform(8, 9)) + (dg.level * dg.multiplier)) + dg.boss_modulations["ATK"]
        base_boss_def = math.floor((dg.level * random.uniform(8, 9)) + (dg.level * dg.multiplier)) + dg.boss_modulations["DEF"]
        dg.Boss.HP = base_boss_hp
        dg.Boss.ATK = base_boss_atk
        dg.Boss.DEF = base_boss_def
        if Party is None:
            base_player_hp = getPlayerHP(user_id)
            base_player_atk = getPlayerATK(user_id) + dg.Player.weapon_atk
            base_player_atk = config.stats_cap if base_player_atk > config.stats_cap else base_player_atk
            base_player_def = getPlayerDEF(user_id)
            if getPlayerLevel(user_id) > dg.Player.level:
                dg.Player.level = getPlayerLevel(user_id)
                dg.Player.HP = getPlayerHP(user_id)
        else:
            base_player_1_hp = getPlayerHP(Party["Player_1"]["ID"])
            base_player_1_atk = getPlayerATK(Party["Player_1"]["ID"]) + dg.Player1.weapon_atk
            base_player_1_atk = config.stats_cap if base_player_1_atk > config.stats_cap else base_player_1_atk
            base_player_1_def = getPlayerDEF(Party["Player_1"]["ID"])
            if getPlayerLevel(Party["Player_1"]["ID"]) > dg.Player1.level:
                dg.Player1.level = getPlayerLevel(Party["Player_1"]["ID"])
                dg.Player1.HP = getPlayerHP(Party["Player_1"]["ID"])

            base_player_2_hp = getPlayerHP(Party["Player_2"]["ID"])
            base_player_2_atk = getPlayerATK(Party["Player_2"]["ID"]) + dg.Player2.weapon_atk
            base_player_2_atk = config.stats_cap if base_player_2_atk > config.stats_cap else base_player_2_atk
            base_player_2_def = getPlayerDEF(Party["Player_2"]["ID"])
            if getPlayerLevel(Party["Player_2"]["ID"]) > dg.Player2.level:
                dg.Player2.level = getPlayerLevel(Party["Player_2"]["ID"])
                dg.Player2.HP = getPlayerHP(Party["Player_2"]["ID"])

        async def updateEmbed(e, boss_state, player_state, console, turn, atk_gauge, def_gauge):
            if Party is None:
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            else:
                e.set_author(name = Party[f"Player_{Party['Current']}"]["Name"], icon_url = Party[f"Player_{Party['Current']}"]["Member"].display_avatar)
            e.set_field_at(2, name = "Boss HP", value = f"🩸 **{'{:,}'.format(dg.Boss.HP)} / {'{:,}'.format(boss['HP'])}**")
            e.set_field_at(3, name = "Turn:", value = f"#️⃣ **{turn}**")
            e.set_field_at(4, name = "ATK Ougi Gauge:", value = f"{Icons['supercharge']} **{atk_gauge} / 5**")
            e.set_field_at(5, name = "DEF Ougi Gauge:", value = f"{Icons['evade']} **{def_gauge} / 5**")
            e.set_field_at(6, name = "Boss stats:", value = boxifyArray(boss_state, padding = 2))
            e.set_field_at(7, name = "Player stats:", value = boxifyArray(player_state, padding = 2))
            e.set_field_at(8, name = "Console:", value = boxifyArray(console[-7:], padding = 2, min_width = 33), inline = False)

        def updateAgents():
            boss_state = ["", f"{dg.Boss.name}", f"Phase: {dg.Boss.phase}", "", f"Boss HP: {'{:,}'.format(dg.Boss.HP)}", f"Boss ATK: {'{:,}'.format(dg.Boss.ATK)}", f"Boss DEF: {'{:,}'.format(dg.Boss.DEF)}", ""]
            player_state = ["", f"{dg.Player.name}", f"Level: {dg.Player.level}", f"⚔ {dg.Player.weapon} ⚔", "", f"Player HP: {'{:,}'.format(dg.Player.HP)}", f"Player ATK: {'{:,}'.format(dg.Player.ATK)}", f"Player DEF: {'{:,}'.format(dg.Player.DEF)}", ""]
            return boss_state, player_state

        async def printToConsole(message, e, console, turn, atk_gauge, def_gauge, input):
            time.sleep(0.2)
            console.append(str(input))
            boss_state, player_state = updateAgents()
            await updateEmbed(e, boss_state, player_state, console, turn, atk_gauge, def_gauge)
            await message.edit(embed = e)
            return message

        async def loadBossEncounter(message, e, name):
            e.add_field(name = "Boss Encountered!", value = f"Name: __{name}__", inline = True) # Field 3
            e.set_image(url = Resource[f"{name}-2"][0].replace(" ", "%20"))
            e.description = "🔄 **Loading Combat Engine** 🔄"
            await message.edit(embed = e)
            time.sleep(1)
            e.description = "🔄 **Loading Combat Engine** 🔄 ▫️"
            await message.edit(embed = e)
            time.sleep(1)
            e.description = "🔄 **Loading Combat Engine** 🔄 ▫️ ▫️"
            await message.edit(embed = e)
            time.sleep(1)
            e.description = "🔄 **Loading Combat Engine** 🔄 ▫️ ▫️ ▫️"
            await message.edit(embed = e)
            time.sleep(1)
            e.remove_field(3)
            if Party is None:
                e.description = None
            else:
                e.description = f"**Party: <@{Party['Player_1']['ID']}>, <@{Party['Player_2']['ID']}>**"
            e.set_image(url = None)
            return message

        async def playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = False):
            damage, is_critical = damageCalculator(dg.Player, dg.Boss, Party)
            effectiveness = 0
            weapon_elements = Weapons[dg.Player.weapon]["Elements"]
            if weapon_elements:
                for resistance in dg.boss["Resistances"]:
                    for element in weapon_elements:
                        if element == resistance:
                            effectiveness -= 1
                for weakness in dg.boss["Weaknesses"]:
                    for element in weapon_elements:
                        if element == weakness:
                            effectiveness += 1
            if effectiveness < 0:
                if effectiveness < -2:
                    damage = 0
                else:
                    damage = math.floor(damage / (abs(effectiveness) * 2))
            elif effectiveness > 0:
                damage = math.floor(damage * ((effectiveness / 2) * 2.5))
            if is_supercharging:
                damage *= 2
            dg.Boss.HP = dg.Boss.HP - damage if not dg.Boss.HP - damage < 0 else 0
            if not is_supercharging:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Dealt {'{:,}'.format(damage)} damage to {dg.Boss.name}!")
            else:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Dealt {'{:,}'.format(damage)} supercharged damage to {dg.Boss.name}!")
            if is_critical:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
            match effectiveness:
                case 1:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Super effective!)")
                case 2:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(HYPER effective!!)")
                case x if x > 2:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(ULTRA EFFECTIVE!!!)")
                case -1:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Not very effective)")
                case -2:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Astronomically uneffective)")
                case x if x < -2:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Missed due to immunity)")
            return message

        async def playerDefend(message, e, console, turn, atk_gauge, def_gauge):
            dg.Player.DEF *= 3
            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You fortified your defences!")
            return message

        async def bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending = False, is_evading = False):
            damage, is_critical = damageCalculator(dg.Boss, dg.Player, Party)
            if is_charging and not is_defending:
                damage *= 2
            if not is_evading:
                dg.Player.HP = dg.Player.HP - damage if not dg.Player.HP - damage < 0 else 0
                if not is_charging:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Took {'{:,}'.format(damage)} damage from {dg.Boss.name}!")
                else:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Took {'{:,}'.format(damage)} heavy damage from {dg.Boss.name}!")
                if is_critical:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
            else:
                if not is_charging:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Evaded {'{:,}'.format(damage)} damage from {dg.Boss.name}!")
                else:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Evaded {'{:,}'.format(damage)} heavy damage from {dg.Boss.name}!")
                if is_critical:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical evaded!)")
            return message

        async def bossDefend(message, e, console, turn, atk_gauge, def_gauge):
            dg.Boss.DEF *= 2
            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} fortified its defences!")
            return message

        async def healPartyMember(message, e, console, turn, atk_gauge, def_gauge):
            heal, is_critical = healCalculator(dg.Player, Party)
            if Party["Current"] == "1":
                dg.Player2.HP = dg.Player2.HP + heal if not dg.Player2.HP + heal > getPlayerHP(Party["Player_2"]["ID"]) else getPlayerHP(Party["Player_2"]["ID"])
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Healed {'{:,}'.format(heal)} HP to {Party['Player_2']['Name']}!")
            else:
                dg.Player1.HP = dg.Player1.HP + heal if not dg.Player1.HP + heal > getPlayerHP(Party["Player_1"]["ID"]) else getPlayerHP(Party["Player_1"]["ID"])
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Healed {'{:,}'.format(heal)} HP to {Party['Player_1']['Name']}!")
            if is_critical:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(2x Critical!)")
            return message

        # Loading screen
        message = await loadBossEncounter(message, e, dg.Boss.name)

        # Begin Combat Engine
        e.add_field(name = "Turn", value = "Placeholder", inline = True) # Field 3
        e.add_field(name = "ATK Ougi", value = "Placeholder", inline = True) # Field 4
        e.add_field(name = "DEF Ougi", value = "Placeholder", inline = False) # Field 5
        e.add_field(name = "Boss", value = "Placeholder", inline = True) # Field 6
        e.add_field(name = "Player", value = "Placeholder", inline = True) # Field 7
        e.add_field(name = "Console", value = "Placeholder", inline = False) # Field 8
        console = [""]
        boss_action = ""
        player_action = ""
        atk_gauge = 0
        def_gauge = 0
        turn = 0
        phase = 1
        while flag:
            boss_state, player_state = updateAgents()
            boss_killed = False if dg.Boss.HP > 0 else True
            player_killed = False if dg.Player.HP > 0 else True
            if not Party is None:
                player_1_killed = False if dg.Player1.HP > 0 else True
                player_2_killed = False if dg.Player2.HP > 0 else True
                if player_killed:
                    if not player_1_killed or not player_2_killed:
                        player_killed = False
                        if player_1_killed and Party["Player_1"]["Alive"]:
                            dg.Player = dg.Player2
                            Party.update({"Current": 2})
                            Party["Player_1"].update({"Alive": False})
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} has slain {Party['Player_1']['Name']}")
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                        elif player_2_killed and Party["Player_2"]["Alive"]:
                            dg.Player = dg.Player1
                            Party.update({"Current": 1})
                            Party["Player_2"].update({"Alive": False})
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} has slain {Party['Player_2']['Name']}")
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
            if not boss_killed and not player_killed:
                turn += 1
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"Turn: #{turn}")
                dg.Boss.ATK = base_boss_atk
                dg.Boss.DEF = base_boss_def
                if Party is None:
                    dg.Player.ATK = base_player_atk
                    dg.Player.DEF = base_player_def
                else:
                    if Party["Current"] == 1:
                        e.set_author(name = Party["Player_1"]["Name"], icon_url = Party["Player_1"]["Member"].display_avatar)
                        dg.Player.ATK = base_player_1_atk
                        dg.Player.DEF = base_player_1_def
                    else:
                        e.set_author(name = Party["Player_2"]["Name"], icon_url = Party["Player_2"]["Member"].display_avatar)
                        dg.Player.ATK = base_player_2_atk
                        dg.Player.DEF = base_player_2_def
                is_charging = True if random.random() < 0.25 else False
                if is_charging:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({dg.Boss.name} is charging a heavy attack!)")
                is_defending = False
                is_evading = False
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "Choose an action to perform")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Attack | Defend | Leave Dungeon)")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")

                while True:
                    emojis = [Icons["attack"], Icons["defend"], Icons["riceball"]]
                    if atk_gauge == 5: emojis.append(Icons["supercharge"])
                    if def_gauge == 5: emojis.append(Icons["evade"])
                    if Weapons[dg.Player.weapon]["Type"] == "Staff" and not Party is None and Party["Player_1"]["Alive"] and Party["Player_2"]["Alive"]: emojis.append(Icons["heal"])
                    if not Party is None and (not player_1_killed and not player_2_killed): emojis.append("🔀")
                    emojis.append(Icons["exit"])
                    if Party is None:
                        reaction, user = await waitForReaction(ctx, message, e, emojis)
                    else:
                        reaction, user = await waitForReaction(ctx, message, e, emojis, user_override = Party[f"Player_{Party['Current']}"]["Member"])
                    if reaction is None:
                        flag = False
                    else:
                        is_player_turn = bool(random.getrandbits(1))
                        boss_action = "Attack" if bool(random.getrandbits(1)) or is_charging else "Defend"
                        player_action = ""
                        match str(reaction.emoji):
                            case x if x == Icons["attack"]:
                                await message.clear_reactions()
                                if is_player_turn:
                                    if boss_action == "Defend":
                                        message = await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Boss.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    if boss_action == "Attack":
                                        message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
                                else:
                                    message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Player.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge)
                                atk_gauge = atk_gauge + 1 if atk_gauge + 1 <= 5 else 5
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case x if x == Icons["defend"]:
                                await message.clear_reactions()
                                player_action = "Defend"
                                message = await playerDefend(message, e, console, turn, atk_gauge, def_gauge)
                                is_defending = True
                                message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                if boss_action == "Attack":
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(Suppressed)")
                                def_gauge = def_gauge + 1 if def_gauge + 1 <= 5 else 5
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case x if x == Icons["riceball"]:
                                await message.clear_reactions()
                                message, flag, result = await consumeNigiri(message, flag, e, console, turn, atk_gauge, def_gauge, dg, printToConsole, Party)
                                if result:
                                    message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                else:
                                    continue
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case x if x == Icons["supercharge"] and atk_gauge == 5:
                                await message.clear_reactions()
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Activated Ougi skill: Supercharge ATK)")
                                atk_gauge = 0
                                if is_player_turn:
                                    if boss_action == "Defend":
                                        message = await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = True)
                                    if not dg.Boss.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    if boss_action == "Attack":
                                        message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
                                else:
                                    message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Player.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    message = await playerAttack(message, e, console, turn, atk_gauge, def_gauge, is_supercharging = True)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case x if x == Icons["evade"] and def_gauge == 5:
                                await message.clear_reactions()
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Activated Ougi skill: Perfect Dodge)")
                                is_evading = True
                                def_gauge = 0
                                continue
                            case x if x == Icons["heal"]:
                                await message.clear_reactions()
                                if is_player_turn:
                                    if boss_action == "Defend":
                                        message = await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    message = await healPartyMember(message, e, console, turn, atk_gauge, def_gauge)
                                    if boss_action == "Attack":
                                        message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading)
                                else:
                                    message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Player.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                    message = await healPartyMember(message, e, console, turn, atk_gauge, def_gauge)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            case "🔀":
                                await message.clear_reactions()
                                if not is_player_turn:
                                    message = await bossAttack(message, e, console, turn, atk_gauge, def_gauge, is_charging, is_defending, is_evading) if boss_action == "Attack" else await bossDefend(message, e, console, turn, atk_gauge, def_gauge)
                                    if not dg.Player.HP > 0:
                                        message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                        break
                                if Party["Current"] == 1:
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Swapping to {Party['Player_2']['Name']})")
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                    dg.Player = dg.Player2
                                    Party.update({"Current": 2})
                                    break
                                else:
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Swapping to {Party['Player_1']['Name']})")
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                    dg.Player = dg.Player1
                                    Party.update({"Current": 1})
                                    break
                            case x if x == Icons["exit"]:
                                await message.clear_reactions()
                                message, flag, result = await exitDungeon(message, flag, e, field = 9, Party = Party)
                                if result:
                                    e.description = "**Player aborted the dungeon!**"
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Aborting dungeon)")
                                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                                    flag = False
                                else:
                                    continue
                        if phase == 1 and dg.Boss.HP <= math.trunc(boss["HP"] / 2) and dg.Boss.HP > 0:
                            dg.Boss.phase = 2
                        if phase == 1 and dg.Boss.phase == 2:
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} has augmented to Phase 2!")
                            base_boss_atk = math.floor(base_boss_atk * random.uniform(1.1, 1.2))
                            base_boss_def = math.floor(base_boss_def * random.uniform(1.1, 1.2))
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(ATK and DEF buffed)")
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            phase = 2
                        if phase == 2 and dg.Boss.HP <= math.trunc(boss["HP"] / 4) and dg.Boss.HP > 0:
                            dg.Boss.phase = 3
                        if phase == 2 and dg.Boss.phase == 3:
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} has augmented to Phase 3!")
                            base_boss_atk = math.floor(base_boss_atk * random.uniform(1.1, 1.2))
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "(ATK buffed)")
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                            phase = 3
                    break

            elif boss_killed:
                ryou0 = math.floor((dg.rewards["Ryou"]['range'][0] * 0.75) + (dg.rewards["Ryou"]['range'][0] / 4) * dg.multiplier)
                ryou1 = math.floor((dg.rewards["Ryou"]['range'][1] * 0.75) + (dg.rewards["Ryou"]['range'][1] / 4) * dg.multiplier)
                exp0 = math.floor((dg.rewards["EXP"]['range'][0] * 0.75) + (dg.rewards["EXP"]['range'][0] / 4) * dg.multiplier)
                exp1 = math.floor((dg.rewards["EXP"]['range'][1] * 0.75) + (dg.rewards["EXP"]['range'][1] / 4) * dg.multiplier)
                ryou_range = [ryou0, ryou1]
                exp_range = [exp0, exp1]
                ryou_amount = random.randint(ryou_range[0], ryou_range[1])
                exp_amount = random.randint(exp_range[0], exp_range[1])
                if Party is None:
                    exp_amount = addPlayerExp(user_id, exp_amount)
                else:
                    if Party["Player_1"]["Alive"]: exp_amount_1 = addPlayerExp(Party['Player_1']['ID'], math.floor(exp_amount / (2 if Party["Player_2"]["Alive"] else 1)))
                    if Party["Player_2"]["Alive"]: exp_amount_2 = addPlayerExp(Party['Player_2']['ID'], math.floor(exp_amount / (2 if Party["Player_1"]["Alive"] else 1)))
                boost = getUserBoost(ctx)
                if boost > 0:
                    ryou_amount = ryou_amount + math.floor(ryou_amount * (boost / 100.))
                if Party is None:
                    ryou_amount = addPlayerRyou(user_id, ryou_amount)
                    clear_rewards.update({"ryou": ryou_amount, "exp": exp_amount})
                else:
                    if Party["Player_1"]["Alive"]: ryou_amount_1 = addPlayerRyou(Party['Player_1']['ID'], math.floor(ryou_amount / (2 if Party["Player_2"]["Alive"] else 1)))
                    if Party["Player_2"]["Alive"]: ryou_amount_2 = addPlayerRyou(Party['Player_2']['ID'], math.floor(ryou_amount / (2 if Party["Player_1"]["Alive"] else 1)))
                    if Party["Player_1"]["Alive"] and Party["Player_2"]["Alive"]:
                        clear_rewards.update({"ryou": ryou_amount_1 + ryou_amount_2, "exp": exp_amount_1 + exp_amount_2})
                    elif Party["Player_1"]["Alive"] and not Party["Player_2"]["Alive"]:
                        clear_rewards.update({"ryou": ryou_amount_1 , "exp": exp_amount_1})
                    elif not Party["Player_1"]["Alive"] and Party["Player_2"]["Alive"]:
                        clear_rewards.update({"ryou": ryou_amount_2 , "exp": exp_amount_2})
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"You have defeated {dg.Boss.name}!")
                if "Weapons" in dg.rewards:
                    if Party is None:
                        for weapon, rate in dg.rewards["Weapons"].items():
                            random_number = random.uniform(0, 100)
                            if random_number <= rate * dg.multiplier:
                                weapons_inv = getPlayerWeaponsInv(user_id)
                                weapons_list = weapons_inv.split(", ")
                                if not weapon in weapons_list:
                                    givePlayerWeapon(user_id, weapon)
                                dg.Cache.weapon_rewards.append(weapon)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} dropped '{weapon}'")
                    else:
                        for weapon, rate in dg.rewards["Weapons"].items():
                            random_number_1 = random.uniform(0, 100)
                            random_number_2 = random.uniform(0, 100)
                            if random_number_1 <= rate * dg.multiplier and Party["Player_1"]["Alive"]:
                                weapons_inv = getPlayerWeaponsInv(Party['Player_1']['ID'])
                                weapons_list = weapons_inv.split(", ")
                                if not weapon in weapons_list:
                                    givePlayerWeapon(Party['Player_1']['ID'], weapon)
                                dg.Cache.weapon_rewards.append(weapon)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{Party['Player_1']['Name']} found '{weapon}'")
                            elif random_number_2 <= rate * dg.multiplier and Party["Player_2"]["Alive"]:
                                weapons_inv = getPlayerWeaponsInv(Party['Player_2']['ID'])
                                weapons_list = weapons_inv.split(", ")
                                if not weapon in weapons_list:
                                    givePlayerWeapon(Party['Player_2']['ID'], weapon)
                                dg.Cache.weapon_rewards.append(weapon)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{Party['Player_2']['Name']} found '{weapon}'")
                if "Magatamas" in dg.rewards:
                    if Party is None:
                        for magatama, rate in dg.rewards["Magatamas"].items():
                            random_number = random.uniform(0, 100)
                            if random_number <= rate * dg.multiplier:
                                magatamas_inv = getPlayerMagatamasInv(user_id)
                                magatamas_list = magatamas_inv.split(", ")
                                if not magatama in magatamas_list:
                                    givePlayerMagatama(user_id, magatama)
                                dg.Cache.magatama_rewards.append(magatama)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} dropped '{magatama}'")
                    else:
                        for magatama, rate in dg.rewards["Magatamas"].items():
                            random_number_1 = random.uniform(0, 100)
                            random_number_2 = random.uniform(0, 100)
                            if random_number_1 <= rate * dg.multiplier and Party["Player_1"]["Alive"]:
                                magatamas_inv = getPlayerMagatamasInv(Party['Player_1']['ID'])
                                magatamas_list = magatamas_inv.split(", ")
                                if not magatama in magatamas_list:
                                    givePlayerMagatama(Party['Player_1']['ID'], magatama)
                                dg.Cache.magatama_rewards.append(magatama)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{Party['Player_1']['Name']} found '{magatama}'")
                            elif random_number_2 <= rate * dg.multiplier and Party["Player_2"]["Alive"]:
                                magatamas_inv = getPlayerMagatamasInv(Party['Player_2']['ID'])
                                magatamas_list = magatamas_inv.split(", ")
                                if not magatama in magatamas_list:
                                    givePlayerMagatama(Party['Player_2']['ID'], magatama)
                                dg.Cache.magatama_rewards.append(magatama)
                                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{Party['Player_2']['Name']} found '{magatama}'")
                if Party is None:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {'{:,}'.format(ryou_amount)} Ryou!{' ─ +' + str(boost) + '%' if boost > 0 else ''})")
                else:
                    if Party["Player_1"]["Alive"]: message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({Party['Player_1']['Name']} Gained {'{:,}'.format(ryou_amount_1 * (1 if not Party['Player_2']['Alive'] else 2))} Ryou!{' ─ +' + str(boost) + '%' if boost > 0 else ''})")
                    if Party["Player_2"]["Alive"]: message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({Party['Player_2']['Name']} Gained {'{:,}'.format(ryou_amount_2 * (1 if not Party['Player_1']['Alive'] else 2))} Ryou!{' ─ +' + str(boost) + '%' if boost > 0 else ''})")
                if dg.Cache.pool > 0:
                    if dg.founder != user_id:
                        whitelist = getUserWhitelist(dg.founder)
                        wl = None
                        is_whitelisted = False
                        for row in whitelist:
                            if user_id in row:
                                is_whitelisted = True
                                wl = row
                                break
                        if is_whitelisted:
                            discount = round((wl[1] / 100.) * config.tax, 3)
                        else:
                            discount = 0
                        tax = config.tax - discount
                        dg.Cache.tax_rate = math.floor(tax * 100)
                        dg.Cache.tax = addPlayerRyou(dg.founder, math.floor(dg.Cache.pool * tax))
                        if Party is None:
                            pooled_ryou = addPlayerRyou(user_id, dg.Cache.pool - dg.Cache.tax)
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {'{:,}'.format(pooled_ryou)} Ryou from pool)")
                        else:
                            if Party["Player_1"]["Alive"]: pooled_ryou = addPlayerRyou(Party['Player_1']['ID'], math.floor(dg.Cache.pool / (2 if Party["Player_2"]["Alive"] else 1)) - dg.Cache.tax)
                            if Party["Player_2"]["Alive"]: pooled_ryou = addPlayerRyou(Party['Player_2']['ID'], math.floor(dg.Cache.pool / (2 if Party["Player_1"]["Alive"] else 1)) - dg.Cache.tax)
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {'{:,}'.format(pooled_ryou)} Ryou from pool each)")
                    else:
                        if Party is None:
                            pooled_ryou = addPlayerRyou(user_id, dg.Cache.pool)
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {'{:,}'.format(pooled_ryou)} Ryou from pool)")
                        else:
                            if Party["Player_1"]["Alive"]: pooled_ryou = addPlayerRyou(Party['Player_1']['ID'], math.floor(dg.Cache.pool / (2 if Party["Player_2"]["Alive"] else 1)))
                            if Party["Player_2"]["Alive"]: pooled_ryou = addPlayerRyou(Party['Player_2']['ID'], math.floor(dg.Cache.pool / (2 if Party["Player_1"]["Alive"] else 1)))
                            message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {'{:,}'.format(pooled_ryou)} Ryou from pool each)")

                if Party is None:
                    message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Gained {'{:,}'.format(exp_amount)} EXP!)")
                else:
                    if Party["Player_1"]["Alive"]: message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({Party['Player_1']['Name']} Gained {'{:,}'.format(exp_amount_1 * (1 if not Party['Player_2']['Alive'] else 2))} EXP!)")
                    if Party["Player_2"]["Alive"]: message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"({Party['Player_2']['Name']} Gained {'{:,}'.format(exp_amount_2 * (1 if not Party['Player_1']['Alive'] else 2))} EXP!)")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                dg.Cache.cleared = True
                break
            elif player_killed:
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"{dg.Boss.name} has killed you!")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, f"(Aborting dungeon)")
                message = await printToConsole(message, e, console, turn, atk_gauge, def_gauge, "")
                time.sleep(1)
                message = await deathScreen(message, e, dg.Boss.name)
                flag = False
        return message, flag, clear_rewards

    def writeBlueprint(Blueprint, dungeon, difficulty):
        json_blueprint = json.dumps(Blueprint, indent=4)
        path = f"Blueprints/{dungeon}/{difficulty}"
        makedirs(path, exist_ok = True)
        json_filename = f"{path}/{Blueprint['header']['Seed']}.json"
        if not file_exists(json_filename):
            founder = True
            with open(json_filename, "w") as outfile:
                outfile.write(json_blueprint)
        else:
            founder = False
        file = discord.File(json_filename)
        return file, founder

    def damageCalculator(attacker, defender, Party):
        if Party is None:
            if attacker.name == user_name:
                sf = getPlayerSkillForce(user_id)
                critical = getPlayerCriticalRate(user_id)
                rate = math.floor(critical / 100.)
            else:
                sf = 0
                rate = math.floor(config.default_critical_rate / 100.)
        else:
            if attacker.name == Party[f"Player_{Party['Current']}"]["Name"]:
                sf = getPlayerSkillForce(Party[f"Player_{Party['Current']}"]["ID"])
                critical = getPlayerCriticalRate(Party[f"Player_{Party['Current']}"]["ID"])
                rate = math.floor(critical / 100.)
            else:
                sf = 0
                rate = math.floor(config.default_critical_rate / 100.)
        is_critical = True if random.random() < rate else False
        damage = math.floor(attacker.ATK / (defender.DEF / attacker.ATK))
        variance = round(damage / 10)
        var_roll = random.randint(-variance, variance)
        damage += var_roll
        damage += round(damage * (sf / 100.))
        damage *= 2 if is_critical else 1
        return damage, is_critical

    def healCalculator(healer, Party):
        sf = getPlayerSkillForce(Party[f"Player_{Party['Current']}"]["ID"])
        critical = getPlayerCriticalRate(Party[f"Player_{Party['Current']}"]["ID"])
        rate = math.floor(critical / 100.)
        is_critical = True if random.random() < rate else False
        heal = healer.ATK * 2
        variance = round(heal / 10)
        var_roll = random.randint(-variance, variance)
        heal += var_roll
        heal += round(heal * sf * (sf / 100.))
        heal *= 2 if is_critical else 1
        return heal, is_critical

    def getDungeonEnergy(dungeon):
        dungeon_metric = Dungeons[dungeon]["Energy_Metric"]
        dungeon_energy = []
        for mode in Dungeons[dungeon]["Difficulties"]:
            match mode:
                case "Normal":
                    energy_divisor = mode_divisors[0]
                case "Hard":
                    energy_divisor = mode_divisors[1]
                case "Hell":
                    energy_divisor = mode_divisors[2]
                case "Oni":
                    energy_divisor = mode_divisors[3]
            dungeon_energy.append(math.floor(dungeon_metric / energy_divisor))
        return dungeon_energy

    def getDungeonModes(type = "string"):
        default_string = f"{Icons['normal']}\n{Icons['hard']}\n{Icons['hell']}\n{Icons['oni']}"
        default_array = [Icons["normal"], Icons["hard"], Icons["hell"], Icons["oni"]]
        default_dict = {"Normal": Icons["normal"], "Hard": Icons["hard"], "Hell": Icons["hell"], "Oni": Icons["oni"]}
        match type:
            case "string":
                formatted_string = ""
                for key, value in default_dict.items():
                    formatted_string += f"\n{value} ─ __{key}__ ─ {value}\n"
                return formatted_string
            case "array":
                return default_array
            case "dict":
                return default_dict

    def formatBossStats(stats, mode):
        multiplier          = mode_multipliers[mode]
        boss_name           = stats["Name"]
        base_hp             = stats["HP"]
        scaled_hp           = math.floor((base_hp * 0.75) + (base_hp / 4 * multiplier))
        boss_resistances    = stats["Resistances"]
        boss_weaknesses     = stats["Weaknesses"]
        resistance_emojis   = getElementEmojis(boss_resistances)
        weakness_emojis     = getElementEmojis(boss_weaknesses)

        formatted_string = ""
        formatted_string += f"───────────────\n"
        formatted_string += f"👹 ─ Boss: **__{boss_name}__**\n"
        formatted_string += f"───────────────\n"
        formatted_string += f"🩸 ─ HP: `{'{:,}'.format(scaled_hp)}`\n"
        formatted_string += f"───────────────\n"
        formatted_string += f"🛡️ ─ Resistances\n"
        formatted_string += f" ╰──  {resistance_emojis}\n"
        formatted_string += f"───────────────\n"
        formatted_string += f"🗡️ ─ Weaknesses\n"
        formatted_string += f" ╰──  {weakness_emojis}\n"

        ### <TO-DO>
        ### Use text rendering modules to determine width of content
        ### Wrap content in a pretty box to display to the end-user

        # from matplotlib import rcParams
        # import os.path
        # string = "Hello there"
        # spacer_character    = " "
        # border_character    = "─"
        # border_character    = "-"

        # fields = [len(str(boss_name)), len(str('{:,}'.format(boss_hp))), len(boss_resistances), len(boss_weaknesses)]
        # max_width = getMaxItemWidth(fields, min_width = 0)
        # print(max_width)

        # border_width = max_width + 18
        # border = ""
        # for _ in range(border_width):
        #     border += border_character
        # formatting_array = []
        # formatting_array.append(f"╓{border}╖\n")
        # formatting_array.append(f"║👹 ─ Boss: **__{boss_name}__**\n")
        # formatting_array.append(f"╟{border}╢\n")
        # formatting_array.append(f"║🩸 ─ HP: `{'{:,}'.format(boss_hp)}`\n")
        # formatting_array.append(f"╟{border}╢\n")
        # formatting_array.append(f"║🛡️ ─ Resistances\n")
        # formatting_array.append(f"║ ╰──  {resistance_emojis}\n")
        # formatting_array.append(f"╟{border}╢\n")
        # formatting_array.append(f"║⚔️ ─ Weaknesses\n")
        # formatting_array.append(f"║ ╰──  {weakness_emojis}\n")
        # formatting_array.append(f"╙{border}╜\n")

        ### </TO-DO>

        return formatted_string

    def formatDungeonRewards(ctx, dungeon_rewards, mode):
        boost = getUserBoost(ctx)
        multiplier = mode_multipliers[mode]
        formatted_string = ""
        index = 0
        for key, value in dungeon_rewards.items():
            match key:
                case "Ryou":
                    icon = Icons["ryou"]
                    formatted_string += "───────────────\n"
                    value0 = math.floor((value["range"][0] * 0.75) + (value["range"][0] / 4) * multiplier)
                    value1 = math.floor((value["range"][1] * 0.75) + (value["range"][1] / 4) * multiplier)
                    formatted_string += f"{icon} ─ {key}: `{'{:,}'.format(value0)} - {'{:,}'.format(value1)}`\n"
                    if boost > 0:
                        formatted_string += f" ╰──  *Boosted:* **+{boost}%**\n"
                    formatted_string += f" ╰──  *Drop rate:* **{value['rate']}%**\n"
                case "EXP":
                    icon = Icons["exp"]
                    formatted_string += "───────────────\n"
                    value0 = math.floor((value["range"][0] * 0.75) + (value["range"][0] / 4) * multiplier)
                    value1 = math.floor((value["range"][1] * 0.75) + (value["range"][1] / 4) * multiplier)
                    formatted_string += f"{icon} ─ {key}: `{'{:,}'.format(value0)} - {'{:,}'.format(value1)}`\n"
                    formatted_string += f" ╰──  *Drop rate:* **{value['rate']}%**\n"
                # case "Weapons":
                #     icon = "⚔️"
                #     formatted_string += "───────────────\n"
                #     formatted_string += f"{icon} ─ {key}\n"
                #     for weapon, rate in value.items():
                #         formatted_string += f" ╰──  {Icons[Weapons[weapon]['Type'].lower().replace(' ', '_')]} *__{weapon}__* {Icons['rarity_' + Weapons[weapon]['Rarity'].lower()]}: **{rate}%**\n"
                # case _:
                #     icon = Icons["material_common"]
            index += 1
        formatted_string += "───────────────\n"
        formatted_string += "🎁 = Extended rewards list"
        return formatted_string

    def formatWeaponRewards(dungeon_rewards, multiplier):
        formatted_string = ""
        formatted_string += "───────────────\n"
        for weapon, rate in dungeon_rewards["Weapons"].items():
            elements = ""
            if not Weapons[weapon]['Elements'] is None:
                for element in Weapons[weapon]['Elements']:
                    elements += Icons[element]
            formatted_string += f"{Icons[Weapons[weapon]['Type'].lower().replace(' ', '_')]} *__{weapon}__* {Icons['rarity_' + Weapons[weapon]['Rarity'].lower()]}{' │ ' + elements if not elements == '' else ''} │ **{rate * multiplier}%**\n"
        return formatted_string

    def formatMagatamaRewards(dungeon_rewards, multiplier):
        formatted_string = ""
        formatted_string += "───────────────\n"
        for magatama, rate in dungeon_rewards["Magatamas"].items():
            elements = ""
            if not Magatamas[magatama]['Elements'] is None:
                for element in Magatamas[magatama]['Elements']:
                    if Magatamas[magatama]['Elements'][element]:
                        elements += f"(+{Icons[element]})"
                    else:
                        elements += f"(-{Icons[element]})"
                    if index + 1 < len(Magatamas[magatama]['Elements']):
                        elements += ", "
            formatted_string += f"{Icons['magatama_' + Magatamas[magatama]['Type'].lower().replace(' ', '_')]} *__{magatama}__*{' │ ' + elements if not elements == '' else ''} │ **{rate * multiplier}%**\n"
        return formatted_string

    def getElementEmojis(array):
        emoji_string = ""
        for element in array:
            emoji_string += Icons[element]
        return emoji_string if not emoji_string == "" else "None"

    # main()
    message = None
    mode = None
    seed = None
    Party = None
    if input:
        # User provided arguments
        try:
            # Assume both dungeon name string and mode were provided
            dg_query = list(input)
            for index, arg in enumerate(dg_query):
                # Check if user provided the -seed argument
                if arg == "-seed" or arg == "-s":
                    seed = dg_query.pop(index + 1)
                    dg_query.pop(index)
                    break
            for index, arg in enumerate(dg_query):
                # Check if user provided the -party argument
                if arg == "-party" or arg == "-p":
                    player_2 = dg_query.pop(index + 1)
                    dg_query.pop(index)
                    break
            mode_test = dg_query.pop()
            dg_string = ' '.join(dg_query)
            modes = ["Normal", "Hard", "Hell", "Oni"]
            if len(mode_test) == 1:
                # Try to get mode as integer
                mode = int(mode_test)
                if mode > 3 or mode < 0:
                    # User tried to access a protected or non-existant dungeon mode
                    await ctx.send(f"⚠️ **Invalid Mode ID:** `{mode}`")
                    return
            else:
                # Try to get mode as string
                modes = ["Normal", "Hard", "Hell", "Oni"]
                for mode_name in modes:
                    if mode_test.casefold() == mode_name.casefold():
                        mode = mode_mapping_inverse[mode_name]
                        break
                if mode == None:
                    # There was no matching string found
                    raise ValueError
        except ValueError:
            # Conlude that mode wasn't provided
            dg_query = list(input)
            for index, arg in enumerate(dg_query):
                # Check if user provided the -seed argument
                if arg == "-seed" or arg == "-s":
                    seed = dg_query.pop(index + 1)
                    dg_query.pop(index)
                    break
                # Check if user provided the -party argument
                if arg == "-party" or arg == "-p":
                    player_2 = dg_query.pop(index + 1)
                    dg_query.pop(index)
                    break
            dg_string = ' '.join(dg_query)
            mode = -1
        for dungeon in Dungeons:
            # Check if the provided dungeon argument is an existing dungeon
            if dg_string.casefold() == dungeon.casefold():
                # A match was found! Proceed to load the dungeon
                dungeon_ready = True
                break
            else:
                dungeon_ready = False
                continue
        try:
            if re.match(r"<(@|@&)[0-9]{18,19}>", player_2):
                user_1 = ctx.author
                user_2_id = convertMentionToId(player_2)
                user_2 = await bot.fetch_user(user_2_id)
                user_2_name = user_2.name
                e = discord.Embed(title = "🔔 ─ Party Invitation! ─ 🔔", description = f"Sender: {user_1.mention} | Target: {player_2}", color = default_color)
                e.set_author(name = user_2_name, icon_url = user_2.display_avatar)
                e.add_field(name = "Verify party invite:", value = f"__Join Party?__")
                verify = await ctx.send(embed = e)
                emojis = ["✅", "❌"]
                reaction, user = await waitForReaction(ctx, verify, e, emojis, user_override = user_2)
                if reaction is None:
                    return
                match str(reaction.emoji):
                    case "✅":
                        await verify.clear_reactions()
                        e.set_field_at(0, name = "Verify party invite:", value = "✅ Accepted!")
                        await verify.edit(embed = e)
                        Party = {
                            "Player_1": {"ID": user_id, "Name": user_name, "Member": user_1, "Alive": True}, \
                            "Player_2": {"ID": user_2_id, "Name": user_2_name, "Member": user_2, "Alive": True}, \
                            "Current": 0
                        }
                    case "❌":
                        await verify.clear_reactions()
                        e.set_field_at(0, name = "Verify party invite:", value = "❌ Denied!")
                        await verify.edit(embed = e)
                        return
            else:
                raise ValueError
        except NameError:
            # Concluce that player_2 wasn't provided
            pass
        except ValueError:
            # Conclude that player_2 is invalid
            await ctx.send("Please provide a valid `@mention` to choose the player to invite")
            return
        if dungeon_ready:
            await selectDungeon(ctx, message, dungeon, mode, seed, Party)
        else:
            # Checks failed; therefore, user must have mistyped the dungeon name
            await ctx.send(f"⚠️ **There doesn't exist any dungeons with the name:** `{dg_string}`")
    else:
        # Conclude that neither dungeon name nor mode was provided
        # Show the user a list of dungeons they have unlocked
        await menuDungeons(ctx, message)
    # EOF
    return

@bot.command(aliases = ["quest", "questing", "subquest", "subquests", "sidequest", "sidequests", "mission", "missions"])
@commands.check(checkChannel)
async def quests(ctx, arg: str = None):
    ''' | Usage: +quests [collect]'''
    user_id         = ctx.author.id
    default_color   = config.default_color
    last_quest      = getLastQuest(user_id)
    wait            = 0 if checkAdmin(ctx) and debug_mode else config.quest_wait
    now             = int(time.time())

    def chooseQuest():
        level = getPlayerLevel(user_id)
        for quest in reversed(Quests):
            if Quests[quest]["Level_Required"] > level:
                continue
            else:
                choice = quest
                break
        return choice

    async def promptQuest(ctx, message, flag, quest):
        banner = generateFileObject("Oni-Quests", Graphics["Banners"]["Oni-Quests"][0])
        npc = Quests[quest]["NPC"]
        lvl = Quests[quest]["Level_Required"]
        conditions = getConditions(quest)
        rewards = getRewards(quest)
        boost = getUserBoost(ctx)
        dialogue = getDialogue(quest)
        e = discord.Embed(title = "🗺️ Quest found!", description = "Will you accept this quest?", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
        e.add_field(name = "📜 Title", value = f"`{quest}`", inline = True)
        e.add_field(name = "🧍 NPC", value = f"`{npc}`", inline = True)
        e.add_field(name = "⚙️ Level Required", value = f"`{lvl}`", inline = True)
        e.add_field(name = "📌 Clearing Conditions:", value = conditions, inline = True)
        e.add_field(name = f"🎁 Rewards:{'  ─  (+' + str(boost) + '%)' if boost > 0 else ''}", value = rewards, inline = True)
        e.add_field(name = "💬 Dialogue:", value = "```" + dialogue + "```", inline = False)
        message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
        emojis = ["✅", "❌"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            flag = False
            return message, flag
        match str(reaction.emoji):
            case "✅":
                now = int(time.time())
                last_quest = getLastQuest(user_id)
                if now >= last_quest + wait or checkAdmin(ctx):
                    await message.clear_reactions()
                    message, flag = await startQuest(ctx, message, flag, quest, e)
                else:
                    hours = math.floor((last_quest + wait - now) / 60 / 60)
                    minutes = math.floor((last_quest + wait - now) / 60 - (hours * 60))
                    seconds = (last_quest + wait - now) % 60
                    await ctx.send(f"There are currently no quests, please check back in ⌛ **{hours} hours**, **{minutes} minutes**, and **{seconds} seconds**.")
                return message, flag
            case "❌":
                await message.clear_reactions()
                flag = False
                return message, flag
        return message, flag

    async def startQuest(ctx, message, flag, quest, e):
        current_quest = getPlayerQuest(user_id)
        if current_quest == "":
            QuestsDB.execute("UPDATE quests SET quest = ? WHERE user_id = ?", (quest, user_id))
            e = discord.Embed(title = "🧭 Quest accepted!", description = f"*You set off to complete the conditions.*\n**Type **`{config.prefix}quest collect` **to collect the rewards.**", color = default_color)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
            await ctx.send(embed = e)
        else:
            e = discord.Embed(title = "❌ Failed to accept quest!", description = "You already have a quest in progress.", color = 0xef5350)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
            e.add_field(name = f"Current Quest: `{current_quest}`", value = f"Type `{config.prefix}quest collect` to complete this quest first.")
            await ctx.send(embed = e)
        return message, flag

    async def completeQuest(ctx, message, flag, quest):
        marketdata = getUserMarketInv(user_id)
        ryou = marketdata.ryou
        exp = getPlayerExp(user_id)
        boost = getUserBoost(ctx)
        now = int(time.time())
        rewards_list = Quests[quest]["Rewards"]
        ryou_range = rewards_list["Ryou"] if "Ryou" in rewards_list else [0, 0]
        exp_range = rewards_list["EXP"] if "EXP" in rewards_list else [0, 0]
        ryou_random = random.randint(ryou_range[0], ryou_range[1])
        ryou_reward = ryou_random + math.floor(ryou_random * (boost / 100.))
        exp_random = random.randint(exp_range[0], exp_range[1])
        exp_reward = exp_random + math.floor(exp_random * (boost / 100.))
        MarketDB.execute("UPDATE userdata SET ryou = ? WHERE user_id = ?", (ryou + ryou_reward, user_id))
        exp_reward = addPlayerExp(user_id, exp_reward)
        ActivityDB.execute("UPDATE quests SET last_activity = ? WHERE user_id = ?", (now, user_id))
        QuestsDB.execute("UPDATE quests SET quest = ? WHERE user_id = ?", ("", user_id))
        e = discord.Embed(title = f"🎊 Quest Completed  ─  `{quest}`", description = "Recieved the following rewards:", color = 0x4caf50)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["Kinka_Mei-4"][0])
        e.add_field(name = f"Ryou{'  ─  (+' + str(boost) + '%)' if boost > 0 else ''}", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou_reward)}`", inline = True)
        e.add_field(name = f"EXP{'  ─  (+' + str(boost) + '%)' if boost > 0 else ''}", value = f"{Icons['exp']} x {'`{:,}`'.format(exp_reward) if exp_reward != 0 else '`0` *(Level cap reached)*'}", inline = True)
        message = await ctx.send(embed = e)
        return message, flag

    def getConditions(quest):
        conditions_list = Quests[quest]["Conditions"]
        conditions = ""
        for condition in conditions_list:
            for key, value in condition.items():
                match key:
                    case "Defeat":
                        conditions += f"**{key}**" + ": " + str(f"*{value[1]}*") + " " + f"__{value[0]}__" + "\n"
                    case "Clear":
                        match value[1]:
                            case -1:
                                difficulty = "Any"
                            case 0:
                                difficulty = "Normal"
                            case 1:
                                difficulty = "Hard"
                            case 2:
                                difficulty = "Hell"
                            case 3:
                                difficulty = "Oni"
                        conditions += f"**{key}**" + ": " + f"__{value[0]}__" + " - " + f"*{difficulty}*" + "\n"
        return conditions

    def getRewards(quest):
        rewards_list = Quests[quest]["Rewards"]
        rewards = ""
        for key, value in rewards_list.items():
            match key:
                case "Ryou":
                    rewards += "**Ryou range**" + ": " + Icons["ryou"] + " __" + '{:,}'.format(value[0]) + " - " + '{:,}'.format(value[1]) + "__\n"
                case "EXP":
                    rewards += "**EXP range**" + ": " + Icons["exp"] + " __" + '{:,}'.format(value[0]) + " - " + '{:,}'.format(value[1]) + "__\n"
        rewards = "None" if rewards == "" else rewards
        return rewards

    def getDialogue(quest):
        dialogue = ""
        for line in Quests[quest]["Dialogue"]:
            dialogue += line + " "
        return dialogue

    # main()
    current_quest = getPlayerQuest(user_id)
    message = None
    flag = True
    if arg == "collect" and current_quest != "":
        quest = getPlayerQuest(user_id)
        await completeQuest(ctx, message, flag, quest)
        return
    if now >= last_quest + wait or checkAdmin(ctx):
        quest = chooseQuest()
        message, flag = await promptQuest(ctx, message, flag, quest)
    else:
        hours = math.floor((last_quest + wait - now) / 60 / 60)
        minutes = math.floor((last_quest + wait - now) / 60 - (hours * 60))
        seconds = (last_quest + wait - now) % 60
        await ctx.send(f"There are currently no quests, please check back in ⌛ **{hours} hours**, **{minutes} minutes**, and **{seconds} seconds**.")

@bot.command(aliases = ["market", "buy", "sell", "trade", "shop", "store"])
@commands.check(checkChannel)
async def tavern(ctx):
    ''' | Usage: +tavern | Use reactions to navigate the menus '''
    user_id         = ctx.author.id
    menu_top        = config.menu_top
    menu_separator  = config.menu_separator
    menu_bottom     = config.menu_bottom
    default_color   = config.default_color
    numbers         = config.numbers
    conv_rate       = config.conv_rate
    conv_rates      = [
        f"{Icons['ryou']} x `{'{:,}'.format(conv_rate[0])}` *Ryou D-Coins*  =  {Icons['ticket']} x `{'{:,}'.format(conv_rate[1])}` *Gacha Tickets*",
        f"{Icons['ticket']} x `{'{:,}'.format(conv_rate[1])}` *Gacha Tickets*  =  {Icons['ryou']} x `{'{:,}'.format(int(conv_rate[0] / 10))}` *Ryou D-Coins*"
    ]

    async def menuMain(ctx, message, flag):
        banner = generateFileObject("Oni-Tavern", Graphics["Banners"]["Oni-Tavern"][0])
        e = discord.Embed(title = f"Welcome to the {branch_name} Tavern!", description = "What would you like to do today?", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
        e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
        e.add_field(name = "▷ ⚖️  ──────  Trade  ───────  ⚖️ ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ 🛒 ─────── Buy ──────── 🛒 ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ ❌ ─────  Exit  Menu  ─────  ❌ ◁", value = menu_bottom, inline = False)
        message = await ctx.send(file = banner, embed = e) if message == None else await message.edit(embed = e)
        emojis = ["⚖️", "🛒", "❌"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            flag = False
            return message, flag
        match str(reaction.emoji):
            case "⚖️":
                e.set_field_at(1, name = "►⚖️  ──────  Trade  ───────  ⚖️ ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                message, flag = await tradeEntry(ctx, message, flag)
                return message, flag
            case "🛒":
                e.set_field_at(2, name = "►🛒 ─────── Buy ──────── 🛒 ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                message, flag = await shopEntry(ctx, message, flag)
                return message, flag
            case "❌":
                e.set_field_at(3, name = "►❌ ─────  Exit  Menu  ─────  ❌ ◄", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                flag = False
                return message, flag

    async def tradeEntry(ctx, message, flag):
        while flag:
            inv_gacha   = getUserGachaInv(user_id)
            inv_market  = getUserMarketInv(user_id)
            tickets     = inv_gacha.gacha_tickets
            fragments   = inv_gacha.gacha_fragments
            total_rolls = inv_gacha.total_rolls
            ryou        = inv_market.ryou
            e = discord.Embed(title = f"Welcome to the {branch_name} Exchange!", description = "Exchange between *Ryou D-Coins* and *Gacha Tickets*!", color = default_color)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
            e.add_field(name = "Conversion Rates:", value = conv_rates[0] + "\n" + conv_rates[1], inline = False)
            e.add_field(name = "Your Ryou D-Coins:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
            e.add_field(name = "Your Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
            e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
            e.add_field(name = f"▷ {Icons['ticket']} ─ Ryou D-Coins ─> Tickets ─  {Icons['ticket']} ◁", value = menu_separator, inline = False)
            e.add_field(name = f"▷ {Icons['ryou']} ─ Tickets ─> Ryou D-Coins ─  {Icons['ryou']} ◁", value = menu_separator, inline = False)
            e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
            await message.edit(embed = e)
            emojis = [Icons['ticket'], Icons['ryou'], "↩️"]
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                flag = False
                return message, flag
            match str(reaction.emoji):
                case x if x == Icons['ticket']:
                    e.set_field_at(4, name = f"►{Icons['ticket']} ─ Ryou D-Coins ─> Tickets ─  {Icons['ticket']} ◄", value = menu_separator, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    message, flag = await ryouToTickets(ctx, message, flag)
                case x if x == Icons['ryou']:
                    e.set_field_at(5, name = f"►{Icons['ryou']} ─ Tickets ─> Ryou D-Coins ─  {Icons['ryou']} ◄", value = menu_separator, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    message, flag = await ticketsToRyou(ctx, message, flag)
                case "↩️":
                    e.set_field_at(6, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    return message, flag
            if flag:
                continue
            else:
                return message, flag

    async def ryouToTickets(ctx, message, flag):
        inv_gacha   = getUserGachaInv(user_id)
        inv_market  = getUserMarketInv(user_id)
        tickets     = inv_gacha.gacha_tickets
        fragments   = inv_gacha.gacha_fragments
        total_rolls = inv_gacha.total_rolls
        ryou        = inv_market.ryou
        if ryou >= conv_rate[0]:
            e = discord.Embed(title = f"Welcome to the {branch_name} Exchange!", description = "Trade your *Ryou D-Coins* into *Gacha Tickets*", color = default_color)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
            e.add_field(name = "Conversion Rates:", value = conv_rates[0] + "\n" + conv_rates[1], inline = False)
            e.add_field(name = "Your Ryou D-Coins:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
            e.add_field(name = "Bulk Gacha Ticket yield:", value = f"{Icons['ticket']} x `{'{:,}'.format(math.floor(ryou / conv_rate[0]))}`", inline = True)
            e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
            e.add_field(name = "▷ 1️⃣  ──── Exchange  One ────  1️⃣ ◁", value = menu_separator, inline = False)
            e.add_field(name = "▷ *️⃣  ──── Exchange  Bulk ────  *️⃣ ◁", value = menu_separator, inline = False)
            e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
            await message.edit(embed = e)
            emojis = ["1️⃣", "*️⃣", "↩️"]
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                flag = False
                return message, flag
            match str(reaction.emoji):
                case "1️⃣":
                    e.set_field_at(4, name = "►1️⃣  ──── Exchange  One ────  1️⃣ ◄", value = menu_separator, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    ryou_traded = int(conv_rate[0])
                    tickets_traded = int(conv_rate[1])
                case "*️⃣":
                    e.set_field_at(5, name = "►*️⃣  ──── Exchange  Bulk ────  *️⃣ ◄", value = menu_separator, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    e.remove_field(6)
                    e.remove_field(5)
                    e.remove_field(4)
                    e.remove_field(3)
                    e.add_field(name = "⚠️ WARNING ⚠️", value = "**This is an __irreversible__ action, please ensure you are aware of the __2 different conversion rates above__ before proceeding.**", inline = False)
                    e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
                    if ryou >= conv_rate[0] * 10:
                        e.add_field(name = "▷ 🔟  ──── Exchange  Ten  ────  🔟 ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ *️⃣  ──── Exchange  ALL  ────  *️⃣ ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    emojis = []
                    if ryou >= conv_rate[0] * 10:
                        emojis.append("🔟")
                    emojis.extend(["*️⃣", "↩️"])
                    reaction, user = await waitForReaction(ctx, message, e, emojis)
                    if reaction is None:
                        flag = False
                        return message, flag
                    match str(reaction.emoji):
                        case "🔟":
                            await message.clear_reactions()
                            ryou_traded = int(conv_rate[0] * 10)
                            tickets_traded = int(conv_rate[1] * 10)
                        case "*️⃣":
                            await message.clear_reactions()
                            ryou_traded = int(math.floor(ryou / conv_rate[0]) * conv_rate[0])
                            tickets_traded = int(math.floor(ryou / conv_rate[0]) * conv_rate[1])
                        case "↩️":
                            await message.clear_reactions()
                            return message, flag
                case "↩️":
                    e.set_field_at(6, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    return message, flag
            e = discord.Embed(title = "Trade Result", description = f"✅ Successfully Exchanged *Ryou D-Coins* into *Gacha Tickets*!", color = 0x4caf50)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
            e.add_field(name = "Traded *Ryou D-Coins*:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou_traded)}`", inline = True)
            e.add_field(name = "Obtained *Gacha Tickets*:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets_traded)}`", inline = True)
            e.add_field(name = "You now have this many *Ryou D-Coins* left:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou - ryou_traded)}`", inline = False)
            e.add_field(name = "Your total *Gacha Tickets* are now:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets + tickets_traded)}`", inline = False)
            message = await ctx.send(embed = e)
            MarketDB.userdata[user_id] = {"ryou": ryou - ryou_traded}
            GachaDB.userdata[user_id] = {"gacha_tickets": tickets + tickets_traded, "gacha_fragments": fragments, "total_rolls": total_rolls}
            flag = False
            return message, flag
        else:
            e = discord.Embed(title = "Trade Result", description = "❌ Exchange Failed!", color = 0xef5350)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
            e.add_field(name = "You have insufficient *Ryou D-Coins*.", value =  f"Need {Icons['ryou']} x `{'{:,}'.format(conv_rate[0] - ryou)}` more!", inline = False)
            message = await ctx.send(embed = e)
            flag = False
            return message, flag

    async def ticketsToRyou(ctx, message, flag):
        inv_gacha   = getUserGachaInv(user_id)
        inv_market  = getUserMarketInv(user_id)
        tickets     = inv_gacha.gacha_tickets
        fragments   = inv_gacha.gacha_fragments
        total_rolls = inv_gacha.total_rolls
        ryou        = inv_market.ryou
        if tickets >= conv_rate[1]:
            e = discord.Embed(title = f"Welcome to the {branch_name} Exchange!", description = "Trade your *Gacha Tickets* into *Ryou D-Coins*", color = default_color)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
            e.add_field(name = "Conversion Rates:", value = conv_rates[0] + "\n" + conv_rates[1], inline = False)
            e.add_field(name = "Your Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
            e.add_field(name = "Bulk Ryou D-Coins yield:", value = f"{Icons['ryou']} x `{'{:,}'.format(math.floor(tickets * (conv_rate[0] / 10)))}`", inline = True)
            e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
            e.add_field(name = "▷ 1️⃣  ──── Exchange  One ────  1️⃣ ◁", value = menu_separator, inline = False)
            e.add_field(name = "▷ *️⃣  ──── Exchange  Bulk ────  *️⃣ ◁", value = menu_separator, inline = False)
            e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
            await message.edit(embed = e)
            emojis = ["1️⃣", "*️⃣", "↩️"]
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                flag = False
                return message, flag
            match str(reaction.emoji):
                case "1️⃣":
                    e.set_field_at(4, name = "►1️⃣  ──── Exchange  One ────  1️⃣ ◄", value = menu_separator, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    ryou_traded = int(conv_rate[0] / 10)
                    tickets_traded = int(conv_rate[1])
                case "*️⃣":
                    e.set_field_at(5, name = "►*️⃣  ──── Exchange  Bulk ────  *️⃣ ◄", value = menu_separator, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    e.remove_field(6)
                    e.remove_field(5)
                    e.remove_field(4)
                    e.remove_field(3)
                    e.add_field(name = "⚠️ WARNING ⚠️", value = "**This is an __irreversible__ action, please ensure you are aware of the __2 different conversion rates above__ before proceeding.**", inline = False)
                    e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
                    if ryou >= conv_rate[0] * 10:
                        e.add_field(name = "▷ 🔟  ──── Exchange  Ten  ────  🔟 ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ *️⃣  ──── Exchange  ALL  ────  *️⃣ ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    emojis = []
                    if ryou >= conv_rate[0] * 10:
                        emojis.append("🔟")
                    emojis.extend(["*️⃣", "↩️"])
                    reaction, user = await waitForReaction(ctx, message, e, emojis)
                    if reaction is None:
                        flag = False
                        return message, flag
                    match str(reaction.emoji):
                        case "🔟":
                            await message.clear_reactions()
                            ryou_traded = int(math.floor((conv_rate[0] / 10) * 10))
                            tickets_traded = int(conv_rate[1] * 10)
                        case "*️⃣":
                            await message.clear_reactions()
                            ryou_traded = int(math.floor(tickets / conv_rate[1]) * (conv_rate[0] / 10))
                            tickets_traded = int(tickets)
                        case "↩️":
                            await message.clear_reactions()
                            return message, flag
                case "↩️":
                    e.set_field_at(6, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    return message, flag
            e = discord.Embed(title = "Trade Result", description = f"✅ Successfully Exchanged *Gacha Tickets* into *Ryou D-Coins*!", color = 0x4caf50)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
            e.add_field(name = "Traded *Gacha Tickets*:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets_traded)}`", inline = True)
            e.add_field(name = "Obtained *Ryou D-Coins*:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou_traded)}`", inline = True)
            e.add_field(name = "You now have this many *Gacha Tickets* left:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets - tickets_traded)}`", inline = False)
            e.add_field(name = "Your total *Ryou D-Coins* are now:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou + ryou_traded)}`", inline = False)
            message = await ctx.send(embed = e)
            GachaDB.userdata[user_id] = {"gacha_tickets": tickets - tickets_traded, "gacha_fragments": fragments, "total_rolls": total_rolls}
            MarketDB.userdata[user_id] = {"ryou": ryou + ryou_traded}
            flag = False
            return message, flag
        else:
            e = discord.Embed(title = "Trade Result", description = "❌ Exchange Failed!", color = 0xef5350)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
            e.add_field(name = "You have insufficient *Gacha Tickets*.", value =  f"Need {Icons['ticket']} x `{'{:,}'.format(conv_rate[1] - tickets)}` more!", inline = False)
            message = await ctx.send(embed = e)
            flag = False
            return message, flag

    async def shopEntry(ctx, message, flag):
        products_length = len(Products)
        e = discord.Embed(title = f"Welcome to the {branch_name} Shop!", description = "Select a product to purchase:", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
        # Set offset to 0 (page 1) and begin bidirectional page system
        offset = 0
        while flag:
            counter = 0
            emojis = []
            # Iterate through products in groups of 5
            for index, product in enumerate(Products):
                if index < offset:
                    # Skipping to next entry until arriving at the proper page/offset
                    continue
                e.add_field(name = f"{numbers[counter]}  -  ***{product}***", value = f"╰ Price: {Icons['ryou']} x `{'{:,}'.format(Products[product]['Price'])}`", inline = True)
                emojis.append(numbers[counter])
                counter +=1
                # Once a full page is assembled, print it
                if counter == 6 or index + 1 == products_length:
                    await message.edit(embed = e)
                    if index + 1 > 6 and index + 1 < products_length:
                        # Is a middle page
                        emojis[:0] = ["⏪", "⏩", "❌"]
                    elif index + 1 < products_length:
                        # Is the first page
                        emojis[:0] = ["⏩", "❌"]
                    elif products_length > 6:
                        # Is the last page
                        emojis[:0] = ["⏪", "❌"]
                    else:
                        # Is the only page
                        emojis[:0] = ["❌"]
                    reaction, user = await waitForReaction(ctx, message, e, emojis)
                    if reaction is None:
                        flag = False
                        return message, flag
                    match str(reaction.emoji):
                        case "⏩":
                            # Tell upcomming re-iteration to skip to the next page's offset
                            offset += 6
                            await message.clear_reactions()
                            e.clear_fields()
                            break
                        case "⏪":
                            # Tell upcomming re-iteration to skip to the previous page's offset
                            offset -= 6
                            await message.clear_reactions()
                            e.clear_fields()
                            break
                        case "❌":
                            await message.clear_reactions()
                            return message, flag
                        case number_emoji if number_emoji in numbers:
                            await message.clear_reactions()
                            product_index = getProductIndex(number_emoji, offset)
                            product = getProduct(product_index)
                            if product is None:
                                await ctx.send("The product you chose could not be loaded!")
                                flag = False
                            else:
                                e.clear_fields()
                                message, flag = await selectProduct(ctx, message, flag, product)
                                if flag:
                                    break
                                else:
                                    return message, flag
                    if flag:
                        continue
                    else:
                        return message, flag

    async def selectProduct(ctx, message, flag, product):
        stock = getProductStock(product)
        attributes = getProductAttributes(product)
        e = discord.Embed(title = f"Cart Checkout", description = f"Properties of product selected:", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
        e.add_field(name = "Product name", value = f"🏷️ **{product}**", inline = True)
        e.add_field(name = "Price", value = f"{Icons['ryou']} x `{'{:,}'.format(Products[product]['Price'])}`", inline = True)
        e.add_field(name = "Current stock", value = f"🏦 `{stock}`", inline = True)
        e.add_field(name = "Type", value = f"🔧 `{Products[product]['Type']}`", inline = True)
        e.add_field(name = "Stacks in inventory?", value = f"🗃️ `{str(Products[product]['Stackable'])}`", inline = True)
        e.add_field(name = f"📍 Attributes ({len(Products[product]['Attributes'])}):", value = "None" if not attributes else f"```{attributes}```", inline = False)
        e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
        e.add_field(name = "▷ ✅   ─────   Purchase   ─────    ✅ ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ 🚫  ──────   Cancel   ──────  🚫 ◁", value = menu_bottom, inline = False)
        await message.edit(embed = e)
        emojis = ["✅", "🚫"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            flag = False
            return message, flag
        match str(reaction.emoji):
            case "✅":
                e.set_field_at(7, name = "►✅   ─────   Purchase   ─────    ✅ ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                message, flag = await buyProduct(ctx, message, flag, product)
                flag = False
                return message, flag
            case "🚫":
                e.set_field_at(8, name = "►🚫  ──────   Cancel   ──────  🚫 ◄", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                return message, flag

    async def buyProduct(ctx, message, flag, product):
        inv_gacha       = getUserGachaInv(user_id)
        inv_market      = getUserMarketInv(user_id)
        inv_items       = getUserItemInv(user_id)
        item_quantity   = getUserItemQuantity(user_id, product)
        requirements    = getProductRequirements(product)
        stock           = getProductStock(product)
        tickets         = inv_gacha.gacha_tickets
        fragments       = inv_gacha.gacha_fragments
        total_rolls     = inv_gacha.total_rolls
        ryou            = inv_market.ryou
        price           = Products[product]["Price"]
        stackable       = Products[product]['Stackable']
        if stock == "Unlimited" or stock > 0:
            if checkMeetsItemRequirements(user_id, product):
                if ryou >= price:
                    if stackable or not stackable and item_quantity == None:
                        if not updateProductStock(product):
                            await ctx.send("‼️ Critical Error: Could not complete transaction. ‼️")
                            flag = False
                            return message, flag
                        if item_quantity == None:
                            ItemsDB.execute("INSERT INTO {} (item, quantity) VALUES ('{}', {})".format(f"user_{user_id}", product, 1))
                        else:
                            ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity + 1, product))
                        MarketDB.execute("UPDATE userdata SET ryou = ? WHERE user_id = ?", (ryou - price, user_id))
                        e = discord.Embed(title = "Checkout Result", description = f"✅ Purchase was successful!", color = 0x4caf50)
                        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                        e.set_thumbnail(url = Resource["Kinka_Mei-4"][0])
                        e.add_field(name = "Spent *Ryou D-Coins*:", value = f"{Icons['ryou']} x `{'{:,}'.format(price)}`", inline = True)
                        e.add_field(name = "Obtained *Item*:", value = f"🏷️ ***{product}***", inline = True)
                        e.add_field(name = "You now have this many *Ryou D-Coins* left:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou - price)}`", inline = False)
                        await ctx.send(embed = e)
                        if product in config.role_boosts:
                            await addRole(ctx, product)
                    else:
                        e = discord.Embed(title = "Checkout Result", description = "❌ Purchase Failed!", color = 0xef5350)
                        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                        e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
                        e.add_field(name = "This item is not stackable!", value =  "You already have one of this item.", inline = False)
                        await ctx.send(embed = e)
                else:
                    e = discord.Embed(title = "Checkout Result", description = "❌ Purchase Failed!", color = 0xef5350)
                    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                    e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
                    e.add_field(name = "You have insufficient *Ryou D-Coins*.", value =  f"Need {Icons['ryou']} x `{'{:,}'.format(price - ryou)}` more!", inline = False)
                    await ctx.send(embed = e)
            else:
                e = discord.Embed(title = "Checkout Result", description = "❌ Purchase Failed!", color = 0xef5350)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
                e.add_field(name = "You do not meet the product requirements.", value =  f"Check your {config.prefix}inv to compare your items to the requirements above.", inline = False)
                await ctx.send(embed = e)
        else:
            e = discord.Embed(title = "Checkout Result", description = "❌ Purchase Failed!", color = 0xef5350)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
            e.add_field(name = "This product is out of stock!", value = "Sorry! Please come again~", inline = False)
            await ctx.send(embed = e)
        return message, flag

    def getProductIndex(number_emoji, offset = 0):
        for n, emoji in enumerate(numbers):
            if number_emoji == emoji:
                product_index = n + offset
        return product_index

    def getProduct(product_index):
        product_array = list(Products.items())
        for p in Products:
            if p == product_array[product_index][0]:
                product = p
                break
            else:
                product = None
        return product

    def getProductAttributes(product):
        attributes = Products[product]["Attributes"]
        attributes_formatted = ""
        for attribute in attributes:
            border = ""
            for _ in attribute:
                border += "═"
            attributes_formatted += f"╔{border}╗\n║{attribute}║\n╚{border}╝\n"
        return attributes_formatted

    def getProductRequirements(product):
        requirements = Products[product]["Requirements"]
        return requirements

    def checkMeetsItemRequirements(user_id, product):
            inv_items = getUserItemInv(user_id)
            requirements = getProductRequirements(product)
            if not requirements:
                meets_requirements = True
            elif not inv_items:
                    meets_requirements = False
            else:
                for requirement, quantity in requirements.items():
                    for item in inv_items:
                        if item[0] == requirement and item[1] >= quantity:
                            meets_requirements = True
                            break
                        else:
                            meets_requirements = False
                            continue
            return meets_requirements

    def getProductStock(product):
        data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{product}'")
        if data:
            stock = GachaDB.backstock[product]
            current_stock = stock.current_stock
            return current_stock
        else:
            return "Unlimited"

    def updateProductStock(product):
        data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{product}'")
        if data:
            stock = GachaDB.backstock[product]
            current_stock = stock.current_stock
            times_rolled = stock.times_rolled
            max_limit = stock.max_limit
            if times_rolled < max_limit and current_stock > 0:
                GachaDB.backstock[product] = {"current_stock": current_stock - 1, "times_rolled": times_rolled + 1, "max_limit": max_limit}
                return True
            else:
                return False
        else:
            return True

    # main()
    message = None
    flag = True
    while flag:
        message, flag = await menuMain(ctx, message, flag)

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
                case "WL":
                    wl_role = discord.utils.get(ctx.guild.roles, name = config.wl_role)
                    if not wl_role in ctx.author.roles:
                        if await updateStock(ctx, sub_prize):
                            await member.add_roles(wl_role)
                            await ctx.send(f"🎉 Rewarded {ctx.author.mention} with whitelist Role: **{config.wl_role}**!")
                        else:
                            continue
                case "OG":
                    og_role = discord.utils.get(ctx.guild.roles, name = config.og_role)
                    if not og_role in ctx.author.roles:
                        if await updateStock(ctx, sub_prize):
                            await member.add_roles(og_role)
                            await ctx.send(f"🎉 Rewarded {ctx.author.mention} with OG Role: **{config.og_role}**!")
                        else:
                            continue
                case x if x.endswith("EXP"):
                    exp = int(x.rstrip(" EXP"))
                    # channel = bot.get_channel(config.channels["exp"])
                    # role_id = config.gacha_mod_role
                    # if await updateStock(ctx, sub_prize):
                    #     if not checkAdmin(ctx):
                    #         await channel.send(f"<@&{role_id}> | {ctx.author.mention} has won {exp} EXP from the Gacha! Please paste this to reward them:{chr(10)}`!give-xp {ctx.author.mention} {exp}`")
                    #     await ctx.send(f"🎉 Reward sent for reviewal: {ctx.author.mention} with **{exp} EXP**!")
                    if await updateStock(ctx, sub_prize):
                        exp_reward = addPlayerExp(user_id, exp)
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with **{'{:,}'.format(exp_reward)} EXP**!")
                    else:
                        continue
                case x if x.endswith("Ryou"):
                    ryou = int(x.rstrip(" Ryou"))
                    if await updateStock(ctx, sub_prize):
                        ryou_reward = addPlayerRyou(user_id, ryou)
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with **{'{:,}'.format(ryou_reward)} Ryou**!")
                    else:
                        continue
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
                case x if x.endswith("Energy Restores"):
                    product = "Energy Restore"
                    amount = int(x.rstrip(" Energy Restores"))
                    if await updateStock(ctx, product):
                        item_quantity = getUserItemQuantity(user_id, product)
                        if item_quantity == None:
                            ItemsDB.execute("INSERT INTO {} (item, quantity) VALUES ('{}', {})".format(f"user_{user_id}", product, 1))
                        else:
                            ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity + 1, product))
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with **{sub_prize}**!")
                    else:
                        continue
                case x if x == "1 Random Magatama":
                    magatamas_inv = getPlayerMagatamasInv(user_id)
                    magatamas_list = magatamas_inv.split(", ")
                    magatamas = list(Magatamas.keys())
                    choosing = True
                    while choosing:
                        choice = random.choice(magatamas)
                        if not choice in magatamas_list:
                            givePlayerMagatama(user_id, choice)
                            magatama_string = f"{Icons['magatama_' + Magatamas[choice]['Type'].lower().replace(' ', '_')]} **{choice}**"
                            await ctx.send(f"🎉 Rewarded {ctx.author.mention} with {magatama_string}!")
                            choosing = False
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
        e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
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
        e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
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
                e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
                e.set_image(url = Resource["Blue"][0])
            case "green":
                e.color = capsule_colors[1]
                e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
                e.set_image(url = Resource["Green"][0])
            case "red":
                e.color = capsule_colors[2]
                e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
                e.set_image(url = Resource["Red"][0])
            case "silver":
                e.color = capsule_colors[3]
                e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
                e.set_image(url = Resource["Silver"][0])
            case "gold":
                e.color = capsule_colors[4]
                e.set_thumbnail(url = Resource["Kinka_Mei-4"][0])
                e.set_image(url = Resource["Gold"][0])
            case "platinum":
                e.color = capsule_colors[5]
                e.set_thumbnail(url = Resource["Kinka_Mei-4"][0])
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
        e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
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
                        🔵  ─  *Blue*  ─  {config.encouragement[tier][0]}%\n  └ **`{getPrize(tier, 'blue')}`**\n\
                        🟢  ─  *Green*  ─  {config.encouragement[tier][1]}%\n  └ **`{getPrize(tier, 'green')}`**\n\
                        🔴  ─  *Red*  ─  {config.encouragement[tier][2]}%\n  └ **`{getPrize(tier, 'red')}`**\n\
                        ⚪  ─  *Silver*  ─  {config.encouragement[tier][3]}%\n  └ **`{getPrize(tier, 'silver')}`**\n\
                        🟡  ─  *Gold*  ─  {config.encouragement[tier][4]}%\n  └ **`{getPrize(tier, 'gold')}`**\n\
                        🟣  ─  *Platinum*  ─  {config.encouragement[tier][5]}%\n  └ **`{getPrize(tier, 'platinum')}`**\n\
                    "
                    return formatted_prize_list

                e.set_field_at(1, name = "►📜 ─────  Prize  List  ────── 📜 ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Here are today's prize pools:", color = default_color)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
                e.add_field(name = f"Tier 1: {Prizes['tier_1']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_1']['tickets_required']}", value = formatPrizeList("tier_1"), inline = True)
                e.add_field(name = f"Tier 2: {Prizes['tier_2']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_2']['tickets_required']}", value = formatPrizeList("tier_2"), inline = True)
                e.add_field(name = "\u200b", value = "\u200b", inline = True)
                e.add_field(name = f"Tier 3: {Prizes['tier_3']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_3']['tickets_required']}", value = formatPrizeList("tier_3"), inline = True)
                e.add_field(name = f"Tier 4: {Prizes['tier_4']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_4']['tickets_required']}", value = formatPrizeList("tier_4"), inline = True)
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
                        e.set_field_at(7, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                        await message.edit(embed = e)
                        await message.clear_reactions()
            case "🎰":
                e.set_field_at(2, name = "►🎰 ──── Select  a  Raffle ──── 🎰 ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                while not (exit_flag or prev_flag):
                    e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Select a Gacha Unit to spin!", color = default_color)
                    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                    e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
                    e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
                    e.add_field(name = "▷ 🥉 ───── Tier 1 Raffle ───── 🥉 ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ 🥈 ───── Tier 2 Raffle ───── 🥈 ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ 🥇 ───── Tier 3 Raffle ───── 🥇 ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ 🏅 ───── Tier 4 Raffle ───── 🏅 ◁", value = menu_separator, inline = False)
                    e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
                    await message.edit(embed = e)
                    emojis = ["🥉", "🥈", "🥇", "🏅", "↩️"]
                    reaction, user = await waitForReaction(ctx, message, e, emojis)
                    if reaction is None:
                        exit_flag = True
                        break
                    match str(reaction.emoji):
                        case "🥉":
                            tier = "tier_1"
                            e.set_field_at(1, name = "►🥉 ───── Tier 1 Raffle ───── 🥉 ◄", value = menu_separator, inline = False)
                            await message.edit(embed = e)
                            await message.clear_reactions()
                            message, e, status = await raffleEntry(ctx, message, e, tier, skip)
                            if status:
                                rolled_flag = True
                            else:
                                rolled_flag = False
                        case "🥈":
                            tier = "tier_2"
                            e.set_field_at(2, name = "►🥈 ───── Tier 2 Raffle ───── 🥈 ◄", value = menu_separator, inline = False)
                            await message.edit(embed = e)
                            await message.clear_reactions()
                            message, e, status = await raffleEntry(ctx, message, e, tier, skip)
                            if status:
                                rolled_flag = True
                            else:
                                rolled_flag = False
                        case "🥇":
                            tier = "tier_3"
                            e.set_field_at(3, name = "►🥇 ───── Tier 3 Raffle ───── 🥇 ◄", value = menu_separator, inline = False)
                            await message.edit(embed = e)
                            await message.clear_reactions()
                            message, e, status = await raffleEntry(ctx, message, e, tier, skip)
                            if status:
                                rolled_flag = True
                            else:
                                rolled_flag = False
                        case "🏅":
                            tier = "tier_4"
                            e.set_field_at(4, name = "►🏅 ───── Tier 4 Raffle ───── 🏅 ◄", value = menu_separator, inline = False)
                            await message.edit(embed = e)
                            await message.clear_reactions()
                            message, e, status = await raffleEntry(ctx, message, e, tier, skip)
                            if status:
                                rolled_flag = True
                            else:
                                rolled_flag = False
                        case "↩️":
                            prev_flag = edit_flag = True
                            e.set_field_at(5, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
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
                e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
                e.add_field(name = "Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
                e.add_field(name = "Gacha Fragments:", value = f"{Icons['fragment']} x `{'{:,}'.format(fragments)}`", inline = True)
                e.add_field(name = "Total roll count:", value = f"🎲 x `{'{:,}'.format(total_rolls)}`", inline = True)
                e.add_field(name = "Ryou D-Coins:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
                e.add_field(name = "EXP:", value = f"{Icons['exp']} x `{'{:,}'.format(exp)}`", inline = True)
                e.add_field(name = "Level:", value = f"{Icons['level']} `{'{:,}'.format(level)}`", inline = True)
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
                        e.set_field_at(5, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                        await message.edit(embed = e)
                        await message.clear_reactions()
            case "❌":
                e.set_field_at(4, name = "►❌ ─────  Exit  Menu  ─────  ❌ ◄", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                return

@bot.command(aliases = ["seed"])
@commands.check(checkChannel)
async def seeds(ctx, target = None):
    """ | Usage: +seeds [@user | top] """
    default_color = config.default_color
    global_keywords = ["global", "top", "all"]

    if target in global_keywords:
        is_global = True
    else:
        is_global = False
        if target is None:
            target = ctx.author.mention
        if re.match(r"<(@|@&)[0-9]{18,19}>", target):
            target_id = convertMentionToId(target)
        else:
            await ctx.send("Please **@ mention** a valid user to check their stats (+help seeds)")
            return

    def getTopSeeds(amount):
        top_seeds = []
        clears = getAllDungeonClears()

        seeds = []
        for clear in clears:
            seeds.append((clear[6], clear[3], clear[4]))

        if not is_global:
            founded_seeds = []
            for entry in seeds:
                filename = f"Blueprints/{entry[1]}/{config.mode_mapping[entry[2]]}/{entry[0]}.json"
                if file_exists(filename):
                    temp_blueprint = json.load(open(filename))
                    founder = temp_blueprint["footer"]["Founder"]
                    if target_id == founder:
                        founded_seeds.append(entry)
            seeds = founded_seeds

        c = Counter(seeds)

        def sortByFrequency(tup):
            return tup[1]

        sorted_seeds = list(c.items())
        sorted_seeds.sort(key = sortByFrequency, reverse=True)

        index = 0
        for entry, frequency in sorted_seeds:
            top_seeds.append({"seed": entry[0], "dungeon": entry[1], "mode": entry[2], "frequency": frequency})
            index += 1
            if index == amount:
                break
        return top_seeds

    def formatTopFrequencies(top_seeds):
        formatted_string = ""
        for index, entry in enumerate(top_seeds):
            formatted_string += f"┃ ◂ {config.numbers[index]} ▸\n"
            formatted_string += f"┃ `({entry['frequency']}x)`\n"
            if index + 1 == len(top_seeds):
                formatted_string += "┗━━━━━━\n"
            else:
                formatted_string += "┃ \n"
        return formatted_string

    def formatTopSeeds(top_seeds):
        formatted_string = ""
        for index, entry in enumerate(top_seeds):
            formatted_string += f"┃ 🌱 `{entry['seed']}`\n"
            formatted_string += f"┃ ⛩️ **__{entry['dungeon']}__**\n"
            if index + 1 == len(top_seeds):
                formatted_string += "┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            else:
                formatted_string += "┃\n"
        return formatted_string

    def formatTopModes(top_seeds):
        formatted_string = ""
        for index, entry in enumerate(top_seeds):
            formatted_string += f"┃ `-Mode-`\n"
            formatted_string += f"┃ {Icons[config.mode_mapping[entry['mode']].lower()]} ╱ **{entry['mode']}**\n"
            if index + 1 == len(top_seeds):
                formatted_string += "┻━━━━━━\n"
            else:
                formatted_string += "┃\n"
        return formatted_string

    e = discord.Embed(title = "Top ten most popular seeds", description = f"Viewing seeds founded by user: {target if not is_global else '**GLOBAL**'}", color = default_color)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
    e.add_field(name = "┏━━━━━━", value = formatTopFrequencies(getTopSeeds(10)), inline = True)
    e.add_field(name = "┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━", value = formatTopSeeds(getTopSeeds(10)), inline = True)
    e.add_field(name = "┳━━━━━━", value = formatTopModes(getTopSeeds(10)), inline = True)
    await ctx.send(embed = e)

@bot.command(aliases = ["equipment", "weapon", "magatama", "mag", "swap"])
@commands.check(checkChannel)
async def equip(ctx, *input):
    ''' | Usage: +equip [weapon name | magatama name | inv | inv mobile] '''
    user_id = ctx.author.id
    default_color = config.default_color
    argument = ' '.join(list(input))
    equipment = getPlayerEquipment(user_id)

    def formatEquippedWeapon(equipment):
        equipped = equipment["weapon"]
        weapon = Weapons[equipped]
        formatted_string = ""
        emoji = weapon["Type"].lower().replace(" ", "_")
        rarity = f"rarity_{weapon['Rarity'].lower()}"
        elements = ""
        if not weapon["Elements"] is None:
            for element in weapon["Elements"]:
                elements += f"{Icons[element]}"
        else:
            elements = "None"

        formatted_string += "──────────────────\n"
        formatted_string += f"🏷️ ─ Name: **__{equipped}__**\n"
        formatted_string += "──────────────────\n"
        formatted_string += f"{Icons[emoji]} ─ Type: **{weapon['Type']}**\n"
        formatted_string += "──────────────────\n"
        formatted_string += f"{Icons['level']} ─ Level: **{weapon['Level_Required']}**\n"
        formatted_string += "──────────────────\n"
        formatted_string += f"{Icons[rarity]} ─ Rarity: **{weapon['Rarity']}**\n"
        formatted_string += "──────────────────\n"
        formatted_string += f"{Icons['attack']} ─ Attack: **{'{:,}'.format(weapon['Attack'])}**\n"
        formatted_string += "──────────────────\n"
        formatted_string += f"⚛️ ─ Elements: **{elements}**"
        return formatted_string

    def listEquippedMagatamas(equipment):
        equipped = equipment["magatamas"]
        magatamas = []
        for magatama in equipped:
            magatamas.append((magatama, Magatamas[magatama]) if magatama != "" else ())
        return magatamas

    def getMagatamaEmoji(slot):
        magatamas = listEquippedMagatamas(equipment)
        if magatamas[slot]:
            emoji = "magatama_" + magatamas[slot][1]["Type"].lower().replace(" ", "_")
        else:
            emoji = "magatama"
        return emoji

    def getMagatamaElements(slot):
        magatamas = listEquippedMagatamas(equipment)
        elements = ""
        if magatamas[slot] and not magatamas[slot][1]["Elements"] is None:
            for index, element in enumerate(magatamas[slot][1]["Elements"]):
                if Magatamas[magatamas[slot][0]]["Elements"][element]:
                    elements += f"(+{Icons[element]})"
                else:
                    elements += f"(-{Icons[element]})"
                if index + 1 < len(magatamas[slot][1]["Elements"]):
                    elements += ", "
        else:
            elements = "None"
        return elements

    def getMagatamaSkillForce(slot):
        magatamas = listEquippedMagatamas(equipment)
        sf = 0
        if "Skill Force" in magatamas[slot][1]["Effects"]:
            sf = magatamas[slot][1]["Effects"]["Skill Force"]
        return sf

    def getMagatamaCriticalRate(slot):
        magatamas = listEquippedMagatamas(equipment)
        critical = 0
        if "Critical" in magatamas[slot][1]["Effects"]:
            critical = magatamas[slot][1]["Effects"]["Critical"]
        return critical

    def formatEquippedMagatamas(equipment):
        magatamas = listEquippedMagatamas(equipment)
        formatted_string = ""

        formatted_string += "──────────────────\n"
        for slot, magatama in enumerate(magatamas):
            if magatama:
                formatted_string += f"📍 **Slot {slot + 1}:** {Icons[getMagatamaEmoji(slot)]} **__{magatamas[slot][0]}__**\n"
                formatted_string += f" ╰─  Level: **{magatamas[slot][1]['Level_Required']}**\n"
                formatted_string += f" ╰─  Chakra: **{magatamas[slot][1]['Chakra']}**\n"
                formatted_string += f" ╰─  Defence: **{'{:,}'.format(magatamas[slot][1]['Defence'])}**\n"
                if not magatamas[slot][1]["Elements"] is None:
                    formatted_string += f" ╰─  Elements: **{getMagatamaElements(slot)}**\n"
                if "Skill Force" in magatamas[slot][1]["Effects"]:
                    formatted_string += f" ╰─  Skill Force: **+{getMagatamaSkillForce(slot)}%**\n"
                if "Critical" in magatamas[slot][1]["Effects"]:
                    formatted_string += f" ╰─  Critical: **+{getMagatamaCriticalRate(slot)}%**\n"
                formatted_string += "──────────────────\n"
            else:
                formatted_string += f"{Icons[getMagatamaEmoji(slot)]} ─ Slot {slot + 1}: None\n"
                formatted_string += "──────────────────\n"
        return formatted_string

    def formatWeaponInventory(offset, size, half, is_compact):
        weapons_inv = getPlayerWeaponsInv(user_id)
        weapons_list = weapons_inv.split(", ")
        formatted_string = ""
        counter = 0
        size = math.floor(size / 2)
        if half == "second":
            offset += size
        if weapons_inv and not offset >= len(weapons_list):
            for index, weapon in enumerate(weapons_list):
                if index < offset:
                    # Skipping to next entry until arriving at the proper page/offset
                    continue
                lvl = Weapons[weapon]["Level_Required"]
                elements = ""
                if not Weapons[weapon]["Elements"] is None:
                    for index, element in enumerate(Weapons[weapon]["Elements"]):
                        elements += f"{Icons[element]}"
                        if index + 1 < len(Weapons[weapon]["Elements"]):
                            elements += ", "
                else:
                    elements = "None"
                if not is_compact:
                    formatted_string += f"{Icons[Weapons[weapon]['Type'].lower().replace(' ', '_')]} ┃ **__{weapon}__**\n"
                    formatted_string += f" ╰─  *Rarity:* {Icons['rarity_' + Weapons[weapon]['Rarity'].lower()]}\n"
                    formatted_string += f" ╰─  *Level:* **{lvl}**\n"
                    formatted_string += f" ╰─  *Attack:* **{Weapons[weapon]['Attack']}**\n"
                    formatted_string += f" ╰─  *Elements:* **{elements}**\n"
                else:
                    formatted_string += f"{Icons[Weapons[weapon]['Type'].lower().replace(' ', '_')]} ┃ **__{weapon}__** {Icons['rarity_' + Weapons[weapon]['Rarity'].lower()]}\n"
                counter += 1
                # Once a full page is assembled, print it
                if counter == size or index + 1 == len(weapons_list):
                    break
        else:
            formatted_string = "**None**"
        return formatted_string

    def formatMagatamaInventory(offset, size, half, is_compact):
        magatamas_inv = getPlayerMagatamasInv(user_id)
        magatamas_list = magatamas_inv.split(", ")
        formatted_string = ""
        counter = 0
        size = math.floor(size / 2)
        if half == "second":
            offset += size
        if magatamas_inv and not offset >= len(magatamas_list):
            for index, magatama in enumerate(magatamas_list):
                if index < offset:
                    # Skipping to next entry until arriving at the proper page/offset
                    continue
                lvl = Magatamas[magatama]["Level_Required"]
                chakra = Magatamas[magatama]["Chakra"]
                defence = Magatamas[magatama]["Defence"]
                sf = Magatamas[magatama]["Effects"]["Skill Force"] if "Skill Force" in Magatamas[magatama]["Effects"] else 0
                critical = Magatamas[magatama]["Effects"]["Critical"] if "Critical" in Magatamas[magatama]["Effects"] else 0
                elements = ""
                if not Magatamas[magatama]["Elements"] is None:
                    for index, element in enumerate(Magatamas[magatama]["Elements"]):
                        if Magatamas[magatama]["Elements"][element]:
                            elements += f"+{Icons[element]}"
                        else:
                            elements += f"-{Icons[element]}"
                        if index + 1 < len(Magatamas[magatama]["Elements"]):
                            elements += ", "
                else:
                    elements = "None"
                type = Magatamas[magatama]["Type"].lower().replace(" ", "_")
                if not is_compact:
                    formatted_string += f"{Icons['magatama_' + type]} ┃ **__{magatama}__**\n"
                    formatted_string += f" ╰─  *Level:* **{lvl}** ┃ *Chakra:* **{chakra}**\n"
                    formatted_string += f" ╰─  *Defence:* **{defence}**\n"
                    if not Magatamas[magatama]["Elements"] is None:
                        formatted_string += f" ╰─  *Elements:* **{elements}**\n"
                    if "Skill Force" in Magatamas[magatama]["Effects"]:
                        formatted_string += f" ╰─  *Skill Force:* **+{sf}%**\n"
                    if "Critical" in Magatamas[magatama]["Effects"]:
                        formatted_string += f" ╰─  *Critical:* **+{critical}%**\n"
                else:
                    formatted_string += f"{Icons['magatama_' + type]} ┃ **__{magatama}__**\n"
                counter += 1
                # Once a full page is assembled, print it
                if counter == size or index + 1 == len(magatamas_list):
                    break
        else:
            formatted_string = "**None**"
        return formatted_string

    if not input:
        level = getPlayerLevel(user_id)
        chakra = getPlayerChakra(user_id)
        commands = ["", "Equip a weapon/magatama:", "(+equip <item name>)", "", "View your inventory:", "(+equip inv [mobile])", "", "Clear your magatama slots:", "(+equip clear)", ""]
        e = discord.Embed(title = "🛠️ ─ Equipment Screen ─ 🛠️", description = f"Viewing equipment of <@{user_id}> ┃ *Chakra* = **{chakra} / {level}**", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.add_field(name = "⚔️ ─ Equipped Weapon ─ ⚔️", value = formatEquippedWeapon(equipment), inline = True)
        e.add_field(name = f"{Icons['magatama']} ─ Equipped Magatamas ─ {Icons['magatama']}", value = formatEquippedMagatamas(equipment), inline = True)
        e.add_field(name = "Commands:", value = boxifyArray(commands, padding = 2), inline = False)
        await ctx.send(embed = e)
    else:
        if argument.startswith("inventory") or argument.startswith("inv"):

            def getSeparator(is_compact):
                separator = ""
                length = 5 if not is_compact else 1
                for _ in range(0, math.floor(size / 2) * length + 1):
                    separator += "┃\n"
                return separator

            if argument.endswith(("compact", "mobile", "short", "small", "phone")):
                is_mobile = True
            else:
                is_mobile = False

            is_compact = False
            message = None
            level = getPlayerLevel(user_id)
            chakra = getPlayerChakra(user_id)
            w_length = len(getPlayerWeaponsInv(user_id).split(", "))
            m_length = len(getPlayerMagatamasInv(user_id).split(", "))
            w_offset = 0
            m_offset = 0
            size = 6

            flag = True
            # Set offset to 0 (page 1) and begin bidirectional page system
            while flag:
                e = discord.Embed(title = "🛠️ ─ Equipment Screen ─ 🛠️", description = f"Viewing inventory of <@{user_id}> ┃ *Chakra* = **{chakra} / {level}**", color = default_color)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                if not is_mobile:
                    half = "first"
                    e.add_field(name = "Weapon Inventory:\n━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━", value = formatWeaponInventory(w_offset, size, half, is_compact), inline = True)
                    e.add_field(name = "┃", value = getSeparator(is_compact), inline = True)
                    e.add_field(name = "Magatama Inventory:\n━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━", value = formatMagatamaInventory(m_offset, size, half, is_compact), inline = True)
                    half = "second"
                    e.add_field(name = "─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─", value = formatWeaponInventory(w_offset, size, half, is_compact), inline = True)
                    e.add_field(name = "┃", value = getSeparator(is_compact), inline = True)
                    e.add_field(name = "─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─", value = formatMagatamaInventory(m_offset, size, half, is_compact), inline = True)
                else:
                    half = "first"
                    e.add_field(name = "Weapon Inventory:\n━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━", value = formatWeaponInventory(w_offset, size, half, is_compact), inline = False)
                    half = "second"
                    e.add_field(name = "─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─", value = formatWeaponInventory(w_offset, size, half, is_compact), inline = False)
                    half = "first"
                    e.add_field(name = "Magatama Inventory:\n━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━", value = formatMagatamaInventory(m_offset, size, half, is_compact), inline = False)
                    half = "second"
                    e.add_field(name = "─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─", value = formatMagatamaInventory(m_offset, size, half, is_compact), inline = False)
                e.set_footer(text = f"Page: {max(math.floor(w_offset / size) + 1, math.floor(m_offset / size) + 1)}/{max(math.ceil(w_length / size), math.ceil(m_length / size))}")
                message = await ctx.send(embed = e) if message == None else await message.edit(embed = e)
                emojis = ["⏪", "⏩", "📏", "📱", "❌"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                if reaction is None:
                    flag = False
                    break
                match str(reaction.emoji):
                    case "⏩":
                        if not w_offset + size >= w_length or not m_offset + size >= m_length:
                            # Tell upcomming re-iteration to skip to the next page's offset
                            if not w_offset + size >= w_length:
                                if w_length > size:
                                    w_offset += size
                            if not m_offset + size >= m_length:
                                if m_length > size:
                                    m_offset += size
                        else:
                            # Skip to the first page
                            w_offset = 0
                            m_offset = 0
                        await message.clear_reactions()
                        continue
                    case "⏪":
                        if not w_offset == 0 or not m_offset == 0:
                            # Tell upcomming re-iteration to skip to the previous page's offset
                            if not w_offset == 0:
                                if w_offset >= size:
                                    w_offset -= size
                            if not m_offset == 0:
                                if m_offset >= size:
                                    m_offset -= size
                        else:
                            # Skip to the last page
                            w_offset = size * math.floor(w_length / size)
                            m_offset = size * math.floor(m_length / size)
                        await message.clear_reactions()
                        continue
                    case "📏":
                        is_compact = True if not is_compact else False
                        await message.clear_reactions()
                    case "📱":
                        is_mobile = True if not is_mobile else False
                        await message.clear_reactions()
                    case "❌":
                        await message.clear_reactions()
                        flag = False
                        break
        elif argument == "clear" or argument == "reset":
            clearPlayerEquipment(user_id)
            await ctx.reply("You have successfully cleared your equipment slots!")
        else:
            weapon = [w for w in Weapons if argument.casefold() == w.casefold()]
            magatama = [m for m in Magatamas if argument.casefold() == m.casefold()]
            if weapon:
                weapon = weapon[0]
                weapon_string = f"{Icons[Weapons[weapon]['Type'].lower().replace(' ', '_')]} **{weapon}** {Icons['rarity_' + Weapons[weapon]['Rarity'].lower()]}"
                weapons_inv = getPlayerWeaponsInv(user_id)
                weapons_list = weapons_inv.split(", ")
                if weapon in weapons_list:
                    level = getPlayerLevel(user_id)
                    if level >= Weapons[weapon]["Level_Required"]:
                        equipWeapon(user_id, weapon)
                        await ctx.reply(f"You equipped {weapon_string}")
                    else:
                        await ctx.reply(f"You are not high enough level to wield: {weapon_string}" + "\n" + \
                        f"*Your level:* {Icons['level']}**{level}**" + "\n" + \
                        f"*Level Required:* {Icons['level']}**{Weapons[weapon]['Level_Required']}**")
                else:
                    await ctx.reply(f"You don't own: {weapon_string}")
            elif magatama:
                magatama = magatama[0]
                magatama_string = f"{Icons['magatama_' + Magatamas[magatama]['Type'].lower().replace(' ', '_')]} **__{magatama}__**"
                magatamas_inv = getPlayerMagatamasInv(user_id)
                magatamas_list = magatamas_inv.split(", ")
                slots = listEquippedMagatamas(equipment)
                level = getPlayerLevel(user_id)
                chakra = getPlayerChakra(user_id)
                if magatama in magatamas_list:
                    if level >= Magatamas[magatama]["Level_Required"]:
                        if chakra + Magatamas[magatama]["Chakra"] <= level:
                            if not magatama in [m[0] for m in slots if m]:
                                e = discord.Embed(title = f"{Icons['magatama']} ─ Equip Magatama ─ {Icons['magatama']}", description = f"Select a slot to equip {magatama_string} into:", color = default_color)
                                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                                e.add_field(name = "1️⃣ ─ Slot 1", value = f"{Icons[getMagatamaEmoji(0)]} **{slots[0][0] if slots[0] else 'None'}**", inline = True)
                                e.add_field(name = "2️⃣ ─ Slot 2", value = f"{Icons[getMagatamaEmoji(1)]} **{slots[1][0] if slots[1] else 'None'}**", inline = True)
                                e.add_field(name = "\u200b", value = "\u200b", inline = True)
                                e.add_field(name = "3️⃣ ─ Slot 3", value = f"{Icons[getMagatamaEmoji(2)]} **{slots[2][0] if slots[2] else 'None'}**", inline = True)
                                e.add_field(name = "4️⃣ ─ Slot 4", value = f"{Icons[getMagatamaEmoji(3)]} **{slots[3][0] if slots[3] else 'None'}**", inline = True)
                                e.add_field(name = "\u200b", value = "\u200b", inline = True)
                                message = await ctx.send(embed = e)
                                emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "🚫"]
                                reaction, user = await waitForReaction(ctx, message, e, emojis)
                                if reaction is None:
                                    return
                                match str(reaction.emoji):
                                    case "1️⃣":
                                        await message.clear_reactions()
                                        slot = 1
                                    case "2️⃣":
                                        await message.clear_reactions()
                                        slot = 2
                                    case "3️⃣":
                                        await message.clear_reactions()
                                        slot = 3
                                    case "4️⃣":
                                        await message.clear_reactions()
                                        slot = 4
                                    case "🚫":
                                        await message.clear_reactions()
                                        return
                                equipMagatama(user_id, magatama, slot)
                                await ctx.reply(f"You equipped {magatama_string} to **Slot {slot}**")
                            else:
                                await ctx.reply(f"You already have {magatama_string} equipped!")
                        else:
                            await ctx.reply(f"You don't have enough chakra to equip {magatama_string}! (Overshot by **{(chakra + Magatamas[magatama]['Chakra']) - level}**)")
                    else:
                        await ctx.reply(f"You are not high enough level to equip: {magatama_string}" + "\n" + \
                        f"*Your level:* {Icons['level']}**{level}**" + "\n" + \
                        f"*Level Required:* {Icons['level']}**{Magatamas[magatama]['Level_Required']}**")
                else:
                    await ctx.reply(f"You don't own: {magatama_string}")

            else:
                await ctx.reply(f"There were no matches found for `{argument}`")

@bot.command(aliases = ["wl"])
@commands.check(checkChannel)
async def whitelist(ctx, target = None, percent = None):
    ''' | Usage: +whitelist <@user> [discount%]'''
    if percent is None:
        percent = 100
    try:
        percent = int(percent)
    except ValueError:
        await ctx.send(f"Please input a valid **integer** as the tax discount ({config.prefix}help whitelist)")
        return
    user_id = ctx.author.id
    if not target is None and not target == ctx.author.mention and re.match(r"<(@|@&)[0-9]{18,19}>", target):
        target_id = convertMentionToId(target)
        whitelist = getUserWhitelist(user_id)
        percent = 100 if percent > 100 else percent
        percent = 0 if percent < 0 else percent
        wl_exists = False
        for wl in whitelist:
            if target_id in wl:
                wl_exists = True
                break
        if not wl_exists:
            WhitelistDB.execute("INSERT INTO {} (user_id, percent) VALUES ({}, {})".format(f"user_{user_id}", target_id, percent))
        else:
            WhitelistDB.execute("UPDATE {} SET percent = {} WHERE user_id = {}".format(f"user_{user_id}", percent, target_id))
        await ctx.send(f"✅ Successfully added <@{target_id}> to your whitelist with a tax discount of **{percent}%**")
    else:
        await ctx.send("Please **@ mention** a valid user to check their stats (+help whitelist)")

@bot.command(aliases = ["speedrun", "best", "times", "fastest"])
@commands.check(checkChannel)
async def records(ctx, *input):
    ''' | Usage: +records <dungeon name> '''
    default_color = config.default_color

    def sortRecords(records):
        records.sort(key = lambda tup: tup[5])
        _records = [[], [], [], []]
        _users = [[], [], [], []]
        for record in records:
            mode = record[4]
            user = record[1]
            if len(_records[mode]) >= 5 or user in _users[mode]:
                continue
            _records[mode].append(record)
            _users[mode].append(user)
        return _records

    def formatRecordUsers(records):
        formatted_string = ""
        for index, record in enumerate(records):
            match index:
                case 0:
                    emoji = "🥇"
                case 1:
                    emoji = "🥈"
                case 2:
                    emoji = "🥉"
                case _:
                    emoji = "🏅"
            formatted_string += f"{emoji} | <@{record[1]}>\n"
        return formatted_string if formatted_string != "" else "None"

    def formatRecordDividers(records):
        formatted_string = ""
        for _ in records:
            formatted_string += "─\n"
        return formatted_string if formatted_string != "" else "\u200b"

    def formatRecordTimes(records):
        formatted_string = ""
        for record in records:
            formatted_string += f"__{record[5]}__\n"
        return formatted_string if formatted_string != "" else "None"

    if input:
        dg = ' '.join(list(input))
        for dungeon in Dungeons:
            if dg.casefold() == dungeon.casefold():
                records = sortRecords(getDungeonRecords(dungeon))
                e = discord.Embed(title = f"⏱️ ─ __{dungeon}__ ─ ⏱️", description = "Top 5 global records for each difficulty:", color = default_color)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])

                e.add_field(name = "Normal:", value = formatRecordUsers(records[0]), inline = True)
                e.add_field(name = "\u200b", value = formatRecordDividers(records[0]), inline = True)
                e.add_field(name = "Times:", value = formatRecordTimes(records[0]), inline = True)

                e.add_field(name = "Hard:", value = formatRecordUsers(records[1]), inline = True)
                e.add_field(name = "\u200b", value = formatRecordDividers(records[1]), inline = True)
                e.add_field(name = "Times:", value = formatRecordTimes(records[1]), inline = True)

                e.add_field(name = "Hell:", value = formatRecordUsers(records[2]), inline = True)
                e.add_field(name = "\u200b", value = formatRecordDividers(records[2]), inline = True)
                e.add_field(name = "Times:", value = formatRecordTimes(records[2]), inline = True)

                e.add_field(name = "Oni:", value = formatRecordUsers(records[3]), inline = True)
                e.add_field(name = "\u200b", value = formatRecordDividers(records[3]), inline = True)
                e.add_field(name = "Times:", value = formatRecordTimes(records[3]), inline = True)

                await ctx.send(embed = e)
                return
    await ctx.send(f"Please provide a **valid dungeon name** to see the records of.\nYou can list all the available dungeons with the `{config.prefix}dg` command.")

@bot.command(aliases = ["use", "item", "energy", "refill", "recharge"])
@commands.check(checkChannel)
async def restore(ctx):
    ''' | Usage: +restore '''
    user_id = ctx.author.id
    energy = getPlayerEnergy(user_id)
    max_energy = getPlayerMaxEnergy(user_id)
    product = "Energy Restore"
    item_quantity = getUserItemQuantity(user_id, product)
    if not item_quantity is None and item_quantity > 0:
        e = discord.Embed(title = "Energy Restoration", description = "Will you use 1 Energy Restore to recover your energy?")
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
        e.add_field(name = "Current Energy", value = f"{Icons['energy']} **{energy}**")
        e.add_field(name = "Energy after restoring", value = f"{Icons['energy']} **{max_energy}**")
        message = await ctx.send(embed = e)
        emojis = ["✅", "❌"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            return
        match str(reaction.emoji):
            case "✅":
                await message.clear_reactions()
                ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity - 1, product))
                if item_quantity - 1 == 0:
                    ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(user_id), product))
                addPlayerEnergy(user_id, max_energy)
                await ctx.send(f"{ctx.author.mention} used 1 **{product}** to fully restore their energy!")
                return
            case "❌":
                await message.clear_reactions()
                return
    else:
        await ctx.send(f"You do not have any **{product}s** to use!")
        return

@bot.command(aliases = ["stat", "level", "levelup", "lvl", "lvlup", "allocate"])
@commands.check(checkChannel)
async def stats(ctx, target = None):
    ''' | Usage: +stats [@user] | Check and allocate stat points '''

    def formatPlayerStats(user_id):
        HP = getPlayerHP(user_id)
        ATK = getPlayerATK(user_id)
        DEF = getPlayerDEF(user_id)
        weapon_ATK = Weapons[getPlayerEquipment(user_id)["weapon"]]["Attack"]
        player_stats = ["", f"{user.name}", f"Total HP: {HP}", f"Total ATK: {ATK} (+{weapon_ATK})", f"Total DEF: {DEF}", ""]
        return player_stats

    def formatPlayerPoints(user_id):
        stat_points = getPlayerStatPoints(user_id)
        player_points = ["", f"Points: {stat_points['points']}", f"HP Points: {stat_points['hp']}", f"ATK Points: {stat_points['atk']}", f"DEF Points: {stat_points['def']}", ""]
        return player_points

    # main()
    if target is None:
        target = ctx.author.mention
    if re.match(r"<(@|@&)[0-9]{18,19}>", target):
        flag = True
        message = None
        while flag:
            user_id         = convertMentionToId(target)
            user            = await bot.fetch_user(user_id)
            default_color   = config.default_color
            exp             = getPlayerExp(user_id)
            level           = getPlayerLevel(user_id)
            exp_to_next     = getPlayerExpToNextLevel(user_id)
            player_stats    = formatPlayerStats(user_id)
            player_points   = formatPlayerPoints(user_id)
            stat_points     = getPlayerStatPoints(user_id)
            points = stat_points["points"]
            e = discord.Embed(title = "Viewing stats of user:", description = target, color = default_color)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
            e.add_field(name = "Current Level", value = f"{Icons['level']} **{level}**", inline = True)
            e.add_field(name = "Current EXP", value = f"{Icons['exp']} **{'{:,}'.format(exp)}**", inline = True)
            e.add_field(name = "EXP to next level", value = f"{Icons['exp']} **{'{:,}'.format(exp_to_next)}**", inline = True)
            e.add_field(name = "📊 Player Stats:", value = boxifyArray(player_stats, padding = 2), inline = True)
            e.add_field(name = "🧮 Allocated Stat Points:", value = boxifyArray(player_points, padding = 2), inline = True)
            e.add_field(name = "\u200b", value = "────────────────────────────────", inline = False)
            message = await ctx.send(embed = e) if message == None else await message.edit(embed = e)
            if target == ctx.author.mention and points > 0:
                e.add_field(name = f"You have `{points}` unallocated stat points!", value = "Choose a Stat to increment:", inline = True)
                e.add_field(name = "│ Stat options:", value = "**│** 🩸 ─ **HP**\n**│** ⚔️ ─ **ATK**\n**│** 🛡️ ─ **DEF**", inline = True)
                await message.edit(embed = e)
                emojis = ["🩸", "⚔️", "🛡️", Icons["statsreset"], "❌"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                if reaction is None:
                    return
                match str(reaction.emoji):
                    case "🩸":
                        await message.clear_reactions()
                        addPlayerStatPoints(user_id, "hp", 1)
                        addPlayerStatPoints(user_id, "points", -1)
                    case "⚔️":
                        await message.clear_reactions()
                        addPlayerStatPoints(user_id, "atk", 1)
                        addPlayerStatPoints(user_id, "points", -1)
                    case "🛡️":
                        await message.clear_reactions()
                        addPlayerStatPoints(user_id, "def", 1)
                        addPlayerStatPoints(user_id, "points", -1)
                    case x if x == Icons["statsreset"]:
                        await message.clear_reactions()
                        product = "Stats Reset"
                        item_quantity = getUserItemQuantity(user_id, product)
                        e.description = "Will you reset your stats?"
                        e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
                        e.add_field(name = f"{Icons['statsreset']} Confirmation: Will you reset your stat points?", value = f"(You have `{item_quantity if not item_quantity is None else 0}` Stats Reset uses.)", inline = False) # Field 8
                        await message.edit(embed = e)
                        emojis = ["✅", "❌"]
                        reaction, user = await waitForReaction(ctx, message, e, emojis)
                        if reaction is None:
                            return
                        match str(reaction.emoji):
                            case "✅":
                                await message.clear_reactions()
                                if not item_quantity is None and item_quantity > 0:
                                    StatsDB.execute(f"DELETE FROM userdata WHERE user_id = {user_id}")
                                    ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity - 1, product))
                                    if item_quantity - 1 == 0:
                                        ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(user_id), product))
                                    e.add_field(name = "✅ Success!", value = "Your points have been successfuly reset.", inline = False) # Field 9
                                    await message.edit(embed = e)
                                    time.sleep(4)
                                    e.remove_field(9)
                                    e.remove_field(8)
                                else:
                                    e.add_field(name = "❌ Failure!", value = "You don't have any Stats Reset uses, you can buy one from the Market.", inline = False) # Field 9
                                    await message.edit(embed = e)
                                    time.sleep(4)
                                    e.remove_field(8)
                            case "❌":
                                await message.clear_reactions()
                                e.remove_field(8)
                    case "❌":
                        await message.clear_reactions()
                        return
            else:
                e.add_field(name = f"You have `{points}` available stat points.", value = "Choose an option:", inline = True)
                e.add_field(name = "│ Options:", value = f"**│** {Icons['statsreset']} ─ **Reset Stats**\n**│** ❌ ─ **Exit**\n", inline = True)
                await message.edit(embed = e)
                emojis = [Icons["statsreset"], "❌"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                if reaction is None:
                    return
                match str(reaction.emoji):
                    case x if x == Icons["statsreset"]:
                        await message.clear_reactions()
                        product = "Stats Reset"
                        item_quantity = getUserItemQuantity(user_id, product)
                        e.description = "Will you reset your stats?"
                        e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
                        e.add_field(name = f"{Icons['statsreset']} Confirmation: Will you reset your stat points?", value = f"(You have `{item_quantity if not item_quantity is None else 0}` Stats Reset uses.)", inline = False) # Field 8
                        await message.edit(embed = e)
                        emojis = ["✅", "❌"]
                        reaction, user = await waitForReaction(ctx, message, e, emojis)
                        if reaction is None:
                            return
                        match str(reaction.emoji):
                            case "✅":
                                await message.clear_reactions()
                                if not item_quantity is None and item_quantity > 0:
                                    StatsDB.execute(f"DELETE FROM userdata WHERE user_id = {user_id}")
                                    ItemsDB.execute("UPDATE user_{} SET quantity = {} WHERE item = '{}'".format(str(user_id), item_quantity - 1, product))
                                    if item_quantity - 1 == 0:
                                        ItemsDB.execute("DELETE FROM user_{} WHERE item = '{}'".format(str(user_id), product))
                                    e.add_field(name = "✅ Success!", value = "Your points have been successfuly reset.", inline = False) # Field 9
                                    await message.edit(embed = e)
                                    time.sleep(4)
                                    e.remove_field(9)
                                    e.remove_field(8)
                                else:
                                    e.add_field(name = "❌ Failure!", value = "You don't have any Stats Reset uses, you can buy one from the Market.", inline = False) # Field 9
                                    await message.edit(embed = e)
                                    time.sleep(4)
                                    e.remove_field(8)
                            case "❌":
                                await message.clear_reactions()
                                e.remove_field(8)
                    case "❌":
                        await message.clear_reactions()
                        return
                flag = False
    else:
        await ctx.send("Please **@ mention** a valid user to check their stats (+help stats)")

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
        e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
        e.add_field(name = "Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
        e.add_field(name = "Gacha Fragments:", value = f"{Icons['fragment']} x `{'{:,}'.format(fragments)}`", inline = True)
        e.add_field(name = "Total roll count:", value = f"🎲 x `{'{:,}'.format(total_rolls)}`", inline = True)
        e.add_field(name = "Ryou D-Coins:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
        e.add_field(name = "EXP:", value = f"{Icons['exp']} x `{'{:,}'.format(exp)}`", inline = True)
        e.add_field(name = "Level:", value = f"{Icons['level']} `{'{:,}'.format(level)}`", inline = True)
        e.add_field(name = "Energy:", value = f"{Icons['energy']} `{'{:,}'.format(energy)}`", inline = True)
        e.add_field(name = "Dungeons cleared:", value = f"{Icons['dungeon']} `{'{:,}'.format(total_clears)}`", inline = True)
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
    e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
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
                e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
                e.add_field(name = "Used fragments:", value = f"🧩 x {craft_amount * 4}", inline = False)
                e.add_field(name = "You now have this many Gacha Tickets:", value = f"🎟️ x {tickets + craft_amount}", inline = False)
                await ctx.send(embed = e)
                # Add crafted tickets to and subtract used fragments from database
                GachaDB.userdata[user_id] = {"gacha_tickets": tickets + craft_amount, "gacha_fragments": fragments - craft_amount * 4, "total_rolls": total_rolls}
            else:
                e = discord.Embed(title = "Crafting Result", description = "❌ Craft failed!", color = 0x00897b)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
                e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
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
    e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
    exit_flag = edit_flag = False
    if history_length == 0:
        e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
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

        if item == "weapon":
            weapon = quantity
            for w in Weapons:
                if weapon.casefold() == w.casefold():
                    user_id = convertMentionToId(target)
                    weapons_inv = getPlayerWeaponsInv(user_id)
                    weapons_list = weapons_inv.split(", ")
                    weapon_string = f"{Icons[Weapons[w]['Type'].lower().replace(' ', '_')]} **{w}**"
                    if not w in weapons_list:
                        givePlayerWeapon(user_id, w)
                        await ctx.send(f"Rewarded {target} with {weapon_string}!")
                    else:
                        await ctx.send(f"User already has {weapon_string}!")
                    return
            await ctx.send("Please enter a **valid weapon name** to reward.")
            return
        elif item == "magatama":
            magatama = quantity
            for m in Magatamas:
                if magatama.casefold() == m.casefold():
                    user_id = convertMentionToId(target)
                    magatamas_inv = getPlayerMagatamasInv(user_id)
                    magatamas_list = magatamas_inv.split(", ")
                    magatama_string = f"{Icons['magatama_' + Magatamas[m]['Type'].lower().replace(' ', '_')]} **{m}**"
                    if not m in magatamas_list:
                        givePlayerMagatama(user_id, m)
                        await ctx.send(f"Rewarded {target} with {magatama_string}!")
                    else:
                        await ctx.send(f"User already has {magatama_string}!")
                    return
            await ctx.send("Please enter a **valid magatama name** to reward.")
            return
        else:
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
                        await ctx.send(f"Rewarded {target} with {Icons['ryou']} `{quantity}` **Ryou D-Coin(s)**! User now has a total of `{ryou + quantity}`.")
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

# @bot.command()
# @commands.is_owner()
# async def findgolddaruma(ctx):
#     for f in Blueprint["blueprint"]["floors"]:
#         if f["type"] == "Floor":
#             for r in f["rooms"]:
#                 if r["type"] == "Normal":
#                     if "Gold Daruma" in r["yokai"]:
#                         print(dg.seed)

@bot.command()
@commands.is_owner()
async def test(ctx):
    pass

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
