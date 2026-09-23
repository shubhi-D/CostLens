# CostLens

CostLens is an AWS cloud cost optimization POC that combines AWS billing data,
EC2 infrastructure metadata, and CloudWatch utilization metrics to identify
potential infrastructure optimization opportunities.

The goal is to move beyond simple cost visualization and correlate:

**AWS Spend → Infrastructure → Utilization → Optimization Signals**

---

## Problem

AWS Cost Explorer provides visibility into account-level and service-level
spending, but cost alone does not explain whether a resource is being
efficiently utilized.

For example:

- An EC2 instance may have ongoing compute costs.
- The instance may have very low CPU utilization.
- However, making an optimization recommendation without sufficient monitoring
  data could be misleading.

CostLens combines billing and infrastructure telemetry to provide
evidence-based optimization signals.

---

## Current Capabilities

### 1. AWS Cost Visibility

CostLens retrieves real AWS Cost Explorer data and displays:

- Total AWS spend for the selected period
- Cost by AWS service
- Monthly cost trends

AWS Cost Explorer supports grouping and filtering cost and usage data by
dimensions such as service. CostLens currently uses the AWS Cost Explorer API
for this data.

### 2. Real EC2 Inventory

CostLens discovers EC2 instances across enabled AWS regions and collects:

- Instance ID
- Instance name
- Region
- Availability Zone
- Instance type
- Instance state
- Launch time
- Private IP
- Public IP
- Architecture
- Platform

### 3. CloudWatch Utilization Analysis

For running EC2 instances, CostLens retrieves CloudWatch metrics including:

- Average CPU utilization
- Minimum CPU utilization
- Maximum CPU utilization
- Number of CPU datapoints
- CPU credit balance for burstable instances

### 4. Data Quality Assessment

CostLens evaluates whether enough monitoring data exists before generating
optimization signals.

Possible states include:

- Good
- Limited
- Insufficient
- No data
- Not applicable

This prevents the system from making recommendations based on very limited
monitoring history.

### 5. Optimization Signals

The current optimization engine uses conservative rules.

For example, a running EC2 instance may be identified as a potential
low-utilization optimization opportunity when:

- Average CPU utilization is below 10%
- Maximum CPU utilization is below 30%
- Sufficient monitoring data is available

CostLens does not automatically modify or terminate resources.

Recommendations are presented as:

> Potential optimization opportunities

rather than definitive cost-saving actions.

---

## Architecture

```text
                         AWS Account
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
       Cost Explorer        EC2 API        CloudWatch
             |                |                |
             v                v                v
        AWS Spend        Infrastructure    Utilization
        by Service          Metadata         Metrics
             |                |                |
             +----------------+----------------+
                              |
                              v
                    CostLens Analysis Engine
                              |
                              v
                  Optimization Signals
                              |
                              v
                       Streamlit Dashboard