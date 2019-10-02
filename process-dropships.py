import requests
import json
import xml.etree.ElementTree as ET
import datetime
import config as cfg

log_file = f"LOG-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"

taw_u = cfg.taw_username
taw_p = cfg.taw_password
taw_url = cfg.taw_url

taw_headers = {
	'Content-Type' : 'application/x-www-form-urlencoded',
}

ord_headers = {
	'Authorization' : cfg.ord_auth,
	'Content-Type' : 'application/json'
}

ord_url = cfg.ord_url
ord_legacy_url = cfg.ord_legacy_url

ord_tag_id_drop_ready = '30093'
ord_tag_name_drop_ready = 'Dropship Ready'

ord_tag_id_drop_failed = '30067'
ord_tag_name_drop_failed = 'Dropship Request Failed'

ord_tag_id_await_tracking = '30068'
ord_tag_name_await_tracking = 'Awaiting Tracking'

ord_supplier_taw_id = 44251

ord_get_dropship_orders_params = {
	'tag' : ord_tag_name_drop_ready,
	'limit' : '100'
}

ord_get_await_tracking_orders_params = {
	'tag' : ord_tag_name_await_tracking
}

def log(str):
	print(str, flush=True)
	with open(log_file, 'a') as file:
		file.write(f"{str}\n\r")
		
def submit_dropships():
	### GET ALL DROPSHIP READY ORDERS FROM ORDORO ###
	log(f"Requesting all orders with 'Dropship Ready' from ordoro...")

	r = requests.get(f"{ord_url}/order", params=ord_get_dropship_orders_params, headers=ord_headers)
	robj = json.loads(r.content)

	ord_orders = robj['order']

	log(f"Found {len(ord_orders)} to process.\n\r\n\r")

	for eachOrder in ord_orders:
		### PARSE ORDER INFO FROM ORDORO ###
		parsed_order = {}
		parsed_order['PONumber'] = eachOrder['order_number']
		
		log(f"Parsing {parsed_order['PONumber']}...")
		
		parsed_order['ReqDate'] = eachOrder['order_placed_date']
		log(f"Order Date: {parsed_order['ReqDate']}")
		
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
			r = requests.get(f"{ord_legacy_url}/product/{ord_sku}/", headers=ord_headers)
			rob = r.json()
			
			taw_sku = ''
			
			# Loop through suppliers until you find TAW
			for eachSupplier in rob['suppliers']:
				if (eachSupplier['id'] == ord_supplier_taw_id):
					taw_sku = eachSupplier['supplier_sku']
					
			parsed_order['Parts'].append({'PartNo' : taw_sku, 'Qty' : eachLine['quantity']})
			
		for eachTag in eachOrder['tags']:
			if(eachTag['text'] == 'Signature Required'):
				parsed_order['SpecialInstructions'] = 'Signature Required'
		
		### CONSTRUCT XML TO SEND TO TAW ###
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
			xml_pt2 = f"{xml_pt2}<Part Number='{eachPart['PartNo']}'><Qty>{eachPart['Qty']}</Qty></Part>"
		
		xml_pt3 = ""
		
		try:
			xml_pt3 = f"<SpecialInstructions>{parsed_order['SpecialInstructions']}</SpecialInstructions>"
		except:
			pass
			
		xml_pt4 = "</Order>"	
		full_xml = f"{xml_pt1}{xml_pt2}{xml_pt3}{xml_pt4}"
		
		log(f"Sending XML to TAW:\n\r{full_xml}")
		
		### SEND ORDER TO TAW ###
		r = requests.post(f"{taw_url}/SubmitOrder", data=f"UserID={taw_u}&Password={taw_p}&OrderInfo={full_xml}", headers=taw_headers)
		
		status = ""
		taw_order_id = ""
		
		try:
			# PARSE XML RESPONSE FROM TAW
			tree = ET.ElementTree(ET.fromstring(r.content))
			root = tree.getroot()
			status = root.find('Status').text
			
			if (status == "PASS"):
				taw_order_id = root.find('Order').attrib['Id']
				log(f"Order submitted successfully. Order ID: {taw_order_id}")
				
				# ADD AWAITING TRACKING TAG
				log(f"Adding 'Awaiting Tracking' tag...")
				r = requests.post(f"{ord_url}/order/{parsed_order['PONumber']}/tag/{ord_tag_id_await_tracking}", headers=ord_headers)
				
				# ADD COMMENT WITH TAW ORDER ID
				log(f"Adding comment with TAW Order ID {taw_order_id}")
				r = requests.post(f"{ord_url}/order/{parsed_order['PONumber']}/comment", headers=ord_headers, data=json.dumps({'comment' : f'TAW_ORD_ID:{taw_order_id}'}))
			else:
				log(f"Status is not 'PASS': {status}")

				# ADD DROPSHIP FAILED TAG
				log(f"Adding 'Dropship Failed' tag...")
				r = requests.post(f"{ord_url}/order/{parsed_order['PONumber']}/tag/{ord_tag_id_drop_failed}", headers=ord_headers)
		except Exception as err:
			log(f"Error parsing response. Exception:\n\r{err}\n\rLast Response:\n\r{r.content.decode('UTF-8')}")
			
			# ADD DROPSHIP FAILED TAG
			log(f"Adding 'Dropship Failed' tag...")
			r = requests.post(f"{ord_url}/order/{parsed_order['PONumber']}/tag/{ord_tag_id_drop_failed}", headers=ord_headers)
			
		# REMOVE DROPSHIP READY TAG #
		r = requests.delete(f"{ord_url}/order/{parsed_order['PONumber']}/tag/{ord_tag_id_drop_ready}", headers=ord_headers)

		log("Done submitting dropships!\n\r")
		
def get_tracking():
	#### GET ALL AWAITING TRACKING ORDERS FROM ORDORO ###
	log("Requesting all orders with 'Awaiting Tracking' from ordoro...")

	r = requests.get(f"{ord_url}/order", params=ord_get_await_tracking_orders_params, headers=ord_headers)
	robj = json.loads(r.content)

	ord_orders = robj['order']

	log(f"Found {len(ord_orders)} to process.")

	for eachOrder in ord_orders:
		PONumber = eachOrder['order_number']
		taw_order_id = ''
		
		log(f"\n\r---- {PONumber} ----")
		
		# LOOP THROUGH ORDER COMMENTS TO FIND THE ORDER NUMBER RETURNED BY TAW
		for eachComment in eachOrder['comments']:
			if("TAW_ORD_ID" in eachComment['text']):
				taw_order_id = eachComment['text'].split(':')[1]
				
		log(f"[{PONumber}] TAW order id {taw_order_id}")
		log(f"[{PONumber}] Requesting tracking info from TAW...")
				
		# ASK FOR TRACKING INFO FROM TAW
		r = requests.post(f"{taw_url}/GetTrackingInfo", data=f"UserID={taw_u}&Password={taw_p}&OrderNumber={taw_order_id}&PONumber={PONumber}", headers=taw_headers)
		
		log(f"[{PONumber}] Response from TAW:\n\r{r.content.decode('UTF-8')}")

		try:
			# PARSE TRACKING INFO FROM TAW RESPONSE
			root = ET.ElementTree(ET.fromstring(r.content)).getroot()
			record = root.find('Record')
			
			log(f"[{PONumber}] Tracking info found! Parsing...")
			
			data = {}
			
			order_date_str = record.find('OrderDate').text
			order_date_obj = datetime.datetime.strptime(order_date_str, '%m/%d/%Y')
			order_date_str = order_date_obj.strftime('%Y-%m-%dT%H:%M:%S.000Z')
			
			data['ship_date'] = order_date_str
			
			log(f"[{PONumber}] Ship date: {data['ship_date']}")
			
			data['tracking_number'] = record.find('TrackNum').text.strip()
					
			log(f"[{PONumber}] Tracking number: {data['tracking_number']}")
			
			# IF NO TRACKING NUMBER, LOG IT AND GO ON TO THE NEXT ONE
			if (data['tracking_number'] == ""):
				log(f"[{PONumber}] No tracking number found. Skipping.")
				continue
			
			data['carrier_name'] = record.find('Type').text.strip()
			
			# IF NO VENDOR, LOG IT AND GO ON TO THE NEXT ONE
			if (data['carrier_name'] == ""):
				log(f"[{PONumber}] No vendor found. Skipping.")
				continue
				
			data['shipping_method'] = "ground"
			data['cost'] = 14
			
			log(f"[{PONumber}] Vendor: {data['carrier_name']}")
			log(f"[{PONumber}] Sending to ordoro...")
			
			# SEND TRACKING INFO TO ORDORO
			r = requests.post(f"{ord_url}/order/{PONumber}/shipping_info", data=json.dumps(data), headers=ord_headers)
			
			log(f"[{PONumber}] Response from ordoro:\n\r{r.content.decode('UTF-8')}")
			log(f"[{PONumber}] Removing 'Awaiting Tracking' tag...")
			
			# DELETE AWAITING TRACKING TAG FROM ORDER
			r = requests.delete(f"{ord_url}/order/{PONumber}/tag/{ord_tag_id_await_tracking}", headers=ord_headers)
			
			log(f"[{PONumber}] Response from ordoro:\n\r{r.content.decode('UTF-8')}")

		except Exception as err:
			log(f"[{PONumber}] Error parsing tracking info...\n\rException:\n\r{err}\n\rLast Response:\n\r{r.content.decode('UTF-8')}")

		log(f"[{PONumber}] Finished.")
	log(f"Done getting tracking info.")

inp = ''

while (inp.lower() != 'q'):
	print("\n\rWhat would you like to do?\n\r")
	print("\t1 Submit 'Dropship Ready' orders to TAW")
	print("\t2 Get tracking info from TAW for 'Awaiting Tracking' orders")
	print("\t3 Both")
	print("\tq Quit\n\r")
	
	while (True):
		print("=> ", end='')
		inp = input()
		
		if inp.lower() == 'q':
			exit()
		
		if (inp in ['1','3']):
			submit_dropships()

		if (inp in ['2','3']):
			get_tracking()

		if (inp in ['1', '2', '3']):
			inp = ''
			break