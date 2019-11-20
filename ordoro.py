import requests
import json
import config
import errors

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
    data['notify_cart'] = True
    return requests.post(f"{url}/order/{order_id}/shipping_info", data=json.dumps(data), headers=__get_headers())


def get_supplier_sku(product_obj, supplier_id):
    return_sku = None
    for supplier in product_obj['suppliers']:
        if supplier['id'] == supplier_id:
            return_sku = supplier['supplier_sku']

    if return_sku is None:
        raise errors.SupplierSKUNotFound(product_obj['sku'])


def get_product_list(lines, supplier_id):
    return_list = []
    for line in lines:
        # Get the ordoro SKU
        ord_sku = line['sku']

        # Get the product from ordoro
        product = get_product(ord_sku)

        # If it's a kit...
        if product['is_kit_parent']:
            # Get kit quantity
            kit_qty = line['quantity']

            # Loop through kit_components
            for component in product['kit_components']:
                # Get product object from ordoro for each product
                component_obj = get_product(component['sku'])

                component_sku = get_supplier_sku(component_obj, supplier_id)

                # Get the quantity of the product included in the kit
                component_qty = component['quantity']

                # quantity needed = quantity included in kit * kit quantity
                needed_qty = int(component_qty * kit_qty)

                # Add product to parsed_order['Parts']
                return_list.append({'sku': component_sku, 'qty': needed_qty})
        else:
            # If not a kit, just add the supplier sku and quantity to the order
            sku = get_supplier_sku(product, supplier_id)
            return_list.append({'sku': sku, 'qty': line['quantity']})
    return return_list
