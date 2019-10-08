import requests
import json
import config

auth = config.ord_auth
url = config.ord_url
legacy_url = config.ord_legacy_url

headers = {
	'Authorization': auth,
	'Content-Type': 'application/json'
}

tag_drop_ready = {
	'id': '30093',
	'name': 'Dropship Ready'
}

tag_drop_fail = {
	'id': '30067',
	'name': 'Dropship Request Failed'
}

tag_await_track = {
	'id': '30068',
	'name': 'Awaiting Tracking'
}

supplier_taw_id = 44251


def get_orders(tag):
	params = {
		'tag': tag['name'],
		'limit': 100
	}
	return requests.get(f"{url}/order", params=params, headers=headers).json()


def get_dropship_ready_orders():
	return get_orders(tag_drop_ready)


def get_await_track_orders():
	return get_orders(tag_await_track)


def get_product(sku):
	return requests.get(f"{legacy_url}/product/{sku}/", headers=headers).json()


def post_tag(order_id, tag):
	return requests.post(f"{url}/order/{order_id}/tag/{tag['id']}", headers=headers)


def post_tag_drop_fail(order_id):
	return post_tag(order_id, tag_drop_fail)


def post_tag_await_track(order_id):
	return post_tag(order_id, tag_await_track)


def delete_tag(order_id, tag):
	return requests.delete(f"{url}/order/{order_id}/tag/{tag['id']}", headers=headers)


def delete_tag_drop_ready(order_id):
	return delete_tag(order_id, tag_drop_ready)


def delete_tag_await_track(order_id):
	return delete_tag(order_id, tag_await_track)


def post_comment(order_id, comment):
	data = json.dumps({'comment': comment})
	return requests.post(f"{url}/order/{order_id}/comment", headers=headers, data=data)


def post_shipping_info(order_id, data):
	return requests.post(f"{url}/order/{order_id}/shipping_info", data=json.dumps(data), headers=headers)