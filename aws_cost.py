import boto3
import pandas as pd


def get_monthly_costs(start_date, end_date):
    """
    Get monthly AWS costs grouped by service.

    start_date: YYYY-MM-DD
    end_date: YYYY-MM-DD
    """

    ce = boto3.client("ce", region_name="us-east-1")

    response = ce.get_cost_and_usage(
        TimePeriod={
            "Start": start_date,
            "End": end_date,
        },
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[
            {
                "Type": "DIMENSION",
                "Key": "SERVICE",
            }
        ],
    )

    rows = []

    for period in response["ResultsByTime"]:

        month = period["TimePeriod"]["Start"]

        for group in period["Groups"]:

            service = group["Keys"][0]

            amount = float(
                group["Metrics"]["UnblendedCost"]["Amount"]
            )

            rows.append({
                "month": month,
                "service": service,
                "cost": amount,
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":

    df = get_monthly_costs(
        "2026-03-01",
        "2026-09-01"
    )

    print("\n=== AWS COSTLENS — REAL AWS DATA ===\n")

    print(df.to_string(index=False))

    print("\n=== TOTAL COST BY SERVICE ===\n")

    service_totals = (
        df.groupby("service")["cost"]
        .sum()
        .sort_values(ascending=False)
    )

    print(service_totals)