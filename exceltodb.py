import pandas as pd
from sqlalchemy import create_engine

# CSV file
file_path = "/home/anu/Downloads/Sales_Dashboard/sales_dashboard/Region Wise Customers - Overall Sheet.csv"

# Read CSV
df = pd.read_csv(file_path)

# PostgreSQL connection
engine = create_engine(
    "postgresql://postgres:postgres@localhost:5432/PPC_Data"
)

# Import to PostgreSQL
df.to_sql(
    "regionwise_customer",
    engine,
    if_exists="append",
    index=False
)

print("✅ CSV imported successfully")


# import pandas as pd
# from sqlalchemy import create_engine

# file_path = "/home/anu/Downloads/Sales_Dashboard/sales_dashboard/Over all sale date 22 to 26.xlsx"

# df = pd.read_excel(file_path, engine="openpyxl")

# # Rename mapping (Excel → DB columns)
# df.rename(columns={
#     "Bill DocNo": "bill_doc_no",
#     "Inv.Ref.No.": "inv_ref_no",
#     "Inv.Ref.Date": "inv_ref_date",
#     "Customer Name": "customer_name",
#     "Material Qty": "material_qty",
#     "Basic Price/Uom": "basic_price_uom",
#     "Freight Charges": "freight_charges",
#     "Basic Price": "basic_price",
#     "CGST": "cgst",
#     "SGST": "sgst",
#     "IGST": "igst",
#     "UGST": "ugst",
#     "TCS - Base": "tcs_base",
#     "Total Inv.Value Before Round-Off": "total_invoice_value",
#     "Customer Code": "customer_code",
#     "Purchase Order No": "po_no",
#     "Document Type": "document_type",
#     "Plant": "plant",
#     "Sale Order": "sale_order",
#     "Material Description": "material_description",
#     "Material": "material",
#     "Material Group": "material_group",
#     "GST No": "gst_no",
#     "Desc-terms of payment": "payment_terms"
# }, inplace=True)

# # PostgreSQL connection
# engine = create_engine(
#     "postgresql://postgres:postgres@localhost:5432/Sales_Data"
# )

# # Insert into DB
# df.to_sql(
#     "sales_excel_data",
#     engine,
#     if_exists="replace",
#     index=False
# )

# print("✅ Excel imported with proper column mapping")