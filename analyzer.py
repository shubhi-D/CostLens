import pandas as pd
from aws_cost import get_monthly_costs



def get_real_aws_costs():
    return get_monthly_costs(
        "2026-03-01",
        "2026-09-01"
    )

def load_cost_data():
    df = pd.read_csv("data/costs.csv")

    df["date"] = pd.to_datetime(df["date"])
    df["cost"] = pd.to_numeric(df["cost"])

    return df


def load_resource_data():
    df = pd.read_csv("data/resources.csv")

    df["cpu_utilization"] = pd.to_numeric(df["cpu_utilization"])
    df["memory_utilization"] = pd.to_numeric(df["memory_utilization"])

    return df


def get_total_cost(df):
    return df["cost"].sum()


def get_cost_by_service(df):
    return (
        df.groupby("service")["cost"]
        .sum()
        .sort_values(ascending=False)
    )


def get_cost_by_resource(df):
    return (
        df.groupby(["service", "resource"])["cost"]
        .sum()
        .sort_values(ascending=False)
    )


def find_optimization_opportunities(cost_df, resource_df):

    merged_df = cost_df.merge(
        resource_df,
        on=["resource", "service"],
        how="left"
    )

    opportunities = []

    for _, row in merged_df.iterrows():

        # Rule 1:
        # EC2 instance is running but has very low CPU utilization
        if (
            row["service"] == "EC2"
            and row["cpu_utilization"] < 10
            and row["state"] == "running"
        ):
            opportunities.append({
                "resource": row["resource"],
                "service": row["service"],
                "cost": row["cost"],
                "reason": "Low CPU utilization",
                "recommendation": (
                    "Investigate rightsizing or scheduled shutdown."
                ),
            })

    return pd.DataFrame(opportunities)


if __name__ == "__main__":

    cost_df = load_cost_data()
    resource_df = load_resource_data()

    print("\n=== AWS COSTLENS ===")

    print(f"\nTotal cost: ${get_total_cost(cost_df):.2f}")

    print("\nCost by service:")
    print(get_cost_by_service(cost_df))

    print("\nCost by resource:")
    print(get_cost_by_resource(cost_df))

    print("\n=== OPTIMIZATION OPPORTUNITIES ===")

    opportunities = find_optimization_opportunities(
        cost_df,
        resource_df
    )

    if opportunities.empty:
        print("No optimization opportunities detected.")
    else:
        print(opportunities.to_string(index=False))