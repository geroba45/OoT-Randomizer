import io
import hashlib
import logging
import os
import struct
import random

from HintList import getHint, getHintGroup, Hint
from ItemList import eventlocations
from Messages import update_message_by_id
from TextBox import lineWrap

def buildHintString(hintString):
    if len(hintString) < 77:
        hintString = "They say that " + hintString
    elif len(hintString) < 82:
        hintString = "They say " + hintString
    # captitalize the sentance
    hintString = hintString[:1].upper() + hintString[1:]

    return hintString


def getItemGenericName(item):
    if item.type == 'Map' or item.type == 'Compass' or item.type == 'BossKey' or item.type == 'SmallKey' or item.type == 'FortressSmallKey':
        return item.type
    else:
        return item.name


def isDungeonItem(item):
    return item.type == 'Map' or item.type == 'Compass' or item.type == 'BossKey' or item.type == 'SmallKey'


def add_hint(world, id, text):
    world.spoiler.hints[id] = lineWrap(text)


def writeGossipStoneHintsHints(world, messages):
    for id,text in world.spoiler.hints.items():
        update_message_by_id(messages, id, get_raw_text(text))

def filterTrailingSpace(text):
    if text.endswith('& '):
        return text[:-1]
    else:
        return text

hintPrefixes = [
    'a few ',
    'some ',
    'plenty of ',
    'a ',
    'an ',
    'the ',
    '',
]

def getSimpleHintNoPrefix(item):
    hint = getHint(item.name, True).text

    for prefix in hintPrefixes:
        if hint.startswith(prefix):
            # return without the prefix
            return hint[len(prefix):]

    # no prefex
    return hint

def colorText(text, color):
    colorMap = {
        'White':      '\x40',
        'Red':        '\x41',
        'Green':      '\x42',
        'Blue':       '\x43',
        'Light Blue': '\x44',
        'Pink':       '\x45',
        'Yellow':     '\x46',
        'Black':      '\x47',
    }

    colorTags = False
    while True:
        splitText = text.split('#', 2)
        if len(splitText) == 3:
            splitText[1] = '\x05' + colorMap[color] + splitText[1] + '\x05\x40'
            text = ''.join(splitText)
            colorTags = True
        else:
            text = '#'.join(splitText)
            break

    if not colorTags:
        for prefix in hintPrefixes:
            if text.startswith(prefix):
                text = text[:len(prefix)] + '\x05' + colorMap[color] + text[len(prefix):] + '\x05\x40'
                break

    return text


#builds out general hints based on location and whether an item is required or not
def buildGossipHints(world):

    stoneIDs = [0x0401, 0x0402, 0x0403, 0x0404, 0x0405, 0x0406, 0x0407, 0x0408,
                0x0409, 0x040A, 0x040B, 0x040C, 0x040D, 0x040E, 0x040F, 0x0410,
                0x0411, 0x0412, 0x0413, 0x0414, 0x0415, 0x0416, 0x0417, 0x0418,
                0x0419, 0x041A, 0x041B, 0x041C, 0x041D, 0x041E, 0x041F, 0x0420]

    #shuffles the stone addresses for randomization, always locations will be placed first
    random.shuffle(stoneIDs)

    # Initialize these now.
    requiredSample = world.spoiler.required_locations[world.id]
    alwaysLocations = getHintGroup('alwaysLocation', world)
    sometimesLocations = getHintGroup('location', world)

    # Determine number of each type of hint to add.
    hintMultiplication = {
        'trial': 1,
        'woth': 1,
        'requiredLocation': 1
    }
    hintCounts = {
        'trial': sum(hintMultiplication['trial'] for trial,skipped in world.skipped_trials.items() if
                     (6 > world.trials > 3 and skipped) or (3 >= world.trials > 0 and not skipped)),
        'woth': 0,
        'requiredLocation': len(alwaysLocations) * hintMultiplication['requiredLocation'],
        'goodlocation': 0,
        'badDungeon': 0,
        'badOverworld': 0,
        'goodItem': 0,
        'joke': 0  # Joke hints will fill the rest of the gossips regardless.
    }

    if world.hint_distribution == 'powerful':
        # Powerful Hints
        hintMultiplication['woth'] = 3
        hintCounts['woth'] = 4 * hintMultiplication['woth']
        hintMultiplication['requiredLocation'] = 2
        hintCounts['requiredLocation'] = hintCounts['requiredLocation'] * hintMultiplication['requiredLocation']
        # Good Item and Bad Overworld/Dungeon hints fill out the remainder, split as evenly as possible.
        hintCounts['goodItem'] = int((len(stoneIDs) - sum(hintCounts.values())) / 2)
        if (sum(hintCounts.values()) % 2) != 0:
            hintCounts['goodItem'] += random.randint(0,1)
        hintCounts['badOverworld'] = random.randint(0, (len(stoneIDs) - sum(hintCounts.values())))
        hintCounts['badDungeon'] = (len(stoneIDs) - sum(hintCounts.values()))
        # Remove Lens of Truth and other bad hint items from Way of the Hero.
        requiredSample = [x for x in requiredSample if x not in world.spoiler.pseudo_required_locations[world.id]]
    elif world.hint_distribution == 'jokes':
        # Jokes!
        hintCounts['trial'] = 0
        hintCounts['requiredLocation'] = 0
        hintCounts['joke'] = len(stoneIDs)
    else:
        # Normal Hints
        hintCounts['woth'] = hintMultiplication['woth'] * len(requiredSample) if not len(requiredSample) >= 5 else random.randint(3,4)
        hintCounts['goodlocation'] = random.randint(11,12) - len(alwaysLocations)
        hintCounts['badDungeon'] = random.randint(3,4)
        # Use bad overworld hints to balance hints given via trials
        if world.trials == 3:
            hintCounts['badOverworld'] = random.randint(1,2)
        elif world.trials in [2, 4]:
            hintCounts['badOverworld'] = random.randint(1,3)
        elif world.trials in [1, 5]:
            hintCounts['badOverworld'] = random.randint(2,3)
        else:
            hintCounts['badOverworld'] = random.randint(2,4)
        hintCounts['goodItem'] = random.randint(4,6)
        hintCounts['joke'] = len(stoneIDs) - sum(hintCounts.values())

    # Add trial hints
    trialHintsAdded = 0
    for i in range(hintMultiplication['trial']):
        for trial, skipped in world.skipped_trials.items():
            if trialHintsAdded >= hintCounts['trial']:
                break
            if world.trials < 6 and world.trials > 3 and skipped:
                trialHintsAdded += 1
                add_hint(world, stoneIDs.pop(0), buildHintString("the " + colorText(trial + " Trial", 'Yellow') + " was dispelled by Sheik."))
            elif world.trials <= 3 and world.trials > 0 and not skipped:
                trialHintsAdded += 1
                add_hint(world, stoneIDs.pop(0), buildHintString("the " + colorText(trial + " Trial", 'Pink') + " protects Ganon's Tower."))

    # add required items locations for hints (good hints)
    requiredSample = random.sample(requiredSample, int(hintCounts['woth'] / hintMultiplication['woth']))
    for i in range(hintMultiplication['woth']):
        j = 0
        for location in requiredSample:
            j += 1
            if (len(requiredSample) * i) + j > hintCounts['woth']:
                break
            if location.parent_region.dungeon:
                add_hint(world, stoneIDs.pop(0), buildHintString(colorText(getHint(location.parent_region.dungeon.name, world.clearer_hints).text, 'Light Blue') + \
                    " is on the way of the hero."))
            else:
                add_hint(world, stoneIDs.pop(0), buildHintString(colorText(location.hint, 'Light Blue') + " is on the way of the hero."))

    # Don't repeat hints
    checkedLocations = []

    # Add required location hints
    for i in range(hintMultiplication['requiredLocation']):
        j = 0
        for hint in alwaysLocations:
            j += 1
            if (len(alwaysLocations) * i) + j > hintCounts['requiredLocation']:
                break
            for locationWorld in world.get_locations():
                if hint.name == locationWorld.name:
                    checkedLocations.append(hint.name)
                    add_hint(world, stoneIDs.pop(0), buildHintString(colorText(getHint(locationWorld.name, world.clearer_hints).text, 'Green') + " " + \
                        colorText(getHint(getItemGenericName(locationWorld.item), world.clearer_hints).text, 'Red') + "."))


    # Add good location hints
    if sometimesLocations:
        for _ in range(0, hintCounts['goodlocation']):
            hint = random.choice(sometimesLocations)
            # Repick if location isn't new
            while hint.name in checkedLocations or hint.name in alwaysLocations:
                hint = random.choice(sometimesLocations)

            for locationWorld in world.get_locations():
                if hint.name == locationWorld.name:
                    checkedLocations.append(locationWorld.name)    
                    add_hint(world, stoneIDs.pop(0), buildHintString(colorText(getHint(locationWorld.name, world.clearer_hints).text, 'Green') + " " + \
                        colorText(getHint(getItemGenericName(locationWorld.item), world.clearer_hints).text, 'Red') + "."))

    # add bad dungeon locations hints
    for dungeon in random.sample(world.dungeons, hintCounts['badDungeon']):
        # Choose a random dungeon location that is a non-dungeon item
        dungeon_locations = [location for region in dungeon.regions for location in region.locations
            if location.item.type != 'Event' and \
            location.item.type != 'Shop' and \
            not location.locked and \
            not isDungeonItem(location.item) and \
            (world.tokensanity != 'off' or location.item.type != 'Token') and\
            location.item.type != 'Song']
        if (len(dungeon_locations) == 0):
            continue
        locationWorld = random.choice(dungeon_locations)

        checkedLocations.append(locationWorld.name)
        add_hint(world, stoneIDs.pop(0), buildHintString(colorText(getHint(dungeon.name, world.clearer_hints).text, 'Green') + \
            " hoards " + colorText(getHint(getItemGenericName(locationWorld.item), world.clearer_hints).text, 'Red') + "."))

    # add bad overworld locations hints
    # only choose location if it is new and a proper item from the overworld
    overworldlocations = [locationWorld for locationWorld in world.get_locations()
            if not locationWorld.name in checkedLocations and \
            not locationWorld.name in alwaysLocations and \
            not locationWorld.name in sometimesLocations and \
            locationWorld.item.type != 'Event' and \
            locationWorld.item.type != 'Shop' and \
            not locationWorld.locked and \
            (world.tokensanity == 'all' or locationWorld.item.type != 'Token') and \
            not locationWorld.parent_region.dungeon]
    for locationWorld in random.sample(overworldlocations, hintCounts['badOverworld']):
        checkedLocations.append(locationWorld.name)
        add_hint(world, stoneIDs.pop(0), buildHintString(colorText(getHint(getItemGenericName(locationWorld.item), world.clearer_hints).text, 'Red') + \
            " can be found at " + colorText(locationWorld.hint, 'Green') + ".")) 

    # add good item hints
    # only choose location if it is new and a good item
    gooditemlocations = [locationWorld for locationWorld in world.get_locations() 
            if not locationWorld.name in checkedLocations and \
            locationWorld.item.advancement and \
            locationWorld.item.type != 'Event' and \
            locationWorld.item.type != 'Shop' and \
            not locationWorld.locked and \
            locationWorld.item.type != 'Token' and \
            not locationWorld.item.key]
    for locationWorld in random.sample(gooditemlocations, hintCounts['goodItem']):
        checkedLocations.append(locationWorld.name)
        if locationWorld.parent_region.dungeon:
            add_hint(world, stoneIDs.pop(0), buildHintString(colorText(getHint(locationWorld.parent_region.dungeon.name, world.clearer_hints).text, 'Green') + \
                " hoards " + colorText(getHint(getItemGenericName(locationWorld.item), world.clearer_hints).text, 'Red') + "."))
        else:
            add_hint(world, stoneIDs.pop(0), buildHintString(colorText(getHint(getItemGenericName(locationWorld.item), world.clearer_hints).text, 'Red') + \
                " can be found at " + colorText(locationWorld.hint, 'Green') + "."))

    # fill the remaining hints with junk    
    junkHints = getHintGroup('junkHint', world)
    random.shuffle(junkHints)
    while stoneIDs:
        add_hint( world, stoneIDs.pop(0), junkHints.pop().text )

# builds boss reward text that is displayed at the temple of time altar for child and adult, pull based off of item in a fixed order.
def buildBossRewardHints(world, messages):
    bossRewardsSpiritualStones = ['Kokiri Emerald', 'Goron Ruby', 'Zora Sapphire']
    bossRewardsMedallions = ['Forest Medallion', 'Fire Medallion', 'Water Medallion', 'Shadow Medallion', 'Spirit Medallion', 'Light Medallion']

    # text that appears at altar as a child.
    text = '\x08'
    text += get_raw_text(getHint('Spiritual Stone Text Start', world.clearer_hints).text)
    for reward in bossRewardsSpiritualStones:
        text += buildBossString(reward, world)

    text = setRewardColor(text)
    text += get_raw_text(getHint('Spiritual Stone Text End', world.clearer_hints).text)
    text += '\x0B'

    update_message_by_id(messages, 0x707a, text, 0x20)


    # text that appears at altar as an adult.
    start = '\x08When evil rules all, an awakening\x01voice from the Sacred Realm will\x01call those destined to be Sages,\x01who dwell in the \x05\x41five temples\x05\x40.\x04'
    text = ''
    for reward in bossRewardsMedallions:
        text += buildBossString(reward, world)

    text = setRewardColor(text)
    text += get_raw_text(getHint('Medallion Text End', world.clearer_hints).text)
    text += '\x0B'

    update_message_by_id(messages, 0x7057, start + text, 0x20)

# pulls text string from hintlist for reward after sending the location to hintlist.
def buildBossString(reward, world):
    text = ''
    for location in world.get_locations():
        if location.item.name == reward:
            text += '\x08' + get_raw_text(getHint(location.name, world.clearer_hints).text)
    return text

# alternates through color set commands in child and adult boss reward hint strings setting the colors at the start of the string to correspond with the reward found at the location.
# skips over color commands at the end of stings to set color back to white.
def setRewardColor(text):
    rewardColors = ['\x42', '\x41', '\x43', '\x45', '\x46', '\x44']

    colorWhite = True
    for i, char in enumerate(text):
        if char == '\x05' and colorWhite:
            text = text[:i + 1] + rewardColors.pop(0) + text[i + 2:]
            colorWhite = False 
        elif char == '\x05' and not colorWhite:
            colorWhite = True
        
    return text

# fun new lines for Ganon during the final battle
def buildGanonText(world, messages):
    # empty now unused messages to make space for ganon lines
    update_message_by_id(messages, 0x70C8, " ")
    update_message_by_id(messages, 0x70C9, " ")
    update_message_by_id(messages, 0x70CA, " ")

    # lines before battle
    text = '\x08'
    ganonLines = getHintGroup('ganonLine', world)
    random.shuffle(ganonLines)
    text = get_raw_text(ganonLines.pop().text)
    update_message_by_id(messages, 0x70CB, text)

    # light arrow hint or validation chest item
    text = '\x08'
    if world.trials == 0:
        for location in world.get_locations():
            if location.item.name == 'Light Arrows':
                text = get_raw_text(getHint('Light Arrow Location', world.clearer_hints).text)
                location_hint = location.hint.replace('Ganon\'s Castle', 'my castle')
                location_hint = location.hint.replace('Ganon\'s Tower', 'my tower')
                text += get_raw_text(location_hint)
                text += '!'
                break
    else:
        text = get_raw_text(getHint('Validation Line', world.clearer_hints).text)
        for location in world.get_locations():
            if location.name == 'Ganons Tower Boss Key Chest':
                text += get_raw_text(getHint(getItemGenericName(location.item), world.clearer_hints).text)
                text += '!'
                break
    
    update_message_by_id(messages, 0x70CC, text)
        
def get_raw_text(string):
    text = ''
    for char in string:
        if char == '^':
            text += '\x04' # box break
        elif char == '&':
            text += '\x01' #new line
        elif char == '@':
            text += '\x0F' #print player name
        elif char == '#':
            text += '\x05\x40' #sets color to white
        else:
            text += char
    return text
