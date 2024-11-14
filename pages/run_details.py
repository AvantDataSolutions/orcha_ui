from __future__ import annotations

import json
from datetime import datetime as dt
from datetime import timedelta as td

import dash
from dash import dcc, html

from orcha.core import tasks
from orcha_ui.components import modal_cmp
from orcha_ui.credentials import PLOTLY_APP_PATH
from orcha_ui.utils import format_dt


def can_read():
    return True


dash.register_page(
    __name__,
    name='Run Details',
    path='/run_details',
    image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/bullseye.svg',
    title='Run Details | Orcha',
    description='View the details of a specific run.',
    can_read_callback=can_read,
    can_edit_callback=lambda: True,
)


def create_run_detail_rows(run: tasks.RunItem | None):

    if run is None:
        return html.Div(className='row', children=[
            html.Div(className='col-12', children=[
                html.H4('No run selected')
            ])
        ])

    duration = 'Not Started'
    if run.start_time:
        if run.end_time:
            duration = str(td(seconds=(run.end_time - run.start_time).total_seconds()))
        else:
            # add hh:mm:ss to duration
            duration = f'In Progress ({str(dt.now() - run.start_time)[:-7]})'

    schedule_div = ''
    if run.run_type == 'scheduled':
        s_set = None
        for s in run._task.schedule_sets:
            if s.set_idk == run.set_idf:
                s_set = s
                break
        if s_set:
            schedule_div = html.Div(className='col', children=[
                html.H6('Schedule'),
                html.P(s_set.cron_schedule)
            ])

    # Output is a dict of unknowns, so we want to truncate each
    # key-value pair to 3000 characters
    # We also want to format the text to be more readable
    run_output = run.output
    if run_output:
        # cast to string in the event people log numbers or other types
        run_output = {
            k: v for k, v in run_output.items()
        }
        run_output = json.dumps(run_output, indent=4)[0:5000].replace("\\n", "   \n")
    else:
        run_output = 'No output'

    return [
        html.Div(className='row mb-1 border-bottom', children=[
            html.Div(className='col', children=[
                html.H4('Parent Task'),
            ]),
            html.Div(className='col-auto', children=[
                html.Button(
                    id={
                        'type': 'rd-btn-go-to-task',
                        'index': run.task_idf
                    },
                    className='btn btn-sm btn-primary me-3',
                    children=[
                        'Go to Task'
                    ]
                )
            ]),
        ]),
        html.Div(className='row', children=[
            html.Div(className='col', children=[
                html.H6('Name'),
                html.P(run._task.name),
            ]),
            html.Div(className='col', children=[
                html.H6('Description'),
                html.P(run._task.description),
            ]),
            html.Div(className='col', children=[
                html.H6('Status'),
                html.P(run._task.status),
            ]),
        ]),
        html.Div(className='row', children=[
            html.Div(className='col-12 border-bottom mb-2 ', children=[
                html.Div(className='row justify-content-between', children=[
                    html.Div(className='col-auto', children=[
                        html.H4('Run Details'),
                    ]),
                    html.Div(className='col-auto', children=[
                        html.Button(
                            id={
                                'type': modal_cmp.BUTTON_SHOW_TYPE,
                                'index': 'rd-cancel-run-modal'
                            },
                            className='btn btn-sm btn-warning me-3',
                            disabled=run.progress == 'complete',
                            children=[
                                'Cancel Run'
                            ]
                        )
                    ]),
                ]),
            ]),
        ]),
        html.Div(className='row', children=[
            html.Div(className='col-auto me-2', children=[
                html.H6('Run ID'),
                html.P(run.run_idk),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Scheduled Time'),
                html.P(format_dt(run.scheduled_time)),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Created By'),
                html.P(f'{run.created_by} ({format_dt(run.created_time)})'),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Start Time'),
                html.P(format_dt(run.start_time)),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('End Time'),
                html.P(format_dt(run.end_time)),
            ]) if run.progress == 'complete' else '',
            html.Div(className='col-auto me-2', children=[
                html.H6('Duration'),
                html.P(duration),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Last Active'),
                html.Div(
                    f'{format_dt(run.last_active)} \
                    ({str(dt.now() - run.last_active)[:-7]})'
                ) if run.last_active else '',
            ]) if run.progress == 'running' else '',
            html.Div(className='col-auto me-2', children=[
                html.H6('Progress'),
                html.P(run.progress),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Status'),
                html.P(run.status),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Type'),
                html.P(run.run_type),
            ]),
            schedule_div,
        ]),
        html.Div(className='row', children=[
            html.Div(className='col', children=[
                html.H6('Config'),
                html.Pre(json.dumps(run.config, indent=4)),
            ]),
        ]),
        html.Div(className='row', children=[
            html.Div(className='col', children=[
                html.H6('Output'),
                html.Pre(
                    run_output,
                    style={'white-space': 'pre-wrap'}
                ),
            ]),
        ]),
        html.Div(className='row', children=[
            html.Div(className='col', children=[
                html.Button(
                    id={
                        'type': 'rd-btn-go-to-run',
                        'index': run.output.get('triggered_run_id') or 'no-id'
                    },
                    className='btn btn-sm btn-primary me-3',
                    children=[
                        'Triggered Task ➡️'
                    ]
                )
            ]),
        ]) if run.output and run.output.get('triggered_run_id') else ''
    ]


def get_run_dropdown_options(task_idk: str):
    task = tasks.TaskItem.get(task_idk)
    if task is None:
        return []
    runs = tasks.RunItem.get_all(
        task=task,
        since=dt.now() - td(days=30),
        max_count=100,
        schedule=None
    )

    runs.sort(key=lambda r: r.scheduled_time, reverse=True)

    return [
        {
            'label': f'{r.scheduled_time} - {r.status}',
            'value': r.run_idk
        }
        for r in runs
    ]

def layout(run_id: str = ''):

    run = tasks.RunItem.get(run_id)

    all_tasks = tasks.TaskItem.get_all()

    task_dropdown_value = run.task_idf if run else ''

    # if the run isn't 'finished' then we want a higher update interval
    # but if its done then there really isnt anything to update
    interval_ms = 10000
    if run is not None:
        if (run.progress == 'running'):
            interval_ms = 2000

    top_dropdown_row = html.Div(className='row content-row no-bkg py-0 align-items-center', children=[
        html.Div(className='col-auto', children=[
            html.Span('Select Task')
        ]),
        html.Div(className='col', children=[
            dcc.Dropdown(
                id='rd-task-dropdown',
                options=[{'label': t.name, 'value': t.task_idk} for t in all_tasks],
                value=task_dropdown_value,
            )
        ]),
        html.Div(className='col-auto', children=[
            html.Span('Select Run')
        ]),
        html.Div(className='col', children=[
            dcc.Dropdown(
                id='rd-runs-dropdown',
                options=[],
                value=run_id,
            )
        ])
    ])

    return [
        dcc.Interval(id='rd-update-interval', interval=interval_ms),
        html.Div(className='col-auto', children=[
            top_dropdown_row,
        ]),
        modal_cmp.create_modal(
            inner_html=html.Div(
                html.P(
                    'Cancel current run?',
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
            id_index='rd-cancel-run-modal',
            show=False
        ),
        html.Div(className='col', children=[
            html.Div(className='row content-row', children=[
                html.Div(className='col-12', children=[
                    html.Div(className='row', children=[
                        html.Div(
                            id='rd-col-run-details',
                            className='col-12',
                            children=create_run_detail_rows(run)
                        )
                    ]),
                ])
            ]),
        ])
    ]

@dash.callback(
    dash.Output('app-location', 'pathname', allow_duplicate=True),
    dash.Output('app-location', 'search', allow_duplicate=True),
    dash.Input({'type': 'rd-btn-go-to-run', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def go_to_run(n_clicks):
    if all(v is None for v in n_clicks):
        return dash.no_update
    if dash.ctx.triggered_id is None:
        return dash.no_update
    run_idk = dash.ctx.triggered_id['index']
    return '/run_details', f'?run_id={run_idk}'

# go to parent task callback
@dash.callback(
    dash.Output('app-location', 'pathname', allow_duplicate=True),
    dash.Output('app-location', 'search', allow_duplicate=True),
    dash.Input({'type': 'rd-btn-go-to-task', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def go_to_task(n_clicks):
    if all(v is None for v in n_clicks):
        return dash.no_update
    if dash.ctx.triggered_id is None:
        return dash.no_update
    task_idk = dash.ctx.triggered_id['index']
    return '/task_details', f'?task_id={task_idk}'

@dash.callback(
    dash.Output('rd-runs-dropdown', 'options'),
    dash.Output('rd-runs-dropdown', 'value'),
    dash.Input('rd-task-dropdown', 'value'),
    dash.State('rd-runs-dropdown', 'value'),
)
def update_runs_dropdown(task_idk, run_id):
    if not task_idk:
        return []
    # Select the first run when changing tasks
    # This is to avoid the auto-refresh reloading the runs
    # for the current task, not the newly selected task
    options = get_run_dropdown_options(task_idk)
    selected_run = options[0]['value'] if options else None
    # If the selected run matches the current task then
    # we don't need to change the selected run
    current_run = tasks.RunItem.get(run_id)
    if current_run and current_run.task_idf == task_idk:
        selected_run = dash.no_update
    return [
        options,
        selected_run
    ]

# callback to update run details
@dash.callback(
    dash.Output('rd-col-run-details', 'children', allow_duplicate=True),
    dash.Output('app-location-norefresh', 'search', allow_duplicate=True),
    dash.Output('rd-runs-dropdown', 'options', allow_duplicate=True),
    dash.Input('rd-runs-dropdown', 'value'),
    dash.Input('rd-update-interval', 'n_intervals'),
    prevent_initial_call=True
)
def update_run_details(run_idk, n_intervals):
    if not run_idk:
        return dash.no_update
    run = tasks.RunItem.get(run_idk)
    if run is None:
        return dash.no_update

    return [
        create_run_detail_rows(run),
        f'?run_id={run_idk}',
        get_run_dropdown_options(run.task_idf)
    ]


# Callback to cancel the current run
@dash.callback(
    dash.Output('rd-col-run-details', 'children', allow_duplicate=True),
    dash.Output('app-location-norefresh', 'search', allow_duplicate=True),
    dash.Output('rd-runs-dropdown', 'options', allow_duplicate=True),
    dash.Input({'type': modal_cmp.BUTTON_OK_TYPE, 'index': 'rd-cancel-run-modal'}, 'n_clicks'),
    dash.State('rd-runs-dropdown', 'value'),
    prevent_initial_call=True
)
def cancel_run(n_clicks, run_idk):
    if n_clicks is None:
        return dash.no_update
    if dash.ctx.triggered_id is None:
        return dash.no_update
    run = tasks.RunItem.get(run_idk)
    if run is None:
        return dash.no_update

    run.set_status(
        status='cancelled',
        output={
            'message': 'Run was cancelled by user.'
        }
    )
    run.set_progress('complete', zero_duration=True)
    return [
        create_run_detail_rows(run),
        f'?run_id={run_idk}',
        get_run_dropdown_options(run.task_idf)
    ]