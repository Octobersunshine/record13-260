import io
import json
from app import app

client = app.test_client()

csv_data = '''region,product,sales,quantity
East,A,100,10
East,A,200,20
East,B,150,15
West,A,300,30
West,B,250,25
'''

# Test 1: 逗号分隔的多聚合
print('=== 逗号分隔: aggfunc=sum,mean ===')
resp = client.post('/pivot', data={
    'file': (io.BytesIO(csv_data.encode()), 'data.csv'),
    'rows': 'region',
    'values': 'sales,quantity',
    'aggfunc': 'sum,mean',
}, content_type='multipart/form-data')
print('Status:', resp.status_code)
data = resp.get_json()
print('Columns:', list(data[0].keys()))
print(json.dumps(data, indent=2, ensure_ascii=False))
print()

# Test 2: JSON 格式 per-value 聚合
print('=== JSON映射: sales->[sum,mean], quantity->count ===')
aggfunc_json = json.dumps({"sales": ["sum", "mean"], "quantity": "count"})
resp = client.post('/pivot', data={
    'file': (io.BytesIO(csv_data.encode()), 'data.csv'),
    'rows': 'region',
    'values': 'sales,quantity',
    'aggfunc': aggfunc_json,
}, content_type='multipart/form-data')
print('Status:', resp.status_code)
data = resp.get_json()
print('Columns:', list(data[0].keys()))
print(json.dumps(data, indent=2, ensure_ascii=False))
print()

# Test 3: JSON + cols
print('=== JSON映射 + cols ===')
aggfunc_json = json.dumps({"sales": ["sum", "mean"], "quantity": "count"})
resp = client.post('/pivot', data={
    'file': (io.BytesIO(csv_data.encode()), 'data.csv'),
    'rows': 'region',
    'cols': 'product',
    'values': 'sales,quantity',
    'aggfunc': aggfunc_json,
}, content_type='multipart/form-data')
print('Status:', resp.status_code)
data = resp.get_json()
print('Columns:', list(data[0].keys()))
print(json.dumps(data, indent=2, ensure_ascii=False))
print()

# Test 4: 单聚合（默认）
print('=== 单聚合: aggfunc=sum ===')
resp = client.post('/pivot', data={
    'file': (io.BytesIO(csv_data.encode()), 'data.csv'),
    'rows': 'region',
    'values': 'sales',
    'aggfunc': 'sum',
}, content_type='multipart/form-data')
print('Status:', resp.status_code)
data = resp.get_json()
print('Columns:', list(data[0].keys()))
print(json.dumps(data, indent=2, ensure_ascii=False))
