import os

import boto3
import pandas as pd
import plotly.express as px
import streamlit as st

from aws_cost import get_monthly_costs
from aws_analyzer import (
    analyze_ec2,
    analyze_ebs,
    analyze_elastic_ips,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AWS CostLens",
    page_icon="💰",
    layout="wide",
)


# ============================================================
# AWS SAFETY CHECK
# ============================================================

aws_profile = os.getenv("AWS_PROFILE")

if aws_profile != "personal":
    st.error("🛑 CostLens was stopped for safety.")
    st.warning(
        "AWS_PROFILE is not set to 'personal'. "
        "The application will not run because it could accidentally "
        "connect to another AWS account."
    )

    st.code(
        '$env:AWS_PROFILE="personal"\n'
        "aws sts get-caller-identity\n"
        "streamlit run app.py",
        language="powershell",
    )

    st.stop()


# Verify the AWS identity actually being used.
# This prevents CostLens from silently running against
# an unexpected AWS account or credential configuration.
try:
    sts = boto3.client("sts")
    sts.get_caller_identity()

except Exception as e:
    st.error(f"Unable to verify AWS identity: {e}")
    st.stop()


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
        "2026-10-01",
    )


@st.cache_data(ttl=300)
def load_ec2_analysis():

    return analyze_ec2()

@st.cache_data(ttl=300)
def load_ebs_analysis():
    """Load potential orphaned EBS findings."""
    return analyze_ebs()


@st.cache_data(ttl=300)
def load_elastic_ip_analysis():
    """Load potential unused Elastic IP findings."""
    return analyze_elastic_ips()


# ============================================================
# LOAD AWS COST DATA
# ============================================================

try:

    cost_df = load_aws_costs()

except Exception as e:

    st.error(
        f"Unable to retrieve AWS Cost Explorer data: {e}"
    )

    st.stop()


# ============================================================
# LOAD EC2 DATA
# ============================================================

try:

    ec2_df = load_ec2_analysis()

except Exception as e:

    st.error(
        f"Unable to retrieve EC2 / CloudWatch data: {e}"
    )

    st.stop()


# ============================================================
# LOAD EBS DATA
# ============================================================

try:

    ebs_df = load_ebs_analysis()

except Exception as e:

    st.error(
        f"Unable to retrieve EBS data: {e}"
    )

    st.stop()


# ============================================================
# LOAD ELASTIC IP DATA
# ============================================================

try:

    elastic_ip_df = load_elastic_ip_analysis()

except Exception as e:

    st.error(
        f"Unable to retrieve Elastic IP data: {e}"
    )

    st.stop()


# ============================================================
# PREPARE COST DATA
# ============================================================

if cost_df is None or cost_df.empty:

    st.warning(
        "No AWS cost data was returned."
    )

    total_cost = 0.0
    service_costs = pd.DataFrame()

else:

    cost_df = cost_df.copy()

    cost_df["cost"] = pd.to_numeric(
        cost_df["cost"],
        errors="coerce",
    ).fillna(0)

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

if ec2_df is None or ec2_df.empty:

    ec2_df = pd.DataFrame()

    running_ec2 = pd.DataFrame()

else:

    ec2_df = ec2_df.copy()

    if "state" in ec2_df.columns:

        running_ec2 = ec2_df[
            ec2_df["state"].astype(str).str.lower() == "running"
        ].copy()

    else:

        running_ec2 = pd.DataFrame()


# Count actual running instances
running_instance_count = len(running_ec2)


# ============================================================
# COUNT OPTIMIZATION SIGNALS
# ============================================================

optimization_count = 0

if not running_ec2.empty and "optimization_status" in running_ec2.columns:

    optimization_count = len(
        running_ec2[
            running_ec2["optimization_status"]
            .astype(str)
            .str.contains(
                "opportunity",
                case=False,
                na=False,
            )
        ]
    )


# ============================================================
# KPI CARDS
# ============================================================

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "AWS Spend (Selected Period)",
        f"${total_cost:,.2f}",
    )


with col2:

    st.metric(
        "AWS Services",
        cost_df["service"].nunique()
        if not cost_df.empty and "service" in cost_df.columns
        else 0,
    )


with col3:

    st.metric(
        "Running EC2",
        running_instance_count,
    )


with col4:

    st.metric(
        "Optimization Signals",
        optimization_count,
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
        "Cost",
    ]

    fig_service = px.bar(
        service_df,
        x="Service",
        y="Cost",
        title="AWS Cost by Service",
    )

    fig_service.update_layout(
        xaxis_title="AWS Service",
        yaxis_title="Cost (USD)",
    )

    st.plotly_chart(
        fig_service,
        width="stretch",
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
        monthly_cost["month"],
        errors="coerce",
    )

    fig_monthly = px.line(
        monthly_cost,
        x="month",
        y="cost",
        markers=True,
        title="Monthly AWS Cost",
    )

    fig_monthly.update_layout(
        xaxis_title="Month",
        yaxis_title="Cost (USD)",
    )

    st.plotly_chart(
        fig_monthly,
        width="stretch",
    )


# ============================================================
# EC2 INVENTORY
# ============================================================

st.divider()

st.subheader("🖥️ Real EC2 Infrastructure")


if ec2_df.empty:

    st.info(
        "No EC2 instances found in the AWS account."
    )

else:

    # These are the fields we WANT to display.
    # Missing fields will be created automatically.
    display_columns = [
    "instance_id",
    "name",
    "region",
    "availability_zone",
    "instance_type",
    "state",
    "average_cpu",
    "p95_cpu",
    "maximum_cpu",
    "network_in_gib_per_day",
    "network_out_gib_per_day",
    "disk_read_gib_per_day",
    "disk_write_gib_per_day",
    "cpu_credit_balance",
    "cpu_credit_usage",
    "cpu_datapoints",
    "data_quality",
    "optimization_status",
]

    # Reindex instead of directly selecting columns.
    # This prevents KeyError when a field is missing.
    display_df = ec2_df.reindex(
        columns=display_columns
    ).copy()

    # --------------------------------------------------------
    # Safely convert numeric fields
    # --------------------------------------------------------

    numeric_columns = [
    "average_cpu",
    "p95_cpu",
    "maximum_cpu",
    "network_in_gib_per_day",
    "network_out_gib_per_day",
    "disk_read_gib_per_day",
    "disk_write_gib_per_day",
    "cpu_credit_balance",
    "cpu_credit_usage",
    "cpu_datapoints",
]

    for column in numeric_columns:

        if column in display_df.columns:

            display_df[column] = pd.to_numeric(
                display_df[column],
                errors="coerce",
            )

    # Round CPU-related values
    for column in [
        "average_cpu",
        "p95_cpu",
        "maximum_cpu",
        "cpu_credit_balance",
    ]:

        if column in display_df.columns:

            display_df[column] = display_df[column].round(2)

    # --------------------------------------------------------
    # Rename columns for the UI
    # --------------------------------------------------------

    display_df = display_df.rename(
    columns={
        "instance_id": "Instance ID",
        "name": "Name",
        "region": "Region",
        "availability_zone": "AZ",
        "instance_type": "Type",
        "state": "State",
        "average_cpu": "Avg CPU %",
        "p95_cpu": "P95 CPU %",
        "maximum_cpu": "Max CPU %",
        "network_in_gib_per_day": "Network In GiB/day",
        "network_out_gib_per_day": "Network Out GiB/day",
        "disk_read_gib_per_day": "Disk Read GiB/day",
        "disk_write_gib_per_day": "Disk Write GiB/day",
        "cpu_credit_balance": "CPU Credits",
        "cpu_credit_usage": "CPU Credit Usage",
        "cpu_datapoints": "CPU Datapoints",
        "data_quality": "Data Quality",
        "optimization_status": "Optimization Status",
    }
)

    # Replace missing values with a clean UI representation
    display_df = display_df.fillna("—")

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
    )


st.divider()

st.subheader("💾 Storage Optimization")


if ebs_df.empty:

    st.success(
        "No potentially orphaned EBS volumes detected."
    )

else:

    st.warning(
        f"{len(ebs_df)} potentially orphaned "
        "EBS volume(s) require review."
    )

    ebs_display = ebs_df.reindex(
    columns=[
        "volume_id",
        "region",
        "volume_type",
        "size_gb",
        "state",
        "age_days",
        "optimization_status",
        "optimization_reason",
    ]
    ).copy()

    ebs_display = ebs_display.rename(
        columns={
            "volume_id": "Volume ID",
            "region": "Region",
            "volume_type": "Type",
            "size_gb": "Size (GB)",
            "state": "State",
            "age_days": "Age (days)",
            "optimization_status": "Signal",
            "optimization_reason": "Reason",
        }
    )

    st.dataframe(
        ebs_display,
        width="stretch",
        hide_index=True,
    )

st.subheader("🌐 Network Resource Optimization")


if elastic_ip_df.empty:

    st.success(
        "No potentially unused Elastic IPs detected."
    )

else:

    st.warning(
        f"{len(elastic_ip_df)} potentially unused "
        "Elastic IP(s) require review."
    )

    eip_display = elastic_ip_df.reindex(
    columns=[
        "public_ip",
        "region",
        "allocation_id",
        "optimization_status",
        "optimization_reason",
    ]
    ).copy()

    eip_display = eip_display.rename(
        columns={
            "public_ip": "Public IP",
            "region": "Region",
            "allocation_id": "Allocation ID",
            "optimization_status": "Signal",
            "optimization_reason": "Reason",
        }
    )

    st.dataframe(
        eip_display,
        width="stretch",
        hide_index=True,
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
            # LEFT SIDE
            # ------------------------------------------------

            with col1:

                instance_name = row.get(
                    "name",
                    "",
                )

                instance_id = row.get(
                    "instance_id",
                    "Unknown",
                )

                if pd.isna(instance_name) or not instance_name:

                    display_name = instance_id

                else:

                    display_name = instance_name

                st.write(
                    f"### {display_name}"
                )

                st.caption(
                    instance_id
                )

                st.write(
                    f"**Type:** "
                    f"{row.get('instance_type', 'Unknown')}"
                )

                st.write(
                    f"**Region:** "
                    f"{row.get('region', 'Unknown')}"
                )

            # ------------------------------------------------
            # RIGHT SIDE
            # ------------------------------------------------

            with col2:

                metric1, metric2, metric3 = st.columns(3)

                # --------------------------------------------
                # Average CPU
                # --------------------------------------------

                with metric1:

                    average_cpu = row.get(
                        "average_cpu"
                    )

                    if pd.notna(average_cpu):

                        st.metric(
                            "Avg CPU",
                            f"{float(average_cpu):.2f}%",
                        )

                    else:

                        st.metric(
                            "Avg CPU",
                            "N/A",
                        )

                # --------------------------------------------
                # Maximum CPU
                # --------------------------------------------

                with metric2:

                    maximum_cpu = row.get(
                        "maximum_cpu"
                    )

                    if pd.notna(maximum_cpu):

                        st.metric(
                            "Max CPU",
                            f"{float(maximum_cpu):.2f}%",
                        )

                    else:

                        st.metric(
                            "Max CPU",
                            "N/A",
                        )

                # --------------------------------------------
                # CPU Credits
                # --------------------------------------------

                with metric3:

                    cpu_credits = row.get(
                        "cpu_credit_balance"
                    )

                    if pd.notna(cpu_credits):

                        st.metric(
                            "CPU Credits",
                            f"{float(cpu_credits):.2f}",
                        )

                    else:

                        st.metric(
                            "CPU Credits",
                            "N/A",
                        )

                # --------------------------------------------
                # Data Quality
                # --------------------------------------------

                data_quality = row.get(
                    "data_quality",
                    "Unknown",
                )

                st.write(
                    f"**Data quality:** "
                    f"{data_quality}"
                )

                # --------------------------------------------
                # Optimization Status
                # --------------------------------------------

                status = row.get(
                    "optimization_status",
                    "No optimization analysis available.",
                )

                status = str(status)

                if "opportunity" in status.lower():

                    st.warning(
                        f"⚠️ {status}"
                    )

                elif "insufficient" in status.lower():

                    st.info(
                        f"ℹ️ {status}"
                    )

                elif "no data" in status.lower():

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