#@title Detect school { display-mode: "form" }
import re

SCHOOL_URL_OR_CODE = "" #@param {type:"string"}
SCHOOL_NAME = "" #@param {type:"string"}

school_reference = SCHOOL_URL_OR_CODE.strip()
if not school_reference:
    school_reference = input('Paste UDISE+ School URL or enter the numeric UDISE code: ').strip()

url_match = re.search(r'/school/(\d+)(?:/|$)', school_reference)
if url_match:
    SCHOOL_ID = url_match.group(1)
elif re.fullmatch(r'\d{7,15}', school_reference):
    SCHOOL_ID = school_reference
else:
    raise ValueError('Enter a complete UDISE school URL or a numeric UDISE code (7–15 digits).')

SCHOOL_NAME = ' '.join(SCHOOL_NAME.split())
print(f'UDISE code detected: {SCHOOL_ID}')
if SCHOOL_NAME:
    print(f'School name: {SCHOOL_NAME}')
else:
    print('School name: not entered. It will be displayed after roster fetch if UDISE includes it.')
