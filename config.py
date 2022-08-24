import tokens

# Discord
discord_token   = tokens.discord_token
prefix          = "+"

# Names
coin_name       = "GAMA D-Coins"

# RPG
level_cap               = 100
mode_mapping            = {-1: "Any", 0: "Normal", 1: "Hard", 2: "Hell", 3: "Oni"}
mode_mapping_inverse    = {"Any": -1, "Normal": 0, "Hard": 1, "Hell": 2, "Oni": 3}
mode_multipliers        = {-1: 0, 0: 1, 1: 2, 2: 3, 3: 5}
mode_divisors           = {-1: 1, 0: 4, 1: 3, 2: 2, 3: 1}
default_rooms_range     = [2, 5]
default_mob_spawnrate   = [0, 3]
goldaruma_spawnrate     = 1
default_chest_loot      = [{"pool": {"Ryou": [100, 200]}, "rate": 50}, {"pool": {"EXP": [100, 200]}, "rate": 50}]
consumables             = {
    "Tuna Nigiri": 50,
    "Salmon Nigiri": 100,
    "Anago Nigiri": 200,
    "Squid Nigiri": 300,
    "Octopus Nigiri": 450,
    "Ootoro Nigiri": 650,
    "Kinmedai Nigiri": 1000,
    "Crab Nigiri": 1500,
    "Lobster Nigiri": 2500,
    "Shachihoko Nigiri": 5000,
    "Shenlong Nigiri": 10000
}

# RNG
weights         = {"tier_1": [25, 25, 20, 15, 10, 5], # Probability % out of 100 for each capsule respectively. (Must add up to 100 total!)
                   "tier_2": [25, 25, 20, 15, 10, 5],
                   "tier_3": [25, 25, 20, 15, 10, 5],
                   "tier_4": [29, 25, 20, 15, 10, 1]}
weight_mods     = [1] # Applied respectively according to how many times prize has been rolled. 0 rolled = weight_mods[0], 1 rolled = weight_mods[1], etc.
encouragement   = {"tier_1": [32, 25, 18, 12, 8, 5],
                   "tier_2": [32, 25, 18, 12, 8, 5],
                   "tier_3": [32, 25, 18, 12, 8, 5],
                   "tier_4": [32, 25, 18, 12, 8, 5]}

# Server
ip              = "137.220.33.63"
serve_dir       = "u"

# Permissions
admin_role      = "Catheon Core"
admin_list      = [462763810365898783, 859699653128486912, 629713896747433995, 458993054674583556, 889201372636004432, 559568144033906708, 115775022848671749]
wl_role         = "VIP WL PASS (Silver)"
gold_pass_role  = "GOLD PASS"
og_role         = "o🇬 (500)"
gacha_mod_role  = 989407410693210117

# Channels
channels = {
    "roll": [1001853369285099590],
    "tavern": [1001869730992361554],
    "quests": [1011471996011413514],
    "dungeons": [1011471996011413514],
    "chat_earn": [989407418008096807],
    "exp": [1011471996011413514],
    "history": [1001853369285099590, 1001869730992361554],
    "craft": [1001853369285099590, 1001869730992361554],
    "inv": [1001853369285099590, 1001869730992361554],
    "stats": [1011471996011413514],
    "leaderboard": [1001853369285099590, 1001869730992361554],
    "restore": [1011471996011413514]
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
numbers         = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
# Testing server: custom_emojis   = {"ryou": "<:ryouu1:1004945368460578908>", "ticket": "<:gamaticket:1003394371883892826>", "fragment": "<:GachaTicketReg:1004959178814668881>", "exp": "<:exp:1005561171295879308>", "level": "<:level:1005563309124223067>"}
custom_emojis   = {
    "ryou": "<:GAMADCOIN:1003392621005262931>",
    "ticket": "<:gamaticket:1003394371883892826>",
    "fragment": "<:GachaTicketReg:1004959142458446005>",
    "exp": "<:exp:1006052726603517954>",
    "level": "<:level:1006053105420484669>",
    "energy": "<:energy:1007492998487097365>",
    "dungeon": "<:dungeon:1007493881174184048>",
    "door_closed": "<:door_closed:1007714383893368882>",
    "door_open": "<:door_open:1007714397633921045>",
    "material_common": "<:material_common:1007728592756691024>",
    "material_rare": "<:material_rare:1007728607050866758>",
    "material_special": "<:material_special:1007728619172417670>",
    "yokai": "<:yokai:1009485551440765048>",
    "chest": "<:chest:1009486809916518563>",
    "attack": "<:attack:1009540591182430208>",
    "defend": "<:defend:1009540603920523374>",
    "exit": "<:exit:1009544808479604856>",
    "statsreset": "<:statsreset:1010726645885308928>",
    "supercharge": "<:supercharge:1011404535505371146>",
    "evade": "<:evade:1011404551565365308>"
}
mode_emojis     = {
    "normal": "<:normal:1007526343501688862>",
    "hard": "<:hard:1007526356428537947>",
    "hell": "<:hell:1007526372090073159>",
    "oni": "<:oni:1007526385746710609>"
}
element_emojis  = {
    "Fire": "<:fire:1007710358695317545>",
    "Ice": "<:ice:1007710391872262264>",
    "Lightning": "<:lightning:1007710798447120544>",
    "Rain": "<:rain:1007710309051547748>",
    "Mountain": "<:mountain:1007710371852849226>",
    "Wind": "<:wind:1007710345961418772>",
    "Holy": "<:holy:1007710333252665345>",
    "Dark": "<:dark:1007710321571541052>"
}
nigiri_emojis   = {
    "riceball": "<:riceball:1010803854838861856>",
    "tuna_nigiri": "<:tuna_nigiri:1010803682826264617>",
    "salmon_nigiri": "<:salmon_nigiri:1010803695920877629>",
    "anago_nigiri": "<:anago_nigiri:1010803708755443742>",
    "squid_nigiri": "<:squid_nigiri:1010803725591400458>",
    "octopus_nigiri": "<:octopus_nigiri:1010803745833107456>",
    "ootoro_nigiri": "<:ootori_nigiri:1010803758676066335>",
    "kinmedai_nigiri": "<:kinmedai_nigiri:1010803779056173158>",
    "crab_nigiri": "<:crab_nigiri:1010803797750198313>",
    "lobster_nigiri": "<:lobster_nigiri:1010803813181050920>",
    "shachihoko_nigiri": "<:shachihoko_nigiri:1010803825424203806>",
    "shenlong_nigiri": "<:shenlong_nigiri:1010803837898072064>"
}

# Conversion rate
conv_rate   = [1000000, 1] # [Ryou, Tickets]

# Intervals (seconds)
quest_wait      = 28800
dungeon_wait    = 43200
chat_earn_wait  = 300

# Ranges
chat_ryou_earn  = [1, 2] # [Min, Max]

# Boosts
role_boosts = {
    "Diamond-Oni": 50,
    "Gold-Oni": 30,
    "Silver-Oni": 20,
    "Oni": 10,
    "Demi-God": 8,
    "Exemplar": 5,
    "OniOG": 7,
    "Oni-Booster": 20
}
