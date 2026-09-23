import boto3
from datetime import datetime, timedelta, timezone


def get_average_cpu(instance_id, region, hours=24):

    cloudwatch = boto3.client(
        "cloudwatch",
        region_name=region
    )

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[
            {
                "Name": "InstanceId",
                "Value": instance_id
            }
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=300,
        Statistics=["Average"],
        Unit="Percent"
    )

    datapoints = response.get("Datapoints", [])

    if not datapoints:
        return None

    average_cpu = sum(
        point["Average"]
        for point in datapoints
    ) / len(datapoints)

    return average_cpu


if __name__ == "__main__":

    instance_id = "i-0d7c8a9ad918e03a9"
    region = "ap-south-1"

    cpu = get_average_cpu(
        instance_id,
        region,
        hours=24
    )

    print("\n=== REAL EC2 METRICS ===\n")

    if cpu is None:
        print("No CPU data available yet.")

    else:
        print(f"Instance: {instance_id}")
        print(f"Region: {region}")
        print(f"Average CPU (24h): {cpu:.2f}%")