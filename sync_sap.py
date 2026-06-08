import requests
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta
import urllib3
import time
import numpy as np

urllib3.disable_warnings()


# SAP CONFIG


URL = "https://20.244.40.189:44302/zfi_sr_ysrepgst?sap-client=900"

SAP_USERNAME = "HO_PE"
SAP_PASSWORD = "Npg@pe*"


# PLANTS


plants = ["3200", "3300", "3700", "3800"]


# POSTGRESQL


engine = create_engine(
    "postgresql://postgres:postgres@localhost:5432/Sales_Data"
)


# SAP FIELD -> DB COLUMN


field_map = {

    "VBELN": "bill_doc_no",
    "XBLNR2": "inv_ref_no",
    "BLDAT2": "inv_ref_date",
    "NAME1": "customer_name",

    "FKIMG": "material_qty",

    "PER": "basic_price_uom",

    "FRTCHARGE": "freight_charges",

    "BASPRIC": "basic_price",

    "CGST": "cgst",
    "SGST": "sgst",
    "IGST": "igst",
    "UGST": "ugst",

    "JTCS": "tcs_base",

    "TOTAL": "total_invoice_value",

    "KUNAG": "customer_code",

    "BSTKD": "po_no",

    "DBEZEI": "document_type",

    "WERKS": "plant",

    "ORDER": "sale_order",

    "ARKTX": "material_description",

    "MATNR": "material",

    "WGBEZ": "material_group",

    "GSTNO": "gst_no",

    "VTEXT1": "payment_terms",

    "SHIP_NAME": "Ship to Party Name"
}


# DATE RANGE

today = datetime.now().date()
yesterday = today - timedelta(days=1)

start_date = yesterday
end_date = today

# today = datetime.now().date() 

# start_date = today 
# end_date = today

# start_date = datetime(2026, 5, 23).date()
# end_date = datetime.now().date()


# ALL DATA


all_rows = []

current_date = start_date

while current_date <= end_date:

    sap_date = current_date.strftime("%Y%m%d")

    print("\n==============================")
    print("DATE :", sap_date)
    print("==============================")

    for plant in plants:

        print(f"Plant : {plant}")

        payload = {
            "DATAB": sap_date,
            "WERKS": plant
        }

        try:

            response = requests.request(
                method="GET",
                url=URL,
                auth=(SAP_USERNAME, SAP_PASSWORD),
                headers={
                    "Content-Type": "application/json"
                },
                json=payload,
                verify=False,
                timeout=300
            )

            print("Status:", response.status_code)

            if response.status_code != 200:

                print(response.text[:300])
                continue

            data = response.json()

            rows = []

            
            # FIND LIST DATA
            

            if isinstance(data, dict):

                for key, value in data.items():

                    if isinstance(value, list):

                        for item in value:

                            if isinstance(item, dict):

                                clean_row = {}

                                for sap_col, db_col in field_map.items():

                                    clean_row[db_col] = item.get(sap_col)

                                rows.append(clean_row)

            print("Rows:", len(rows))

            all_rows.extend(rows)

            time.sleep(1)

        except Exception as e:

            print("ERROR:", e)

    current_date += timedelta(days=1)


# DATAFRAME


df = pd.DataFrame(all_rows)

print("\nTOTAL ROWS :", len(df))


# REQUIRED DB COLUMNS


db_cols = [
    "bill_doc_no",
    "inv_ref_no",
    "inv_ref_date",
    "customer_name",
    "material_qty",
    "basic_price_uom",
    "freight_charges",
    "basic_price",
    "cgst",
    "sgst",
    "igst",
    "ugst",
    "tcs_base",
    "total_invoice_value",
    "customer_code",
    "po_no",
    "document_type",
    "plant",
    "sale_order",
    "material_description",
    "material",
    "material_group",
    "gst_no",
    "payment_terms",
    "Ship to Party Name"
]

df = df.reindex(columns=db_cols)


# NUMERIC COLUMNS


numeric_cols = [
    "material_qty",
    "basic_price_uom",
    "freight_charges",
    "basic_price",
    "cgst",
    "sgst",
    "igst",
    "ugst",
    "tcs_base",
    "total_invoice_value"
]


# CLEAN NUMERIC DATA


for col in numeric_cols:

    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )


# CLEAN STRING COLUMNS


string_cols = [
    col for col in df.columns
    if col not in numeric_cols
]

for col in string_cols:

    df[col] = df[col].replace(
        ["", "nan", "None"],
        None
    )


# DATE CLEAN


df["inv_ref_date"] = pd.to_datetime(
    df["inv_ref_date"],
    errors="coerce"
)


# SAVE TO POSTGRESQL


df.to_sql(
    "sales_excel_data",
    engine,
    if_exists="append",
    index=False,
    chunksize=5000
)

print("\n✅ SAP DATA STORED SUCCESSFULLY")