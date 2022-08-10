### Gacha Bot for Onigiri
### Created by pianosuki
### https://github.com/pianosuki
### For use by Catheon only
branch_name = "Onigiri"
bot_version = "1.8"
debug_mode  = False

import config, dresource
from database import Database
import discord, re, time, random, json, math
from discord.ext import commands
from datetime import datetime
import numpy as np
from collections import Counter

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

# Player Stats
PlayerDB = Database("playerdata.db")
PlayerDB.execute("CREATE TABLE IF NOT EXISTS userdata (user_id INTEGER PRIMARY KEY UNIQUE, exp INTEGER)")

# Objects
Prizes      = json.load(open("prizes.json")) # Load list of prizes for the gacha to pull from
Products    = json.load(open("products.json")) # Load list of products for shop to sell
Graphics    = json.load(open("graphics.json")) # Load list of graphical assets to build Resource with
Quests      = json.load(open("quests.json")) # Load list of quests for the questing system
Tables      = json.load(open("tables.json")) # Load tables for systems to use constants from
Resource    = dresource.resCreate(Graphics) # Generate discord file attachment resource
Icons       = config.custom_emojis

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
    PlayerDB.execute("INSERT OR IGNORE INTO userdata (user_id, exp) VALUES (%s, '0')" % str(user_id))
    playerdata = PlayerDB.query(f"SELECT * FROM userdata WHERE user_id = '{user_id}'")
    return playerdata

def getPlayerExp(user_id):
    PlayerDB.execute("INSERT OR IGNORE INTO userdata (user_id, exp) VALUES (%s, '0')" % str(user_id))
    exp = PlayerDB.query(f"SELECT exp FROM userdata WHERE user_id = '{user_id}'")[0][0]
    return exp

def addPlayerExp(user_id, exp_reward):
    ExpTable = Tables["ExpTable"]
    exp = getPlayerExp(user_id)
    max_exp = ExpTable[config.level_cap - 1][1]
    if exp + exp_reward > max_exp:
        exp_reward -= (exp + exp_reward - max_exp)
    PlayerDB.execute("UPDATE userdata SET exp = ? WHERE user_id = ?", (exp + exp_reward, user_id))
    return exp_reward

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
        refill = (100 - total) / relevant_length
        index = 0
        hot_weights = cold_weights
        for i in hot_weights:
            if i > 0:
                hot_weights[index] = i + refill
            index +=1
        return hot_weights
    else:
        return cold_weights

def generateFileObject(object, path):
    Resource[object][1] = discord.File(path)
    return Resource[object][1]

### User Commands
# @bot.command(aliases = ["dungeon", "dg", "dung", "run", "warding", "wardings"])
# @commands.check(checkChannel)
# async def dungeons(ctx):
#     ''' | Usage: +dungeons '''
#     user_id         = ctx.author.id
#     await ctx.send("test")

@bot.command(aliases = ["quest", "questing", "subquest", "subquests", "sidequest", "sidequests", "mission", "missions"])
@commands.check(checkChannel)
async def quests(ctx, arg: str = None):
    ''' | Usage: +quests [collect]'''
    user_id         = ctx.author.id
    default_color   = config.default_color
    last_quest      = getLastQuest(user_id)
    wait            = 0 if checkAdmin(ctx) and debug_mode else config.quest_wait
    now             = int(time.time())
    def chooseRandomQuest():
        while True:
            choice = random.choice(list(Quests))
            level = getPlayerLevel(user_id)
            if Quests[choice]["Level_Required"] > level:
                continue
            else:
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
                await message.clear_reactions()
                message, flag = await startQuest(ctx, message, flag, quest, e)
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
                            case 0:
                                difficulty = "Any"
                            case 1:
                                difficulty = "Normal"
                            case 2:
                                difficulty = "Hard"
                            case 3:
                                difficulty = "Hell"
                            case 4:
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
    if now >= last_quest + wait:
        quest = chooseRandomQuest()
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
                    ryou_traded = int(math.floor(ryou / conv_rate[0]) * conv_rate[0])
                    tickets_traded = int(math.floor(ryou / conv_rate[0]) * conv_rate[1])
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
                    ryou_traded = int(math.floor(tickets / conv_rate[1]) * (conv_rate[0] / 10))
                    tickets_traded = int(tickets)
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
        while flag:
            e = discord.Embed(title = f"Welcome to the {branch_name} Shop!", description = "Select a product to purchase:", color = default_color)
            e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
            e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
            emojis = []
            for index, product in enumerate(Products):
                e.add_field(name = f"{numbers[index]}  -  ***{product}***", value = f"╰ Price: {Icons['ryou']} x `{'{:,}'.format(Products[product]['Price'])}`", inline = True)
                emojis.append(numbers[index])
            await message.edit(embed = e)
            emojis.append("↩️")
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                flag = False
                return message, flag
            match str(reaction.emoji):
                case number_emoji if number_emoji in numbers:
                    await message.clear_reactions()
                    product_index = getProductIndex(number_emoji)
                    product = getProduct(product_index)
                    if product is None:
                        await ctx.send("The product you chose could not be loaded!")
                        flag = False
                    else:
                        message, flag = await selectProduct(ctx, message, flag, product)
                case "↩️":
                    await message.clear_reactions()
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

    def getProductIndex(number_emoji):
        for n, emoji in enumerate(numbers):
            if number_emoji == emoji:
                product_index = n
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

# @bot.command(aliases = ["gacha", "spin"])
# @commands.check(checkChannel)
# async def roll(ctx, skip=None):
#     ''' | Usage: +roll | Use reactions to navigate the menus '''
#     user_id         = ctx.author.id
#     menu_top        = config.menu_top
#     menu_separator  = config.menu_separator
#     menu_bottom     = config.menu_bottom
#     default_color   = config.default_color
#     colors          = config.colors
#     capsules        = config.capsules
#     capsule_colors  = config.capsule_colors
#     progressbar     = config.progressbar
#
#     if skip == "skip":
#         skip = True
#     else:
#         skip = False
#
#     async def loadProgressBar(ctx, message, e):
#         for step, color in enumerate(colors):
#             e.color = color
#             e.set_field_at(1, name = progressbar[step + 1], value = menu_bottom, inline = False)
#             await message.edit(embed = e)
#             time.sleep(0.5)
#
#     async def updateStock(ctx, sub_prize):
#         data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{sub_prize}'")
#         if data:
#             stock = GachaDB.backstock[sub_prize]
#             current_stock = stock.current_stock
#             times_rolled = stock.times_rolled
#             max_limit = stock.max_limit
#             if times_rolled < max_limit and current_stock > 0:
#                 GachaDB.backstock[sub_prize] = {"current_stock": current_stock - 1, "times_rolled": times_rolled + 1, "max_limit": max_limit}
#                 return True
#             else:
#                 await ctx.send(f"Prize **'{sub_prize}'** is out of stock!")
#                 return False
#         else:
#             return True
#
#     async def rewardPrize(ctx, tier, capsule):
#         prize_array     = Prizes[tier]["prizes"][capsule]
#         user_id         = ctx.author.id
#         member          = ctx.author
#         inventory       = getUserGachaInv(user_id)
#         tickets         = inventory.gacha_tickets
#         fragments       = inventory.gacha_fragments
#         total_rolls     = inventory.total_rolls
#         grand_prize_string = f"1 {branch_name} NFT"
#         for sub_prize in prize_array:
#             match sub_prize:
#                 case "WL":
#                     wl_role = discord.utils.get(ctx.guild.roles, name = config.wl_role)
#                     if not wl_role in ctx.author.roles:
#                         if await updateStock(ctx, sub_prize):
#                             await member.add_roles(wl_role)
#                             await ctx.send(f"🎉 Rewarded {ctx.author.mention} with whitelist Role: **{config.wl_role}**!")
#                         else:
#                             continue
#                 case "OG":
#                     og_role = discord.utils.get(ctx.guild.roles, name = config.og_role)
#                     if not og_role in ctx.author.roles:
#                         if await updateStock(ctx, sub_prize):
#                             await member.add_roles(og_role)
#                             await ctx.send(f"🎉 Rewarded {ctx.author.mention} with OG Role: **{config.og_role}**!")
#                         else:
#                             continue
#                 case x if x.endswith("EXP"):
#                     exp = x.rstrip(" EXP")
#                     channel = bot.get_channel(config.channels["exp"])
#                     role_id = config.gacha_mod_role
#                     if await updateStock(ctx, sub_prize):
#                         if not checkAdmin(ctx):
#                             await channel.send(f"<@&{role_id}> | {ctx.author.mention} has won {exp} EXP from the Gacha! Please paste this to reward them:{chr(10)}`!give-xp {ctx.author.mention} {exp}`")
#                         await ctx.send(f"🎉 Reward sent for reviewal: {ctx.author.mention} with **{exp} EXP**!")
#                     else:
#                         continue
#                 case x if x.endswith("Fragment") or x.endswith("Fragments"):
#                     amount = int(x.split(" ")[0])
#                     if await updateStock(ctx, sub_prize):
#                         GachaDB.userdata[user_id] = {"gacha_tickets": tickets, "gacha_fragments": fragments + amount, "total_rolls": total_rolls}
#                         await ctx.send(f"🎉 Rewarded {ctx.author.mention} with prize: **{amount} Gacha Fragment(s)**! User now has a total of `{fragments + amount}`.")
#                     else:
#                         continue
#                 case x if x.endswith("Ticket") or x.endswith("Tickets"):
#                     amount = int(x.split(" ")[0])
#                     if await updateStock(ctx, sub_prize):
#                         GachaDB.userdata[user_id] = {"gacha_tickets": tickets + amount, "gacha_fragments": fragments, "total_rolls": total_rolls}
#                         await ctx.send(f"🎉 Rewarded {ctx.author.mention} with prize: **{amount} Gacha Ticket(s)**! User now has a total of `{tickets + amount}`.")
#                     else:
#                         continue
#                 case x if x == grand_prize_string:
#                     role_id = config.gacha_mod_role
#                     if await updateStock(ctx, sub_prize):
#                         await ctx.send(f"<@&{role_id}> | 🎉 {ctx.author.mention} has just won the grand prize! 🏆 Congratulations! 🎉")
#                     else:
#                         continue
#
#     def getPrize(tier, capsule, filter = True):
#         prize_array = Prizes[tier]["prizes"][capsule]
#         prize_length = len(prize_array)
#         full_prize = ""
#         prize_counter = 0
#         for sub_prize in prize_array:
#             # Build full string with all prizes in array
#             prize_counter += 1
#             data = GachaDB.query(f"SELECT * FROM backstock WHERE prize = '{sub_prize}'")
#             if data:
#                 # Check backstock of sub prize
#                 stock = GachaDB.backstock[sub_prize]
#                 current_stock = stock.current_stock
#                 times_rolled = stock.times_rolled
#                 max_limit = stock.max_limit
#                 if not times_rolled < max_limit and not current_stock > 0:
#                     # Prize is out of stock, skip it
#                     if filter:
#                         continue
#             full_prize += sub_prize
#             if prize_counter < prize_length:
#                 # Add separator between prizes in the string
#                 full_prize += " + "
#         # Ensure not empty string
#         if full_prize == "":
#             full_prize = " "
#         return full_prize
#
#     async def raffleEntry(ctx, message, e, tier, skip):
#         inventory       = getUserGachaInv(user_id)
#         tickets         = inventory.gacha_tickets
#         fragments       = inventory.gacha_fragments
#         total_rolls     = inventory.total_rolls
#         name            = Prizes[tier]["name"]
#         symbol          = Prizes[tier]["symbol"]
#         cost            = Prizes[tier]["tickets_required"]
#         e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Spin to win!", color = default_color)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
#         e.add_field(name = f"{name} Raffle", value = symbol, inline = True)
#         e.add_field(name = "Admission:", value = f"🎟️ x {cost} ticket(s)", inline = True)
#         e.add_field(name = "Your current tickets:", value = tickets, inline = False)
#         if tickets >= cost:
#             e.add_field(name = "Tickets after spinning:", value = tickets - cost, inline = False)
#             e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#             e.add_field(name = "▷ 🎲 ────  Spin the Gacha  ──── 🎲 ◁", value = menu_separator, inline = False)
#             e.add_field(name = "▷ ↩️  ──  Select another Raffle  ──  ↩️ ◁", value = menu_bottom, inline = False)
#             await message.edit(embed = e)
#             emojis = ["🎲", "↩️"]
#             reaction, user = await waitForReaction(ctx, message, e, emojis)
#             if reaction is None:
#                 return message, e, False
#             match str(reaction.emoji):
#                 case "🎲":
#                     e.set_field_at(5, name = "►🎲 ────  Spin the Gacha  ──── 🎲 ◄", value = menu_separator, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     message, e = await rollGacha(ctx, message, e, tier, name, cost, symbol, tickets, fragments, total_rolls, skip)
#                     return message, e, True
#                 case "↩️":
#                     e.set_field_at(6, name = "►↩️  ──  Select another Raffle  ──  ↩️ ◄", value = menu_bottom, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     return message, e, False
#         else:
#             e.add_field(name = "You need this many more tickets to spin:", value = cost - tickets, inline = False)
#             e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#             e.add_field(name = "▷ ↩️  ──  Select another Raffle  ──  ↩️ ◁", value = menu_bottom, inline = False)
#             await message.edit(embed = e)
#             emojis = ["↩️"]
#             reaction, user = await waitForReaction(ctx, message, e, emojis)
#             if reaction is None:
#                 return message, e, False
#             match str(reaction.emoji):
#                 case "↩️":
#                     e.set_field_at(5, name = "►↩️  ──  Select another Raffle  ──  ↩️ ◄", value = menu_bottom, inline = False)
#                     await message.edit(embed = e)
#                     await message.clear_reactions()
#                     return message, e, False
#
#     async def rollGacha(ctx, message, e, tier, name, cost, symbol, tickets, fragments, total_rolls, skip):
#         # Subtract ticket(s) from user's inventory, increment roll count, then roll the gacha
#         GachaDB.userdata[user_id] = {"gacha_tickets": tickets - cost, "gacha_fragments": fragments, "total_rolls": total_rolls + 1}
#         e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Good luck!", color = default_color)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
#         e.add_field(name = f"Spinning the {name} Raffle:", value = menu_top, inline = False)
#         e.add_field(name = progressbar[0], value = menu_bottom, inline = False)
#         await message.edit(embed = e)
#         if not skip:
#             await loadProgressBar(ctx, message, e)
#         message, e = await pullCapsule(ctx, message, e, tier, name, cost, symbol, tickets, fragments, total_rolls)
#         return message, e
#
#     async def pullCapsule(ctx, message, e, tier, name, cost, symbol, tickets, fragments, total_rolls):
#         cold_weights = config.weights[tier]
#
#         # Nullify chances to roll a capsule if its prize array is empty
#         for index, category in enumerate(Prizes[tier]["prizes"]):
#             if not Prizes[tier]["prizes"][category]:
#                 cold_weights[index] = 0
#
#         # Rebalance weights to ensure they add up to 100
#         cold_weights = rebalanceWeights(cold_weights)
#
#         if Prizes[tier]["regulated"]:
#             # Modify probability for regulated prize
#             regulated_prize = getPrize(tier, "platinum", filter = False)
#             GachaDB.execute(f"INSERT OR IGNORE INTO backstock (prize, current_stock, times_rolled, max_limit) values ('{regulated_prize}', '0', '0', '0')")
#             stock = GachaDB.backstock[regulated_prize]
#             current_stock = stock.current_stock
#             times_rolled = stock.times_rolled
#             max_limit = stock.max_limit
#             if times_rolled < max_limit and current_stock > 0:
#                 # Max limit hasn't been reached, allow platinum to be rolled
#                 which_mod = times_rolled
#                 mod = config.weight_mods[which_mod]
#             else:
#                 # Nullify chance to roll platinum
#                 mod = cold_weights[5]
#             hot_weights = [cold_weights[0] + mod / 5, cold_weights[1] + mod / 5, cold_weights[2] + mod / 5, cold_weights[3] + mod / 5, cold_weights[4] + mod / 5, cold_weights[5] - mod]
#             # Use modified probabilities
#             capsule = randomWeighted(capsules, hot_weights)
#         else:
#             # Use unmodified probabilities
#             capsule = randomWeighted(capsules, cold_weights)
#         e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = f"🎉 Congratulations {ctx.author.mention}! 🎊")
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         match capsule:
#             case "blue":
#                 e.color = capsule_colors[0]
#                 e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
#                 e.set_image(url = Resource["Blue"][0])
#             case "green":
#                 e.color = capsule_colors[1]
#                 e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
#                 e.set_image(url = Resource["Green"][0])
#             case "red":
#                 e.color = capsule_colors[2]
#                 e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
#                 e.set_image(url = Resource["Red"][0])
#             case "silver":
#                 e.color = capsule_colors[3]
#                 e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
#                 e.set_image(url = Resource["Silver"][0])
#             case "gold":
#                 e.color = capsule_colors[4]
#                 e.set_thumbnail(url = Resource["Kinka_Mei-4"][0])
#                 e.set_image(url = Resource["Gold"][0])
#             case "platinum":
#                 e.color = capsule_colors[5]
#                 e.set_thumbnail(url = Resource["Kinka_Mei-4"][0])
#                 e.set_image(url = Resource["Platinum"][0])
#         prize = getPrize(tier, capsule)
#         e.add_field(name = "Raffle Spun:", value = f"{symbol} {name} {symbol}", inline = True)
#         e.add_field(name = "You Won:", value = f"🎁 {prize} 🎁", inline = True)
#         # Add record of prize to database
#         prize_id = str(user_id) + str("{:05d}".format(total_rolls + 1))
#         now = datetime.utcnow()
#         GachaDB.prizehistory[prize_id] = {"user_id": user_id, "date": now, "tickets_spent": cost, "tier": tier, "capsule": capsule, "prize": prize}
#         e.set_footer(text = f"Prize ID: {prize_id}")
#         # Reward prizes if applicable
#         await rewardPrize(ctx, tier, capsule)
#         await message.edit(embed = e)
#         return message, e
#
#     # main()
#     exit_flag = edit_flag = False
#     while not (exit_flag):
#         prev_flag = False
#         e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Test your luck for amazing prizes!", color = default_color)
#         e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#         e.set_thumbnail(url = Resource["Kinka_Mei-1"][0])
#         e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#         e.add_field(name = "▷ 📜 ─────  Prize  List  ────── 📜 ◁", value = menu_separator, inline = False)
#         e.add_field(name = "▷ 🎰 ──── Select  a  Raffle ──── 🎰 ◁", value = menu_separator, inline = False)
#         e.add_field(name = "▷ 📦 ── View your inventory ─── 📦 ◁", value = menu_separator, inline = False)
#         e.add_field(name = "▷ ❌ ─────  Exit  Menu  ─────  ❌ ◁", value = menu_bottom, inline = False)
#         if not edit_flag:
#             message = await ctx.send(embed = e)
#         else:
#             await message.edit(embed = e)
#         emojis = ["📜", "🎰", "📦", "❌"]
#         reaction, user = await waitForReaction(ctx, message, e, emojis)
#         if reaction is None:
#             break
#         match str(reaction.emoji):
#             case "📜":
#                 def formatPrizeList(tier):
#                     formatted_prize_list = f"\
#                         🔵  ─  *Blue*  ─  {config.encouragement[tier][0]}%\n  └ **`{getPrize(tier, 'blue')}`**\n\
#                         🟢  ─  *Green*  ─  {config.encouragement[tier][1]}%\n  └ **`{getPrize(tier, 'green')}`**\n\
#                         🔴  ─  *Red*  ─  {config.encouragement[tier][2]}%\n  └ **`{getPrize(tier, 'red')}`**\n\
#                         ⚪  ─  *Silver*  ─  {config.encouragement[tier][3]}%\n  └ **`{getPrize(tier, 'silver')}`**\n\
#                         🟡  ─  *Gold*  ─  {config.encouragement[tier][4]}%\n  └ **`{getPrize(tier, 'gold')}`**\n\
#                         🟣  ─  *Platinum*  ─  {config.encouragement[tier][5]}%\n  └ **`{getPrize(tier, 'platinum')}`**\n\
#                     "
#                     return formatted_prize_list
#
#                 e.set_field_at(1, name = "►📜 ─────  Prize  List  ────── 📜 ◄", value = menu_separator, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Here are today's prize pools:", color = default_color)
#                 e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#                 e.set_thumbnail(url = Resource["Kinka_Mei-3"][0])
#                 e.add_field(name = f"Tier 1: {Prizes['tier_1']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_1']['tickets_required']}", value = formatPrizeList("tier_1"), inline = True)
#                 e.add_field(name = f"Tier 2: {Prizes['tier_2']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_2']['tickets_required']}", value = formatPrizeList("tier_2"), inline = True)
#                 e.add_field(name = "\u200b", value = "\u200b", inline = True)
#                 e.add_field(name = f"Tier 3: {Prizes['tier_3']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_3']['tickets_required']}", value = formatPrizeList("tier_3"), inline = True)
#                 e.add_field(name = f"Tier 4: {Prizes['tier_4']['symbol']}\nTickets required: 🎟️ x {Prizes['tier_4']['tickets_required']}", value = formatPrizeList("tier_4"), inline = True)
#                 e.add_field(name = "\u200b", value = "\u200b", inline = True)
#                 e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#                 e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
#                 await message.edit(embed = e)
#                 emojis = ["↩️"]
#                 reaction, user = await waitForReaction(ctx, message, e, emojis)
#                 if reaction is None:
#                     break
#                 match str(reaction.emoji):
#                     case "↩️":
#                         prev_flag = edit_flag = True
#                         e.set_field_at(7, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
#                         await message.edit(embed = e)
#                         await message.clear_reactions()
#             case "🎰":
#                 e.set_field_at(2, name = "►🎰 ──── Select  a  Raffle ──── 🎰 ◄", value = menu_separator, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 while not (exit_flag or prev_flag):
#                     e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Select a Gacha Unit to spin!", color = default_color)
#                     e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#                     e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
#                     e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#                     e.add_field(name = "▷ 🥉 ───── Tier 1 Raffle ───── 🥉 ◁", value = menu_separator, inline = False)
#                     e.add_field(name = "▷ 🥈 ───── Tier 2 Raffle ───── 🥈 ◁", value = menu_separator, inline = False)
#                     e.add_field(name = "▷ 🥇 ───── Tier 3 Raffle ───── 🥇 ◁", value = menu_separator, inline = False)
#                     e.add_field(name = "▷ 🏅 ───── Tier 4 Raffle ───── 🏅 ◁", value = menu_separator, inline = False)
#                     e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
#                     await message.edit(embed = e)
#                     emojis = ["🥉", "🥈", "🥇", "🏅", "↩️"]
#                     reaction, user = await waitForReaction(ctx, message, e, emojis)
#                     if reaction is None:
#                         exit_flag = True
#                         break
#                     match str(reaction.emoji):
#                         case "🥉":
#                             tier = "tier_1"
#                             e.set_field_at(1, name = "►🥉 ───── Tier 1 Raffle ───── 🥉 ◄", value = menu_separator, inline = False)
#                             await message.edit(embed = e)
#                             await message.clear_reactions()
#                             message, e, status = await raffleEntry(ctx, message, e, tier, skip)
#                             if status:
#                                 rolled_flag = True
#                             else:
#                                 rolled_flag = False
#                         case "🥈":
#                             tier = "tier_2"
#                             e.set_field_at(2, name = "►🥈 ───── Tier 2 Raffle ───── 🥈 ◄", value = menu_separator, inline = False)
#                             await message.edit(embed = e)
#                             await message.clear_reactions()
#                             message, e, status = await raffleEntry(ctx, message, e, tier, skip)
#                             if status:
#                                 rolled_flag = True
#                             else:
#                                 rolled_flag = False
#                         case "🥇":
#                             tier = "tier_3"
#                             e.set_field_at(3, name = "►🥇 ───── Tier 3 Raffle ───── 🥇 ◄", value = menu_separator, inline = False)
#                             await message.edit(embed = e)
#                             await message.clear_reactions()
#                             message, e, status = await raffleEntry(ctx, message, e, tier, skip)
#                             if status:
#                                 rolled_flag = True
#                             else:
#                                 rolled_flag = False
#                         case "🏅":
#                             tier = "tier_4"
#                             e.set_field_at(4, name = "►🏅 ───── Tier 4 Raffle ───── 🏅 ◄", value = menu_separator, inline = False)
#                             await message.edit(embed = e)
#                             await message.clear_reactions()
#                             message, e, status = await raffleEntry(ctx, message, e, tier, skip)
#                             if status:
#                                 rolled_flag = True
#                             else:
#                                 rolled_flag = False
#                         case "↩️":
#                             prev_flag = edit_flag = True
#                             e.set_field_at(5, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
#                             await message.edit(embed = e)
#                             await message.clear_reactions()
#                             break
#                     if rolled_flag:
#                         time.sleep(0.3)
#                         emojis = ["🔁", "❌"]
#                         reaction, user = await waitForReaction(ctx, message, e, emojis, False)
#                         if reaction is None:
#                             exit_flag = True
#                             break
#                         match str(reaction.emoji):
#                             case "🔁":
#                                 await message.clear_reactions()
#                                 exit_flag = edit_flag = False
#                                 prev_flag = True
#                             case "❌":
#                                 await message.clear_reactions()
#                                 exit_flag = True
#             case "📦":
#                 inv_gacha   = getUserGachaInv(user_id)
#                 inv_market  = getUserMarketInv(user_id)
#                 tickets     = inv_gacha.gacha_tickets
#                 fragments   = inv_gacha.gacha_fragments
#                 total_rolls = inv_gacha.total_rolls
#                 ryou        = inv_market.ryou
#                 exp         = getPlayerExp(user_id)
#                 level       = getPlayerLevel(user_id)
#                 e.set_field_at(3, name = "►📦 ── View your inventory ─── 📦 ◄", value = menu_bottom, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Your inventory:", color = default_color)
#                 e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
#                 e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
#                 e.add_field(name = "Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
#                 e.add_field(name = "Gacha Fragments:", value = f"{Icons['fragment']} x `{'{:,}'.format(fragments)}`", inline = True)
#                 e.add_field(name = "Total roll count:", value = f"🎲 x `{'{:,}'.format(total_rolls)}`", inline = True)
#                 e.add_field(name = "Ryou D-Coins:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
#                 e.add_field(name = "EXP:", value = f"{Icons['exp']} x `{'{:,}'.format(exp)}`", inline = True)
#                 e.add_field(name = "Level:", value = f"{Icons['level']} `{'{:,}'.format(level)}`", inline = True)
#                 e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
#                 e.add_field(name = "▷ ↩️ ───── Main  Menu ───── ↩️ ◁", value = menu_bottom, inline = False)
#                 await message.edit(embed = e)
#                 emojis = ["↩️"]
#                 reaction, user = await waitForReaction(ctx, message, e, emojis)
#                 if reaction is None:
#                     break
#                 match str(reaction.emoji):
#                     case "↩️":
#                         prev_flag = edit_flag = True
#                         e.set_field_at(5, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
#                         await message.edit(embed = e)
#                         await message.clear_reactions()
#             case "❌":
#                 e.set_field_at(4, name = "►❌ ─────  Exit  Menu  ─────  ❌ ◄", value = menu_bottom, inline = False)
#                 await message.edit(embed = e)
#                 await message.clear_reactions()
#                 return

@bot.command(aliases = ["inventory"])
@commands.check(checkChannel)
async def inv(ctx, target = None):
    ''' | Usage: +inv [@user] | Check the inventory of a user '''
    if target is None:
        target = ctx.author.mention
    # Ensure valid discord ID
    if re.match(r"<(@|@&)[0-9]{18,19}>", target):
        user_id     = convertMentionToId(target)
        inv_gacha   = getUserGachaInv(user_id)
        inv_market  = getUserMarketInv(user_id)
        inv_items   = getUserItemInv(user_id)
        playerdata  = getPlayerData(user_id)
        tickets     = inv_gacha.gacha_tickets
        fragments   = inv_gacha.gacha_fragments
        total_rolls = inv_gacha.total_rolls
        ryou        = inv_market.ryou
        exp         = getPlayerExp(user_id)
        level       = getPlayerLevel(user_id)
        Icons       = config.custom_emojis
        e = discord.Embed(title = "Viewing inventory of user:", description = target, color = 0xfdd835)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.display_avatar)
        e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
        e.add_field(name = "Gacha Tickets:", value = f"{Icons['ticket']} x `{'{:,}'.format(tickets)}`", inline = True)
        e.add_field(name = "Gacha Fragments:", value = f"{Icons['fragment']} x `{'{:,}'.format(fragments)}`", inline = True)
        e.add_field(name = "Total roll count:", value = f"🎲 x `{'{:,}'.format(total_rolls)}`", inline = True)
        e.add_field(name = "Ryou D-Coins:", value = f"{Icons['ryou']} x `{'{:,}'.format(ryou)}`", inline = True)
        e.add_field(name = "EXP:", value = f"{Icons['exp']} x `{'{:,}'.format(exp)}`", inline = True)
        e.add_field(name = "Level:", value = f"{Icons['level']} `{'{:,}'.format(level)}`", inline = True)
        for slot, item in enumerate(inv_items):
            border = ""
            for _ in item[0]:
                border += "═"
            e.add_field(name = f"📍 Slot {slot + 1}  ─  (x{item[1]})", value = f"```╔{border}╗\n║{item[0]}║\n╚{border}╝```", inline = False)
        await ctx.send(embed = e)
    else:
        await ctx.send("Please **@ mention** a valid user to check their inventory (!help inv)")

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
    ''' | Usage: +reward <@user> <item> <quantity> | Items: "ticket", "fragment", "ryou" '''
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
            exp         = getPlayerExp(user_id)
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
                    PlayerDB.userdata[user_id] = {"exp": exp + quantity}
                    await ctx.send(f"Rewarded {target} with {Icons['exp']} `{quantity}` **Experience Points**! User now has a total of `{exp + quantity}`.")
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
@commands.check(checkAdmin)
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
