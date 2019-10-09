import xml.etree.ElementTree as ET
import requests
import config
import ordoro
import logging

username = config.taw_username
password = config.taw_password
url = config.taw_url

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
}

logger = logging.getLogger('process-dropships')


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


def submit_dropships():
    # GET ALL DROPSHIP READY ORDERS FROM ORDORO
    logger.info("Requesting all orders with 'Dropship Ready' from ordoro...")

    robj = ordoro.get_dropship_ready_orders(ordoro.supplier_taw_id)

    ord_orders = robj['order']

    logger.info(f"Found {len(ord_orders)} to process.\n\r\n\r")

    for eachOrder in ord_orders:
        # PARSE ORDER INFO FROM ORDORO ###
        parsed_order = dict()

        parsed_order['PONumber'] = eachOrder['order_number']

        # If we're in 'test' mode, only process orders with 'test' in the order number
        if config.test and 'test' not in parsed_order['PONumber'].lower():
            continue

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

        for eachLine in eachOrder['lines']:
            # Get the ordoro SKU
            ord_sku = eachLine['sku']

            # Get the product from ordoro
            rob = ordoro.get_product(ord_sku)

            # If it's a kit...
            if rob['is_kit_parent']:
                # Get kit quantity
                kit_qty = eachLine['quantity']

                # Loop through kit_components
                for eachComponent in rob['kit_components']:
                    # Get product object from ordoro for each product
                    component_obj = ordoro.get_product(eachComponent['sku'])

                    component_sku = ''
                    # Get the supplier sku of the product
                    for eachSupplier in component_obj['suppliers']:
                        if eachSupplier['id'] == ordoro.supplier_taw_id:
                            component_sku = eachSupplier['supplier_sku']

                    # Get the quantity of the product included in the kit
                    component_qty = eachComponent['quantity']

                    # quantity needed = quantity included in kit * kit quantity
                    needed_qty = int(component_qty * kit_qty)

                    # Add product to parsed_order['Parts']
                    parsed_order['Parts'].append({'PartNo': component_sku, 'Qty': needed_qty})
            else:
                # If not a kit, just add the supplier sku and quantity to the order
                taw_sku = ''

                # Loop through suppliers until you find TAW
                for eachSupplier in rob['suppliers']:
                    if eachSupplier['id'] == ordoro.supplier_taw_id:
                        taw_sku = eachSupplier['supplier_sku']

                parsed_order['Parts'].append({'PartNo': taw_sku, 'Qty': eachLine['quantity']})

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

        logger.info("Sending order to TAW...")
        logger.debug(f"{full_xml}")

        # SEND ORDER TO TAW
        r = post_submit_order(full_xml)

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

        logger.info(f"Done processing order number {parsed_order['PONumber']}")

    logger.info("Done submitting dropships!")