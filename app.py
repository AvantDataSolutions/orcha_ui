import os

import dash
from dash import Dash, Input, Output, dcc, html

from orcha.core import initialise

from .credentials import (
    ORCHA_CORE_DB,
    ORCHA_CORE_PASSWORD,
    ORCHA_CORE_SERVER,
    ORCHA_CORE_USER,
    PLOTLY_APP_PATH,
)

initialise(
    orcha_user=ORCHA_CORE_USER,
    orcha_pass=ORCHA_CORE_PASSWORD,
    orcha_server=ORCHA_CORE_SERVER,
    orcha_db=ORCHA_CORE_DB,
    application_name='orcha_ui'
)

app = Dash(__name__,
    title = 'Orcha',
    url_base_pathname=PLOTLY_APP_PATH,
    external_stylesheets=[
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    ],
    external_scripts=[
        'https://d3js.org/d3.v7.min.js',
    ],
    suppress_callback_exceptions=False,
    eager_loading=True,
    use_pages=True,
)

app._favicon = 'favicon.ico'

def get_nav_list(current_page: str = ''):
    link_list = []
    for page in dash.page_registry.values():
        page_class = ''
        if page['path'] == current_page:
            page_class = 'active'

        link_list.append(
            dcc.Link(
                className=f'row nav-card {page_class}', href=f"{PLOTLY_APP_PATH}{page['path']}".replace('//', '/'), children=[
                html.Img(src=page['image_url'], className='col-auto nav-icon'),
                html.Span(className='col nav-link', children=[
                    page['name'],
                ])
            ])
        )
    return link_list


app.layout = html.Div(className='container-fluid p-3 main-page', children=[
    dcc.Location(id='app-location', refresh='callback-nav'),
    dcc.Location(id='app-location-external', refresh=True),
    dcc.Location(id='app-location-norefresh', refresh=False),
    html.Div(className='row', children=[
        html.Div(className='col-auto', children=[
            dcc.Link([
                html.Img(
                    className='col-auto',
                    src=f'{PLOTLY_APP_PATH}assets/orcha-logo-round.png',
                    height='80px'
                ),
                html.Img(
                    className='col-auto',
                    src=f'{PLOTLY_APP_PATH}assets/orcha-font-black.png',
                    height='40px'
                ),
            ], className='column m-0 h4 home-link', href=f'{PLOTLY_APP_PATH}overview'),
            html.Div('-', id='app-h3-username', className='row m-0 pb-3 text-muted'),
            html.Div(className='row d-none', children=[
                dcc.Dropdown(id='in-page', options=[]),
            ]),
            html.Div(className='row', children=[
                html.Div(
                    id='app-nav-links',
                    className='col-12',
                    children=get_nav_list()
                ),
            ]),
        ]),
        html.Div(className='col overflow-auto', children=[
                html.Div(id='app-div-readonly', className='d-none', children=[
                    html.Div('read-only view'),
                ]),
                dash.page_container
            ]
        ),
    ])
])


@app.callback(
    Output('in-page', 'options'),
    Output('app-h3-username', 'children'),
    Output('app-nav-links', 'children'),
    Input('app-location', 'pathname'),
)
def process_auth(current_path):
    authed_email = 'user@orcha'
    if not authed_email:
        return [[], 'Not logged in', []]
    else:
        pages = dash.page_registry.values()
        options = [{
            'label': html.Div(page['name']),
            'value': page['name'],
        } for page in pages]

        return [
            options,
            f'User: {authed_email}',
            get_nav_list(current_path)
        ]


@app.callback(
    Output('app-div-readonly', 'className'),
    Output('in-page', 'value'),
    Output('app-location', 'pathname', allow_duplicate=True),
    Output('app-location', 'search', allow_duplicate=True),
    Input('in-page', 'value'),
    Input('app-location', 'pathname'),
    prevent_initial_call=True,
)
def do_navigate(selected_page, pathname):
    t_id = dash.ctx.triggered_id
    if 'in-page' in str(t_id):
        for page in dash.page_registry.values():
            if selected_page == page['name']:
                if page['relative_path'] == pathname:
                    return dash.no_update
                return [
                    dash.no_update,
                    dash.no_update,
                    page['relative_path'],
                    ''
                ]
    elif 'app-location' in str(t_id):
        banner_class = 'd-none'
        page_name = ''
        for page in dash.page_registry.values():
            if 'can_edit_callback' in page and pathname == page['relative_path']:
                page_name = page['name']
                if not page['can_edit_callback']():
                    banner_class = 'read-only-banner'
        return [
            banner_class,
            page_name,
            dash.no_update,
            dash.no_update
        ]
    return dash.no_update

if __name__ == '__main__':
    app.run(
        debug=os.environ['IS_DEV']=='True',
        host='0.0.0.0',
        dev_tools_props_check=False # to use input datetime-local
    )