import dash
from dash import MATCH, Input, Output

AUTOCLEAR_ID_TYPE = 'cmp-autoclear-id-type'

dash.clientside_callback(
'''
async function (initial_text) {
    if (initial_text != '') {
        await new Promise(resolve => {
            setTimeout(() => {
                resolve('')
            }, 5000);
        })
        return ''
    }
    return dash_clientside.no_update
}
''',
Output({'type': AUTOCLEAR_ID_TYPE, 'index': MATCH}, 'children', allow_duplicate=True),
Input({'type': AUTOCLEAR_ID_TYPE, 'index': MATCH}, 'children'),
prevent_initial_call=True,
)