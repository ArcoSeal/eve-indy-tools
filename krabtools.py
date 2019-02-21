import os
import sys
import csv
import dateutil.parser
import sqlite3
import argparse
import requests
import bz2
import re

from urllib.parse import urlparse
from datetime import datetime, timezone
from dateutil.tz import tzutc
from statistics import mean, stdev, StatisticsError
from math import ceil, floor
from operator import itemgetter

import sqlitetools
import auxdatatools
import crest
import evemarket
import indytools

import presets

# non-standard dependencies: requests, xlrd

auxdata_updated = False
debug, verbose = False, 0 # defaults, will be overridden by docmdargs()

def docmdargs():
    global cmdargs, forceupdateauxdata, skip_aux_data_check

    argparser = argparse.ArgumentParser()

    argparser.add_argument('-v','--verbose', help='Verbosity', action='count')
    argparser.add_argument('--debug', help='Debug mode', action='store_true', default=False)

    arg_group_auxupdate = argparser.add_mutually_exclusive_group(required=False)
    arg_group_auxupdate.add_argument('--forceauxupdate', help='Force update of auxiliary data (itemIDs, systemIDs etc.)', action='store_true', default=False)
    arg_group_auxupdate.add_argument('--skipauxupdate', help='Skip check of auxiliary data', action='store_true', default=False)

    arg_group_action = argparser.add_mutually_exclusive_group(required=False)
    arg_group_action.add_argument('--getpricesforfile', help='Get prices for .csv of item IDs and output to file', nargs='+', type=str)

    argparser.add_argument('--location', help='Location to use', type=str)

    cmdargs = argparser.parse_args()

    if cmdargs.debug:
        setdebug(True)
    else:
        setdebug(False)

    if not cmdargs.verbose:
        setverbosity(0)
    else:
        setverbosity(cmdargs.verbose)

    forceupdateauxdata = cmdargs.forceauxupdate
    skip_aux_data_check = cmdargs.skipauxupdate

def passglobals():
    # pass on some global variables to sub modules
    global verbose, debug

    sqlitetools.verbose, auxdatatools.verbose, crest.verbose, evemarket.verbose = verbose, verbose, verbose, verbose
    sqlitetools.debug, auxdatatools.debug, crest.debug, evemarket.debug = debug, debug, debug, debug

def setverbosity(n):
    # use setter method to ensure that submodules have their verbosity updated too
    global verbose
    if not isinstance(verbose, int) and not isinstance(verbose, bool): raise Exception('Invalid verbosity level: %s' % n)
    
    verbose = n
    passglobals()

def setdebug(n):
    # use setter method to ensure that submodules have their debug updated too
    global debug
    if not isinstance(n, bool): raise Exception('Invalid debug setting: %s' % n)

    if n: print('Debug mode is ON')
    passglobals()

def downloadfile(url, dlpath='./'):
    outfilepath = os.path.join(dlpath, os.path.basename(url))

    r = requests.get(url)

    with open(outfilepath, 'wb') as outfile:
        for chunk in r.iter_content(1024):
            outfile.write(chunk)

    return outfilepath

def decompress_bz2(bz2file, outfilepath=None, deletebz2=False):
    if not outfilepath: outfilepath = os.path.splitext(bz2file)[0]

    with open(bz2file, 'rb') as infile, open(outfilepath, 'wb') as outfile:
        outfile.write(bz2.decompress(infile.read()))

    if deletebz2: os.remove(bz2file)

    return outfilepath

def invert_dict(dict_in):
    return {v:k for k,v in dict_in.items()}

def currenttimeUTC():
    return datetime.now(tzutc())

def updateauxdata(url=presets.sde_fuzzwork_url, remove_temp_files=True):
    global auxdata_updated
    auxdata_updated = True

    if verbose: print('Downloading master data from %s...' % url)
    mainDB = downloadfile(url=url)

    if verbose: print('Decompressing...')
    mainDB = decompress_bz2(mainDB, deletebz2=remove_temp_files)

    if verbose: print('Extracting required data...')
    createauxDB(mainDB)

    if verbose: print('Creating metadata...')
    storefileupdateinfo(currenttimeUTC(), getlastmodified(url), metadatafile='auxdata_meta.txt')

    if remove_temp_files: os.remove(mainDB)

    if verbose: print('')

def createauxDB(masterDB, auxDB=presets.auxdataDB):
    for dataset in presets.auxdatainfo:
        dbtable, srctable, cols_to_keep = dataset['desttable'], dataset['srctable'], dataset['cols_to_keep']

        sqlitetools.copycolstonewDB(masterDB, srctable, auxDB, dbtable, cols_to_keep)

def auxdataneedsupdate(dbfile=presets.auxdataDB, metadatafile='auxdata_meta.txt', url=presets.sde_fuzzwork_url):
    if verbose: print('Checking %s...' % presets.auxdataDB, end='')

    if not os.path.isfile(metadatafile) or not os.path.isfile(dbfile): # if metadata or DB is missing
        if verbose: print('File(s) missing')
        return True

    dbtables = set([ii['desttable'] for ii in presets.auxdatainfo])
    if not dbtables.issubset(sqlitetools.tablesindb(dbfile)): # if tables are missing
        if verbose: print('Table(s) missing from DB')
        return True

    time_last_dl, time_last_mod = getfileupdateinfo(metadatafile)
    if not time_last_dl or not time_last_mod: # if meta info file is not complete...
        if verbose: print('Metadata incomplete')
        return True
    elif (getlastmodified(url) - time_last_mod).total_seconds() != 0: # or if data on server has been modified since last dl...
        if verbose: print('Data obsolete')
        return True
    elif (currenttimeUTC() - time_last_dl).days >= 30: # or if it's been >= 30 days
        if verbose: print('Data needs refresh')
        return True

    if verbose: print('done.')
    return False

def getlastmodified(url):
    r = requests.head(url)

    d = dateutil.parser.parse(r.headers['last-modified'])

    return d

def storefileupdateinfo(last_dl, last_mod, metadatafile, format='%a, %d %b %Y %H:%M:%S %Z'):
    last_dl, last_mod = last_dl.strftime(format), last_mod.strftime(format)

    with open(metadatafile, 'w', encoding='utf-8', newline='') as outfile:
        csvwriter = csv.writer(outfile, delimiter=' ')
        csvwriter.writerow(['last_dl', last_dl])
        csvwriter.writerow(['last_mod', last_mod])

def getfileupdateinfo(metadatafile):
    last_dl, last_mod = None, None
    if os.path.isfile(metadatafile):
        with open(metadatafile, 'r', encoding='utf-8', newline='') as infile:
            csvreader = csv.reader(infile, delimiter=' ')
            for line in csvreader:
                if line[0] == 'last_dl': last_dl = dateutil.parser.parse(line[1])
                if line[0] == 'last_mod': last_mod = dateutil.parser.parse(line[1])

    return (last_dl, last_mod)

def doUltimateMarketGroups():
    conn = sqlite3.connect(presets.auxdataDB)
    c = conn.cursor()

    # figure out what the ultimate group is for each marketGroup by following the parentGroups
    if 'ultimateGroupID' not in sqlitetools.columnsindbtable(presets.auxdataDB, 'MarketGroups'):
        c.execute('''ALTER TABLE MarketGroups ADD COLUMN ultimateGroupID INT''')

    d = conn.cursor() # we're going to need an extra cursor

    c.execute('''SELECT MarketGroupID, ParentGroupID FROM MarketGroups WHERE ParentGroupID IS NOT NULL''') # get all records that have a parent ID (i.e. are not master market groups)
    baserow = c.fetchone() # get the first record
    try:
        while baserow: # while we still have records
            basemarketgroupID = baserow[0] # the original market group, the one we're finding an ultimate group for
            
            thismarketgroupID, thisparentID = baserow[0], baserow[1] # starting group & parent group IDs for iteration
            while thisparentID: # while there is still a parentID i.e. there are more levels to go up
                d.execute('''SELECT MarketGroupID, ParentGroupID FROM MarketGroups WHERE MarketGroupID=?''', (thisparentID,)) # get the record for the parentID
                parentrow = d.fetchone()
                thismarketgroupID, thisparentID = parentrow[0], parentrow[1] # get the IDs of this record
                # if thisparentID exists, we still have a level to go up, so repeat for new parentID

            # if parentID is NULL/None, we have hit a master group
            d.execute('''UPDATE MarketGroups SET ultimateGroupID=? WHERE MarketGroupID=?''', (thismarketgroupID, basemarketgroupID)) # update ultimateGroupID of base record accordingly

            baserow = c.fetchone() # get next row to work on
    except:
        print(baserow)
        raise
    finally:
        conn.commit()
        conn.close()

def flagitemDB():
    if verbose: print('Flagging items to exclude from trading...')

    items_to_flag = []

    if 'ExcludeFromTrade' not in sqlitetools.columnsindbtable(presets.auxdataDB, 'Items'): sqlitetools.addcolumntodbtable(presets.auxdataDB, 'Items', 'ExcludeFromTrade', 'INT', 'DEFAULT 0')

    conn = sqlite3.connect(presets.auxdataDB)
    c = conn.cursor()

    c.execute('''DELETE FROM Items WHERE typeID IS NULL''') # delete any entries without an typeID
    c.execute('''DELETE FROM Items WHERE marketGroupID IS NULL AND typeName NOT LIKE ?''', ('%% Blueprint',)) # delete any entries without a marketGroupID, except T2 Blueprints

    if verbose: print('Flagging items not available on market...')
    items_to_flag.extend(c.execute('''SELECT typeID FROM Items WHERE marketGroupID IS NULL''').fetchall()) # delete entries with no marketGroupID i.e. cannot be sold on the market

    if verbose: print('Flagging items without documented market group...')
    items_to_flag.extend(c.execute('''SELECT Items.typeID FROM Items WHERE Items.marketGroupID not in (SELECT marketGroupID FROM MarketGroups)''').fetchall())

    if verbose: print('Flagging officer items...')
    items_to_flag.extend(c.execute('''SELECT typeID FROM Items WHERE typeName LIKE ?''', ('%%\'s Modified %',)).fetchall())
    items_to_flag.extend(c.execute('''SELECT typeID FROM Items WHERE typeName LIKE ?''', ('%%s\' Modified %',)).fetchall())

    if verbose:
        print('Flagging items in master market groups: ', end='')
        sql_cmd = '''SELECT marketGroupName FROM MarketGroups WHERE marketGroupID IN %s''' % sqlitetools.sql_placeholder_of_length(len(presets.ultimateMarketGroupsToSkip))
        print(', '.join([jj[0] for jj in c.execute(sql_cmd, presets.ultimateMarketGroupsToSkip).fetchall()]))
    
    sql_cmd = '''SELECT Items.typeID FROM Items NATURAL JOIN MarketGroups WHERE MarketGroups.ultimateGroupID IN %s''' % sqlitetools.sql_placeholder_of_length(len(presets.ultimateMarketGroupsToSkip))
    items_to_flag.extend(c.execute(sql_cmd, presets.ultimateMarketGroupsToSkip).fetchall())

    if verbose:
        print('Flagging items in sub market groups: ', end='')
        sql_cmd = '''SELECT marketGroupName FROM MarketGroups WHERE marketGroupID IN %s''' % sqlitetools.sql_placeholder_of_length(len(presets.subMarketGroupsToSkip))
        print(', '.join([jj[0] for jj in c.execute(sql_cmd, presets.subMarketGroupsToSkip).fetchall()]))

    sql_cmd = '''SELECT typeID FROM Items WHERE marketGroupID IN %s''' % sqlitetools.sql_placeholder_of_length(len(presets.subMarketGroupsToSkip))
    items_to_flag.extend(c.execute(sql_cmd, presets.subMarketGroupsToSkip).fetchall())

    if verbose:
        print('Flagging specific items: ', end='')
        sql_cmd = '''SELECT typeName FROM Items WHERE typeName IN %s''' % sqlitetools.sql_placeholder_of_length(len(presets.itemsToSkip))
        print(', '.join([jj[0] for jj in c.execute(sql_cmd, presets.itemsToSkip).fetchall()]))

    sql_cmd = '''SELECT typeID FROM Items WHERE typeName IN %s''' % sqlitetools.sql_placeholder_of_length(len(presets.itemsToSkip))
    items_to_flag.extend(c.execute(sql_cmd, presets.itemsToSkip).fetchall())

    items_to_flag = [ii[0] for ii in items_to_flag] # flatten list [(x1,), (x2,)...] -> [x1, x2...]

    for item in items_to_flag: c.execute('''UPDATE Items SET ExcludeFromTrade=1 WHERE typeID = %s''' % item)

    if verbose:
        print('Total items flagged: %s' % conn.total_changes)
        print('')

    conn.commit()
    conn.close()

def trimBPDB():
    if verbose: print('Trimming BP data...')

    conn = sqlite3.connect(presets.auxdataDB)
    c = conn.cursor()

    sql_cmd = ('''DELETE FROM Materials
                    WHERE activityID NOT IN %s ''' % sqlitetools.sql_placeholder_of_length(len(presets.bp_activities.values())))

    c.execute(sql_cmd, list(presets.bp_activities.values()))

    sql_cmd = ('''DELETE FROM Products
                    WHERE activityID NOT IN %s ''' % sqlitetools.sql_placeholder_of_length(len(presets.bp_activities.values())))

    c.execute(sql_cmd, list(presets.bp_activities.values()))

    conn.commit()
    conn.close()

    if verbose: print('Flagging manufacturable items...')

    if 'Manufacturable' not in sqlitetools.columnsindbtable(presets.auxdataDB, 'Items'): sqlitetools.addcolumntodbtable(presets.auxdataDB, 'Items', 'Manufacturable', 'INT', 'DEFAULT 0')

    items_to_flag = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'bpProducts', 'productTypeID', 'activityID', presets.bp_activities['Manufacturing'])
    items_to_flag = [ii for ii in items_to_flag if ii] # get rid of items which don't resolve to a name - 
    # !TODO: fix this properly with trimBPDB()
    items_to_flag = sorted(items_to_flag)

    conn = sqlite3.connect(presets.auxdataDB)
    c = conn.cursor()

    for item in items_to_flag: c.execute('''UPDATE Items SET Manufacturable=1 WHERE typeID = %s''' % item)

    if verbose:
        print('%s manufacturable items total' % conn.total_changes)
        print('')

    conn.commit()
    conn.close()
        
def checkstrisfloat(string):
    try:
        float(string)
    except ValueError:
        return False

    return True

def readdatafromcsv(filename, header=True, cols_to_keep=None):
    with open(filename, 'r', encoding='utf-8', newline='') as infile:
        dialect = csv.Sniffer().sniff(infile.read(1024), delimiters=";,")
        infile.seek(0)
        csvreader = csv.reader(infile, dialect)

        if header:
            headers = next(csvreader)
        else:
            headers = [str(ii) for ii in range(0, len(next(csvreader)))]
            infile.seek(0)

        csvfile = {}
        for col in headers: csvfile[col] = []

        for line in csvreader:
            line_parse = [float(ii) if checkstrisfloat(ii) else ii for ii in line]
            for h,v in zip(headers, line_parse):
                csvfile[h].append(v)

    if cols_to_keep:
        if isinstance(cols_to_keep, int):
            csvfile = csvfile[headers[cols_to_keep]]
        else:
            cols_to_keep = set(cols_to_keep), set(range(0,len(headers)))

            cols_to_del = cols_to_del.difference(cols_to_keep)

            for col in cols_to_del:
                del csvfile[headers[col]]

    return csvfile

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

def pulladjprices(updatedb):
    if verbose: print('Updating adjusted prices...')

    data = crest.getcrestdata(crest.getcresturl('adjprices'))

    adjprices = []
    for item in data['items']: adjprices.append( (item['type']['id'], item['adjustedPrice']) )

    if updatedb:
        if 'adjPrice' not in sqlitetools.columnsindbtable(presets.auxdataDB, 'Items'): sqlitetools.addcolumntodbtable(presets.auxdataDB, 'Items', 'adjPrice', 'REAL')

        conn = sqlite3.connect(presets.auxdataDB)
        c = conn.cursor()

        for entry in adjprices: c.execute('''UPDATE Items SET adjPrice=? WHERE typeID=?''', (entry[1], entry[0]))

        if verbose > 1: print('Updated %s adjusted prices' % conn.total_changes)

        conn.commit()
        conn.close()

    else:
        return adjprices

def getadjpriceforitem(item):
    item = auxdatatools.getitemid(item)

    if 'adjPrice' not in sqlitetools.columnsindbtable(presets.auxdataDB, 'Items'): pulladjprices(updatedb=True)

    return sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Items', 'adjPrice', 'typeID', item)

def calcbasecostforitem(item, updatedb=True):
    matslist = indytools.getmatsforitem(item)

    baseCost = 0
    for matID, matqty in matslist.items(): baseCost += (getadjpriceforitem(matID) * matqty)

    baseCost = round(baseCost, 2)

    if updatedb:
        if 'baseCost' not in sqlitetools.columnsindbtable(presets.auxdataDB, 'Items'): sqlitetools.addcolumntodbtable(presets.auxdataDB, 'Items', 'baseCost', 'REAL')

        conn = sqlite3.connect(presets.auxdataDB)
        c = conn.cursor()

        c.execute('''UPDATE Items SET baseCost=? WHERE typeID=?''', (baseCost, item))

        conn.commit()
        conn.close()

    return baseCost

def getbasecostforitem(item):
    item = auxdatatools.getitemid(item)

    if 'baseCost' not in sqlitetools.columnsindbtable(presets.auxdataDB, 'Items'):
        baseCost = calcbasecostforitem(item)
    else:
        baseCost = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'Items', 'baseCost', 'typeID', item)
        if not baseCost: baseCost = calcbasecostforitem(item)

    return baseCost

def deleteindypriceDB():
    if os.path.isfile(presets.indypriceDB): os.remove(presets.indypriceDB)

def initauxdata():
    global forceupdateauxdata

    if not skip_aux_data_check and (forceupdateauxdata or auxdataneedsupdate()):
        updateauxdata()
 
        doUltimateMarketGroups()
        flagitemDB()
        pulladjprices(updatedb=True)
        trimBPDB()
        deleteindypriceDB()

        forceupdateauxdata = False # turn off force update for next time

## SHIT HERE GETS RUN REGARDLESS
docmdargs()

if __name__ == '__main__':
    
    initauxdata()

    if cmdargs.getpricesforfile:
        # read a list of items from a file, get the price stats and write back out

        infilepath = cmdargs.getpricesforfile[0]
        # if not out file is specified we will overwrite the input file
        if len(cmdargs.getpricesforfile) > 1:
            outfilepath = cmdargs.getpricesforfile[1]
        else:
            outfilepath = infilepath

        itemstopull = readdatafromcsv(infilepath, cols_to_keep=1) # get list of item IDs to pull
        itemstopull = [int(ii) for ii in itemstopull] # make sure IDs are ints

        if not cmdargs.location:
            location = 'Jita'
        else:
            location = cmdargs.location

        location = auxdatatools.getlocationid(location)

        if verbose: print('Getting prices for location: %s' % auxdatatools.getlocationname(location))

        data_out = []

        if verbose: print_str=''
        counter = 0
        for itemID in itemstopull:
            counter += 1

            itemName = auxdatatools.getitemName(itemID)

            if verbose:
                if len(print_str) > 0: print('\r' + ' '*len(print_str), end='\r')
                print_str = 'Pulling data for item %s of %s... (%s)' % (counter, len(itemstopull), itemName)
                print(print_str, end='')
                sys.stdout.flush()

            itemstats_buy, itemstats_sell = evemarket.getitemstats(itemID, location, 'buy'), evemarket.getitemstats(itemID, location, 'sell', get_region_stats=False)
            itemstats = [itemName, itemID, itemstats_buy[3], itemstats_sell[3], itemstats_buy[5]]
            data_out.append(itemstats)

        if verbose: print('')

        header_out = ['typeName', 'typeID', 'percentilePrice_buy', 'percentilePrice_sell', 'meanRegionalVolume_7day']

        if verbose: print('Writing data to %s ...' % outfilepath, end='')
        with open(outfilepath, 'w', encoding='utf-8', newline='') as outfile:
            csvwriter = csv.writer(outfile, delimiter=',')
            csvwriter.writerow(header_out)
            csvwriter.writerows(data_out)

        if verbose: print('done.')

    else:
        pass