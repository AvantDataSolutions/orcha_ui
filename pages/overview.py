from __future__ import annotations

from datetime import datetime as dt
from datetime import timedelta as td

import dash
from dash import ALL, Input, Output, dcc, html

from orcha.core import tasks
from orcha_ui.components import run_slices_cmp
from orcha_ui.credentials import PLOTLY_APP_PATH


def can_read():
    return True


dash.register_page(
    __name__,
    name='Overview',
    path='/overview',
    image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/home.svg',
    title='Overview | Orcha',
    description='Overview of current Orcha tasks and runs.',
    can_read_callback=can_read,
    can_edit_callback=lambda: True,
)


def create_tasks_overview(
        tasks: list[tasks.TaskItem],
        runs: dict[str, list[tasks.RunItem]]
    ):
    elements = []
    for task in tasks:
        task_runs = runs[task.task_idk][-5:]
        # sort by scheduled time
        task_runs.sort(key=lambda x: x.scheduled_time)
        elements.append(html.Div(className='col-auto', children=[
            html.Div(className='row', children=[
                html.Div(className='col-auto', children=[
                    dcc.Link(
                        task.name,
                        href=f'/task_details?task_id={task.task_idk}',
                        className='task-link h5'
                    )
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-auto', children=[
                    html.H6('Last Scheduled'),
                ]),
                html.Div(className='col-auto', children=[
                    html.P(task_runs[-1:][0].scheduled_time if len(task_runs) > 0 else 'N/A')
                ])
            ]),
            run_slices_cmp.create_run_slice_row_bunched(
                task_runs=task_runs,
                slice_run_id_type='ov-popover-run'
            ),
        ]))

    return html.Div(className='row content-row', children=[
        html.Div(className='col-12', children=[
            html.H4('Overview')
        ]),
        *elements
    ])

def create_task_element(
        task: tasks.TaskItem,
        all_runs: list[tasks.RunItem],
        display_start_time: dt,
        display_end_time: dt,
        display_count: int
    ):

    all_runs.sort(key=lambda x: x.scheduled_time)
    all_runs = [
        run
        for run in all_runs
        if (
            run.scheduled_time >= display_start_time
            and run.scheduled_time <= display_end_time
        )
    ]

    # want to count all runs for the display window
    all_run_count = len(all_runs)
    # and then limit to the display count
    all_runs = all_runs[-display_count:]

    return html.Div(className='row content-row', children=[
        html.Div(className='col-12', children=[
            html.Div(className='row', children=[
                dcc.Link(
                    task.name,
                    href=f'/task_details?task_id={task.task_idk}',
                    className='task-link h4'
                )
            ]),
            html.Div(className='row', children=[
                html.P(task.description)
            ]),
            html.Div(className='row', children=[
                html.H6('Schedule Sets'),
                *[
                    html.Div(s_set.cron_schedule, className='col-auto pe-4')
                    for s_set in task.schedule_sets
                ],
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-12', children=[
                    html.H5('Runs')
                ]),
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-12', children=[
                    f'Displaying {len(all_runs)} of {all_run_count} runs'
                ]),
            ]),
            run_slices_cmp.create_run_slice_row(
                task=task,
                all_runs=all_runs,
                display_count=display_count,
                display_start_time=display_start_time,
                display_end_time=display_end_time
            )
        ])
    ])

def create_all_task_elements(
        all_tasks: list[tasks.TaskItem],
        display_start_time: dt,
        display_end_time: dt
    ):
    task_runs: dict[str, list[tasks.RunItem]] = {}
    for task in all_tasks:
        task_runs[task.task_idk] = tasks.RunItem.get_all(
            task=task,
            schedule=None,
            since=(dt.utcnow() - td(days=10))
        )

    max_runs = 500
    runs_per_task = int(max_runs / len(task_runs))

    task_elements = []
    task_elements.append(create_tasks_overview(
        tasks=all_tasks,
        runs=task_runs
    ))

    for task in all_tasks:
        task_elements.append(create_task_element(
            task=task,
            all_runs=task_runs[task.task_idk],
            display_count=runs_per_task,
            display_start_time=display_start_time,
            display_end_time=display_end_time
        ))

    return task_elements

def layout():
    display_start_time = dt.utcnow() - td(hours=6)
    display_end_time = dt.utcnow()

    all_tasks = tasks.TaskItem.get_all()

    task_elements = create_all_task_elements(
        all_tasks=all_tasks,
        display_start_time=display_start_time,
        display_end_time=display_end_time
    )

    return [
        html.Div(className='container-fluid', children=[
            html.Div(className='row content-row no-bkg py-0 align-items-center', children=[
                html.Div(className='col-auto', children=[
                    'End Time:'
                ]),
                html.Div(className='col-auto', children=[
                    dcc.Input(
                        value=display_end_time.strftime('%Y-%m-%dT%H:%M'),
                        id='ov-end-time',
                        type='datetime-local'
                    ),
                ]),
                html.Div(className='col-auto', children=[
                    'View Hours:'
                ]),
                html.Div(className='col-auto', children=[
                    dcc.Input(
                        value=6,
                        id='ov-lookback-hours',
                        type='number'
                    ),
                ]),
                # align a refresh button on the right
                html.Div(className='col', children=[
                    html.Div(className='row justify-content-end align-items-center', children=[
                        # add a last refreshed time
                        html.Div(className='col-auto g-0 pe-1 refresh-time', children=[
                            'Last Refreshed:'
                        ]),
                        html.Div(className='col-auto g-0 refresh-time', children=[
                            html.Span(
                                dt.utcnow().strftime('%Y-%m-%dT%H:%M'),
                                id='ov-last-refreshed',
                                className=''
                            )
                        ]),
                        html.Div(className='col-auto', children=[
                            html.Button(
                                'Refresh',
                                id='ov-refresh-button',
                                className='btn btn-primary'
                            )
                        ])
                    ])
                ])
            ])
        ]),
        dcc.Loading(
            id='ov-loading-tasks',
            children=[
                html.Div(
                    className='container-fluid',
                    id='ov-task-list',
                    children=task_elements
                )
            ],
            type='default'
        )

    ]

# populate ov-task-list
@dash.callback(
    Output('ov-task-list', 'children', allow_duplicate=True),
    Output('ov-end-time', 'value'),
    Output('ov-last-refreshed', 'children'),
    Input('ov-end-time', 'value'),
    Input('ov-lookback-hours', 'value'),
    Input('ov-refresh-button', 'n_clicks'),
    prevent_initial_call=True,
)
def update_task_list(end_time, lookback_hours, refresh_clicks):
    if end_time is None:
        return dash.no_update
    if lookback_hours is None:
        lookback_hours = 6

    if dash.ctx.triggered_id == 'ov-refresh-button':
        end_time = dt.utcnow().strftime('%Y-%m-%dT%H:%M')

    display_end_time = dt.strptime(end_time, '%Y-%m-%dT%H:%M')
    display_start_time = display_end_time - td(hours=lookback_hours)

    all_tasks = tasks.TaskItem.get_all()

    return (
        create_all_task_elements(
            all_tasks=all_tasks,
            display_start_time=display_start_time,
            display_end_time=display_end_time
        ),
        dt.utcnow().strftime('%Y-%m-%dT%H:%M'),
        end_time
    )



# navigate to the run details page
@dash.callback(
    Output('app-location', 'pathname', allow_duplicate=True),
    Input({'type': 'ov-popover-run', 'index': ALL}, 'n_clicks'),
    prevent_initial_call=True,
)
def navigate_to_run_details(n_clicks):
    if all([x is None for x in n_clicks]):
        return dash.no_update
    if dash.ctx.triggered_id is None:
        return dash.no_update
    run_id = dash.ctx.triggered_id['index']
    return f'/run_details?run_id={run_id}'

