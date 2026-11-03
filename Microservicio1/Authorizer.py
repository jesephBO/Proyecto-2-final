import json

def lambda_handler(event, context):
    print("Evento recibido en Authorizer:", json.dumps(event))
    
    # 1. Extraer el token recibido desde la cabecera
    token = event.get('authorizationToken', '')
    
    try:
        # Validar el prefijo 'Bearer '
        if token.startswith("Bearer "):
            token_data = token.replace("Bearer ", "").strip()
            parts = token_data.split(":")
            
            # Verificar que contenga tenant_id, usuario_id y rol
            if len(parts) == 3:
                tenant_id = parts[0]
                usuario_id = parts[1]
                rol = parts[2]
                
                # 2. Retornar LA ESTRUCTURA EXACTA que exige API Gateway
                policy = {
                    "principalId": usuario_id,
                    "policyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": "Allow",
                                "Resource": "*"
                            }
                        ]
                    },
                    "context": {
                        "tenant_id": tenant_id,
                        "usuario_id": usuario_id,
                        "rol": rol
                    }
                }
                print("Politica generada exitosamente:", json.dumps(policy))
                return policy
                
    except Exception as e:
        print(f"Error procesando token: {e}")
        
    # 3. Si el token no es válido o está mal formado, denegar acceso
    raise Exception("Unauthorized")