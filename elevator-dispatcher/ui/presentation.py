"""Display-only components. No operational state is changed here."""
from html import escape
ELEVATOR='<svg viewBox="0 0 90 110" fill="none" aria-hidden="true"><path d="M45 0v18M45 92v18" stroke="currentColor" stroke-width="2"/><rect x="15" y="18" width="60" height="74" rx="8" stroke="currentColor" stroke-width="4"/><path d="M45 34v42m-12-30 12-12 12 12m-24 18 12 12 12-12" stroke="#dc77ac" stroke-width="5"/></svg>'
def progress_strip(status):
    steps=[('UNASSIGNED','Unassigned'),('ASSIGNED','Assigned'),('ACKNOWLEDGED','Acknowledged'),('IN_PROGRESS','In progress'),('RESTORED','Restored'),('CLOSED','Closed')]
    active='IN_PROGRESS' if status in {'EN_ROUTE','ON_SITE','DIAGNOSING','REPAIRING'} else status
    items=''.join('<li class="'+('current' if key==active else '')+'"'+(' aria-current="step"' if key==active else '')+'><span class="step-dot"></span><span>'+label+'</span></li>' for key,label in steps)
    note='Paused · Blocked' if status=='BLOCKED' else 'Current status: '+status.replace('_',' ').title()
    return '<section class="progress-panel" aria-label="Work progress"><h4>Work progress</h4><ol class="progress-strip">'+items+'</ol><p>'+escape(note)+' · Current state only; earlier steps are not inferred.</p></section>'
