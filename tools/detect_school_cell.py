#@title Detect school { display-mode: "form" }
import re

SCHOOL_URL_OR_CODE = "" #@param {type:"string"}

school_reference = SCHOOL_URL_OR_CODE.strip()
if not school_reference:
    school_reference = input('Paste UDISE+ School URL or enter its numeric internal school ID: ').strip()

url_match = re.search(r'/school/(\d+)(?:/|$)', school_reference)
if url_match:
    SCHOOL_ID = url_match.group(1)
elif re.fullmatch(r'\d{7}', school_reference):
    SCHOOL_ID = school_reference
elif re.fullmatch(r'\d{11}', school_reference):
    raise ValueError('This is an 11-digit UDISE code. Paste the school URL or its 7-digit internal school ID instead.')
else:
    raise ValueError('Enter a complete UDISE school URL or its 7-digit internal school ID.')

# This identity was confirmed on the authenticated school dashboard on 23 Sep 2026.
known_school = {'2497128': ('10160203806', 'UCHCH MADHYAMIK VIDYALAY, TETAHALI')}.get(SCHOOL_ID)
UDISE_CODE, SCHOOL_NAME = known_school if known_school else ('', '')
print(f'Internal school ID for API requests: {SCHOOL_ID}')
print(f'UDISE code: {UDISE_CODE or "not available for this school"}')
if SCHOOL_NAME:
    print(f'School name: {SCHOOL_NAME}')
else:
    print('School name: not available yet. It will be displayed after roster fetch if UDISE includes it.')
