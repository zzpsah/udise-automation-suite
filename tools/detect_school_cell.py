#@title Detect school { display-mode: "form" }
import re

SCHOOL_URL_OR_CODE = "" #@param {type:"string"}
UDISE_CODE = "" #@param {type:"string"}
SCHOOL_NAME = "" #@param {type:"string"}

school_reference = SCHOOL_URL_OR_CODE.strip()
if not school_reference:
    school_reference = input('Paste UDISE+ School URL or enter its numeric internal school ID: ').strip()

url_match = re.search(r'/school/(\d+)(?:/|$)', school_reference)
if url_match:
    SCHOOL_ID = url_match.group(1)
elif re.fullmatch(r'\d{7}', school_reference):
    SCHOOL_ID = school_reference
elif re.fullmatch(r'\d{11}', school_reference):
    raise ValueError('This is an 11-digit UDISE code. Paste the school URL or its 7-digit internal school ID here; enter the UDISE code in the separate field.')
else:
    raise ValueError('Enter a complete UDISE school URL or its 7-digit internal school ID.')

UDISE_CODE = UDISE_CODE.strip()
if UDISE_CODE and not re.fullmatch(r'\d{11}', UDISE_CODE):
    raise ValueError('UDISE code must contain 11 digits.')
SCHOOL_NAME = ' '.join(SCHOOL_NAME.split())
# This identity was confirmed on the authenticated school dashboard on 23 Sep 2026.
known_school = {'2497128': ('10160203806', 'UCHCH MADHYAMIK VIDYALAY, TETAHALI')}.get(SCHOOL_ID)
if known_school:
    if UDISE_CODE and UDISE_CODE != known_school[0]:
        raise ValueError('Entered UDISE code does not match the selected internal school ID.')
    if SCHOOL_NAME and SCHOOL_NAME.casefold() != known_school[1].casefold():
        raise ValueError('Entered school name does not match the selected internal school ID.')
    UDISE_CODE, SCHOOL_NAME = known_school
print(f'Internal school ID for API requests: {SCHOOL_ID}')
print(f'UDISE code: {UDISE_CODE or "not entered"}')
if SCHOOL_NAME:
    print(f'School name: {SCHOOL_NAME}')
else:
    print('School name: not entered. It will be displayed after roster fetch if UDISE includes it.')
