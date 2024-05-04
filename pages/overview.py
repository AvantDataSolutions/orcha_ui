from __future__ import annotations

from datetime import datetime as dt
from datetime import timedelta as td

import dash
from dash import Input, Output, dcc, html, State

from orcha.core import tasks, scheduler
from orcha_ui.components import run_slices_cmp, collapsible_div_cmp
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

def get_task_opacity(task: tasks.TaskItem):
    if task.status == 'enabled':
        return 'opacity-100'
    else:
        return 'opacity-50'


def create_tasks_overview(
        tasks: list[tasks.TaskItem],
        runs: dict[str, list[tasks.RunItem]]
    ):
    sched_last_active = scheduler.Scheduler.get_last_active()
    sched_loaded_at = scheduler.Scheduler.get_loaded_at()

    if sched_last_active is None:
        sched_last_active_text = 'Not Active'
        last_active_class = 'text-danger'
        uptime = 'Not Active'
    else:
        sched_last_active_text = str(dt.now() - sched_last_active)
        if sched_last_active > (dt.now() - td(minutes=2)):
            last_active_class = 'text-success'
        else:
            last_active_class = 'text-danger'

        if sched_loaded_at is None:
            uptime = 'Not Active'
            uptime_class = 'text-danger'
        else:
            uptime = str(dt.now() - sched_loaded_at)
            uptime_class = 'text-success'

    elements = [
        html.Div(className='col-auto pb-5 pe-5', children=[
            html.Div(className='row', children=[
                html.Div(className='col-auto', children=[
                    html.Div(
                        'Scheduler',
                        className='task-link h5'
                    )
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-auto', children=[
                    html.Span('Uptime'),
                ]),
                html.Div(className='col-auto', children=[
                    html.P(
                        uptime,
                        className=uptime_class
                    )
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-auto', children=[
                    html.Span('Last Active'),
                ]),
                html.Div(className='col-auto', children=[
                    html.P(
                        sched_last_active_text,
                        className=last_active_class
                    )
                ])
            ])
        ])
    ]
    for task in tasks:
        next_scheduled_text = task.get_next_scheduled_time()
        if task.status == 'disabled':
            next_scheduled_text = 'Disabled'
        elif task.status == 'inactive':
            next_scheduled_text = 'Inactive'

        task_active_class = 'text-success'
        if task.last_active < (dt.now() - td(minutes=2)):
            task_active_class = 'text-danger'

        # sort by scheduled time
        runs[task.task_idk].sort(key=lambda x: x.scheduled_time)
        # then get latest 5
        task_runs = runs[task.task_idk][-5:]
        active_runs = task.get_running_runs()
        base_classes = f'col-auto pb-5 pe-5 {get_task_opacity(task)}'
        elements.append(html.Div(className=base_classes, children=[
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
                    html.Span('Last Active'),
                ]),
                html.Div(className='col-auto', children=[
                    html.P(
                        str(dt.now() - task.last_active),
                        className=task_active_class
                    )
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-auto', children=[
                    html.Span('Last Scheduled'),
                ]),
                html.Div(className='col-auto', children=[
                    html.P(task_runs[-1:][0].scheduled_time if len(task_runs) > 0 else 'N/A')
                ])
            ]),
            html.Div(className='row', children=[
                html.Div(className='col-auto', children=[
                    html.Span('Next Scheduled'),
                ]),
                html.Div(className='col-auto', children=[
                    next_scheduled_text
                ])
            ]),
            run_slices_cmp.create_run_slice_row_bunched(
                title_div=html.Div(
                    'Active Runs',
                    style={'width': '100px'},
                ),
                task_runs=active_runs
            ),
            run_slices_cmp.create_run_slice_row_bunched(
                title_div=html.Div(
                    'Recent Runs',
                    style={'width': '100px', 'font-weight': 600},
                ),
                task_runs=task_runs
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
        html.Div(className=f'col-12 {get_task_opacity(task)}', children=[
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
                html.Span('Schedule Sets'),
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
            since=(dt.now() - td(days=10))
        )

    max_runs = 500
    max_per_task = 200
    runs_per_task: dict[str, int] = {}

    task_elements = []
    task_elements.append(create_tasks_overview(
        tasks=all_tasks,
        runs=task_runs
    ))

    total_runs = 0
    for _, runs in task_runs.items():
        total_runs += len(runs)

    if total_runs > max_runs:
        for task_idk, runs in task_runs.items():
            runs_per_task[task_idk] = min(int(len(runs) * max_runs / total_runs), max_per_task)

    # Order the tasks by workspace name
    all_tasks.sort(key=lambda x: x.task_metadata.get('workspace', 'Other'))
    all_workspaces = ['No Workspace']
    for task in all_tasks:
        workspace = task.task_metadata.get('workspace', 'No Workspace')
        if workspace not in all_workspaces:
            all_workspaces.append(workspace)

    for workspace in all_workspaces:
        workspace_tasks = [
            task for task in all_tasks
            if workspace == task.task_metadata.get('workspace', 'No Workspace')
        ]
        workspace_elements = [
            create_task_element(
                task=task,
                all_runs=task_runs[task.task_idk],
                display_count=runs_per_task.get(task.task_idk, 100),
                display_start_time=display_start_time,
                display_end_time=display_end_time
            )
            for task in workspace_tasks
        ]
        task_elements.append(collapsible_div_cmp.create_collapsible_container(
            children=workspace_elements,
            title=workspace,
            className='pt-3 pb-1 border-bottom'
        ))

    return task_elements

def layout(
        hours: int | None = None,
        types: str | None = None,
        workspaces: str | None = None,
        end_time: str | None = None,
    ):
    if end_time is None:
        display_end_time = dt.now()
    else:
        display_end_time = dt.strptime(end_time, '%Y-%m-%dT%H:%M')
    if hours is None:
        hours = 6

    if types is None:
        selected_types = ['all']
    else:
        selected_types = types.split(',')

    if workspaces is None:
        selected_workspaces = ['All Workspaces']
    else:
        selected_workspaces = workspaces.split(',')

    try:
        hours = int(hours)
        if hours < 1:
            hours = 1
    except ValueError:
        hours = 6

    task_elements = []

    return [
        html.Div(className='container-fluid', children=[
            dcc.Interval(id='ov-refresh-interval', interval=30000),
            html.Div(className='row content-row no-bkg py-0 mt-0 align-items-center', children=[
                html.Div(className='col-auto', children=[
                    html.Label('Workspaces', style={'font-weight': 'normal'}),
                    dcc.Dropdown(
                        style={'width': '200px'},
                        id='ov-dd-task-workspaces',
                        value=selected_workspaces,
                        multi=True
                    ),
                ]),
                html.Div(className='col-auto', children=[
                    html.Label('Task Types', style={'font-weight': 'normal'}),
                    dcc.Dropdown(
                        style={'width': '200px'},
                        id='ov-dd-task-types',
                        value=selected_types,
                        multi=True
                    ),
                ]),
                html.Div(className='col-auto', children=[
                    'End Time'
                ]),
                html.Div(className='col-auto', children=[
                    dcc.Input(
                        value=display_end_time.strftime('%Y-%m-%dT%H:%M'),
                        id='ov-end-time',
                        type='datetime-local'
                    ),
                ]),
                html.Div(className='col-auto g-0', children=[
                    html.Button(
                        'Now',
                        id='ov-button-now',
                        className='btn btn-primary btn-sm'
                    )
                ]),
                html.Div(className='col-auto', children=[
                    'View Hours'
                ]),
                html.Div(className='col-auto', children=[
                    dcc.Input(
                        value=hours,
                        id='ov-lookback-hours',
                        type='number',
                        style={'width': '80px'}
                    ),
                ]),
                # toggle to show disabled tasks
                html.Div(className='col-auto', children=[
                    'Show Disabled'
                ]),
                html.Div(className='col-auto', children=[
                    dcc.Checklist(
                        id='ov-show-disabled',
                        options=[{'label': '', 'value': 'show_disabled'}],
                        value=[]
                    )
                ]),
                # align a refresh button on the right
                html.Div(className='col', children=[
                    html.Div(className='row justify-content-end align-items-center', children=[
                        # add a last refreshed time
                        html.Div(className='col-auto g-0 pe-1 refresh-time', children=[
                            html.Div('Last Refreshed: ', className='row'),
                            html.Span(
                                dt.now().strftime('%Y-%m-%dT%H:%M'),
                                id='ov-last-refreshed',
                                className='row'
                            )
                        ]),
                        html.Div(className='col-auto g-0 refresh-time', children=[

                        ]),
                        html.Div(className='col-auto', children=[
                            html.Button(
                                'Refresh',
                                id='ov-refresh-button',
                                className='btn btn-primary btn-sm'
                            )
                        ])
                    ])
                ])
            ])
        ]),
        dcc.Loading(
            id='ov-loading-tasks',
            className='pt-5',
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

# clicking the now button removes the end time and sets it to now
# and removes it from the url too
@dash.callback(
    Output('ov-end-time', 'value', allow_duplicate=True),
    Output('app-location-norefresh', 'search', allow_duplicate=True),
    Input('ov-button-now', 'n_clicks'),
    State('ov-lookback-hours', 'value'),
    prevent_initial_call=True
)
def set_end_time_to_now(n_clicks, hours):
    if n_clicks is None:
        return dash.no_update
    return (
        dt.now().strftime('%Y-%m-%dT%H:%M'),
        f'?hours={str(hours)}'
    )

# whenever the end time is updated, if its not within the last 10 seconds
# then disable the refresh button and set the interval to 1 hour
@dash.callback(
    Output('ov-refresh-button', 'disabled'),
    Output('ov-refresh-interval', 'interval'),
    Input('ov-end-time', 'value'),
    prevent_initial_call=True
)
def update_refresh_button(end_time):
    if dt.strptime(end_time, '%Y-%m-%dT%H:%M') < (dt.now() - td(minutes=1)):
        return True, 3600000
    else:
        return False, 30000

# populate ov-task-list
@dash.callback(
    Output('ov-task-list', 'children', allow_duplicate=True),
    Output('ov-end-time', 'value'),
    Output('ov-last-refreshed', 'children'),
    Output('app-location-norefresh', 'search'),
    Output('ov-dd-task-types', 'options'),
    Output('ov-dd-task-workspaces', 'options'),
    Input('ov-end-time', 'value'),
    Input('ov-lookback-hours', 'value'),
    Input('ov-refresh-button', 'n_clicks'),
    Input('ov-show-disabled', 'value'),
    Input('ov-dd-task-types', 'value'),
    Input('ov-dd-task-workspaces', 'value'),
    Input('ov-refresh-interval', 'n_intervals'),
    prevent_initial_call=True,
)
def update_task_list(
        end_time, lookback_hours, refresh_clicks,
        show_disabled, task_types, workspaces, n_intervals
    ):
    if end_time is None:
        return dash.no_update
    if lookback_hours is None:
        lookback_hours = 6

    # if the end time isn't within the last 10 seconds, then add it to the url
    # as we're using a static end time
    if dt.strptime(end_time, '%Y-%m-%dT%H:%M') < (dt.now() - td(minutes=1)):
        endtime_str = f'&end_time={end_time}'
    else:
        endtime_str = ''

    display_end_time = dt.strptime(end_time, '%Y-%m-%dT%H:%M')
    display_start_time = display_end_time - td(hours=lookback_hours)

    all_tasks = tasks.TaskItem.get_all()
    all_tags:list[str] = ['all']
    for task in all_tasks:
        all_tags.extend(task.task_tags)

    # only keep tasks with the selected type
    filtered_tasks = set()
    if 'all' not in task_types:
        for task in all_tasks:
            for tag in task.task_tags:
                if tag in task_types:
                    filtered_tasks.add(task)
                    break
    else:
        filtered_tasks = all_tasks

    if not workspaces:
        workspaces = ['All Workspaces']

    all_workspaces = set()
    all_workspaces.add('All Workspaces')
    # Loop through all tasks to get all workspaces
    for task in all_tasks:
        workspace = task.task_metadata.get('workspace', 'No Workspace')
        if workspace not in all_workspaces:
            all_workspaces.add(workspace)
    # but need to further filter down the filtered tasks list
    if 'All Workspaces' not in workspaces:
        filtered_tasks = [
            task
            for task in filtered_tasks
            if task.task_metadata.get('workspace', 'No Workspace') in workspaces
        ]

    # We still want to show inactive tasks so the user can deal with them
    if 'show_disabled' not in show_disabled:
        filtered_tasks = [
            task
            for task in filtered_tasks
            if task.status != 'disabled' and task.status != 'deleted'
        ]

    # calculate the url string separately to make it easier to read
    hours_str = f'&hours={str(lookback_hours)}'
    types_str = '&types='
    types_str += ','.join(task_types) if task_types else 'all'
    workspace_str = '&workspaces='
    workspace_str += ','.join(workspaces) if workspaces else 'No Workspace'


    return (
        create_all_task_elements(
            all_tasks=list(filtered_tasks),
            display_start_time=display_start_time,
            display_end_time=display_end_time
        ),
        end_time,
        dt.now().strftime("%Y-%m-%dT%H:%M"),
        f'?{workspace_str}{types_str}{hours_str}{endtime_str}',
        [{'label': tag, 'value': tag} for tag in set(all_tags)],
        [{'label': ws, 'value': ws} for ws in all_workspaces]
    )
