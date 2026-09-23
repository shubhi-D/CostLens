"""
CloudWatch metric collection for EC2 resources.

This module is responsible only for retrieving AWS telemetry.

It intentionally does not contain optimization business logic.
Keeping collection separate from analysis makes the system easier
to test and extend.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List

import boto3

from config import (
    LOOKBACK_DAYS,
    METRIC_PERIOD_SECONDS,
)


# -------------------------------------------------------------------
# Metric definitions
# -------------------------------------------------------------------

EC2_METRICS = {
    "cpu": {
        "metric_name": "CPUUtilization",
        "stat": "Average",
    },
    "network_in": {
        "metric_name": "NetworkIn",
        "stat": "Sum",
    },
    "network_out": {
        "metric_name": "NetworkOut",
        "stat": "Sum",
    },
    "disk_read": {
        "metric_name": "DiskReadBytes",
        "stat": "Sum",
    },
    "disk_write": {
        "metric_name": "DiskWriteBytes",
        "stat": "Sum",
    },
    "cpu_credit_balance": {
        "metric_name": "CPUCreditBalance",
        "stat": "Average",
    },
    "cpu_credit_usage": {
        "metric_name": "CPUCreditUsage",
        "stat": "Sum",
    },
}


def _build_metric_query(
    query_id: str,
    metric_name: str,
    statistic: str,
    instance_id: str,
) -> dict:
    """
    Build a CloudWatch GetMetricData query for one EC2 metric.
    """

    return {
        "Id": query_id,
        "MetricStat": {
            "Metric": {
                "Namespace": "AWS/EC2",
                "MetricName": metric_name,
                "Dimensions": [
                    {
                        "Name": "InstanceId",
                        "Value": instance_id,
                    }
                ],
            },
            "Period": METRIC_PERIOD_SECONDS,
            "Stat": statistic,
        },
        "ReturnData": True,
    }


def _get_metric_data(
    cloudwatch,
    queries: List[dict],
    start_time: datetime,
    end_time: datetime,
) -> Dict[str, List[float]]:
    """
    Retrieve CloudWatch metric data using GetMetricData.

    The API supports multiple metrics in a single request, which is
    more efficient than making one API call per metric.
    """

    results: Dict[str, List[float]] = {
        query["Id"]: []
        for query in queries
    }

    next_token = None

    while True:

        request = {
            "StartTime": start_time,
            "EndTime": end_time,
            "MetricDataQueries": queries,
            "ScanBy": "TimestampDescending",
        }

        if next_token:
            request["NextToken"] = next_token

        response = cloudwatch.get_metric_data(**request)

        for metric_result in response.get(
            "MetricDataResults",
            [],
        ):

            metric_id = metric_result["Id"]

            values = metric_result.get(
                "Values",
                [],
            )

            results.setdefault(
                metric_id,
                [],
            ).extend(values)

        next_token = response.get(
            "NextToken"
        )

        if not next_token:
            break

    return results


def get_ec2_metrics(
    instance_id: str,
    region: str,
) -> Dict[str, List[float]]:
    """
    Retrieve the configured CloudWatch metrics for one EC2 instance.

    Parameters
    ----------
    instance_id:
        EC2 instance ID.

    region:
        AWS region containing the instance.

    Returns
    -------
    dict
        Mapping between logical metric names and datapoint lists.
    """

    session = boto3.Session()

    cloudwatch = session.client(
        "cloudwatch",
        region_name=region,
    )

    end_time = datetime.now(
        timezone.utc
    )

    start_time = end_time - timedelta(
        days=LOOKBACK_DAYS
    )

    queries = []

    query_mapping = {}

    for index, (
        logical_name,
        metric_config,
    ) in enumerate(
        EC2_METRICS.items(),
        start=1,
    ):

        query_id = f"metric{index}"

        queries.append(
            _build_metric_query(
                query_id=query_id,
                metric_name=metric_config["metric_name"],
                statistic=metric_config["stat"],
                instance_id=instance_id,
            )
        )

        query_mapping[
            query_id
        ] = logical_name

    raw_results = _get_metric_data(
        cloudwatch=cloudwatch,
        queries=queries,
        start_time=start_time,
        end_time=end_time,
    )

    metrics = {}

    for query_id, values in raw_results.items():

        logical_name = query_mapping.get(
            query_id
        )

        if logical_name:
            metrics[logical_name] = values

    return metrics