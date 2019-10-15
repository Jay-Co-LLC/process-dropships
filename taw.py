import xml.etree.ElementTree as ET
import requests
import datetime
import config
import ordoro
import logging

url = config.taw_url

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
}

logger = logging.getLogger('process-dropships')


def __post_submit_order(order_xml):
    return requests.post(
        f"{url}/SubmitOrder",
        data=f"UserID={__get_user()}&Password={__get_pass()}&OrderInfo={order_xml}",
        headers=headers)


def __post_get_tracking(PONumber):
    return requests.post(
        f"{url}/GetTrackingInfo",
        data=f"UserID={__get_user()}&Password={__get_pass()}&PONumber={PONumber}&OrderNumber=",
        headers=headers)


def __get_user():
    return config.taw_username


def __get_pass():
    return config.taw_password


def submit_dropships():
    # GET ALL DROPSHIP READY ORDERS FROM ORDORO
    logger.info("Requesting all TAW orders with 'Dropship Ready' from Ordoro...")

    robj = ordoro.get_dropship_ready_orders(ordoro.supplier_taw_id)

    ord_orders = robj['order']

    logger.info(f"Found {len(ord_orders)} to process.")

    for eachOrder in ord_orders:
        # Determine if order should be skipped based on what mode we're in
        if config.should_skip(eachOrder['order_number']):
            logger.info(f"Skipping order {eachOrder['order_number']}.")
            continue

        parsed_order = dict()

        parsed_order['PONumber'] = eachOrder['order_number']

        logger.info(f"Parsing {parsed_order['PONumber']}...")

        parsed_order['ReqDate'] = eachOrder['order_placed_date']

        parsed_order['ShipTo'] = {}
        parsed_order['ShipTo']['Name'] = eachOrder['shipping_address']['name']
        parsed_order['ShipTo']['Address1'] = eachOrder['shipping_address']['street1']
        parsed_order['ShipTo']['Address2'] = eachOrder['shipping_address']['street2']
        parsed_order['ShipTo']['City'] = eachOrder['shipping_address']['city']
        parsed_order['ShipTo']['State'] = eachOrder['shipping_address']['state']
        parsed_order['ShipTo']['Zip'] = eachOrder['shipping_address']['zip']
        parsed_order['ShipTo']['Country'] = eachOrder['shipping_address']['country']
        parsed_order['Parts'] = []

        product_list = ordoro.get_product_list(eachOrder['lines'], ordoro.supplier_taw_id)
        for product in product_list:
            parsed_order['Parts'].append({'PartNo': product['sku'], 'Qty': product['qty']})

        for eachTag in eachOrder['tags']:
            if eachTag['text'] == 'Signature Required':
                parsed_order['SpecialInstructions'] = 'Signature Required'

        # CONSTRUCT XML TO SEND TO TAW
        xml_pt1 = f"""<?xml version='1.0' ?>
                <Order>
                    <PONumber>{parsed_order['PONumber']}</PONumber>
                    <ReqDate>{parsed_order['ReqDate']}</ReqDate>
                    <ShipTo>				
                        <Name>{parsed_order['ShipTo']['Name']}</Name>		
                        <Address>{parsed_order['ShipTo']['Address1']}</Address>	
                        <Address>{parsed_order['ShipTo']['Address2']}</Address>
                        <City>{parsed_order['ShipTo']['City']}</City>
                        <State>{parsed_order['ShipTo']['State']}</State>
                        <Zip>{parsed_order['ShipTo']['Zip']}</Zip>
                        <Country>{parsed_order['ShipTo']['Country']}</Country>
                    </ShipTo>
        """

        xml_pt2 = ""

        for eachPart in parsed_order['Parts']:
            partno = eachPart['PartNo']
            qty = eachPart['Qty']
            xml_pt2 = f"{xml_pt2}<Part Number='{partno}'><Qty>{qty}</Qty></Part>\n\r"

        xml_pt3 = ""

        try:
            xml_pt3 = f"<SpecialInstructions>{parsed_order['SpecialInstructions']}</SpecialInstructions>"
        except:
            pass

        xml_pt4 = "</Order>"
        full_xml = f"{xml_pt1}{xml_pt2}{xml_pt3}{xml_pt4}"

        logger.info(f"Sending order {eachOrder['order_number']} to TAW...")
        logger.debug(f"{full_xml}")

        # SEND ORDER TO TAW
        try:
            r = __post_submit_order(full_xml)
        except Exception as err:
            logger.info(f"Unable to submit order to TAW. Error:")
            logger.info(f"{err}")
            logger.info("Skipping.\n\r")
            continue

        try:
            # PARSE XML RESPONSE FROM TAW
            tree = ET.ElementTree(ET.fromstring(r.content))
            root = tree.getroot()
            status = root.find('Status').text

            if status == "PASS":
                taw_order_id = root.find('Order').attrib['Id']
                logger.info(f"Order submitted successfully. Order ID: {taw_order_id}")

                logger.info(f"Adding 'Awaiting Tracking' tag...")
                ordoro.post_tag_await_track(parsed_order['PONumber'])
            else:
                logger.error(f"Status is not 'PASS': {status}")
                logger.error("Adding 'Dropship Failed' tag...")
                ordoro.post_tag_drop_fail(parsed_order['PONumber'])
        except Exception as err:
            logger.error(f"Error parsing response. Exception:"
                         f"\n\r{err}"
                         f"\n\rLast Response:"
                         f"\n\r{r.content.decode('UTF-8')}")

            logger.info("Adding 'Dropship Failed' tag...")
            ordoro.post_tag_drop_fail(parsed_order['PONumber'])

        logger.info("Removing 'Dropship Ready' tag...")
        ordoro.delete_tag_drop_ready(parsed_order['PONumber'])

        logger.info(f"Done processing order number {parsed_order['PONumber']}.\n\r")

    logger.info("Done submitting TAW dropships.\n\r")


def get_tracking():
    logger.info("Requesting all TAW orders with 'Awaiting Tracking' from Ordoro...")
    robj = ordoro.get_await_track_orders(ordoro.supplier_taw_id)

    ord_orders = robj['order']

    logger.info(f"Found {len(ord_orders)} to process.")

    for eachOrder in ord_orders:
        # Determine if order should be skipped based on what mode we're in
        if config.should_skip(eachOrder['order_number']):
            logger.info(f"Skipping order {eachOrder['order_number']}.\n\r")
            continue

        PONumber = eachOrder['order_number']

        logger.info(f"Processing order {PONumber}...")
        logger.info("Requesting tracking info from TAW...")

        # ASK FOR TRACKING INFO FROM TAW
        r = __post_get_tracking(PONumber)

        logger.debug(f"Response from TAW:\n\r{r.content.decode('UTF-8')}")

        try:
            # PARSE TRACKING INFO FROM TAW RESPONSE
            root = ET.ElementTree(ET.fromstring(r.content)).getroot()

            records = root.findall('Record')
            if len(records) < 1:
                logger.info("No records received, skipping.\n\r")
                continue

            logger.info(f"{len(records)} records received, checking for tracking info...")

            i = 1
            for record in records:
                # For the first record, actually add the tracking number as shipping info
                if i == 1:
                    data = dict()

                    data['tracking_number'] = record.find('TrackNum').text.strip()

                    # IF NO TRACKING NUMBER, LOG IT AND GO ON TO THE NEXT ONE
                    if data['tracking_number'] == "":
                        logger.info("No tracking number found. Skipping.\n\r")
                        continue

                    order_date_str = record.find('OrderDate').text
                    order_date_obj = datetime.datetime.strptime(order_date_str, '%m/%d/%Y')
                    order_date_str = order_date_obj.strftime('%Y-%m-%dT%H:%M:%S.000Z')

                    data['ship_date'] = order_date_str
                    data['carrier_name'] = record.find('Type').text.strip()

                    # IF NO VENDOR, LOG IT AND GO ON TO THE NEXT ONE
                    if data['carrier_name'] == "":
                        logger.info("No vendor found. Skipping.\n\r")
                        continue

                    data['shipping_method'] = "ground"
                    data['cost'] = 14

                    logger.info(f"Applying {data['tracking_number']} as official shipping method...")
                    logger.debug(f"{data}")

                    # SEND TRACKING INFO TO ORDORO
                    r = ordoro.post_shipping_info(PONumber, data)

                    logger.info(f"Removing 'Awaiting Tracking' tag...")
                    ordoro.delete_tag_await_track(PONumber)
                else:
                    taw_invoice_num = record.find('InvoiceNumber').text.strip()
                    tracking_number = record.find('TrackNum').text.strip()

                    if tracking_number == "":
                        continue

                    logger.info(f"Applying {tracking_number} in a comment...")
                    ordoro.post_comment(
                        PONumber,
                        f'Additional tracking information: '
                        f'\n\rTAW Order ID: {taw_invoice_num}'
                        f'\n\rTracking Number: {tracking_number}')
                i = i + 1

        except Exception as err:
            logger.error(
                f"[{PONumber}] Error parsing tracking info..."
                f"\n\rException:"
                f"\n\r{err}"
                f"\n\rLast Response:"
                f"\n\r{r.content.decode('UTF-8')}")

        logger.info(f"Finished applying tracking for Ordoro order {PONumber}.\n\r")

    logger.info(f"Finished getting tracking info from TAW.\n\r")
