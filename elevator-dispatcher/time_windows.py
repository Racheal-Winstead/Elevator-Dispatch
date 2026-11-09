"""One timezone-aware interval boundary for UI, adapters and persistence."""
from datetime import datetime, timezone

def utc(value):
    try:
        value=datetime.fromisoformat(value) if isinstance(value,str) else value
        if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Timezone-aware timestamp required')
        return value.astimezone(timezone.utc)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError('INVALID_TIME_WINDOW: a valid timezone-aware timestamp is required') from exc

def window(start,end):
    start,end=utc(start),utc(end)
    if start>=end: raise ValueError('INVALID_TIME_WINDOW: start must precede end')
    return start,end

def overlaps(start,end,other_start,other_end):
    start,end=window(start,end); other_start,other_end=window(other_start,other_end)
    return start<other_end and other_start<end

def booked(technician_id,start,end,assignments):
    return any(technician_id in a['crew'] and overlaps(start,end,a['start'],a['end']) for a in assignments)
