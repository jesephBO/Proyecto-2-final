import boto3
import uuid
import os
import json
import hashlib
from datetime import datetime
from boto3.dynamodb.conditions import Key

def lambda_handler(event, context):
    print(event)
    
    # Extraer tenant_id y rol del contexto del Authorizer de API Gateway
    claims = event.get('requestContext', {}).get('authorizer', {})
    tenant_id = claims.get('tenant_id')
    rol_solicitante = claims.get('rol')
    
    if rol_solicitante != 'admin':
        return {
            'statusCode': 403,
            'body': json.dumps({'codigo': 'prohibido', 'mensaje': 'Solo un usuario admin puede registrar empleados'})
        }
        
    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
    nombre = body.get('nombre')
    correo = body.get('correo')
    contrasena = body.get('contrasena')
    rol = body.get('rol') # 'gerente' o 'vendedor'
    
    if not tenant_id or not nombre or not correo or not contrasena or not rol:
        return {
            'statusCode': 400,
            'body': json.dumps({'codigo': 'datos_incompletos', 'mensaje': 'Faltan campos obligatorios'})
        }
    
    # Normalizar correo (ignora mayúsculas y espacios extra)
    correo = correo.strip().lower()
    
    tabla_usuarios = os.environ.get("TABLE_USUARIOS", "t_usuarios")
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")
    
    uuid_raw = str(uuid.uuid4()).replace('-', '')[:8]
    usuario_id = f"usr_{uuid_raw}"
    fecha_creacion = datetime.utcnow().isoformat() + "Z"
    contrasena_hash = hashlib.sha256(contrasena.encode('utf-8')).hexdigest()
    
    usuario = {
        'tenant_id': tenant_id,
        'usuario_id': usuario_id,
        'nombre': nombre,
        'correo': correo,
        'contrasena_hash': contrasena_hash,
        'rol': rol,
        'estado': 'activo',
        'fecha_creacion': fecha_creacion
    }
    
    # 1. Guardar en DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(tabla_usuarios)
    
    # Verificar que el correo no esté registrado (consulta por GSI correo-index)
    response_busqueda = table.query(
        IndexName='correo-index',
        KeyConditionExpression=Key('correo').eq(correo),
        Limit=1
    )
    if response_busqueda.get('Count', 0) > 0:
        return {
            'statusCode': 409,
            'body': json.dumps({'codigo': 'correo_existente', 'mensaje': 'El correo ya se encuentra registrado'})
        }
    
    response_dynamo = table.put_item(Item=usuario)
    
    # 2. Publicar evento 'usuario.creado' en SNS
    if sns_topic_arn:
        try:
            sns = boto3.client('sns')
            evento = {
                'evento_id': f"evt_{str(uuid.uuid4())[:8]}",
                'tipo': 'usuario.creado',
                'tenant_id': tenant_id,
                'fecha': fecha_creacion,
                'datos': {
                    'usuario_id': usuario_id,
                    'nombre': nombre,
                    'rol': rol
                }
            }
            sns.publish(
                TopicArn=sns_topic_arn,
                Message=json.dumps(evento)
            )
        except Exception as e_sns:
            print(f"Advertencia: No se pudo publicar en SNS: {e_sns}")
        
    return {
        'statusCode': 201,
        'body': json.dumps({
            'mensaje': 'Usuario creado exitosamente',
            'usuario_id': usuario_id
        })
    }