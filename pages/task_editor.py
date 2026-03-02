"""
Task Editor page for Orcha UI.
Provides a Monaco-like code editor for creating entities, sources, sinks,
transforms, and task functions using pure Python code.
The code is compiled, pickled, encrypted, and deployed to a target environment
via the agent.
"""
from __future__ import annotations

import json

import dash
from dash import Input, Output, State, dcc, html, callback, ALL, MATCH

from orcha_ui.credentials import PLOTLY_APP_PATH, ORCHA_AGENT_URLS
from orcha_ui.utils import agent_client


def can_read():
    return True


dash.register_page(
    __name__,
    name='Task Editor',
    path='/task_editor',
    image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/code.svg',
    title='Task Editor | Orcha',
    description='Create and deploy tasks, modules, and functions using Python code.',
    can_read_callback=can_read,
    can_edit_callback=lambda: True,
    order=600,
)


# ──────────────────────────────────────────────
# Code templates
# ──────────────────────────────────────────────

TEMPLATES = {
    'task': {
        'label': 'Task Function',
        'code': '''# Task function template
# 'secrets' dict is available with env secret values
# 'registry' provides access to registered modules
import pandas as pd

def task_function(task, run, config):
    """
    Your task function. This receives:
    - task: The TaskItem instance
    - run: The RunItem instance (has .config, .set_output(), etc.)
    - config: The config dict from the schedule set
    """
    print(f"Running task: {task.task_idk if task else 'unknown'}")

    # Example: use a registered source
    # source = registry.get_source('user_table_source')
    # if source:
    #     data = source.get()
    #     print(f"Got {len(data)} rows")

    # Example: use secrets
    # db_password = secrets.get('ORCHA_CORE_PASSWORD', '')

    # Example: update run output
    if run:
        run.set_output({'message': 'Task completed successfully'}, merge=True)
''',
    },
    'entity': {
        'label': 'Entity',
        'code': '''# Entity template
# Define 'result' as the object to be pickled and stored
from orcha.common.modules.postgres import PostgresEntity

result = PostgresEntity(
    module_idk='my_entity',
    description='My custom entity',
    user_name=secrets.get('DB_USER', 'postgres'),
    password=secrets.get('DB_PASSWORD', ''),
    host='orcha-db',
    port=5432,
    database_name='postgres',
)
''',
    },
    'source': {
        'label': 'Source',
        'code': '''# Source template
# Define 'result' as the object to be pickled and stored
from orcha.core.module_base import DatabaseSource

# You can reference entities from the registry
# entity = registry.get_entity('postgres')

result = DatabaseSource(
    module_idk='my_source',
    description='My custom source',
    data_entity=None,  # Set to an entity
    tables=[],
    query='SELECT 1',
)
''',
    },
    'sink': {
        'label': 'Sink',
        'code': '''# Sink template
# Define 'result' as the object to be pickled and stored
from orcha.core.module_base import DatabaseSink

result = DatabaseSink(
    module_idk='my_sink',
    description='My custom sink',
    data_entity=None,  # Set to an entity
    table=None,
    if_exists='append',
)
''',
    },
    'transform': {
        'label': 'Transform',
        'code': '''# Transform template
# Define 'result' as the object to be pickled and stored
import pandas as pd
from orcha.core.module_base import TransformBase

def my_transform_function(data: pd.DataFrame) -> pd.DataFrame:
    """Your transform logic here."""
    # Example: add a column
    data['processed'] = True
    return data

result = TransformBase(
    module_idk='my_transform',
    description='My custom transform',
    transform_func=my_transform_function,
    create_inputs=pd.DataFrame,
)
''',
    },
    'validation': {
        'label': 'Validation',
        'code': '''# Validation template
# Define 'result' as the object to be pickled and stored
import pandas as pd
from orcha.core.module_base import ValidationBase

def my_validation_function(data: pd.DataFrame, threshold: int) -> bool:
    """Your validation logic here."""
    return len(data) > threshold

result = ValidationBase(
    module_idk='my_validation',
    description='My custom validation',
    validate_func=my_validation_function,
    create_inputs=int,
)
''',
    },
}


layout = html.Div([
    # Interval fires once on page load to populate environments without blocking import
    dcc.Interval(id='te-env-loader', interval=500, max_intervals=1),

    html.H3('Task Editor', className='mb-3'),
    html.P('Create and deploy modules, transforms, and tasks using Python code.', className='text-muted'),

    html.Div(className='row mb-3', children=[
        html.Div(className='col-md-3', children=[
            html.Label('Target Environment', className='form-label'),
            dcc.Dropdown(
                id='te-env-dropdown',
                options=[],
                value=None,
                placeholder='Loading environments...',
            ),
        ]),
        html.Div(className='col-md-2', children=[
            html.Label('Type', className='form-label'),
            dcc.Dropdown(
                id='te-type-dropdown',
                options=[
                    {'label': v['label'], 'value': k}
                    for k, v in TEMPLATES.items()
                ],
                value='task',
            ),
        ]),
        html.Div(className='col-md-3', children=[
            html.Label('Name', className='form-label'),
            dcc.Input(
                id='te-name-input',
                type='text',
                placeholder='my_task',
                className='form-control',
            ),
        ]),
        html.Div(className='col-md-4', children=[
            html.Label('Description', className='form-label'),
            dcc.Input(
                id='te-desc-input',
                type='text',
                placeholder='Description of this module/task',
                className='form-control',
            ),
        ]),
    ]),

    # Task-specific fields (shown only for task type)
    html.Div(id='te-task-fields', className='row mb-3', children=[
        html.Div(className='col-md-3', children=[
            html.Label('Task ID', className='form-label'),
            dcc.Input(
                id='te-task-idk',
                type='text',
                placeholder='my_task_id',
                className='form-control',
            ),
        ]),
        html.Div(className='col-md-3', children=[
            html.Label('Thread Group', className='form-label'),
            dcc.Input(
                id='te-thread-group',
                type='text',
                value='pickle_tasks',
                className='form-control',
            ),
        ]),
        html.Div(className='col-md-3', children=[
            html.Label('Cron Schedule', className='form-label'),
            dcc.Input(
                id='te-cron-schedule',
                type='text',
                placeholder='*/5 * * * *',
                className='form-control',
            ),
        ]),
        html.Div(className='col-md-3', children=[
            html.Label('Tags (comma-separated)', className='form-label'),
            dcc.Input(
                id='te-tags',
                type='text',
                placeholder='etl, pickle',
                className='form-control',
            ),
        ]),
    ]),

    # Code editor using Monaco via textarea (Monaco loaded via JS asset)
    html.Div(className='row mb-3', children=[
        html.Div(className='col-12', children=[
            html.Label('Python Code', className='form-label'),
            dcc.Textarea(
                id='te-code-editor',
                style={
                    'width': '100%',
                    'height': '500px',
                    'fontFamily': 'monospace',
                    'fontSize': '14px',
                    'backgroundColor': '#1e1e1e',
                    'color': '#d4d4d4',
                    'padding': '16px',
                    'border': '1px solid #333',
                    'borderRadius': '4px',
                    'tabSize': '4',
                    'resize': 'vertical',
                },
                value=TEMPLATES['task']['code'],
            ),
        ]),
    ]),

    # Action buttons
    html.Div(className='row mb-3', children=[
        html.Div(className='col-auto', children=[
            html.Button(
                '🚀 Deploy',
                id='te-btn-deploy',
                className='btn btn-success me-2',
            ),
        ]),
        html.Div(className='col-auto', children=[
            html.Button(
                '⚠️ Error Check',
                id='te-btn-check',
                className='btn btn-warning me-2',
            ),
        ]),
        html.Div(className='col-auto', children=[
            html.Button(
                '▶️ Test Code',
                id='te-btn-test',
                className='btn btn-info me-2',
            ),
        ]),
        html.Div(className='col-auto', children=[
            html.Button(
                '📋 Load Template',
                id='te-btn-template',
                className='btn btn-outline-secondary me-2',
            ),
        ]),
    ]),

    # Output area
    html.Div(id='te-output', className='mt-3'),
    html.Div(id='te-check-output', className='mt-2'),
    html.Div(id='te-test-output', className='mt-2'),

    # Existing pickles
    html.Hr(),
    html.H5('Deployed Pickles', className='mb-2'),
    html.Button('Refresh', id='te-btn-refresh-pickles', className='btn btn-sm btn-outline-primary mb-2'),
    html.Div(id='te-pickles-list'),
])


@callback(
    Output('te-code-editor', 'value'),
    Input('te-btn-template', 'n_clicks'),
    State('te-type-dropdown', 'value'),
    prevent_initial_call=True
)
def load_template(n_clicks, template_type):
    if template_type and template_type in TEMPLATES:
        return TEMPLATES[template_type]['code']
    return dash.no_update


@callback(
    Output('te-task-fields', 'style'),
    Input('te-type-dropdown', 'value'),
)
def toggle_task_fields(type_value):
    if type_value == 'task':
        return {'display': 'flex'}
    return {'display': 'none'}


@callback(
    Output('te-code-editor', 'value', allow_duplicate=True),
    Input('te-type-dropdown', 'value'),
    prevent_initial_call=True
)
def update_template_on_type_change(type_value):
    if type_value and type_value in TEMPLATES:
        return TEMPLATES[type_value]['code']
    return dash.no_update


@callback(
    Output('te-output', 'children'),
    Input('te-btn-deploy', 'n_clicks'),
    State('te-env-dropdown', 'value'),
    State('te-type-dropdown', 'value'),
    State('te-name-input', 'value'),
    State('te-desc-input', 'value'),
    State('te-code-editor', 'value'),
    State('te-task-idk', 'value'),
    State('te-thread-group', 'value'),
    State('te-cron-schedule', 'value'),
    State('te-tags', 'value'),
    prevent_initial_call=True,
)
def deploy_code(n_clicks, env_url, pickle_type, name, description, code,
                task_idk, thread_group, cron_schedule, tags):
    if not env_url:
        return html.Div('Please select a target environment.', className='alert alert-warning')
    if not name:
        return html.Div('Please enter a name.', className='alert alert-warning')
    if not code:
        return html.Div('Please enter code.', className='alert alert-warning')

    if pickle_type == 'task':
        if not task_idk:
            return html.Div('Please enter a Task ID.', className='alert alert-warning')

        schedule_sets = []
        if cron_schedule:
            schedule_sets.append({
                'cron_schedule': cron_schedule,
                'config': {},
            })

        tag_list = [t.strip() for t in (tags or '').split(',') if t.strip()]
        if not tag_list:
            tag_list = ['pickle']

        result = agent_client.deploy_pickle_task(
            agent_url=env_url,
            task_idk=task_idk,
            name=name,
            description=description or '',
            source_code=code,
            schedule_sets=schedule_sets,
            thread_group=thread_group or 'pickle_tasks',
            task_tags=tag_list,
            created_by='orcha_ui',
        )
    else:
        result = agent_client.deploy_pickle(
            agent_url=env_url,
            name=name,
            pickle_type=pickle_type,
            source_code=code,
            description=description or '',
            created_by='orcha_ui',
        )
    if result.get('status') == 'success':
        return html.Div([
            html.Span('✅ Deployed successfully! ', className='text-success'),
            html.Code(json.dumps(result, indent=2)),
        ], className='alert alert-success')
    else:
        error_detail = result.get('detail', json.dumps(result))
        return html.Div([
            html.Span('❌ Deployment failed: '),
            html.Pre(str(error_detail), className='text-danger'),
        ], className='alert alert-danger')


@callback(
    Output('te-pickles-list', 'children'),
    Input('te-btn-refresh-pickles', 'n_clicks'),
    State('te-env-dropdown', 'value'),
    prevent_initial_call=False,
)
def refresh_pickles(n_clicks, env_url):
    if not env_url:
        return html.P('Select an environment to view pickles.', className='text-muted')

    pickles = agent_client.get_pickles(env_url)
    if not pickles:
        return html.P('No pickles deployed.', className='text-muted')

    rows = []
    for p in pickles:
        rows.append(
            html.Tr([
                html.Td(p.get('name', '')),
                html.Td(html.Span(
                    p.get('pickle_type', ''),
                    className='badge bg-info'
                )),
                html.Td(p.get('description', '')[:60]),
                html.Td(p.get('module_idk', '') or ''),
                html.Td(p.get('created_at', '')[:19] if p.get('created_at') else ''),
                html.Td(
                    html.Button(
                        '🗑',
                        id={'type': 'te-btn-delete-pickle', 'index': p.get('pickle_idk', '')},
                        className='btn btn-sm btn-outline-danger',
                    )
                ),
                html.Td(
                    html.Button(
                        '📝 Edit',
                        id={'type': 'te-btn-edit-pickle', 'index': p.get('pickle_idk', '')},
                        className='btn btn-sm btn-outline-primary',
                        **{'data-source-code': p.get('source_code', '')},
                    ) if p.get('source_code') else None
                ),
            ])
        )

    return html.Table(className='table table-sm table-hover', children=[
        html.Thead(html.Tr([
            html.Th('Name'),
            html.Th('Type'),
            html.Th('Description'),
            html.Th('Module ID'),
            html.Th('Created'),
            html.Th(''),
            html.Th(''),
        ])),
        html.Tbody(rows),
    ])


@callback(
    Output('te-output', 'children', allow_duplicate=True),
    Input({'type': 'te-btn-delete-pickle', 'index': ALL}, 'n_clicks'),
    State('te-env-dropdown', 'value'),
    prevent_initial_call=True,
)
def delete_pickle_handler(n_clicks_list, env_url):
    ctx = dash.ctx
    if not ctx.triggered_id:
        return dash.no_update

    pickle_idk = ctx.triggered_id.get('index', '')
    if not pickle_idk or not env_url:
        return dash.no_update

    # Check if any button was actually clicked
    if not any(n for n in n_clicks_list if n):
        return dash.no_update

    result = agent_client.delete_pickle(env_url, pickle_idk)
    if result.get('status') == 'success':
        return html.Div(f'✅ Deleted {pickle_idk}', className='alert alert-success')
    else:
        return html.Div(f'❌ Failed to delete: {result}', className='alert alert-danger')


# ──────────────────────────────────────────────
# Deferred environment loading
# ──────────────────────────────────────────────

@callback(
    Output('te-env-dropdown', 'options'),
    Output('te-env-dropdown', 'value'),
    Input('te-env-loader', 'n_intervals'),
    prevent_initial_call=True,
)
def load_environments(n_intervals):
    """Load environment options after page load (not at import time)."""
    options = []
    first_value = None
    for url in ORCHA_AGENT_URLS:
        info = agent_client.get_agent_info(url)
        if info:
            options.append({
                'label': f"{info.get('environment_name', 'Unknown')} ({url})",
                'value': url,
            })
        else:
            options.append({
                'label': f"⚠ {url} (unreachable)",
                'value': url,
            })
        if first_value is None:
            first_value = url
    return options, first_value


# ──────────────────────────────────────────────
# Error Check / Test Code
# ──────────────────────────────────────────────

@callback(
    Output('te-check-output', 'children'),
    Input('te-btn-check', 'n_clicks'),
    State('te-env-dropdown', 'value'),
    State('te-type-dropdown', 'value'),
    State('te-code-editor', 'value'),
    prevent_initial_call=True,
)
def check_code_handler(n_clicks, env_url, pickle_type, code):
    """Ask the agent to compile-check the code without executing it."""
    if not env_url:
        return html.Div('Select a target environment first.', className='alert alert-warning')
    if not code:
        return html.Div('Enter some code first.', className='alert alert-warning')

    result = agent_client.check_code(env_url, code, pickle_type or 'task')

    if result.get('status') == 'success':
        return html.Div([
            html.Span('✅ '),
            html.Span(result.get('message', 'No errors found')),
        ], className='alert alert-success py-2')
    else:
        parts = [html.Span('❌ '), html.Strong(result.get('error_type', 'Error')), html.Span(': ')]
        parts.append(html.Span(result.get('message', 'Unknown error')))
        if result.get('line'):
            parts.append(html.Span(f' (line {result["line"]})', className='text-muted'))
        if result.get('traceback'):
            parts.append(html.Pre(result['traceback'], className='mt-2 small', style={'maxHeight': '200px', 'overflowY': 'auto'}))
        return html.Div(parts, className='alert alert-danger py-2')


@callback(
    Output('te-test-output', 'children'),
    Input('te-btn-test', 'n_clicks'),
    State('te-env-dropdown', 'value'),
    State('te-type-dropdown', 'value'),
    State('te-code-editor', 'value'),
    prevent_initial_call=True,
)
def test_code_handler(n_clicks, env_url, pickle_type, code):
    """Ask the agent to compile AND execute the code."""
    if not env_url:
        return html.Div('Select a target environment first.', className='alert alert-warning')
    if not code:
        return html.Div('Enter some code first.', className='alert alert-warning')

    result = agent_client.test_code(env_url, code, pickle_type or 'task')

    if result.get('status') == 'success':
        children: list = [html.Span('✅ '), html.Span(result.get('message', 'Executed OK'))]
        stdout = result.get('stdout', '')
        if stdout:
            children.append(html.Hr(className='my-1'))
            children.append(html.Pre(stdout, className='mb-0 small', style={'maxHeight': '300px', 'overflowY': 'auto'}))
        return html.Div(children, className='alert alert-success py-2')
    else:
        parts = [html.Span('❌ '), html.Strong(result.get('error_type', 'Error')), html.Span(': ')]
        parts.append(html.Span(result.get('message', 'Unknown error')))
        if result.get('line'):
            parts.append(html.Span(f' (line {result["line"]})', className='text-muted'))
        stdout = result.get('stdout', '')
        if stdout:
            parts.append(html.Hr(className='my-1'))
            parts.append(html.Pre(stdout, className='small', style={'maxHeight': '150px', 'overflowY': 'auto'}))
        if result.get('traceback'):
            parts.append(html.Pre(result['traceback'], className='mt-2 small text-danger', style={'maxHeight': '200px', 'overflowY': 'auto'}))
        return html.Div(parts, className='alert alert-danger py-2')
