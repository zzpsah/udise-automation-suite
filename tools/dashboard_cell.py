#@title Open UDISE dashboard { display-mode: "form" }
import traceback
import ipywidgets as widgets
from IPython.display import display, clear_output

globals()['DASHBOARD_SOURCES'] = __SOURCE_MAP__

def dash_button(label, action, color='#24558c'):
    button = widgets.Button(description=label, layout=widgets.Layout(width='230px', height='42px'))
    button.style.button_color = color
    button.on_click(action)
    return button

def dash_panel(title, explanation, controls):
    return widgets.VBox([
        widgets.HTML(f'<div style="padding:14px;border-radius:10px;background:#eaf2fb"><b>{title}</b><br>{explanation}</div>'),
        *controls,
    ], layout=widgets.Layout(padding='10px', border='1px solid #c7d7ea', width='100%'))

dash_output = widgets.Output(layout=widgets.Layout(border='1px solid #c7d7ea', padding='12px', max_height='520px', overflow='auto', width='100%'))

def dash_run(step, replacements=(), secret=None):
    source = DASHBOARD_SOURCES[step]
    for before, after in replacements:
        if before not in source:
            raise RuntimeError(f'Control for {step} no longer matches the notebook. Use the original cell below.')
        source = source.replace(before, after, 1)
    if secret is not None:
        globals()['_DASH_COOKIE'] = secret
        before = 'cookie_header = getpass("Paste complete UDISE Cookie header: ").strip()'
        if before not in source:
            raise RuntimeError('Authentication cell changed. Use the original cell below.')
        source = source.replace(before, 'cookie_header = _DASH_COOKIE.strip()', 1)
    with dash_output:
        clear_output(wait=True)
        print(f'Running: {step}', flush=True)
        try:
            transformed = get_ipython().input_transformer_manager.transform_cell(source)
            exec(compile(transformed, f'<dashboard:{step}>', 'exec'), globals())
        except Exception as exc:
            print(f'Action stopped: {type(exc).__name__}: {exc}', flush=True)
            traceback.print_exc(limit=2)
        finally:
            globals().pop('_DASH_COOKIE', None)

school_input = widgets.Text(description='School URL / ID', layout=widgets.Layout(width='95%'))
udise_input = widgets.Text(description='UDISE code', layout=widgets.Layout(width='95%'))
school_name_input = widgets.Text(description='School name', layout=widgets.Layout(width='95%'))
cookie_input = widgets.Password(description='Cookie', layout=widgets.Layout(width='95%'))
roster_timeout = widgets.BoundedIntText(value=300, min=15, max=300, description='Wait seconds')

def authenticate(_):
    value = cookie_input.value
    cookie_input.value = ''
    if not value:
        with dash_output:
            clear_output(wait=True)
            print('Enter the Cookie header in the password field first.')
        return
    dash_run('Authentication', secret=value)

def detect(_):
    if not school_input.value.strip():
        with dash_output:
            clear_output(wait=True)
            print('Enter the school URL or internal school ID first.')
        return
    dash_run('Detect school', [
        ('SCHOOL_URL_OR_CODE = ""', f'SCHOOL_URL_OR_CODE = {school_input.value.strip()!r}'),
        ('UDISE_CODE = ""', f'UDISE_CODE = {udise_input.value.strip()!r}'),
        ('SCHOOL_NAME = ""', f'SCHOOL_NAME = {school_name_input.value.strip()!r}'),
    ])

start_card = dash_panel('1. Start', 'Run these buttons from top to bottom. Results appear in the panel below.', [
    dash_button('Set up environment', lambda _: dash_run('Setup environment')),
    cookie_input,
    dash_button('Authenticate', authenticate),
    school_input, udise_input, school_name_input,
    dash_button('Detect school', detect),
    roster_timeout,
    dash_button('Fetch students', lambda _: dash_run('Fetch current academic-session students', [('ROSTER_READ_TIMEOUT = 300', f'ROSTER_READ_TIMEOUT = {roster_timeout.value}') ])),
])

gp_approve = widgets.Checkbox(value=False, description='I reviewed the General Profile workbook')
def gp_submit(_):
    if gp_approve.value:
        dash_run('General Profile — Submit Updates', [('ALLOW_PROFILE_UPDATE = False', 'ALLOW_PROFILE_UPDATE = True')])
    else:
        with dash_output:
            clear_output(wait=True)
            print('Review and validate the workbook, then check the review box.')
gp_card = dash_panel('2. General Profile', 'Download, edit, upload, validate, then review before submission.', [
    dash_button('Load dropdown labels', lambda _: dash_run('REFERENCE DATA')),
    dash_button('Download workbook', lambda _: dash_run('General Profile — Download Excel')),
    dash_button('Upload workbook', lambda _: dash_run('General Profile — Upload Excel')),
    dash_button('Validate workbook', lambda _: dash_run('General Profile — Validate Excel')),
    gp_approve, dash_button('Submit reviewed updates', gp_submit, '#905620'),
])

enrolment_class = widgets.Dropdown(options=['IX', 'X', 'IX and X'], value='IX', description='Class')
enrolment_end = widgets.BoundedIntText(value=0, min=0, max=100000, description='End Excel row')
enrolment_approve = widgets.Checkbox(value=False, description='I reviewed the Enrollment workbook')
def enrolment_submit(_):
    if enrolment_approve.value:
        dash_run('Enrolment Profile — Submit Reviewed Updates', [
            ('ALLOW_ENROLMENT_UPDATE = False', 'ALLOW_ENROLMENT_UPDATE = True'),
            ('ENROLMENT_END_ROW = 0', f'ENROLMENT_END_ROW = {enrolment_end.value}'),
        ])
    else:
        with dash_output:
            clear_output(wait=True)
            print('Review and validate the workbook, then check the review box.')
enrolment_card = dash_panel('3. Enrollment Profile', 'End Excel row 0 processes every validated row. Row 2 processes only the first student.', [
    enrolment_class,
    dash_button('Load class subject choices', lambda _: dash_run('Enrolment Profile — Load IX/X subject rules', [('ENROLMENT_CLASS = "IX"', f'ENROLMENT_CLASS = {enrolment_class.value!r}') ])),
    dash_button('Download workbook', lambda _: dash_run('Enrolment Profile — Export Selected Class Excel')),
    dash_button('Upload and validate', lambda _: dash_run('Enrolment Profile — Validate Selected Class Excel')),
    enrolment_end, enrolment_approve,
    dash_button('Submit reviewed rows', enrolment_submit, '#905620'),
])

facility_class = widgets.Dropdown(options=['IX', 'X', 'IX and X'], value='IX', description='Class')
facility_max = widgets.BoundedIntText(value=1, min=1, max=100000, description='Max rows')
facility_approve = widgets.Checkbox(value=False, description='I reviewed the Facility workbook')
def facility_submit(_):
    if facility_approve.value:
        dash_run('Facility Profile — Submit Reviewed Updates', [
            ('ALLOW_FACILITY_UPDATE = False', 'ALLOW_FACILITY_UPDATE = True'),
            ('FACILITY_MAX_SUBMISSIONS = 1', f'FACILITY_MAX_SUBMISSIONS = {facility_max.value}'),
        ])
    else:
        with dash_output:
            clear_output(wait=True)
            print('Review and validate the workbook, then check the review box.')
facility_card = dash_panel('4. Facility Profile', 'Class IX defaults unanswered Yes/No fields to No. Enter actual height and weight.', [
    facility_class,
    dash_button('Select class', lambda _: dash_run('Facility Profile — Select Class and Load Reference Data', [('FACILITY_CLASS = "IX"', f'FACILITY_CLASS = {facility_class.value!r}') ])),
    dash_button('Download workbook', lambda _: dash_run('Facility Profile — Export Selected Class Excel')),
    dash_button('Upload and validate', lambda _: dash_run('Facility Profile — Upload and Validate')),
    facility_max, facility_approve,
    dash_button('Submit reviewed rows', facility_submit, '#905620'),
])

other_card = dash_panel('5. Other tools', 'Run these only for the relevant school workflow.', [
    dash_button('All students details', lambda _: dash_run('Download ALL STUDENTS DETAILS')),
    dash_button('PEN search', lambda _: dash_run('PEN SEARCH MODULE')),
    dash_button('Bulk student import', lambda _: dash_run('BULK STUDENT IMPORT SYSTEM')),
])

dashboard_tabs = widgets.Tab(children=[start_card, gp_card, enrolment_card, facility_card, other_card], layout=widgets.Layout(width='100%'))
for index, title in enumerate(('Start', 'General', 'Enrollment', 'Facility', 'Other')):
    dashboard_tabs.set_title(index, title)
display(widgets.VBox([dashboard_tabs, widgets.HTML('<b>Current action and result</b>'), dash_output], layout=widgets.Layout(width='100%')))
