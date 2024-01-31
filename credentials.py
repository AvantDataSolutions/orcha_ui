import os

IS_DEV = os.environ['IS_DEV']=='True'

SERVER_ROOT_URL=os.getenv('SERVER_ROOT_URL') or '/'

# None should default to the root path, '/'
PLOTLY_APP_PATH = os.getenv('PLOTLY_APP_PATH') or '/'

ORCHA_CORE_USER = os.environ['ORCHA_CORE_USER']
ORCHA_CORE_PASSWORD = os.environ['ORCHA_CORE_PASSWORD']
ORCHA_CORE_SERVER = os.environ['ORCHA_CORE_SERVER']
ORCHA_CORE_DB = os.environ['ORCHA_CORE_DB']