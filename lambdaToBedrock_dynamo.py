import boto3
import json

bedrock = boto3.client('bedrock-runtime')

def invoke_bedrock(form_data):
    prompt = f"""
Dưới đây là dữ liệu biểu mẫu hóa đơn bán lẻ đã được Textract trích xuất:

{json.dumps(form_data, indent=2)}

Hãy phân tích và trả về một JSON với cấu trúc sau:

{{
  "invoice_id": string, 
  "invoice_date": string,
  "cashier": string,
  "counter": string,
  "total_amount": number,
  "discount": number,
  "customer_paid": number,
  "change": number,
  "payment_method": string,
  "items": [
    {{
      "name": string,
      "code": string,
      "quantity": number,
      "unit_price": number,
      "total_price": number
    }},
    ...
  ]
}}

Chỉ trả về đúng một chuỗi JSON hợp lệ.
"""

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.3
        })
    )

    raw_output = json.loads(response['body'].read())
    print("Raw output from Claude:", raw_output)

    messages = raw_output.get("content", [])
    if isinstance(messages, list) and len(messages) > 0:
        try:
            text_content = messages[0].get("text", "")
            start_index = text_content.find("{")
            end_index = text_content.rfind("}") + 1
            if start_index != -1 and end_index != -1:
                json_string = text_content[start_index:end_index]
                return json.loads(json_string)
            else:
                print("Không tìm thấy JSON trong phản hồi từ Claude.")
                return {"error": "No valid JSON found in Claude response", "data": text_content}
        except json.JSONDecodeError:
            print("Claude không trả về chuỗi JSON hợp lệ.")
            return {"error": "Invalid JSON from Claude", "data": messages}
    else:
        print("Claude trả về dữ liệu không hợp lệ.")
        return {"error": "Invalid response from Claude"}

def lambda_handler(event, context):
    print("Lambda B triggered")
    form_data = event.get("form_data", {})
    summary = invoke_bedrock(form_data)
    print("Claude summary:", summary)
    return summary
