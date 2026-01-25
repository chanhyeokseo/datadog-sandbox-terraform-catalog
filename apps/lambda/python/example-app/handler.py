import json
import os
from datetime import datetime

def lambda_handler(event, context):
    """
    Simple health check Lambda function
    """
    app_name = os.environ.get('APP_NAME', 'example-app')
    
    result = {
        'timestamp': datetime.utcnow().isoformat(),
        'app_name': app_name,
        'status': 'healthy',
        'message': 'Lambda function is running successfully'
    }
    
    if context:
        result['lambda_info'] = {
            'request_id': context.aws_request_id,
            'function_name': context.function_name,
            'memory_limit_mb': context.memory_limit_in_mb
        }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(result, indent=2)
    }
