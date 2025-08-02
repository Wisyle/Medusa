# get_pending_orders_test.py
import json
from rest_client import BitgetRESTClient

symbol = "FARTCOINUSDT"
product_type = "USDT-FUTURES"

with open("config.json") as f:
    cfg = json.load(f)
creds = cfg["bitget"]

client = BitgetRESTClient(creds["apiKey"], creds["apiSecret"], creds["passphrase"])

def cb(resp):
    print("\nPENDING ORDERS:")
    print(json.dumps(resp, indent=2))

client.submit_rest_task("get_pending_orders", {
    "productType": product_type,
    "symbol": symbol
}, callback=cb)

client.task_queue.join()
