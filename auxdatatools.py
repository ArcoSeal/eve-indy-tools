## Functions for doing quick queries on auxiliary data

import sqlitetools
from urllib.parse import urljoin

import presets

def urljoin_long(*args):
    # join a url using unlimited sections (like with os.path.join)
    return urljoin(args[0], '/'.join(args[1:]))

def getregionID(name):
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Regions', 'regionID', 'regionName', name)

def getregionName(ID):
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Regions', 'regionName', 'regionID', ID)

def isregion(region):
    if isinstance(region, str):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Regions', 'regionName', region)
    elif isinstance(region, int):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Regions', 'regionID', region)
    else:
        raise Exception()

def getsystemID(name):
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Systems', 'solarSystemID', 'solarSystemName', name)

def getsystemName(ID):
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Systems', 'solarSystemName', 'solarSystemID', ID)

def getsystemsecurity(system):
    if isinstance(system, str): system = getsystemID(system)
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Systems', 'Security', 'solarSystemID', system)

def getsystemregion(system):
    if isinstance(system, str): system = getsystemID(system)
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Systems', 'regionID', 'solarSystemID', system)

def issystem(system):
    if isinstance(system, str):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Systems', 'solarSystemName', system)
    elif isinstance(system, int):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Systems', 'solarSystemID', system)
    else:
        raise Exception()

def isitem(item):
    if isinstance(item, str):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Items', 'typeName', item)
    elif isinstance(item, int):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Items', 'typeID', item)
    else:
        raise Exception()

def isbp(bp):
    if isinstance(bp, str): bp = getitemid(bp)

    if isinstance(bp, int):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'bpProducts', 'typeID', bp)
    else:
        raise Exception()

def hasbp(item):
    item = getitemid(item)

    return sqlitetools.checkifitemindb(presets.auxdataDB, 'bpProducts', 'productTypeID', item)

def getstationid(name):
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Stations', 'stationID', 'stationName', name)

def getstationname(ID):
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Stations', 'stationName', 'stationID', ID)

def getstationcorp(station):
    if isinstance(station, str): station = getstationid(station)
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Stations', 'corporationID', 'stationID', station)

def getstationsystem(station):
    if isinstance(station, str): station = getstationid(station)
    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Stations', 'solarSystemID', 'stationID', station)

def getstationregion(station):
    if isinstance(station, str): station = getstationid(station)
    return getsystemregion(getstationsystem(station))

def isstation(station):
    if isinstance(station, str):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Stations', 'stationName', station)
    elif isinstance(station, int):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Stations', 'stationID', station)
    else:
        raise Exception()

def islocation(location):
    return (isregion(location) or issystem(location) or isstation(location))

def getlocationid(location):
    if isregion(location):
        return getregionID(location)
    elif issystem(location):
        return getsystemID(location)
    elif isstation(location):
        return getstationid(location)
    else:
        raise Exception()

def getlocationname(location):
    if isregion(location):
        return getregionName(location)
    elif issystem(location):
        return getsystemName(location)
    elif isstation(location):
        return getstationname(location)
    else:
        raise Exception()

def getlocationregion(location):
    if isinstance(location, str): location = getlocationid(location)

    if isregion(location):
        return location
    elif issystem(location):
        return getsystemregion(location)
    elif isstation(location):
        return getstationregion(location)
    else:
        raise Exception()

def getitemid(name):
    if isitem(name):
        if isinstance(name, int):
            return name
        if isinstance(name, str):
            return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Items', 'typeID', 'typeName', name)
        else:
            raise Exception('Unexpected type for item: %s (%s)' % (name, type(name)))
    else:
        raise Exception('Not an item! %s' % name)

def getitemName(ID):
    if isitem(ID):
        if isinstance(ID, str):
            return ID
        if isinstance(ID, int):
            return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Items', 'typeName', 'typeID', ID)
        else:
            raise Exception()
    else:
        # raise Exception('Invalid item: %s' % ID)
        return None
    
def getitemNames(IDs):
    out = []
    for ID in IDs: out.append(getitemName(ID))

    if isinstance(IDs, tuple): out = tuple(out)

    return out

def geticonfilename(itemID, size):
    if not isinstance(itemID, int): raise Exception()
    return str(itemID)+'_'+str(size)+'.png'

def geticonurl(itemID, size):
    if size not in (32, 64): raise Exception('Invalid icon size: %s')
    if not isinstance(itemID, int): itemID = getitemid(itemID)

    baseURL = 'https://image.eveonline.com/'
    filename = geticonfilename(itemID, size)

    return urljoin_long(baseURL, 'Type', filename)

def isitem(item):
    if isinstance(item, str):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Items', 'typeName', item)
    elif isinstance(item, int):
        return sqlitetools.checkifitemindb(presets.auxdataDB, 'Items', 'typeID', item)
    else:
        raise Exception('Unexpected type for item: %s (%s), expecting int (ID) or str (name)' % (item, type(item)) )

def getallmarketitems():
    return sqlitetools.getallitemsfromdbcol(presets.auxdataDB, 'Items', 'typeID')

def getbpIDforitem(item):
    # get the ID for the BP that produces the given item, if it exists
    item = getitemid(item) # get item ID if necessary

    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'bpProducts', 'typeID', 'productTypeID', item)

def getmatsforbp(bp, activity='Manufacturing'):
    # get the inputs needed for specified BP (1 run, no ME modifiers)
    if isinstance(activity, str): activity = presets.bp_activities[activity]

    mats_list = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'bpMaterials', ('materialTypeID', 'quantity'), ('typeID', 'activityID'), (bp, activity))

    mats_dict = {}
    for mat in mats_list: mats_dict[mat[0]] = mat[1]

    return mats_dict

def isT2(check):
    # checks if an item (or its BP) is T2, by finding if its BP can be produce by invention
    # check: item (name or ID) or BP (ID) to check
    
    if isbp(check):
        bp = check
    else:
        bp = getbpIDforitem(check)

    entries = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'bpProducts', 'activityID', 'productTypeID', bp, flatten_on_single_match=False)
  
    # this probably isn't necessary, but just in case there's more than one way of making a BP we check that it's due to Invention
    if entries:
        activityID_invent = presets.bp_activities['Invention']
        for entry in entries:
            if entry == activityID_invent:
                return True

    return False

def getinventbase(product):
    # gets the T1 BP ID from which a T2/T3 item's BP is invented
    # product: T2/T3 item (name or ID) or BP (ID)
    # if we're inventing T3, this will return a list of multiple items (the hull section types)

    if isbp(product):
        bp_T2 = product
    else:
        bp_T2 = getbpIDforitem(product)

    activityID_invent = presets.bp_activities['Invention']
    bp_T1 = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'bpProducts', 'typeID', ('productTypeID', 'activityID'), (bp_T2, activityID_invent), flatten_on_single_match=True)

    return bp_T1

def ishullsection(item):
    item = getitemName(item)

    if 'Hull Section' in item:
        return True
    else:
        return False

def getBPproductgroup(bp):
    bp = getitemid(bp)
    marketgroupid = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Items', 'marketGroupID', 'typeID', bp, flatten_on_single_match=True)
    parentgroupid = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'MarketGroups', 'parentGroupID', 'marketGroupID', marketgroupid, flatten_on_single_match=True)
    parentgroupname = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'MarketGroups', 'marketGroupName', 'marketGroupID', parentgroupid, flatten_on_single_match=True)

    if 'Rigs' in parentgroupname: parentgroupname = 'Rigs'

    return parentgroupname

def getBPtime(bp, activity):
    if isinstance(activity, str): activity = presets.bp_activities[activity]

    time = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'bpTimes', 'time', ('typeID', 'activityID'), (bp, activity), flatten_on_single_match=True)

    return time

    
