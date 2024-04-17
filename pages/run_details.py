from __future__ import annotations

import json
from datetime import datetime as dt
from datetime import timedelta as td

import dash
from dash import dcc, html

from orcha.core import tasks
from orcha_ui.credentials import PLOTLY_APP_PATH


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

    return [
        html.Div(className='row', children=[
            html.Div(className='col-auto me-2', children=[
                html.H6('Run ID'),
                html.P(run.run_idk),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Scheduled Time'),
                html.P(run.scheduled_time),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Start Time'),
                html.P(run.start_time),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('End Time'),
                html.P(run.end_time),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Duration'),
                html.P(duration),
            ]),
            html.Div(className='col-auto me-2', children=[
                html.H6('Last Active'),
                html.Div(
                    f'{run.last_active.strftime("%Y-%m-%d %H:%M:%S")} \
                    ({str(dt.now() - run.last_active)[:-7]})'
                ) if run.last_active else '',
            ]) if run.status == 'running' else '',
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
                    json.dumps(run.output, indent=4)[0:5000],
                    style={'white-space': 'pre-wrap'}
                ),
            ]),
        ]),
        html.Div(className='row pt-5', children=[
            html.Div(className='col-12', children=[
                html.H4('Parent Task', className='border-bottom pb-2'),
            ])
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
        ])
    ]


def get_run_dropdown_options(task_idk: str):
    task = tasks.TaskItem.get(task_idk)
    if task is None:
        return []
    runs = tasks.RunItem.get_all(
        task=task,
        since=dt.now() - td(days=2),
        schedule=None
    )

    runs.sort(key=lambda r: r.scheduled_time, reverse=True)
    runs = runs[:100]

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
    interval_ms = 60000
    if run is not None:
        if (run.status == tasks.RunStatus.QUEUED
                or run.status == tasks.RunStatus.RUNNING
            ):
            interval_ms = 3000

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
        html.Div(className='container-fluid', children=[
            top_dropdown_row,
        ]),
        html.Div(className='container-fluid', children=[
            html.Div(className='row content-row', children=[
                html.Div(className='col-12', children=[
                    html.H4('Run Details', className='border-bottom pb-2'),
                ]) if run else '',
                html.Div(
                    id='rd-col-run-details',
                    className='col-12',
                    children=create_run_detail_rows(run)
                )
            ]),
        ])
    ]

@dash.callback(
    dash.Output('rd-runs-dropdown', 'options'),
    dash.Input('rd-task-dropdown', 'value')
)
def update_runs_dropdown(task_idk):
    if not task_idk:
        return []
    return get_run_dropdown_options(task_idk)

# callback to update run details
@dash.callback(
    dash.Output('rd-col-run-details', 'children'),
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