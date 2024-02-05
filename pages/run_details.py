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
            duration = 'In Progress'

    return [
        html.Div(className='row', children=[
            html.Div(className='col', children=[
                html.H6('Run ID'),
                html.P(run.run_idk),
            ]),
            html.Div(className='col', children=[
                html.H6('Scheduled Time'),
                html.P(run.scheduled_time),
            ]),
            html.Div(className='col', children=[
                html.H6('Start Time'),
                html.P(run.start_time),
            ]),
            html.Div(className='col', children=[
                html.H6('End Time'),
                html.P(run.end_time),
            ]),
            # calculate duration
            html.Div(className='col', children=[
                html.H6('Duration'),
                html.P(duration),
            ]),
            html.Div(className='col', children=[
                html.H6('Last Active'),
                html.P(run.last_active),
            ]) if run.status == 'running' else '',
            html.Div(className='col', children=[
                html.H6('Status'),
                html.P(run.status),
            ]),
            html.Div(className='col', children=[
                html.H6('Type'),
                html.P(run.run_type),
            ]),
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
                html.Pre(json.dumps(run.output, indent=4)),
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


def layout(run_id: str = ''):

    run = tasks.RunItem.get_by_id(run_id)

    all_tasks = tasks.TaskItem.get_all()

    task_dropdown_value = run.task_idf if run else ''

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
                value='',
            )
        ])
    ])

    return [
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
    task = tasks.TaskItem.get(task_idk)
    runs = tasks.RunItem.get_all(
        task=task,
        since=dt.now() - td(days=2),
        schedule=None
    )[-50:]

    runs.sort(key=lambda r: r.scheduled_time, reverse=True)

    return [
        {
            'label': f'{r.scheduled_time} - {r.status}',
            'value': r.run_idk
        }
        for r in runs
    ]


# callback to update run details
@dash.callback(
    dash.Output('rd-col-run-details', 'children'),
    dash.Input('rd-runs-dropdown', 'value'),
)
def update_run_details(run_idk):
    if not run_idk:
        return dash.no_update
    run = tasks.RunItem.get_by_id(run_idk)
    if run is None:
        return dash.no_update
    return create_run_detail_rows(run)