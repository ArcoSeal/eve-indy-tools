## Tools for talking to CREST

import requests
import json
from math import floor
from urllib.parse import urljoin
import time

CREST_public_baseURL = 'https://public-crest.eveonline.com/'
CREST_public_rateLimits = {'rate' : 100, 'burst' : 100, 'safety_margin' : 0.8} # safety margin reduces rate limits e.g. 0.8 will use 80% of the official rate limit

class TokensOverCapacity(Exception):
    pass

class NotEnoughTokens(Exception):
    pass

class TokenRefillTimeout(Exception):
    pass

def urljoin_long(*args):
    # join a url using unlimited sections (like with os.path.join)
    return urljoin(args[0], '/'.join(args[1:]))

def getcresturl(reqtype, **kwargs):
    def check_kwargs(args_to_check_for, args_to_check=kwargs.keys()):
        if not set(args_to_check_for).issubset(kwargs): raise Exception('Missing required input argument(s), expected %s got %s' % (args_to_check_for, args_to_check))

    reqtype = reqtype.lower()

    if reqtype == 'dailystats':
        check_kwargs(('regionID', 'typeID'))

        CRESTUrl = urljoin_long(CREST_public_baseURL, 'market', str(kwargs['regionID']), 'types', str(kwargs['typeID']), 'history')

    elif reqtype in ('buyorders', 'sellorders'):
        check_kwargs(('regionID', 'typeID'))

        CRESTUrl = urljoin_long(CREST_public_baseURL, 'market', str(kwargs['regionID']), 'orders', ('buy' if reqtype == 'buyorders' else 'sell'))
        CRESTParams = {'type' : urljoin_long(CREST_public_baseURL, 'types', str(kwargs['typeID']))}

    elif reqtype == 'adjprices':
        CRESTUrl = urljoin_long(CREST_public_baseURL, 'market', 'prices')

    else:
        raise Exception()

    if CRESTUrl[-1] != '/': CRESTUrl += '/' # CREST urls require a trailing slash
    if 'CRESTParams' in locals():
        for param in CRESTParams:
            if CRESTParams[param].startswith('http://') or CRESTParams[param].startswith('https://') and CRESTParams[param][-1] != '/': CRESTParams[param] += '/' # so parameters, if they're URLs

    if 'CRESTParams' in locals():
        return (CRESTUrl, CRESTParams)
    else:
        return CRESTUrl

def inittokenbucket():
    global TokenBucket, TokenBucket_rate, TokenBucket_capacity, TokenBucket_last_update

    TokenBucket_rate = 1 / (CREST_public_rateLimits['rate'] * CREST_public_rateLimits['safety_margin'])
    TokenBucket_capacity = int(CREST_public_rateLimits['burst'] * CREST_public_rateLimits['safety_margin'])

    TokenBucket = TokenBucket_capacity

    TokenBucket_last_update = time.time()

def refilltokenbucket():
    global TokenBucket, TokenBucket_last_update

    update_time = time.time()
    delta_time = floor(update_time - TokenBucket_last_update)

    if delta_time >= 2 * TokenBucket_rate: # if the time since the last update is minimal, don't bother 

        new_tokens = floor(delta_time / TokenBucket_rate)

        if TokenBucket + new_tokens > TokenBucket_capacity:
            TokenBucket = TokenBucket_capacity
        else:
            TokenBucket += new_tokens

        TokenBucket_last_update = update_time

def overridetokenbucket(tokens):
    global TokenBucket

    TokenBucket = tokens

def consumetokens(tokens_consumed):
    global TokenBucket

    refilltokenbucket()

    if tokens_consumed > TokenBucket_capacity:
        raise TokensOverCapacity('Token Bucket capacity: ', TokenBucket_capacity, ', Tokens requested: ', tokens_consumed)
    elif tokens_consumed > TokenBucket:
        raise NotEnoughTokens('Token Bucket contents: ', TokenBucket, ', Tokens requested: ', tokens_consumed)
    else:
        TokenBucket -= tokens_consumed

def getcrestdata(url, params=None):
    if 'TokenBucket' not in globals(): inittokenbucket()

    token_timeout = 20 # retry period in seconds
    start_time, time_trying = time.time(), 0
    already_slept = False
    while time_trying < token_timeout:
        try:
            consumetokens(1)
        except NotEnoughTokens:
            time.sleep(TokenBucket_rate * 2)
            time_trying = time.time() - start_time
            if verbose and not already_slept:
                print('')
                print_str = ''
            if verbose:
                if len(print_str) > 0: print('\r' + ' '*len(print_str), end='\r')
                print_str = 'Rate limit reached, sleeping (%ss)' % round(time_trying,2)
                print(print_str, end='')
                sys.stdout.flush()
            already_slept = True

        else:
            break
    
    if verbose and already_slept: print('')
    if time_trying >= token_timeout: raise TokenRefillTimeout('Tokens did not refill in timeout period!')

    conn_timeout = 15
    tries, max_tries, retry_wait = 0, 10, 2
    while tries <= max_tries:
        tries += 1
        if tries > 1: print('retrying %s/%s' % (tries, max_tries))
        try:
            resp = requests.get(url, params, timeout=conn_timeout)
        except requests.exceptions.ReadTimeout as e:
            if tries < max_tries:
                if verbose:
                    if tries == 1: print('')
                    print('Timeout reached (%ss), waiting %s seconds before retry...' % (conn_timeout, retry_wait), end='')
                time.sleep(retry_wait)
            else:
                print('Retry limit reached, bailing...')
                raise

        except requests.exceptions.ConnectionError as e:
            if 'BadStatusLine' in str(e):
                if tries < max_tries:
                    if verbose:
                        if tries == 1: print('')
                        print('Bad HTTP response, possibly connection being shit. Waiting %s seconds before retry...' % retry_wait, end='')
                    time.sleep(retry_wait)
                else:
                    print('Retry limit reached, bailing...')
                    raise

            else:
                raise

        else:
            break

    try:
        resp.raise_for_status() # raise an error if we get an error response e.g. 404
    except requests.exceptions.HTTPError:
        print(resp.url)
        print(str(resp.status_code) + ': ' + json.loads(resp.text)['message'] + '\n')
        raise
    
    data = json.loads(resp.text)

    return data
