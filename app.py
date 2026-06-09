from sqlalchemy import create_engine, text
import os
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
import numpy as np
import re

app = Flask(__name__, static_folder='static')

DB_URL = os.environ.get(
    "DB_URL",
    "postgresql://postgres:postgres@localhost:5432/Sales_Data"
)
engine = create_engine(DB_URL)

PLANT_MAP = {
    '3200':'Pondy',
    '3700':'Silvassa',
    '3300':'Roorkee',
    '3800':'Howrah'
}

# Will be updated dynamically after DB load
def get_real_salespersons():
    if CUSTOMER_PERSON_MAP:
        persons = list(set(v for v in CUSTOMER_PERSON_MAP.values() if v and v != 'Others'))
        return sorted(persons)
    return REAL_SALESPERSONS

# def get_real_salespersons():
#     persons = set()
#     if CUSTOMER_CODE_PERSON_MAP:
#         persons.update(v for v in CUSTOMER_CODE_PERSON_MAP.values() if v and v != 'Others')
#     if CUSTOMER_PERSON_MAP:
#         persons.update(v for v in CUSTOMER_PERSON_MAP.values() if v and v != 'Others')
#     return sorted(persons) if persons else list(REGION_HEAD.values())

# ── FIX 1: Region head mapping ──
REGION_HEAD = {
    'North': 'Balvinder',
    'South': 'Sakthivel',
    'East':  'Bishwajeet',
    'West':  'West Customer'
}

def clean_number(val):
    if pd.isna(val):
        return 0.0
    s = str(val).replace(',', '').strip()
    try:
        return float(s)
    except:
        return 0.0

# def extract_gm(desc):
#     if pd.isna(desc):
#         return 0.0
#     text = str(desc).upper()
#     match = re.search(r'(\d+(?:\.\d+)?)\s*GM', text)
#     if match:
#         return float(match.group(1))
#     return 0.0

def extract_gm(desc):
    if not desc or pd.isna(desc): return 0.0
    text = str(desc).upper().strip()
    if 'HANDLE' in text:
        if '5' in text and ('LTR' in text or '5L' in text): return 6.30
        if '2' in text and ('LTR' in text or '2L' in text): return 2.50
        return 2.0
    is_lid      = any(w in text for w in ['LID', 'CAP'])
    is_assembly = any(w in text for w in ['ASSEMBLY', 'ASSY', 'IML', 'CUP+LID', 'CONT+LID', 'WITH LID'])
    is_container= any(w in text for w in ['CONTAINER', 'CONT', 'CUP', 'BOWL', 'SPREAD'])
    if 'ITC CAP'       in text: return 18.0
    if 'ORANGE BOWL'   in text: return 18.0
    if 'CHEESE SPREAD' in text:
        return 6.5 if is_lid else (11.0 if is_container else 0.0)
    if 'BUTTER CUP' in text:
        if 'WITH LID' in text or is_assembly: return 16.5
        return 6.5 if is_lid else 10.0
    if 'BUTTER' in text and ('LID' in text or 'CAP' in text): return 6.5
    if 'BUTTER' in text and 'CUP' in text: return 10.0
    ml = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*ML', text)
    if m: ml = float(m.group(1))
    if ml is None:
        m = re.search(r'(\d+(?:\.\d+)?)\s*LTR', text)
        if m: ml = float(m.group(1)) * 1000
    if ml is None:
        m = re.search(r'(\d+(?:\.\d+)?)\s*L\b', text)
        if m: ml = float(m.group(1)) * 1000
    weight_table = {
        (125,'lid'):2.5,(125,'container'):8.5,(125,'assembly'):11.0,
        (200,'lid'):6.5,(200,'container'):10.0,(200,'assembly'):16.5,
        (500,'lid'):10.0,(500,'container'):17.2,(500,'assembly'):27.2,
        (1000,'lid'):10.6,(1000,'container'):43.6,(1000,'assembly'):54.2,(1000,'handle'):2.0,
        (2000,'lid'):10.6,(2000,'container'):43.6,(2000,'assembly'):54.2,(2000,'handle'):2.50,
        (5000,'lid'):10.6,(5000,'container'):43.6,(5000,'assembly'):54.2,(5000,'handle'):6.30,
    }
    if ml is not None and ml > 0:
        comp = 'assembly' if is_assembly else ('lid' if is_lid else 'container')
        sizes = list(set(k[0] for k in weight_table))
        closest = min(sizes, key=lambda s: abs(s - ml))
        if abs(closest - ml) <= closest * 0.3:
            return weight_table.get((closest, comp), weight_table.get((closest, 'assembly'), 0.0))
    return 0.0

# ─ Build customer→region + salesperson map 
# Reads from regionwise_customer table OR falls back to CSV
# Handles: case mismatch, truncated names, "West Customers" vs "West Customer"
# def build_customer_region_map():
#     try:
#         df = pd.read_sql("SELECT * FROM regionwise_customer", engine)
#         df.columns = [c.lower().strip().replace(' ', '_') for c in df.columns]
#         print("regionwise_customer columns:", df.columns.tolist())
#     except Exception as e:
#         print(f"DB read failed: {e}")
#         df = pd.DataFrame()

#     # Flexible column detection
#     name_col   = next((c for c in df.columns if 'customer' in c and 'name' in c), None) \
#               or next((c for c in df.columns if 'customer' in c), None)
#     region_col = next((c for c in df.columns if 'region' in c), None)
#     person_col = next((c for c in df.columns if 'marketing' in c or 'person' in c), None)

#     print(f"  name_col={name_col}, region_col={region_col}, person_col={person_col}")

#     region_map = {}
#     person_map = {}
#     full_names = []

#     for _, row in df.iterrows():
#         name = str(row.get(name_col, '') or '').strip()
#         if not name or name.lower() == 'nan':
#             continue
#         key    = name.lower()
#         region = str(row.get(region_col, '') or '').strip() if region_col else ''
#         # Normalize "West Customers" → "West Customer"
#         person = str(row.get(person_col, '') or '').strip() if person_col else ''
#         person = person.rstrip('s') + '' if person.lower() == 'west customers' else person
#         person = 'West Customer' if person.lower() in ('west customers','west customer') else person

#         region_map[key] = region
#         person_map[key] = person
#         full_names.append(key)

#     print(f"✅ Region map: {len(region_map)} | Person map: {len(person_map)}")
#     return region_map, person_map, full_names

# CUSTOMER_REGION_MAP, CUSTOMER_PERSON_MAP, CUSTOMER_FULL_NAMES = build_customer_region_map()

# Initialize globals
CUSTOMER_CODE_REGION_MAP = {}
CUSTOMER_CODE_PERSON_MAP = {}
CUSTOMER_REGION_MAP      = {}
CUSTOMER_PERSON_MAP      = {}
CUSTOMER_FULL_NAMES      = []

def normalize_name(name):
    n = str(name).lower().strip()
    n = re.sub(r'\bltd\.?\b',  'limited',       n)
    n = re.sub(r'\bpvt\.?\b',  'private',       n)
    n = re.sub(r'\binc\.?\b',  'incorporated',  n)
    n = re.sub(r'\bcorp\.?\b', 'corporation',   n)
    n = re.sub(r'\bindl\.?\b', 'industries',    n)
    n = re.sub(r'\bmfg\.?\b',  'manufacturing', n)
    n = re.sub(r'\bent\.?\b',  'enterprises',   n)
    n = re.sub(r'\bintl\.?\b', 'international', n)
    n = re.sub(r'[.,\-()&/]', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def build_customer_region_map():
    try:
        df = pd.read_sql("SELECT * FROM regionwise_customer", engine)
        df.columns = [c.lower().strip().replace(' ', '_') for c in df.columns]
        print("regionwise_customer columns:", df.columns.tolist())
    except Exception as e:
        print(f"DB read failed: {e}")
        df = pd.DataFrame()

    name_col   = next((c for c in df.columns if 'customer' in c and 'name' in c), None) \
              or next((c for c in df.columns if 'customer' in c), None)
    region_col = next((c for c in df.columns if 'region' in c), None)
    person_col = next((c for c in df.columns if 'marketing' in c or 'person' in c), None)
    code_col   = next((c for c in df.columns if c == 'code'), None)
    print(f"  name_col={name_col}, region_col={region_col}, person_col={person_col}, code_col={code_col}")

    code_region_map = {}
    code_person_map = {}
    name_region_map = {}
    name_person_map = {}
    full_names = []

    for _, row in df.iterrows():
        name   = str(row.get(name_col, '') or '').strip()
        region = str(row.get(region_col, '') or '').strip() if region_col else ''
        person = str(row.get(person_col, '') or '').strip() if person_col else ''
        person = 'West Customer' if person.lower() in ('west customers', 'west customer') else person
        code   = str(row.get(code_col,   '') or '').strip() if code_col else ''

        if not name or name.lower() == 'nan':
            continue

        if code and code not in ('nan', ''):
            try:
                code_int = int(float(code))
                # First occurrence only — don't overwrite
                if code_int not in code_region_map:
                    code_region_map[code_int] = region
                if code_int not in code_person_map:
                    code_person_map[code_int] = person
            except:
                pass

        key      = name.lower()
        norm_key = normalize_name(name)
        name_region_map[key]      = region
        name_region_map[norm_key] = region
        name_person_map[key]      = person
        name_person_map[norm_key] = person
        if norm_key not in full_names:
            full_names.append(norm_key)

    print(f"✅ Code map: {len(code_region_map)} | Name map: {len(name_region_map)}")
    return code_region_map, code_person_map, name_region_map, name_person_map, full_names

(CUSTOMER_CODE_REGION_MAP, CUSTOMER_CODE_PERSON_MAP,
 CUSTOMER_REGION_MAP, CUSTOMER_PERSON_MAP, CUSTOMER_FULL_NAMES) = build_customer_region_map()

def load_data():

    df = pd.read_sql(
        "SELECT * FROM sales_excel_data",
        engine
    )

    df.columns = [
        c.lower().strip()
        for c in df.columns
    ]

    # Fix column name with space
    if 'ship to party name' in df.columns:
        df.rename(columns={'ship to party name': 'ship_to_party_name'}, inplace=True)

    print("Columns Found:")
    print(df.columns.tolist())

    # Date
    df["date"] = pd.to_datetime(df["inv_ref_date"], errors="coerce")
    df = df[df["date"].notna()].copy()

    # Customer
    # df["customer"] = (
    #     df["customer_name"]
    #     .fillna("")
    #     .astype(str)
    #     .str.strip()
    # )
    
    df["customer"] = (
        df["customer_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.rstrip('.')
        .str.strip()
    )

    # Use regionwise_customer name as canonical (longest/official name)

    # rw = pd.read_sql("SELECT \"CODE\", \"CUSTOMER NAME\" FROM regionwise_customer", engine)
    # code_to_official = dict(zip(rw["CODE"].astype(int), rw["CUSTOMER NAME"].str.strip()))
    
    rw = pd.read_sql("SELECT \"CODE\", \"CUSTOMER NAME\" FROM regionwise_customer", engine)
    rw_first = rw.drop_duplicates(subset="CODE", keep="first")
    code_to_official = dict(zip(rw_first["CODE"].astype(int), rw_first["CUSTOMER NAME"].str.strip()))

    # Map official name; fallback to longest name from sales_excel_data
    code_to_longest = (
        df.groupby("customer_code")["customer"]
        .apply(lambda names: max(names, key=len))
        .to_dict()
    )
    df["cust_code_int"] = pd.to_numeric(df["customer_code"], errors="coerce").fillna(0).astype(int)
    df["customer"] = df["cust_code_int"].map(code_to_official).fillna(
                     df["cust_code_int"].map(code_to_longest)).fillna(df["customer"])
   
    
    # ── Region + Salesperson via regionwise_customer table (case-insensitive) ──
    # Handles truncation: "ARCHIAN FOODS INDIA PRIVATE LI" matches "ARCHIAN FOODS INDIA PRIVATE LIMITED"
    # def lookup_map(name, mapping):
    #     key = name.lower().strip()
    #     # Exact match first
    #     if key in mapping:
    #         return mapping[key]
    #     # Prefix match — sales_excel_data name is truncated version of regionwise_customer name
    #     for full in CUSTOMER_FULL_NAMES:
    #         if full.startswith(key) or key.startswith(full):
    #             return mapping[full]
    #     return 'Others'

    # df["region"]     = df["customer"].apply(lambda c: lookup_map(c, CUSTOMER_REGION_MAP))
    # df["salesperson"]= df["customer"].apply(lambda c: lookup_map(c, CUSTOMER_PERSON_MAP))
    
    df["cust_code"] = pd.to_numeric(
        df["customer_code"].astype(str).str.strip(), errors="coerce"
    ).fillna(0).astype(int)

    def lookup_region(row):
        code = row['cust_code']
        if code and code in CUSTOMER_CODE_REGION_MAP:
            return CUSTOMER_CODE_REGION_MAP[code]
        name     = row['customer']
        key      = name.lower().strip()
        norm_key = normalize_name(name)
        if key      in CUSTOMER_REGION_MAP: return CUSTOMER_REGION_MAP[key]
        if norm_key in CUSTOMER_REGION_MAP: return CUSTOMER_REGION_MAP[norm_key]
        for full in CUSTOMER_FULL_NAMES:
            if full.startswith(norm_key) or norm_key.startswith(full):
                return CUSTOMER_REGION_MAP.get(full, 'Others')
        return 'Others'

    def lookup_person(row):
        code = row['cust_code']
        if code and code in CUSTOMER_CODE_PERSON_MAP:
            return CUSTOMER_CODE_PERSON_MAP[code]
        name     = row['customer']
        key      = name.lower().strip()
        norm_key = normalize_name(name)
        if key      in CUSTOMER_PERSON_MAP: return CUSTOMER_PERSON_MAP[key]
        if norm_key in CUSTOMER_PERSON_MAP: return CUSTOMER_PERSON_MAP[norm_key]
        for full in CUSTOMER_FULL_NAMES:
            if full.startswith(norm_key) or norm_key.startswith(full):
                return CUSTOMER_PERSON_MAP.get(full, 'Others')
        return 'Others'

    df["region"]      = df.apply(lookup_region, axis=1)
    df["salesperson"] = df.apply(lookup_person, axis=1)
    df["salesperson"] = df["salesperson"].replace('West Customers', 'West Customer')

    # Quantity
    df["qty"] = (
        df["material_qty"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)

    # ── FIX 4: Revenue — both basic price and total invoice value ──
    # Basic Price (before GST)
    df["basic_price_val"] = pd.to_numeric(
        df["basic_price"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip(),
        errors="coerce"
    ).fillna(0)

    # Total Invoice Value (after GST)
    df["total_value"] = pd.to_numeric(
        df["total_invoice_value"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip(),
        errors="coerce"
    ).fillna(0)

    # GST components
    for col, newcol in [('cgst','cgst_val'),('sgst','sgst_val'),('igst','igst_val')]:
        df[newcol] = pd.to_numeric(
            df[col].astype(str).str.replace(",","",regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
    df["gst_total"] = df["cgst_val"] + df["sgst_val"] + df["igst_val"]

    # Weight
    # df["gm_per_piece"] = df["material_description"].fillna("").apply(extract_gm)
    # df["total_grams"]  = df["qty"] * df["gm_per_piece"]
    # df["kg"]           = df["total_grams"] / 1000
    # df["mt_tons"]      = df["kg"] / 1000
    
    def get_piece_weight(row):
        grp  = str(row.get('material_group', '') or '').upper().strip()
        desc = str(row.get('material_description', '') or '').upper().strip()

        if 'PREFORM' in grp:
            # PREFORM: extract GM from description
            m = re.search(r'(\d+(?:\.\d+)?)\s*G(?:M\b|M$|\b)', desc)
            return float(m.group(1)) if m else 0.0

        elif 'IML' in grp or 'HANDLE' in grp or 'CAP' in grp:
            # IML/Handle/Cap: use weight table lookup
            return extract_gm(desc)

        else:
            # SCRAP, RAW MATERIALS etc. → 0
            return 0.0

    df["gm_per_piece"] = df.apply(get_piece_weight, axis=1)
    df["mt_tons"]      = (df["qty"] * df["gm_per_piece"]) / 1_000_000

    # Date columns
    df["year"]       = df["date"].dt.year.astype(int)
    df["month_num"]  = df["date"].dt.month.astype(int)
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    df["date_str"]   = df["date"].dt.strftime("%Y-%m-%d")

    # ── FIX 5: Week = Sunday to Saturday ──
    # dayofweek: Mon=0 … Sun=6 → days since last Sunday = (dayofweek+1)%7
    df["week_num"] = df["date"].dt.isocalendar().week.astype(int)
    df["week"]     = "W" + df["week_num"].astype(str)

    # Plant
    df["plant_code"] = df["plant"].fillna("").astype(str).str.strip()
    df["plant_name"] = df["plant_code"].map(PLANT_MAP).fillna(df["plant_code"])

    # Credit days / due date
    def parse_days(pt):
        if pd.isna(pt): return 30
        nums = re.findall(r'\d+', str(pt))
        return int(nums[-1]) if nums else 30

    df["credit_days"] = df["payment_terms"].apply(parse_days)
    df["due_date"]    = df["date"] + pd.to_timedelta(df["credit_days"], unit="D")

    # Category
    df["category"] = df["material_group"].fillna("Others").astype(str).str.strip()

    print(f"Loaded Rows   : {len(df):,}")
    print(f"Basic Price   : {df['basic_price_val'].sum():,.2f}")
    print(f"Total Invoice : {df['total_value'].sum():,.2f}")
    print(f"MT Tons       : {df['mt_tons'].sum():,.3f}")
    print(f"Mapped        : {df[df['region']!='Others']['customer'].nunique()} customers")
    print(f"Others    : {df[df['region']=='Others']['customer'].nunique()} customers")

    return df

DF    = load_data()
TODAY = pd.Timestamp.now().normalize()   # actual today, not max DB date
print(f"✅ Loaded {len(DF):,} rows | TODAY={TODAY.date()}")

def apply_filters(df, customer=None, from_date=None, to_date=None,
                  week=None, year=None, plant=None, region=None, material=None):
    if region    and region    not in ('all',''):
        df = df[df['region'] == region]
    if year      and str(year) not in ('all',''):
        df = df[df['year'] == int(year)]
    if week      and week      not in ('all',''):
        df = df[df['week'] == week]
    if from_date:
        df = df[df['date'] >= pd.to_datetime(from_date)]
    if to_date:
        df = df[df['date'] <= pd.to_datetime(to_date)]
    if customer  and customer  != 'all':
        df = df[df['customer'].str.lower() == customer.lower()]
    if plant     and plant     not in ('all',''):
        df = df[df['plant_code'] == str(plant)]
    if material  and material  not in ('all',''): 
        df = df[df['category'] == str(material)]
    return df

def safe_json(obj):
    if isinstance(obj, dict):  return {k: safe_json(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [safe_json(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)): return 0
    if isinstance(obj, (np.integer,)):  return int(obj)
    if isinstance(obj, (np.floating,)): return float(obj)
    return obj

@app.after_request
def add_cors(r):
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return r

@app.route('/')
def index():
    return app.send_static_file('index.html')

def get_f():
    return {k: request.args.get(k,'') for k in
            ['customer','from_date','to_date','week','year','plant','region','material']}

def smart_filter(df, f, default_7days=True):
    has_filters = any(f.values())
    if not has_filters and default_7days:
        df = df[df["date"] >= TODAY - pd.Timedelta(days=7)]
    else:
        df = apply_filters(df, **{k: v or None for k, v in f.items()})
    return df

# def smart_filter(df, f, default_7days=True):
#     return apply_filters(df, **{k: v or None for k, v in f.items()})

# ── APIs 
@app.route('/api/yearly_summary')
def yearly_summary():
    grp = DF.groupby('year').agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
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
        'min_date':     str(DF['date'].min().date()),
        'max_date':     str(TODAY.date()),
        'total_rows':   len(DF),
        'customers':    customers,
        'weeks':        week_df['week'].tolist(),
        'years':        [y for y in years if y > 0],
        'plants':       plants,
        'salespersons': get_real_salespersons(),
        'region_heads': REGION_HEAD,
    })

@app.route('/api/kpis')
def kpis():
    f  = get_f()
    df = smart_filter(DF.copy(), f)
    df["is_overdue"] = df["due_date"] < TODAY

    return jsonify(safe_json({
        'total_revenue':    round(df['total_value'].sum(), 2),
        'total_basic':      round(df['basic_price_val'].sum(), 2),
        'total_gst':        round(df['gst_total'].sum(), 2),
        'total_qty':        int(df['qty'].sum()),
        'total_mt_tons':    round(df['mt_tons'].sum(), 3),
        'unique_customers': int(df['customer'].nunique()),
        'transactions':     len(df),
        'record_count':     len(df),
        'outstanding':      round(df['total_value'].sum(), 2),
        'overdue':          round(df[df['is_overdue']]['total_value'].sum(), 2),
    }))

@app.route('/api/revenue_trend')
def revenue_trend():
    f        = get_f()
    group_by = request.args.get('group_by','month')
    df       = smart_filter(DF.copy(), f)

    if group_by == 'day':
        df['period']   = df['date_str']
        df['sort_key'] = df['date_str']
    elif group_by == 'week':
        df['period']   = df['week']
        df['sort_key'] = df['week_num'].astype(str).str.zfill(3)
    else:
        df['period']   = df['year_month']
        df['sort_key'] = df['year_month']

    grp = df.groupby(['period','sort_key']).agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),
        transactions=('total_value','count')
    ).reset_index().sort_values('sort_key')

    return jsonify(safe_json(
        grp.rename(columns={'period':'label'})[
            ['label','revenue','basic','qty','mt_tons','transactions']
        ].to_dict(orient='records')
    ))

@app.route('/api/top_customers')
def top_customers():
    f     = get_f()
    limit = int(request.args.get('limit', 20))
    df    = smart_filter(DF.copy(), f)

    grp = df.groupby('customer').agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),
        transactions=('total_value','count'),
        region=('region','first'),
        salesperson=('salesperson','first'),
    ).reset_index().sort_values('revenue', ascending=False).head(limit)

    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/category_breakdown')
def category_breakdown():
    f  = get_f()
    df = smart_filter(DF.copy(), f)
    grp = df.groupby('category').agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum')
    ).reset_index().sort_values('revenue', ascending=False)
    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/region_breakdown')
def region_breakdown():
    f  = get_f()
    df = smart_filter(DF.copy(), f)
    df["is_overdue"] = df["due_date"] < TODAY

    grp = df.groupby('region').agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),
        transactions=('total_value','count')
    ).reset_index().sort_values('revenue', ascending=False)

    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/plant_breakdown')
def plant_breakdown():
    f  = get_f()
    df = smart_filter(DF.copy(), f)
    grp = df.groupby(['plant_code','plant_name']).agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),
        transactions=('total_value','count'),
        customers=('customer','nunique')
    ).reset_index().sort_values('revenue', ascending=False)
    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/salesperson_breakdown')
def salesperson_breakdown():
    f  = get_f()
    df = smart_filter(DF.copy(), f)
    # ── FIX: filter by salesperson (region-based), not plant ──
    df = df[df['salesperson'].isin(get_real_salespersons())]
    df["is_overdue"] = df["due_date"] < TODAY

    grp = df.groupby('salesperson').agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),
        transactions=('total_value','count'),
        customers=('customer','nunique'),
    ).reset_index().sort_values('revenue', ascending=False)

    return jsonify(safe_json(grp.to_dict(orient='records')))

@app.route('/api/salesperson_all_details')
def salesperson_all_details():
    f  = get_f()
    df = DF.copy()
    df = apply_filters(df,
        customer=f.get("customer") or None,
        from_date=f.get("from_date") or None,
        to_date=f.get("to_date") or None,
        week=f.get("week") or None,
        year=f.get("year") or None,
        plant=f.get("plant") or None,
        region=f.get("region") or None,
    )
    df = df[df['salesperson'].isin(get_real_salespersons())]

    all_weeks  = sorted(df[['week','week_num']].drop_duplicates().values.tolist(), key=lambda x: x[1])
    all_months = sorted(df['year_month'].dropna().unique().tolist())

    result = {}
    for sp in get_real_salespersons():
        sp_df = df[df['salesperson'] == sp]
        monthly = sp_df.groupby('year_month').agg(
            revenue=('total_value','sum'),
            basic=('basic_price_val','sum'),
            qty=('qty','sum'),
            mt_tons=('mt_tons','sum'),
            transactions=('total_value','count')
        ).reset_index().sort_values('year_month')
        weekly = sp_df.groupby(['week','week_num']).agg(
            revenue=('total_value','sum'),
            basic=('basic_price_val','sum'),
            qty=('qty','sum'),
            mt_tons=('mt_tons','sum'),
            transactions=('total_value','count')
        ).reset_index().sort_values('week_num')
        result[sp] = {
            'total_revenue':  round(sp_df['total_value'].sum(), 2),
            'total_basic':    round(sp_df['basic_price_val'].sum(), 2),
            'total_qty':      int(sp_df['qty'].sum()),
            'total_mt_tons':  round(sp_df['mt_tons'].sum(), 3),
            'transactions':   int(len(sp_df)),
            'customers':      int(sp_df['customer'].nunique()),
            'monthly': {r['year_month']: {
                'revenue': round(r['revenue'],2), 'basic': round(r['basic'],2),
                'qty': int(r['qty']), 'mt_tons': round(r['mt_tons'],3),
                'transactions': int(r['transactions'])
            } for r in monthly.to_dict(orient='records')},
            'weekly': {r['week']: {
                'revenue': round(r['revenue'],2), 'basic': round(r['basic'],2),
                'qty': int(r['qty']), 'mt_tons': round(r['mt_tons'],3),
                'transactions': int(r['transactions'])
            } for r in weekly.to_dict(orient='records')},
        }
    return jsonify(safe_json({
        'salespersons': get_real_salespersons(),
        'all_weeks':    [w[0] for w in all_weeks],
        'all_months':   all_months,
        'data':         result
    }))

@app.route('/api/salesperson_detail')
def salesperson_detail():
    f          = get_f()
    salesperson = request.args.get('salesperson', '')
    df = DF.copy()
    df = apply_filters(df,
        from_date=f.get('from_date') or None,
        to_date=f.get('to_date')     or None,
        week=f.get('week')           or None,
        year=f.get('year')           or None,
        plant=f.get('plant')         or None
    )
    # if salesperson: df = df[df['salesperson'] == salesperson]
    
    # if salesperson:
    #     rw = pd.read_sql("""
    #     SELECT DISTINCT "CODE","MARKETING PERSON"
    #     FROM regionwise_customer
    # """, engine)

    #     codes = set(
    #     pd.to_numeric(
    #         rw[rw["MARKETING PERSON"] == salesperson]["CODE"],
    #         errors="coerce"
    #     ).dropna().astype(int)
    # )

    #     df = df[df["cust_code"].isin(codes)]
    # else:           df = df[df['salesperson'].isin(get_real_salespersons())]
    
    if salesperson:
        # Normalize West Customers → West Customer
        sp_normalized = 'West Customer' if salesperson.lower() in ('west customer', 'west customers') else salesperson
        df = df[df['salesperson'] == sp_normalized]
    else:
        df = df[df['salesperson'].isin(get_real_salespersons())]
    

    df["is_overdue"] = df["due_date"] < TODAY

    monthly = df.groupby(['year_month','month_num','year']).agg(
        revenue=('total_value','sum'), basic=('basic_price_val','sum'),
        qty=('qty','sum'), mt_tons=('mt_tons','sum'),
        transactions=('total_value','count')
    ).reset_index().sort_values('year_month')

    weekly = df.groupby(['week','week_num','year']).agg(
        revenue=('total_value','sum'), basic=('basic_price_val','sum'),
        qty=('qty','sum'), mt_tons=('mt_tons','sum'),
        transactions=('total_value','count')
    ).reset_index().sort_values(['year','week_num'])

    plant_split = df.groupby(['plant_code','plant_name']).agg(
        revenue=('total_value','sum'), basic=('basic_price_val','sum'),
        qty=('qty','sum'), mt_tons=('mt_tons','sum')
    ).reset_index().sort_values('revenue', ascending=False)

    cat_split = df.groupby('category').agg(
        revenue=('total_value','sum'), basic=('basic_price_val','sum'),
        qty=('qty','sum'), mt_tons=('mt_tons','sum')
    ).reset_index().sort_values('revenue', ascending=False)

    yearly = df.groupby('year').agg(
        revenue=('total_value','sum'), basic=('basic_price_val','sum'),
        qty=('qty','sum'), mt_tons=('mt_tons','sum'),
        transactions=('total_value','count')
    ).reset_index().sort_values('year')

# Customers under this salesperson
    cust_grp = df.groupby(['customer','region']).agg(
        revenue=('total_value','sum'), basic=('basic_price_val','sum'),
        mt_tons=('mt_tons','sum'), transactions=('total_value','count'),
        overdue=('total_value', lambda x: x[df.loc[x.index,'is_overdue']].sum()),
    ).reset_index()
    cust_grp = cust_grp.sort_values('customer', key=lambda x: x.str.lower(), ascending=True)

    return jsonify(safe_json({
        'salesperson':    salesperson,
        'total_revenue':  round(df['total_value'].sum(), 2),
        'total_basic':    round(df['basic_price_val'].sum(), 2),
        'total_qty':      int(df['qty'].sum()),
        'total_mt_tons':  round(df['mt_tons'].sum(), 3),
        'transactions':   len(df),
        'outstanding':    round(df['total_value'].sum(), 2),
        'overdue':        round(df[df['is_overdue']]['total_value'].sum(), 2),
        'monthly':    monthly[['year_month','month_num','year','revenue','basic','qty','mt_tons','transactions']].to_dict(orient='records'),
        'weekly':     weekly[['week','week_num','year','revenue','basic','qty','mt_tons','transactions']].to_dict(orient='records'),
        'plant_split':plant_split.to_dict(orient='records'),
        'cat_split':  cat_split.to_dict(orient='records'),
        'yearly':     yearly.to_dict(orient='records'),
        'customers':  cust_grp.to_dict(orient='records'),
    }))

@app.route('/api/salesperson_weekly')
def salesperson_weekly():
    f           = get_f()
    salesperson = request.args.get('salesperson','')
    df = DF.copy()
    df = df[df['salesperson'].isin(get_real_salespersons())]

    if f['year']      and f['year']      != 'all': df = df[df['year'] == int(f['year'])]
    if f['from_date']:                              df = df[df['date'] >= pd.to_datetime(f['from_date'])]
    if f['to_date']:                                df = df[df['date'] <= pd.to_datetime(f['to_date'])]
    if f['plant']     and f['plant']     not in ('all',''): df = df[df['plant_code'] == str(f['plant'])]
    if salesperson    and salesperson    != 'all':  df = df[df['salesperson'] == salesperson]

    grp = df.groupby(['salesperson','week','week_num']).agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum'),
        transactions=('total_value','count')
    ).reset_index().sort_values(['salesperson','week_num'])

    all_weeks = sorted(df[['week','week_num']].drop_duplicates().values.tolist(), key=lambda x: x[1])
    return jsonify(safe_json({
        'weeks': [w[0] for w in all_weeks],
        'data':  grp[['salesperson','week','revenue','basic','qty','mt_tons','transactions']].to_dict(orient='records')
    }))

@app.route('/api/customer_detail')
def customer_detail():
    customer = request.args.get('customer','')
    if not customer:
        return jsonify({'error':'customer required'}), 400

    df = DF[DF['customer'].str.lower() == customer.lower()].copy()
    df["is_overdue"] = df["due_date"] < TODAY

    monthly = df.groupby('year_month').agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum')
    ).reset_index().sort_values('year_month')

    cats = df.groupby('category').agg(
        revenue=('total_value','sum'),
        basic=('basic_price_val','sum'),
        qty=('qty','sum'),
        mt_tons=('mt_tons','sum')
    ).reset_index().sort_values('revenue', ascending=False)

    first      = df.iloc[0] if len(df) else {}
    plant_code = str(first.get('plant_code','')) if len(df) else ''

    return jsonify(safe_json({
        'customer':      customer,
        'total_revenue': round(df['total_value'].sum(), 2),
        'total_basic':   round(df['basic_price_val'].sum(), 2),
        'total_qty':     int(df['qty'].sum()),
        'total_mt_tons': round(df['mt_tons'].sum(), 3),
        'transactions':  len(df),
        'outstanding':   round(df['total_value'].sum(), 2),
        'overdue':       round(df[df['is_overdue']]['total_value'].sum(), 2),
        'first_order':   str(df['date'].min().date()) if len(df) else '',
        'last_order':    str(df['date'].max().date())  if len(df) else '',
        'region':        str(first.get('region',''))      if len(df) else '',
        'salesperson':   str(first.get('salesperson','')) if len(df) else '',
        'payment_terms': str(first.get('payment_terms',''))if len(df) else '',
        'plant_code':    plant_code,
        'plant_name':    PLANT_MAP.get(plant_code, plant_code),
        'monthly':       monthly.rename(columns={'year_month':'label'}).to_dict(orient='records'),
        'categories':    cats.to_dict(orient='records'),
    }))

@app.route('/api/collections')
def collections():
    f      = get_f()
    period = request.args.get('period', 'mtd')

    # ── FIX 6: WTD = Sun–Sat ──
    if period == 'mtd':
        start = TODAY.replace(day=1)
        label = 'MTD'
    elif period == 'wtd':
        # days since last Sunday: Mon=0→1, Tue=1→2 … Sun=6→0
        days_since_sun = (TODAY.dayofweek + 1) % 7
        start = TODAY - pd.Timedelta(days=days_since_sun)
        label = 'WTD'
    else:  # ytd
        start = TODAY.replace(month=1, day=1)
        label = 'YTD'

    df = DF.copy()
    df = apply_filters(df,
        customer=f.get('customer') or None,
        plant=f.get('plant')       or None,
        year=f.get('year')         or None,
        region=f.get('region')     or None,
    )
    df_period = df[df['date'] >= start].copy()

    def parse_days(pt):
        if pd.isna(pt): return 30
        nums = re.findall(r'\d+', str(pt))
        return int(nums[-1]) if nums else 30

    # df_period['due_date']    = df_period.apply(
    #     lambda r: r['date'] + pd.Timedelta(days=parse_days(r.get('payment_terms',''))), axis=1
    # )
    # df_period['is_overdue']  = df_period['due_date'] < TODAY
    # df_period['overdue_days']= (TODAY - df_period['due_date']).dt.days

    # df_period['outstanding'] = df_period['total_value']
    # df_period['overdue_val'] = df_period.apply(
    #     lambda r: r['total_value'] if r['is_overdue'] else 0, axis=1
    # )
    # df_period['is_likely_collected'] = df_period['due_date'] < (TODAY - pd.Timedelta(days=15))
    # df_period['collected_val'] = df_period.apply(
    #     lambda r: r['total_value'] if r['is_likely_collected'] else 0, axis=1
    # )
    
    df_period['due_date'] = pd.to_datetime(
    df_period['date'] + pd.to_timedelta(
    df_period['payment_terms'].apply(parse_days), unit='D'
    )
    ).dt.tz_localize(None)
    df_period['is_overdue']   = df_period['due_date'] < TODAY
    df_period['overdue_days'] = (TODAY - df_period['due_date']).dt.days
    df_period['outstanding']  = df_period['total_value']
    df_period['overdue_val']  = df_period['total_value'].where(df_period['is_overdue'], 0)
    df_period['is_likely_collected'] = df_period['due_date'] < (TODAY - pd.Timedelta(days=15))
    df_period['collected_val'] = df_period['total_value'].where(df_period['is_likely_collected'], 0)

    total_invoiced   = df_period['total_value'].sum()
    total_basic      = df_period['basic_price_val'].sum()
    total_outstanding= df_period['outstanding'].sum()
    total_overdue    = df_period['overdue_val'].sum()
    total_collected  = df_period['collected_val'].sum()
    total_mt         = df_period['mt_tons'].sum()
    invoice_count    = df_period['bill_doc_no'].nunique()

    # Aging buckets
    aging = {
        '>180 days': round(float(df_period[df_period['overdue_days']>180]['total_value'].sum()),2),
        '>90 days':  round(float(df_period[df_period['overdue_days']>90]['total_value'].sum()),2),
        '>60 days':  round(float(df_period[df_period['overdue_days']>60]['total_value'].sum()),2),
        '>30 days':  round(float(df_period[df_period['overdue_days']>30]['total_value'].sum()),2),
    }

    # Daily trend
    trend_grp = df_period.groupby('date_str').agg(
        invoiced=('total_value','sum'),
        basic=('basic_price_val','sum'),
        overdue=('overdue_val','sum'),
        mt=('mt_tons','sum')
    ).reset_index().sort_values('date_str')
    trend = trend_grp.rename(columns={'date_str':'date'}).to_dict(orient='records')

    # Payment terms
    terms_grp = df_period.groupby('payment_terms').agg(
        outstanding=('outstanding','sum'),
        overdue=('overdue_val','sum'),
        invoiced=('total_value','sum')
    ).reset_index().sort_values('outstanding', ascending=False)
    terms = terms_grp.head(8).to_dict(orient='records')

    # ── FIX 7: Customer breakdown now includes region & salesperson ──
    cust_grp = df_period.groupby(
        ['customer','payment_terms','gst_no','region','salesperson']
    ).agg(
        invoiced=('total_value','sum'),
        basic=('basic_price_val','sum'),
        outstanding=('outstanding','sum'),
        overdue=('overdue_val','sum'),
        mt_tons=('mt_tons','sum'),
        invoice_count=('bill_doc_no','nunique')
    ).reset_index().sort_values('invoiced', ascending=False)

    customers = []
    for _, row in cust_grp.iterrows():
        customers.append({
            'customer':      row['customer'],
            'region':        str(row.get('region',''))      if not pd.isna(row.get('region','NA')) else '',
            'salesperson':   str(row.get('salesperson','')) if not pd.isna(row.get('salesperson','NA')) else '',
            'gst_no':        str(row.get('gst_no',''))      if not pd.isna(row.get('gst_no','NA')) else '',
            'payment_terms': str(row.get('payment_terms',''))if not pd.isna(row.get('payment_terms','NA')) else '',
            'invoiced':      round(float(row['invoiced']),2),
            'basic':         round(float(row['basic']),2),
            'outstanding':   round(float(row['outstanding']),2),
            'overdue':       round(float(row['overdue']),2),
            'mt_tons':       round(float(row['mt_tons']),3),
            'invoice_count': int(row['invoice_count']),
        })

    return jsonify(safe_json({
        'period':         period,
        'as_of':          str(TODAY.date()),
        'total_invoiced': round(float(total_invoiced),2),
        'total_basic':    round(float(total_basic),2),
        'outstanding':    round(float(total_outstanding),2),
        'overdue':        round(float(total_overdue),2),
        'collected':      round(float(total_collected),2),
        'total_mt':       round(float(total_mt),3),
        'invoice_count':  int(invoice_count),
        'aging':          aging,
        'trend':          trend,
        'terms':          terms,
        'customers':      customers,
    }))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
