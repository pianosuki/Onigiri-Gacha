### Gacha Bot for Onigiri
### Created by pianosuki
### https://github.com/pianosuki
### For use by Catheon only
branch_name = "Onigiri"
bot_version = "1.2"

import config
from database import Database
import discord, re, time, random, json
from discord.ext import commands
from datetime import datetime
import numpy as np
from collections import Counter

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix = config.prefix, intents = intents)
DB = Database("gachadata.db")
DB.execute("CREATE TABLE IF NOT EXISTS userdata (user_id INTEGER PRIMARY KEY UNIQUE, gacha_tickets INTEGER, gacha_fragments INTEGER, total_rolls INTEGER)")
DB.execute("CREATE TABLE IF NOT EXISTS prizehistory (prize_id TEXT PRIMARY KEY UNIQUE, user_id INTEGER, date TEXT, tickets_spent TEXT, tier TEXT, capsule TEXT, prize TEXT)")
DB.execute("CREATE TABLE IF NOT EXISTS backstock (prize TEXT PRIMARY KEY UNIQUE, current_stock INTEGER, times_rolled INTEGER, max_limit INTEGER)")

@bot.event
async def on_ready():
    print("Logged in as {0.user}".format(bot))
    await bot.change_presence(status = discord.Status.online, activity = discord.Game("+roll to spin the Gacha!"))

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

### User Commands
@bot.command(aliases = ["gacha", "spin"])
async def roll(ctx, skip=None):
    ''' | Usage: +roll | Use reactions to navigate the menus'''
    prizes          = json.load(open('prizes.json'))
    user_id         = ctx.author.id
    inventory       = await getUserInv(user_id)
    tickets         = inventory.gacha_tickets
    fragments       = inventory.gacha_fragments
    total_rolls     = inventory.total_rolls
    menu_top        = "┌───────────────────────┐"
    menu_separator  = "├───────────────────────┤"
    menu_bottom     = "└───────────────────────┘"
    default_color   = 0xfdd835
    colors          = [0xe53935, 0xd81b60, 0x8e24aa, 0x5e35b1, 0x3949ab, 0x1e88e5, 0x039be5, 0x00acc1, 0x00897b, 0x43a047, 0x7cb342, 0xc0ca33, 0xfdd835, 0xffb300, 0xfb8c00, 0xf4511e]
    capsule_colors  = [0x2196f3, 0x4caf50, 0xef5350, 0xeceff1, 0xffeb3b, 0xe8eaf6]
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

    if checkAdmin(ctx) and skip == "skip":
        skip = True
    else:
        skip = False

    async def loadProgressBar(ctx, message, e):
        for step, color in enumerate(colors):
            e.color = color
            e.set_field_at(1, name = progressbar[step + 1], value = menu_bottom, inline = False)
            await message.edit(embed = e)
            time.sleep(0.5)

    def getPrize(tier, capsule):
        return prizes[tier]["prizes"][capsule]

    async def raffleEntry(ctx, message, e, tier, skip):
        name = prizes[tier]["name"]
        symbol = prizes[tier]["symbol"]
        cost = prizes[tier]["tickets_required"]
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Spin to win!", color = default_color)
        e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_6.png")
        e.add_field(name = f"{name} Raffle", value = symbol, inline = True)
        e.add_field(name = "Admission:", value = f"🎟️ x {cost} ticket(s)", inline = True)
        e.add_field(name = "Your current tickets:", value = tickets, inline = False)
        if tickets >= cost:
            e.add_field(name = "Tickets after spinning:", value = tickets - cost, inline = False)
            e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
            e.add_field(name = "▷ 🎲 ────  Spin the Gacha  ──── 🎲 ◁", value = menu_separator, inline = False)
            e.add_field(name = "▷ ↩️  ──  Select another Raffle  ──  ↩️ ◁", value = menu_bottom, inline = False)
            await message.edit(embed=e)
            emojis = ["🎲", "↩️"]
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                return message, e, False
            match str(reaction.emoji):
                case "🎲":
                    e.set_field_at(5, name = "►🎲 ────  Spin the Gacha  ──── 🎲 ◄", value = menu_separator, inline = False)
                    await message.edit(embed = e)
                    await message.clear_reactions()
                    message, e = await rollGacha(ctx, message, e, tier, name, cost, symbol, skip)
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

    async def rollGacha(ctx, message, e, tier, name, cost, symbol, skip):
        # Subtract ticket(s) from user's inventory, increment roll count, then roll the gacha
        DB.userdata[user_id] = {"gacha_tickets": tickets - cost, "gacha_fragments": fragments, "total_rolls": total_rolls + 1}
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Good luck!", color = default_color)
        e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_1.png")
        e.add_field(name = f"Spinning the {name} Raffle:", value = menu_top, inline = False)
        e.add_field(name = progressbar[0], value = menu_bottom, inline = False)
        await message.edit(embed = e)
        if not skip:
            await loadProgressBar(ctx, message, e)
        message, e = await pullCapsule(ctx, message, e, tier, name, cost, symbol)
        return message, e

    async def pullCapsule(ctx, message, e, tier, name, cost, symbol):
        cold_weights = config.weights[tier]
        if prizes[tier]["regulated"]:
            # Modify probability for regulated prize
            regulated_prize = prizes[tier]["prizes"]["platinum"]
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
            hot_weights = [cold_weights[0], cold_weights[1], cold_weights[2], cold_weights[3], cold_weights[4] + mod, cold_weights[5] - mod]
            # Use modified probabilities
            capsule = randomWeighted(capsules, hot_weights)
        else:
            # Use unmodified probabilities
            capsule = randomWeighted(capsules, cold_weights)
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = f"🎉 Congratulations {ctx.author.mention}! 🎊")
        match capsule:
            case "blue":
                e.color = capsule_colors[0]
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_2.png")
                e.set_image(url = "http://a.pianosuki.com/u/Capsule_Blue.png")
            case "green":
                e.color = capsule_colors[1]
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_2.png")
                e.set_image(url = "http://a.pianosuki.com/u/Capsule_Green.png")
            case "red":
                e.color = capsule_colors[2]
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_3.png")
                e.set_image(url = "http://a.pianosuki.com/u/Capsule_Red.png")
            case "silver":
                e.color = capsule_colors[3]
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_3.png")
                e.set_image(url = "http://a.pianosuki.com/u/Capsule_Silver.png")
            case "gold":
                e.color = capsule_colors[4]
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_4.png")
                e.set_image(url = "http://a.pianosuki.com/u/Capsule_Gold.png")
            case "platinum":
                e.color = capsule_colors[5]
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_4.png")
                e.set_image(url = "http://a.pianosuki.com/u/Capsule_Platinum.png")
        prize = getPrize(tier, capsule)
        e.add_field(name = "Raffle Spun:", value = f"{symbol} {name} {symbol}", inline = True)
        e.add_field(name = "You Won:", value = f"🎁 {prize} 🎁", inline = True)
        # Add record of prize to database
        prize_id = str(user_id) + str("{:05d}".format(total_rolls + 1))
        now = datetime.utcnow()
        DB.prizehistory[prize_id] = {"user_id": user_id, "date": now, "tickets_spent": cost, "tier": tier, "capsule": capsule, "prize": prize}
        if prizes[tier]["regulated"] and capsule == "platinum":
            # Update stock of prize if the prize was regulated
            DB.execute(f"INSERT OR IGNORE INTO backstock (prize, current_stock, times_rolled, max_limit) values ('{prize}', '0', '0', '0')")
            stock = DB.backstock[regulated_prize]
            current_stock = stock.current_stock
            times_rolled = stock.times_rolled
            max_limit = stock.max_limit
            DB.backstock[prize] = {"current_stock": current_stock - 1, "times_rolled": times_rolled + 1, "max_limit": max_limit}
        e.set_footer(text = f"Prize ID: {prize_id}")
        await message.edit(embed = e)
        return message, e

    # main()
    exit_flag = edit_flag = False
    while not (exit_flag):
        prev_flag = False
        e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Test your luck for amazing prizes!", color = default_color)
        e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_1.png")
        e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
        e.add_field(name = "▷ 📜 ─────  Prize  List  ────── 📜 ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ 🎰 ──── Select  a  Raffle ──── 🎰 ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ 📦 ── View your inventory ─── 📦 ◁", value = menu_bottom, inline = False)
        if not edit_flag:
            message = await ctx.send(embed = e)
        else:
            await message.edit(embed = e)
        emojis = ["📜", "🎰", "📦"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            break
        match str(reaction.emoji):
            case "📜":
                def formatPrizeList(prize_list):
                    formatted_prize_list = f"\
                        🔵  ─  *Blue*  ─  {config.encouragement[0]}%\n  └ **`{prize_list['blue']}`**\n\
                        🟢  ─  *Green*  ─  {config.encouragement[1]}%\n  └ **`{prize_list['green']}`**\n\
                        🔴  ─  *Red*  ─  {config.encouragement[2]}%\n  └ **`{prize_list['red']}`**\n\
                        ⚪  ─  *Silver*  ─  {config.encouragement[3]}%\n  └ **`{prize_list['silver']}`**\n\
                        🟡  ─  *Gold*  ─  {config.encouragement[4]}%\n  └ **`{prize_list['gold']}`**\n\
                        🟣  ─  *Platinum*  ─  {config.encouragement[5]}%\n  └ **`{prize_list['platinum']}`**\n\
                    "
                    return formatted_prize_list

                e.set_field_at(1, name = "►📜 ─────  Prize  List  ────── 📜 ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Here are today's prize pools:", color = default_color)
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_3.png")
                e.add_field(name = f"Tier 1: {prizes['tier_1']['symbol']}", value = formatPrizeList(prizes["tier_1"]["prizes"]), inline = True)
                e.add_field(name = f"Tier 2: {prizes['tier_2']['symbol']}", value = formatPrizeList(prizes["tier_2"]["prizes"]), inline = True)
                e.add_field(name = "\u200b", value = "\u200b", inline = True)
                e.add_field(name = f"Tier 3: {prizes['tier_3']['symbol']}", value = formatPrizeList(prizes["tier_3"]["prizes"]), inline = True)
                e.add_field(name = f"Tier 4: {prizes['tier_4']['symbol']}", value = formatPrizeList(prizes["tier_4"]["prizes"]), inline = True)
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
                        e.set_field_at(2, name = "►↩️ ───── Main  Menu ───── ↩️ ◄", value = menu_bottom, inline = False)
                        await message.edit(embed = e)
                        await message.clear_reactions()
            case "🎰":
                e.set_field_at(2, name = "►🎰 ──── Select  a  Raffle ──── 🎰 ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                while not (exit_flag or prev_flag):
                    e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Select a Gacha Unit to spin!", color = default_color)
                    e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_5.png")
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
                e.set_field_at(3, name = "►📦 ── View your inventory ─── 📦 ◄", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                e = discord.Embed(title = f"Welcome to the {branch_name} Gacha!", description = "Your inventory:", color = default_color)
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_5.png")
                e.add_field(name = "Gacha Tickets:", value = f"🎟️ x {tickets} ticket(s)", inline = False)
                e.add_field(name = "Gacha Ticket Fragments:", value = f"🧩 x {fragments} piece(s)", inline = False)
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

@bot.command(aliases = ["inventory"])
async def inv(ctx, target = None):
    ''' | Usage: +inv [@user] | Check the inventory of a user '''
    if target is None:
        target = ctx.author.mention
    # Ensure valid discord ID
    if re.match(r"<(@|@&)[0-9]{18}>", target):
        user_id = await convertMentionToId(target)
        # Check if user is already in database, if not then set them up default values of 0
        DB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values ("+str(user_id)+", '0', '0', '0')")
        inventory   = DB.userdata[user_id]
        tickets     = inventory.gacha_tickets
        fragments   = inventory.gacha_fragments
        total_rolls = inventory.total_rolls
        e = discord.Embed(title = "Viewing inventory of user:", description = target, color = 0xfdd835)
        e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_6.png")
        e.add_field(name = "Gacha Tickets:", value = f"🎟️ x {tickets} ticket(s)", inline = False)
        e.add_field(name = "Gacha Ticket Fragments:", value = f"🧩 x {fragments} piece(s)", inline = False)
        e.add_field(name = "Total roll count:", value = f"🎲 x {total_rolls} roll(s)", inline = False)
        await ctx.send(embed = e)
    else:
        await ctx.send("Please **@ mention** a valid user to check their inventory (!help inv)")

@bot.command()
async def craft(ctx):
    ''' | Usage: +craft | Craft a Gacha Ticket from 4 Gacha Pieces '''
    menu_top        = "┌───────────────────────┐"
    menu_separator  = "├───────────────────────┤"
    menu_bottom     = "└───────────────────────┘"
    user_id = await convertMentionToId(ctx.author.mention)
    DB.execute("INSERT OR IGNORE INTO userdata (user_id, gacha_tickets, gacha_fragments, total_rolls) values ("+str(user_id)+", '0', '0', '0')")
    inventory   = DB.userdata[user_id]
    tickets     = inventory.gacha_tickets
    fragments   = inventory.gacha_fragments
    total_rolls = inventory.total_rolls
    e = discord.Embed(title = "Crafting Menu", description = "Turn your Gacha Fragments into Gacha Tickets!", color = 0x00897b)
    e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_1.png")
    e.add_field(name = "Conversion Rate:", value = "`🧩 x 4 Pieces  =  🎟️ x 1 Gacha Ticket`", inline = False)
    e.add_field(name = "Your Gacha Ticket Fragments:", value = f"🧩 x {fragments} piece(s)", inline = False)
    if not fragments < 4:
        e.add_field(name = "Reaction Menu:", value = menu_top, inline = False)
        e.add_field(name = "▷ ⚒️ ─── Craft Gacha Ticket ─── ⚒️ ◁", value = menu_separator, inline = False)
        e.add_field(name = "▷ ❌ ─────  Exit  Menu  ─────  ❌ ◁", value = menu_bottom, inline = False)
        message = await ctx.send(embed = e)
        emojis = ["⚒️", "❌"]
        reaction, user = await waitForReaction(ctx, message, e, emojis)
        if reaction is None:
            return
        match str(reaction.emoji):
            case "⚒️":
                e.set_field_at(3, name = "►⚒️ ─── Craft Gacha Ticket ─── ⚒️ ◄", value = menu_separator, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                e = discord.Embed(title = "Crafting Menu", description = "Successfully crafted a Gacha Ticket!", color = 0x00897b)
                e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_6.png")
                e.add_field(name = "You now have this many Gacha Tickets:", value = f"🎟️ x {tickets + 1}", inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
                DB.userdata[user_id] = {"gacha_tickets": tickets + 1, "gacha_fragments": fragments - 4, "total_rolls": total_rolls}
            case "❌":
                e.set_field_at(4, name = "►❌ ─────  Exit  Menu  ─────  ❌ ◄", value = menu_bottom, inline = False)
                await message.edit(embed = e)
                await message.clear_reactions()
    else:
        e.add_field(name = "You have insufficient ticket pieces.", value = f"Need 🧩 x {4 - fragments} more!", inline = False)
        await ctx.send(embed = e)

@bot.command()
async def history(ctx, target = None):
    ''' | Usage: +history [@user] | View prize history of a user '''
    if target is None:
        target = ctx.author.mention
    if not checkAdmin(ctx):
        target = ctx.author.mention
    else:
        if not re.match(r"<(@|@&)[0-9]{18}>", target):
            await ctx.send("Admin-only: Please **@ mention** a valid user to view prize history of")
            return
    user_id = await convertMentionToId(target)
    history = DB.query(f"SELECT * FROM prizehistory WHERE user_id = '{user_id}'")
    history.reverse()
    history_length = len(history)
    e = discord.Embed(title = "View Prize History", description = f"History of {target}", color = 0xd81b60)
    e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_3.png")
    edit_flag = False
    counter = 0
    if history_length == 0:
        e.set_thumbnail(url = "http://a.pianosuki.com/u/KinkaMei_2.png")
        e.add_field(name = "User has not rolled any prizes yet!", value = "Try `+roll` to change that", inline = False)
        await ctx.send(embed = e)
        return
    for index, entry in enumerate(history):
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
        e.add_field(name = f"{index + 1}  ─  {circle} {prize_prize}", value = f"Prize ID: {prize_id}", inline = False)
        counter += 1
        if counter == 5 or index + 1 == history_length:
            if not edit_flag:
                message = await ctx.send(embed = e)
                edit_flag = True
            else:
                await message.edit(embed = e)
            if index + 1 < history_length:
                emojis = ["⏩", "❌"]
            else:
                emojis = ["❌"]
            reaction, user = await waitForReaction(ctx, message, e, emojis)
            if reaction is None:
                exit_flag = True
                return
            match str(reaction.emoji):
                case "⏩":
                    await message.clear_reactions()
                    e.clear_fields()
                    counter = 0
                case "❌":
                    await message.clear_reactions()
                    return

### Admin Commands
@bot.command()
@commands.check(checkAdmin)
async def reward(ctx, target: str, item: str, quantity):
    ''' | Usage: +reward <@user> <item> <quantity> | Items: "ticket", "fragment" '''
    # Ensure valid discord ID
    if re.match(r"<(@|@&)[0-9]{18}>", target):
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
async def simulate(ctx, tier, n: int):
    ''' | Usage: +simulate <Tier> <Simulations> '''
    capsules = [1, 2, 3, 4, 5, 6]
    outcomes = []
    for _ in range(n):
        outcomes.append(randomWeighted(capsules, config.weights[tier]))
    c = Counter(outcomes)
    for key in c:
        c[key] = c[key] / n
    await ctx.send(f"{sorted(c.values())}")

@bot.command()
@commands.check(checkAdmin)
async def restock(ctx, prize: str, stock: int, max_limit: int = -1, reset: bool = True):
    ''' | Usage: +restock <"Prize name"> <Stock> [Maximum roll limit] [Reset "times_rolled" counter? Default = True] '''
    data = DB.query(f"SELECT * FROM backstock WHERE prize = '{prize}'")
    if reset:
        times_rolled = 0
    else:
        times_rolled = DB.backstock[prize].times_rolled
    if max_limit == -1:
        max_limit = stock
    if data:
        e = discord.Embed(title = "Restock Prize Database", description = "Confirm the following:", color = 0xc0ca33)
        e.add_field(name = f"Stock of '{prize}' will be set to:", value = stock, inline = False)
        e.add_field(name = f"With a maximum limit of:", value = max_limit, inline = False)
        e.add_field(name = "Reset 'Times Rolled' counter:", value = reset, inline = False)
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
    ''' | Usage: +dashboard | View current statistics of the database '''

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
    pass

@bot.command()
@commands.check(checkAdmin)
async def test(ctx, tier, times_rolled: int):
    pass

bot.run(config.discord_token)
