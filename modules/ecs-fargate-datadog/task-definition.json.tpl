[
  {
    "name": "datadog-agent",
    "image": "public.ecr.aws/datadog/agent:latest",
    "essential": false,
    "environment": [
      {
        "name": "DD_API_KEY",
        "value": "${datadog_api_key}"
      },
      {
        "name": "DD_SITE",
        "value": "${datadog_site}"
      },
      {
        "name": "DD_APM_ENABLED",
        "value": "true"
      },
      {
        "name": "DD_APM_NON_LOCAL_TRAFFIC",
        "value": "true"
      },
      {
        "name": "DD_DOGSTATSD_NON_LOCAL_TRAFFIC",
        "value": "true"
      },
      {
        "name": "ECS_FARGATE",
        "value": "true"
      }
    ]
  },
  {
    "name": "fastapi-app",
    "image": "${aws_account_id}.dkr.ecr.${aws_region}.amazonaws.com/${app_image}",
    "essential": true,
    "portMappings": [
      {
        "containerPort": 8000,
        "protocol": "tcp"
      }
    ],
    "environment": [
      {
        "name": "DD_AGENT_HOST",
        "value": "localhost"
      },
      {
        "name": "DD_DOGSTATSD_PORT",
        "value": "8125"
      }
    ]
  }
]

