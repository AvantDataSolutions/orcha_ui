import dash
from dash import MATCH, Input, Output, html

BUTTON_OK_TYPE = 'cmp-mdl-btn-ok'
BUTTON_CANCEL_KEY = 'cmp-mdl-btn-cancel'

def create_modal(
        inner_html: html.Div,
        id_index: str,
        outer_style: dict = {},
        show = True
    ):
    class_str = 'position-fixed top-50 start-50 translate-middle wf-root w-auto'
    if not show:
        class_str += ' d-none'

    outer_style['z-index'] = '1000'

    return html.Div(
        className=class_str,
        id={'type': 'cmp-mdl-div-root', 'index': id_index},
        style=outer_style,
        children=_create_outer_div(inner_html, id_index)
    )


def _create_outer_div(
        inner_html: html.Div,
        id_index: str
    ):
    return html.Div(className='container-fluid wf-outer', children=[
        html.Div(className='row', children=inner_html),
        html.Div(className='row justify-content-center pt-2', children=[
            html.Button('Ok', id={'type': BUTTON_OK_TYPE, 'index': id_index},
                className='btn btn-primary btn-sm',
                style={'width': '5rem'}
            ),
            html.Div(className='col-1'),
            html.Button('Cancel', id={'type': BUTTON_CANCEL_KEY, 'index': id_index},
                className='btn btn-secondary button-sm',
                style={'width': '5rem'}
            )
        ])
    ])


dash.clientside_callback(
'''
async function(ok_clicks, cancel_clicks) {
    if(ok_clicks == undefined && cancel_clicks == undefined) {
        return dash_clientside.no_update;
    }
    return 'd-none';
}
''',
Output({'type': 'cmp-mdl-div-root', 'index': MATCH}, 'className'),
Input({'type': BUTTON_OK_TYPE, 'index': MATCH}, 'n_clicks'),
Input({'type': BUTTON_CANCEL_KEY, 'index': MATCH}, 'n_clicks'),
)