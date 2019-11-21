import requests
import json
import config
import ordoro
import errors
import logging

logger = logging.getLogger('process-dropships')


def __get_url():
    return config.meyer_url


def __get_headers():
    return {
        'Authorization': config.meyer_auth,
        'Content-Type': 'application/json'
    }


def __post_create_order(order_data):
    return requests.post(
        f"{__get_url()}/CreateOrder",
        data=json.dumps(order_data),
        headers=__get_headers()
    ).json()


def __get_sales_tracking(order_id):
    return requests.get(
        f"{__get_url()}/SalesTracking",
        params={'OrderNumber': order_id},
        headers=__get_headers()
    ).json()


def submit_dropships():
    # Get all Dropship Ready orders associated with Meyer
    logger.info("Requesting all Meyer orders with 'Dropship Ready' from Ordoro...")
    robj = ordoro.get_dropship_ready_orders(ordoro.supplier_meyer_id)

    if robj['count'] < 1:
        logger.info("No orders returned. Nothing to do.")
        return

    orders = robj['order']

    logger.info(f"Found {robj['count']} to process.")

    # Loop through orders
    for order in orders:
        # Determine if order should be skipped based on what mode we're in
        if config.should_skip(order['order_number']):
            logger.info(f"Skipping order {order['order_number']}.")
            continue

        logger.info(f"Processing order {order['order_number']}...")

        shipinf = order['shipping_address']

        # Create dictionary for order information
        order_info = {
            'ShipMethod': 'UPS',
            'ShipToName': shipinf['name'],
            'ShipToAddress1': shipinf['street1'],
            'ShipToAddress2': shipinf['street2'],
            'ShipToCity': shipinf['city'],
            'ShipToState': shipinf['state'],
            'ShipToZipcode': shipinf['zip'],
            'ShipToPhone': shipinf['phone'],
            'CustPO': order['order_number'],
            'Items': []
        }

        # Meyer requires 3-char country code
        if shipinf['country'] == 'US':
            order_info['ShipToCountry'] = 'USA'
        else:
            order_info['ShipToCountry'] = shipinf['country']

        try:
            product_list = ordoro.get_product_list(order['lines'], ordoro.supplier_meyer_id)
            for product in product_list:
                order_info['Items'].append({'ItemNumber': product['sku'], 'Quantity': product['qty']})
        except errors.SupplierSKUNotFound as e:
            logger.error(f"Error: {e.msg()}")
            logger.error("Unable to parse product list. Skipping order.")
            continue

        # Send to Meyer
        logger.info(f"Sending order {order['order_number']} to Meyer...")
        logger.debug(f"{order_info}")

        rob = __post_create_order(order_info)
        logger.info(f"Parsing response from Meyer...")

        try:
            mey_orders = rob['Orders']
        except KeyError:
            logger.error("Error! Unexpected response from Meyer.")
            logger.error(f"Error code: {rob['errorCode']}")
            logger.error(f"Error message: {rob['errorMessage']}")

            logger.info("Removing 'Dropship Ready' tag...")
            ordoro.delete_tag_drop_ready(order['order_number'])

            logger.info("Adding 'Dropship Failed' tag...")
            ordoro.post_tag_drop_fail(order['order_number'])

            logger.info("Skipping order.")
            continue

        try:
            for mey_order in mey_orders:
                # Loop through responses and add order ids returned as comments
                logger.info(f"Adding Meyer order number {mey_order['OrderNumber']} as comment...")
                ordoro.post_comment(order['order_number'], f"[SR-MID]: {mey_order['OrderNumber']}")

            logger.info("Removing 'Dropship Ready' tag...")
            ordoro.delete_tag_drop_ready(order['order_number'])

            logger.info("Adding 'Awaiting Tracking' tag...")
            ordoro.post_tag_await_track(order['order_number'])
        except Exception as err:
            logger.info("Unable to parse response from Meyer. Error:")
            logger.info(f"{err}")
            logger.debug(f"{rob}")
            logger.info("Skipping.\n\r")
            continue

        logger.info(f"Done submitting order {order['order_number']}.\n\r")

    logger.info("Done submitting Meyer dropships.\n\r")


def get_tracking():
    # Get all Awaiting Tracking orders associate with Meyer
    logger.info("Requesting all Meyer orders with 'Awaiting Tracking' from Ordoro...")
    rob = ordoro.get_await_track_orders(ordoro.supplier_meyer_id)

    if rob['count'] < 1:
        logger.info("No orders returned. Nothing to do.")
        return

    orders = rob['order']

    logger.info(f"Found {rob['count']} to process.")

    # Loop through orders
    for order in orders:
        # Determine if order should be skipped based on what mode we're in
        if config.should_skip(order['order_number']):
            logger.info(f"Skipping order {order['order_number']}.\n\r")
            continue

        logger.info(f"Processing order {order['order_number']}...")

        # Keep track of how many tracking numbers we get back, 1st is added as official shipping method
        num_tracking = 1
        for comment in order['comments']:
            if '[SR-MID]' in comment['text']:
                mey_order_id = comment['text'].split(':')[1].strip()

                logger.info(f"Asking Meyer for tracking info on order {mey_order_id}...")
                tracking_info = __get_sales_tracking(mey_order_id)

                # If what we get back isn't a list, it means nothing was found
                if not isinstance(tracking_info, list):
                    logger.info(f"Could not retrieve tracking info: {tracking_info['errorMessage']}, skipping.\n\r")
                    continue

                logger.info(f"Tracking info retrieved, processing...")

                for tracking in tracking_info:
                    # If this is the first tracking number, we add it as the official shipping method
                    if num_tracking == 1:
                        shipping_data = dict()

                        shipping_data['tracking_number'] = tracking['TrackingNumber']
                        shipping_data['ship_date'] = order['order_placed_date']
                        shipping_data['carrier_name'] = 'UPS'
                        shipping_data['shipping_method'] = 'ground'
                        shipping_data['cost'] = 13

                        logger.info(f"Applying {shipping_data['tracking_number']} as official shipping method...")
                        ordoro.post_shipping_info(order['order_number'], shipping_data)

                        logger.info("Removing 'Awaiting Tracking' tag...")
                        ordoro.delete_tag_await_track(order['order_number'])

                        num_tracking = num_tracking + 1
                    else:
                        # If this is not the first tracking number, add it as a comment
                        tracking_number = tracking['TrackingNumber']

                        logger.info(f"Applying {tracking_number} in a comment...")
                        ordoro.post_comment(
                            order['order_number'],
                            f"Additional tracking information: "
                            f"Order ID: {mey_order_id} "
                            f"Tracking Number: {tracking_number}"
                        )
                        num_tracking = num_tracking + 1

                logger.info(f"Finished applying tracking for Meyer order {mey_order_id}.")

        logger.info(f"Finished applying tracking for Ordoro order {order['order_number']}.\n\r")

    logger.info("Finished getting tracking info from Meyer.\n\r")