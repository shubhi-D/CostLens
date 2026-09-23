import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

from aws_cost import get_monthly_costs
from aws_analyzer import analyze_ec2


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AWS CostLens",
    page_icon="💰",
    layout="wide",
)


# ============================================================
# HEADER
# ============================================================

st.title("💰 AWS CostLens")

st.caption(
    "AWS Infrastructure Cost Optimization POC"
)

st.divider()


# ============================================================
# LOAD REAL AWS DATA
# ============================================================

@st.cache_data(ttl=300)
def load_aws_costs():

    return get_monthly_costs(
        "2026-03-01",
        "2026-10-01"
    )


@st.cache_data(ttl=300)
def load_ec2_analysis():

    return analyze_ec2()


try:

    cost_df = load_aws_costs()

except Exception as e:

    st.error(
        f"Unable to retrieve AWS Cost Explorer data: {e}"
    )

    st.stop()


try:

    ec2_df = load_ec2_analysis()

except Exception as e:

    st.error(
        f"Unable to retrieve EC2 / CloudWatch data: {e}"
    )

    st.stop()


# ============================================================
# PREPARE COST DATA
# ============================================================

if cost_df.empty:

    st.warning(
        "No AWS cost data was returned."
    )

    total_cost = 0

    service_costs = pd.DataFrame()

else:

    total_cost = cost_df["cost"].sum()

    service_costs = (
        cost_df
        .groupby("service")["cost"]
        .sum()
        .sort_values(ascending=False)
    )


# ============================================================
# PREPARE EC2 DATA
# ============================================================

if ec2_df.empty:

    running_ec2 = ec2_df

else:

    running_ec2 = ec2_df[
        ec2_df["state"] == "running"
    ].copy()


# Count actual running instances
running_instance_count = len(running_ec2)


# Count optimization signals
optimization_count = 0

if not running_ec2.empty:

    optimization_count = len(
        running_ec2[
            running_ec2[
                "optimization_status"
            ].str.contains(
                "opportunity",
                na=False
            )
        ]
    )


# ============================================================
# KPI CARDS
# ============================================================

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "AWS Cost",
        f"${total_cost:.2f}"
    )


with col2:

    st.metric(
        "AWS Services",
        cost_df["service"].nunique()
        if not cost_df.empty
        else 0
    )


with col3:

    st.metric(
        "Running EC2",
        running_instance_count
    )


with col4:

    st.metric(
        "Optimization Signals",
        optimization_count
    )


st.divider()


# ============================================================
# AWS COST BY SERVICE
# ============================================================

st.subheader("💵 AWS Cost by Service")


if service_costs.empty:

    st.info(
        "No service-level cost data available."
    )

else:

    service_df = (
        service_costs
        .reset_index()
    )

    service_df.columns = [
        "Service",
        "Cost"
    ]

    fig_service = px.bar(
        service_df,
        x="Service",
        y="Cost",
        title="AWS Cost by Service",
    )

    fig_service.update_layout(
        xaxis_title="AWS Service",
        yaxis_title="Cost (USD)"
    )

    st.plotly_chart(
        fig_service,
        use_container_width=True
    )


# ============================================================
# MONTHLY COST TREND
# ============================================================

st.subheader("📈 Monthly AWS Cost")


if not cost_df.empty:

    monthly_cost = (
        cost_df
        .groupby("month")["cost"]
        .sum()
        .reset_index()
    )

    monthly_cost["month"] = pd.to_datetime(
        monthly_cost["month"]
    )

    fig_monthly = px.line(
        monthly_cost,
        x="month",
        y="cost",
        markers=True,
        title="Monthly AWS Cost"
    )

    fig_monthly.update_layout(
        xaxis_title="Month",
        yaxis_title="Cost (USD)"
    )

    st.plotly_chart(
        fig_monthly,
        use_container_width=True
    )


# ============================================================
# EC2 INVENTORY
# ============================================================

st.divider()

st.subheader("🖥️ Real EC2 Infrastructure")


if ec2_df.empty:

    st.info(
        "No EC2 instances found."
    )

else:

    display_columns = [
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
    ]

    display_df = ec2_df[
        display_columns
    ].copy()

    # Round CPU values
    for column in [
        "average_cpu",
        "minimum_cpu",
        "maximum_cpu",
        "cpu_credit_balance"
    ]:

        display_df[column] = display_df[
            column
        ].round(2)

    display_df = display_df.rename(
        columns={
            "instance_id": "Instance ID",
            "name": "Name",
            "region": "Region",
            "availability_zone": "AZ",
            "instance_type": "Type",
            "state": "State",
            "average_cpu": "Avg CPU %",
            "minimum_cpu": "Min CPU %",
            "maximum_cpu": "Max CPU %",
            "cpu_datapoints": "CPU Datapoints",
            "cpu_credit_balance": "CPU Credits",
            "data_quality": "Data Quality",
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# OPTIMIZATION ANALYSIS
# ============================================================

st.divider()

st.subheader(
    "🔍 Infrastructure Optimization Analysis"
)


if running_ec2.empty:

    st.info(
        "No running EC2 instances available "
        "for optimization analysis."
    )

else:

    for _, row in running_ec2.iterrows():

        with st.container(border=True):

            col1, col2 = st.columns(
                [1, 3]
            )

            # ------------------------------------------------
            # LEFT
            # ------------------------------------------------

            with col1:

                st.write(
                    f"### {row['name'] or row['instance_id']}"
                )

                st.caption(
                    row["instance_id"]
                )

                st.write(
                    f"**Type:** "
                    f"{row['instance_type']}"
                )

                st.write(
                    f"**Region:** "
                    f"{row['region']}"
                )

            # ------------------------------------------------
            # RIGHT
            # ------------------------------------------------

            with col2:

                metric1, metric2, metric3 = (
                    st.columns(3)
                )

                with metric1:

                    if pd.notna(
                        row["average_cpu"]
                    ):

                        st.metric(
                            "Avg CPU",
                            f"{row['average_cpu']:.2f}%"
                        )

                    else:

                        st.metric(
                            "Avg CPU",
                            "N/A"
                        )

                with metric2:

                    if pd.notna(
                        row["maximum_cpu"]
                    ):

                        st.metric(
                            "Max CPU",
                            f"{row['maximum_cpu']:.2f}%"
                        )

                    else:

                        st.metric(
                            "Max CPU",
                            "N/A"
                        )

                with metric3:

                    if pd.notna(
                        row["cpu_credit_balance"]
                    ):

                        st.metric(
                            "CPU Credits",
                            f"{row['cpu_credit_balance']:.2f}"
                        )

                    else:

                        st.metric(
                            "CPU Credits",
                            "N/A"
                        )

                st.write(
                    f"**Data quality:** "
                    f"{row['data_quality']}"
                )

                status = row[
                    "optimization_status"
                ]

                if "opportunity" in status.lower():

                    st.warning(
                        f"⚠️ {status}"
                    )

                elif "insufficient" in status.lower():

                    st.info(
                        f"ℹ️ {status}"
                    )

                else:

                    st.success(
                        f"✅ {status}"
                    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "CostLens reads AWS Cost Explorer, EC2 inventory, "
    "and CloudWatch metrics. Recommendations are "
    "potential optimization signals, not automatic actions."
)