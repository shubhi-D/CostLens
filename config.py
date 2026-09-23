"""
Application configuration for CostLens.

Centralizing configuration makes the analysis engine easier to tune,
test, and maintain as the project grows.
"""

# -------------------------------------------------------------------
# CloudWatch configuration
# -------------------------------------------------------------------

# Number of days of historical CloudWatch data used for analysis.
LOOKBACK_DAYS = 7

# Basic EC2 monitoring uses 5-minute intervals.
METRIC_PERIOD_SECONDS = 300

# -------------------------------------------------------------------
# Data quality thresholds
# -------------------------------------------------------------------

# Minimum number of CPU datapoints required before generating
# utilization-based optimization signals.
MIN_CPU_DATAPOINTS = 100

# -------------------------------------------------------------------
# CPU optimization thresholds
# -------------------------------------------------------------------

LOW_CPU_AVERAGE_THRESHOLD = 10.0
LOW_CPU_P95_THRESHOLD = 20.0
LOW_CPU_MAX_THRESHOLD = 30.0

# -------------------------------------------------------------------
# Network optimization thresholds
# -------------------------------------------------------------------

# Total network traffic below this value is considered low.
# Unit: GiB/day.
LOW_NETWORK_GIB_PER_DAY = 0.1

# -------------------------------------------------------------------
# Disk optimization thresholds
# -------------------------------------------------------------------

# Total disk throughput below this value is considered low.
# Unit: GiB/day.
LOW_DISK_GIB_PER_DAY = 0.1

# -------------------------------------------------------------------
# Resource age / cleanup thresholds
# -------------------------------------------------------------------

# A stopped instance older than this many days is flagged for review.
STOPPED_INSTANCE_REVIEW_DAYS = 14

# An unattached EBS volume older than this many days is flagged.
UNATTACHED_VOLUME_REVIEW_DAYS = 7

# -------------------------------------------------------------------
# T-series CPU credit thresholds
# -------------------------------------------------------------------

# A low CPU-credit balance can indicate sustained burst usage.
LOW_CPU_CREDIT_BALANCE = 20.0