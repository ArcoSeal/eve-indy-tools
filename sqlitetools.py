## Functions for doing general operations on sqlite dbs

import sqlite3

def addcolumntodbtable(db, table, colname, coltype, options=None):
    conn = sqlite3.connect(db)
    c = conn.cursor()

    c.execute('''ALTER TABLE {} ADD COLUMN {} {} {}'''.format(table, colname, coltype, options)) # !TODO: This is insecure!

    conn.commit()
    conn.close()

def sql_placeholder_of_length(length):
    return '(' + ', '.join('?'*length) + ')'

def checkifitemindb(db, table, column, item):
    # returns True if item exists in column of table in DB
    conn = sqlite3.connect(db)
    c = conn.cursor()

    sql_cmd = '''SELECT COUNT(%s) FROM %s WHERE %s=?''' % (column, table, column)

    result = bool(c.execute(sql_cmd, (item,)).fetchone()[0])

    conn.close()

    return result

def tablesindb(db):
    conn = sqlite3.connect(db)
    c = conn.cursor()

    c.execute('''SELECT name FROM sqlite_master WHERE type='table';''')

    result = tuple(ii[0] for ii in c.fetchall())

    conn.close()

    return result

def columnsindbtable(db, table):
    conn = sqlite3.connect(db)
    c = conn.cursor()

    c.execute('''SELECT * FROM %s LIMIT 1''' % table)

    colnames = (ii[0] for ii in c.description)

    conn.close()

    return colnames

def gettablelen(db, table):
    # gets number of rows in table
    conn = sqlite3.connect(db)
    c = conn.cursor()

    sql_cmd = '''SELECT COUNT(*) FROM %s''' % table

    result = c.execute(sql_cmd).fetchone()[0]

    conn.close()

    return result

def getxbyyfromdb(db, table, x, y, y_val, flatten_on_single_match=True):
    # finds entries in DB table where columns match criteria and returns requested columns
    # x: columns to return, either single string or list/tuple of strings for multiple columns e.g. ['Column1', 'Column2']
    # y: columns to match (str or list/tuple of str)
    # y_val: values to match, either single value (for 1 column) or list/tuple of values for multiple columns
    #
    # if matching only one column (x), the return list will be flattened slightly e.g. [(x1,), (x2,)] -> [x1, x2]
    # if there is only once match in these conditions, the results may be flattend further if specified e.g. [x1] -> x1

    if (isinstance(x, list) or isinstance(x, tuple)) and all(isinstance(ii, str) for ii in x): # if x is a list/tuple of strings i.e. we have multiple cols to return
        multiselect = True
        x = ','.join(x) # e.g. if Col1 & Col2 are to be returned we have "Col1,Col2"
    else:
        multiselect = False

    if y == 'ALL' and y_val == 'ALL':
        sql_cmd = ('''SELECT %s FROM %s''') % tuple([x, table])

    else:
        if not (isinstance(y, list) or isinstance(y, tuple)): y, y_val = (y,), (y_val,) # if single column, put into tuple to make iteration work
        
        if len(y) != len(y_val): raise Exception()

        params = ' AND '.join(['%s=?'] * len(y)) # set up critera for SQL query e.g. "Column1=? AND Column2=?"

        sql_cmd = ('''SELECT %s FROM %s WHERE ''' + params) % tuple([x, table] + list(y)) # create SQL query with placeholders e.g. "SELECT Col1,Col2 FROM Table WHERE Col3=? AND Col4=?"

    conn = sqlite3.connect(db)
    c = conn.cursor()

    try:
        if y == 'ALL' and y_val == 'ALL':
            found = c.execute(sql_cmd).fetchall()
        else:
            found = c.execute(sql_cmd, y_val).fetchall()
    except:
        print(sql_cmd)
        raise
    finally:
        conn.close()

    if not found:
        return None
   
    else:
        if not multiselect:
            x_val = tuple( ii[0] for ii in found ) # [(x_val1,), (x_val2,)] -> [x_val1, xval2]
            
            if len(x_val) == 1 and flatten_on_single_match: x_val = x_val[0] # single match for single column, if specified e.g. [x_val] -> x_val
        
        else:
            x_val = found

    return x_val

def getallitemsfromdbcol(db, table, columns, unique=False):
    #!TODO replace this with getXbyY for wildcard
    if isinstance(columns, list) or isinstance(columns, tuple): columns = ', '.join(columns)

    conn = sqlite3.connect(db)
    c = conn.cursor()

    if unique:
        sql_cmd = '''SELECT DISTINCT %s FROM %s''' % (columns, table)
    else:
        sql_cmd = '''SELECT %s FROM %s''' % (columns, table)

    items = tuple( (ii[0] if isinstance(columns, str) else ii) for ii in c.execute(sql_cmd).fetchall()) # if we only want one column's data, we can flatten the output

    conn.close()

    return items

def createtable(db, table, columns=None):
    # !TODO: This is insecure!
    conn = sqlite3.connect(db)
    c = conn.cursor()

    c.execute('''DROP TABLE IF EXISTS {}'''.format(table))
    
    colparams = '(%s)' % ', '.join(columns)

    c.execute('''CREATE TABLE {} {}'''.format(table, colparams))

    conn.commit()
    conn.close()

def insertmany(db, table, entries):
    conn = sqlite3.connect(db)
    c = conn.cursor()

    c.executemany('''INSERT INTO {} VALUES {}'''.format(table, sql_placeholder_of_length(len(entries[0]))), entries) # !TODO: This is insecure!

    if verbose: print('Added %s entries' % conn.total_changes)

    conn.commit()
    conn.close()

def copycolstonewDB(db_src, table_src, db_dest, table_dest, cols_to_copy):
    # copy columns from one DB to another
    # cols_to_copy: names of columns to copy, must be iterable of strings
    # cols_new_names: names of columns in new DB (default: original names), must be iterable of strings

    conn = sqlite3.connect(db_dest)
    c = conn.cursor()

    c.execute('''DROP TABLE IF EXISTS %s''' % table_dest)
    c.execute('''ATTACH DATABASE "%s" AS dbsrc''' % db_src)
    c.execute('''CREATE TABLE %s AS SELECT %s FROM dbsrc.%s''' % (table_dest, ','.join(cols_to_copy), table_src))

    conn.commit()
    conn.close()


    


