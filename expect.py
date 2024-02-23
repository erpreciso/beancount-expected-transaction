import collections
import pdb
from beancount.core import data
from dateutil.rrule import rrule, FREQNAMES
from datetime import date

__plugins__ = ['expect']


multiplier = {
    'YEARLY': 1,
    'MONTHLY': 12,
    'WEEKLY': 56,
    'DAILY': 365.25,
}


def _is_origin(entry):
    v = isinstance(entry, data.Transaction)
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
        until = date.fromisoformat(entry.meta.get('until'))
    else:
        until = None
    expected_dates = [dt.date() for dt in rrule(freq=freq,
                                                dtstart=entry.date,
                                                count=count,
                                                interval=interval,
                                                until=until)]
    return expected_dates


def expect(entries, options_map, config_string="{}"):
    ""
    errors = []
    forecasted = []
    for entry in [entry for entry in entries if _is_origin(entry)]:
        for expected_date in get_expected_dates(entry):
            expected_entry = entry._replace(date=expected_date)
            expected_entry = tag_entry('expected', expected_entry)
            # TODO compare with existing entries
            # TODO if until is approaching, error that forecasted are finishing
            forecasted.append(expected_entry)
    # pdb.set_trace()
    return entries + forecasted, errors
