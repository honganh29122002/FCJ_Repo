import boto3
import json
import os
from urllib.parse import unquote_plus
from decimal import Decimal

# AWS clients
textract = boto3.client('textract')
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get("TABLE_NAME", "InvoicesTable")
table = dynamodb.Table(table_name)

# ----------- Helper Functions --------------

def get_kv_map(bucket, key):
    response = textract.analyze_document(
        Document={'S3Object': {'Bucket': bucket, 'Name': key}},
        FeatureTypes=['FORMS']
    )

    blocks = response['Blocks']
    key_map, value_map, block_map = {}, {}, {}

    for block in blocks:
        block_id = block['Id']
        block_map[block_id] = block
        if block['BlockType'] == "KEY_VALUE_SET":
            if 'KEY' in block['EntityTypes']:
                key_map[block_id] = block
            else:
                value_map[block_id] = block

    return key_map, value_map, block_map

def find_value_block(key_block, value_map):
    for rel in key_block.get('Relationships', []):
        if rel['Type'] == 'VALUE':
            for value_id in rel['Ids']:
                return value_map.get(value_id)
    return None

def get_text(result, blocks_map):
    text = ''
    for rel in result.get('Relationships', []):
        if rel['Type'] == 'CHILD':
            for child_id in rel['Ids']:
                word = blocks_map[child_id]
                if word['BlockType'] == 'WORD':
                    text += word['Text'] + ' '
                elif word['BlockType'] == 'SELECTION_ELEMENT':
                    if word['SelectionStatus'] == 'SELECTED':
                        text += 'X '
    return text.strip()

def get_kv_relationship(key_map, value_map, block_map):
    kvs = {}
    for key_block in key_map.values():
        value_block = find_value_block(key_block, value_map)
        key = get_text(key_block, block_map)
        val = get_text(value_block, block_map) if value_block else ''
        kvs[key] = val
    return kvs

def convert_floats_to_decimals(obj):
    """Đệ quy chuyển đổi float thành Decimal (kể cả trong list và dict lồng nhau)."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimals(elem) for elem in obj]
    else:
        return obj

def replace_none_with_zero(value):
    """Chuyển đổi giá trị 'None' thành 0"""
    if value == "None":
        return 0
    return value

def format_items(items):
    """Chuyển đổi các item trong danh sách thành định dạng phù hợp với DynamoDB"""
    formatted_items = []
    for item in items:
        formatted_item = {
            "name": {"S": item.get("name", "")},
            "code": {"S": item.get("code", "") or {"NULL": True}},  # Đảm bảo code không phải None
            "quantity": {"N": str(item.get("quantity", 0))},  # Nếu quantity là None hoặc không có thì gán 0
            "unit_price": {"N": str(item.get("unit_price", 0))},  # Nếu unit_price là None thì gán 0
            "total_price": {"N": str(item.get("total_price", 0))}  # Tương tự với total_price
        }
        formatted_items.append({"M": formatted_item})  # Sử dụng "M" cho mỗi item
    return formatted_items

# ----------- Lambda Handler ----------------

def lambda_handler(event, context):
    try:
        print("Lambda A triggered")

        record = event['Records'][0]
        bucket = unquote_plus(record['s3']['bucket']['name'])
        key = unquote_plus(record['s3']['object']['key'])

        print(f"File uploaded: {key} in bucket: {bucket}")

        # Step 1: Extract KV data using Textract
        key_map, value_map, block_map = get_kv_map(bucket, key)
        kvs = get_kv_relationship(key_map, value_map, block_map)

        print(f"Extracted {len(kvs)} key-value pairs")
        print(f"Extracted key-value pairs: {json.dumps(kvs, indent=2)}")

        # Step 2: Call Lambda B synchronously to process with Bedrock
        response = lambda_client.invoke(
            FunctionName='receive_bedrockHandle_putDynamodb',
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'form_data': kvs
            }).encode('utf-8')
        )

        response_payload = json.loads(response['Payload'].read())
        print("Response from Lambda B:", json.dumps(response_payload, indent=2))

        # Step 3: Save to DynamoDB if valid
        if response_payload and isinstance(response_payload, dict):
            invoice_id = response_payload.get("invoice_id", "").strip()

            if invoice_id:
                items = format_items(response_payload.get("items", []))
                item = convert_floats_to_decimals({
                    "InvoiceID": invoice_id,
                    "InvoiceDate": response_payload.get("invoice_date", ""),
                    "Cashier": response_payload.get("cashier", ""),
                    "Counter": response_payload.get("counter", ""),
                    "TotalAmount": response_payload.get("total_amount", 0),
                    "Discount": response_payload.get("discount", 0),
                    "CustomerPaid": response_payload.get("customer_paid", 0),
                    "Change": response_payload.get("change", 0),
                    "PaymentMethod": response_payload.get("payment_method", "Tiền mặt"),
                    "Items": items
                })

                print("Saving item to DynamoDB:", json.dumps(item, indent=2, default=str))
                table.put_item(Item=item)
                print("Data saved to DynamoDB successfully.")
            else:
                print("Invoice ID is missing. Data will not be saved to DynamoDB.")
        else:
            print("Lambda B did not return valid data.")

    except Exception as e:
        print(f"[ERROR] Exception occurred: {str(e)}", flush=True)
        raise
