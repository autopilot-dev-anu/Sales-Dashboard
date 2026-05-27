from sqlalchemy import create_engine
import os
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
import numpy as np
import re

app = Flask(__name__, static_folder='static')

DB_URL = os.environ.get(
    "DB_URL",
    "postgresql://postgres:admin123@localhost:5432/Sales_Data"
)

engine = create_engine(DB_URL)

PLANT_MAP = {
    '3200':'Pondy',
    '3700':'Silvassa',
    '3300':'Roorkee',
    '3800':'Howrah'
}

REAL_SALESPERSONS = [
    'Balvinder','Sakthivel',
    'Bishwajeet','West Customer'
]

def clean_number(val):
    if pd.isna(val):
        return 0.0

    s = str(val).replace(',', '').strip()

    try:
        return float(s)
    except:
        return 0.0


def extract_gm(desc):

    if pd.isna(desc):
        return 0.0

    text = str(desc).upper()

    match = re.search(
        r'(\d+(?:\.\d+)?)\s*GM',
        text
    )

    if match:
        return float(match.group(1))

    return 0.0


def load_data():

    df = pd.read_sql(
        "SELECT * FROM sales_excel_data",
        engine
    )

    df.columns = [
        c.lower().strip()
        for c in df.columns
    ]

    print("Columns Found:")
    print(df.columns.tolist())

    # -----------------------------
    # Date
    # -----------------------------
    df["date"] = pd.to_datetime(
        df["inv_ref_date"],
        errors="coerce"
    )

    df = df[
        df["date"].notna()
    ].copy()

    # -----------------------------
    # Customer
    # -----------------------------
    df["customer"] = (
        df["customer_name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # -----------------------------
    # Quantity (Pieces)
    # -----------------------------
    df["qty"] = (
        df["material_qty"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    df["qty"] = pd.to_numeric(
        df["qty"],
        errors="coerce"
    ).fillna(0)

    # -----------------------------
    # Revenue
    # -----------------------------
    df["total_value"] = (
        df["total_invoice_value"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip()
    )

    df["total_value"] = pd.to_numeric(
        df["total_value"],
        errors="coerce"
    ).fillna(0)

    # -----------------------------
    # Extract GM from Material Description
    # Example:
    # PREFORM 19.5 GM AQUA
    # PREFORM 11.5 GM 26/22
    # -----------------------------
    df["gm_per_piece"] = (
        df["material_description"]
        .fillna("")
        .apply(extract_gm)
    )

    # -----------------------------
    # Weight Calculations
    # Pieces × GM = Total Grams
    # Grams → KG → MT
    # -----------------------------
    df["total_grams"] = (
        df["qty"]
        * df["gm_per_piece"]
    )

    df["kg"] = (
        df["total_grams"]
        / 1000
    )

    df["mt_tons"] = (
        df["kg"]
        / 1000
    )

    # -----------------------------
    # Date Columns
    # -----------------------------
    df["year"] = (
        df["date"]
        .dt.year
        .astype(int)
    )

    df["month_num"] = (
        df["date"]
        .dt.month
        .astype(int)
    )

    df["year_month"] = (
        df["date"]
        .dt.strftime("%Y-%m")
    )

    df["week_num"] = (
        df["date"]
        .dt.isocalendar()
        .week
        .astype(int)
    )

    df["week"] = (
        "W"
        + df["week_num"].astype(str)
    )

    df["date_str"] = (
        df["date"]
        .dt.strftime("%Y-%m-%d")
    )

    # -----------------------------
    # Plant
    # -----------------------------
    df["plant_code"] = (
        df["plant"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["plant_name"] = (
        df["plant_code"]
        .map(PLANT_MAP)
        .fillna(df["plant_code"])
    )

    # -----------------------------
    # Category
    # -----------------------------
    df["category"] = (
        df["material_group"]
        .fillna("Others")
        .astype(str)
        .str.strip()
    )

    # -----------------------------
    # Placeholder Fields
    # -----------------------------
    df["region"] = "Unknown"
    df["salesperson"] = "Unassigned"

    # -----------------------------
    # Debug Prints
    # -----------------------------
    print(
        df[
            [
                "material_description",
                "qty",
                "gm_per_piece",
                "mt_tons"
            ]
        ].head(10)
    )

    print(f"Loaded Rows : {len(df):,}")
    print(f"Revenue     : {df['total_value'].sum():,.2f}")
    print(f"Qty         : {df['qty'].sum():,.0f}")
    print(f"MT Tons     : {df['mt_tons'].sum():,.3f}")

    return df

  
DF = load_data()
print(f"✅ Loaded {len(DF):,} rows | MT Tons total: {DF['mt_tons'].sum():,.1f}")

def apply_filters(df, customer=None, from_date=None, to_date=None, week=None, year=None, plant=None):
    if year and str(year) not in ('all',''):
        df = df[df['year'] == int(year)]
    if week and week not in ('all',''):
        df = df[df['week'] == week]
    if from_date:
        df = df[df['date'] >= pd.to_datetime(from_date)]
    if to_date:
        df = df[df['date'] <= pd.to_datetime(to_date)]
    if customer and customer != 'all':
        df = df[df['customer'].str.lower() == customer.lower()]
    if plant and plant not in ('all',''):
        df = df[df['plant_code'] == str(plant)]
    return df

def safe_json(obj):
    if isinstance(obj, dict): return {k: safe_json(v) for k, v in obj.items()}
    if isinstance(obj, list): return [safe_json(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)): return 0
    return obj

@app.after_request
def add_cors(r):
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return r

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/yearly_summary')
def yearly_summary():
    grp = DF.groupby('year').agg(
        revenue=('total_value','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),
        transactions=('total_value','count'),
        customers=('customer','nunique')
    ).reset_index().sort_values('year')

    return jsonify(safe_json(grp.to_dict(orient='records')))
    
@app.route('/api/meta')
def meta():
    customers = sorted(DF['customer'].unique().tolist())
    week_df   = DF[['week','week_num']].drop_duplicates().sort_values('week_num')
    years     = sorted(DF['year'].unique().tolist())
    plants    = [{'code':k,'name':v} for k,v in PLANT_MAP.items()]
    return jsonify({
        'min_date': str(DF['date'].min().date()),
        'max_date': str(DF['date'].max().date()),
        'total_rows': len(DF),
        'customers': customers,
        'weeks': week_df['week'].tolist(),
        'years': [y for y in years if y > 0],
        'plants': plants,
        'salespersons': REAL_SALESPERSONS,
    })

def get_f(): 
    return {k: request.args.get(k,'') for k in ['customer','from_date','to_date','week','year','plant']}

def smart_filter(df, f, default_7days=True):

    has_filters = any(f.values())

    if not has_filters and default_7days:
        df = df[
            df["date"]
            >= DF["date"].max() - pd.Timedelta(days=7)
        ]
    else:
        df = apply_filters(
            df,
            customer=f.get("customer") or None,
            from_date=f.get("from_date") or None,
            to_date=f.get("to_date") or None,
            week=f.get("week") or None,
            year=f.get("year") or None,
            plant=f.get("plant") or None
        )
    return df

@app.route('/api/kpis')
def kpis():

    f = get_f()
    df = smart_filter(DF.copy(), f)

    print("ROWS:", len(df))
    print("REVENUE:", df["total_value"].sum())
    print(df[["date","total_invoice_value","total_value"]].head(20))

    return jsonify({
        'total_revenue': round(df['total_value'].sum(), 2),
        'total_qty': int(df['qty'].sum()),
        'total_mt_tons': round(df['mt_tons'].sum(), 3),
        'unique_customers': int(df['customer'].nunique()),
        'transactions': len(df),
        'record_count': len(df)
    })

@app.route('/api/revenue_trend')
def revenue_trend():
    f = get_f(); group_by = request.args.get('group_by','month')
    df = smart_filter(DF.copy(), f)
    if group_by=='day':   df['period']=df['date_str']; df['sort_key']=df['date_str']
    elif group_by=='week': df['period']=df['week']; df['sort_key']=df['week_num'].astype(str).str.zfill(3)
    else:                  df['period']=df['year_month']; df['sort_key']=df['year_month']
    grp = df.groupby(['period','sort_key']).agg(
        revenue=('total_value','sum'), qty=('qty','sum'),
        mt_tons=('mt_tons','sum'), transactions=('total_value','count')
    ).reset_index().sort_values('sort_key')
    return jsonify(safe_json(grp.rename(columns={'period':'label'})[['label','revenue','qty','mt_tons','transactions']].to_dict(orient='records')))

@app.route('/api/top_customers')
def top_customers():
    f = get_f(); limit=int(request.args.get('limit',20))
    df = smart_filter(DF.copy(), f)
    grp = df.groupby('customer').agg(revenue=('total_value','sum'),qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),transactions=('total_value','count')
    ).reset_index().sort_values('revenue',ascending=False).head(limit)
    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/category_breakdown')
def category_breakdown():
    f = get_f(); df = smart_filter(DF.copy(), f)
    grp = df.groupby('category').agg(revenue=('total_value','sum'),qty=('qty','sum'),
        mt_tons=('mt_tons','sum')).reset_index().sort_values('revenue',ascending=False)
    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/region_breakdown')
def region_breakdown():
    f = get_f(); df = smart_filter(DF.copy(), f)
    grp = df.groupby('region').agg(revenue=('total_value','sum'),qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),transactions=('total_value','count')
    ).reset_index().sort_values('revenue',ascending=False)
    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/plant_breakdown')
def plant_breakdown():
    f = get_f(); df = smart_filter(DF.copy(), f)
    grp = df.groupby(['plant_code','plant_name']).agg(
        revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum'),
        transactions=('total_value','count'),customers=('customer','nunique')
    ).reset_index().sort_values('revenue',ascending=False)
    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/salesperson_breakdown')
def salesperson_breakdown():
    f = get_f(); df = smart_filter(DF.copy(), f)
    df = df[df['salesperson'].isin(REAL_SALESPERSONS)]
    grp = df.groupby('salesperson').agg(
        revenue=('total_value','sum'),qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),transactions=('total_value','count')
    ).reset_index().sort_values('revenue',ascending=False)
    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/salesperson_all_details')
def salesperson_all_details():
    f = get_f()
    df = DF.copy()
    df = apply_filters(
      df,
      customer=f.get("customer") or None,
      from_date=f.get("from_date") or None,
      to_date=f.get("to_date") or None,
      week=f.get("week") or None,
      year=f.get("year") or None,
      plant=f.get("plant") or None
)
    df = df[df['salesperson'].isin(REAL_SALESPERSONS)]

    all_weeks  = sorted(df[['week','week_num']].drop_duplicates().values.tolist(), key=lambda x: x[1])
    all_months = sorted(df['year_month'].dropna().unique().tolist())

    result = {}
    for sp in REAL_SALESPERSONS:
        sp_df = df[df['salesperson']==sp]
        monthly = sp_df.groupby('year_month').agg(
            revenue=('total_value','sum'),qty=('qty','sum'),
            mt_tons=('mt_tons','sum'),transactions=('total_value','count')
        ).reset_index().sort_values('year_month')
        weekly = sp_df.groupby(['week','week_num']).agg(
            revenue=('total_value','sum'),qty=('qty','sum'),
            mt_tons=('mt_tons','sum'),transactions=('total_value','count')
        ).reset_index().sort_values('week_num')
        result[sp] = {
            'total_revenue': round(sp_df['total_value'].sum(),2),
            'total_qty': int(sp_df['qty'].sum()),
            'total_mt_tons': round(sp_df['mt_tons'].sum(),3),
            'transactions': int(len(sp_df)),
            'monthly': {r['year_month']: {'revenue':round(r['revenue'],2),'qty':int(r['qty']),'mt_tons':round(r['mt_tons'],3),'transactions':int(r['transactions'])} for r in monthly.to_dict(orient='records')},
            'weekly':  {r['week']: {'revenue':round(r['revenue'],2),'qty':int(r['qty']),'mt_tons':round(r['mt_tons'],3),'transactions':int(r['transactions'])} for r in weekly.to_dict(orient='records')},
        }
    return jsonify(safe_json({'salespersons':REAL_SALESPERSONS,'all_weeks':[w[0] for w in all_weeks],'all_months':all_months,'data':result}))

@app.route('/api/salesperson_detail')
def salesperson_detail():
    f = get_f(); salesperson = request.args.get('salesperson','')
    df = DF.copy()
    df = apply_filters(df, from_date=f.get('from_date') or None, to_date=f.get('to_date') or None,
                       week=f.get('week') or None, year=f.get('year') or None, plant=f.get('plant') or None)
    if salesperson: df = df[df['salesperson']==salesperson]
    else:           df = df[df['salesperson'].isin(REAL_SALESPERSONS)]

    monthly = df.groupby(['year_month','month_num','year']).agg(
        revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum'),transactions=('total_value','count')
    ).reset_index().sort_values('year_month')

    weekly = df.groupby(['week','week_num','year']).agg(
        revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum'),transactions=('total_value','count')
    ).reset_index().sort_values(['year','week_num'])

    plant_split = df.groupby(['plant_code','plant_name']).agg(
        revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum')
    ).reset_index().sort_values('revenue',ascending=False)

    cat_split = df.groupby('category').agg(
        revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum')
    ).reset_index().sort_values('revenue',ascending=False)

    yearly = df.groupby('year').agg(
        revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum'),transactions=('total_value','count')
    ).reset_index().sort_values('year')

    return jsonify(safe_json({
        'salesperson': salesperson,
        'total_revenue': round(df['total_value'].sum(),2),
        'total_qty': int(df['qty'].sum()),
        'total_mt_tons': round(df['mt_tons'].sum(),3),
        'transactions': len(df),
        'monthly': monthly[['year_month','month_num','year','revenue','qty','mt_tons','transactions']].to_dict(orient='records'),
        'weekly':  weekly[['week','week_num','year','revenue','qty','mt_tons','transactions']].to_dict(orient='records'),
        'plant_split': plant_split.to_dict(orient='records'),
        'cat_split': cat_split.to_dict(orient='records'),
        'yearly': yearly.to_dict(orient='records'),
    }))

@app.route('/api/salesperson_weekly')
def salesperson_weekly():
    f = get_f(); salesperson=request.args.get('salesperson','')
    df = DF.copy()
    df = df[df['salesperson'].isin(REAL_SALESPERSONS)]
    if f['year'] and f['year']!='all': df=df[df['year']==int(f['year'])]
    if f['from_date']: df=df[df['date']>=pd.to_datetime(f['from_date'])]
    if f['to_date']:   df=df[df['date']<=pd.to_datetime(f['to_date'])]
    if f['plant'] and f['plant'] not in ('all',''): df=df[df['plant_code']==str(f['plant'])]
    if salesperson and salesperson!='all': df=df[df['salesperson']==salesperson]
    grp = df.groupby(['salesperson','week','week_num']).agg(
        revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum'),transactions=('total_value','count')
    ).reset_index().sort_values(['salesperson','week_num'])
    all_weeks=sorted(df[['week','week_num']].drop_duplicates().values.tolist(),key=lambda x:x[1])
    return jsonify(safe_json({'weeks':[w[0] for w in all_weeks],'data':grp[['salesperson','week','revenue','qty','mt_tons','transactions']].to_dict(orient='records')}))

@app.route('/api/customer_detail')
def customer_detail():
    customer=request.args.get('customer','')
    if not customer: return jsonify({'error':'customer required'}),400
    df=DF[DF['customer'].str.lower()==customer.lower()].copy()
    monthly=df.groupby('year_month').agg(revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum')).reset_index().sort_values('year_month')
    cats=df.groupby('category').agg(revenue=('total_value','sum'),qty=('qty','sum'),mt_tons=('mt_tons','sum')).reset_index().sort_values('revenue',ascending=False)
    first=df.iloc[0] if len(df) else {}
    plant_code=str(first.get('plant_code','')) if len(df) else ''
    return jsonify(safe_json({
        'customer':customer,'total_revenue':round(df['total_value'].sum(),2),
        'total_qty':int(df['qty'].sum()),'total_mt_tons':round(df['mt_tons'].sum(),3),
        'transactions':len(df),'first_order':str(df['date'].min().date()) if len(df) else '',
        'last_order':str(df['date'].max().date()) if len(df) else '',
        'region':str(first.get('region','')) if len(df) else '',
        'plant_code':plant_code,'plant_name':PLANT_MAP.get(plant_code,plant_code),
        'monthly':monthly.rename(columns={'year_month':'label'}).to_dict(orient='records'),
        'categories':cats.to_dict(orient='records'),
    }))

@app.route('/api/collections')
def collections():
    import datetime
    f = get_f()
    period = request.args.get('period', 'mtd')
    today = DF['date'].max()  # use latest data date as "today"

    # Determine period window
    if period == 'mtd':
        start = today.replace(day=1)
        label = 'MTD'
    elif period == 'wtd':
        start = today - pd.Timedelta(days=today.dayofweek)  # Monday
        label = 'WTD'
    else:  # ytd
        start = today.replace(month=1, day=1)
        label = 'YTD'

    df = DF.copy()
    # Apply user filters (customer/plant/year/week) but override date with period
    df = apply_filters(df,
        customer=f.get('customer') or None,
        plant=f.get('plant') or None,
        year=f.get('year') or None
    )
    df_period = df[df['date'] >= start].copy()

    # ── Outstanding / Overdue logic ──────────────────────────────────────
    # Parse payment_terms to get days (e.g. "30 days", "Net 45", "60")
    def parse_days(pt):
        if pd.isna(pt): return 30
        nums = re.findall(r'\d+', str(pt))
        return int(nums[-1]) if nums else 30

    df_period['due_date'] = df_period.apply(
        lambda r: r['date'] + pd.Timedelta(days=parse_days(r.get('payment_terms', ''))), axis=1
    )
    # Outstanding = not yet due or past due (all unpaid estimated as % of total)
    # In absence of a payments table, we estimate:
    # Outstanding = full invoice value for current period
    # Overdue = invoices where due_date < today
    df_period['is_overdue'] = df_period['due_date'] < today
    df_period['outstanding'] = df_period['total_value']
    df_period['overdue_val'] = df_period.apply(
        lambda r: r['total_value'] if r['is_overdue'] else 0, axis=1
    )
    # Collected = invoices due more than 15 days ago (estimated settled)
    df_period['is_likely_collected'] = df_period['due_date'] < (today - pd.Timedelta(days=15))
    df_period['collected_val'] = df_period.apply(
        lambda r: r['total_value'] if r['is_likely_collected'] else 0, axis=1
    )

    total_invoiced = df_period['total_value'].sum()
    total_outstanding = df_period['outstanding'].sum()
    total_overdue = df_period['overdue_val'].sum()
    total_collected = df_period['collected_val'].sum()
    total_mt = df_period['mt_tons'].sum()
    invoice_count = df_period['bill_doc_no'].nunique()

    # ── Daily trend ──────────────────────────────────────────────────────
    trend_grp = df_period.groupby('date_str').agg(
        invoiced=('total_value', 'sum'),
        overdue=('overdue_val', 'sum'),
        mt=('mt_tons', 'sum')
    ).reset_index().sort_values('date_str')
    trend = trend_grp.rename(columns={'date_str': 'date'}).to_dict(orient='records')

    # ── Payment terms breakdown ──────────────────────────────────────────
    terms_grp = df_period.groupby('payment_terms').agg(
        outstanding=('outstanding', 'sum'),
        overdue=('overdue_val', 'sum'),
        invoiced=('total_value', 'sum')
    ).reset_index().sort_values('outstanding', ascending=False)
    terms = terms_grp.head(8).to_dict(orient='records')

    # ── Customer breakdown ───────────────────────────────────────────────
    cust_grp = df_period.groupby(['customer', 'payment_terms', 'gst_no']).agg(
        invoiced=('total_value', 'sum'),
        outstanding=('outstanding', 'sum'),
        overdue=('overdue_val', 'sum'),
        mt_tons=('mt_tons', 'sum'),
        invoice_count=('bill_doc_no', 'nunique')
    ).reset_index().sort_values('invoiced', ascending=False)

    customers = []
    for _, row in cust_grp.iterrows():
        customers.append({
            'customer': row['customer'],
            'gst_no': str(row.get('gst_no', '')) if not pd.isna(row.get('gst_no', '')) else '',
            'payment_terms': str(row.get('payment_terms', '')) if not pd.isna(row.get('payment_terms', '')) else '',
            'invoiced': round(float(row['invoiced']), 2),
            'outstanding': round(float(row['outstanding']), 2),
            'overdue': round(float(row['overdue']), 2),
            'mt_tons': round(float(row['mt_tons']), 3),
            'invoice_count': int(row['invoice_count']),
        })

    return jsonify(safe_json({
        'period': period,
        'as_of': str(today.date()),
        'total_invoiced': round(float(total_invoiced), 2),
        'outstanding': round(float(total_outstanding), 2),
        'overdue': round(float(total_overdue), 2),
        'collected': round(float(total_collected), 2),
        'total_mt': round(float(total_mt), 3),
        'invoice_count': int(invoice_count),
        'trend': trend,
        'terms': terms,
        'customers': customers,
    }))

# def yearly_summary():
#     grp=DF.groupby('year').agg(revenue=('total_value','sum'),qty=('qty','sum'),
#         mt_tons=('mt_tons','sum'),transactions=('total_value','count'),customers=('customer','nunique')
#     ).reset_index().sort_values('year')
#     return jsonify(safe_json(grp.to_dict(orient='records')))

if __name__=='__main__':
    app.run(debug=True,port=5000)
