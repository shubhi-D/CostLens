"""
Unit tests for the CostLens optimization decision engine.

These tests intentionally avoid calling AWS.

The goal is to verify that the analysis logic produces the
expected optimization signal for different telemetry scenarios.
"""

from aws_analyzer import _generate_ec2_signal


def test_insufficient_monitoring_data():
    """
    CostLens must not make a utilization recommendation when
    there is not enough CloudWatch data.
    """

    status, reason = _generate_ec2_signal(
        instance_type="t3.micro",
        average_cpu=1.0,
        p95_cpu=2.0,
        maximum_cpu=5.0,
        network_in_gib_per_day=0.01,
        disk_gib_per_day=0.01,
        cpu_credit_balance=50.0,
        data_quality="Insufficient",
    )

    assert status == "Insufficient monitoring data"
    assert "CloudWatch history" in reason


def test_low_utilization_instance():
    """
    A well-observed instance with consistently low CPU,
    network, and disk activity should produce a potential
    low-utilization optimization signal.
    """

    status, reason = _generate_ec2_signal(
        instance_type="t3.micro",
        average_cpu=5.0,
        p95_cpu=8.0,
        maximum_cpu=12.0,
        network_in_gib_per_day=0.01,
        disk_gib_per_day=0.01,
        cpu_credit_balance=50.0,
        data_quality="Good",
    )

    assert status == "Potential low-utilization optimization opportunity"
    assert "CPU utilization is consistently low" in reason


def test_high_cpu_instance():
    """
    An instance with high CPU utilization should not be flagged
    as a low-utilization optimization opportunity.
    """

    status, reason = _generate_ec2_signal(
        instance_type="t3.micro",
        average_cpu=65.0,
        p95_cpu=80.0,
        maximum_cpu=95.0,
        network_in_gib_per_day=2.0,
        disk_gib_per_day=1.0,
        cpu_credit_balance=50.0,
        data_quality="Good",
    )

    assert status == "No obvious optimization signal"


def test_low_cpu_but_high_network():
    """
    Low CPU alone should not automatically produce the stronger
    low-utilization signal when network activity is significant.
    """

    status, reason = _generate_ec2_signal(
        instance_type="t3.micro",
        average_cpu=5.0,
        p95_cpu=8.0,
        maximum_cpu=12.0,
        network_in_gib_per_day=2.0,
        disk_gib_per_day=0.01,
        cpu_credit_balance=50.0,
        data_quality="Good",
    )

    assert status == "Potential CPU rightsizing opportunity"


def test_low_cpu_but_high_disk():
    """
    Low CPU alone should not produce the stronger optimization
    signal when disk activity is significant.
    """

    status, reason = _generate_ec2_signal(
        instance_type="t3.micro",
        average_cpu=5.0,
        p95_cpu=8.0,
        maximum_cpu=12.0,
        network_in_gib_per_day=0.01,
        disk_gib_per_day=2.0,
        cpu_credit_balance=50.0,
        data_quality="Good",
    )

    assert status == "Potential CPU rightsizing opportunity"


from unittest.mock import patch

import pandas as pd

from aws_analyzer import analyze_ebs, analyze_elastic_ips


@patch("aws_analyzer.get_ebs_volumes")
def test_unattached_old_ebs_volume(mock_get_volumes):
    """
    An unattached EBS volume older than the review threshold
    should produce an optimization finding.
    """

    mock_get_volumes.return_value = pd.DataFrame(
        [
            {
                "volume_id": "vol-test-001",
                "region": "ap-south-1",
                "availability_zone": "ap-south-1a",
                "volume_type": "gp3",
                "size_gb": 20,
                "state": "available",
                "attached_instance_id": None,
                "create_time": pd.Timestamp.now(tz="UTC")
                - pd.Timedelta(days=30),
            }
        ]
    )

    result = analyze_ebs()

    assert len(result) == 1
    assert result.iloc[0]["volume_id"] == "vol-test-001"
    assert result.iloc[0]["optimization_status"] == (
        "Potential orphaned EBS volume"
    )


@patch("aws_analyzer.get_ebs_volumes")
def test_recent_unattached_ebs_volume_not_flagged(mock_get_volumes):
    """
    A recently created unattached volume should not immediately
    be considered an orphaned resource.
    """

    mock_get_volumes.return_value = pd.DataFrame(
        [
            {
                "volume_id": "vol-test-002",
                "region": "ap-south-1",
                "availability_zone": "ap-south-1a",
                "volume_type": "gp3",
                "size_gb": 20,
                "state": "available",
                "attached_instance_id": None,
                "create_time": pd.Timestamp.now(tz="UTC")
                - pd.Timedelta(days=1),
            }
        ]
    )

    result = analyze_ebs()

    assert result.empty


@patch("aws_analyzer.get_ebs_volumes")
def test_attached_ebs_volume_not_flagged(mock_get_volumes):
    """
    An attached EBS volume should not be considered orphaned.
    """

    mock_get_volumes.return_value = pd.DataFrame(
        [
            {
                "volume_id": "vol-test-003",
                "region": "ap-south-1",
                "availability_zone": "ap-south-1a",
                "volume_type": "gp3",
                "size_gb": 20,
                "state": "in-use",
                "attached_instance_id": "i-test-001",
                "create_time": pd.Timestamp.now(tz="UTC")
                - pd.Timedelta(days=30),
            }
        ]
    )

    result = analyze_ebs()

    assert result.empty


@patch("aws_analyzer.get_elastic_ips")
def test_unused_elastic_ip(mock_get_ips):
    """
    An Elastic IP without an association should produce
    an optimization finding.
    """

    mock_get_ips.return_value = pd.DataFrame(
        [
            {
                "allocation_id": "eipalloc-test-001",
                "public_ip": "203.0.113.10",
                "region": "ap-south-1",
                "instance_id": None,
                "association_id": None,
            }
        ]
    )

    result = analyze_elastic_ips()

    assert len(result) == 1
    assert result.iloc[0]["public_ip"] == "203.0.113.10"
    assert result.iloc[0]["optimization_status"] == (
        "Potential unused Elastic IP"
    )


@patch("aws_analyzer.get_elastic_ips")
def test_associated_elastic_ip_not_flagged(mock_get_ips):
    """
    An associated Elastic IP should not be flagged as unused.
    """

    mock_get_ips.return_value = pd.DataFrame(
        [
            {
                "allocation_id": "eipalloc-test-002",
                "public_ip": "203.0.113.11",
                "region": "ap-south-1",
                "instance_id": "i-test-001",
                "association_id": "eipassoc-test-001",
            }
        ]
    )

    result = analyze_elastic_ips()

    assert result.empty