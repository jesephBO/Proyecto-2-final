import boto3
import os
import json

def lambda_handler(event, context):
    print(event)
    
    claims = event.get('requestContext', {}).get('authorizer', {})
    tenant_id = claims.get('tenant_id')
    rol_solicitante = claims.get('rol')
    
    if rol_solicitante != 'admin':
        return {
            'statusCode': 403,
            'body': json.dumps({'codigo': 'prohibido', 'mensaje': 'Solo administradores pueden modificar usuarios'})
        }
        
    path_parameters = event.get('pathParameters', {}) or {}
    usuario_id = path_parameters.get('usuario_id')
    
    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
    rol = body.get('rol')
    estado = body.get('estado')
    
    tabla_usuarios = os.environ.get("TABLE_USUARIOS", "t_usuarios")
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(tabla_usuarios)
    
    response = table.update_item(
        Key={
            'tenant_id': tenant_id,
            'usuario_id': usuario_id
        },
        UpdateExpression="SET rol = :rol, estado = :estado",
        ExpressionAttributeValues={
            ':rol': rol,
            ':estado': estado
        },
        ReturnValues="UPDATED_NEW"
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({'mensaje': 'Usuario actualizado correctamente', 'respuesta': response})
    }