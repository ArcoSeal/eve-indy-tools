# Functions for dealing with market order data

import sys
from statistics import mean, median, stdev, StatisticsError
from numpy import percentile

import auxdatatools
import sqlitetools
import crest

def getdailystats(item, region, days_back=1):
    # CREST history returns data for previous 13 months, days_back specifies how many days of data to retrieve
    # days_back = 1 will get just yesterday's data
    if isinstance(item, str): item = auxdatatools.getitemid(item)
    if isinstance(region, str): region = auxdatatools.getregionID(region)

    stats = crest.getcrestdata(crest.getcresturl('DailyStats', regionID=region, typeID=item))['items']

    return list(reversed(stats))[0:days_back]

def getorders(item, location, order_type):
    order_type = order_type.lower()
    if isinstance(item, str): item = auxdatatools.getitemid(item)
    if isinstance(location, str): location = auxdatatools.getlocationid(location)

    region = auxdatatools.getlocationregion(location)

    if order_type == 'buy':
        url, params = crest.getcresturl('BuyOrders', regionID=region, typeID=item)
    elif order_type == 'sell':
        url, params = crest.getcresturl('SellOrders', regionID=region, typeID=item)
    else:
        raise Exception()

    regionOrders =  crest.getcrestdata(url, params)['items']

    if auxdatatools.isregion(location):
        return regionOrders
    elif auxdatatools.issystem(location) or auxdatatools.isstation(location):
        return selectordersbylocation(regionOrders, location)

def getbuyorders(item, location):
    return getorders(item, location, 'Buy')

def getsellorders(item, location):
    return getorders(item, location, 'Sell')

def getorderstation(order):
    return order['location']['id']

def getordersystem(order):
    return auxdatatools.getstationsystem(getorderstation(order))

def getorderregion(order):
    return auxdatatools.getstationregion(getorderstation(order))

def selectordersbylocation(orders, location):
    if isinstance(location, str): location = auxdatatools.getlocationid(location)

    found_orders = []
    for order in orders:
        if (auxdatatools.isstation(location) and getorderstation(order) == location) \
        or (auxdatatools.issystem(location) and getordersystem(order) == location) \
        or (auxdatatools.isregion(location) and getorderregion(order) == location):
            found_orders.append(order)

    return found_orders

def getordertime(order):
    return order['issued']

def getordervolume(order):
    return order['volume']

def getorderprice(order):
    return order['price']

def getmeanpriceoforders(orders):
    return round(mean([getorderprice(order) for order in orders]), 2)

def getmedianpriceoforders(orders):
    return round(median([getorderprice(order) for order in orders]), 2)

def getstdpriceoforders(orders):
    return round(stdev([getorderprice(order) for order in orders]), 2)

def getpercentilepriceoforders(orders, pctile):
    return round(percentile([getorderprice(order) for order in orders], pctile), 2)

def gettotalvolumeoforders(orders):
    return sum([getordervolume(order) for order in orders])

def getitemstats(item, location, order_type, orders=None, get_region_stats=True, return_type='tuple'):
    if not orders: orders = getorders(item, location, order_type) # pull orders from CREST if orders not supplied

    if len(orders) == 0:
        meanPrice, medianPrice, stdPrice, percentilePrice, nOrders = None, None, None, None, None
    else:
        meanPrice, medianPrice = getmeanpriceoforders(orders), getmedianpriceoforders(orders)
        percentilePrice = ( getpercentilepriceoforders(orders, 95) if order_type == 'buy' else getpercentilepriceoforders(orders, 5) ) # highest 5% for buy, lowest 5% for sell
        try:
            stdPrice = getstdpriceoforders(orders)
        except StatisticsError:
            if len(orders) == 1:
                stdPrice = 0
            else:
                print(orders)
                raise
        
        nOrders = len(orders)
        
    if get_region_stats:
        region = auxdatatools.getlocationregion(location)

        meanRegionalVolume, stdRegionalVolume = getavgregionstats(item, region, avg_period=7)
    
        if return_type == 'dict':
            return {'meanPrice' : meanPrice, 'medianPrice' : medianPrice, 'stdPrice' : stdPrice, 'percentilePrice' : percentilePrice, 'nOrders' : nOrders, 'meanRegionalVolume' : meanRegionalVolume, 'stdRegionalVolume' : stdRegionalVolume}
        elif return_type == 'tuple':
            return (meanPrice, medianPrice, stdPrice, percentilePrice, nOrders, meanRegionalVolume, stdRegionalVolume)
    
    else:
        if return_type == 'dict':
            return {'meanPrice' : meanPrice, 'medianPrice' : medianPrice, 'stdPrice' : stdPrice, 'percentilePrice' : percentilePrice, 'nOrders' : nOrders}
        elif return_type == 'tuple':
            return (meanPrice, medianPrice, stdPrice, percentilePrice, nOrders)

def getavgregionstats(item, region, avg_period):
    tries, max_tries, retry_wait = 0, 2, 5 # retry a few times if the wrong length of data comes back - it happens sometimes
    while tries <= max_tries:
        tries += 1
        if verbose and tries > 1: print('retrying %s/%s' % (tries, max_tries))
        DailyStats = getdailystats(item, region, avg_period)
        if len(DailyStats) < avg_period:
            if tries < max_tries:
                if verbose:
                    if tries == 1: print('')
                    print('Daily stats not of expected length, sleeping %ss before retry...' % retry_wait, end='')
                time.sleep(retry_wait)
            else:
                break # give up after we hit max retries
        else:
            break
        
    if len(DailyStats) != avg_period:
        meanRegionalVolume, stdRegionalVolume = None, None
    else:
        try:
            meanRegionalVolume = mean([day['volume'] for day in DailyStats])
            stdRegionalVolume = stdev([day['volume'] for day in DailyStats])
        except StatisticsError:
            print(DailyStats)
            raise

    return (meanRegionalVolume, stdRegionalVolume)

def getpricelist(items, order_type, location='Jita'):
    # get a dict of buy or sell prices for list of items, at a given location
    # items: list of items (name or ID), or list of materials e.g. ((item1, quantity1), (item2, quantity2))
    # returned dict is of form {item1ID : {order_type : price}}
    
    if isinstance(items, str) or isinstance(items, int):
        items = [items] # so we can iterate if there's just one item
    elif (isinstance(items, list) or isinstance(items, tuple)) and (isinstance(items[0], list) or isinstance(items[0], tuple)):
        items = [ii[0] for ii in items] # if we have a materials list, get just the items 

    pricelist = {}

    if verbose > 1: counter, print_str = 0, ''
    for item in items:
        if verbose > 1:
            counter += 1
            if len(print_str) > 0: print('\r' + ' '*len(print_str), end='\r')
            print_str = 'Getting price for item %s/%s...' % (counter, len(items))
            print(print_str, end='')
            sys.stdout.flush()
        
        item = auxdatatools.getitemid(item)

        price = getitemstats(item, location, order_type, get_region_stats=False, return_type='dict')['percentilePrice']

        if item not in pricelist: pricelist[item] = {}
        pricelist[item][order_type] = price

    if verbose > 1: print('done')

    return pricelist

def combinepricelists(pricelist_master, pricelist_new, overwrite=True):
    # updates an older pricelist dict with newer prices and/or items
    # if overwrite is False, only new items will be added (previously existing prices will remain the same)

    for item in pricelist_new:
        if item in pricelist_master: # updating with newer prices
            for order_type in pricelist_new[item]:
                if (order_type not in pricelist_master[item]) or (pricelist_master[item][order_type] == None) or overwrite:
                    pricelist_master[item][order_type] = pricelist_new[item][order_type]
        else:
            pricelist_master[item] = pricelist_new[item] # adding new item

    return pricelist_master

def refreshpricelist(pricelist, location='Jita'):
    items_buy, items_sell = [], []

    for item in pricelist:
        if 'buy' in pricelist[item]: items_buy.append(item)
        if 'sell' in pricelist[item]: items_sell.append(item)

    pricelist_buy = getpricelist(items_buy, 'buy', location)
    pricelist_sell = getpricelist(items_sell, 'sell', location)

    pricelist = combinepricelists(pricelist_buy, pricelist_sell, overwrite=False)

    return pricelist

def iteminpricelist(item, pricelist, order_type):
    item = auxdatatools.getitemid(item)

    if item in pricelist:
        if order_type in pricelist[item] and pricelist[item][order_type] != None:
            return True

    return False

def addmissingitemstopricelist(items, pricelist, order_type, location='Jita'):
    if isinstance(items, str) or isinstance(items, int): items = [items]

    missingitems = []
    for item in items:
        item = auxdatatools.getitemid(item)
        if not iteminpricelist(item, pricelist, order_type): missingitems.append(item)

    if missingitems: pricelist = combinepricelists(pricelist, getpricelist(items, order_type, location))

    return pricelist

def calcbuyfee(order_value, buy_from_order_type, skillBrokerRelations=None, brokerFeeRate=None):
    if not brokerFeeRate: brokerFeeRate = calcbrokerfeerate(skillBrokerRelations)

    if isinstance(order_value, list) or isinstance(order_value, tuple):
        feesList = []
        for order in order_value: feesList.append(calcbuyfee(order, buy_from_order_type, brokerFeeRate=brokerFeeRate))
        return feesList

    else:
        if buy_from_order_type == 'sell':
            fee = 0
        elif buy_from_order_type == 'buy':
            fee = round(order_value * brokerFeeRate, 2)

        return fee

def calcsellfee(order_value, sell_to_order_type, skillBrokerRelations, skillAccounting, brokerFeeRate=None, salesTaxRate=None):  
    if not brokerFeeRate: brokerFeeRate = calcbrokerfeerate(skillBrokerRelations)
    if not salesTaxRate: salesTaxRate = calcsalestaxrate(skillAccounting)

    if isinstance(order_value, list) or isinstance(order_value, tuple):
        feesList = []
        for order in order_value: feesList.append(calcsellfee(order, sell_to_order_type, brokerFeeRate=brokerFeeRate, salesTaxRate=salesTaxRate))
        return feesList

    else:
        if sell_to_order_type == 'buy':
            fee = round(order_value * salesTaxRate, 2)
        elif sell_to_order_type == 'sell':
            fee = round(order_value * salesTaxRate, 2) + round(order_value * brokerFeeRate, 2)

        return fee

def calcbrokerfeerate(skillBrokerRelations):
    checkvalidskilllevel(skillBrokerRelations)

    brokerFeeRate = 0.03 - (skillBrokerRelations*0.01) # starts at 3%, reduces by 0.1% per level - MAY CHANGE IN FUTURE PATCHES

    return brokerFeeRate

def calcsalestaxrate(skillAccounting):
    checkvalidskilllevel(skillAccounting)

    salesTaxRate = 0.02 * (1 - skillAccounting*0.1) # starts at 2%, reduced by 10% of initial (0.2%) per level - MAY CHANGE IN FUTURE PATCHES

    return salesTaxRate

def checkvalidskilllevel(skills):
    if not (isinstance(skills, list) or isinstance(skills, tuple)):
        if isinstance(skills, int):
            skills = [skills]
        elif isinstance(skills, float):
            if not skills.isinteger():
                raise Exception('Invalid skill level: %s, must be int' % skills)
            else:
                skills = [skills]
        else:
            raise Exception('Invalid skill or skills: %s' % skills)

    for skill in skills:
        if skill < 0 or skill > 5:
            raise Exception('Invalid skill level: %s' % skill)
        else:
            pass

def savepricelisttoDB(pricelist, db):
    sqlitetools.createtable(db, 'Prices', ('typeID INT PRIMARY KEY NOT NULL', 'buy REAL', 'sell REAL'))

    pricelist_list = []
    for item in pricelist:
        for order_type in ('buy', 'sell'):
            if order_type not in pricelist[item]: pricelist[item][order_type] = None
        pricelist_list.append( (item, pricelist[item]['buy'], pricelist[item]['sell']) )

    sqlitetools.insertmany(db, 'Prices', pricelist_list)

def loadpricelistfromDB(db):
    entries = sqlitetools.getxbyyfromdb(db, 'Prices', ('typeID', 'buy', 'sell'), 'ALL', 'ALL')

    pricelist = {}

    for entry in entries:
        pricelist[entry[0]] = {}
        pricelist[entry[0]]['buy'] = entry[1]
        pricelist[entry[0]]['sell'] = entry[2]

    if verbose: print('loaded %s entries' % len(pricelist))

    return pricelist


