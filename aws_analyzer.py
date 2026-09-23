import boto3
import pandas as pd

from datetime import datetime, timedelta, timezone


# ============================================================
# CONFIGURATION
# ============================================================

LOOKBACK_HOURS = 24
CPU_PERIOD = 300  # 5 minutes


# ============================================================
# EC2 INVENTORY
# ============================================================

def get_ec2_inventory():

    session = boto3.Session()

    # Used only to discover enabled regions
    ec2_global = session.client(
        "ec2",
        region_name="us-east-1"
    )

    regions = ec2_global.describe_regions(
        AllRegions=False
    )["Regions"]

    rows = []

    for region_info in regions:

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
                    "name": tags.get("Name", ""),
                    "region": region,
                    "availability_zone": instance.get(
                        "Placement", {}
                    ).get("AvailabilityZone", ""),
                    "instance_type": instance["InstanceType"],
                    "state": instance["State"]["Name"],
                    "launch_time": instance.get("LaunchTime"),
                    "private_ip": instance.get(
                        "PrivateIpAddress",
                        ""
                    ),
                    "public_ip": instance.get(
                        "PublicIpAddress",
                        ""
                    ),
                    "architecture": instance.get(
                        "Architecture",
                        ""
                    ),
                    "platform": instance.get(
                        "PlatformDetails",
                        ""
                    ),
                })

    return pd.DataFrame(rows)


# ============================================================
# CLOUDWATCH METRIC HELPER
# ============================================================

def get_metric_values(
    cloudwatch,
    instance_id,
    metric_name,
    statistic="Average"
):

    end_time = datetime.now(timezone.utc)

    start_time = (
        end_time
        - timedelta(hours=LOOKBACK_HOURS)
    )

    response = cloudwatch.get_metric_data(

        MetricDataQueries=[
            {
                "Id": "metricdata",

                "MetricStat": {

                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": metric_name,

                        "Dimensions": [
                            {
                                "Name": "InstanceId",
                                "Value": instance_id
                            }
                        ]
                    },

                    "Period": CPU_PERIOD,
                    "Stat": statistic
                },

                "ReturnData": True
            }
        ],

        StartTime=start_time,
        EndTime=end_time,

        ScanBy="TimestampAscending"
    )

    results = response.get(
        "MetricDataResults",
        []
    )

    if not results:
        return []

    return results[0].get(
        "Values",
        []
    )


# ============================================================
# CPU METRICS
# ============================================================

def get_cpu_metrics(
    instance_id,
    region
):

    cloudwatch = boto3.client(
        "cloudwatch",
        region_name=region
    )

    values = get_metric_values(
        cloudwatch=cloudwatch,
        instance_id=instance_id,
        metric_name="CPUUtilization",
        statistic="Average"
    )

    if not values:

        return {
            "average_cpu": None,
            "minimum_cpu": None,
            "maximum_cpu": None,
            "cpu_datapoints": 0
        }

    return {
        "average_cpu": sum(values) / len(values),
        "minimum_cpu": min(values),
        "maximum_cpu": max(values),
        "cpu_datapoints": len(values)
    }


# ============================================================
# CPU CREDIT METRICS
# ============================================================

def get_cpu_credit_balance(
    instance_id,
    region
):

    cloudwatch = boto3.client(
        "cloudwatch",
        region_name=region
    )

    values = get_metric_values(
        cloudwatch=cloudwatch,
        instance_id=instance_id,
        metric_name="CPUCreditBalance",
        statistic="Average"
    )

    if not values:
        return None

    # Most recent value
    return values[-1]


# ============================================================
# DATA QUALITY
# ============================================================

def determine_data_quality(
    state,
    cpu_datapoints
):

    if state != "running":

        return "Not applicable"

    if cpu_datapoints == 0:

        return "No data"

    if cpu_datapoints < 10:

        return "Insufficient"

    if cpu_datapoints < 100:

        return "Limited"

    return "Good"


# ============================================================
# OPTIMIZATION SIGNAL
# ============================================================

def determine_optimization_status(row):

    # Never analyze terminated/stopped resources
    if row["state"] != "running":

        return "Not applicable"

    # Don't make recommendations without enough data
    if row["data_quality"] in [
        "No data",
        "Insufficient"
    ]:

        return "Insufficient monitoring data"

    average_cpu = row["average_cpu"]
    maximum_cpu = row["maximum_cpu"]

    if average_cpu is None:

        return "Insufficient monitoring data"

    # Conservative first rule
    if (
        average_cpu < 10
        and maximum_cpu < 30
    ):

        return (
            "Potential low-utilization "
            "optimization opportunity"
        )

    return "No obvious CPU optimization signal"


# ============================================================
# COMPLETE EC2 ANALYSIS
# ============================================================

def analyze_ec2():

    instances = get_ec2_inventory()

    if instances.empty:

        return instances

    analysis_rows = []

    for _, row in instances.iterrows():

        instance_id = row["instance_id"]
        region = row["region"]
        state = row["state"]

        # ----------------------------------------------------
        # Don't query CloudWatch for terminated instances
        # ----------------------------------------------------

        if state != "running":

            analysis_rows.append({
                "average_cpu": None,
                "minimum_cpu": None,
                "maximum_cpu": None,
                "cpu_datapoints": 0,
                "cpu_credit_balance": None
            })

            continue

        print(
            f"Getting CPU metrics for "
            f"{instance_id}..."
        )

        # ----------------------------------------------------
        # CPU
        # ----------------------------------------------------

        cpu = get_cpu_metrics(
            instance_id,
            region
        )

        # ----------------------------------------------------
        # CPU credits
        # ----------------------------------------------------

        cpu_credit_balance = None

        # CPU credit metrics are relevant to
        # burstable instances such as T3.
        if row["instance_type"].startswith(
            ("t2.", "t3.", "t3a.")
        ):

            cpu_credit_balance = (
                get_cpu_credit_balance(
                    instance_id,
                    region
                )
            )

        analysis_rows.append({

            "average_cpu": cpu["average_cpu"],

            "minimum_cpu": cpu["minimum_cpu"],

            "maximum_cpu": cpu["maximum_cpu"],

            "cpu_datapoints": cpu["cpu_datapoints"],

            "cpu_credit_balance": (
                cpu_credit_balance
            )
        })

    metrics_df = pd.DataFrame(
        analysis_rows
    )

    result = pd.concat(
        [
            instances.reset_index(drop=True),
            metrics_df
        ],
        axis=1
    )

    # --------------------------------------------------------
    # Data quality
    # --------------------------------------------------------

    result["data_quality"] = result.apply(
        lambda row: determine_data_quality(
            row["state"],
            row["cpu_datapoints"]
        ),
        axis=1
    )

    # --------------------------------------------------------
    # Optimization status
    # --------------------------------------------------------

    result["optimization_status"] = result.apply(
        determine_optimization_status,
        axis=1
    )

    return result


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    df = analyze_ec2()

    print(
        "\n=== COSTLENS REAL EC2 ANALYSIS ===\n"
    )

    if df.empty:

        print("No EC2 instances found.")

    else:

        # Display important columns first
        columns = [
            "instance_id",
            "name",
            "region",
            "availability_zone",
            "instance_type",
            "state",
            "average_cpu",
            "minimum_cpu",
            "maximum_cpu",
            "cpu_datapoints",
            "cpu_credit_balance",
            "data_quality",
            "optimization_status"
        ]

        print(
            df[columns].to_string(
                index=False
            )
        )