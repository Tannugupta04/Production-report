"""Cleaning and SQLite storage helpers for the dashboard."""
from __future__ import annotations

import hashlib
import io
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/sales_dashboard.db")

# Standardises reporting names while preserving unlisted items.
ALIASES = {
    "Chicken Malai Tikka (9 Pcs)": "Chicken Malai Tikka", "Chicken Malai Tikka (6 Pcs)": "Chicken Malai Tikka", "Chicken Malai Tikka Roll": "Chicken Malai Tikka",
    "Chicken Peri Peri Tikka (9 Pcs)": "Chicken Peri Peri Tikka", "Chicken Peri Peri Tikka (6 Pcs)": "Chicken Peri Peri Tikka", "Chicken Peri Peri Tikka Roll": "Chicken Peri Peri Tikka", "Chicken Peri Peri Roll": "Chicken Peri Peri Tikka",
    "Chicken Spicy Tikka (9 Pcs)": "Chicken Spicy Tikka", "Chicken Spicy Tikka (6 Pcs)": "Chicken Spicy Tikka", "Chicken Spicy Tikka Roll": "Chicken Spicy Tikka", "Chicken Spicy Roll": "Chicken Spicy Tikka",
    "Chicken Tikka (9 Pcs)": "Chicken Tikka", "Chicken Tikka (6 Pcs)": "Chicken Tikka", "Chicken Tikka Roll": "Chicken Tikka", "Fish Tikka (9 Pcs)": "Fish Tikka", "Fish Tikka (6 Pcs)": "Fish Tikka", "Fish Tikka Roll": "Fish Tikka",
    "Soya Achari Tikka": "Soya Achari", "Soya Achari Tikka Roll": "Soya Achari", "Soya Achari Roll": "Soya Achari", "Soya Tikka (9 Pcs)": "Soya Tikka", "Soya Tikka (6 Pcs)": "Soya Tikka", "Soya Tikka Roll": "Soya Tikka",
    "Paneer Tikka (9 Pcs)": "Paneer Tikka", "Paneer Tikka (6 Pcs)": "Paneer Tikka", "Paneer Tikka Roll": "Paneer Tikka", "Paneer Zaika (Large (800 gms))": "Paneer Zaika", "Paneer Zaika (Regular (400gms))": "Paneer Zaika",
    "Chicken Seekh": "Chicken Seekh Kebab", "Chicken Seekh Roll": "Chicken Seekh Kebab", "Mutton Kakori": "Mutton Kakori Kebab", "Mutton Kakori Roll": "Mutton Kakori Kebab", "Mutton Seekh": "Mutton Seekh Kebab", "Mutton Seekh Roll": "Mutton Seekh Kebab", "Veg Hariyali Kebab": "Veg Haryali Kebab",
    "Butter Chicken (Large (900 gms))": "Butter Chicken", "Butter Chicken (Regular (450 gms))": "Butter Chicken", "Dal Makhni": "Dal Makhani", "Dal Makhani (Large (560 gms))": "Dal Makhani", "Dal Makhani (Regular (280 gms))": "Dal Makhani",
    "Chicken Korma (Large (800 gms))": "Chicken Korma", "Chicken Korma (Regular (400 gms))": "Chicken Korma", "Mutton Nihari (Large (740 gms))": "Mutton Nihari", "Mutton Nihari (Regular (370 gms))": "Mutton Nihari", "Mutton Korma (Large (800 gms))": "Mutton Korma", "Mutton Korma (Regular (400 gms))": "Mutton Korma", "Mutton Haleem (Large (500 gms))": "Mutton Haleem", "Mutton Haleem (Regular (250 gms))": "Mutton Haleem",
    "Soya Tawa Masala (Large (940 gms))": "Soya Tawa Masala", "Soya Tawa Masala (Regular (470 gms))": "Soya Tawa Masala", "Taftan": "Taftaan", "Gulab Jamun 1 Pc": "Gulab Jamun", "Bisleri Vedica @60": "Water Bottle", "Purani Dilli Achari Biryani Non Veg": "Non-Veg achari biryani", "Purani Dilli Achari Biryani Veg": "Veg achari biryani", "Veg Achari Biryani": "Veg achari biryani",
    "Chicken Malai Tikka (3 Pcs)": "Chicken Malai Tikka", "Chicken Peri Peri Tikka (3 Pcs)": "Chicken Peri Peri Tikka", "Chicken Spicy Tikka (3 Pcs)": "Chicken Spicy Tikka", "Chicken Tikka (3 Pcs)": "Chicken Tikka", "Fish Tikka (3 Pcs)": "Fish Tikka", "Soya Tikka (3 Pcs)": "Soya Tikka", "Paneer Tikka (3 Pcs)": "Paneer Tikka",
    "Junior Chicken Malai Tikka Roll": "Chicken Malai Tikka", "Junior Chicken Peri Peri Tikka Roll": "Chicken Peri Peri Tikka", "Junior Chicken Spicy Tikka Roll": "Chicken Spicy Tikka", "Junior Chicken Tikka Roll": "Chicken Tikka", "Junior Fish Tikka Roll": "Fish Tikka", "Junior Soya Achari Roll": "Soya Achari", "Junior Soya Tikka Roll": "Soya Tikka", "Junior Paneer Tikka Roll": "Paneer Tikka",
    "Chicken Seekh Kebab Roll": "Chicken Seekh Kebab", "Mutton Kakori Kebab Roll": "Mutton Kakori Kebab", "Mutton Seekh Kebab Roll": "Mutton Seekh Kebab", "Veg Haryali Kebab Roll": "Veg Haryali Kebab",
    "Mutton Kroma": "Mutton Korma", "Mutton Korma (200 Gms)": "Mutton Korma", "Mutton Korma (400 Gms)": "Mutton Korma", "Butter Chicken (1pc)": "Butter Chicken", "Butter Chicken (200 Gms)": "Butter Chicken", "Paneer Zaika (200 Gms)": "Paneer Zaika", "Soya Tawa Masala (200 Gms)": "Soya Tawa Masala",
    "Coke.": "Coke", "Coca Cola": "Coke", "Coke Zero": "Coke", "Pepsi Black": "Pepsi", "Pepsi Zero Sugar": "Pepsi", "7 Up": "7UP", "Aam Ras@80": "Aam Ras", "Red Bull": "Redbull Plain", "Red Bull Original": "Redbull Plain", "Redbull": "Redbull Plain", "Bisleri": "Water Bottle", "Bisleri Water": "Water Bottle", "Vedica Water": "Water Bottle",}
HANDLERS = {
    "Chicken Malai Tikka": "Lalan", "Chicken Peri Peri Tikka": "Lalan", "Chicken Spicy Tikka": "Lalan", "Chicken Tikka": "Lalan", "Fish Tikka": "Lalan", "Soya Achari": "Lalan", "Soya Tikka": "Lalan", "Paneer Tikka": "Lalan", "Chicken Seekh Kebab": "Lalan", "Mutton Kakori Kebab": "Lalan", "Mutton Seekh Kebab": "Lalan", "Veg Haryali Kebab": "Lalan", "Kakori Paste": "Lalan", "Chicken Tikka Masala": "Lalan", "Mutton Seekh Masala": "Lalan", "Mutton Kakori Masala": "Lalan", "Teekhi Chutney Premix": "Lalan", "Green Chutney Premix Big": "Lalan", "Green Chutney Premix Small": "Lalan",
    "Chicken Biryani": "Rajesh", "Mutton Biryani": "Rajesh", "Non-Veg achari biryani": "Rajesh", "Veg achari biryani": "Rajesh", "Veg Biryani": "Rajesh", "Chicken Korma": "Rajesh", "Mutton Haleem": "Rajesh", "Mutton Korma": "Rajesh", "Phirni": "Rajesh", "Normal Biryani Mist": "Rajesh", "Biryani achari MIST": "Rajesh",
    "Butter Chicken": "Sunil Thakur", "Dal Makhani": "Sunil Thakur", "Soya Tawa Masala": "Sunil Thakur", "Paneer Zaika": "Sunil Thakur", "Brown Onion": "Sunil Thakur", "Mutton Nihari": "Sunil Thakur", "Shahi Tukda": "Sunil Thakur", "Raita Premix": "Sunil Thakur",
    "Taftaan": "Hazik", "Roomali Roti": "Hazik", "Jr.Roomali roti": "Hazik", "Gulab Jamun": "Hazik", "Butter Naan": "Hazik",
}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_database() -> None:
    with _connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS uploads (batch_id TEXT PRIMARY KEY, uploaded_at TEXT, sales_filename TEXT, cancel_filename TEXT, row_count INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS cleaned_transactions (batch_id TEXT, outlet TEXT, invoice TEXT, date TEXT, order_source TEXT, item_name TEXT, quantity REAL, unit TEXT, net_sales REAL, category TEXT, customer_name TEXT, customer_phone TEXT, status TEXT, hour REAL, handler TEXT, weekday TEXT, month TEXT, week_number INTEGER, sales_impact REAL, quantity_impact REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS dispatch_uploads (batch_id TEXT PRIMARY KEY, uploaded_at TEXT, filename TEXT, row_count INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS cleaned_dispatch (batch_id TEXT, transfer_date TEXT, item_name TEXT, quantity_delivered REAL, weekday TEXT, week_start TEXT)")
        for column, definition in (("handler", "TEXT"), ("unit", "TEXT DEFAULT 'units'")):
            try:
                conn.execute(f"ALTER TABLE cleaned_transactions ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        conn.execute("UPDATE cleaned_transactions SET unit = 'units' WHERE unit IS NULL OR TRIM(unit) = ''")


def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    payload = uploaded_file.getvalue()
    if uploaded_file.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(payload))
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(payload), low_memory=False, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.BytesIO(payload), low_memory=False)


def _item_key(value: object) -> str:
    """Comparison key that removes harmless punctuation, case and extra spaces."""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


_ALIASES_BY_KEY = {_item_key(source): target for source, target in ALIASES.items()}


def normalise_names(series: pd.Series) -> pd.Series:
    """Return one reporting name for spelling, punctuation and pack-size variants."""
    cleaned = series.astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.rstrip(".")
    return cleaned.map(lambda value: _ALIASES_BY_KEY.get(_item_key(value), value))

def _base(raw: pd.DataFrame, quantity_column: str, status: str) -> pd.DataFrame:
    required = ["Branch Code", "Invoice Number", "Business Date", "Order Source", "Item Name", quantity_column, "Net Amount"]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise ValueError(f"{status} file is missing: {', '.join(missing)}")
    timestamp_source = raw["Created Time"] if "Created Time" in raw.columns else raw.get("Invoice Date", pd.Series(pd.NaT, index=raw.index))
    timestamp = pd.to_datetime(timestamp_source, errors="coerce")
    return pd.DataFrame({
        "outlet": raw["Branch Code"], "invoice": raw["Invoice Number"], "date": pd.to_datetime(raw["Business Date"], errors="coerce"),
        "order_source": raw["Order Source"], "item_name": raw["Item Name"], "quantity": pd.to_numeric(raw[quantity_column], errors="coerce").fillna(0),
        "unit": raw.get("Measuring Unit", pd.Series("units", index=raw.index)), "net_sales": pd.to_numeric(raw["Net Amount"], errors="coerce").fillna(0),
        "category": raw.get("Category", pd.Series("Uncategorised", index=raw.index)), "customer_name": raw.get("Customer Name", pd.Series("", index=raw.index)),
        "customer_phone": raw.get("Customer Phone", pd.Series("", index=raw.index)), "status": status, "hour": timestamp.dt.hour,
    })


def _handler(data: pd.DataFrame) -> pd.Series:
    result = data["item_name"].map(HANDLERS)
    drink = data["item_name"].str.contains("Coke|Pepsi|Sprite|Fanta|Limca|Thums Up|Water|Bisleri|Vedica|Red ?Bull|Redbull|Ice Tea|Ginger Ale|7UP|Mirinda|Mountain Dew", case=False, na=False)
    return result.mask(result.isna() & drink, "Drinks").fillna("Unassigned")


def clean_uploads(sales_upload, cancel_upload) -> pd.DataFrame:
    sales_raw, cancel_raw = read_uploaded_file(sales_upload), read_uploaded_file(cancel_upload)
    sales, cancels = _base(sales_raw, "Sale Item Qty", "Completed"), _base(cancel_raw, "Original Quantity", "Cancelled")
    if {"Item Name", "Type", "Parent Item Name (Sold With)"}.issubset(sales_raw.columns):
        qty = pd.to_numeric(sales_raw["Sale Item Qty"], errors="coerce")
        parent, option = sales_raw["Parent Item Name (Sold With)"].astype(str), sales_raw["Type"].eq("Option")
        multiplier = pd.Series(1.0, index=sales_raw.index)
        dilli = ["Dilli Dawat Combo (Veg)", "Dilli Dawat Combo (Non Veg)"]
        multiplier.loc[(sales_raw["Item Name"] == "Taftan") & option & parent.isin(dilli) & qty.eq(1)] = 2
        multiplier.loc[(sales_raw["Item Name"] == "Roomali Roti") & option & parent.isin(dilli) & qty.eq(1)] = 4
        multiplier.loc[(sales_raw["Item Name"] == "Roomali Roti") & option & parent.eq("Mughlai Non Veg Curry Combo") & qty.eq(1)] = 2
        sales["quantity"] *= multiplier.to_numpy()
    data = pd.concat([sales, cancels], ignore_index=True)
    data["outlet"] = data["outlet"].replace({"NDL": "CP", "CP-67": "CP67"})
    data["source_item_name"] = data["item_name"].astype(str).str.strip()
    data["item_name"] = normalise_names(data["item_name"])
    large_gravy = data["source_item_name"].str.contains(r"Large.*(?:800|900|940|740|560|500)\s*g", case=False, regex=True, na=False)
    plate_items = data["item_name"].isin({"Chicken Korma", "Butter Chicken", "Paneer Zaika", "Dal Makhani", "Mutton Korma", "Mutton Nihari", "Mutton Haleem", "Soya Tawa Masala"})
    data.loc[large_gravy & plate_items, "quantity"] *= 2
    data["unit"] = data["unit"].fillna("units").astype(str).str.strip().replace({"ea": "units", "EA": "units", "piece": "pieces", "Piece": "pieces"})
    data["handler"] = _handler(data)
    data["order_source"] = data["order_source"].astype(str).str.strip().str.lower().map({"pos": "POS", "zomato": "Zomato", "swiggy": "Swiggy", "magic_pin": "Magic_pin"}).fillna("Other")
    data["weekday"] = data["date"].dt.day_name(); data["month"] = data["date"].dt.strftime("%B %Y"); data["week_number"] = data["date"].dt.isocalendar().week.astype("Int64")
    data["sales_impact"] = data["net_sales"].where(data["status"].eq("Completed"), -data["net_sales"].abs())
    data["quantity_impact"] = data["quantity"].where(data["status"].eq("Completed"), -data["quantity"].abs())
    return data.dropna(subset=["date", "item_name"]).reset_index(drop=True)


def save_batch(data: pd.DataFrame, sales_upload, cancel_upload) -> tuple[str, bool]:
    init_database(); batch_id = hashlib.sha256(sales_upload.getvalue() + cancel_upload.getvalue()).hexdigest()[:16]
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM uploads WHERE batch_id = ?", (batch_id,)).fetchone(): return batch_id, False
        conn.execute("INSERT INTO uploads VALUES (?, ?, ?, ?, ?)", (batch_id, datetime.now(timezone.utc).isoformat(), sales_upload.name, cancel_upload.name, len(data)))
        stored = data.copy(); stored["batch_id"] = batch_id; stored["date"] = stored["date"].dt.strftime("%Y-%m-%d")
        stored.to_sql("cleaned_transactions", conn, if_exists="append", index=False)
    return batch_id, True


def load_data() -> pd.DataFrame:
    init_database()
    with _connect() as conn: data = pd.read_sql_query("SELECT * FROM cleaned_transactions", conn)
    if not data.empty: data["date"] = pd.to_datetime(data["date"])
    return data


def upload_summary() -> pd.DataFrame:
    init_database()
    with _connect() as conn: return pd.read_sql_query("SELECT * FROM uploads ORDER BY uploaded_at DESC", conn)


def clean_dispatch_upload(uploaded_file) -> pd.DataFrame:
    raw = read_uploaded_file(uploaded_file); required = ["Item Name", "Quantity Delivered", "Transfer Date"]
    missing = [column for column in required if column not in raw.columns]
    if missing: raise ValueError(f"Dispatch file is missing: {', '.join(missing)}")
    data = raw[required].rename(columns={"Item Name": "item_name", "Quantity Delivered": "quantity_delivered", "Transfer Date": "transfer_date"}).copy()
    data["source_item_name"] = data["item_name"].astype(str).str.strip()
    data["item_name"] = normalise_names(data["item_name"]); data["quantity_delivered"] = pd.to_numeric(data["quantity_delivered"], errors="coerce"); data["transfer_date"] = pd.to_datetime(data["transfer_date"], errors="coerce").dt.normalize()
    data = data.dropna().loc[lambda frame: frame["quantity_delivered"].gt(0)].copy(); data["weekday"] = data["transfer_date"].dt.day_name(); data["week_start"] = data["transfer_date"] - pd.to_timedelta(data["transfer_date"].dt.dayofweek, unit="D")
    return data.reset_index(drop=True)


def save_dispatch_batch(data: pd.DataFrame, uploaded_file) -> tuple[str, bool]:
    init_database(); batch_id = hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:16]
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM dispatch_uploads WHERE batch_id = ?", (batch_id,)).fetchone(): return batch_id, False
        conn.execute("INSERT INTO dispatch_uploads VALUES (?, ?, ?, ?)", (batch_id, datetime.now(timezone.utc).isoformat(), uploaded_file.name, len(data)))
        stored = data.copy(); stored["batch_id"] = batch_id; stored["transfer_date"] = stored["transfer_date"].dt.strftime("%Y-%m-%d"); stored["week_start"] = stored["week_start"].dt.strftime("%Y-%m-%d")
        stored.to_sql("cleaned_dispatch", conn, if_exists="append", index=False)
    return batch_id, True


def load_dispatch_data() -> pd.DataFrame:
    init_database()
    with _connect() as conn: data = pd.read_sql_query("SELECT * FROM cleaned_dispatch", conn)
    if not data.empty: data["transfer_date"] = pd.to_datetime(data["transfer_date"]); data["week_start"] = pd.to_datetime(data["week_start"])
    return data

# Optional persistent deployment storage.  On Streamlit Cloud add DATABASE_URL
# to Secrets; locally the app continues to use data/sales_dashboard.db.
def _external_database_url():
    import os
    value = os.getenv("DATABASE_URL")
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get("DATABASE_URL")
    except Exception:
        return None

_EXTERNAL_URL = _external_database_url()

class DatabaseConnectionError(RuntimeError):
    """A safe deployment message that never exposes the connection string."""

def database_status():
    return "PostgreSQL (persistent deployment database)" if _EXTERNAL_URL else "Local SQLite (persistent only on this computer)"

if _EXTERNAL_URL:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError
    _url = _EXTERNAL_URL.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)
    _ENGINE = create_engine(_url, pool_pre_ping=True, pool_size=1, max_overflow=1, connect_args={"sslmode": "require"})

    def init_database():
        try:
            with _ENGINE.begin() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS uploads (batch_id TEXT PRIMARY KEY, uploaded_at TEXT, sales_filename TEXT, cancel_filename TEXT, row_count INTEGER)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS cleaned_transactions (batch_id TEXT, outlet TEXT, invoice TEXT, date TEXT, order_source TEXT, item_name TEXT, quantity DOUBLE PRECISION, unit TEXT, net_sales DOUBLE PRECISION, category TEXT, customer_name TEXT, customer_phone TEXT, status TEXT, hour DOUBLE PRECISION, handler TEXT, weekday TEXT, month TEXT, week_number INTEGER, sales_impact DOUBLE PRECISION, quantity_impact DOUBLE PRECISION)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS dispatch_uploads (batch_id TEXT PRIMARY KEY, uploaded_at TEXT, filename TEXT, row_count INTEGER)"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS cleaned_dispatch (batch_id TEXT, transfer_date TEXT, item_name TEXT, quantity_delivered DOUBLE PRECISION, weekday TEXT, week_start TEXT)"))
        except OperationalError as error:
            provider_message = str(error).lower()
            if "password authentication failed" in provider_message:
                reason = "Supabase rejected the database password. Reset or re-enter the database password, then URL-encode any special characters."
            elif "could not translate host name" in provider_message or "name or service not known" in provider_message:
                reason = "The pooler host is incorrect. Copy it again from Supabase Connect > Session pooler."
            elif "connection refused" in provider_message or "timeout" in provider_message:
                reason = "The database is unavailable or paused. Confirm the Supabase project is Active and use the Session pooler on port 5432."
            elif "network is unreachable" in provider_message:
                reason = "The direct database endpoint is unreachable. Use the IPv4 Session pooler host ending in .pooler.supabase.com."
            else:
                reason = "Confirm Session pooler port 5432, username postgres.PROJECT_REF, sslmode=require, an active project, and a URL-encoded password."
            raise DatabaseConnectionError(f"Unable to connect to the hosted database. {reason}") from None

    def save_batch(data, sales_upload, cancel_upload):
        init_database(); batch_id = hashlib.sha256(sales_upload.getvalue() + cancel_upload.getvalue()).hexdigest()[:16]
        with _ENGINE.begin() as conn:
            if conn.execute(text("SELECT 1 FROM uploads WHERE batch_id = :id"), {"id": batch_id}).first(): return batch_id, False
            conn.execute(text("INSERT INTO uploads VALUES (:id, :time, :sales, :cancel, :rows)"), {"id": batch_id, "time": datetime.now(timezone.utc).isoformat(), "sales": sales_upload.name, "cancel": cancel_upload.name, "rows": len(data)})
            stored = data.copy(); stored["batch_id"] = batch_id; stored["date"] = stored["date"].dt.strftime("%Y-%m-%d")
            stored.to_sql("cleaned_transactions", conn, if_exists="append", index=False)
        return batch_id, True

    def load_data():
        init_database()
        with _ENGINE.connect() as conn: data = pd.read_sql(text("SELECT * FROM cleaned_transactions"), conn)
        if not data.empty: data["date"] = pd.to_datetime(data["date"])
        return data

    def upload_summary():
        init_database()
        with _ENGINE.connect() as conn: return pd.read_sql(text("SELECT * FROM uploads ORDER BY uploaded_at DESC"), conn)

    def save_dispatch_batch(data, uploaded_file):
        init_database(); batch_id = hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:16]
        with _ENGINE.begin() as conn:
            if conn.execute(text("SELECT 1 FROM dispatch_uploads WHERE batch_id = :id"), {"id": batch_id}).first(): return batch_id, False
            conn.execute(text("INSERT INTO dispatch_uploads VALUES (:id, :time, :name, :rows)"), {"id": batch_id, "time": datetime.now(timezone.utc).isoformat(), "name": uploaded_file.name, "rows": len(data)})
            stored = data.copy(); stored["batch_id"] = batch_id; stored["transfer_date"] = stored["transfer_date"].dt.strftime("%Y-%m-%d"); stored["week_start"] = stored["week_start"].dt.strftime("%Y-%m-%d")
            stored.to_sql("cleaned_dispatch", conn, if_exists="append", index=False)
        return batch_id, True

    def load_dispatch_data():
        init_database()
        with _ENGINE.connect() as conn: data = pd.read_sql(text("SELECT * FROM cleaned_dispatch"), conn)
        if not data.empty: data["transfer_date"] = pd.to_datetime(data["transfer_date"]); data["week_start"] = pd.to_datetime(data["week_start"])
        return data






# Clean production units. Raw exported quantity stays unchanged; analysis_quantity
# is the quantity used in the dashboard and reflects the business rules.
_TIKKA_ITEMS = {"Chicken Malai Tikka", "Chicken Peri Peri Tikka", "Chicken Spicy Tikka", "Chicken Tikka", "Fish Tikka", "Soya Achari", "Soya Tikka", "Paneer Tikka"}
_KEBAB_ITEMS = {"Chicken Seekh Kebab", "Mutton Kakori Kebab", "Mutton Seekh Kebab", "Veg Haryali Kebab"}
_PLATE_PATTERN = r"Biryani|Butter Chicken|Dal Makhani|Soya Tawa Masala|Paneer Zaika|Chicken Korma|Mutton Nihari|Mutton Haleem|Mutton Korma|Chicken Tikka Masala|Mutton Seekh Masala|Mutton Kakori Masala|Shahi Tukda|Phirni"

def apply_production_measurements(data):
    result = data.copy()
    names = result["item_name"].astype(str).str.strip()
    source = result.get("source_item_name", names).astype(str)
    factor = pd.Series(1.0, index=result.index)
    unit = pd.Series("units", index=result.index, dtype="object")
    tikka = names.isin(_TIKKA_ITEMS)
    kebab = names.isin(_KEBAB_ITEMS) | names.str.contains(r"Junior.*(?:Kebab|Kakori|Seekh)", case=False, regex=True, na=False)
    junior = source.str.contains(r"\bJunior\b", case=False, na=False)
    nine_piece = source.str.contains(r"\b0?9\s*Pcs\b", case=False, regex=True, na=False)
    four_piece = source.str.contains(r"\b4\s*Pcs\b", case=False, regex=True, na=False) & ~names.eq("Butter Chicken")
    unit.loc[tikka] = "pieces"; factor.loc[tikka] = 6
    factor.loc[tikka & junior] = 3; factor.loc[tikka & nine_piece] = 9; factor.loc[tikka & four_piece] = 4
    unit.loc[kebab] = "kg"; factor.loc[kebab] = 0.180; factor.loc[kebab & junior] = 0.090
    junior_roll = source.str.contains(r"\bJunior\b.*\bRoll\b|\bJr\.?\s*Roomali", case=False, regex=True, na=False) & ~kebab
    unit.loc[junior_roll] = "pieces"
    coke_pepsi = names.str.contains(r"Coke|Pepsi", case=False, regex=True, na=False)
    water = names.str.contains(r"Water|Vedica|Bisleri", case=False, regex=True, na=False)
    beverages = names.str.contains(r"Sprite|Fanta|Limca|Thums Up|Red ?Bull|Redbull|Ice Tea|Ginger Ale|Shikanji|Aam|Drink|7UP|Mirinda|Mountain Dew", case=False, regex=True, na=False)
    plates = names.str.contains(_PLATE_PATTERN, case=False, regex=True, na=False)
    unit.loc[coke_pepsi] = "cans"; unit.loc[water | beverages] = "bottles"; unit.loc[plates] = "plates"
    calculated = pd.to_numeric(result["quantity"], errors="coerce").fillna(0).abs() * factor
    existing = pd.to_numeric(result.get("analysis_quantity", pd.Series(float("nan"), index=result.index)), errors="coerce")
    result["analysis_quantity"] = existing.abs().where(existing.notna(), calculated)
    result["unit"] = unit
    return result.drop(columns=["source_item_name"], errors="ignore")

_base_init_database = init_database
_base_clean_uploads = clean_uploads
_base_load_data = load_data

def init_database():
    _base_init_database()
    if _EXTERNAL_URL:
        with _ENGINE.begin() as conn:
            conn.execute(text("ALTER TABLE cleaned_transactions ADD COLUMN IF NOT EXISTS analysis_quantity DOUBLE PRECISION"))
    else:
        with _connect() as conn:
            try:
                conn.execute("ALTER TABLE cleaned_transactions ADD COLUMN analysis_quantity REAL")
            except sqlite3.OperationalError:
                pass

def clean_uploads(sales_upload, cancel_upload):
    return apply_production_measurements(_base_clean_uploads(sales_upload, cancel_upload))

def load_data():
    loaded = _base_load_data()
    if not loaded.empty:
        loaded["item_name"] = normalise_names(loaded["item_name"])
        loaded["handler"] = _handler(loaded)
    return apply_production_measurements(loaded)

