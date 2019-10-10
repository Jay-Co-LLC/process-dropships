import requests
import json
import config

url = config.ord_url
legacy_url = config.ord_legacy_url

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
supplier_meyer_id = 44359


def __get_headers():
	return {
		'Authorization': config.ord_auth,
		'Content-Type': 'application/json'
	}


def __get_orders(tag, supplier=None):
	params = {
		'tag': tag['name'],
		'limit': 100
	}
	if supplier:
		params['supplier'] = supplier
	return requests.get(f"{url}/order", params=params, headers=__get_headers()).json()


def get_dropship_ready_orders(supplier=None):
	return __get_orders(tag_drop_ready, supplier)


def get_await_track_orders(supplier=None):
	return __get_orders(tag_await_track, supplier)


def get_product(sku):
	return requests.get(f"{legacy_url}/product/{sku}/", headers=__get_headers()).json()


def __post_tag(order_id, tag):
	return requests.post(f"{url}/order/{order_id}/tag/{tag['id']}", headers=__get_headers())


def post_tag_drop_fail(order_id):
	return __post_tag(order_id, tag_drop_fail)


def post_tag_await_track(order_id):
	return __post_tag(order_id, tag_await_track)


def __delete_tag(order_id, tag):
	return requests.delete(f"{url}/order/{order_id}/tag/{tag['id']}", headers=__get_headers())


def delete_tag_drop_ready(order_id):
	return __delete_tag(order_id, tag_drop_ready)


def delete_tag_await_track(order_id):
	return __delete_tag(order_id, tag_await_track)


def post_comment(order_id, comment):
	data = json.dumps({'comment': comment})
	return requests.post(f"{url}/order/{order_id}/comment", headers=__get_headers(), data=data)


def post_shipping_info(order_id, data):
	return requests.post(f"{url}/order/{order_id}/shipping_info", data=json.dumps(data), headers=__get_headers())
