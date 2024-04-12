from __future__ import annotations

import random
from typing import Sequence

import dash
from dash import MATCH, Input, Output, State, html
from dash.development.base_component import Component

COLLAPSIBLE_DIV_TYPE = 'cdc-collapsible-div-type'
COLLAPSIBLE_BTN_TYPE = 'cdc-collapsible-id-type'

def create_collapsible_container(
        children: Component | Sequence[Component],
        title: str,
        className: str
    ):
    index = str(random.randint(0, 999999999))
    return html.Div(
        children=[
            html.Div(className='row', children=[
                html.Div(className='col', children=[
                    html.H5(title)
                ]),
                html.Div(className='col-auto', children=[
                    html.Button(
                        'Collapse',
                        className='btn btn-secondary btn-sm',
                        id={
                            'type': COLLAPSIBLE_BTN_TYPE,
                            'index': index
                        }
                    )
                ]),
            ]),
            html.Div(
                className='row',
                id={
                    'type': COLLAPSIBLE_DIV_TYPE,
                    'index': index
                },
                children=children
            ),
        ],
        className=f'container-fluid {className}'
    )


dash.clientside_callback(
'''
async function(n_clicks, class_name) {
    if (n_clicks === undefined) {
        return dash_clientside.no_update;
    }
    if (class_name.includes('d-none')) {
        return [
            'Collapse',
            class_name.replace('d-none', '').trim().replace('  ', ' ')
        ];
    }
    return ['Expand', class_name + ' d-none'];
}
''',
Output({'type': COLLAPSIBLE_BTN_TYPE, 'index': MATCH}, 'children'),
Output({'type': COLLAPSIBLE_DIV_TYPE, 'index': MATCH}, 'className'),
Input({'type': COLLAPSIBLE_BTN_TYPE, 'index': MATCH}, 'n_clicks'),
State({'type': COLLAPSIBLE_DIV_TYPE, 'index': MATCH}, 'className'),
prevent_initial_call=True,
)