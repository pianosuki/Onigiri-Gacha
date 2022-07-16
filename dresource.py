import config
import discord

def isDir(item):
    return type(item) is dict

def isArray(item):
    return type(item) is list

def hasArrays(item):
    return any(isinstance(subitem, list) for subitem in item)

def resCreate(dictionary, Resource = {}):
    for key in dictionary:
        if isDir(dictionary[key]):
            # Recursive
            resCreate(dictionary[key], Resource)
        else:
            if hasArrays(dictionary[key]):
                # Handle arrays inside of arrays
                index = 1
                for item in dictionary[key]:
                    try:
                        file = discord.File(item[0], filename = item[1])
                        url = f"http://{config.ip}/{config.serve_dir}/{item[0]}"
                        Resource.update({f"{key}-{index}": [url, file, item[2]]})
                        index +=1
                    except FileNotFoundError:
                        # Only build resource with existing local files
                        continue
            else:
                if isArray(dictionary[key]):
                    # Handle tails
                    file = discord.File(dictionary[key][0], filename = dictionary[key][1])
                    url = f"http://{config.ip}/{config.serve_dir}/{dictionary[key][0]}"
                    Resource.update({key: [url, file, dictionary[key][2]]})
    return Resource
