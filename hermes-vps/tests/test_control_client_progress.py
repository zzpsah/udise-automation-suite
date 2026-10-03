#!/usr/bin/env python3
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("control_client",ROOT/"tools"/"control_client.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
events=[
{"id":1,"message":"Starting UDISE job"},
{"id":2,"message":"Roster loaded: 208 students"},
{"id":3,"message":"UDISE session authenticated"},
{"id":4,"message":"Full snapshot: 1/208 students checked"},
{"id":5,"message":"Full snapshot: 52/208 students checked"},
{"id":6,"message":"Full snapshot: 104/208 students checked"},
{"id":7,"message":"Full snapshot: 156/208 students checked"},
{"id":8,"message":"Full snapshot: 208/208 students checked"},
{"id":9,"message":"Report file ready"},
{"id":10,"message":"Completed successfully"},
]
lines,last,bucket=m.milestone_events(events,step=25)
assert "Roster loaded: 208 students" in lines
assert "UDISE session authenticated" in lines
assert "PROGRESS=25% (52/208)" in lines
assert "PROGRESS=50% (104/208)" in lines
assert "PROGRESS=75% (156/208)" in lines
assert "PROGRESS=100% (208/208)" in lines
assert "Report file ready" in lines
assert "Completed successfully" in lines
assert not any("1/208" in x for x in lines)
assert last==10
print("1/1 passed")
