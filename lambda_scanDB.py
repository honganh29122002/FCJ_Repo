import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('InvoicesTable')

def format_invoice_text(invoice):
    """Chuyển đổi thông tin hóa đơn thành định dạng văn bản dễ đọc cho người dùng"""
    formatted_text = []
    formatted_text.append(f"<h2>Mã hóa đơn: {invoice.get('InvoiceID')}</h2>")
    formatted_text.append(f"<p><strong>Ngày:</strong> {invoice.get('InvoiceDate')}</p>")
    formatted_text.append(f"<p><strong>Thu ngân:</strong> {invoice.get('Cashier')}</p>")
    formatted_text.append(f"<p><strong>Quầy:</strong> {invoice.get('Counter')}</p>")
    formatted_text.append(f"<p><strong>Phương thức thanh toán:</strong> {invoice.get('PaymentMethod')}</p>")
    formatted_text.append(f"<p><strong>Khách đưa:</strong> {invoice.get('CustomerPaid')}</p>")
    formatted_text.append(f"<p><strong>Tổng tiền:</strong> {invoice.get('TotalAmount')}</p>")
    formatted_text.append(f"<p><strong>Chiết khấu:</strong> {invoice.get('Discount')}</p>")
    formatted_text.append(f"<p><strong>Tiền thối:</strong> {invoice.get('Change')}</p>")
    
    # Danh sách sản phẩm
    items = invoice.get("Items", [])
    if items:
        formatted_text.append("<h3>Danh sách sản phẩm:</h3>")
        formatted_text.append("<table border='1' cellpadding='5' cellspacing='0'>")
        formatted_text.append("<tr><th>#</th><th>Tên sản phẩm</th><th>Số lượng</th><th>Đơn giá</th><th>Thành tiền</th></tr>")
        for idx, item in enumerate(items, 1):
            name = item.get("name") or "Không rõ"
            quantity = item.get("quantity") or "Không rõ"
            unit_price = item.get("unit_price") or "Không rõ"
            total_price = item.get("total_price") or "Không rõ"
            formatted_text.append(f"<tr><td>{idx}</td><td>{name}</td><td>{quantity}</td><td>{unit_price}</td><td>{total_price}</td></tr>")
        formatted_text.append("</table>")

    return "".join(formatted_text)


def lambda_handler(event, context):
    try:
        #  Truy xuất toàn bộ dữ liệu từ bảng
        response = table.scan()
        items = response.get('Items', [])

        if not items:
            return {
                'statusCode': 404,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*'
                },
                'body': json.dumps({"message": "Không có dữ liệu hóa đơn."})
            }

        # Định dạng dữ liệu thành dạng HTML dễ nhìn
        formatted_result = "<div>" + "".join([format_invoice_text(invoice) for invoice in items]) + "</div>"

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*'
            },
            'body': json.dumps({"formatted_result": formatted_result})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
