## Data that (currently) has to be manually specified

sde_fuzzwork_url = 'https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2'

auxdataDB = 'auxdata.sqlite3'

marketDB = 'market.sqlite3'
indypriceDB = 'indyprices.sqlite3'

# Blueprints (2), Skills (150), Structures (477), Apparel (1396), Special Edition Assets (1659), Pilot's Services (1922), Ship SKINs (1954), Infantry Gear (350001)
ultimateMarketGroupsToSkip = (2, 150, 477, 1396, 1659, 1922, 1954, 350001)
# Titans (812-816), Boosters (491, 977, 1858), SE Ships
subMarketGroupsToSkip = tuple(range(812,816+1)) + (491, 977, 1858) + (1612, 1614, 1631, 1698, 1699, 1837, 1838, 2115) + tuple(range(1618,1624+1))
# specific item names to skip
itemsToSkip = ('Metal Scraps', 'Nyx', 'Wyvern', 'Aeon', 'Hel')

null_regions = ('Branch','Cache','Catch','Cloud Ring','Cobalt Edge','Curse','Deklein','Delve','Detorid','Esoteria','Etherium Reach','Fade','Feythabolis','Fountain','Geminate','Great Wildlands','Immensea','Impass','Insmother','The Kalevala Expanse','Malpais','Oasa','Omist','Outer Passage','Outer Ring','Paragon Soul','Period Basis','Perrigen Falls','Providence','Pure Blind','Querious','Scalding Pass','The Spire','Stain','Syndicate','Tenal','Tenerifis','Tribute','Vale of the Silent','Venal','Wicked Creek')
jove_regions = ('A821-A', 'J7HZ-F', 'UUA-F4')

trade_hubs = ('Jita', 'Amarr', 'Dodixie', 'Rens', 'Hek')

auxdatainfo = (
                {
                'desttable' : 'Items',
                'srctable' : 'invTypes',
                'cols_to_keep' : ('typeID', 'typeName', 'groupID', 'marketGroupID'),
                },

                {
                'desttable' : 'MarketGroups',
                'srctable' : 'invMarketGroups',
                'cols_to_keep' : ('marketGroupID', 'parentGroupID', 'marketGroupName'),
                },
                
                {
                'desttable' : 'Regions',
                'srctable' : 'mapRegions',
                'cols_to_keep' : ('regionID', 'regionName'),
                },

                {
                'desttable' : 'Systems',
                'srctable' : 'mapSolarSystems',
                'cols_to_keep' : ('solarsystemID', 'solarsystemName', 'regionID', 'constellationID', 'security'),
                },

                {
                'desttable' : 'Stations',
                'srctable' : 'staStations',
                'cols_to_keep' : ('stationID', 'stationName', 'solarsystemID', 'corporationID'),
                },

                {
                'desttable' : 'bpMaterials',
                'srctable': 'industryActivityMaterials',
                'cols_to_keep' : ('typeID', 'activityID', 'materialTypeID', 'quantity'),
                },

                {
                'desttable' : 'bpProducts',
                'srctable': 'industryActivityProducts',
                'cols_to_keep' : ('typeID', 'activityID', 'productTypeID', 'quantity'),
                },

                {
                'desttable' : 'bpTimes',
                'srctable': 'industryActivity',
                'cols_to_keep' : ('typeID', 'activityID', 'time'),
                },
                )
                
# auxdatainfo = (item_data, marketGroup_data, region_data, system_data, station_data, bp_in_data, bp_out_data)

# del item_data, region_data, system_data, marketGroup_data, station_data, bp_in_data, bp_out_data

bp_activities = {'Manufacturing' : 1, 'Researching Time Efficiency' : 3, 'Researching Material Efficiency' :4 , 'Copying' : 5, 'Reverse Engineering' : 7, 'Invention' : 8}

decryptors = {
                'Accelerant'               : {'inventChanceMod' : 1.2, 'runsMod' : 1, 'MEMod' :  2, 'TEMod' :  10},
                'Attainment'               : {'inventChanceMod' : 1.8, 'runsMod' : 4, 'MEMod' : -1, 'TEMod' :   4},
                'Augmentation'             : {'inventChanceMod' : 0.6, 'runsMod' : 9, 'MEMod' : -2, 'TEMod' :   2},
                'Optimized Attainment'     : {'inventChanceMod' : 1.9, 'runsMod' : 3, 'MEMod' :  1, 'TEMod' :  -2},
                'Optimized Augmentation'   : {'inventChanceMod' : 0.9, 'runsMod' : 7, 'MEMod' :  2, 'TEMod' :   0},
                'Parity'                   : {'inventChanceMod' : 1.5, 'runsMod' : 3, 'MEMod' :  1, 'TEMod' :  -2},
                'Process'                  : {'inventChanceMod' : 1.1, 'runsMod' : 0, 'MEMod' :  3, 'TEMod' :   6},
                'Symmetry'                 : {'inventChanceMod' : 1.0, 'runsMod' : 2, 'MEMod' :  1, 'TEMod' :   8},
                'NONE'                     : {'inventChanceMod' : 1.0, 'runsMod' : 0, 'MEMod' :  0, 'TEMod' :   0},
                }

invent_types = {
                'Small Intact Hull Section'            : {'inventChance' : 0.39, 'runs' :  20},
                'Small Malfunctioning Hull Section'    : {'inventChance' : 0.35, 'runs' :  10},
                'Small Wrecked Hull Section'           : {'inventChance' : 0.26, 'runs' :   3},
                'Intact Hull Section'                  : {'inventChance' : 0.39, 'runs' :  20},
                'Malfunctioning Hull Section'          : {'inventChance' : 0.35, 'runs' :  10},
                'Wrecked Hull Section'                 : {'inventChance' : 0.26, 'runs' :   3},
                'Modules'                              : {'inventChance' : 0.34, 'runs' :  10},
                'Rigs'                                 : {'inventChance' : 0.34, 'runs' :   1},
                'Ammo'                                 : {'inventChance' : 0.34, 'runs' : 100},
                'Frigates'                             : {'inventChance' : 0.30, 'runs' :   1},
                'Destroyers'                           : {'inventChance' : 0.30, 'runs' :   1},
                'Cruisers'                             : {'inventChance' : 0.26, 'runs' :   1},
                'Battlecruisers'                       : {'inventChance' : 0.26, 'runs' :   1},
                'Battleships'                          : {'inventChance' : 0.22, 'runs' :   1},
                'Freighters'                           : {'inventChance' : 0.18, 'runs' :   1},
                }