from __future__ import annotations

from datetime import datetime as dt, timedelta as td
from typing import Any

import dash
from dash import dcc, html, Input, Output

from orcha_ui.credentials import (
    PLOTLY_APP_PATH
)

# Use the log structure defined in orcha.utils.log
from orcha.utils.log import LogManager


def can_read():
    return True


dash.register_page(
    __name__,
    name='Logs',
    path='/logs',
    image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/log.png',
    title='Logs | Orcha',
    description='Explore application logs with date range and source filters.',
    can_read_callback=can_read,
    can_edit_callback=lambda: True,
    order=400,
)


def _fmt_dt(value: dt | str) -> str:
    if isinstance(value, str):
        return value
    return value.strftime('%Y-%m-%d %H:%M:%S')


def _parse_local_dt(val: str) -> dt:
    """Parse HTML datetime-local input (no seconds)."""
    return dt.strptime(val, '%Y-%m-%dT%H:%M')


def _seconds_only(val: dt | td) -> str:
    return str(val).split('.')[0]


def _get_distinct_sources() -> list[str]:
    return LogManager.get_distinct_sources()


def _query_logs(start_dt: dt, end_dt: dt, sources: list[str] | None, limit: int) -> list[dict[str, Any]]:
    # If 'All Sources' is present or sources is empty, query all logs
    if not sources or 'All Sources' in sources:
        filt_sources = None
    else:
        filt_sources = sources
    rows = LogManager.get_entries(
        limit=limit,
        sources=filt_sources,
        start=start_dt,
        end=end_dt,
    )
    result: list[dict[str, Any]] = []
    for r in rows:
        result.append({
            'created': getattr(r, 'created', None),
            'source': getattr(r, 'source', '') or '',
            'category': getattr(r, 'category', '') or '',
            'actor': getattr(r, 'actor', '') or '',
            'text': getattr(r, 'text', '') or '',
            'json': getattr(r, 'json', {}) or {},
        })
    return result


def _render_logs_table(entries: list[dict[str, Any]]):
    header = html.Thead(html.Tr([
        html.Th('Created'),
        html.Th('Source'),
        html.Th('Category'),
        html.Th('Actor'),
        html.Th('Text'),
        html.Th('JSON'),
    ]))
    rows = []
    for e in entries:
        # Lightly truncate large fields for readability
        text = e['text']
        text_disp = (text[:200] + '…') if isinstance(text, str) and len(text) > 200 else text
        js = e['json']
        js_str = '' if js is None else str(js)
        js_disp = (js_str[:200] + '…') if len(js_str) > 200 else js_str
        rows.append(html.Tr([
            html.Td(_fmt_dt(e['created'])),
            html.Td(e['source']),
            html.Td(e['category']),
            html.Td(e['actor']),
            html.Td(text_disp),
            html.Td(js_disp, className='font-monospace small'),
        ]))
    body = html.Tbody(rows)
    # Only the table scrolls, not the page
    return html.Div([
        html.Table([
            header,
            body,
        ], className='table table-striped table-sm mb-0'),
    ], style={
        'maxHeight': '80vh',
        'overflowY': 'auto',
        'width': '100%',
        'border': '1px solid #ddd',
        'background': '#fff',
        'padding': '0',
    })


def layout(hours: int | None = None, start: str | None = None, end: str | None = None, sources: str | None = None):
    # Defaults
    now = dt.now()
    if end is None:
        end_dt = now
    else:
        try:
            end_dt = _parse_local_dt(end)
        except Exception:
            end_dt = now

    if hours is None:
        hours = 6
    try:
        hours = int(hours)
        if hours < 1:
            hours = 1
    except Exception:
        hours = 6

    if start is None:
        start_dt = end_dt - td(hours=hours)
    else:
        try:
            start_dt = _parse_local_dt(start)
        except Exception:
            start_dt = end_dt - td(hours=hours)

    selected_sources = ['All Sources'] if sources is None else sources.split(',')

    src_options = [{'label': s, 'value': s} for s in (['All Sources'] + _get_distinct_sources())]

    return [
        html.Div(className='container-fluid', children=[
            dcc.Interval(id='lv-refresh-interval', interval=30000),
            html.Div(className='row content-row no-bkg py-0 mt-0 align-items-center', children=[
                html.Div(className='col-auto', children=[
                    html.Label('Sources', style={'font-weight': 'normal'}),
                    dcc.Dropdown(
                        style={'width': '240px'},
                        id='lv-dd-sources',
                        options=src_options,
                        value=selected_sources,
                        multi=True,
                        placeholder='Select sources…',
                    ),
                ]),
                html.Div(className='col-auto', children=['Start']),
                html.Div(className='col-auto', children=[
                    dcc.Input(
                        id='lv-start-time',
                        type='datetime-local',
                        value=start_dt.strftime('%Y-%m-%dT%H:%M'),
                    )
                ]),
                html.Div(className='col-auto', children=['End']),
                html.Div(className='col-auto', children=[
                    dcc.Input(
                        id='lv-end-time',
                        type='datetime-local',
                        value=end_dt.strftime('%Y-%m-%dT%H:%M'),
                    )
                ]),
                html.Div(className='col-auto g-0', children=[
                    html.Button('Now', id='lv-button-now', className='btn btn-primary btn-sm')
                ]),
                html.Div(className='col-auto', children=['Limit']),
                html.Div(className='col-auto', children=[
                    dcc.Input(id='lv-limit', type='number', value=100, style={'width': '90px'})
                ]),
                html.Div(className='col', children=[
                    html.Div(className='row justify-content-end align-items-center', children=[
                        html.Div(className='col-auto g-0 me-3 refresh-time', children=[
                            html.Div('Last Refreshed: ', className='row'),
                            html.Span(_seconds_only(dt.now()), id='lv-last-refreshed', className='row')
                        ]),
                        html.Div(className='col-auto', children=[
                            html.Button('Refresh', id='lv-refresh-button', className='btn btn-primary btn-sm')
                        ])
                    ])
                ])
            ])
        ]),
        dcc.Loading(
            id='lv-loading-logs',
            className='pt-3',
            type='default',
            children=[
                html.Div(className='container-fluid', id='lv-logs-container', children=[])
            ]
        )
    ]


@dash.callback(
    Output('lv-end-time', 'value', allow_duplicate=True),
    Input('lv-button-now', 'n_clicks'),
    prevent_initial_call=True,
)
def lv_set_end_time_to_now(n_clicks):
    if not n_clicks:
        return dash.no_update
    return dt.now().strftime('%Y-%m-%dT%H:%M')


@dash.callback(
    Output('lv-refresh-button', 'disabled'),
    Output('lv-refresh-interval', 'interval'),
    Input('lv-end-time', 'value'),
    prevent_initial_call=True,
)
def lv_update_refresh_behaviour(end_time):
    try:
        end_dt = _parse_local_dt(end_time)
    except Exception:
        end_dt = dt.now()
    if end_dt < (dt.now() - td(minutes=1)):
        # Stale end time -> disable auto refresh and button
        return True, 60 * 60 * 1000  # 1 hour
    else:
        return False, 30 * 1000  # 30s


@dash.callback(
    Output('lv-logs-container', 'children', allow_duplicate=True),
    Output('lv-last-refreshed', 'children'),
    Output('lv-dd-sources', 'options'),
    Output('lv-dd-sources', 'value'),
    Input('lv-start-time', 'value'),
    Input('lv-end-time', 'value'),
    Input('lv-dd-sources', 'value'),
    Input('lv-limit', 'value'),
    Input('lv-refresh-button', 'n_clicks'),
    Input('lv-refresh-interval', 'n_intervals'),
    prevent_initial_call='initial_duplicate'
)
def lv_update_logs(start_time, end_time, selected_sources, limit, _n_clicks, _n_intervals):
    # Validate and coerce inputs
    try:
        start_dt = _parse_local_dt(start_time)
    except Exception:
        start_dt = dt.now() - td(hours=6)
    try:
        end_dt = _parse_local_dt(end_time)
    except Exception:
        end_dt = dt.now()
    if end_dt < start_dt:
        start_dt, end_dt = end_dt - td(hours=1), end_dt

    try:
        limit_val = int(limit) if limit is not None else 500
        if limit_val < 1:
            limit_val = 1
        if limit_val > 5000:
            limit_val = 5000
    except Exception:
        limit_val = 500

    # Refresh source options each time to reflect new emitters
    all_sources = ['All Sources'] + _get_distinct_sources()
    src_options = [{'label': s, 'value': s} for s in all_sources]

    if not selected_sources or len(selected_sources) == 0:
        selected_sources = ['All Sources']

    # Automatically de-select 'All Sources' if we have another source for convenience
    if len(selected_sources) > 1 and 'All Sources' in selected_sources:
        selected_sources.remove('All Sources')

    # Query logs and render
    entries = _query_logs(start_dt, end_dt, selected_sources, limit_val)
    content = [
        html.Div(className='row content-row', children=[
            html.Div(className='col-12', children=[
                html.H4(f'Logs ({len(entries)})'),
                _render_logs_table(entries),
            ])
        ])
    ]

    return (
        content,
        _seconds_only(dt.now()),
        src_options,
        selected_sources,
    )
