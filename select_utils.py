from sqlalchemy import create_engine
import pandas as pd

engine = create_engine(
        "postgresql+psycopg2://postgres:postgres@localhost:5432/sales_data"
    )

df = pd.read_sql("SELECT * FROM sales_data", engine)

print(df)