EC2 instance running Forwardog

- **AMI:** Amazon Linux 2023 (Standard)
- **Architecture:** x86_64

After deploying the resource, you can access the Forwardog service using the endpoint provided as "forwardog_url" in the resource outputs.

Ensure that port 8000 is open in the associated security group for your IP address to allow connectivity to the Forwardog service.

For more information about Forwardog, check out below link:
- https://github.com/chanhyeokseo/forwardog