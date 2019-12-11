from flask import Flask, render_template # Lightweight web application framework
from poseidon import poseidon  # This is the python SDK for EnOS API.
import urllib.parse as parser  # The library to convert a dictionary into query string.
from datetime import timedelta, datetime

# The appliction AccessKey and SecretKey, you get it when you register an appliction
app_access_key = '0787eefe-d96c-4db6-a97c-c5ee16ce9a93'
app_secret_key = '7b12307f-4993-4ef3-8554-93c6cc0e3cb6'
# The api gateway address
api_gateway = 'https://apim-ppe1.envisioniot.com'

# This is the training OU Id in which we perform our experiment
training_orgId = 'o15724268424841'
# This is **Asset Tree Id** where batteries is mounted on, if you create your own asset tree,
# please replace it wit your own.
battery_provider_treeId = '50XiYXpx' 


# *****Private Section*****

# The following function is used to query assets under the specified parent node,
# by specifying orgId and treeId of the asset tree. 
# Refer to `Search Related Asset Node` API doc in our doc center.
# Args:
#   parentId: The parent asset Id under which the child assets is located
def _get_child_asset_list(parentId):
    url = api_gateway + '/asset-tree-service/v2.1/asset-nodes?'

    query_data = {
        'action': 'searchRelatedAsset',
        'treeId': battery_provider_treeId,
        'orgId': training_orgId }
    
    query_string = parser.urlencode(query_data)
    url += query_string

    data = {
        "filter": {
            "isChildOfAssetId": parentId # Specify the parent node Id for this query
        },
        "projection": ["assetId", "name.defaultValue"]
    }

    # poseidon.urlopen is the function defined in our SDK to send an API request.
    req = poseidon.urlopen(app_access_key, app_secret_key, url, data)
    return req

# The following function is used to query the specified asset information by specifying asset Id. 
# Refer to `Get Asset` API doc in our doc center.
# Args:
#   assetId: The asset Id you want to query
def _get_asset_info(assetId):
    url = api_gateway + '/asset-service/v2.1/assets?'

    query_data = {
        'action': 'get',
        'orgId': training_orgId,
        'assetId': assetId }
    
    query_string = parser.urlencode(query_data)
    url += query_string

    req = poseidon.urlopen(app_access_key, app_secret_key, url)
     
    return req

# The following function is used to get the latest reading of all measurement points of a specified device. 
# Refer to `Get Asset Latest Data` API doc in our doc center.
# Args:
#   assetIds: The asset Id to query, multiple assets can be sperated by comma.
#   measurepoints: The measure poin Ids to query, multiple measure points can be sperated by comma.
def _get_asset_latest_data(assetIds, measurepoints):
    url = api_gateway + '/tsdb-service/v2.0/latest?'

    query_data = {
        'orgId': training_orgId,
        'assetIds': assetIds,
        'measurepoints': measurepoints,
        'timeWindow': '',
        'accessKey': app_access_key }
    
    query_string = parser.urlencode(query_data)
    url += query_string

    req = poseidon.urlopen(app_access_key, app_secret_key, url)
    return req

# The following function is used to get the AI raw data of current, voltage and temperature
# for the specified battery device within a certain period.
# Refer to `Get Asset AI Raw Data` API doc in our doc center.
# Args:
#   assetId: The asset Id you want to query
#   startTime: Time of start sampling data, UTC time format or local time format
#   endTime: Time of end sampling data, UTC time format or local time format
def _get_asset_ai_raw_data(assetId, startTime, endTime):
    url = api_gateway + '/tsdb-service/v2.0/ai?'

    query_data = {
        'orgId': training_orgId,
        'modelId': '',
        'assetIds': assetId,
        'measurepoints': 'current,voltage,temp',
        'startTime': startTime,
        'endTime': endTime,
        'pageSize': '',
        'accessKey': app_access_key }
    
    query_string = parser.urlencode(query_data)
    url += query_string

    req = poseidon.urlopen(app_access_key, app_secret_key, url)

    # Arrange the returned data in array format
    time=[]
    current=[]
    voltage=[]
    temp=[]
    for item in req['data']['items']:
        if 'current' in item.keys():
            time.append(item['localtime'])
            current.append(item['current'])
        elif 'voltage' in item.keys():
            voltage.append(item['voltage'])
        elif 'temp' in item.keys():
            temp.append(item['temp'])
        else:
            pass

    # Assemble the response structure
    resp = {}
    resp['time'] = time
    resp['voltage'] = voltage
    resp['current'] = current
    resp['temp'] = temp

    return resp

# The following function is used to get the current active alerts from all the batteries 
# on the battery asset tree. 
# Refer to `Search Active Alerts` API doc in our doc center.
def _get_active_alerts():
    url = api_gateway + '/event-service/v2.1/active-alerts?'

    query_data = {
        'action': 'search',
        'orgId': training_orgId }
    
    query_string = parser.urlencode(query_data)
    url += query_string

    data = {
        "scope": {
            "treeId": battery_provider_treeId # Specify the asset tree from which to search active alerts
        },
        "pagination": {
            "pageNo": 1,
            "pageSize": 10
        }
    }

    req = poseidon.urlopen(app_access_key, app_secret_key, url, data)
    return req


# *****application logic*****

# Initialize hte web framework
app = Flask(__name__, template_folder='./', static_folder='./static/')

# The following @app.route decorator is used to register the web request handler

@app.route('/', endpoint='index')
def index():
    return render_template('battery.html')

@app.route('/battery/list/', endpoint='battery.list')
def list():
    parent_assetId = '0RmeXD6D'   # Change this to your battery's parent assentId
    results = _get_child_asset_list(parent_assetId)

    resp={}
    battery_list={}
    for item in results['data']:
        battery_list[item['name']['defaultValue']] = item['assetId']
    
    # Sort the asset list in ascending order by the aseet name
    sorted_list = [{'name': k, 'assetId': battery_list[k]} for k in sorted(battery_list.keys())]
    resp['batteries'] = sorted_list

    return resp

@app.route('/battery/asset/<assetId>', endpoint='battery.asset')
def asset(assetId):
    req = _get_asset_info(assetId)
    return req

@app.route('/battery/status/<assetId>', endpoint='battery.status')
def status(assetId):
    req = _get_asset_info(assetId)
    capacity = req['data']['attributes']['Capacity']

    health_level = 100
    accumulating_power = 0
 
    req = _get_asset_latest_data(assetId, 'health_level,accumulating_power')
    for item in req['data']['items']:
        if 'health_level' in item.keys():
            health_level = int(item['health_level'])/10
        elif 'accumulating_power' in item.keys():
            accumulating_power = int(item['accumulating_power'])
    
    # Calculate the remaining power peecentage of batteries
    remaining_power = "%.0f%%" % (100*accumulating_power/capacity)

    resp = {}
    resp['health_level'] = health_level
    resp['remaining_power'] = remaining_power

    return resp

@app.route('/battery/tsdb/<assetId>', endpoint='battery.tsdb')
def tsdb(assetId):
    endTime = datetime.now()
    startTime = endTime + timedelta(hours=-1)
    startTime = startTime.strftime(format='%Y-%m-%d %H:%M:%S')
    endTime = endTime.strftime(format='%Y-%m-%d %H:%M:%S')
    resp = _get_asset_ai_raw_data(assetId, startTime, endTime)
    return resp

@app.route('/battery/alerts/', endpoint='battery.alerts')
def alerts():
    req = _get_active_alerts()

    # Add asset name for each alert record
    for item in req['data']:
        result = _get_asset_info(item['assetId'])
        item['assetName'] = result['data']['name']['defaultValue']

    return req

# Main entrance
if __name__ == '__main__':
    app.debug = True
    app.run()