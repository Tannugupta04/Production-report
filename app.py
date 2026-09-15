import calendar, io
from datetime import timedelta
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from cleaning import clean_uploads, load_data, save_batch, upload_summary, clean_dispatch_upload, save_dispatch_batch, load_dispatch_data

st.set_page_config(page_title="Weekly Itemwise Sales", page_icon="Sales", layout="wide")
WEEKDAYS=list(calendar.day_name)

@st.cache_data(show_spinner=False)
def sales_data(): return load_data()
@st.cache_data(show_spinner=False)
def dispatch_data(): return load_dispatch_data()

def download_pattern(pattern, adjustment_percent=10):
    report = pattern.copy()
    for day in WEEKDAYS:
        if day in report:
            report[day] = np.ceil(pd.to_numeric(report[day], errors="coerce") * (1 + adjustment_percent / 100))
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        report.to_excel(writer, sheet_name="Mon-Sun Pattern", index=False, startrow=3)
        ws = writer.sheets["Mon-Sun Pattern"]
        ws["A1"] = "Monday-Sunday Production Pattern"
        ws["A2"] = f"Includes {adjustment_percent}% production increase"
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(report.columns))
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        navy, blue, white = "17365D", "D9EAF7", "FFFFFF"
        ws["A1"].font = Font(bold=True, size=16, color=white)
        ws["A1"].fill = PatternFill("solid", fgColor=navy)
        ws["A1"].alignment = Alignment(horizontal="center")
        ws["A2"].font = Font(italic=True, color="555555")
        header_row = 4
        thin = Side(style="thin", color="B7C9D6")
        for cell in ws[header_row]:
            cell.font = Font(bold=True, color=navy)
            cell.fill = PatternFill("solid", fgColor=blue)
            cell.alignment = Alignment(horizontal="center")
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row):
            for cell in row:
                cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
                if isinstance(cell.value, float) and pd.isna(cell.value):
                    cell.value = None
                elif isinstance(cell.value, (int, float)):
                    cell.number_format = "0"
        ws.freeze_panes = "B5"
        ws.auto_filter.ref = f"A4:{chr(64 + len(report.columns))}{ws.max_row}"
        ws.column_dimensions["A"].width = 34
        for column in range(2, len(report.columns) + 1):
            ws.column_dimensions[chr(64 + column)].width = 15
    return out.getvalue()
def sales_page():
    st.title("Weekly Itemwise Sales Dashboard")
    with st.sidebar:
        st.header("Sales / cancel upload")
        sf=st.file_uploader("Sales file",type=["csv","xlsx","xls"],key="sales")
        cf=st.file_uploader("Cancel file",type=["csv","xlsx","xls"],key="cancel")
        if st.button("Clean and save sales data",type="primary",disabled=not(sf and cf)):
            try:
                with st.spinner("Cleaning, standardising item names and saving..."):
                    data=clean_uploads(sf,cf); bid,saved=save_batch(data,sf,cf)
                st.cache_data.clear(); st.success(f"{'Saved' if saved else 'Already saved'} {len(data):,} cleaned records ({bid}).")
            except Exception as e: st.error(str(e))
    data=sales_data()
    if data.empty:
        st.info("Upload one Sales file and one Cancel file to start."); return
    with st.sidebar:
        st.divider(); st.header("Current dashboard filters")
        lo,hi=data.date.min().date(),data.date.max().date(); mode=st.radio("Period",["Custom dates","A month","Latest week","Previous week"],key="period")
        if mode=="A month":
            months=sorted(data.month.dropna().unique(),key=pd.to_datetime); choice=st.selectbox("Month",months); ds=data.loc[data.month.eq(choice),"date"]; start,end=ds.min().date(),ds.max().date()
        elif mode in ("Latest week","Previous week"):
            start=hi-timedelta(days=hi.weekday()+(7 if mode=="Previous week" else 0)); end=start+timedelta(days=6)
        else: start,end=st.date_input("Date range",value=(lo,hi),min_value=lo,max_value=hi)
        outlets=st.multiselect("Outlet",sorted(data.outlet.dropna().unique())); sources=st.multiselect("Order source",sorted(data.order_source.dropna().unique())); statuses=st.multiselect("Status",["Completed","Cancelled"],default=["Completed","Cancelled"])
        st.divider(); st.header("Person segregation")
        handlers=st.multiselect("Handled by",sorted(data.handler.dropna().unique()),help="Sudama, drinks, kitchen and unassigned items are separated here.")
    f=data[(data.date.dt.date>=start)&(data.date.dt.date<=end)&data.status.isin(statuses)].copy()
    if outlets: f=f[f.outlet.isin(outlets)]
    if sources: f=f[f.order_source.isin(sources)]
    if handlers: f=f[f.handler.isin(handlers)]
    selected=st.radio("Measure",["Quantity","Sales (INR)"],horizontal=True); metric,title=("quantity_impact","Quantity") if selected=="Quantity" else ("sales_impact","Realised sales (INR)")
    a,b,c,d=st.columns(4); a.metric(f"Net {title}",f"{f[metric].sum():,.2f}"); b.metric(f"Completed {title}",f"{f.loc[f.status.eq('Completed'),metric].sum():,.2f}"); c.metric("Cancellation impact",f"{f.loc[f.status.eq('Cancelled'),metric].sum():,.2f}"); d.metric("Records",f"{len(f):,}")
    st.subheader("Overall analysis")
    x,y=st.columns(2); daily=f.groupby("date",as_index=False)[metric].sum(); top=f.groupby("item_name",as_index=False)[metric].sum().sort_values(metric,ascending=False).head(25)
    with x: st.plotly_chart(px.line(daily,x="date",y=metric,markers=True,title="Daily trend",labels={metric:title}),use_container_width=True)
    with y: st.plotly_chart(px.bar(top.sort_values(metric),x=metric,y="item_name",orientation="h",title="Top 25 items",labels={metric:title}),use_container_width=True)
    st.subheader("Item-wise weekday seasonality"); st.caption("Each tab combines all occurrences of that weekday in the selected date range.")
    for day,tab in zip(WEEKDAYS,st.tabs(WEEKDAYS)):
        with tab:
            v=f[f.weekday.eq(day)].groupby("item_name",as_index=False)[metric].sum().sort_values(metric,ascending=False)
            if v.empty: st.info(f"No {day} data for these filters.")
            else:
                st.plotly_chart(px.bar(v.head(35),x="item_name",y=metric,title=f"{day}: {title} by item",labels={metric:title,"item_name":"Item"}).update_xaxes(tickangle=-45),use_container_width=True)
                st.dataframe(v.rename(columns={"item_name":"Item",metric:title}),hide_index=True,use_container_width=True)
    with st.expander("Stored data and download"):
        st.dataframe(upload_summary(),hide_index=True,use_container_width=True); st.download_button("Download filtered cleaned sales CSV",f.to_csv(index=False).encode(),"filtered_cleaned_sales.csv","text/csv")

def production_page():
    st.title("Dispatch & Production Planning")
    st.caption("Upload dispatch data to calculate weekday demand and recommended production from the 75th-percentile weekly requirement.")
    with st.sidebar:
        st.header("Dispatch upload")
        upload=st.file_uploader("Dispatch file",type=["csv","xlsx","xls"],key="dispatch")
        if st.button("Clean and save dispatch data",type="primary",disabled=not upload):
            try:
                clean=clean_dispatch_upload(upload); bid,saved=save_dispatch_batch(clean,upload); st.cache_data.clear(); st.success(f"{'Saved' if saved else 'Already saved'} {len(clean):,} dispatch rows ({bid}).")
            except Exception as e: st.error(str(e))
    data=dispatch_data()
    if data.empty: st.info("Upload a dispatch file with Item Name, Quantity Delivered and Transfer Date."); return
    with st.sidebar:
        st.divider(); st.caption("The downloaded Monday-Sunday pattern includes a fixed 10% production increase.")
        chosen=st.multiselect("Production item",sorted(data.item_name.unique()))
    if chosen: data=data[data.item_name.isin(chosen)]
    daily=data.groupby(["transfer_date","item_name","weekday"],as_index=False).quantity_delivered.sum()
    weekly=daily.assign(week_start=daily.transfer_date-pd.to_timedelta(daily.transfer_date.dt.dayofweek,unit="D")).groupby(["week_start","item_name"],as_index=False).quantity_delivered.sum().rename(columns={"quantity_delivered":"Weekly Quantity"})
    benchmark=weekly.groupby("item_name")["Weekly Quantity"].agg(Average_Weekly="mean",Median_Weekly="median",P75_Weekly=lambda x:x.quantile(.75),P90_Weekly=lambda x:x.quantile(.90),Min_Weekly="min",Max_Weekly="max").reset_index()
    benchmark["Recommended Weekly Production"]=np.ceil(benchmark.P75_Weekly*1.10).astype(int)
    day_benchmark=daily.groupby(["item_name","weekday"])["quantity_delivered"].agg(Average="mean",Median="median",P75=lambda x:x.quantile(.75),P90=lambda x:x.quantile(.90)).reset_index(); day_benchmark.weekday=pd.Categorical(day_benchmark.weekday,categories=WEEKDAYS,ordered=True); day_benchmark=day_benchmark.sort_values(["item_name","weekday"]); matrix=day_benchmark.pivot(index="item_name",columns="weekday",values="Median").reindex(columns=WEEKDAYS).reset_index()
    st.subheader("Recommended weekly production")
    st.dataframe(benchmark.round(0),hide_index=True,use_container_width=True)
    tabs=st.tabs(WEEKDAYS)
    for day,tab in zip(WEEKDAYS,tabs):
        with tab:
            view=day_benchmark[day_benchmark.weekday.eq(day)].sort_values("P75",ascending=False)
            st.plotly_chart(px.bar(view,x="item_name",y="P75",title=f"{day} production benchmark (P75)").update_xaxes(tickangle=-45),use_container_width=True)
            st.dataframe(view.round(2),hide_index=True,use_container_width=True)
    output=download_pattern(matrix, 10)
    st.download_button("Download Monday-Sunday pattern (+10%)",output,"monday_sunday_production_pattern_plus_10.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

page=st.sidebar.radio("Page",["Sales dashboard","Dispatch & production"])
if page=="Sales dashboard": sales_page()
else: production_page()



