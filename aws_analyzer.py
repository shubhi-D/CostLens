"""
CostLens EC2 analysis engine.

This module converts raw AWS infrastructure and CloudWatch telemetry
into structured optimization signals.

Design principle:
    Collection != Analysis

AWS API modules collect facts.
This module interprets those facts.
The Streamlit application only presents the results.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from aws_metrics import get_ec2_metrics
from aws_resources import (
    get_ec2_instances,
    get_ebs_volumes,
    get_elastic_ips,
)

from config import (
    LOW_CPU_AVERAGE_THRESHOLD,
    LOW_CPU_P95_THRESHOLD,
    LOW_CPU_MAX_THRESHOLD,
    LOW_NETWORK_GIB_PER_DAY,
    LOW_DISK_GIB_PER_DAY,
    MIN_CPU_DATAPOINTS,
    LOW_CPU_CREDIT_BALANCE,
    STOPPED_INSTANCE_REVIEW_DAYS,
    UNATTACHED_VOLUME_REVIEW_DAYS,
)


# ============================================================
# Utility functions
# ============================================================

def _safe_mean(values: List[float]) -> Optional[float]:
    """Return the mean of numeric values or None."""

    if not values:
        return None

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    )

    numeric_values = numeric_values[
        ~pd.isna(numeric_values)
    ]

    if len(numeric_values) == 0:
        return None

    return float(
        np.mean(numeric_values)
    )


def _safe_percentile(
    values: List[float],
    percentile: float,
) -> Optional[float]:
    """Return a percentile or None when no usable data exists."""

    if not values:
        return None

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    )

    numeric_values = numeric_values[
        ~pd.isna(numeric_values)
    ]

    if len(numeric_values) == 0:
        return None

    return float(
        np.percentile(
            numeric_values,
            percentile,
        )
    )


def _safe_sum(values: List[float]) -> float:
    """Return the sum of numeric values."""

    if not values:
        return 0.0

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    )

    numeric_values = numeric_values[
        ~pd.isna(numeric_values)
    ]

    if len(numeric_values) == 0:
        return 0.0

    return float(
        np.sum(numeric_values)
    )


def _bytes_to_gib(value: float) -> float:
    """Convert bytes to GiB."""

    return value / (
        1024 ** 3
    )


def _calculate_data_quality(
    cpu_datapoints: int,
) -> str:
    """
    Determine whether enough CPU telemetry exists to make
    utilization-based recommendations.
    """

    if cpu_datapoints == 0:
        return "No data"

    if cpu_datapoints < MIN_CPU_DATAPOINTS:
        return "Insufficient"

    expected_points = (
        7 * 24 * 60
    ) / 5

    if cpu_datapoints < expected_points * 0.50:
        return "Limited"

    return "Good"


# ============================================================
# EC2 analysis
# ============================================================

def _analyze_single_instance(
    instance: pd.Series,
) -> Dict:
    """
    Analyze one EC2 instance using CloudWatch telemetry.

    Returns a normalized dictionary that can be consumed by
    the dashboard or future APIs.
    """

    instance_id = instance["instance_id"]
    region = instance["region"]
    state = instance["state"]

    result = instance.to_dict()

    # --------------------------------------------------------
    # Non-running instances
    # --------------------------------------------------------

    if state != "running":

        result.update(
            {
                "average_cpu": None,
                "minimum_cpu": None,
                "maximum_cpu": None,
                "p95_cpu": None,
                "cpu_datapoints": 0,
                "network_in_gib_per_day": None,
                "network_out_gib_per_day": None,
                "disk_read_gib_per_day": None,
                "disk_write_gib_per_day": None,
                "cpu_credit_balance": None,
                "cpu_credit_usage": None,
                "data_quality": "Not applicable",
                "optimization_status": (
                    "Not applicable for non-running instance"
                ),
                "optimization_reason": (
                    "Instance is not currently running."
                ),
            }
        )

        return result

    # --------------------------------------------------------
    # CloudWatch metrics
    # --------------------------------------------------------

    metrics = get_ec2_metrics(
        instance_id=instance_id,
        region=region,
    )

    cpu_values = metrics.get(
        "cpu",
        [],
    )

    network_in_values = metrics.get(
        "network_in",
        [],
    )

    network_out_values = metrics.get(
        "network_out",
        [],
    )

    disk_read_values = metrics.get(
        "disk_read",
        [],
    )

    disk_write_values = metrics.get(
        "disk_write",
        [],
    )

    cpu_credit_balance_values = metrics.get(
        "cpu_credit_balance",
        [],
    )

    cpu_credit_usage_values = metrics.get(
        "cpu_credit_usage",
        [],
    )

    # --------------------------------------------------------
    # CPU statistics
    # --------------------------------------------------------

    average_cpu = _safe_mean(
        cpu_values
    )

    minimum_cpu = (
        min(cpu_values)
        if cpu_values
        else None
    )

    maximum_cpu = (
        max(cpu_values)
        if cpu_values
        else None
    )

    p95_cpu = _safe_percentile(
        cpu_values,
        95,
    )

    cpu_datapoints = len(
        cpu_values
    )

    data_quality = _calculate_data_quality(
        cpu_datapoints
    )

    # --------------------------------------------------------
    # Network statistics
    #
    # NetworkIn/NetworkOut are returned as bytes per
    # CloudWatch period when using Sum.
    #
    # We normalize the observation window to GiB/day.
    # --------------------------------------------------------

    total_network_in = _safe_sum(
        network_in_values
    )

    total_network_out = _safe_sum(
        network_out_values
    )

    observation_days = 7

    network_in_gib_per_day = (
        _bytes_to_gib(
            total_network_in
        )
        / observation_days
    )

    network_out_gib_per_day = (
        _bytes_to_gib(
            total_network_out
        )
        / observation_days
    )

    # --------------------------------------------------------
    # Disk statistics
    # --------------------------------------------------------

    total_disk_read = _safe_sum(
        disk_read_values
    )

    total_disk_write = _safe_sum(
        disk_write_values
    )

    disk_read_gib_per_day = (
        _bytes_to_gib(
            total_disk_read
        )
        / observation_days
    )

    disk_write_gib_per_day = (
        _bytes_to_gib(
            total_disk_write
        )
        / observation_days
    )

    # --------------------------------------------------------
    # CPU credits
    # --------------------------------------------------------

    cpu_credit_balance = _safe_mean(
        cpu_credit_balance_values
    )

    cpu_credit_usage = _safe_sum(
        cpu_credit_usage_values
    )

    # --------------------------------------------------------
    # Optimization analysis
    # --------------------------------------------------------

    status, reason = _generate_ec2_signal(
        instance_type=instance[
            "instance_type"
        ],
        average_cpu=average_cpu,
        p95_cpu=p95_cpu,
        maximum_cpu=maximum_cpu,
        network_in_gib_per_day=(
            network_in_gib_per_day
            + network_out_gib_per_day
        ),
        disk_gib_per_day=(
            disk_read_gib_per_day
            + disk_write_gib_per_day
        ),
        cpu_credit_balance=cpu_credit_balance,
        data_quality=data_quality,
    )

    result.update(
        {
            "average_cpu": average_cpu,
            "minimum_cpu": minimum_cpu,
            "maximum_cpu": maximum_cpu,
            "p95_cpu": p95_cpu,
            "cpu_datapoints": cpu_datapoints,
            "network_in_gib_per_day": (
                network_in_gib_per_day
            ),
            "network_out_gib_per_day": (
                network_out_gib_per_day
            ),
            "disk_read_gib_per_day": (
                disk_read_gib_per_day
            ),
            "disk_write_gib_per_day": (
                disk_write_gib_per_day
            ),
            "cpu_credit_balance": (
                cpu_credit_balance
            ),
            "cpu_credit_usage": (
                cpu_credit_usage
            ),
            "data_quality": data_quality,
            "optimization_status": status,
            "optimization_reason": reason,
        }
    )

    return result


def _generate_ec2_signal(
    instance_type: str,
    average_cpu: Optional[float],
    p95_cpu: Optional[float],
    maximum_cpu: Optional[float],
    network_in_gib_per_day: float,
    disk_gib_per_day: float,
    cpu_credit_balance: Optional[float],
    data_quality: str,
) -> tuple[str, str]:
    """
    Generate a conservative EC2 optimization signal.

    The engine deliberately avoids making recommendations when
    telemetry quality is insufficient.

    This function does NOT estimate savings and does NOT perform
    any AWS changes.
    """

    if data_quality in {
        "No data",
        "Insufficient",
    }:

        return (
            "Insufficient monitoring data",
            "More CloudWatch history is required before generating "
            "a utilization-based optimization signal.",
        )

    if (
        average_cpu is None
        or p95_cpu is None
        or maximum_cpu is None
    ):

        return (
            "Insufficient monitoring data",
            "Required CPU statistics are unavailable.",
        )

    # --------------------------------------------------------
    # CPU evidence
    # --------------------------------------------------------

    cpu_is_low = (
        average_cpu
        < LOW_CPU_AVERAGE_THRESHOLD
        and p95_cpu
        < LOW_CPU_P95_THRESHOLD
        and maximum_cpu
        < LOW_CPU_MAX_THRESHOLD
    )

    # --------------------------------------------------------
    # Network evidence
    # --------------------------------------------------------

    network_is_low = (
        network_in_gib_per_day
        < LOW_NETWORK_GIB_PER_DAY
    )

    # --------------------------------------------------------
    # Disk evidence
    # --------------------------------------------------------

    disk_is_low = (
        disk_gib_per_day
        < LOW_DISK_GIB_PER_DAY
    )

    # --------------------------------------------------------
    # CPU credit evidence
    # --------------------------------------------------------

    burstable_instance = (
        instance_type.startswith("t2.")
        or instance_type.startswith("t3.")
        or instance_type.startswith("t3a.")
    )

    healthy_cpu_credits = True

    if (
        burstable_instance
        and cpu_credit_balance is not None
    ):

        healthy_cpu_credits = (
            cpu_credit_balance
            >= LOW_CPU_CREDIT_BALANCE
        )

    # --------------------------------------------------------
    # Stronger multi-signal opportunity
    # --------------------------------------------------------

    if (
        cpu_is_low
        and network_is_low
        and disk_is_low
        and healthy_cpu_credits
    ):

        return (
            "Potential low-utilization optimization opportunity",
            (
                f"CPU utilization is consistently low "
                f"(avg={average_cpu:.2f}%, "
                f"P95={p95_cpu:.2f}%, "
                f"max={maximum_cpu:.2f}%). "
                f"Network and disk activity are also low. "
                f"Review whether the current instance type is "
                f"larger than the workload requires."
            ),
        )

    # --------------------------------------------------------
    # CPU-only signal
    # --------------------------------------------------------

    if cpu_is_low:

        return (
            "Potential CPU rightsizing opportunity",
            (
                f"CPU utilization is consistently low "
                f"(avg={average_cpu:.2f}%, "
                f"P95={p95_cpu:.2f}%, "
                f"max={maximum_cpu:.2f}%), "
                "but other resource signals do not provide "
                "enough evidence for a stronger recommendation."
            ),
        )

    # --------------------------------------------------------
    # No obvious signal
    # --------------------------------------------------------

    return (
        "No obvious optimization signal",
        (
            f"Observed CPU utilization does not meet the "
            f"current low-utilization thresholds "
            f"(avg={average_cpu:.2f}%, "
            f"P95={p95_cpu:.2f}%, "
            f"max={maximum_cpu:.2f}%)."
        ),
    )


# ============================================================
# Public EC2 analysis API
# ============================================================

def analyze_ec2() -> pd.DataFrame:
    """
    Discover and analyze all EC2 instances.

    Returns
    -------
    pandas.DataFrame
        Enriched EC2 inventory containing utilization metrics
        and optimization signals.
    """

    instances = get_ec2_instances()

    if instances.empty:

        return pd.DataFrame()

    analyzed_instances = []

    for _, instance in instances.iterrows():

        analyzed_instances.append(
            _analyze_single_instance(
                instance
            )
        )

    return pd.DataFrame(
        analyzed_instances
    )


# ============================================================
# EBS analysis
# ============================================================

def analyze_ebs() -> pd.DataFrame:
    """
    Identify potentially orphaned EBS volumes.

    No destructive action is taken.
    """

    volumes = get_ebs_volumes()

    if volumes.empty:

        return pd.DataFrame()

    now = datetime.now(
        timezone.utc
    )

    volumes = volumes.copy()

    volumes["create_time"] = pd.to_datetime(
        volumes["create_time"],
        errors="coerce",
        utc=True,
    )

    volumes["age_days"] = (
        now
        - volumes["create_time"]
    ).dt.days

    orphaned = volumes[
        volumes["attached_instance_id"].isna()
        & (
            volumes["age_days"]
            >= UNATTACHED_VOLUME_REVIEW_DAYS
        )
    ].copy()

    if orphaned.empty:

        return pd.DataFrame()

    orphaned[
        "optimization_status"
    ] = "Potential orphaned EBS volume"

    orphaned[
        "optimization_reason"
    ] = (
        "Volume is unattached and has remained "
        "unattached beyond the configured review period."
    )

    return orphaned


# ============================================================
# Elastic IP analysis
# ============================================================

def analyze_elastic_ips() -> pd.DataFrame:
    """
    Identify Elastic IP addresses that are not associated
    with an EC2 resource.
    """

    addresses = get_elastic_ips()

    if addresses.empty:

        return pd.DataFrame()

    unused = addresses[
        addresses["association_id"].isna()
    ].copy()

    if unused.empty:

        return pd.DataFrame()

    unused[
        "optimization_status"
    ] = "Potential unused Elastic IP"

    unused[
        "optimization_reason"
    ] = (
        "Elastic IP is currently not associated "
        "with an AWS resource. Review whether it is required."
    )

    return unused