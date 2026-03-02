"""
Environments page for Orcha UI.
Lists all connected environments via agents, showing their modules,
tasks, task runners, and secrets.
"""
import dash
from dash import Input, Output, callback, dcc, html

from orcha_ui.credentials import ORCHA_AGENT_URLS, PLOTLY_APP_PATH
from orcha_ui.utils import agent_client


def can_read():
    return True


dash.register_page(
    __name__,
    name='Environments',
    path='/environments',
    image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/server.svg',
    title='Environments | Orcha',
    description='View and manage connected environments and their modules.',
    can_read_callback=can_read,
    can_edit_callback=lambda: True,
    order=500,
)


def _create_module_card(module: dict, module_type: str) -> html.Div:
    """Create a card for a single module."""
    inputs = module.get('inputs', [])
    input_items = []
    for inp in inputs:
        val_display = ''
        if 'current_value' in inp and inp['current_value'] is not None:
            cv = inp['current_value']
            if isinstance(cv, str) and len(cv) > 60:
                cv = cv[:60] + '...'
            val_display = f' = {cv}'

        input_items.append(
            html.Div(className='row small ps-3', children=[
                html.Span([
                    html.Code(inp['name'], className='text-primary'),
                    html.Span(f': {inp["type"]}', className='text-muted'),
                    html.Span(f'{val_display}', className='text-secondary'),
                    html.Span(' (required)', className='text-danger') if inp.get('required') else None,
                ])
            ])
        )

    extra_info = []
    if module.get('query'):
        extra_info.append(html.Div(className='small mt-1', children=[
            html.Strong('Query: '),
            html.Code(module['query'][:100], className='text-muted'),
        ]))
    if module.get('table_name'):
        extra_info.append(html.Div(className='small', children=[
            html.Strong('Table: '),
            html.Code(module['table_name']),
        ]))
    if module.get('request_type'):
        extra_info.append(html.Div(className='small', children=[
            html.Strong('Method: '),
            html.Code(module['request_type']),
        ]))
    if module.get('tables') and isinstance(module['tables'], list):
        for t in module['tables'][:3]:
            if isinstance(t, dict):
                cols = ', '.join([c['name'] for c in t.get('columns', [])[:5]])
                extra_info.append(html.Div(className='small', children=[
                    html.Strong(f'Table {t.get("schema","")}.{t["name"]}: '),
                    html.Code(cols, className='text-muted'),
                ]))
            elif isinstance(t, str):
                extra_info.append(html.Span(t + ' ', className='badge bg-secondary me-1'))

    badge_class = {
        'entity': 'bg-info',
        'source': 'bg-success',
        'sink': 'bg-warning',
        'transform': 'bg-primary',
        'validation': 'bg-secondary',
    }.get(module_type, 'bg-secondary')

    return html.Div(className='card mb-2', children=[
        html.Div(className='card-body py-2', children=[
            html.Div(className='row align-items-center', children=[
                html.Div(className='col', children=[
                    html.Span(module.get('module_idk', 'unknown'), className='fw-bold'),
                    html.Span(
                        module.get('type', module_type),
                        className=f'badge {badge_class} ms-2'
                    ),
                ]),
            ]),
            html.P(module.get('description', ''), className='small text-muted mb-1'),
            *extra_info,
            html.Div(className='mt-1', children=input_items) if input_items else None,
        ])
    ])


def _create_environment_card(agent_url: str, info: dict | None, modules: dict | None,
                              tasks_data: dict | None, runners: dict | None,
                              secrets: list[str]) -> html.Div:
    """Create a card for a single environment."""
    if info is None:
        return html.Div(className='card mb-3 border-danger', children=[
            html.Div(className='card-body', children=[
                html.H5(f'❌ {agent_url}', className='card-title text-danger'),
                html.P('Agent unreachable', className='text-muted'),
            ])
        ])

    env_name = info.get('environment_name', 'Unknown')
    env_id = info.get('environment_id', 'unknown')
    status = info.get('status', 'unknown')

    # Modules section
    module_sections = []
    if modules:
        for category, label in [
            ('entities', 'Entities'), ('sources', 'Sources'),
            ('sinks', 'Sinks'), ('transforms', 'Transforms'),
            ('validations', 'Validations')
        ]:
            items = modules.get(category, [])
            if items:
                module_sections.append(
                    html.Div(className='mb-2', children=[
                        html.H6(f'{label} ({len(items)})', className='border-bottom pb-1'),
                        *[_create_module_card(m, category[:-1]) for m in items]
                    ])
                )

    # Tasks section
    task_elements = []
    if tasks_data and tasks_data.get('tasks'):
        for task in tasks_data['tasks']:
            schedules = task.get('schedule_sets', [])
            schedule_text = ', '.join([s.get('cron_schedule', '') for s in schedules]) or 'No schedules'

            status_class = {
                'enabled': 'text-success',
                'disabled': 'text-muted',
                'inactive': 'text-warning',
                'error': 'text-danger',
            }.get(task.get('status', ''), 'text-muted')

            task_elements.append(
                html.Div(className='row small border-bottom py-1', children=[
                    html.Div(className='col-3', children=[
                        html.Span(task['task_idk'], className='fw-bold'),
                    ]),
                    html.Div(className='col-2', children=[
                        html.Span(task.get('status', ''), className=status_class),
                    ]),
                    html.Div(className='col-2', children=[
                        html.Span(task.get('thread_group', '')),
                    ]),
                    html.Div(className='col-3', children=[
                        html.Code(schedule_text, className='small'),
                    ]),
                    html.Div(className='col-2', children=[
                        html.Span(', '.join(task.get('task_tags', [])), className='small text-muted'),
                    ]),
                ])
            )

    # Runner section
    runner_elements = []
    if runners and runners.get('runners'):
        for runner in runners['runners']:
            alive_class = 'text-success' if runner.get('thread_alive') else 'text-danger'
            runner_elements.append(
                html.Div(className='row small py-1', children=[
                    html.Div(className='col-4', children=[
                        html.Span(runner['thread_group'], className='fw-bold'),
                    ]),
                    html.Div(className='col-2', children=[
                        html.Span('Alive' if runner.get('thread_alive') else 'Dead', className=alive_class),
                    ]),
                    html.Div(className='col-6', children=[
                        html.Span(', '.join(runner.get('tasks', [])), className='small text-muted'),
                    ]),
                ])
            )
    if not runner_elements:
        runner_elements = [html.P('No task runners', className='text-muted small')]

    if not task_elements:
        task_elements = [html.P('No tasks', className='text-muted small')]

    if not module_sections:
        module_sections = [html.P('No modules loaded', className='text-muted small')]

    # Secrets section
    secret_elements = []
    if secrets:
        secret_elements = [
            html.Span(s, className='badge bg-dark me-1') for s in secrets
        ]
    if not secret_elements:
        secret_elements = [html.P('No secrets', className='text-muted small')]

    status_badge = 'bg-success' if status == 'running' else 'bg-danger'

    return html.Div(className='card mb-3', children=[
        html.Div(className='card-header d-flex justify-content-between align-items-center', children=[
            html.H5([
                html.Span(env_name, className='me-2'),
                html.Span(status, className=f'badge {status_badge}'),
            ], className='mb-0'),
            html.Small(f'{env_id} • {agent_url}', className='text-muted'),
        ]),
        html.Div(className='card-body', children=[
            # Task Runners
            html.Div(className='mb-3', children=[
                html.H6('Task Runners', className='border-bottom pb-1'),
                *runner_elements,
            ]),
            # Secrets
            html.Div(className='mb-3', children=[
                html.H6('Available Secrets', className='border-bottom pb-1'),
                html.Div(secret_elements) if secret_elements else html.P('No secrets', className='text-muted small'),
            ]),
            # Tasks
            html.Div(className='mb-3', children=[
                html.H6(f'Tasks ({len(task_elements)})', className='border-bottom pb-1'),
                *task_elements[:20],
            ]),
            # Modules
            html.Div(className='mb-3', children=[
                html.H6('Modules', className='border-bottom pb-1'),
                *module_sections,
            ]),
        ])
    ])


layout = html.Div([
    html.H3('Environments', className='mb-3'),
    html.P(
        'Connected environments and their modules, tasks, and runners.',
        className='text-muted'
    ),
    html.Button(
        'Refresh', id='env-btn-refresh',
        className='btn btn-primary btn-sm mb-3'
    ),
    dcc.Loading(
        id='env-loading',
        type='default',
        children=[
            html.Div(id='env-container', children=[
                html.P('Click Refresh to load environments.', className='text-muted')
            ])
        ]
    ),
])


@callback(
    Output('env-container', 'children'),
    Input('env-btn-refresh', 'n_clicks'),
    prevent_initial_call=False
)
def refresh_environments(n_clicks):
    cards = []
    for url in ORCHA_AGENT_URLS:
        info = agent_client.get_agent_info(url)
        modules = agent_client.get_modules(url) if info else None
        tasks_data = agent_client.get_tasks(url) if info else None
        runners = agent_client.get_task_runners(url) if info else None
        secrets = agent_client.get_secret_names(url) if info else None
        cards.append(
            _create_environment_card(url, info, modules, tasks_data, runners, secrets or [])
        )
    if not cards:
        return [html.P('No agent URLs configured. Set ORCHA_AGENT_URLS in .env', className='text-warning')]
    return cards
