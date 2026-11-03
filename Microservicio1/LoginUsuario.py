import boto3
import os
import json
import hashlib

def lambda_handler(event, context):
    print(event)
    
    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
    correo = body.get('correo')
    contrasena = body.get('contrasena')
    
    if not correo or not contrasena:
        return {
            'statusCode': 400,
            'body': json.dumps({'codigo': 'datos_incompletos', 'mensaje': 'Correo y contraseña requeridos'})
        }
    # Normalizar correo (ignora mayúsculas y espacios extra)
    correo = correo.strip().lower()
        
    tabla_usuarios = os.environ.get("TABLE_USUARIOS", "t_usuarios")
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(tabla_usuarios)
    
    # Buscar usuario por correo usando Global Secondary Index (GSI)
    response = table.query(
        IndexName='correo-index',
        KeyConditionExpression='correo = :correo',
        ExpressionAttributeValues={':correo': correo}
    )
    
    items = response.get('Items', [])
    if not items:
        return {
            'statusCode': 401,
            'body': json.dumps({'codigo': 'no_autorizado', 'mensaje': 'Credenciales inválidas'})
        }
        
    usuario = items[0]
    contrasena_hash = hashlib.sha256(contrasena.encode('utf-8')).hexdigest()
    
    if usuario.get('contrasena_hash') != contrasena_hash:
        return {
            'statusCode': 401,
            'body': json.dumps({'codigo': 'no_autorizado', 'mensaje': 'Credenciales inválidas'})
        }
        
    # En producción se genera el JWT firmado.
    # Aquí simulamos la respuesta con la estructura de claims requerida.
    token_simulado = f"Bearer {usuario['tenant_id']}:{usuario['usuario_id']}:{usuario['rol']}"
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'token': token_simulado,
            'tenant_id': usuario['tenant_id'],
            'usuario_id': usuario['usuario_id'],
            'rol': usuario['rol']
        })
    }