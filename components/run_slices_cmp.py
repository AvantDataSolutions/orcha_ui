from __future__ import annotations

import json
from datetime import datetime as dt

import dash
from dash import ALL, Input, Output, html

from orcha.core import tasks

POPOVER_ID_TYPE = 'rcs-popover-run'


def get_run_slice_css_class(run: tasks.RunItem):
    if run.progress == 'queued':
        return 'run-queued'
    elif run.progress == 'running':
        return 'run-running'
    elif run.status == 'unstarted':
        return 'run-queued'
    elif run.status == 'success':
        return 'run-success'
    elif run.status == 'failed':
        return 'run-failed'
    elif run.status == 'warn':
        return 'run-warning'
    elif run.status == 'cancelled':
        return 'run-cancelled'
    else:
        return 'run-unknown'

def run_start_time(run: tasks.RunItem) -> str:
    if run.start_time is not None:
        return str(run.start_time).split('.')[0]
    return ''

def run_duration(run: tasks.RunItem) -> str:
    if run.end_time is not None and run.start_time is not None:
        duration = run.end_time - run.start_time
        return str(duration).split('.')[0]
    elif run.start_time is not None:
        duration = dt.now() - run.start_time
        return str(duration).split('.')[0]
    else:
        return 'Not started'

def create_run_slice_row_bunched(
        title_div: html.Div,
        task_runs: list[tasks.RunItem]
    ):
    """
    Creates a row of run slices for a task without spacing between runs
    based on time between runs. Useful for 'last 5 runs' etc.
    """
    return html.Div(className='row', children=[
        html.Div(className='col-auto', children=[
            title_div
        ]),
        html.Div(className='col-auto', children=[
            html.Div(
                id={
                    'type': POPOVER_ID_TYPE,
                    'index': run.run_idk
                },
                style={'width': '10px'},
                className=f'c-tooltip {get_run_slice_css_class(run)}',
                children=[
                    '-',
                    html.Div(className='c-tooltiptext', children=[
                        html.P([html.B('Scheduled: '), run.scheduled_time]),
                        html.P([html.B('Start: '), run_start_time(run)]),
                        html.P([html.B('Duration: '), run_duration(run)]),
                        html.P([html.B('Status: '), run.status]),
                        html.P([html.B('Config: '), json.dumps(run.config)]),
                    ])
                ]
            )
            for run in task_runs
        ])
    ])


def create_run_slice_row(
        task: tasks.TaskItem,
        all_runs: list[tasks.RunItem],
        display_start_time: dt,
        display_end_time: dt,
        display_count: int | None = None,
    ):

    def _get_run_width(run: tasks.RunItem):
        start_time = run.scheduled_time
        end_time = dt.utcnow()
        if run.start_time is not None:
            start_time = run.start_time
        if run.end_time is not None:
            end_time = run.end_time
        # if the run is done and we don't have an end time
        # then set duration to ~zero (e.g. end = start/scheduled time)
        elif run.status in [
                tasks.RunStatusEnum.warn.value,
                tasks.RunStatusEnum.failed.value,
                tasks.RunStatusEnum.success.value
            ]:
            if run.start_time is not None:
                end_time = run.start_time
            else:
                end_time = start_time

        run_duration = end_time - start_time
        run_duration_in_hours = run_duration.total_seconds() / 3600
        run_width_percentage = (run_duration_in_hours / display_hours) * 100
        # minimum of 1%
        if run_width_percentage < 1:
            return '0.5%'
        return f'{run_width_percentage}%'

    def _get_blank_width(start_time: dt, end_time: dt):
        if start_time and end_time:
            blank_duration = end_time - start_time
            blank_duration_in_hours = blank_duration.total_seconds() / 3600
            blank_width_percentage = (blank_duration_in_hours / display_hours) * 100
            return f'{blank_width_percentage}%'
        else:
            return '0.50%'

    display_hours = (display_end_time - display_start_time).total_seconds() / 3600

    all_runs.sort(key=lambda x: x.scheduled_time)

    if display_count:
        all_runs = all_runs[-display_count:]

    next_runs: dict[str, tasks.RunItem | None] = {}
    for index in range(len(all_runs)):
        run = all_runs[index]
        if index < len(all_runs) - 1:
            next_runs[run.run_idk] = all_runs[index+1]
        else:
            next_runs[run.run_idk] = None

    run_elements: list[html.Div] = []
    if task.task_idk not in run_elements:
        run_elements = []

    for run in all_runs:
        if len(run_elements) == 0 and len(all_runs) > 0:
            run_elements.append(html.Div(
                style={'width': _get_blank_width(
                    display_start_time, run.scheduled_time
                )}
            ))

        run_elements.append(html.Div(
            id={
                'type': POPOVER_ID_TYPE,
                'index': run.run_idk
            },
            style={'width': _get_run_width(run)},
            className=f'c-tooltip {get_run_slice_css_class(run)}',
            children=[
                '-',
                html.Div(className='c-tooltiptext', children=[
                    html.P([html.B('Scheduled: '), run.scheduled_time]),
                    html.P([html.B('Start: '), run_start_time(run)]),
                    html.P([html.B('Duration: '), run_duration(run)]),
                    html.P([html.B('Status: '), run.status]),
                    html.P([html.B('Config: '), json.dumps(run.config)]),
                ])
            ]
        ))
        # get the end time as either the next run if we have one
        # or the end of the display window
        next_run = next_runs[run.run_idk]
        if next_run is not None:
            end_time = next_run.scheduled_time
        else:
            end_time = display_end_time
        run_elements.append(
            html.Div(
                style={'width': _get_blank_width(
                    run.scheduled_time, end_time
                )}
            )
        )


    return html.Div(className='row', children=[
        html.Div(className='d-flex flex-row', children=[
            element
            for element in run_elements
        ])
    ])


# navigate to the run details page
@dash.callback(
    Output('app-location', 'pathname', allow_duplicate=True),
    Output('app-location', 'search', allow_duplicate=True),
    Input({'type': POPOVER_ID_TYPE, 'index': ALL}, 'n_clicks'),
    prevent_initial_call=True,
)
def navigate_to_run_details(n_clicks):
    if all([x is None for x in n_clicks]):
        return dash.no_update
    if dash.ctx.triggered_id is None:
        return dash.no_update
    run_id = dash.ctx.triggered_id['index']
    return [
        '/run_details',
        f'?run_id={run_id}'
    ]