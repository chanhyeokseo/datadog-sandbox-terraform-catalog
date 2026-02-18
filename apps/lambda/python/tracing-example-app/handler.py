import json
import os
import time
from datetime import datetime
from ddtrace import tracer
from datadog_lambda.metric import lambda_metric

def create_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, indent=2)
    }

def create_html_response(status_code, html):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'text/html',
            'Access-Control-Allow-Origin': '*'
        },
        'body': html
    }

def get_path(event):
    raw_path = event.get('rawPath', event.get('path', '/'))
    return raw_path if raw_path else '/'

ENDPOINT_DESCRIPTIONS = {
    '/': 'Available endpoints (this page)',
    '/add-tag': 'Add custom tags to current span',
    '/set-error': 'Set error on current span (returns 500)',
    '/trace-decorator': 'Create span using decorator',
    '/manual-span': 'Manually create a span',
    '/nested-spans': 'Create nested spans',
    '/custom-metrics': 'Submit custom metrics',
    '/health': 'Health check',
    '/slow': 'Slow endpoint (2 second delay)',
}

@tracer.wrap(service="tracing-example", resource="index")
def handle_index(context):
    lambda_metric('endpoint.index', 1, tags=['endpoint:index'])

    links = ""
    for path, desc in ENDPOINT_DESCRIPTIONS.items():
        links += f'<li><a href="{path}">{path}</a> — {desc}</li>\n'

    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Tracing Example API</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 20px;color:#333}"
        "h1{color:#632ca6}ul{line-height:2}a{color:#1a73e8;text-decoration:none}"
        "a:hover{text-decoration:underline}.ts{color:#888;font-size:0.85em;margin-top:24px}"
        "</style></head><body>"
        "<h1>Tracing Example API</h1>"
        "<p>Lambda function with Datadog APM tracing examples</p>"
        f"<h2>Available Endpoints</h2><ul>{links}</ul>"
        f"<p class='ts'>Generated at {datetime.utcnow().isoformat()}Z</p>"
        "</body></html>"
    )
    return create_html_response(200, html)

@tracer.wrap(service="tracing-example", resource="add_tag")
def handle_add_tag(context):
    span = tracer.current_span()
    if span:
        today = datetime.utcnow().date().isoformat()
        span.set_tag('date', today)
        span.set_tag('custom.tag', 'example-value')
        span.set_tag('environment', os.environ.get('ENVIRONMENT', 'unknown'))
        span.set_tag('lambda.function', context.function_name if context else 'unknown')
    
    lambda_metric('endpoint.add_tag', 1, tags=['endpoint:add-tag'])
    
    return create_response(200, {
        'message': 'Added tags to span',
        'endpoint': '/add-tag',
        'tags_added': ['date', 'custom.tag', 'environment', 'lambda.function'],
        'timestamp': datetime.utcnow().isoformat()
    })

@tracer.wrap(service="tracing-example", resource="set_error")
def handle_set_error(context):
    """
    GET /set-error - Set an error on the current span and return 500
    """
    span = tracer.current_span()
    if span:
        try:
            small_list = [1]
            _ = small_list[1]
        except Exception as ex:
            span.set_tag('error', True)
            span.set_tag('error.type', type(ex).__name__)
            span.set_tag('error.message', str(ex))
            span.set_tag('error.stack', str(ex))
    
    lambda_metric('endpoint.set_error', 1, tags=['endpoint:set-error', 'error:true'])
    
    return create_response(500, {
        'error': 'Simulated Error',
        'message': 'Error set on span',
        'endpoint': '/set-error',
        'error_simulated': 'IndexError',
        'timestamp': datetime.utcnow().isoformat()
    })

@tracer.wrap(service="tracing-example", resource="trace_decorator")
def handle_trace_decorator(context):
    """
    GET /trace-decorator - Create a span using decorator
    """
    result = do_some_work()
    
    lambda_metric('endpoint.trace_decorator', 1, tags=['endpoint:trace-decorator'])
    
    return create_response(200, {
        'message': 'Created span with decorator',
        'endpoint': '/trace-decorator',
        'work_result': result,
        'timestamp': datetime.utcnow().isoformat()
    })

@tracer.wrap(service="manual-service", resource="doSomeWork")
def do_some_work():
    """
    Simulates work with custom span
    """
    time.sleep(0.5)
    return {
        'work_completed': True,
        'duration_seconds': 0.5
    }

@tracer.wrap(service="tracing-example", resource="manual_span")
def handle_manual_span(context):
    """
    GET /manual-span - Manually create a span
    """
    with tracer.trace("manual.span", service="manual-service", resource="ManualOperation") as span:
        span.set_tag('state', 'crafted')
        span.set_tag('manual', True)
        span.set_tag('custom.operation', 'manual-span-creation')
        time.sleep(0.3)
        operation_result = 'success'
    
    lambda_metric('endpoint.manual_span', 1, tags=['endpoint:manual-span'])
    
    return create_response(200, {
        'message': 'Manually created span',
        'endpoint': '/manual-span',
        'span_type': 'manual',
        'operation_result': operation_result,
        'timestamp': datetime.utcnow().isoformat()
    })

@tracer.wrap(service="tracing-example", resource="slow")
def handle_slow(context):
    """
    GET /slow - Simulate slow endpoint for latency testing
    """
    start_time = time.time()
    time.sleep(2)
    elapsed = time.time() - start_time
    
    lambda_metric('endpoint.slow.duration', elapsed, tags=['endpoint:slow'])
    
    return create_response(200, {
        'message': 'Slow response after 2 seconds',
        'endpoint': '/slow',
        'delay_seconds': 2,
        'actual_duration': round(elapsed, 2),
        'timestamp': datetime.utcnow().isoformat()
    })

@tracer.wrap(service="tracing-example", resource="health")
def handle_health(context):
    """
    GET /health - Simple health check
    """
    lambda_metric('endpoint.health.check', 1, tags=['status:healthy'])
    
    return create_response(200, {
        'message': 'Service is healthy',
        'endpoint': '/health',
        'status': 'healthy',
        'lambda_function': context.function_name if context else 'unknown',
        'timestamp': datetime.utcnow().isoformat()
    })

@tracer.wrap(service="tracing-example", resource="nested_spans")
def handle_nested_spans(context):
    """
    GET /nested-spans - Create nested spans
    """
    with tracer.trace("parent.operation", service="tracing-example") as parent_span:
        parent_span.set_tag('level', 'parent')
        time.sleep(0.1)
        
        with tracer.trace("child.operation.1", service="tracing-example") as child_span_1:
            child_span_1.set_tag('level', 'child')
            child_span_1.set_tag('child_number', 1)
            time.sleep(0.2)
        
        with tracer.trace("child.operation.2", service="tracing-example") as child_span_2:
            child_span_2.set_tag('level', 'child')
            child_span_2.set_tag('child_number', 2)
            time.sleep(0.15)
    
    lambda_metric('endpoint.nested_spans', 1, tags=['endpoint:nested-spans'])
    
    return create_response(200, {
        'message': 'Created nested spans',
        'endpoint': '/nested-spans',
        'span_structure': 'parent -> child1, child2',
        'timestamp': datetime.utcnow().isoformat()
    })

@tracer.wrap(service="tracing-example", resource="custom_metrics")
def handle_custom_metrics(context):
    """
    GET /custom-metrics - Submit custom metrics
    """
    # Submit various custom metrics
    lambda_metric('custom.counter', 1, tags=['metric_type:counter'])
    lambda_metric('custom.gauge', 42, tags=['metric_type:gauge'])
    lambda_metric('custom.timer', 1.5, tags=['metric_type:timer'])
    
    return create_response(200, {
        'message': 'Custom metrics submitted',
        'endpoint': '/custom-metrics',
        'metrics_submitted': ['custom.counter', 'custom.gauge', 'custom.timer'],
        'timestamp': datetime.utcnow().isoformat()
    })

ROUTES = {
    '/': handle_index,
    '': handle_index,
    '/add-tag': handle_add_tag,
    '/set-error': handle_set_error,
    '/trace-decorator': handle_trace_decorator,
    '/manual-span': handle_manual_span,
    '/nested-spans': handle_nested_spans,
    '/custom-metrics': handle_custom_metrics,
    '/health': handle_health,
    '/slow': handle_slow,
}

def lambda_handler(event, context):
    """
    Main Lambda handler with routing
    """
    app_name = os.environ.get('APP_NAME', 'tracing-example-app')
    path = get_path(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    
    current_span = tracer.current_span()
    if current_span:
        current_span.set_tag('app.name', app_name)
        current_span.set_tag('http.path', path)
        current_span.set_tag('http.method', http_method)
        current_span.set_tag('environment', os.environ.get('ENVIRONMENT', 'unknown'))
    
    lambda_metric(
        metric_name='api.request',
        value=1,
        tags=[f'path:{path}', f'method:{http_method}', f'app:{app_name}']
    )
    
    try:
        handler = ROUTES.get(path)
        
        if handler:
            response = handler(context)
        else:
            lambda_metric('api.unknown_endpoint', 1, tags=[f'path:{path}'])
            response = create_response(404, {
                'error': 'Not Found',
                'message': f'Endpoint {path} not found',
                'available_endpoints': list(ROUTES.keys()),
                'timestamp': datetime.utcnow().isoformat()
            })
        
        if current_span:
            current_span.set_tag('http.status_code', response['statusCode'])
            if response['statusCode'] >= 400:
                current_span.set_tag('error', True)
        
        return response
        
    except Exception as e:
        if current_span:
            current_span.set_tag('error', True)
            current_span.set_tag('error.message', str(e))
            current_span.set_tag('error.type', type(e).__name__)
        
        lambda_metric(
            metric_name='api.error',
            value=1,
            tags=[f'error_type:{type(e).__name__}', f'path:{path}']
        )
        
        return create_response(500, {
            'error': 'Internal Server Error',
            'error_type': type(e).__name__,
            'message': str(e),
            'path': path,
            'timestamp': datetime.utcnow().isoformat()
        })
