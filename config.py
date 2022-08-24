import tokens

# Discord
discord_token   = tokens.discord_token
prefix          = "+"

# Names
coin_name       = "VIP Chips"

# RPG
level_cap       = 100

# RNG
weights         = {"tier_1": [25, 25, 25, 10, 10, 5], # Probability % out of 100 for each capsule respectively. (Must add up to 100 total!)
                   "tier_2": [35, 34, 15, 10, 5, 1],
                   "tier_3": [40, 30, 23.25, 5, 1, 0.75],
                   "tier_4": [45, 30, 23.499, 1, 0.001, 0.5]}
weight_mods     = [0, 0.2, 0.4] # Applied respectively according to how many times prize has been rolled. 0 rolled = weight_mods[0], 1 rolled = weight_mods[1], etc.
encouragement   = {"tier_1": [32, 25, 18, 12, 8, 5],
                   "tier_2": [32, 25, 18, 12, 8, 5],
                   "tier_3": [32, 25, 20, 12, 7, 4],
                   "tier_4": [32, 25, 20, 15, 5, 3]}

# Server
ip              = "137.220.33.63"
serve_dir       = "u"

# Permissions
admin_list      = [462763810365898783, 859699653128486912, 629713896747433995, 458993054674583556, 889201372636004432, 343431814347751445, 886841560275234856, 559568144033906708, 115775022848671749]
admin_role      = "Core Team"
wl_role         = "VIPLIST"
og_role         = "OG Voyager"
emerald_role    = "Emerald"
sapphire_role   = "Sapphire"
gacha_mod_role  = 1006676686647083090

# Channels
channels = {
    "roll": [1006348295192457316, 1006436350523867186],
    "market": [1006348295192457316, 1006678330021511168],
    "quests": [1006348295192457316],
    "dungeons": [1006348295192457316],
    "party": [1006678330021511168],
    "chat_earn": [987164353734258739],
    "exp": [1006348295192457316],
    "history": [1006678330021511168, 1006436350523867186],
    "craft": [1006678330021511168, 1006436350523867186],
    "inv": [1006678330021511168, 1006436350523867186],
    "leaderboard": [1006678330021511168, 1006436350523867186]
}

# UI
menu_top        = "┌───────────────────────┐"
menu_separator  = "├───────────────────────┤"
menu_bottom     = "└───────────────────────┘"
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
default_color   = 0xfdd835
colors          = [0xe53935, 0xd81b60, 0x8e24aa, 0x5e35b1, 0x3949ab, 0x1e88e5, 0x039be5, 0x00acc1, 0x00897b, 0x43a047, 0x7cb342, 0xc0ca33, 0xfdd835, 0xffb300, 0xfb8c00, 0xf4511e]
capsule_colors  = [0x2196f3, 0x4caf50, 0xef5350, 0xeceff1, 0xffeb3b, 0xd1c4e9]
capsules        = ["blue", "green", "red", "silver", "gold", "platinum"]
numbers         = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "0️⃣"]
# Testing server: custom_emojis   = {"ryou": "<:ryouu1:1004945368460578908>", "ticket": "<:gamaticket:1003394371883892826>", "fragment": "<:GachaTicketReg:1004959178814668881>", "exp": "<:exp:1005561171295879308>", "level": "<:level:1005563309124223067>"}
custom_emojis   = {"coins": "<:vchip:1006673117143375942>", "ticket": "🎟️", "fragment": "🧩", "exp": "🕹️", "level": "⭐", "emerald": "<:emer1:1006682498048196759>", "sapphire": "<:sapphire:1006682500405411961>"}
default_emojis  = {"coins": "🪙", "ticket": "🎟️", "fragment": "🧩", "exp": "🕹️", "level": "⭐"}
venue_list      = ["Los Vegas", "Paris", "Bangkok", "Prague", "Vienna", "Venice", "Syndey", "Tokyo", "New York", "Dubai"]

# Conversion rate
conv_rate   = [100, 1] # [Coins, Tickets]
conv_tax    = 10 # Will divide by this number

# Intervals (seconds)
party_wait      = 43200
quest_wait      = 28800
dungeon_wait    = 43200
chat_earn_wait  = 180

# Ranges
chat_coins_earn = [1, 2] # [Min, Max]
party_reward    = [10, 100]

# Boosts
role_boosts = {
    "Sapphire": 100,
    "Emerald": 50,
    "VIP Booster": 20,
    "OG Voyager": 20,
    "Diamond Voyager": 10
}
