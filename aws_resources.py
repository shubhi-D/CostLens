import boto3
import pandas as pd


def get_ec2_instances():
    """
    Retrieve real EC2 instances from all enabled AWS regions.
    Read-only.
    """

    session = boto3.Session()

    ec2_global = session.client("ec2", region_name="us-east-1")

    regions_response = ec2_global.describe_regions(
        AllRegions=False
    )

    rows = []

    for region_info in regions_response["Regions"]:

        region = region_info["RegionName"]

        print(f"Checking EC2 resources in {region}...")

        ec2 = session.client(
            "ec2",
            region_name=region
        )

        response = ec2.describe_instances()

        for reservation in response["Reservations"]:

            for instance in reservation["Instances"]:

                tags = {
                    tag["Key"]: tag["Value"]
                    for tag in instance.get("Tags", [])
                }

                rows.append({
                    "instance_id": instance["InstanceId"],
                    "region": region,
                    "instance_type": instance["InstanceType"],
                    "state": instance["State"]["Name"],
                    "name": tags.get("Name", ""),
                })

    return pd.DataFrame(rows)


if __name__ == "__main__":

    df = get_ec2_instances()

    print("\n=== REAL EC2 INSTANCES ===\n")

    if df.empty:
        print("No EC2 instances found.")
    else:
        print(df.to_string(index=False))