"""Proposed joint interface v0.1; all records are synthetic."""
from dataclasses import dataclass, field
from datetime import datetime

RULE_VERSION = 'demo-0.2-boroughs'
STATUSES = ['UNASSIGNED','ASSIGNED','ACKNOWLEDGED','EN_ROUTE','ON_SITE','DIAGNOSING','REPAIRING','RESTORED','CLOSED','BLOCKED']
@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    source_record_id: str
    building: str
    sector: str
    depot: str
    asset: str
    description: str
    created_at: datetime
    priority: int = 3
    work_type: str = 'CORRECTIVE'
    hazard_review: bool = False
    critical: bool = False

@dataclass(frozen=True)
class Technician:
    technician_id: str
    alias: str
    role: str
    attendance: str
    sectors: tuple
    depots: tuple
    shift_start: datetime
    shift_end: datetime
    active: bool = True
    qualifications: tuple = ('ELEVATOR_DEMO',)
    certification_status: str = 'DEMO_CONFIGURED'
    certification_expiry: datetime | None = None

@dataclass(frozen=True)
class CrewRule:
    roles: tuple = ('MECHANIC','HELPER')
    qualifications: tuple = ('ELEVATOR_DEMO',)
    source: str = 'Illustrative demo policy; operations approval pending'

@dataclass(frozen=True)
class Proposal:
    ticket_id: str
    crew: tuple
    start: datetime
    end: datetime
    explanation: str = 'Complete crew; demo attendance, shift, qualification and area checks passed.'
    rule_version: str = RULE_VERSION
    scheduler_source: str = 'LOCAL_FIXTURE'
    engine_rule_version: str = ''
    engine_commit: str = ''
