from __future__ import annotations

import json
from datetime import datetime as dt, timedelta as td
from typing import Any

import dash
from dash import Input, Output, State, dcc, html

from orcha_ui.credentials import PLOTLY_APP_PATH
from orcha.utils import kvdb


def can_read():
	return True


dash.register_page(
	__name__,
	name='KVDB Explorer',
	path='/kvdb',
	image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/database.svg',
	title='KVDB Explorer | Orcha',
	description='Inspect and edit KVDB entries.',
	can_read_callback=can_read,
	can_edit_callback=lambda: True,
	order=450,
)


def _seconds_only(value: dt) -> str:
	return str(value).split('.')[0]


def _format_expiry(expiry: dt | None) -> str:
	if expiry is None:
		return 'No expiry'
	return expiry.strftime('%Y-%m-%d %H:%M:%S')


def _format_ttl(ttl_seconds: int | None) -> str:
	if ttl_seconds is None:
		return 'No expiry'
	delta = td(seconds=abs(ttl_seconds))
	delta_str = str(delta).split('.')[0]
	if ttl_seconds >= 0:
		return f'in {delta_str}'
	return f'{delta_str} ago'


def _format_bytes(size_bytes: int) -> str:
	if size_bytes < 1024:
		return f'{size_bytes} B'
	if size_bytes < 1024 * 1024:
		return f'{size_bytes / 1024:.1f} KB'
	if size_bytes < 1024 * 1024 * 1024:
		return f'{size_bytes / (1024 * 1024):.1f} MB'
	return f'{size_bytes / (1024 * 1024 * 1024):.1f} GB'


def _trim_preview(text: str | None, length: int = 160) -> str:
	if not text:
		return ''
	return text if len(text) <= length else f'{text[:length]}…'


def _render_entries_table(entries: list[dict[str, Any]]):
	if len(entries) == 0:
		return html.Div(
			'No entries found for the current filters.',
			className='text-muted small'
        )

	header = html.Thead(html.Tr([
		html.Th('Key'),
		html.Th('Type'),
		html.Th('Size'),
		html.Th('Expiry'),
		html.Th('TTL'),
		html.Th('Preview'),
	]))

	rows = []
	for entry in entries:
		row_class = ''
		if entry.get('is_expired'):
			row_class = 'table-warning'
		preview = entry.get('value_preview') or ''
		if entry.get('load_error'):
			preview = f"Error: {entry['load_error']}"
			row_class = 'table-danger'
		rows.append(html.Tr([
			html.Td(entry['key']),
			html.Td(entry.get('type', 'unknown')),
			html.Td(_format_bytes(entry.get('size_bytes', 0))),
			html.Td(_format_expiry(entry.get('expiry'))),
			html.Td(_format_ttl(entry.get('ttl_seconds'))),
			html.Td(_trim_preview(preview), className='font-monospace small'),
		], className=row_class))

	return html.Div([
		html.Table([
			header,
			html.Tbody(rows)
		], className='table table-striped table-sm mb-0')
	], style={
		'maxHeight': '65vh',
		'overflowY': 'auto',
		'width': '100%',
		'border': '1px solid #ddd',
		'background': '#fff'
	})


def _stringify_value(value: Any) -> tuple[str, str]:
	if isinstance(value, (dict, list)):
		try:
			return json.dumps(value, indent=2, default=str), 'json'
		except TypeError:
			pass
	if isinstance(value, bool):
		return ('true' if value else 'false'), 'bool'
	if isinstance(value, int):
		return str(value), 'int'
	if isinstance(value, float):
		return str(value), 'float'
	if isinstance(value, str):
		return value, 'string'
	return repr(value), 'python'


def _parse_value(raw_value: str, mode: str) -> Any:
	if mode == 'json':
		return json.loads(raw_value)
	if mode == 'string':
		return raw_value
	if mode == 'int':
		return int(raw_value)
	if mode == 'float':
		return float(raw_value)
	if mode == 'bool':
		lowered = raw_value.strip().lower()
		if lowered in ['true', '1', 'yes', 'y', 'on']:
			return True
		if lowered in ['false', '0', 'no', 'n', 'off']:
			return False
		raise ValueError('Boolean value must be true/false, 1/0, yes/no, y/n, or on/off')

	raise ValueError(f'Unsupported value mode: {mode}')


def _find_entry_metadata(key: str) -> dict[str, Any] | None:
	key = key.strip()
	if not key:
		return None
	try:
		rows = kvdb.list_items(
			storage_type='postgres',
			search=key,
			limit=5,
			include_expired=True
		)
	except Exception:
		return None
	for row in rows:
		if row['key'] == key:
			return row
	return None


def _build_metadata_block(entry: dict[str, Any] | None):
	if entry is None:
		return [html.Div('No entry selected.', className='text-muted')]

	status = 'Expired' if entry.get('is_expired') else 'Active'
	ttl = _format_ttl(entry.get('ttl_seconds'))
	return [
		html.Div([
			html.Strong('Status: '),
			status
		]),
		html.Div([
			html.Strong('Type: '),
			entry.get('type', 'unknown')
		]),
		html.Div([
			html.Strong('Size: '),
			_format_bytes(entry.get('size_bytes', 0))
		]),
		html.Div([
			html.Strong('Expiry: '),
			_format_expiry(entry.get('expiry'))
		]),
		html.Div([
			html.Strong('TTL: '),
			ttl
		])
	]


def layout(key: str | None = None, search: str | None = None):
	selected_key = key or ''
	search_value = search or ''
	return [
		dcc.Store(id='kv-refresh-signal', data=0),
		html.Div(className='container-fluid', children=[
			dcc.Interval(id='kv-refresh-interval', interval=60000),
			html.Div(className='row content-row no-bkg py-0 mt-0 align-items-center', children=[
				html.Div(className='col-auto', children=[
					html.Label('Key Contains', style={'font-weight': 'normal'}),
					dcc.Input(
						id='kv-filter-search',
						type='text',
						value=search_value,
						placeholder='partial_key',
						style={'width': '220px'}
					)
				]),
				html.Div(className='col-auto', children=[
					dcc.Checklist(
						id='kv-filter-include-expired',
						options=[{'label': 'Include expired', 'value': 'include'}],
						value=[],
						inputStyle={'margin-right': '4px'}
					)
				]),
				html.Div(className='col-auto', children=['Limit']),
				html.Div(className='col-auto', children=[
					dcc.Input(id='kv-filter-limit', type='number', value=100, style={'width': '90px'})
				]),
				html.Div(className='col', children=[
					html.Div(className='row justify-content-end align-items-center', children=[
						html.Div(className='col-auto g-0 me-3 refresh-time', children=[
							html.Div('Last Refreshed: ', className='row'),
							html.Span(_seconds_only(dt.now()), id='kv-last-refreshed', className='row')
						]),
						html.Div(className='col-auto', children=[
							html.Button('Refresh', id='kv-refresh-button', className='btn btn-primary btn-sm')
						])
					])
				])
			])
		]),
		dcc.Loading(
			id='kv-loading',
			className='pt-3',
			type='default',
			children=[
				html.Div(className='container-fluid', children=[
					html.Div(className='row content-row', children=[
						html.Div(className='col-12 col-xxl-7', children=[
							html.H4('Stored Entries'),
							html.Div(id='kv-table-container', children=[
								html.Div('No data loaded yet.', className='text-muted small')
							])
						]),
						html.Div(className='col-12 col-xxl-5', children=[
							html.H4('Entry Editor'),
							html.Div(
								id='kv-status-banner',
								className='alert alert-info small',
								role='alert',
								children='Ready.'
							),
							html.Div(className='mb-2', children=[
								html.Label('Known Keys', className='form-label fw-normal'),
								dcc.Dropdown(
									id='kv-key-dropdown',
									options=[],
									value=selected_key if selected_key else None,
									placeholder='Select a key…'
								)
							]),
							html.Div(className='mb-2', children=[
								html.Label('Key', className='form-label fw-normal'),
								dcc.Input(
									id='kv-key-input',
									type='text',
									value=selected_key,
									placeholder='my_key_identifier',
									style={'width': '100%'}
								)
							]),
							html.Div(className='mb-2', children=[
								html.Label('Value', className='form-label fw-normal'),
								dcc.Textarea(
									id='kv-value-text',
									value='',
									placeholder='Enter JSON, text, numbers…',
									style={'width': '100%', 'height': '220px'},
								)
							]),
							html.Div(className='row mb-2', children=[
								html.Div(className='col-6', children=[
									html.Label('Value Format', className='form-label fw-normal'),
									dcc.Dropdown(
										id='kv-value-mode',
										value='json',
										clearable=False,
										options=[
											{'label': 'JSON', 'value': 'json'},
											{'label': 'String', 'value': 'string'},
											{'label': 'Integer', 'value': 'int'},
											{'label': 'Float', 'value': 'float'},
											{'label': 'Boolean', 'value': 'bool'},
										]
									)
								]),
								html.Div(className='col-6', children=[
									html.Label('Expiry (minutes)', className='form-label fw-normal'),
									dcc.Input(
										id='kv-expiry-minutes',
										type='number',
										value=5,
										style={'width': '100%'}
									)
								])
							]),
							html.Div(className='row g-2 mb-2', children=[
								html.Div(className='col-auto', children=[
									html.Button('Load', id='kv-load-button', className='btn btn-outline-secondary btn-sm')
								]),
								html.Div(className='col-auto', children=[
									html.Button('Save', id='kv-save-button', className='btn btn-primary btn-sm')
								]),
								html.Div(className='col-auto', children=[
									html.Button('Delete', id='kv-delete-button', className='btn btn-danger btn-sm')
								])
							]),
							html.Div(id='kv-selected-meta', className='small text-muted', children=[
								html.Div('No entry selected.', className='text-muted')
							])
						])
					])
				])
			]
		)
	]


@dash.callback(
	Output('kv-table-container', 'children', allow_duplicate=True),
	Output('kv-last-refreshed', 'children'),
	Output('kv-key-dropdown', 'options'),
	Output('kv-key-dropdown', 'value'),
	Input('kv-filter-search', 'value'),
	Input('kv-filter-limit', 'value'),
	Input('kv-filter-include-expired', 'value'),
	Input('kv-refresh-button', 'n_clicks'),
	Input('kv-refresh-interval', 'n_intervals'),
	Input('kv-refresh-signal', 'data'),
	State('kv-key-dropdown', 'value'),
	prevent_initial_call='initial_duplicate'
)
def kv_update_entries(
	    search_text, limit, include_expired_opts, _n_clicks,
        _n_intervals, _signal, current_value
    ):
	include_expired = 'include' in (include_expired_opts or [])
	try:
		limit_val = int(limit) if limit else 100
	except (TypeError, ValueError):
		limit_val = 100
	search_clean = (search_text or '').strip() or None
	try:
		entries = kvdb.list_items(
			storage_type='postgres',
			limit=limit_val,
			search=search_clean,
			include_expired=include_expired
		)
	except Exception as exc:
		return (
			html.Div(f'Unable to query kvdb entries: {exc}', className='text-danger small'),
			_seconds_only(dt.now()),
			[],
			None,
		)

	table = _render_entries_table(entries)
	options = [{'label': entry['key'], 'value': entry['key']} for entry in entries]
	dropdown_value = current_value if current_value in [o['value'] for o in options] else (options[0]['value'] if options else None)
	return (
		table,
		_seconds_only(dt.now()),
		options,
		dropdown_value,
	)


@dash.callback(
	Output('kv-key-input', 'value'),
	Input('kv-key-dropdown', 'value'),
	prevent_initial_call=True
)
def kv_sync_key_input(selected_key):
	return selected_key


@dash.callback(
	Output('kv-value-text', 'value'),
	Output('kv-value-mode', 'value'),
	Output('kv-selected-meta', 'children'),
	Output('kv-status-banner', 'children'),
	Output('kv-status-banner', 'className'),
	Output('kv-expiry-minutes', 'value'),
	Input('kv-load-button', 'n_clicks'),
	State('kv-key-input', 'value'),
	prevent_initial_call=True
)
def kv_load_entry(_n_clicks, key_value):
	key = (key_value or '').strip()
	if not key:
		return (
			dash.no_update,
			dash.no_update,
			dash.no_update,
			'Provide a key before loading.',
			'alert alert-warning small',
			dash.no_update
		)
	try:
		raw_value = kvdb.get(
			key=key,
			as_type=object,
			storage_type='postgres',
			no_key_return='exception'
		)
	except Exception as exc:
		return (
			'',
			dash.no_update,
			dash.no_update,
			f'Error loading key: {exc}',
			'alert alert-danger small',
			dash.no_update
		)

	value_text, value_mode = _stringify_value(raw_value)
	meta = _find_entry_metadata(key)
	ttl_minutes = None
	if meta and meta.get('ttl_seconds') is not None and meta['ttl_seconds'] > 0:
		ttl_minutes = round(meta['ttl_seconds'] / 60, 2)

	return (
		value_text,
		value_mode,
		_build_metadata_block(meta),
		'Entry loaded.',
		'alert alert-success small',
		ttl_minutes
	)


@dash.callback(
	Output('kv-status-banner', 'children', allow_duplicate=True),
	Output('kv-status-banner', 'className', allow_duplicate=True),
	Output('kv-refresh-signal', 'data', allow_duplicate=True),
	Output('kv-value-text', 'value', allow_duplicate=True),
	Output('kv-selected-meta', 'children', allow_duplicate=True),
	Input('kv-save-button', 'n_clicks'),
	Input('kv-delete-button', 'n_clicks'),
	State('kv-key-input', 'value'),
	State('kv-value-text', 'value'),
	State('kv-value-mode', 'value'),
	State('kv-expiry-minutes', 'value'),
	State('kv-refresh-signal', 'data'),
	prevent_initial_call=True
)
def kv_update_entry(
	    save_clicks, delete_clicks, key_value, value_text,
		value_mode, expiry_minutes, signal_value
    ):

	triggered = dash.ctx.triggered_id
	if triggered is None:
		return dash.no_update

	key = (key_value or '').strip()
	if not key:
		return (
			'A key is required for this action.',
			'alert alert-warning small',
			signal_value,
			dash.no_update,
			dash.no_update
		)

	if triggered == 'kv-delete-button':
		deleted = kvdb.delete(storage_type='postgres', key=key)
		if deleted:
			return (
				f'Entry "{key}" deleted.',
				'alert alert-success small',
				(signal_value or 0) + 1,
				'',
				_build_metadata_block(None)
			)
		return (
			f'Entry "{key}" was not found.',
			'alert alert-warning small',
			signal_value,
			dash.no_update,
			dash.no_update
		)

	if triggered == 'kv-save-button':
		try:
			parsed_value = _parse_value(value_text or '', value_mode or 'json')
		except ValueError as exc:
			return (
				f'Unable to parse value: {exc}',
				'alert alert-danger small',
				signal_value,
				dash.no_update,
				dash.no_update
			)

		expiry = None
		if expiry_minutes not in (None, ''):
			try:
				minutes_float = float(expiry_minutes)
			except ValueError:
				return (
					'Expiry minutes must be numeric.',
					'alert alert-danger small',
					signal_value,
					dash.no_update,
					dash.no_update
				)
			if minutes_float > 0:
				expiry = td(minutes=minutes_float)

		kvdb.store(
			storage_type='postgres',
			key=key,
			value=parsed_value,
			expiry=expiry
		)
		meta = _find_entry_metadata(key)
		return (
			f'Entry "{key}" saved.',
			'alert alert-success small',
			(signal_value or 0) + 1,
			dash.no_update,
			_build_metadata_block(meta)
		)

	return dash.no_update
