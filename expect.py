import pdb
from beancount.core import data
from dateutil.rrule import rrule, FREQNAMES
import datetime as dt
from itertools import groupby

__plugins__ = ['expect']


multiplier = {
    'YEARLY': 1,
    'MONTHLY': 12,
    'WEEKLY': 56,
    'DAILY': 365.25,
}


def _is_origin(entry):
    assert isinstance(entry, data.Transaction)
    v = True
    v = v and entry.meta.get('expected')
    v = v and entry.meta.get('expected').lower() in ["true", "t"]
    return v


def tag_entry(tag: str, entry):
    new_tagset = entry.tags.union(set([tag]))
    return entry._replace(tags=new_tagset)


def get_expected_dates(entry):
    freq_param = entry.meta.get('frequency', 'monthly').upper()
    freq = FREQNAMES.index(freq_param)
    interval = entry.meta.get('interval', 1)
    duration = entry.meta.get('duration_in_years', 1)
    _count = multiplier.get(freq_param) * duration / interval
    count = entry.meta.get('count', _count)
    if entry.meta.get('until'):
        until = dt.date.fromisoformat(entry.meta.get('until'))
    else:
        until = None
    expected_dates = [d.date() for d in rrule(freq=freq,
                                              dtstart=entry.date,
                                              count=count,
                                              interval=interval,
                                              until=until)]
    # TODO ensure recurrences are on business days
    return expected_dates


def all_equal(iterable):
    # https://stackoverflow.com/a/3844832/2265140
    g = groupby(iterable)
    return next(g, True) and not next(g, False)


def _have_same_postings_accounts(entries: list) -> bool:
    postings = []
    for e in entries:
        postings.append(set([p.account for p in e.postings]))
    if all_equal(postings):
        return True
    return False


def _is_overtrown_by_real_entry(exp_entry,
                                entries,
                                margin: dt.timedelta = dt.timedelta(days=7)):
    for real_entry in entries:
        if _have_same_postings_accounts([exp_entry, real_entry]):
            if real_entry.date >= exp_entry.date - margin:
                return True
    return False
    # pdb.set_trace()


def expect(entries, options_map, config_string="{}"):
    ""
    errors = []
    forecasted = []
    # process, from now on, only data.Transactions
    txns = [e for e in entries if isinstance(e, data.Transaction)]
    # iterate transactions that generate expectations
    for txn in [txn for txn in txns if _is_origin(txn)]:
        # get dates for expected transactions
        expectations = get_expected_dates(txn)
        # iterate the expected dates
        for expected_date in expectations:
            # copy the entry, using the expected date and tag with 'expected'
            # TODO copy without medatdata
            expected_entry = txn._replace(date=expected_date)
            expected_entry = tag_entry('expected', expected_entry)
            # check if the new entry is a duplicate of an existing one
            # e.g., there is real transaction overwriting the expected
            if _is_overtrown_by_real_entry(expected_entry, txns):
                continue
            else:
                forecasted.append(expected_entry)
    return entries + forecasted, errors

# TODO if until is approaching, error that forecasted are finishing
