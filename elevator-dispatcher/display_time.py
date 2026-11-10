"""Display New York civil time; keep authoritative stored timestamps in UTC."""
from datetime import datetime
from zoneinfo import ZoneInfo
NY=ZoneInfo('America/New_York')
def ny_time(value):
    if not value:return 'Not recorded'
    dt=datetime.fromisoformat(value) if isinstance(value,str) else value
    if dt.tzinfo is None:raise ValueError('Timestamp must include a timezone')
    return dt.astimezone(NY).strftime('%b %d, %Y · %I:%M %p %Z')
def ny_window(start,end):
    a=start.astimezone(NY);b=end.astimezone(NY)
    return f'{a:%I:%M %p}–{b:%I:%M %p %Z}'
def local_rows(rows):
    return [{**row,**{k:ny_time(row[k]) for k in ('start','end','last_update','timestamp') if row.get(k)}} for row in rows]
