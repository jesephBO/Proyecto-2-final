import boto3
import uuid
import os
import json
import hashlib
from datetime import datetime
from boto3.dynamodb.conditions import Key

def lambda_handler(event, context):
    print(event)
    
    # Manejar body como string o dict
    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
    
    nombre_empresa = body.get('nombre_empresa')
    rubro = body.get('rubro', 'No especificado')
    nombre_admin = body.get('nombre_admin')
    correo = body.get('correo')
    contrasena = body.get('contrasena')
    
    if not nombre_empresa or not correo or not contrasena:
        return {
            'statusCode': 400,
            'body': json.dumps({'codigo': 'datos_incompletos', 'mensaje': 'Faltan campos obligatorios'})
        }
    
    # Normalizar correo (ignora mayúsculas y espacios extra)
    correo = correo.strip().lower()
    
    tabla_tenants = os.environ.get("TABLE_TENANTS", "t_tenants")
    tabla_usuarios = os.environ.get("TABLE_USUARIOS", "t_usuarios")
    tabla_locks = os.environ.get("TABLE_TENANTS_LOCKS", "t_tenants_locks")
    indice_nombre = os.environ.get("INDEX_NOMBRE", "nombre_normalizado-index")
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")
    
    # Generar identificadores y hash de contraseña
    uuid_raw = str(uuid.uuid4()).replace('-', '')[:8]
    tenant_id = f"ten_{uuid_raw}"
    usuario_id = f"usr_{uuid_raw}"
    fecha_creacion = datetime.utcnow().isoformat() + "Z"
    
    contrasena_hash = hashlib.sha256(contrasena.encode('utf-8')).hexdigest()
    
    # 1. Guardar Tenant en DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table_tenants = dynamodb.Table(tabla_tenants)
    table_locks = dynamodb.Table(tabla_locks)
    table_usuarios = dynamodb.Table(tabla_usuarios)
    
    # Normalizar nombre (ignora mayúsculas y espacios extra)
    nombre_normalizado = ' '.join(nombre_empresa.strip().lower().split())
    
    # Verificar que la empresa no esté registrada (consulta por GSI)
    response_busqueda = table_tenants.query(
        IndexName=indice_nombre,
        KeyConditionExpression=Key('nombre_normalizado').eq(nombre_normalizado),
        Limit=1
    )
    if response_busqueda.get('Count', 0) > 0:
        return {
            'statusCode': 409,
            'body': json.dumps({'codigo': 'empresa_existente', 'mensaje': 'La empresa ya se encuentra registrada'})
        }
    
    # Verificar que el correo del admin no esté registrado (consulta por GSI correo-index)
    response_correo = table_usuarios.query(
        IndexName='correo-index',
        KeyConditionExpression=Key('correo').eq(correo),
        Limit=1
    )
    if response_correo.get('Count', 0) > 0:
        return {
            'statusCode': 409,
            'body': json.dumps({'codigo': 'correo_existente', 'mensaje': 'El correo ya se encuentra registrado'})
        }
    
    # Candado en tabla aparte: evita que dos peticiones simultáneas registren el mismo nombre
    try:
        table_locks.put_item(
            Item={'nombre_normalizado': nombre_normalizado, 'fecha_creacion': fecha_creacion},
            ConditionExpression='attribute_not_exists(nombre_normalizado)'
        )
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {
            'statusCode': 409,
            'body': json.dumps({'codigo': 'empresa_existente', 'mensaje': 'La empresa ya se encuentra registrada'})
        }
    
    item_tenant = {
        'tenant_id': tenant_id,
        'nombre': nombre_empresa,
        'nombre_normalizado': nombre_normalizado,
        'rubro': rubro,
        'estado': 'activo',
        'fecha_creacion': fecha_creacion
    }
    try:
        response_tenant = table_tenants.put_item(Item=item_tenant)
    except Exception:
        # Liberar el candado si no se pudo guardar el tenant
        table_locks.delete_item(Key={'nombre_normalizado': nombre_normalizado})
        raise
    
    # 2. Guardar Usuario Admin en DynamoDB
    item_usuario = {
        'tenant_id': tenant_id,
        'usuario_id': usuario_id,
        'nombre': nombre_admin,
        'correo': correo,
        'contrasena_hash': contrasena_hash,
        'rol': 'admin',
        'estado': 'activo',
        'fecha_creacion': fecha_creacion
    }
    response_usuario = table_usuarios.put_item(Item=item_usuario)
    
    # 3. Publicar evento en SNS
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
                    'nombre': nombre_admin,
                    'rol': 'admin'
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
            'mensaje': 'Tenant y usuario admin creados exitosamente',
            'tenant_id': tenant_id,
            'usuario_id': usuario_id
        })
    }