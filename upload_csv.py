import pandas as pd
from sqlalchemy import create_engine

# -----------------------------
# CSV FILE PATH
# -----------------------------

CSV_PATH = "/home/anu/Downloads/Sales_Dashboard/dashboard_v6/Sales Data - Data.csv"

# -----------------------------
# READ CSV
# -----------------------------

df = pd.read_csv(CSV_PATH, low_memory=False)

print(f"Rows Loaded: {len(df)}")

# -----------------------------
# POSTGRESQL CONNECTION
# -----------------------------

engine = create_engine(
    "postgresql://postgres:admin123@localhost:5432/Sales_Data"
)

# -----------------------------
# UPLOAD TO POSTGRESQL
# -----------------------------

df.to_sql(
    "sales_raw_data",
    engine,
    if_exists="replace",
    index=False
)

print("✅ CSV Uploaded Successfully")