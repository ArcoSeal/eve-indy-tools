from math import ceil, floor

import krabtools
import sqlitetools
import auxdatatools
import evemarket
import presets

def getmatsforitem(item, n_produced=1, ME=0, production_efficiences=None, bpMaxRuns=float('inf')):
    # get the materials required to produce an item
    # n_produced is the number of items desired
    # ME is the Material Efficency level of the item's BP
    # production efficiences is a list/tuple of other material efficiency savings e.g. skills, POS mods etc.

    runs = getrunsfornproducts(item, n_produced) # calc how many runs of BP we need to get desired number of items produced (e.g. 1 run produces 10 and we need 20 -> 2 runs)

    if runs > bpMaxRuns: # if we need more than one BP to do all our runs
        runs_ratio = runs/bpMaxRuns
        runs_fullbp = floor(runs_ratio) # full uses of BP (e.g. if we need 15 runs and the BP max is 6, this will be 2)
        runs_rem = int(round((runs_ratio - floor(runs_ratio)) * bpMaxRuns)) # remaining runs required (e.g. 3 for above example)

        mats_fullbp = scalematslistbyint(getmatsforitem(item, n_produced=bpMaxRuns, ME=ME, production_efficiences=production_efficiences), runs_fullbp) # mats for "full uses" of BP (mats for max run * no of max runs)
        if runs_rem > 0:
            mats_rem = getmatsforitem(item, n_produced=runs_rem, ME=ME, production_efficiences=production_efficiences)
        else:
            mats_rem = {}

        matslist = combinematslists(mats_fullbp, mats_rem)

    else:
        matslist = auxdatatools.getmatsforbp(auxdatatools.getbpIDforitem(item)) # get mats for 1 run w/o ME modifiers

        if runs > 1: matslist = scalematslistbyint(matslist, runs) # scale up to # of runs (this happens *before* ME calculations)

        if ME > 0 or production_efficiences: matslist = scalematslistbyefficiency(matslist, runs, ME, production_efficiences) # calculate ME effects if necessary
    
    return matslist

def getbasematsforitem(item, n_produced=1, ME=0, production_efficiences=None, ME_components={}, production_efficiences_components={}, bpMaxRuns=float('inf'), bpMaxRuns_components={}):
    if not isinstance(ME_components, dict): raise Exception('Invalid MEs for components: %s, component MEs must be given as dict of {typeID : ME}' % ME_components)
    if not isinstance(production_efficiences_components, dict): raise Exception('Invalid production efficiency savings for components: %s, must be given as dict of {typeID : [eff1, eff2,...]}' % production_efficiences_components)

    top_mats = getmatsforitem(item, n_produced, ME, production_efficiences, bpMaxRuns) # get "top tier" materials/components - the stuff actually on the BP

    # we can set one ME for all components with the keyword "ALL"
    if len(ME_components) == 1 and list(ME_components.keys())[0] == 'ALL':
        for mat in top_mats: ME_components[mat] = ME_components['ALL']
        del ME_components['ALL']


    # as above for ME savings from POSes etc.
    if len(production_efficiences_components) == 1 and list(production_efficiences_components.keys())[0] == 'ALL':
        for mat in top_mats: production_efficiences_components[mat] = production_efficiences_components['ALL']
        del production_efficiences_components['ALL']

    base_mats = top_mats

    while any([auxdatatools.hasbp(ii) for ii in base_mats]): # while we have anything that can be manufactured

        temp_mats = {} # use temp dict to avoid confusing when add/removing entries

        for matID, matqty in base_mats.items():       
            
            if not auxdatatools.hasbp(matID): # if this component has no BP i.e. cannot be manufactured, it is already a base material
                temp_mats[matID] = matqty
            
            else: # else get the materials needed from its BP
                ME_thismat = ME_components[matID] if (matID in ME_components) else 0
                production_efficiences_thismat = production_efficiences_components[matID] if (matID in production_efficiences_components) else None
                bpMaxRuns_thismat = bpMaxRuns_components[matID] if (matID in bpMaxRuns_components) else float('inf')
                
                component_mats = getmatsforitem(matID, n_produced=matqty, ME=ME_thismat, production_efficiences=production_efficiences_thismat, bpMaxRuns=bpMaxRuns_thismat)

                temp_mats = combinematslists(temp_mats, component_mats)

        base_mats = temp_mats

    return base_mats

def combinematslists(*args):
    masterlist = args[0]
    
    if len(args) > 2:
        for arg in args[1:]:
            masterlist = combinematslists(masterlist, arg)
    
    elif len(args) == 2:
        for matID, matqty in args[1].items():
            if matID in masterlist:
                masterlist[matID] += matqty
            else:
                masterlist[matID] = matqty

        return masterlist

    else:
        raise Exception('Need at least 2 arguments') 

def scalematslistbyint(matslist, scale_factor):
    if not isinstance(scale_factor, int): raise Exception()
    
    matslist_scaled = {}
    for matID, matqty in matslist.items(): matslist_scaled[matID] = matqty * scale_factor

    return matslist_scaled

def scalematslistbyefficiency(matslist, runs, ME, production_efficiences=None):
    # scales materials in materials list for ME level, and optionally additional material efficiency factors (e.g. skills, POS effects etc.)
    if not isinstance(ME, int) and not (ME >= 0 and ME <= 10): raise Exception('Invalid ME: %s, must be int between 0 & 10' % ME)
    
    if production_efficiences:
        additional_scale_factors = []

        if not isinstance(production_efficiences, list) and not isinstance(production_efficiences, tuple):
            if isinstance(production_efficiences, float):
                production_efficiences = [production_efficiences] # if only one additional efficiency factor, cast as list to make iteration work
            else:
                raise Exception('Invalid efficiency factors: %s, must be list or tuple of floats' % production_efficiences)

        for arg in production_efficiences:
            if not isinstance(arg, float) or not (arg >= 0 and arg < 1): raise Exception('Invalid efficiency factor: %s, must be fraction of 1' % arg)

            additional_scale_factors.append(1 - arg) # convert fractions to scale factor e.g. 25% efficiency saving == 0.25 -> 0.75 scale factor

    ME_scale_factor = 1 - (ME * 0.01) # convert ME level to scale factor e.g. 9 ME == 9% saving -> 0.91 scale factor

    matslist_scaled = {}
    for matID, matqty in matslist.items():      
        matqty *= ME_scale_factor
    
        if production_efficiences:
            for scale_factor in additional_scale_factors: matqty *= scale_factor

        if matqty/runs < 1: # can't have less than 1 matID per run
            matqty = runs
        else:
            matqty = ceil(matqty)

        matslist_scaled[matID] = matqty

    return matslist_scaled

def getrunsfornproducts(product, n_produced):
    # calc number of runs of a BP needed to make desired n of a given product (e.g. if BP produces 100 of product per run and we need 250, we must run BP 3 times)
    product = auxdatatools.getitemid(product)
    bp_output_quantity = sqlitetools.getxbyyfromdb(presets.auxdataDB, 'bpProducts', 'quantity', 'productTypeID', product)

    return(ceil(n_produced / bp_output_quantity))

def convmatslisttonames(matslist):
    out = {}
    for matID, matqty in matslist.items(): out[auxdatatools.getitemName(matID)] = matqty

    return out

def calcinventstats(invent_from, skill_encryption, skill_physics_1, skill_physics_2, decryptortype='NONE'):
    # invent_from: must be T1 BP or Hull Section
    krabtools.checkvalidskilllevel([skill_encryption, skill_physics_1, skill_physics_2])

    if not auxdatatools.ishullsection(invent_from):
        if not auxdatatools.isbp(invent_from): raise Exception('Not a BP or hull section! %s' % invent_from)
        invent_from = auxdatatools.getBPproductgroup(invent_from) # e.g. frigates, cruisers, etc.
   
    if not decryptortype: decryptortype = 'NONE'
    inventChance = presets.invent_types[invent_from]['inventChance'] \
                    * (1 + ( (skill_encryption / 40) + ( (skill_physics_1 + skill_physics_2) / 30) )) \
                    * presets.decryptors[decryptortype]['inventChanceMod']
    inventChance = round(inventChance,3)
   
    runs = presets.invent_types[invent_from]['runs'] + presets.decryptors[decryptortype]['runsMod']
    ME = 2 + presets.decryptors[decryptortype]['MEMod']
    TE = 0 + presets.decryptors[decryptortype]['TEMod']

    return (inventChance, runs, ME, TE)

def getinventmats(invent_type, decryptortype='NONE'):
    # get list materials need for invention - datacores, decryptor (if specified), and hull section (if applicable) (T1 BPCs are not counted)
    # invent_type: either the T2/T3 item desired (or its BP), or the T1 item invented from (or its BP)

    if auxdatatools.isT2(invent_type): # if we've been given a T2/T3 item, we must find out what it's invented from
        invent_type = auxdatatools.getinventbase(invent_type)
        if isinstance(invent_type, list) or isinstance(invent_type,tuple): raise Exception('Multiple invention bases found: %s' % invent_type) # this will fail if given a T3 hull/component, as there are multiple things it could be invented from
    elif auxdatatools.ishullsection(invent_type):
        invent_type = auxdatatools.getitemid(invent_type) # hull sections appear as items, but are actually BPs - so we just need to get the ID and we're good to go
    elif auxdatatools.isitem(invent_type): # we've been given something T1...
        if auxdatatools.isbp(invent_type): # T1 BP
            invent_type = auxdatatools.getitemid(invent_type)
        else: # T1 item
            invent_type = auxdatatools.getbpIDforitem(invent_type)

    invent_mats = auxdatatools.getmatsforbp(invent_type, activity='Invention') # datacores
    if decryptortype != 'NONE': invent_mats = combinematslists(invent_mats, {decryptortype+' Decryptor': 1}) # decryptor (if applicable)
    if auxdatatools.ishullsection(invent_type): combinematslists(invent_mats, {invent_type: 1})

    return invent_mats

def get_matslist_cost_from_pricelist(matslist, pricelist, order_type, return_type):
    totalcost = 0
    matscostslist = {}
    for mat in matslist:
        matID, quantity = auxdatatools.getitemid(mat), matslist[mat]
        matcost = pricelist[matID][order_type] * quantity
        if return_type == 'total': totalcost += matcost
        if return_type == 'list': matscostslist[matID] = matcost

    if return_type == 'total':
        return totalcost
    elif return_type == 'list':
        return matscostslist

def calcjobfee(item, runs, systemModifier, buildLocation='POS'):
    if systemModifier < 0 or systemModifier > 1: raise Exception()

    if isinstance(item, list) or isinstance(item, tuple):
        if isinstance(runs, list) or isinstance(runs, tuple):
            if len(runs) != len(item): raise Exception('List of runs does not match list of items. Got %s items but %s runs' % (len(item), len(runs)))
        else:
            runs = [runs]

        jobFeeList = []
        for ii, itm in enumerate(item): jobFeeList.append(calcjobfee(itm, runs[ii], systemModifier, buildLocation))
        return(jobFeeList)

    jobFee = krabtools.getbasecostforitem(item) * runs * systemModifier

    if buildLocation.lower() == 'station': jobFee += (jobFee * 0.1) # station tax is 10%

    jobFee = round(jobFee, 2)

    return jobFee

def calcbuildcosts(product, productRuns, **kwargs):
    if 'bpMaxRuns' not in kwargs or not kwargs['bpMaxRuns']:
        bpMaxRuns = 99999
    else:
        bpMaxRuns = kwargs['bpMaxRuns']
    
    if 'baseMatsList' not in kwargs or not kwargs['baseMatsList']:
        passargdict = {'item' : product, 'n_produced' : productRuns}
        for arg in ('ME','production_efficiences','ME_components','production_efficiences_components','bpMaxRuns','bpMaxRuns_components'):
            if arg in kwargs: passargdict[arg] = kwargs[arg]

        baseMatsList = getbasematsforitem(**passargdict)

    else:
        baseMatsList = kwargs['baseMatsList']

    basematids = [ii for ii in baseMatsList]

    if 'componentsList' not in kwargs or not kwargs['componentsList']:
        passargdict = {'item' : product, 'n_produced' : productRuns}
        for arg in ('ME','production_efficiences','bpMaxRuns'):
            if arg in kwargs: passargdict[arg] = kwargs[arg]

        componentsList = getmatsforitem(**passargdict)

    else:
        componentsList = kwargs['componentsList']

    if 'buySystem' not in kwargs or not kwargs['buySystem']:
        buySystem = 'Jita'
    else:
        buySystem = kwargs['buySystem']

    if 'buildLocation' not in kwargs or not kwargs['buildLocation']:
        buildLocation = 'POS'
    else:
        buildLocation = kwargs['buildLocation']

    if 'systemModifier' not in kwargs or not kwargs['systemModifier']:
        systemModifier = 0.025
    else:
        systemModifier = kwargs['systemModifier']

    if 'baseMatsPriceList' in kwargs and kwargs['baseMatsPriceList']:
        baseMatsPriceList = kwargs['baseMatsPriceList']
    else:
        if verbose: print('Pulling prices...')
        baseMatsPriceList = evemarket.getpricelist(basematids, 'buy', buySystem)
    
    baseMatsCosts = get_matslist_cost_from_pricelist(baseMatsList, baseMatsPriceList, order_type='buy', return_type='list')

    baseMatsBuyFees = {}
    for basematID, basematcost in baseMatsCosts.items(): baseMatsBuyFees[basematID] = evemarket.calcbuyfee(basematcost, 'buy', skillBrokerRelations=1)

    componentsBuildFees = {}
    for compID, comp_qty in componentsList.items():
        if compID in basematids:
            componentsBuildFees[compID] = 0 # for components which are not manufactured
        else:
            componentsBuildFees[compID] = calcjobfee(compID, comp_qty, systemModifier, buildLocation)

    if isinstance(product, str): product = auxdatatools.getitemid(product)

    if productRuns > bpMaxRuns:
        maxruns = floor(productRuns/bpMaxRuns)
        remruns = productRuns - maxruns*bpMaxRuns
        productBuildFee = calcjobfee(product, bpMaxRuns, systemModifier) * maxruns + calcjobfee(product, remruns, systemModifier)
    else:
        productBuildFee = calcjobfee(product, productRuns, systemModifier)
   
    totalCost = sum(baseMatsCosts.values()) + sum(baseMatsBuyFees.values()) + sum(componentsBuildFees.values()) + productBuildFee

    return {
            'baseMatsPriceList' : baseMatsPriceList,
            'baseMatsCosts' : baseMatsCosts,
            'baseMatsBuyFees' : baseMatsBuyFees,
            'componentsBuildFees' : componentsBuildFees,
            'productBuildFee' : productBuildFee,
            'totalCost' : totalCost,
            }

def calcjobtime(product, activity, runs, TE=0, production_time_efficiencies=[]):
    if auxdatatools.isitem(product): product = auxdatatools.getbpIDforitem(product)

    te_scale_factor = 1 - (TE * 2 * 0.01)

    time = auxdatatools.getBPtime(product, activity) * runs * te_scale_factor

    for pcteff in production_time_efficiencies: time *= (1 - pcteff)

    time = round(time)

    return time

