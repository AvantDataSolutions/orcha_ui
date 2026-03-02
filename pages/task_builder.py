"""
WYSIWYG Task Builder for Orcha UI.
Provides a drag-and-drop style interface where users can:
- Pick sources, sinks, entities, transforms from the environment
- Drop them into a pipeline/function builder
- Configure each component's inputs
- Generate and deploy task functions

Uses the agent to introspect available modules and their input requirements.
"""
import json

import dash
from dash import ALL, Input, Output, State, callback, ctx, dcc, html

from orcha_ui.credentials import ORCHA_AGENT_URLS, PLOTLY_APP_PATH
from orcha_ui.utils import agent_client


def can_read():
    return True


dash.register_page(
    __name__,
    name='Task Builder',
    path='/task_builder',
    image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/puzzle.svg',
    title='Task Builder | Orcha',
    description='Visual drag-and-drop task builder for creating task pipelines.',
    can_read_callback=can_read,
    can_edit_callback=lambda: True,
    order=700,
)


############################################################################
# Helper functions
############################################################################

def _get_icon(module_type: str) -> str:
    return {
        'entity': '🗄️',
        'source': '📥',
        'sink': '📤',
        'transform': '🔄',
        'validation': '✅',
    }.get(module_type, '📦')


def _get_badge_class(module_type: str) -> str:
    return {
        'entity': 'bg-info',
        'source': 'bg-success',
        'sink': 'bg-warning text-dark',
        'transform': 'bg-primary',
        'validation': 'bg-secondary',
    }.get(module_type, 'bg-secondary')


def _create_palette_item(module: dict, module_type: str) -> html.Div:
    """Create a draggable palette item for a module."""
    module_idk = module.get('module_idk', 'unknown')
    base_type = module.get('base_type', module.get('type', module_type))

    return html.Div(
        className='palette-item card mb-1',
        draggable='true',
        style={
            'cursor': 'grab',
            'borderLeft': '4px solid',
            'borderLeftColor': {
                'source': '#28a745',
                'sink': '#ffc107',
                'transform': '#007bff',
                'validation': '#6c757d',
                'entity': '#17a2b8',
            }.get(module_type, '#6c757d'),
        },
        children=[
            html.Div(className='card-body py-1 px-2', children=[
                html.Div(className='d-flex align-items-center', children=[
                    html.Span(_get_icon(module_type), className='me-1'),
                    html.Span(module_idk, className='fw-bold small'),
                    html.Span(
                        base_type,
                        className=f'badge {_get_badge_class(module_type)} ms-auto small',
                        style={'fontSize': '0.65em'}
                    ),
                ]),
                html.Small(
                    module.get('description', '')[:50],
                    className='text-muted d-block',
                    style={'fontSize': '0.7em'}
                ),
                # Button to add to pipeline
                html.Button(
                    '+ Add',
                    id={
                        'type': 'tb-add-module',
                        'module_type': module_type,
                        'module_idk': module_idk,
                    },
                    className='btn btn-sm btn-outline-primary mt-1',
                    style={'fontSize': '0.7em', 'padding': '1px 8px'},
                ),
            ]),
        ],
    )


def _create_pipeline_step(step_index: int, step: dict) -> html.Div:
    """Create a visual pipeline step card with expandable inputs."""
    module_type = step.get('module_type', 'unknown')
    module_idk = step.get('module_idk', 'unknown')
    inputs = step.get('inputs', [])

    # Create input fields for this step
    input_fields = []
    for inp in inputs:
        inp_name = inp.get('name', '')
        inp_type = inp.get('type', 'str')
        inp_required = inp.get('required', False)
        inp_default = inp.get('default')
        is_secret = inp.get('is_secret', False)
        current_value = inp.get('current_value')
        is_code = inp.get('is_code', False)

        # Skip internal/complex fields
        if inp_name.startswith('_'):
            continue
        if inp_type in ('Callable', 'function') and not is_code:
            continue

        label_class = 'text-danger' if inp_required else 'text-muted'

        if is_code:
            input_fields.append(
                html.Div(className='mb-1', children=[
                    html.Label([
                        html.Code(inp_name, className='small'),
                        html.Span(f' ({inp_type})', className=f'small {label_class}'),
                    ]),
                    dcc.Textarea(
                        id={
                            'type': 'tb-step-input',
                            'step': step_index,
                            'field': inp_name,
                        },
                        value=str(current_value) if current_value else (inp_default or ''),
                        style={
                            'width': '100%',
                            'height': '100px',
                            'fontFamily': 'monospace',
                            'fontSize': '12px',
                        },
                    ),
                ])
            )
        elif is_secret:
            input_fields.append(
                html.Div(className='mb-1', children=[
                    html.Label([
                        html.Code(inp_name, className='small'),
                        html.Span(f' ({inp_type})', className=f'small {label_class}'),
                        html.Span(' 🔒', title='This field uses a secret'),
                    ]),
                    dcc.Dropdown(
                        id={
                            'type': 'tb-step-input',
                            'step': step_index,
                            'field': inp_name,
                        },
                        placeholder=f'Select secret for {inp_name}...',
                        options=[],  # Populated dynamically
                    ),
                ])
            )
        elif inp_type in ('int', 'float', 'number'):
            input_fields.append(
                html.Div(className='mb-1', children=[
                    html.Label([
                        html.Code(inp_name, className='small'),
                        html.Span(f' ({inp_type})', className=f'small {label_class}'),
                    ]),
                    dcc.Input(
                        id={
                            'type': 'tb-step-input',
                            'step': step_index,
                            'field': inp_name,
                        },
                        type='number',
                        value=current_value if current_value else (inp_default or ''),
                        className='form-control form-control-sm',
                    ),
                ])
            )
        elif inp_type == 'bool':
            input_fields.append(
                html.Div(className='mb-1', children=[
                    html.Label([
                        html.Code(inp_name, className='small'),
                        html.Span(f' ({inp_type})', className=f'small {label_class}'),
                    ]),
                    dcc.Dropdown(
                        id={
                            'type': 'tb-step-input',
                            'step': step_index,
                            'field': inp_name,
                        },
                        options=[
                            {'label': 'True', 'value': 'True'},
                            {'label': 'False', 'value': 'False'},
                        ],
                        value=str(current_value) if current_value is not None else (inp_default or 'False'),
                    ),
                ])
            )
        elif "Literal" in inp_type:
            # Parse literal options
            try:
                import re
                opts = re.findall(r"'([^']+)'", inp_type)
                input_fields.append(
                    html.Div(className='mb-1', children=[
                        html.Label([
                            html.Code(inp_name, className='small'),
                            html.Span(f' ({inp_type})', className=f'small {label_class}'),
                        ]),
                        dcc.Dropdown(
                            id={
                                'type': 'tb-step-input',
                                'step': step_index,
                                'field': inp_name,
                            },
                            options=[{'label': o, 'value': o} for o in opts],
                            value=current_value or inp_default or (opts[0] if opts else ''),
                        ),
                    ])
                )
            except Exception:
                pass
        else:
            input_fields.append(
                html.Div(className='mb-1', children=[
                    html.Label([
                        html.Code(inp_name, className='small'),
                        html.Span(f' ({inp_type})', className=f'small {label_class}'),
                    ]),
                    dcc.Input(
                        id={
                            'type': 'tb-step-input',
                            'step': step_index,
                            'field': inp_name,
                        },
                        type='text',
                        value=str(current_value) if current_value is not None else (inp_default or ''),
                        className='form-control form-control-sm',
                        placeholder=f'Enter {inp_name}...',
                    ),
                ])
            )

    border_color = {
        'source': '#28a745',
        'sink': '#ffc107',
        'transform': '#007bff',
        'validation': '#6c757d',
        'entity': '#17a2b8',
    }.get(module_type, '#6c757d')

    return html.Div(
        className='pipeline-step card mb-2',
        style={'borderLeft': f'4px solid {border_color}'},
        children=[
            html.Div(className='card-header py-1 d-flex justify-content-between align-items-center', children=[
                html.Div([
                    html.Span(f'{step_index + 1}. ', className='text-muted'),
                    html.Span(_get_icon(module_type), className='me-1'),
                    html.Span(module_idk, className='fw-bold'),
                    html.Span(
                        step.get('base_type', module_type),
                        className=f'badge {_get_badge_class(module_type)} ms-2',
                        style={'fontSize': '0.7em'}
                    ),
                ]),
                html.Div([
                    html.Button(
                        '↑', className='btn btn-sm btn-outline-secondary me-1',
                        id={'type': 'tb-move-up', 'index': step_index},
                        style={'padding': '0 4px'},
                    ),
                    html.Button(
                        '↓', className='btn btn-sm btn-outline-secondary me-1',
                        id={'type': 'tb-move-down', 'index': step_index},
                        style={'padding': '0 4px'},
                    ),
                    html.Button(
                        '✕', className='btn btn-sm btn-outline-danger',
                        id={'type': 'tb-remove-step', 'index': step_index},
                        style={'padding': '0 6px'},
                    ),
                ]),
            ]),
            html.Div(
                className='card-body py-2',
                children=input_fields if input_fields else [
                    html.P('No configurable inputs', className='text-muted small mb-0')
                ],
            ),
        ],
    )


def _generate_task_code(pipeline: list[dict], task_name: str, secret_names: list[str]) -> str:
    """Generate Python task function code from the pipeline definition."""
    lines = [
        '# Auto-generated task function from WYSIWYG builder',
        'import pandas as pd',
        'from orcha.core.tasks import TaskItem, RunItem',
        '',
        '',
        'def task_function(task, run, config):',
        f'    """Auto-generated task: {task_name}"""',
        '    print(f"Running task: {{task.task_idk if task else \'unknown\'}}")',
        '',
    ]

    for i, step in enumerate(pipeline):
        module_type = step.get('module_type', '')
        module_idk = step.get('module_idk', '')
        base_type = step.get('base_type', '')
        inputs = step.get('inputs', [])

        lines.append(f'    # Step {i + 1}: {module_type} - {module_idk}')

        if module_type == 'source':
            lines.append(f'    source_{i} = registry.get_source("{module_idk}")')
            lines.append(f'    if source_{i}:')
            lines.append(f'        data_{i} = source_{i}.get()')
            lines.append(f'        print(f"Source {module_idk}: {{len(data_{i})}} rows")')
            lines.append('')

        elif module_type == 'transform':
            # Find the last data variable
            data_var = f'data_{i-1}' if i > 0 else 'pd.DataFrame()'
            lines.append(f'    transform_{i} = registry.get_transform("{module_idk}")')
            lines.append(f'    if transform_{i}:')
            lines.append(f'        data_{i} = transform_{i}.transform(inputs={data_var})')
            lines.append(f'        print(f"Transform {module_idk}: {{len(data_{i})}} rows")')
            lines.append('')

        elif module_type == 'validation':
            data_var = f'data_{i-1}' if i > 0 else 'pd.DataFrame()'
            lines.append(f'    validation_{i} = registry.get_validation("{module_idk}")')
            lines.append('    # Validation inputs may need to be configured')
            lines.append(f'    # validation_{i}.validate(data={data_var}, inputs=...)')
            lines.append('')

        elif module_type == 'sink':
            data_var = f'data_{i-1}' if i > 0 else 'pd.DataFrame()'
            lines.append(f'    sink_{i} = registry.get_sink("{module_idk}")')
            lines.append(f'    if sink_{i}:')
            lines.append(f'        sink_{i}.save({data_var})')
            lines.append(f'        print(f"Sink {module_idk}: saved data")')
            lines.append('')

    lines.append('    if run:')
    lines.append('        run.set_output({"message": "Task completed successfully"}, merge=True)')
    lines.append('')

    return '\n'.join(lines)


############################################################################
# Layout
############################################################################

layout = html.Div([
    # Store for pipeline state
    dcc.Store(id='tb-pipeline-store', data=[]),
    dcc.Store(id='tb-modules-store', data={}),
    dcc.Store(id='tb-secrets-store', data=[]),
    # Interval fires once on page load to populate environments without blocking import
    dcc.Interval(id='tb-env-loader', interval=500, max_intervals=1),

    html.H3('Task Builder', className='mb-3'),
    html.P(
        'Build task pipelines visually by selecting modules from the palette '
        'and configuring their inputs.',
        className='text-muted'
    ),

    # Environment selector
    html.Div(className='row mb-3', children=[
        html.Div(className='col-md-4', children=[
            html.Label('Environment', className='form-label'),
            dcc.Dropdown(
                id='tb-env-dropdown',
                options=[],
                value=None,
                placeholder='Loading environments...',
            ),
        ]),
        html.Div(className='col-auto d-flex align-items-end', children=[
            html.Button(
                '🔄 Load Modules',
                id='tb-btn-load',
                className='btn btn-primary',
            ),
        ]),
    ]),

    # Main 2-column layout
    html.Div(className='row', children=[
        # Left column: Module Palette
        html.Div(className='col-md-3', children=[
            html.H5('Module Palette', className='mb-2'),
            html.Hr(className='mt-0'),

            # Search
            dcc.Input(
                id='tb-palette-search',
                type='text',
                placeholder='Filter modules...',
                className='form-control form-control-sm mb-2',
            ),

            # Module categories
            dcc.Loading(
                id='tb-palette-loading',
                children=[
                    html.Div(id='tb-palette-container', children=[
                        html.P('Load modules from an environment.', className='text-muted small')
                    ])
                ],
            ),
        ]),

        # Right column: Pipeline Builder
        html.Div(className='col-md-9', children=[
            html.Div(className='row mb-3', children=[
                html.Div(className='col', children=[
                    html.H5('Pipeline Builder', className='mb-0'),
                ]),
            ]),
            html.Hr(className='mt-0'),

            # Task config
            html.Div(className='row mb-3', children=[
                html.Div(className='col-md-3', children=[
                    html.Label('Task ID', className='form-label small'),
                    dcc.Input(
                        id='tb-task-idk',
                        type='text',
                        placeholder='my_wysiwyg_task',
                        className='form-control form-control-sm',
                    ),
                ]),
                html.Div(className='col-md-3', children=[
                    html.Label('Task Name', className='form-label small'),
                    dcc.Input(
                        id='tb-task-name',
                        type='text',
                        placeholder='My Task',
                        className='form-control form-control-sm',
                    ),
                ]),
                html.Div(className='col-md-3', children=[
                    html.Label('Cron Schedule', className='form-label small'),
                    dcc.Input(
                        id='tb-cron-schedule',
                        type='text',
                        placeholder='*/5 * * * *',
                        className='form-control form-control-sm',
                    ),
                ]),
                html.Div(className='col-md-3', children=[
                    html.Label('Thread Group', className='form-label small'),
                    dcc.Input(
                        id='tb-thread-group',
                        type='text',
                        value='pickle_tasks',
                        className='form-control form-control-sm',
                    ),
                ]),
            ]),

            # Pipeline steps
            html.Div(
                id='tb-pipeline-container',
                className='pipeline-container p-3',
                style={
                    'minHeight': '200px',
                    'backgroundColor': '#f8f9fa',
                    'border': '2px dashed #dee2e6',
                    'borderRadius': '8px',
                },
                children=[
                    html.P(
                        '📦 Add modules from the palette to build your pipeline',
                        className='text-muted text-center py-5',
                        id='tb-pipeline-placeholder'
                    )
                ],
            ),

            # Generated code preview
            html.Div(className='mt-3', children=[
                html.H6('Generated Code Preview'),
                html.Div(
                    id='tb-code-preview',
                    style={
                        'backgroundColor': '#1e1e1e',
                        'color': '#d4d4d4',
                        'padding': '16px',
                        'borderRadius': '4px',
                        'fontFamily': 'monospace',
                        'fontSize': '12px',
                        'maxHeight': '400px',
                        'overflowY': 'auto',
                        'whiteSpace': 'pre-wrap',
                    },
                ),
            ]),

            # Deploy button
            html.Div(className='mt-3', children=[
                html.Button(
                    '🚀 Deploy Task',
                    id='tb-btn-deploy',
                    className='btn btn-success me-2',
                ),
                html.Button(
                    '📋 Copy to Code Editor',
                    id='tb-btn-copy-to-editor',
                    className='btn btn-outline-secondary',
                ),
            ]),

            html.Div(id='tb-deploy-output', className='mt-3'),
        ]),
    ]),
])


############################################################################
# Callbacks
############################################################################

@callback(
    Output('tb-palette-container', 'children'),
    Output('tb-modules-store', 'data'),
    Output('tb-secrets-store', 'data'),
    Input('tb-btn-load', 'n_clicks'),
    State('tb-env-dropdown', 'value'),
    prevent_initial_call=True,
)
def load_modules(n_clicks, env_url):
    if not env_url:
        return [html.P('Select an environment', className='text-muted')], {}, []

    modules = agent_client.get_modules(env_url)
    secrets = agent_client.get_secret_names(env_url)

    if not modules:
        return [html.P('Failed to load modules', className='text-danger')], {}, secrets

    palette_sections = []
    for category, label in [
        ('sources', 'Sources'), ('sinks', 'Sinks'),
        ('transforms', 'Transforms'), ('validations', 'Validations'),
    ]:
        items = modules.get(category, [])
        if items:
            palette_sections.append(
                html.Div(className='mb-3', children=[
                    html.H6(f'{_get_icon(category[:-1])} {label} ({len(items)})',
                            className='border-bottom pb-1'),
                    *[_create_palette_item(m, category[:-1]) for m in items]
                ])
            )

    if not palette_sections:
        palette_sections = [html.P('No modules found', className='text-muted')]

    return palette_sections, modules, secrets


@callback(
    Output('tb-pipeline-store', 'data'),
    Input({'type': 'tb-add-module', 'module_type': ALL, 'module_idk': ALL}, 'n_clicks'),
    Input({'type': 'tb-remove-step', 'index': ALL}, 'n_clicks'),
    Input({'type': 'tb-move-up', 'index': ALL}, 'n_clicks'),
    Input({'type': 'tb-move-down', 'index': ALL}, 'n_clicks'),
    State('tb-pipeline-store', 'data'),
    State('tb-modules-store', 'data'),
    prevent_initial_call=True,
)
def update_pipeline(add_clicks, remove_clicks, move_up_clicks, move_down_clicks,
                    pipeline, modules_data):
    triggered = ctx.triggered_id
    if not triggered:
        return dash.no_update

    pipeline = pipeline or []

    if isinstance(triggered, dict):
        action = triggered.get('type', '')

        if action == 'tb-add-module':
            # Check if any button was actually clicked
            if not any(n for n in add_clicks if n):
                return dash.no_update

            module_type = triggered['module_type']
            module_idk = triggered['module_idk']

            # Find the module in the modules data
            category = module_type + 's'
            module_list = modules_data.get(category, [])
            module_info = None
            for m in module_list:
                if m.get('module_idk') == module_idk:
                    module_info = m
                    break

            inputs = module_info.get('inputs', []) if module_info else []
            new_step = {
                'module_type': module_type,
                'module_idk': module_idk,
                'base_type': module_info.get('base_type', '') if module_info else '',
                'inputs': inputs,
            }
            pipeline.append(new_step)

        elif action == 'tb-remove-step':
            if not any(n for n in remove_clicks if n):
                return dash.no_update
            index = triggered['index']
            if 0 <= index < len(pipeline):
                pipeline.pop(index)

        elif action == 'tb-move-up':
            if not any(n for n in move_up_clicks if n):
                return dash.no_update
            index = triggered['index']
            if 0 < index < len(pipeline):
                pipeline[index - 1], pipeline[index] = pipeline[index], pipeline[index - 1]

        elif action == 'tb-move-down':
            if not any(n for n in move_down_clicks if n):
                return dash.no_update
            index = triggered['index']
            if 0 <= index < len(pipeline) - 1:
                pipeline[index], pipeline[index + 1] = pipeline[index + 1], pipeline[index]

    return pipeline


@callback(
    Output('tb-pipeline-container', 'children'),
    Output('tb-code-preview', 'children'),
    Input('tb-pipeline-store', 'data'),
    State('tb-task-name', 'value'),
    State('tb-secrets-store', 'data'),
)
def render_pipeline(pipeline, task_name, secrets):
    pipeline = pipeline or []

    if not pipeline:
        return (
            [html.P(
                '📦 Add modules from the palette to build your pipeline',
                className='text-muted text-center py-5',
            )],
            '# No pipeline steps yet'
        )

    steps = [_create_pipeline_step(i, step) for i, step in enumerate(pipeline)]

    # Generate code
    code = _generate_task_code(pipeline, task_name or 'unnamed_task', secrets or [])

    return steps, code


@callback(
    Output('tb-deploy-output', 'children'),
    Input('tb-btn-deploy', 'n_clicks'),
    State('tb-env-dropdown', 'value'),
    State('tb-task-idk', 'value'),
    State('tb-task-name', 'value'),
    State('tb-cron-schedule', 'value'),
    State('tb-thread-group', 'value'),
    State('tb-pipeline-store', 'data'),
    State('tb-secrets-store', 'data'),
    prevent_initial_call=True,
)
def deploy_task(n_clicks, env_url, task_idk, task_name, cron_schedule,
                thread_group, pipeline, secrets):
    if not env_url:
        return html.Div('Select an environment', className='alert alert-warning')
    if not task_idk:
        return html.Div('Enter a Task ID', className='alert alert-warning')
    if not pipeline:
        return html.Div('Add at least one step to the pipeline', className='alert alert-warning')

    code = _generate_task_code(pipeline, task_name or task_idk, secrets or [])

    schedule_sets = []
    if cron_schedule:
        schedule_sets.append({
            'cron_schedule': cron_schedule,
            'config': {},
        })

    result = agent_client.deploy_pickle_task(
        agent_url=env_url,
        task_idk=task_idk,
        name=task_name or task_idk,
        description=f'WYSIWYG-built task with {len(pipeline)} steps',
        source_code=code,
        schedule_sets=schedule_sets,
        thread_group=thread_group or 'pickle_tasks',
        task_tags=['pickle', 'wysiwyg'],
        created_by='orcha_ui_builder',
    )

    if result.get('status') == 'success':
        return html.Div([
            html.Span('✅ Task deployed successfully! '),
            html.Code(json.dumps(result, indent=2)),
        ], className='alert alert-success')
    else:
        return html.Div([
            html.Span('❌ Deployment failed: '),
            html.Pre(str(result.get('detail', json.dumps(result))), className='text-danger'),
        ], className='alert alert-danger')


############################################################################
# Deferred environment loading
############################################################################

@callback(
    Output('tb-env-dropdown', 'options'),
    Output('tb-env-dropdown', 'value'),
    Input('tb-env-loader', 'n_intervals'),
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
