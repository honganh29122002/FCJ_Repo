import boto3
import base64
import os

s3 = boto3.client("s3")
BUCKET_NAME = "invoicebuckett123"

def lambda_handler(event, context):
    # Xử lý CORS preflight (OPTIONS request)
    if event["httpMethod"] == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",  # hoặc domain cụ thể nếu bạn muốn
                "Access-Control-Allow-Methods": "POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
            },
            "body": ""
        }

    try:
        file_name = event["pathParameters"]["filename"]
        content_type = event["headers"].get("Content-Type") or event["headers"].get("content-type", "application/octet-stream")
        file_content = base64.b64decode(event["body"])

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=file_name,
            Body=file_content,
            ContentType=content_type,
        )

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",  # hoặc domain cụ thể
                "Access-Control-Allow-Methods": "POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
            },
            "body": f"File '{file_name}' uploaded successfully to S3."
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
            },
            "body": f"Upload failed: {str(e)}"
        }
