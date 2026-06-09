import os
import pandas as pd
import streamlit as st


@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    path = "Files/final_df_orc"
    fallback = "meal_forecasting_final.csv"
    try:
        if os.path.isdir(path):
            try:
                from pyspark.sql import SparkSession
                spark = SparkSession.builder.getOrCreate()
                spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
                df = spark.read.orc(path).toPandas()
            except Exception:
                import pyarrow.dataset as ds
                df = ds.dataset(path, format="orc").to_table().to_pandas()
        else:
            df = pd.read_csv(fallback)
    except Exception:
        df = pd.read_csv(fallback)

    df["MONTH_START"] = pd.to_datetime(df["MONTH_START"])
    df["YEAR"] = df["MONTH_START"].dt.year
    df["MONTH"] = df["MONTH_START"].dt.month

    for c in ["LUNCH_PARTICIPATION", "BREAKFAST_PARTICIPATION",
              "absence_rate", "ENROLLMENT", "pct_free_reduced_lunch"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["lunch_pct"] = (df["LUNCH_PARTICIPATION"] * 100).round(1)
    df["breakfast_pct"] = (df["BREAKFAST_PARTICIPATION"] * 100).round(1)
    df["absence_pct"] = (df["absence_rate"] * 100).round(1)

    df["tier"] = df["LUNCH_PARTICIPATION"].apply(
        lambda p: "Critical" if p < 0.40 else "Low" if p < 0.55
        else "Moderate" if p < 0.65 else "Strong"
    )

    month_map = {1: "Jan", 2: "Feb", 3: "Mar", 8: "Aug",
                 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    df["month_label"] = df["MONTH"].map(month_map)

    return df


def school_averages(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("SCHOOL_NAME", as_index=False).agg(
        lunch_avg=("LUNCH_PARTICIPATION", "mean"),
        breakfast_avg=("BREAKFAST_PARTICIPATION", "mean"),
        ENROLLMENT=("ENROLLMENT", "mean"),
        absence_avg=("absence_rate", "mean"),
    )
    agg["lunch_pct"] = (agg["lunch_avg"] * 100).round(1)
    agg["breakfast_pct"] = (agg["breakfast_avg"] * 100).round(1)
    agg["absence_pct"] = (agg["absence_avg"] * 100).round(1)
    agg["tier"] = agg["lunch_avg"].apply(
        lambda p: "Critical" if p < 0.40 else "Low" if p < 0.55
        else "Moderate" if p < 0.65 else "Strong"
    )
    agg["ENROLLMENT"] = agg["ENROLLMENT"].round(0).astype(int)
    agg = agg.sort_values("lunch_avg", ascending=False).reset_index(drop=True)
    agg["label"] = agg.apply(
        lambda r: f"{r['SCHOOL_NAME']}  ·  {r['tier']}  ·  {r['lunch_pct']:.1f}%", axis=1
    )
    return agg
