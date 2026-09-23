import boto3
import pandas as pd

from datetime import datetime, timedelta, timezone


# ============================================================
# CONFIGURATION
# ============================================================

LOOKBACK_DAYS = 7


# ============================================================
# GET EC2 RESOURCE-LEVEL COSTS
# ============================================================

def get_ec2_resource_costs(days=LOOKBACK_DAYS):

    ce = boto3.client(
        "ce",
        region_name="us-east-1"
    )

    today = datetime.now(timezone.utc).date()

    start_date = today - timedelta(days=days)
    end_date = today

    rows = []

    next_page_token = None

    while True:

        request = {
            "TimePeriod": {
                "Start": start_date.strftime("%Y-%m-%d"),
                "End": end_date.strftime("%Y-%m-%d")
            },

            "Granularity": "DAILY",

            "Metrics": [
                "UnblendedCost"
            ],

            "Filter": {
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": [
                        "Amazon Elastic Compute Cloud - Compute"
                    ]
                }
            },

            "GroupBy": [
                {
                    "Type": "DIMENSION",
                    "Key": "RESOURCE_ID"
                }
            ]
        }

        if next_page_token:
            request["NextPageToken"] = next_page_token

        response = ce.get_cost_and_usage_with_resources(
            **request
        )

        for period in response.get(
            "ResultsByTime",
            []
        ):

            date = period[
                "TimePeriod"
            ]["Start"]

            for group in period.get(
                "Groups",
                []
            ):

                resource_id = group[
                    "Keys"
                ][0]

                cost = float(
                    group[
                        "Metrics"
                    ]["UnblendedCost"]["Amount"]
                )

                rows.append({
                    "date": date,
                    "resource_id": resource_id,
                    "cost": cost
                })

        next_page_token = response.get(
            "NextPageToken"
        )

        if not next_page_token:
            break

    return pd.DataFrame(rows)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "\n=== COSTLENS EC2 RESOURCE COSTS ===\n"
    )

    try:

        df = get_ec2_resource_costs()

        if df.empty:

            print(
                "No EC2 resource-level cost data returned."
            )

        else:

            print(
                df.to_string(index=False)
            )

            print(
                "\n=== COST BY RESOURCE ===\n"
            )

            cost_by_resource = (
                df.groupby("resource_id")["cost"]
                .sum()
                .sort_values(
                    ascending=False
                )
            )

            print(
                cost_by_resource.to_string()
            )

    except Exception as e:

        print(
            "\nERROR:\n"
        )

        print(e)