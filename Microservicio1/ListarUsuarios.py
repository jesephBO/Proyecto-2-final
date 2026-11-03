import boto3
import os
import json

def lambda_handler(event, context):
    print(event)
    
    claims = event.get('requestContext', {}).get('authorizer', {})
    tenant_id = claims.get('tenant_id')
    
    tabla_usuarios = os.environ.get("TABLE_USUARIOS", "t_usuarios")
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(tabla_usuarios)
    
    # Consulta filtrando estrictamente por tenant_id
    response = table.query(
        KeyConditionExpression='tenant_id = :tenant_id',
        ExpressionAttributeValues={':tenant_id': tenant_id}
    )
    
    usuarios = response.get('Items', [])
    
    # Limpiar campos sensibles antes de retornar
    for u in usuarios:
        if 'contrasena_hash' in u:
            del u['contrasena_hash']
            
    return {
        'statusCode': 200,
        'body': json.dumps(usuarios)
    }