# python code that takes the metadata tags, after they have
# been processed using the regex definitions and been joined by the separator,
# and processes them accordingly. It is currently required that this will return
# a list of items (strings).
#
# The output will be unconditionally cleaned of empties and uniquified (so you should probably
# set 'uniquify' and 'hide_empty' to false to have consistency in your input).
#
# this holds the item postions we want to drop
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
        if items[ix - 1] in ["Seoul", "Busan"]:
            # ...but drop the city district
            delx.append(ix - 2)
        else:
            # ...otherwise drop the province
            delx.append(ix - 1)
    # always drop the district quarter
    delx.append(ix - 3)
    return items


def pp_morocco(items, it, ix):
    # drop the province
    delx.append(ix - 1)
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
    # assign new content to province item
    items[ix] = loc + ' ' + ''.join(['(', it, ')'])
    return items


# this defines timespans per country
# { 'Start date': {'End date': 'Country'}, ... }
# date format is YYYYMMDD
# this way, un-geotagged images will be associated with the country you visited
timespans = {'20170210':{'20170222':'Portugal'}, '20140925':{'20141101':'USA'}}

# associate an image date with the country if it is in the associated timespan
def pp_country_from_timespan(items):
    # we assume that date is the item before the last and that it's formatted d.m.yyyy
    # and that country is the item before date
    # this has to be configured that way in the configuration file
    # no real error checking is being done here
    # the next two conditionals should catch crashes from missing indices
    # we need at least country|date|something, so more than two items
    if len(items) > 2:
        # if there's no country information
        if not items[len(items) -3]:
           # get the strings for day, month, year (input format d.m.yyyy)
            i_date_list = items[len(items) -2].split('.')
        else:
            # too few items, check instructions in the configuration file; we do nothing
            return items
        if len(i_date_list) != 3:
            # this is not a correct date, do nothing.
            return items
        # convert the date string to YYYYMMDD
        i_date = i_date_list[2]+i_date_list[1].zfill(2)+i_date_list[0].zfill(2)
        for start_date in timespans.keys():
            if i_date >= start_date:
                for end_date in timespans[start_date].keys():
                    if i_date <= end_date:
                        # this assumes the country is before the date
                        items[len(items) -3] = timespans[start_date].get(end_date)
    return(items)


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
glob_replacements = {'Zurich': 'Zürich', ' City': '', ' Township': '', ' Province': ''}


# main filter
def postprocess(items: [str], sep: str) -> str:
    outitems = []
    # clear the drop list
    delx.clear()
    print(items)
    # first, replace the global stuff
    items = pp_glob(items, glob_replacements)
    items= pp_country_from_timespan(items)
    print(items)
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
