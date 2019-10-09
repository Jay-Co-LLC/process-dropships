import datetime
import logging
import config as cfg
import ordoro
import taw

log_file = f"LOG-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
logger = logging.getLogger('process-dropships')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler(log_file))
logger.addHandler(logging.StreamHandler())


def submit_dropships():
    taw.submit_dropships()


def get_tracking():
    logger.info("Requesting all orders with 'Awaiting Tracking' from ordoro...")
    robj = ordoro.get_await_track_orders()

    ord_orders = robj['order']

    logger.info(f"Found {len(ord_orders)} to process.")

    for eachOrder in ord_orders:
        PONumber = eachOrder['order_number']

        # If in 'test' mode, only process orders with 'test' in the order number
        if cfg.test and 'test' not in PONumber.lower():
            continue

        logger.info(f"\n\r---- {PONumber} ----")
        logger.info("Requesting tracking info from TAW...")

        # ASK FOR TRACKING INFO FROM TAW
        r = taw.post_get_tracking(PONumber)

        logger.debug(f"Response from TAW:\n\r{r.content.decode('UTF-8')}")

        try:
            # PARSE TRACKING INFO FROM TAW RESPONSE
            root = ET.ElementTree(ET.fromstring(r.content)).getroot()

            records = root.findall('Record')
            if len(records) < 1:
                logger.info("No records received, skipping.")
                continue

            logger.info("Response received, checking...")

            i = 1
            for record in root.findall('Record'):
                # For the first record, actually add the tracking number as shipping info
                if i == 1:
                    data = {}

                    order_date_str = record.find('OrderDate').text
                    order_date_obj = datetime.datetime.strptime(order_date_str, '%m/%d/%Y')
                    order_date_str = order_date_obj.strftime('%Y-%m-%dT%H:%M:%S.000Z')

                    data['ship_date'] = order_date_str

                    logger.info(f"Ship date: {data['ship_date']}")

                    data['tracking_number'] = record.find('TrackNum').text.strip()

                    logger.info(f"Tracking number: {data['tracking_number']}")

                    # IF NO TRACKING NUMBER, LOG IT AND GO ON TO THE NEXT ONE
                    if data['tracking_number'] == "":
                        logger.info("No tracking number found. Skipping.")
                        continue

                    data['carrier_name'] = record.find('Type').text.strip()

                    # IF NO VENDOR, LOG IT AND GO ON TO THE NEXT ONE
                    if data['carrier_name'] == "":
                        logger.info("No vendor found. Skipping.")
                        continue

                    data['shipping_method'] = "ground"
                    data['cost'] = 14

                    logger.info(f"Vendor: {data['carrier_name']}")
                    logger.info("Sending to ordoro...")

                    # SEND TRACKING INFO TO ORDORO
                    r = ordoro.post_shipping_info(PONumber, data)

                    logger.info(f"[{PONumber}] Removing 'Awaiting Tracking' tag...")
                    r = ordoro.delete_tag_await_track(PONumber)

                    logger.debug(f"[{PONumber}] Response from ordoro:\n\r{r.content.decode('UTF-8')}")
                else:
                    taw_invoice_num = record.find('InvoiceNumber').text.strip()
                    tracking_number = record.find('TrackNum').text.strip()

                    if tracking_number == "":
                        continue

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

        logger.info(f"[{PONumber}] Finished.")
    logger.info(f"Done getting tracking info.")


inp = ''

while inp.lower() != 'q':
    if cfg.test:
        print("\n\r*** TEST MODE ***")
    else:
        print("\n\r!!! LIVE MODE !!!")
    print("What would you like to do?\n\r")
    print("\t1 Submit 'Dropship Ready' orders to TAW")
    print("\t2 Get tracking info from TAW for 'Awaiting Tracking' orders")
    print("\t3 Both")
    print("\t4 Switch between LIVE and TEST modes")
    print("\tq Quit\n\r")

    while True:
        print("=> ", end='')
        inp = input()

        if inp.lower() == 'q':
            exit()

        if inp == '4':
            cfg.test = not cfg.test

        if inp in ['1', '3']:
            submit_dropships()

        if inp in ['2', '3']:
            get_tracking()

        if inp in ['1', '2', '3', '4']:
            inp = ''
            break
