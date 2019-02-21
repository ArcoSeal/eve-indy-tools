def initmarketDB():
    conn = sqlite3.connect(presets.marketDB)
    c = conn.cursor()

    c.execute('''DROP TABLE IF EXISTS MarketItems''')
    c.execute('''CREATE TABLE MarketItems
                    (EntryID INTEGER PRIMARY KEY,
                    ItemID INT,
                    systemID INT,
                    MeanPrice REAL,
                    MedianPrice REAL,
                    StdPrice REAL,
                    PercentilePrice REAL,
                    nOrders INT,
                    MeanRegionalVolume REAL,
                    StdRegionalVolume REAL
                    )''')

    conn.commit()
    conn.close()

    inittradetable()

def inittradetable():
    conn = sqlite3.connect(presets.marketDB)
    c = conn.cursor()

    c.execute('''DROP TABLE IF EXISTS Trades''')
    c.execute('''CREATE TABLE Trades
                    (EntryID INTEGER PRIMARY KEY,
                    ItemID INT,
                    BuysystemID INT,
                    BuyMedianPrice REAL,
                    BuyMeanRegionalVolume REAL,
                    SellsystemID INT,
                    SellMedianPrice REAL,
                    SellMeanRegionalVolume REAL,
                    nSellOrders INT
                    )''')

    conn.commit()
    conn.close()

def pullitemstatstomarketDB(items, systems, order_type, cache_limit=200, resume=False):
    # cache_limit: maximum number of DB entries to be held in memory before dumping to disk
    # make sure iteration works (if there's only one arg)
    if isinstance(items, str): items = [items]
    if isinstance(systems, str): systems = [systems]

    items = tuple(auxdatatools.getitemid(item) if isinstance(item, str) else item for item in items)
    systems = tuple(auxdatatools.getsystemID(system) if isinstance(system, str) else system for system in systems)

    systems_regions = tuple(auxdatatools.getsystemregion(system) for system in systems)

    regionsToPull = set(systems_regions)

    # we assume that the DB is being populated in the same order it was previously - this should be true, as the order is determined by the order of
    # items in presets.auxdataDB and systems in presets.auxdataDB, which will remain constant unless the data is updated (and the new data is different). We could
    # actually check each entry, but this is slow
    if resume and os.path.isfile(presets.marketDB):
        if verbose: print('Attempting to resume from last complete item request...', end='')
        entry_items = sqlitetools.getallitemsfromdbcol(presets.marketDB, 'MarketItems', 'typeID')
        
        if len(entry_items) == 0:
            if verbose: print('\nCannot resume, re-initialising market DB')
            resume = False
            initmarketDB()
        else:
            item_was_inprogress = entry_items[-1] # the item that was in progress last time the DB was written
            items_done = set(entry_items)
            items_done.remove(item_was_inprogress) # these items were definitely done

            # delete all entries for the in progress item
            conn = sqlite3.connect(presets.marketDB)
            c = conn.cursor()
            c.execute('''DELETE FROM MarketItems WHERE ItemID=?''', (item_was_inprogress, ))
            conn.commit()
            conn.close()

            # remove completed items from list of requested items
            items = list(items)
            for item in items_done:
                if item in items: items.remove(item)
            items = tuple(items)

            if verbose: print('ready to go.')

    else:
        if verbose: print('(Re-) initialising market DB')
        initmarketDB() # otherwise (re) initialise the market DB

    counter, total_combos = 1, len(items) * len(systems)
    entries = []
    if verbose: print_str = ''
    for item in items:

        for region in regionsToPull:
            regionOrders = evemarket.getorders(item, region, order_type)
            avgRegionStats = evemarket.getavgregionstats(item, region, avg_period=7)

            for ii, system in enumerate(systems):
                if systems_regions[ii] == region:
                    counter += 1

                    if verbose:
                        if len(print_str) > 0: print('\r' + ' '*len(print_str), end='\r')
                        print_str = 'Pulling data for item/system pair %s of %s... (%s, %s)' % (counter, total_combos, auxdatatools.getitemName(item), auxdatatools.getsystemName(system))
                        print(print_str, end=('\n' if counter == total_combos else ''))
                        sys.stdout.flush()

                    entry = (item, system) + evemarket.getitemstats(item, system, order_type, orders=regionOrders, get_region_stats=False) + avgRegionStats
                    entries.append(entry)

                    # dump data to DB on disk every so often to prevent memory overflow
                    if len(entries) > cache_limit:
                        addtomarketDB(entries, 'MarketItems')
                        entries = []

    addtomarketDB(entries, 'MarketItems')

    print('done.')

def addtomarketDB(entries, table):
    if entries: # ignore empty entries
        conn = sqlite3.connect(presets.marketDB)
        c = conn.cursor()

        try:
            if table == 'MarketItems':
                c.executemany('''INSERT INTO MarketItems(ItemID, systemID, MeanPrice, MedianPrice, StdPrice, nOrders, MeanRegionalVolume, StdRegionalVolume)
                                    VALUES(?,?,?,?,?,?,?,?)''', entries)
            elif table == 'Trades':
                c.executemany('''INSERT INTO Trades(ItemID, BuysystemID, BuyMedianPrice, BuyMeanRegionalVolume, SellsystemID, SellMedianPrice, SellMeanRegionalVolume, nSellOrders)
                                    VALUES(?,?,?,?,?,?,?,?)''', entries)
            else:
                raise Exception()

        finally:
            conn.commit()
            conn.close()

def iswhregion(region):
    if isinstance(region, int): region = auxdatatools.getregionName(region)

    first3, last5 = region[0:3], region[3:]

    # check if region name is of the form X-XYYYYY, where X are string characters and Y are digits
    if isinstance(region[0:3], str) and region[1] == '-' and region[3:].isdigit():
        return True
    else:
        return False

def initWHregions():
    global wh_regions
    
    all_regions = sqlitetools.getallitemsfromdbcol(presets.auxdataDB, 'Regions', 'regionName')
    
    wh_regions = tuple(region for region in all_regions if iswhregion(region))

def initempireregions():
    global empire_regions
    if 'wh_regions' not in globals(): initWHregions()

    non_empire_regions = presets.null_regions + wh_regions + presets.jove_regions

    conn = sqlite3.connect(presets.auxdataDB)
    c = conn.cursor()

    sql_cmd = '''SELECT regionName FROM Regions WHERE regionName not in %s''' % sqlitetools.sql_placeholder_of_length(len(non_empire_regions))

    empire_regions = tuple(ii[0] for ii in c.execute(sql_cmd, non_empire_regions).fetchall())

    conn.close()

def getallHSsystems():
    if 'empire_regions' not in globals(): initempireregions()

    conn = sqlite3.connect(presets.auxdataDB)
    c = conn.cursor()

    sql_cmd = '''SELECT systemID FROM Systems NATURAL JOIN Regions
                    WHERE regionName in %s
                    AND Security >= 0.5''' % sqlitetools.sql_placeholder_of_length(len(empire_regions))

    hs_systems = tuple(ii[0] for ii in c.execute(sql_cmd, empire_regions).fetchall())

    conn.close()

    return hs_systems

def findtrades(itemIDs, margin_threshold_pct, margin_threshold_abs, min_volume_abs, max_competition, cache_limit=200):
    inittradetable()

    if isinstance(itemIDs, int): itemIDs = [itemIDs]
    margin_threshold = margin_threshold_pct / 100 # convert pct to decimal

    for item in itemIDs:
        entries = sqlitetools.getxbyyfromdb(presets.marketDB, 'MarketItems', ('solarSystemID', 'MedianPrice', 'MeanRegionalVolume', 'nOrders'), 'typeID', item)
        entries = [entries[ii] for ii, entry in enumerate(entries) if entry[1] != None] # remove data where price is None
        entries = [entries[ii] for ii, entry in enumerate(entries) if entry[2] != None] # remove data where voluem data was insufficient

        if not entries: continue # skip where we have no entries
        
        try:
            max_entry = max(entries, key = itemgetter(1))
        except:
            print(entries)
            raise

        if max_entry[2] < min_volume_abs: continue # absolute sell volume threshold
        if max_entry[3] > max_competition: continue # sell competition threshold
        
        minprice_for_margin = max_entry[1] / (margin_threshold + 1)

        trades = []
        for entry in entries:
            if entry[1] <= minprice_for_margin:
                this_margin = (max_entry[1] - entry[1]) / entry[1]
                this_margin_abs = this_margin * entry[1]

                if this_margin_abs >= margin_threshold_abs:
                    trades.append( (item, entry[0], entry[1], entry[2], max_entry[0], max_entry[1], max_entry[2], max_entry[3]) )
                    try:
                        if verbose: print('Profitable trade found: %s, %s -> %s. Margin: %s%%' % ( auxdatatools.getitemName(item), auxdatatools.getsystemName(entry[0]), auxdatatools.getsystemName(max_entry[0]), round(this_margin * 100, 1) ) )
                    except NoMatchError:
                        print('Warning: Item ID %s in Market DB but not main Item DB. Maybe Item DB has been updated recently?' % item)

            if len(trades) > cache_limit: addtomarketDB(trades, 'Trades')

        addtomarketDB(trades, 'Trades')

    if verbose: print('Total possible trades found: %s' % sqlitetools.gettablelen(presets.marketDB, 'Trades'))
