### Gacha Bot for Onigiri
### Created by pianosuki
### https://github.com/pianosuki
### For use by Catheon only
branch_name = "Onigiri"
bot_version = "1.7.3"

import config, dresource
from database import Database
import discord, re, time, random, json, math
from discord.ext import commands
from datetime import datetime
import numpy as np
from collections import Counter

intents                 = discord.Intents.default()
intents.message_content = True
bot                     = commands.Bot(command_prefix = config.prefix, intents = intents)
DB                      = Database("gachadata.db") # Initialize sqlite3 database
DB.execute("CREATE TABLE IF NOT EXISTS userdata (user_id INTEGER PRIMARY KEY UNIQUE, gacha_tickets INTEGER, gacha_fragments INTEGER, total_rolls INTEGER)")
DB.execute("CREATE TABLE IF NOT EXISTS prizehistory (prize_id TEXT PRIMARY KEY UNIQUE, user_id INTEGER, date TEXT, tickets_spent TEXT, tier TEXT, capsule TEXT, prize TEXT)")
DB.execute("CREATE TABLE IF NOT EXISTS backstock (prize TEXT PRIMARY KEY UNIQUE, current_stock INTEGER, times_rolled INTEGER, max_limit INTEGER)")
Prizes                  = json.load(open("prizes.json")) # Load list of prizes for the gacha to pull from
Graphics                = json.load(open("graphics.json")) # Load list of graphical assets to build Resource with
Resource                = dresource.resCreate(Graphics) # Generate discord file attachment resource

@bot.event
async def on_ready():
    # Go Online
    await bot.change_presence(status = discord.Status.online, activity = discord.Game(f"{config.prefix}roll to spin the Gacha!"))
    print(f"Logged in as {bot.user} | Version: {bot_version}")

### Functions
def checkAdmin(ctx):
    if ctx.author.id in config.admin_list:
        return True
    admin_role = discord.utils.get(ctx.guild.roles, name = config.admin_role)
    if admin_role in ctx.author.roles:
        return True

async def convertMentionToId(target):
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

async def getUserInv(user_id):
    DB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values ("+str(user_id)+", '0', '0', '0')")
    inventory = DB.userdata[user_id]
    return inventory

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

### User Commands
@bot.command(aliases = ["gacha", "spin"])
async def roll(ctx, skip=None):
    ''' | Usage: +roll | Use reactions to navigate the menus '''
    user_id         = ctx.author.id
    menu_top        = "┌───────────────────────┐"
    menu_separator  = "├───────────────────────┤"
    menu_bottom     = "└───────────────────────┘"
    default_color   = 0xfdd835
    colors          = [0xe53935, 0xd81b60, 0x8e24aa, 0x5e35b1, 0x3949ab, 0x1e88e5, 0x039be5, 0x00acc1, 0x00897b, 0x43a047, 0x7cb342, 0xc0ca33, 0xfdd835, 0xffb300, 0xfb8c00, 0xf4511e]
    capsule_colors  = [0x2196f3, 0x4caf50, 0xef5350, 0xeceff1, 0xffeb3b, 0xd1c4e9]
    capsules        = ["blue", "green", "red", "silver", "gold", "platinum"]
    progressbar     = ["🕛  -=| ──────────────── |=-  🕛",
                       "🕐  -=| ━───────────────  |=-  🕐",
                       "🕑  -=|  ━━──────────────  |=-  🕑",
                       "🕒  -=|  ━━━─────────────  |=-  🕒",
                       "🕓  -=|  ━━━━────────────  |=-  🕓",
                       "🕔  -=|  ━━━━━───────────   |=-  🕔",
                       "🕕  -=|   ━━━━━━──────────   |=-  🕕",
                       "🕖  -=|   ━━━━━━━─────────   |=-  🕖",
                       "🕗  -=|   ━━━━━━━━────────   |=-  🕗",
                       "🕘  -=|   ━━━━━━━━━───────    |=-  🕘",
                       "🕙  -=|    ━━━━━━━━━━──────    |=-  🕙",
                       "🕚  -=|    ━━━━━━━━━━━─────    |=-  🕚",
                       "🕛  -=|    ━━━━━━━━━━━━────    |=-  🕛",
                       "🕐  -=|    ━━━━━━━━━━━━━───     |=-  🕐",
                       "🕑  -=|     ━━━━━━━━━━━━━━──     |=-  🕑",
                       "🕒  -=|     ━━━━━━━━━━━━━━━─     |=-  🕒",
                       "🕓  -=|     ━━━━━━━━━━━━━━━━     |=-  🕓"]

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
        data = DB.query(f"SELECT * FROM backstock WHERE prize = '{sub_prize}'")
        if data:
            stock = DB.backstock[sub_prize]
            current_stock = stock.current_stock
            times_rolled = stock.times_rolled
            max_limit = stock.max_limit
            if times_rolled < max_limit and current_stock > 0:
                DB.backstock[sub_prize] = {"current_stock": current_stock - 1, "times_rolled": times_rolled + 1, "max_limit": max_limit}
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
        inventory       = await getUserInv(user_id)
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
                    exp = x.rstrip(" EXP")
                    channel = bot.get_channel(config.exp_channel)
                    role_id = config.gacha_mod_role
                    if await updateStock(ctx, sub_prize):
                        if not checkAdmin(ctx):
                            await channel.send(f"<@&{role_id}> | {ctx.author.mention} has won {exp} EXP from the Gacha! Please paste this to reward them:{chr(10)}`!give-xp {ctx.author.mention} {exp}`")
                        await ctx.send(f"🎉 Reward sent for reviewal: {ctx.author.mention} with **{exp} EXP**!")
                    else:
                        continue
                case x if x.endswith("Fragment") or x.endswith("Fragments"):
                    channel = bot.get_channel(config.gachaproof_channel)
                    amount = int(x.split(" ")[0])
                    if await updateStock(ctx, sub_prize):
                        DB.userdata[user_id] = {"gacha_tickets": tickets, "gacha_fragments": fragments + amount, "total_rolls": total_rolls}
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with prize: **{amount} Gacha Fragment(s)**!")
                        await channel.send(f"Rewarded {ctx.author.mention} with `{amount}` **Gacha Ticket Fragment(s)**! User now has a total of `{fragments + amount}`.")
                    else:
                        continue
                case x if x.endswith("Ticket") or x.endswith("Tickets"):
                    channel = bot.get_channel(config.gachaproof_channel)
                    amount = int(x.split(" ")[0])
                    if await updateStock(ctx, sub_prize):
                        DB.userdata[user_id] = {"gacha_tickets": tickets + amount, "gacha_fragments": fragments, "total_rolls": total_rolls}
                        await ctx.send(f"🎉 Rewarded {ctx.author.mention} with prize: **{amount} Gacha Ticket(s)**!")
                        await channel.send(f"Rewarded {ctx.author.mention} with `{amount}` **Gacha Ticket(s)**! User now has a total of `{tickets + amount}`.")
                    else:
                        continue
                case x if x == grand_prize_string:
                    role_id = config.gacha_mod_role
                    if await updateStock(ctx, sub_prize):
                        await ctx.send(f"<@&{role_id}> | 🎉 {ctx.author.mention} has just won the grand prize! 🏆 Congratulations! 🎉")
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
            data = DB.query(f"SELECT * FROM backstock WHERE prize = '{sub_prize}'")
            if data:
                # Check backstock of sub prize
                stock = DB.backstock[sub_prize]
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
        inventory       = await getUserInv(user_id)
        tickets         = inventory.gacha_tickets
        fragments       = inventory.gacha_fragments
        total_rolls     = inventory.total_rolls
        name            = Prizes[tier]["name"]
        symbol          = Prizes[tier]["symbol"]
        cost            = Prizes[tier]["tickets_required"]
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Spin to win!", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
        DB.userdata[user_id] = {"gacha_tickets": tickets - cost, "gacha_fragments": fragments, "total_rolls": total_rolls + 1}
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Good luck!", color = default_color)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
            DB.execute(f"INSERT OR IGNORE INTO backstock (prize, current_stock, times_rolled, max_limit) values ('{regulated_prize}', '0', '0', '0')")
            stock = DB.backstock[regulated_prize]
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
        e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
        DB.prizehistory[prize_id] = {"user_id": user_id, "date": now, "tickets_spent": cost, "tier": tier, "capsule": capsule, "prize": prize}
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
        e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
                e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
                    e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
                inventory       = await getUserInv(user_id)
                tickets         = inventory.gacha_tickets
                fragments       = inventory.gacha_fragments
                total_rolls     = inventory.total_rolls
                e.set_field_at(3, name = "►📦 ── View your inventory ─── 📦 ◄", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Your inventory:", color = default_color)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
                e.set_thumbnail(url = Resource["Kinka_Mei-5"][0])
                e.add_field(name = "Gacha Tickets:", value = f"🎟️ x {tickets} ticket(s)", inline = False)
                e.add_field(name = "Gacha Ticket Fragments:", value = f"🧩 x {fragments} piece(s)", inline = False)
                e.add_field(name = "Total roll count:", value = f"🎲 x {total_rolls} roll(s)", inline = False)
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

@bot.command(aliases = ["inventory"])
async def inv(ctx, target = None):
    ''' | Usage: +inv [@user] | Check the inventory of a user '''
    if target is None:
        target = ctx.author.mention
    # Ensure valid discord ID
    if re.match(r"<(@|@&)[0-9]{18,19}>", target):
        user_id = await convertMentionToId(target)
        # Check if user is already in database, if not then set them up default values of 0
        DB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values ("+str(user_id)+", '0', '0', '0')")
        inventory   = DB.userdata[user_id]
        tickets     = inventory.gacha_tickets
        fragments   = inventory.gacha_fragments
        total_rolls = inventory.total_rolls
        e = discord.Embed(title = "Viewing inventory of user:", description = target, color = 0xfdd835)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
        e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
        e.add_field(name = "Gacha Tickets:", value = f"🎟️ x {tickets} ticket(s)", inline = False)
        e.add_field(name = "Gacha Ticket Fragments:", value = f"🧩 x {fragments} piece(s)", inline = False)
        e.add_field(name = "Total roll count:", value = f"🎲 x {total_rolls} roll(s)", inline = False)
        await ctx.send(embed = e)
    else:
        await ctx.send("Please **@ mention** a valid user to check their inventory (!help inv)")

@bot.command()
async def craft(ctx, amount:str = "1"):
    ''' | Usage: +craft [integer or "all"] | Craft a Gacha Ticket from 4 Gacha Pieces '''
    menu_top        = "┌───────────────────────┐"
    menu_separator  = "├───────────────────────┤"
    menu_bottom     = "└───────────────────────┘"
    user_id = await convertMentionToId(ctx.author.mention)
    DB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values ("+str(user_id)+", '0', '0', '0')")
    inventory   = DB.userdata[user_id]
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
    e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
                e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
                e.set_thumbnail(url = Resource["Kinka_Mei-6"][0])
                e.add_field(name = "Used fragments:", value = f"🧩 x {craft_amount * 4}", inline = False)
                e.add_field(name = "You now have this many Gacha Tickets:", value = f"🎟️ x {tickets + craft_amount}", inline = False)
                await ctx.send(embed = e)
                # Add crafted tickets to and subtract used fragments from database
                DB.userdata[user_id] = {"gacha_tickets": tickets + craft_amount, "gacha_fragments": fragments - craft_amount * 4, "total_rolls": total_rolls}
            else:
                e = discord.Embed(title = "Crafting Result", description = "❌ Craft failed!", color = 0x00897b)
                e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
                e.set_thumbnail(url = Resource["Kinka_Mei-2"][0])
                e.add_field(name = "You have insufficient ticket pieces.", value =  f"Need 🧩 x {craft_amount * 4 - fragments} more!", inline = False)
                await ctx.send(embed = e)
        case "❌":
            e.set_field_at(5, name = "►❌ ─────  Exit  Menu  ─────  ❌ ◄", value = menu_bottom, inline = False)
            await message.edit(embed = e)
            await message.clear_reactions()

@bot.command()
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
    user_id = await convertMentionToId(target)
    history = DB.query(f"SELECT * FROM prizehistory WHERE user_id = '{user_id}'")
    history.reverse()
    history_length = len(history)
    e = discord.Embed(title = "View Prize History", description = f"History of {target}", color = 0xd81b60)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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

### Admin Commands
@bot.command()
@commands.check(checkAdmin)
async def reward(ctx, target: str, item: str, quantity):
    ''' | Usage: +reward <@user> <item> <quantity> | Items: "ticket", "fragment" '''
    # Ensure valid discord ID
    if re.match(r"<(@|@&)[0-9]{18,19}>", target):
        # Ensure integer
        try:
            quantity = int(quantity)
            user_id = await convertMentionToId(target)
            # Check if user is already in database, if not then set them up default values of 0
            DB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values ("+str(user_id)+", '0', '0', '0')")
            inventory   = DB.userdata[user_id]
            tickets     = inventory.gacha_tickets
            fragments   = inventory.gacha_fragments
            total_rolls = inventory.total_rolls
            # Add the respective reward on top of what the user already has
            match item:
                case "ticket" | "tickets":
                    DB.userdata[user_id] = {"gacha_tickets": tickets + quantity, "gacha_fragments": fragments, "total_rolls": total_rolls}
                    await ctx.send(f"Rewarded {target} with `{quantity}` **Gacha Ticket(s)**! User now has a total of `{tickets + quantity}`.")
                case "fragment" | "fragments":
                    DB.userdata[user_id] = {"gacha_tickets": tickets, "gacha_fragments": fragments + quantity, "total_rolls": total_rolls}
                    await ctx.send(f"Rewarded {target} with `{quantity}` **Gacha Ticket Fragment(s)**! User now has a total of `{fragments + quantity}`.")
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
    for _ in range(n):
        # Roll the gacha n times
        outcomes.append(randomWeighted(capsules, weights))
    c = Counter(outcomes)
    e = discord.Embed(title = "Roll simulation", color = 0x3949ab)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
    e.add_field(name = f"│ {Prizes[tier]['symbol']} Tier", value = f"│ {Prizes[tier]['name']}", inline = True)
    e.add_field(name = "│ 🎲 Rolls", value = f"│ {n}x", inline = True)
    e.add_field(name = "│ │ 🔵 Blue", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ 🟢 Green", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ 🔴 Red", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ ⚪ Silver", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ 🟡 Gold", value = "│  └  0x   ─   0%", inline = False)
    e.add_field(name = "│ 🟣 Platinum", value = "│  └  0x   ─   0%", inline = False)
    for key in c:
        # Set the results of the simulation accordingly
        match key:
            case "blue":
                e.set_field_at(2, name = "│ 🔵 Blue", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "green":
                e.set_field_at(3, name = "│ 🟢 Green", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "red":
                e.set_field_at(4, name = "│ 🔴 Red", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "silver":
                e.set_field_at(5, name = "│ ⚪ Silver", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "gold":
                e.set_field_at(6, name = "│ 🟡 Gold", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
            case "platinum":
                e.set_field_at(7, name = "│ 🟣 Platinum", value = f"│  └  `{c[key]}x`   ─   *{round(c[key] / n * 100, 2)}%*", inline = False)
    await ctx.send(embed = e)
    await ctx.send(f"Weights used: `{weights}`")

@bot.command()
@commands.check(checkAdmin)
async def restock(ctx, prize: str, stock: int, max_limit: int = -1, reset: int = -1):
    ''' | Usage: +restock <"Prize name"> <Stock> [Maximum roll limit] [Reset "times_rolled" counter? (-1: Reset, 0: Don't reset, n: Set counter to n) ] '''
    data = DB.query(f"SELECT * FROM backstock WHERE prize = '{prize}'")
    match reset:
        case -1:
            times_rolled = 0
            reset_option = "Reset counter to 0"
        case 0:
            times_rolled = DB.backstock[prize].times_rolled
            reset_option = "Leave counter unchanged"
        case x if x > 0:
            times_rolled = x
            reset_option = f"Set counter to {x}"
    if max_limit == -1:
        max_limit = stock
    if data:
        e = discord.Embed(title = "Restock Prize Database", description = "Confirm the following:", color = 0xc0ca33)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
                DB.backstock[prize] = {"current_stock": stock, "times_rolled": times_rolled, "max_limit": max_limit}
            case "❌":
                await ctx.send("❌ Aborted")
                return
    else:
        e = discord.Embed(title = "Restock Prize Database", description = "Confirm the following:", color = 0xc0ca33)
        e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
                e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
                e.add_field(name = f"Stock of '{prize}' will be set to:", value = stock, inline = False)
                e.add_field(name = f"With a maximum limit of:", value = max_limit, inline = False)
                e.add_field(name = "Reset 'Times Rolled' counter:", value = reset, inline = False)
                await message.edit(embed = e)
                emojis = ["✅", "❌"]
                reaction, user = await waitForReaction(ctx, message, e, emojis)
                match str(reaction.emoji):
                    case "✅":
                        DB.execute(f"INSERT OR IGNORE INTO backstock (prize, current_stock, times_rolled, max_limit) values ('{prize}', '0', '0', '0')")
                        DB.backstock[prize] = {"current_stock": stock, "times_rolled": times_rolled, "max_limit": max_limit}
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

    userdata = DB.query("SELECT * FROM userdata")
    prizehistory = DB.query("SELECT * FROM prizehistory")
    backstock = DB.backstock[f"1 {branch_name} NFT"]
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
    e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
        prize_info      = DB.prizehistory[prize_id]
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
        e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
        await ctx.send("Please provide a valid 23-digit Prize ID")

@bot.command()
@commands.check(checkAdmin)
async def backstock(ctx):
    ''' | Usage: +backstock | View current backstock of limited prizes '''
    stock = DB.query(f"SELECT * FROM backstock")
    stock_length = len(stock)
    e = discord.Embed(title = "View Backstock", color = 0xe53935)
    e.set_author(name = ctx.author.name, icon_url = ctx.author.avatar.url)
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
async def test(ctx):
    pass

@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await bot.close()

bot.run(config.discord_token)
