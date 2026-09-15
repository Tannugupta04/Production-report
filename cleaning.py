"""Cleaning and SQLite storage helpers."""
from __future__ import annotations
import hashlib, io, sqlite3
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/sales_dashboard.db")

def _connect():
    """Open SQLite with a short wait and WAL mode for Streamlit's concurrent reads."""
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection
ALIASES = {
 "Chicken Malai Tikka (9 Pcs)":"Chicken Malai Tikka", "Chicken Malai Tikka (6 Pcs)":"Chicken Malai Tikka", "Chicken Malai Tikka Roll":"Chicken Malai Tikka",
 "Chicken Peri Peri Tikka (9 Pcs)":"Chicken Peri Peri Tikka", "Chicken Peri Peri Tikka (6 Pcs)":"Chicken Peri Peri Tikka", "Chicken Peri Peri Tikka Roll":"Chicken Peri Peri Tikka", "Chicken Peri Peri Roll":"Chicken Peri Peri Tikka",
 "Chicken Spicy Tikka (9 Pcs)":"Chicken Spicy Tikka", "Chicken Spicy Tikka (6 Pcs)":"Chicken Spicy Tikka", "Chicken Spicy Tikka Roll":"Chicken Spicy Tikka", "Chicken Spicy Roll":"Chicken Spicy Tikka",
 "Chicken Tikka (9 Pcs)":"Chicken Tikka", "Chicken Tikka (6 Pcs)":"Chicken Tikka", "Chicken Tikka Roll":"Chicken Tikka", "Fish Tikka (9 Pcs)":"Fish Tikka", "Fish Tikka (6 Pcs)":"Fish Tikka", "Fish Tikka Roll":"Fish Tikka",
 "Soya Achari Tikka":"Soya Achari", "Soya Achari Tikka Roll":"Soya Achari", "Soya Achari Roll":"Soya Achari", "Soya Tikka (9 Pcs)":"Soya Tikka", "Soya Tikka (6 Pcs)":"Soya Tikka", "Soya Tikka Roll":"Soya Tikka",
 "Paneer Tikka (9 Pcs)":"Paneer Tikka", "Paneer Tikka (6 Pcs)":"Paneer Tikka", "Paneer Tikka Roll":"Paneer Tikka", "Paneer Zaika (Large (800 gms))":"Paneer Zaika", "Paneer Zaika (Regular (400gms))":"Paneer Zaika",
 "Chicken Seekh":"Chicken Seekh Kebab", "Chicken Seekh Roll":"Chicken Seekh Kebab", "Mutton Kakori":"Mutton Kakori Kebab", "Mutton Kakori Roll":"Mutton Kakori Kebab", "Mutton Seekh":"Mutton Seekh Kebab", "Mutton Seekh Roll":"Mutton Seekh Kebab", "Veg Hariyali Kebab":"Veg Haryali Kebab",
 "Butter Chicken (Large (900 gms))":"Butter Chicken", "Butter Chicken (Regular (450 gms))":"Butter Chicken", "Dal Makhni":"Dal Makhani", "Dal Makhani (Large (560 gms))":"Dal Makhani", "Dal Makhani (Regular (280 gms))":"Dal Makhani",
 "Chicken Korma (Large (800 gms))":"Chicken Korma", "Chicken Korma (Regular (400 gms))":"Chicken Korma", "Mutton Nihari (Large (740 gms))":"Mutton Nihari", "Mutton Nihari (Regular (370 gms))":"Mutton Nihari", "Mutton Korma (Large (800 gms))":"Mutton Korma", "Mutton Korma (Regular (400 gms))":"Mutton Korma", "Mutton Haleem (Large (500 gms))":"Mutton Haleem", "Mutton Haleem (Regular (250 gms))":"Mutton Haleem",
 "Soya Tawa Masala (Large (940 gms))":"Soya Tawa Masala", "Soya Tawa Masala (Regular (470 gms))":"Soya Tawa Masala", "Taftan":"Taftaan", "Gulab Jamun 1 Pc":"Gulab Jamun", "Bisleri Vedica @60":"Water Bottle", "Purani Dilli Achari Biryani Non Veg":"Non-Veg achari biryani", "Purani Dilli Achari Biryani Veg":"Veg achari biryani", "Veg Achari Biryani":"Veg achari biryani"}
HANDLERS = {"Chicken Malai Tikka":"Lalan", "Chicken Peri Peri Tikka":"Lalan", "Chicken Spicy Tikka":"Lalan", "Chicken Tikka":"Lalan", "Fish Tikka":"Lalan", "Soya Achari":"Lalan", "Soya Tikka":"Lalan", "Paneer Tikka":"Lalan", "Chicken Seekh Kebab":"Lalan", "Mutton Kakori Kebab":"Lalan", "Mutton Seekh Kebab":"Lalan", "Veg Haryali Kebab":"Lalan", "Kakori Paste":"Lalan", "Chicken Tikka Masala":"Lalan", "Mutton Seekh Masala":"Lalan", "Mutton Kakori Masala":"Lalan", "Teekhi Chutney Premix":"Lalan", "Green Chutney Premix Big":"Lalan", "Green Chutney Premix Small":"Lalan", "Chicken Biryani":"Rajesh", "Mutton Biryani":"Rajesh", "Non-Veg achari biryani":"Rajesh", "Veg achari biryani":"Rajesh", "Veg Biryani":"Rajesh", "Chicken Korma":"Rajesh", "Mutton Haleem":"Rajesh", "Mutton Korma":"Rajesh", "Phirni":"Rajesh", "Normal Biryani Mist":"Rajesh", "Biryani achari MIST":"Rajesh", "Butter Chicken":"Sunil Thakur", "Dal Makhani":"Sunil Thakur", "Soya Tawa Masala":"Sunil Thakur", "Paneer Zaika":"Sunil Thakur", "Brown Onion":"Sunil Thakur", "Mutton Nihari":"Sunil Thakur", "Shahi Tukda":"Sunil Thakur", "Raita Premix":"Sunil Thakur", "Taftaan":"Hazik", "Roomali Roti":"Hazik", "Jr.Roomali roti":"Hazik", "Gulab Jamun":"Hazik", "Butter Naan":"Hazik"}
KITCHEN = {"Chicken Malai Tikka","Chicken Peri Peri Tikka","Chicken Spicy Tikka","Chicken Tikka","Fish Tikka","Soya Achari","Soya Tikka","Paneer Tikka","Chicken Seekh Kebab","Mutton Kakori Kebab","Mutton Seekh Kebab","Veg Haryali Kebab","Kakori Paste","Chicken Tikka Masala","Mutton Seekh Masala","Mutton Kakori Masala","Teekhi Chutney Premix","Green Chutney Premix Big","Butter Chicken","Dal Makhani","Soya Tawa Masala","Paneer Zaika","Brown Onion","Mutton Nihari","Shahi Tukda","Chicken Biryani","Mutton Biryani","Non-Veg achari biryani","Veg achari biryani","Veg Biryani","Chicken Korma","Mutton Haleem","Mutton Korma","Phirni","Taftaan","Roomali Roti","Jr.Roomali roti","Gulab Jamun"}

def read_uploaded_file(uploaded_file):
    blob=uploaded_file.getvalue()
    if uploaded_file.name.lower().endswith((".xlsx",".xls")): return pd.read_excel(io.BytesIO(blob))
    for encoding in ("utf-8-sig","utf-8","latin-1"):
        try: return pd.read_csv(io.BytesIO(blob), low_memory=False, encoding=encoding)
        except UnicodeDecodeError: continue
    return pd.read_csv(io.BytesIO(blob), low_memory=False)

def normalise_names(series):
    return series.astype(str).str.strip().str.replace(r"\s+"," ",regex=True).str.rstrip(".").replace(ALIASES)

def _base(raw, qty_col, status):
    required=["Branch Code","Invoice Number","Business Date","Order Source","Item Name",qty_col,"Net Amount"]
    missing=[x for x in required if x not in raw]
    if missing: raise ValueError(f"{status} file is missing: {', '.join(missing)}")
    time=pd.to_datetime(raw.get("Created Time",raw.get("Invoice Date")),errors="coerce")
    return pd.DataFrame({"outlet":raw["Branch Code"],"invoice":raw["Invoice Number"],"date":pd.to_datetime(raw["Business Date"],errors="coerce"),"order_source":raw["Order Source"],"item_name":raw["Item Name"],"quantity":pd.to_numeric(raw[qty_col],errors="coerce").fillna(0),"net_sales":pd.to_numeric(raw["Net Amount"],errors="coerce").fillna(0),"category":raw.get("Category","Uncategorised"),"customer_name":raw.get("Customer Name",""),"customer_phone":raw.get("Customer Phone",""),"status":status,"hour":time.dt.hour})

def clean_uploads(sales_upload,cancel_upload):
    sales_raw,cancel_raw=read_uploaded_file(sales_upload),read_uploaded_file(cancel_upload)
    sales,cancels=_base(sales_raw,"Sale Item Qty","Completed"),_base(cancel_raw,"Original Quantity","Cancelled")
    if {"Item Name","Type","Parent Item Name (Sold With)"}.issubset(sales_raw):
        q=pd.to_numeric(sales_raw["Sale Item Qty"],errors="coerce"); parent=sales_raw["Parent Item Name (Sold With)"].astype(str); opt=sales_raw["Type"].eq("Option"); mult=pd.Series(1.,index=sales_raw.index); dilli=["Dilli Dawat Combo (Veg)","Dilli Dawat Combo (Non Veg)"]
        mult.loc[(sales_raw["Item Name"]=="Taftan")&opt&parent.isin(dilli)&q.eq(1)]=2; mult.loc[(sales_raw["Item Name"]=="Roomali Roti")&opt&parent.isin(dilli)&q.eq(1)]=4; mult.loc[(sales_raw["Item Name"]=="Roomali Roti")&opt&parent.eq("Mughlai Non Veg Curry Combo")&q.eq(1)]=2; sales["quantity"]*=mult.to_numpy()
    data=pd.concat([sales,cancels],ignore_index=True); large={"Chicken Korma (Large (800 gms))","Butter Chicken (Large (900 gms))","Paneer Zaika (Large (800 gms))","Dal Makhani (Large (560 gms))","Mutton Korma (Large (800 gms))","Mutton Nihari (Large (740 gms))","Mutton Haleem (Large (500 gms))","Soya Tawa Masala (Large (940 gms))"}; data.loc[normalise_names(data.item_name).isin(large),"quantity"]*=2
    data["outlet"]=data.outlet.replace({"NDL":"CP","CP-67":"CP67"}); data["item_name"]=normalise_names(data.item_name); data["handler"]=data.item_name.map(HANDLERS); data.loc[data.handler.isna()&data.item_name.str.contains("Coke|Sprite|Fanta|Limca|Thums Up|Water|Red Bull|Ice Tea|Ginger Ale",case=False,na=False),"handler"]="Drinks"; data.loc[data.handler.isna()&data.item_name.isin(KITCHEN),"handler"]="Kitchen"; data["handler"]=data.handler.fillna("Unassigned")
    data["order_source"]=data.order_source.astype(str).str.lower().map({"pos":"POS","zomato":"Zomato","swiggy":"Swiggy","magic_pin":"Magic_pin"}).fillna("Other"); data["weekday"]=data.date.dt.day_name(); data["month"]=data.date.dt.strftime("%B %Y"); data["week_number"]=data.date.dt.isocalendar().week.astype("Int64"); data["sales_impact"]=data.net_sales.where(data.status.eq("Completed"),-data.net_sales.abs()); data["quantity_impact"]=data.quantity.where(data.status.eq("Completed"),-data.quantity.abs())
    return data.dropna(subset=["date","item_name"]).reset_index(drop=True)

def init_database():
    DB_PATH.parent.mkdir(exist_ok=True)
    with _connect() as conn:
        try:
            conn.execute("ALTER TABLE cleaned_transactions ADD COLUMN handler TEXT")
        except sqlite3.OperationalError:
            pass
        conn.execute("CREATE TABLE IF NOT EXISTS uploads (batch_id TEXT PRIMARY KEY, uploaded_at TEXT, sales_filename TEXT, cancel_filename TEXT, row_count INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS cleaned_transactions (batch_id TEXT, outlet TEXT, invoice TEXT, date TEXT, order_source TEXT, item_name TEXT, quantity REAL, net_sales REAL, category TEXT, customer_name TEXT, customer_phone TEXT, status TEXT, hour REAL, handler TEXT, weekday TEXT, month TEXT, week_number INTEGER, sales_impact REAL, quantity_impact REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS dispatch_uploads (batch_id TEXT PRIMARY KEY, uploaded_at TEXT, filename TEXT, row_count INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS cleaned_dispatch (batch_id TEXT, transfer_date TEXT, item_name TEXT, quantity_delivered REAL, weekday TEXT, week_start TEXT)")

def save_batch(data,sales_upload,cancel_upload):
    init_database(); bid=hashlib.sha256(sales_upload.getvalue()+cancel_upload.getvalue()).hexdigest()[:16]
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM uploads WHERE batch_id=?",(bid,)).fetchone(): return bid,False
        conn.execute("INSERT INTO uploads VALUES (?,?,?,?,?)",(bid,datetime.now(timezone.utc).isoformat(),sales_upload.name,cancel_upload.name,len(data))); d=data.copy(); d["batch_id"]=bid; d.date=d.date.dt.strftime("%Y-%m-%d"); d.to_sql("cleaned_transactions",conn,if_exists="append",index=False)
    return bid,True

def load_data():
    init_database()
    with _connect() as conn: d=pd.read_sql_query("SELECT * FROM cleaned_transactions",conn)
    if not d.empty: d.date=pd.to_datetime(d.date)
    return d

def upload_summary():
    init_database()
    with _connect() as conn: return pd.read_sql_query("SELECT * FROM uploads ORDER BY uploaded_at DESC",conn)

def clean_dispatch_upload(uploaded_file):
    raw=read_uploaded_file(uploaded_file); req=["Item Name","Quantity Delivered","Transfer Date"]; missing=[x for x in req if x not in raw]
    if missing: raise ValueError(f"Dispatch file is missing: {', '.join(missing)}")
    d=raw[req].rename(columns={"Item Name":"item_name","Quantity Delivered":"quantity_delivered","Transfer Date":"transfer_date"}); d.item_name=normalise_names(d.item_name); d.quantity_delivered=pd.to_numeric(d.quantity_delivered,errors="coerce"); d.transfer_date=pd.to_datetime(d.transfer_date,errors="coerce").dt.normalize(); d=d.dropna(); d=d[d.quantity_delivered.gt(0)].copy(); d["weekday"]=d.transfer_date.dt.day_name(); d["week_start"]=d.transfer_date-pd.to_timedelta(d.transfer_date.dt.dayofweek,unit="D"); return d.reset_index(drop=True)

def save_dispatch_batch(data,uploaded_file):
    init_database(); bid=hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:16]
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM dispatch_uploads WHERE batch_id=?",(bid,)).fetchone(): return bid,False
        conn.execute("INSERT INTO dispatch_uploads VALUES (?,?,?,?)",(bid,datetime.now(timezone.utc).isoformat(),uploaded_file.name,len(data))); d=data.copy(); d["batch_id"]=bid; d.transfer_date=d.transfer_date.dt.strftime("%Y-%m-%d"); d.week_start=d.week_start.dt.strftime("%Y-%m-%d"); d.to_sql("cleaned_dispatch",conn,if_exists="append",index=False)
    return bid,True

def load_dispatch_data():
    init_database()
    with _connect() as conn: d=pd.read_sql_query("SELECT * FROM cleaned_dispatch",conn)
    if not d.empty: d.transfer_date=pd.to_datetime(d.transfer_date); d.week_start=pd.to_datetime(d.week_start)
    return d


def normalise_database_sales():
    """Apply current clean item names and handler labels to records stored earlier."""
    init_database()
    with _connect() as conn:
        data = pd.read_sql_query("SELECT * FROM cleaned_transactions", conn)
        if data.empty:
            return
        data["item_name"] = normalise_names(data["item_name"])
        data["handler"] = data["item_name"].map(HANDLERS)
        drink = data["item_name"].str.contains("Coke|Sprite|Fanta|Limca|Thums Up|Water|Red Bull|Ice Tea|Ginger Ale", case=False, na=False)
        data.loc[data["handler"].isna() & drink, "handler"] = "Drinks"
        data.loc[data["handler"].isna() & data["item_name"].isin(KITCHEN), "handler"] = "Kitchen"
        data["handler"] = data["handler"].fillna("Unassigned")
        data.to_sql("cleaned_transactions", conn, if_exists="replace", index=False)


