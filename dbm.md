# How to Use

There are two Terraform configurations for Database Monitoring (DBM), depending on your setup preference:

Manual configuration: Use `dbm.tf` if you want to configure Datadog Database Monitoring yourself.

Pre-configured setup: Use `dbm-autoconfig.tf` if you want Database Monitoring to be automatically configured for you.

# Configuration Details
### dbm.tf

This configuration provisions the following resources:
- An EC2 instance
- An Amazon RDS for PostgreSQL instance

The Datadog Agent is pre-installed on the EC2 instance, but Database Monitoring must be configured manually.

**Network and Security:**
- The user can remotely access the EC2 instance.
- The EC2 instance can connect to the RDS database instance.


### dbm-autoconfig.tf

This configuration provisions the following resources:
- An EC2 instance
- An Amazon RDS for PostgreSQL instance

Both the Datadog Agent and Database Monitoring are automatically installed and configured as part of the setup. `pg_stat_statements` is also installed in the RDS database.

**Network and Security:**
- The user can remotely access the EC2 instance.
- The EC2 instance can connect to the RDS database instance.

# Documentations
- Setting Up Database Monitoring for Amazon RDS managed Postgres: https://docs.datadoghq.com/database_monitoring/setup_postgres/rds/
- Troubleshooting DBM Setup for Postgres: https://docs.datadoghq.com/database_monitoring/setup_postgres/troubleshooting/