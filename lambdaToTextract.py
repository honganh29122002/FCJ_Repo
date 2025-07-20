import boto3
import json
import os
from urllib.parse import unquote_plus

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

# ----------- Lambda Handler ----------------

def lambda_handler(event, context):
    print("Lambda A triggered")

    record = event['Records'][0]
    bucket = unquote_plus(record['s3']['bucket']['name'])
    key = unquote_plus(record['s3']['object']['key'])

    print(f"File uploaded: {key} in bucket: {bucket}")

    # Step 1: Extract KV data using Textract
    key_map, value_map, block_map = get_kv_map(bucket, key)
    kvs = get_kv_relationship(key_map, value_map, block_map)

     # Log the extracted key-value pairs
    print(f"Extracted key-value pairs: {json.dumps(kvs, indent=2)}")

    print(f"Extracted {len(kvs)} key-value pairs")
    for k, v in kvs.items():
        print(f"{k}: {v}")

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
        recipient = response_payload.get("recipient", "").strip()

        if recipient:
            item = {
                "Recipient": recipient,
                "Sender": response_payload.get("sender", ""),
                "MessageDate": response_payload.get("message_date", ""),
                "Phone": response_payload.get("phone", ""),
                "ActionRequired": response_payload.get("action_required", "")
            }

            print("Saving item to DynamoDB:", json.dumps(item, indent=2))
            table.put_item(Item=item)
            print("Data saved to DynamoDB successfully.")
        else:
            print("Recipient is missing. Data will not be saved to DynamoDB.")
    else:
        print("Lambda B did not return valid data.")
