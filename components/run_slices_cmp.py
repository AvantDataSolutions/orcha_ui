from __future__ import annotations

import json
from datetime import datetime as dt

from dash import html

from orcha.core import tasks


def get_run_slice_css_class(run: tasks.RunItem):
    if run.status == 'running':
        return 'run-running'
    elif run.status == 'success':
        return 'run-success'
    elif run.status == 'failed':
        return 'run-failed'
    elif run.status == 'queued':
        return 'run-queued'
    elif run.status == 'warning':
        return 'run-warning'
    else:
        return 'run-unknown'

def create_run_slice_row_bunched(
        task_runs: list[tasks.RunItem],
        slice_run_id_type: str,
    ):
    """
    Creates a row of run slices for a task without spacing between runs
    based on time between runs. Useful for 'last 5 runs' etc.
    """
    return html.Div(className='row', children=[
        html.Div(className='col-auto', children=[
            html.H6('Recent Runs')
        ]),
        html.Div(className='col-auto', children=[
            html.Div(
                id={
                    'type': slice_run_id_type,
                    'index': run.run_idk
                },
                style={'width': '10px'},
                className=f'c-tooltip {get_run_slice_css_class(run)}',
                children=[
                    '-',
                    html.Div(className='c-tooltiptext', children=[
                        html.P([html.B('Scheduled: '), run.scheduled_time]),
                        html.P([html.B('Start: '), run.start_time]),
                        html.P([html.B('End: '), run.end_time]),
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
                'type': 'ov-popover-run',
                'index': run.run_idk
            },
            style={'width': _get_run_width(run)},
            className=f'c-tooltip {get_run_slice_css_class(run)}',
            children=[
                '-',
                html.Div(className='c-tooltiptext', children=[
                    html.P([html.B('Scheduled: '), run.scheduled_time]),
                    html.P([html.B('Start: '), run.start_time]),
                    html.P([html.B('End: '), run.end_time]),
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