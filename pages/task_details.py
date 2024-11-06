from __future__ import annotations

import json
from datetime import datetime as dt
from datetime import timedelta as td

import dash
from dash import dash_table
from dash import Input, Output, State, dcc, html

from orcha.core import tasks
from orcha_ui.components import autoclear_cpm, run_slices_cmp
from orcha_ui.credentials import PLOTLY_APP_PATH

from orcha_ui.components import modal_cmp


def can_read():
    return True


dash.register_page(
    __name__,
    name='Task Details',
    path='/task_details',
    image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/list-task.svg',
    title='Task Details | Orcha',
    description='View the details of a specific task.',
    can_read_callback=can_read,
    can_edit_callback=lambda: True,
)


def get_run_css_class(run: tasks.RunItem):
    if run.progress == 'queued':
        return 'run-queued'
    elif run.progress == 'running':
        return 'run-running'
    elif run.status == 'success':
        return 'run-success'
    elif run.status == 'failed':
        return 'run-failed'
    elif run.status == 'warn':
        return 'run-warning'
    else:
        return 'run-unknown'


def create_run_history_table(task: tasks.TaskItem, all_runs: list[tasks.RunItem]):
    data = []
    all_runs.sort(key=lambda r: r.scheduled_time, reverse=True)
    for run in all_runs:
        if run.run_type == 'manual':
            schedule_text = 'Manual'
        else:
            s_set = task.get_schedule_set(run.set_idf)
            if s_set is not None:
                schedule_text = s_set.cron_schedule
            else:
                schedule_text = 'Unknown'
        data.append({
            'Run ID': run.run_idk,
            'Schedule': schedule_text,
            'Status': run.status,
            'Scheduled Time': run.scheduled_time,
            'Start Time': run.start_time,
            'End Time': run.end_time,
        })

    columns = [
        {'name': 'Run ID', 'id': 'Run ID'},
        {'name': 'Schedule', 'id': 'Schedule'},
        {'name': 'Status', 'id': 'Status'},
        {'name': 'Scheduled Time', 'id': 'Scheduled Time'},
        {'name': 'Start Time', 'id': 'Start Time'},
        {'name': 'End Time', 'id': 'End Time'}
    ]

    return html.Div(className='col-12', children=[
        dash_table.DataTable(
            data=data,
            columns=columns,
            # fixed_rows={'headers': True},
            style_table={'height': '400px'},
            style_cell={'textAlign': 'left'},
            style_header={'fontWeight': 'bold'}
        )
    ])


def create_task_element(task: tasks.TaskItem):

    all_runs = tasks.RunItem.get_all(
        task=task,
        since=dt.now() - td(days=2),
        schedule=None
    )
    all_runs.sort(key=lambda r: r.scheduled_time)
    all_runs = all_runs[-200:]

    if task.status == 'enabled':
        toggle_buttton = html.Button(
            id='td-btn-toggle-task',
            className='btn btn-sm btn-danger',
            children=[
                'Disable Task'
            ]
        )
    else:
        toggle_buttton = html.Button(
            id='td-btn-toggle-task',
            className='btn btn-sm btn-primary',
            children=[
                'Enable Task'
            ]
        )

    return [
        html.Div(className='row', children=[
            html.Div(className='col-12 border-bottom mb-2 ', children=[
                html.Div(className='row justify-content-between', children=[
                    html.Div(className='col-auto', children=[
                        html.H4('Task Details'),
                    ]),
                    html.Div(className='col-auto', children=[
                        html.Button(
                            id='td-btn-cancel-unstarted',
                            className='btn btn-sm btn-warning me-3',
                            children=[
                                'Cancel Unstarted'
                            ]
                        ),
                        toggle_buttton,
                        html.Button(
                            id={
                                'type': modal_cmp.BUTTON_SHOW_TYPE,
                                'index': 'td-delete-task-modal'
                            },
                            className='btn btn-sm btn-danger ms-3',
                            children=[
                                'Delete Task'
                            ]
                        ),
                    ]),
                ]),
            ]),
        ]),
        html.Div(className='row', children=[
            html.Div(className='col-auto', children=[
                html.H6('Task ID'),
                html.Div(task.task_idk),
            ]),
            html.Div(className='col-auto', children=[
                html.H6('Name'),
                html.Div(task.name),
            ]),
            html.Div(className='col-auto', children=[
                html.H6('Description'),
                html.Div(task.description),
            ]),
            html.Div(className='col-auto', children=[
                html.H6('Thread Group'),
                html.Div(task.thread_group),
            ]),
            html.Div(className='col-auto', children=[
                html.H6('Tags'),
                html.Div(task.task_tags),
            ]),
            html.Div(className='col-auto', children=[
                html.H6('Metadata'),
                html.Pre(json.dumps(task.task_metadata, indent=4))
            ]),
            html.Div(className='col-auto', children=[
                html.H6('Status'),
                html.Div(task.status),
            ]),
            html.Div(className='col-auto', children=[
                html.H6('Last Active'),
                html.Div(task.last_active),
                html.Div(f'({str(dt.now() - task.last_active)})'),
            ]),
        ]),
        html.Div(className='row', children=[
            html.Div(className='col-12', children=[
                html.H6('Schedules'),
            ]),
            *[
                html.Div(className='col-auto', children=[
                    html.H6('Frequency'),
                    html.P(sched.cron_schedule),
                    html.H6('Config'),
                    html.Pre(json.dumps(sched.config, indent=4))
                ])
                for sched in task.schedule_sets
            ]
        ]),
        html.Div(className='row', children=[
            html.Div(className='col-auto', children=[
                html.H6('Recent Runs')
            ]),
        ]),
        run_slices_cmp.create_run_slice_row(
            task=task,
            all_runs=all_runs,
            display_start_time=dt.now() - td(days=2),
            display_end_time=dt.now(),
            display_count=200,
        ),
        # add a row to create a manual run
        html.Div(className='row pt-5', children=[
            html.Div(className='col-12', children=[
                html.H4('Create Manual Run', className='border-bottom pb-2'),
            ])
        ]),
        # dropdown of schedules
        html.Div(className='row', children=[
            html.Div(className='col-auto', children=[
                html.H6('Select Schedule')
            ]),
            html.Div(className='col', children=[
                dcc.Dropdown(
                    id='td-schedule-dropdown',
                    options=[{'label': s.cron_schedule, 'value': s.set_idk} for s in task.schedule_sets],
                    value='',
                )
            ])
        ]),
        # create an input multiline box pre-populated with the task config
        html.Div(id='td-row-create-config', className='row', children=[
            html.Div(className='col-12', children=[
                html.H6('Config'),
                dcc.Textarea(
                    id='td-config-textarea',
                    className='form-control',
                    value='Select a schedule to populate the config',
                    style={'height': '200px'}
                ),
            ]),
        ]),
        # create a button to create a manual run
        html.Div(className='row align-items-center py-1', children=[
            html.Div(className='col-auto', children=[
                html.Button(
                    id='td-btn-create-run',
                    className='d-none',
                    children=[
                        'Create'
                    ]
                )
            ]),
            # create output for the button
            html.Div(className='col-auto', children=[
                html.Div(id={
                    'type': autoclear_cpm.AUTOCLEAR_ID_TYPE,
                    'index': 'td-out-create-run'
                })
            ])
        ]),
        # create run histoy table
        html.Div(className='row pt-5', children=[
            html.Div(className='col-12', children=[
                html.H4('Run History', className='border-bottom pb-2'),
            ])
        ]),
        html.Div(className='row overflow-scroll', children=[
            create_run_history_table(task, all_runs)
        ]),
    ]


def layout(task_id: str = ''):

    all_tasks = tasks.TaskItem.get_all()
    task = tasks.TaskItem.get(task_id)

    task_dropdown_value = task_id if task_id else ''

    if len(all_tasks) == 0:
        return html.Div(className='container-fluid', children=[
            html.Div(className='row', children=[
                html.Div(className='col-12', children=[
                    html.H3('No tasks found'),
                ])
            ])
        ])

    if task is not None:
        task_elements = create_task_element(task)
    else:
        task_elements = [
            html.Div(className='col-12', children=[
                html.H4('No task selected'),
            ]),
            # hidden divs with the required IDs
            dcc.Input(className='d-none', id='td-config-textarea'),
            html.Button(className='d-none', id='td-btn-create-run'),
            html.Div(className='d-none', id={
                'type': autoclear_cpm.AUTOCLEAR_ID_TYPE,
                'index': 'td-out-create-run'
            }),
            dcc.Input(className='d-none', id='td-schedule-dropdown'),
            html.Button(className='d-none', id='td-btn-toggle-task'),
            html.Button(className='d-none', id='td-btn-cancel-unstarted'),
            html.Button(className='d-none', id={
                'type': modal_cmp.BUTTON_OK_TYPE,
                'index': 'td-cancel-unstarted-modal'
            }),
        ]

    return [
        html.Div(className='container-fluid', children=[
            modal_cmp.create_modal(
                inner_html=html.Div([
                    html.H5(
                        'Delete Task',
                        className='fs-5'
                    ),
                    html.Span('This will delete the task and all run data'),
                    html.Br(),
                    html.Span('from the database and cannot be undone.'),
                    html.Br(), html.Br(),
                    html.Span('Logs will not be deleted.'),
                ]),
                outer_style={
                    'background-color': 'white',
                    'padding': '20px',
                    'border-radius': '5px',
                    'border': '1px solid lightgray',
                    'box-shadow': '0px 0px 10px 10px rgba(0, 0, 0, 0.1)',
                },
                id_index='td-delete-task-modal',
                show=False
            ),
            html.Div(id='td-div-modal-area'),
            html.Div(className='row content-row no-bkg py-0 align-items-center', children=[
                html.Div(className='col-auto', children=[
                    html.Div('Select Task')
                ]),
                html.Div(className='col', children=[
                    dcc.Dropdown(
                        id='td-task-dropdown',
                        options=[{'label': t.name, 'value': t.task_idk} for t in all_tasks],
                        value=task_dropdown_value,
                    )
                ])
            ]),
            html.Div(
                id='td-task-details',
                className='row content-row',
                children=task_elements
            )
        ])
    ]




# update the task details page
@dash.callback(
    Output('td-task-details', 'children'),
    Input('td-task-dropdown', 'value'),
    Input('td-btn-toggle-task', 'n_clicks'),
    Input({'type': autoclear_cpm.AUTOCLEAR_ID_TYPE, 'index': 'td-out-create-run'}, 'children'),
    prevent_initial_call=True,
)
def update_task_details(task_id, toggle_clicks, create_run_output):
    task = tasks.TaskItem.get(task_id)
    if task is None:
        return [
            html.Div(className='col-12', children=[
                html.H3('Task not found'),
            ])
        ]
    if dash.ctx.triggered_id == 'td-btn-toggle-task':
        if task.status == 'enabled':
            task.set_status('disabled', 'Manually disabled')
        else:
            task.set_status('enabled', 'Manually enabled')

    return create_task_element(task)


# update the config textarea
@dash.callback(
    Output('td-config-textarea', 'value'),
    Output('td-btn-create-run', 'className'),
    Input('td-schedule-dropdown', 'value'),
    State('td-task-dropdown', 'value'),
    prevent_initial_call=True,
)
def update_config_textarea(schedule_id, task_id):
    task = tasks.TaskItem.get(task_id)

    if task is None:
        return 'No task found', 'd-none'

    s_set = None
    for schedule in task.schedule_sets:
        if schedule.set_idk == schedule_id:
            s_set = schedule
            s_set.config['notes'] = 'manually created run'
            break
    if s_set is None:
        return 'No schedule found', 'd-none'
    return [
        json.dumps(schedule.config, indent=4),
        'btn btn-primary px-5',
    ]


# show fail modal
@dash.callback(
    Output('td-div-modal-area', 'children'),
    Input('td-btn-cancel-unstarted', 'n_clicks'),
    State('td-task-dropdown', 'value'),
    prevent_initial_call=True,
)
def show_cancel_modal(n_clicks, task_id):
    if n_clicks is None:
        return dash.no_update
    if dash.ctx.triggered_id == 'td-btn-cancel-unstarted':
        task = tasks.TaskItem.get(task_id)
        if task is None:
            run_count = 0
        else:
            run_count = len(task.get_queued_runs())
        return modal_cmp.create_modal(
            inner_html=html.Div(
                html.P(
                    f'Cancel {run_count} unstarted runs?',
                    className='fs-5'
                )
            ),
            outer_style={
                'background-color': 'white',
                'padding': '20px',
                'border-radius': '5px',
                'border': '1px solid lightgray',
                'box-shadow': '0px 0px 10px 10px rgba(0, 0, 0, 0.1)',
            },
            id_index='td-cancel-unstarted-modal',
            show=True
        )

# cancel all unstarted runs
@dash.callback(
    Output({'type': autoclear_cpm.AUTOCLEAR_ID_TYPE, 'index': 'td-out-create-run'}, 'children', allow_duplicate=True),
    Input({'type': modal_cmp.BUTTON_OK_TYPE, 'index': 'td-cancel-unstarted-modal'}, 'n_clicks'),
    State('td-task-dropdown', 'value'),
    prevent_initial_call=True,
)
def cancel_unstarted_runs(ok_clicks, task_id):
    if ok_clicks is None:
        return dash.no_update
    task = tasks.TaskItem.get(task_id)
    if task is None:
        return 'No task selected'
    unstarted_runs = task.get_queued_runs()
    for run in unstarted_runs:
        run.set_status(
            'cancelled',
            output={'message': 'Unstarted runs manually cancelled'}
        )
        run.set_progress(
            progress='complete',
            zero_duration=True
        )
    return 'Unstarted runs cancelled'

# create a manual run
@dash.callback(
    Output({'type': autoclear_cpm.AUTOCLEAR_ID_TYPE, 'index': 'td-out-create-run'}, 'children', allow_duplicate=True),
    Input('td-btn-create-run', 'n_clicks'),
    State('td-config-textarea', 'value'),
    State('td-task-dropdown', 'value'),
    State('td-schedule-dropdown', 'value'),
    prevent_initial_call=True,
)
def create_manual_run(n_clicks, config, task_id, schedule_id):
    if n_clicks is None:
        return 'Create Failed'
    task = tasks.TaskItem.get(task_id)
    if task is None:
        return 'Create Failed'
    try:
        new_config = json.loads(config)
    except json.JSONDecodeError:
        return 'Config is not valid JSON'

    for schedule in task.schedule_sets:
        if schedule.set_idk == schedule_id:
            schedule.config = new_config
            run = tasks.RunItem.create(
                task=task,
                run_type='manual',
                schedule=schedule,
                scheduled_time=dt.now(),
                created_by='orcha_ui',
            )
            if run:
                return 'Manual run created'
            break
    else:
        return 'Create Failed'


# delete task callback
@dash.callback(
    Output('app-location', 'href'),
    Input({'type': modal_cmp.BUTTON_OK_TYPE, 'index': 'td-delete-task-modal'}, 'n_clicks'),
    State('td-task-dropdown', 'value'),
    prevent_initial_call=True,
)
def delete_task(ok_clicks, task_id):
    if ok_clicks is None:
        return dash.no_update
    task = tasks.TaskItem.get(task_id)
    if task is None:
        return '/overview'
    try:
        task.delete_from_db()
    except Exception:
        return f'/task_details?task_id={task_id}'
    return '/overview'


@dash.callback(
    Output('app-location-norefresh', 'search', allow_duplicate=True),
    Input('td-task-dropdown', 'value'),
    prevent_initial_call=True,
)
def update_url(task_id):
    return f'?task_id={task_id}'