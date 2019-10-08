import requests
import config

username = config.taw_username
password = config.taw_password
url = config.taw_url

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
}


def post_submit_order(order_xml):
    return requests.post(
        f"{url}/SubmitOrder",
        data=f"UserID={username}&Password={password}&OrderInfo={order_xml}",
        headers=headers)


def post_get_tracking(PONumber):
    return requests.post(
        f"{url}/GetTrackingInfo",
        data=f"UserID={username}&Password={password}&PONumber={PONumber}&OrderNumber=",
        headers=headers)

