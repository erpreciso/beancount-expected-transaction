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
    """Return if entry is an origin for an expectation.

    :param entry: Entry
    :returns: Boolean

    """
    assert isinstance(entry, data.Transaction)
    v = True
    v = v and entry.meta.get('expected')
    v = v and entry.meta.get('expected').lower() in ["true", "t"]
    return v


def tag_entry(tag: str, entry):
    """Add tag to an entry.

    :param tag: Tag to be added
    :param entry: Entry
    :returns: 

    """
    new_tagset = entry.tags.union(set([tag]))
    return entry._replace(tags=new_tagset)


def get_expected_dates(entry):
    """Get expected dates based on entry parameters.

    :param entry: Entry
    :returns: list of expected dates

    Reads entry metadata:
    - frequency :: must be in the RFC 5545 names
      (https://datatracker.ietf.org/doc/html/rfc5545),
      otherwise default to monthly
    - interval :: interval between expectations
    - until OR count OR duration_in_years :: either end date, or
      number of expected occurrences. The two meta MUST NOT be given
      both in the same entry
      (https://dateutil.readthedocs.io/en/stable/rrule.html#dateutil.rrule.rrule)

    """
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
    """Return if all members of iterable are equal.
    
    :param iterable: An iterable
    :returns: Boolean

    https://stackoverflow.com/a/3844832/2265140
    """
    g = groupby(iterable)
    return next(g, True) and not next(g, False)


def _have_same_postings_accounts(entries: list) -> bool:
    """Return if all entries provided have the same postings accounts.

    :param entries: List of entries
    :returns: Boolean

    """
    
    postings = []
    for e in entries:
        postings.append(set([p.account for p in e.postings]))
    if all_equal(postings):
        return True
    return False


def _is_overtrown_by_real_entry(exp_entry,
                                entries,
                                margin: int = 7):
    """Return if entry is overtrown by any existing entry.

    :param exp_entry: Entry to be checked
    :param entries: Existing entries
    :param margin: Margin in days
    :returns: Boolean

    Return True if any entry is either future, or older but within a
    margin in days. This to exclude expected dates obsolete because
    actually duplicates of existing entries either occurred in the future
    or in the immediate past.

    """
    for real_entry in entries:
        if _have_same_postings_accounts([exp_entry, real_entry]):
            margin_days = dt.timedelta(days=margin)
            if real_entry.date >= exp_entry.date - margin_days:
                return True
    return False
    # pdb.set_trace()


def expect(entries, options_map, config_string="{}"):
    """Create expected entries based on entry metadata.

    :param entries: Entries
    :param options_map: Unused option map
    :param config_string: Unused configuration string
    :returns: Existing entries and expected entries, and errors.

    """
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
