"""
AWS resource discovery for CostLens.

This module retrieves infrastructure metadata from AWS.

It does not decide whether a resource is optimized or wasteful.
That responsibility belongs to the analysis layer.
"""

from datetime import datetime, timezone
from typing import List

import boto3
import pandas as pd


def _get_all_regions(session) -> List[str]:
    """
    Return all currently enabled AWS regions for the account.
    """

    ec2 = session.client(
        "ec2",
        region_name="us-east-1",
    )

    response = ec2.describe_regions(
        AllRegions=False
    )

    return [
        region["RegionName"]
        for region in response["Regions"]
    ]


def get_ec2_instances() -> pd.DataFrame:
    """
    Discover EC2 instances across all enabled AWS regions.

    Returns
    -------
    pandas.DataFrame
        One row per EC2 instance.
    """

    session = boto3.Session()

    rows = []

    for region in _get_all_regions(session):

        ec2 = session.client(
            "ec2",
            region_name=region,
        )

        response = ec2.describe_instances()

        for reservation in response.get(
            "Reservations",
            [],
        ):

            for instance in reservation.get(
                "Instances",
                [],
            ):

                tags = {
                    tag["Key"]: tag["Value"]
                    for tag in instance.get(
                        "Tags",
                        [],
                    )
                }

                launch_time = instance.get(
                    "LaunchTime"
                )

                rows.append(
                    {
                        "instance_id": instance[
                            "InstanceId"
                        ],
                        "name": tags.get(
                            "Name",
                            "",
                        ),
                        "region": region,
                        "availability_zone": instance.get(
                            "Placement",
                            {},
                        ).get(
                            "AvailabilityZone"
                        ),
                        "instance_type": instance.get(
                            "InstanceType"
                        ),
                        "state": instance.get(
                            "State",
                            {},
                        ).get(
                            "Name"
                        ),
                        "launch_time": launch_time,
                        "private_ip": instance.get(
                            "PrivateIpAddress"
                        ),
                        "public_ip": instance.get(
                            "PublicIpAddress"
                        ),
                        "architecture": instance.get(
                            "Architecture"
                        ),
                        "platform": instance.get(
                            "PlatformDetails"
                        ),
                    }
                )

    return pd.DataFrame(rows)


def get_ebs_volumes() -> pd.DataFrame:
    """
    Discover EBS volumes across all enabled regions.

    The function identifies whether each volume is currently attached
    to an EC2 instance.
    """

    session = boto3.Session()

    rows = []

    for region in _get_all_regions(session):

        ec2 = session.client(
            "ec2",
            region_name=region,
        )

        paginator = ec2.get_paginator(
            "describe_volumes"
        )

        for page in paginator.paginate():

            for volume in page.get(
                "Volumes",
                [],
            ):

                attachments = volume.get(
                    "Attachments",
                    [],
                )

                attached_instance_id = None

                if attachments:

                    attached_instance_id = attachments[
                        0
                    ].get(
                        "InstanceId"
                    )

                create_time = volume.get(
                    "CreateTime"
                )

                rows.append(
                    {
                        "volume_id": volume[
                            "VolumeId"
                        ],
                        "region": region,
                        "availability_zone": volume.get(
                            "AvailabilityZone"
                        ),
                        "volume_type": volume.get(
                            "VolumeType"
                        ),
                        "size_gb": volume.get(
                            "Size"
                        ),
                        "state": volume.get(
                            "State"
                        ),
                        "attached_instance_id": (
                            attached_instance_id
                        ),
                        "create_time": create_time,
                    }
                )

    return pd.DataFrame(rows)


def get_elastic_ips() -> pd.DataFrame:
    """
    Discover Elastic IP addresses across all enabled regions.

    Elastic IPs that are not associated with a resource can represent
    potential cleanup opportunities.
    """

    session = boto3.Session()

    rows = []

    for region in _get_all_regions(session):

        ec2 = session.client(
            "ec2",
            region_name=region,
        )

        response = ec2.describe_addresses()

        for address in response.get(
            "Addresses",
            [],
        ):

            rows.append(
                {
                    "allocation_id": address.get(
                        "AllocationId"
                    ),
                    "public_ip": address.get(
                        "PublicIp"
                    ),
                    "region": region,
                    "instance_id": address.get(
                        "InstanceId"
                    ),
                    "association_id": address.get(
                        "AssociationId"
                    ),
                }
            )

    return pd.DataFrame(rows)