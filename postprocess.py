# python code that takes a list of the metadata tags, after they have
# been processed using the regex definitions,
# and processes them accordingly. It is currently required that this will return
# a list of items (strings).
#
# The output will be unconditionally cleaned of empties and uniquified unless you return a list of just one item
# (see the example at the end)
#
# this holds the item positions we want to drop
# dropping cannot be done ad hoc because it would shift the positions
delx = []

def pp_s_korea(items, it, ix):
    # look for the item before the country ('Südkorea'), it's ProvinceState
    # the structure is then Info, Quarter, District_or_City, ProvinceState, Südkorea, Date, Creator
    # the offsets:                ^^^-3    ^^^-2             ^^^-1     ^^^we start here
    # the following assumes that the province suffix '-do' has already been regexed away
    #
    # except in the case of Jeju, do this:
    if items[ix - 1] != "Jeju":
        # ...in the big cities, the name of the province is the well-known city name, so keep it
        if items[ix - 1] in ["Seoul"]:
            # ...but drop the city district
            delx.append(ix - 2)
        else:
            if items[ix-1] not in ['Busan']:
                # ...otherwise drop the province
                delx.append(ix - 1)
    # always drop the district quarter
    if items[ix-3] == 'Pungcheon-myeon':
        items[ix-4] = 'Hahoe'
    if items[ix-3] == 'Sanga-dong':
        items[ix-4] = 'Woryeonggyo-Brücke'
    if items[ix-3] == 'Jinhyeon-dong':
       items[ix-4] = 'Bulguksa'
    if items[ix-3] == 'Cheongnyong-dong':
        items[ix-4] = 'Beomeosa'

    delx.append(ix - 3)
    return items


def pp_morocco(items, it, ix):
    # drop the province, except when it's Marrake([s|c]h)
    if not 'Marrakesch' in items[ix - 1]:
        delx.append(ix - 1)
    if items[ix-2] == "M'Semrir":
       items[ix-4] = 'Gorges du Dades'

    return items


# cantons and abbreviations for them, to be extended
cantons = {'Zürich': 'ZH', 'Basel-Stadt': 'BS'}


def pp_ch_cantons(items, ix):
    ct = ''
    for canton in cantons.keys():
        # input fields
        input_canton = items[ix - 1]
        city = items[ix - 2]
        # if the dict term is in the input input_canton
        if canton in input_canton:
            # and if the city name is not port of the dict canton
            if city not in canton:
                # append the canton's abbreviation
                ct = ' ' + cantons.get(canton)
            # mark city field for deletion
            delx.append(ix - 2)
            # update input_canton field with city + abbreviation (or '')
            items[ix - 1] = city + ct


def pp_ch(items, it, ix):
    # Someplace, Kanton Zürich, => Someplace ZH, unless Someplace in 'Kanton Zürich'
    pp_ch_cantons(items, ix)
    return items


def pp_mark(items, it, ix):
    # Someplace, Mark, => Someplace (Mark),
    # get location
    loc = items[ix - 1]
    # drop it
    delx.append(ix - 1)
    if loc == 'Fürstenberg':
        if items[ix -2] == 'Himmelpfort':
            loc = 'Himmelpfort'
            delx.append(ix - 2)
    # assign new content to province item
    items[ix] = loc + ' ' + ''.join(['(', it, ')'])
    return items


# This defines timespans per country (province/state,(city, (...)).
# We use only the key values, the value for the last key has to be None.
# { 'Start date': {'End date': {'Country': None}}, ... }
# This matches the metatags that are defined in the config file, but the order is reversed here.
# This example assumes that the config file metatags amount to
# Name, Sublocation, Location, ProvinceState, Country, Date, Creator
# We match between and including start and end dates and proceed left from there: Country, ProvinceState, etc.
# Date format here is YYYYMMDD (unlike in the display and config file).
# This way, un-geotagged images will be associated with the country or places you visited
# To skip items (leave them untouched), insert an empty string.
# Existing entries will not be overwritten.
# The start date has to be unique. Do not overlap end dates, when they do, the entry starting first wins.
timespans = {
    '20140925': {'20140928': {'USA': {'NY': {'New York': None}}}},
    '20140929': {'20140930': {'USA': {'MA': {'': {'In den Berkshires': None}}}}},
    '20140930': {'20140930': {'USA': {'NY': {'': {'Fahrt in die Adirondacks': None}}}}},
    '20141001': {'20141003': {'USA': {'NY': {'': {'In den Adirondacks': None}}}}},
    '20141004': {'20141004': {'USA': {'NY': {'': {'Adirondacks -> Catskills': None}}}}},
    '20141005': {'20141005': {'USA': {'NY': {'': {'In den Catskills': None}}}}},
    '20141006': {'20141006': {'USA': {'NY': {'': {'Catskills -> Poughkeepsie -> NYC': None}}}}},
    '20141007': {'20141007': {'USA': {'NY': {'New York': None}}}},
    '20141008': {'20141008': {'USA': {'PA': {'Philadelphia': {'30th Street Station': None}}}}},
    '20141009': {'20141010': {'USA': {'PA': {'Pittsburgh': None}}}},
    '20141012': {'20141014': {'USA': {'IL': {'Chicago': None}}}},
    '20141015': {'20141016': {'USA': {'': {'Chicago -> Zug 5 -> Reno': None}}}},
    '20141017': {'20141017': {'USA': {'NV': None}}},
    '20141018': {'20141018': {'USA': {'NV': {'Pyramid Lake': None}}}},
    '20141019': {'20141019': {'USA': {'': {'Lake Tahoe': None}}}},
    '20141020': {'20141120': {'USA': None}},
    '20170210': {'20170222': {'Portugal': None}},
    '20190201': {'20190217': {'Portugal': None}},
    '20190501': {'20190527': {'Südkorea': None}},
    '20201016': {'20201016': {'': {'': {'': {'':{ 'vom Dia': None}}}}}},
    '20201028': {'20201028': {'': {'': {'': {'':{ 'vom Dia': None}}}}}},
    '20201101': {'20210301': {'': {'': {'Himmelpfort (Mark)': None}}}},

}


# consume the rest of the timespan after country
def pp_consume_timespan(key_list, items, pos):
    # build the timespans dict access for the current key from the key list
    # if there are more items in the timespan than items configured, we stop, but that's ok as it is an error.
    # TODO there might be a better way than using eval...
    # this gives timespans[key][key][...]...
    eval_base = "timespans['" + "']['".join(key_list) + "']"
    # now look for the key
    for next_key in eval(eval_base + ".keys()"):
        # move our pointer
        pos = pos + 1
        # we're going backward
        i_pos = len(items) - pos
        # unfortunately, lists wrap, we have to take care of that, otherwise we might overwrite values
        # when we find too many items in a timespan entry, we stop and throw an alert
        if i_pos < 0:
            raise ValueError('Too many items in timespan: ' + str(key_list) + ' >>> ' + next_key)
        else:
            # item not set?
            if not items[i_pos]:
                # let's set it.
                items[i_pos] = next_key
            # is there another key in the queue? Otherwise, we're done.
            if eval(eval_base + ".get('" + next_key + "')") is not None:
                # if there is, do it again for the next key
                key_list.append(next_key)
                items = pp_consume_timespan(key_list, items, pos)
    return items


# add information to image if the image data is inside a timespan
def pp_metadata_from_timespan(items):
    # we assume that 'date' is the item before the last (hence the pos[ition] is set to 2 below,
    # lenght(items)-pos pointing to that place) and that it's formatted d.m.yyyy
    # and that 'country' is the item before date
    # this has to be configured that way in the configuration file
    # no real error checking is being done here, but
    # the conditionals should catch crashes from missing indices
    pos = 2
    # we need at least country|date|something, so more than two items
    if len(items) > pos:
        # get the strings for day, month, year (input format d.m.yyyy)
        i_date_list = items[len(items) - pos].split('.')
        # without 3 items, it's not a correct date
        if len(i_date_list) == 3:
            # convert the date string to YYYYMMDD (add leading zeros if necessary)
            i_date = i_date_list[2] + i_date_list[1].zfill(2) + i_date_list[0].zfill(2)
            # we look for our dates
            for start_date in timespans.keys():
                if i_date >= start_date:
                    # 'for' assigns an anonymous key to a variable, which is what we need, even if
                    # there will be only one key
                    for end_date in timespans[start_date].keys():
                        if i_date <= end_date:
                            key_list = [start_date, end_date]
                            # now we consume the timespan data
                            items = pp_consume_timespan(key_list, items, pos)
    return (items)


# primitive global replacements: the dictionary has keys (to look up) and replacement values.
# these will be replaced wherever they occur
# only literal keys are allowed, no regular expressions.
def pp_glob(items, glob_replacements):
    for i, it in enumerate(items):
        for k in glob_replacements.keys():
            # update the working value to prevent regressions when multiple matches occur
            it = it.replace(k, glob_replacements.get(k))
            items[i] = it
    return items


# value/replacement dictionary
glob_replacements = {'Zurich': 'Zürich',
                     ' City': '',
                     ' Township': '',
                     ' Province': '',
                     'Mezguita': 'Tamnougalt',
                     'Marrakech': 'Marrakesch',
                     'Marrakesh': 'Marrakesch'}


# main filter
def postprocess(items: [str], sep: str) -> str:
    outitems = []
    # clear the drop list
    delx.clear()
    print(items)
    # first, replace the global stuff
    items = pp_glob(items, glob_replacements)
    # get metadata from timespans
    # (if it was me who photographed)
    #if 'Hartmut' in items[len(items)-1]:
    items = pp_metadata_from_timespan(items)
    print(items)
    # now the specific filters
    for ix, it in enumerate(items):
        if it == "Südkorea":
            outitems = pp_s_korea(items, it, ix)
        if it == "Mark":
            outitems = pp_mark(items, it, ix)
        if it == "Marokko":
            outitems = pp_morocco(items, it, ix)
        if it == "Schweiz":
            outitems = pp_ch(items, it, ix)

    if not outitems:
        print("Status line unfiltered.")
    else:
        # only now, we remove the dropped items
        for x in delx:
            if x >= 0:
                if outitems[x]:
                    del outitems[x]
        print("Status line changed to:")
        print(outitems)
        items = outitems

    # if you return a list of items, the final processing will cause empties to be filtered out and
    # multiple items to be returned only once (unconditionally), and finally join them to a line using the
    # separator string.
    return items
    # if you return a list of only one item, the final processing step will see this as a non-empty, unique, single item
    # and will return it unmodified. This way, you can define the final processing step here. The example drops
    # empty items and joins them with the separator, but does not remove multiples.
    # return [sep.join(filter(lambda x: len(x) > 0, items))]


def export():
    # return callable to Rust code
    return postprocess
