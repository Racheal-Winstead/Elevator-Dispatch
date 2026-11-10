"""Run from project root: python3 tests/benchmark.py"""
import sys, json, platform
from pathlib import Path
from time import perf_counter
from statistics import median
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from demo_adapter.fixtures import load_fixture
from integrations.deshawn_adapter import recommend
from roster import demo_roster, slots, RULES
samples=[]
tickets=load_fixture(50); roster=demo_roster()
for _ in range(10):
    start=perf_counter(); proposals,exceptions=recommend(tickets,roster,RULES,slots(),[]); samples.append(perf_counter()-start)
print(json.dumps({'python':platform.python_version(),'os':platform.platform(),'machine':platform.machine(),'tickets':len(tickets),'resources':len(roster),'runs':len(samples),'median_seconds':median(samples),'max_seconds':max(samples),'recommendations':len(proposals),'exceptions':len(exceptions),'scope':'Pinned-engine data adapter computation only; excludes fetch and UI'},indent=2))
