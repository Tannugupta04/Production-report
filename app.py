import calendar
import io
from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from cleaning import (
    DatabaseConnectionError,
    clean_dispatch_upload,
    clean_uploads,
    load_data,
    load_dispatch_data,
    save_batch,
    save_dispatch_batch,
    upload_summary,
)

st.set_page_config(page_title="Weekly Itemwise Sales", page_icon="Sales", layout="wide")
WEEKDAYS = list(calendar.day_name)


@st.cache_data(show_spinner=False)
def sales_data():
    return load_data()


@st.cache_data(show_spinner=False)
def dispatch_data():
    return load_dispatch_data()


def _style_sheet(ws, title, subtitle, header_row, widths, currency_headers=(), date_headers=()):
    """Apply one restrained, company-ready format to an Excel report sheet."""
    navy, blue, white, border_colour = "17365D", "D9EAF7", "FFFFFF", "B7C9D6"
    final_column = get_column_letter(ws.max_column)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ws.max_column)
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=16, color=white)
    ws["A1"].fill = PatternFill("solid", fgColor=navy)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws["A2"] = subtitle
    ws["A2"].font = Font(italic=True, color="555555")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ws.max_column)
    thin = Side(style="thin", color=border_colour)
    headers = {cell.value: cell.column for cell in ws[header_row]}
    for cell in ws[header_row]:
        cell.font = Font(bold=True, color=navy)
        cell.fill = PatternFill("solid", fgColor=blue)
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row):
        for cell in row:
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            cell.alignment = Alignment(vertical="top")
    for name in currency_headers:
        if name in headers:
            for cell in ws.iter_cols(min_col=headers[name], max_col=headers[name], min_row=header_row + 1, max_row=ws.max_row):
                for value in cell:
                    value.number_format = '₹#,##0.00'
    for name in date_headers:
        if name in headers:
            for cell in ws.iter_cols(min_col=headers[name], max_col=headers[name], min_row=header_row + 1, max_row=ws.max_row):
                for value in cell:
                    value.number_format = "dd-mmm-yyyy"
    for column, width in widths.items():
        ws.column_dimensions[get_column_letter(column)].width = width
    ws.freeze_panes = f"A{header_row + 1}"
    ws.auto_filter.ref = f"A{header_row}:{final_column}{ws.max_row}"


def download_pattern(pattern, adjustment_percent=10):
    report = pattern.copy()
    for day in WEEKDAYS:
        if day in report:
            report[day] = np.ceil(pd.to_numeric(report[day], errors="coerce") * (1 + adjustment_percent / 100))
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        report.to_excel(writer, sheet_name="Mon-Sun Pattern", index=False, startrow=3)
        _style_sheet(
            writer.sheets["Mon-Sun Pattern"],
            "Monday-Sunday Production Pattern",
            f"Includes {adjustment_percent}% production increase",
            4,
            {1: 34, **{column: 15 for column in range(2, len(report.columns) + 1)}},
        )
        for row in writer.sheets["Mon-Sun Pattern"].iter_rows(min_row=5):
            for cell in row[1:]:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "#,##0"
    return out.getvalue()


def item_summary(data, day_count):
    grouped = data.groupby(["item_name", "unit"], as_index=False).agg(
        total_quantity=("analysis_quantity", "sum"),
        total_sales=("display_sales", "sum"),
    )
    grouped["Average Quantity per Business Day"] = grouped["total_quantity"] / day_count
    grouped["Average Sales per Business Day (INR)"] = grouped["total_sales"] / day_count
    return grouped.rename(columns={
        "item_name": "Item",
        "unit": "Unit",
        "total_quantity": "Total Quantity",
        "total_sales": "Total Sales (INR)",
    }).sort_values(["Average Sales per Business Day (INR)", "Item"], ascending=[False, True])


def weekday_summary(data, scope):
    date_days = scope[["date", "weekday"]].drop_duplicates()
    reports = []
    for day in WEEKDAYS:
        occurrences = date_days.loc[date_days["weekday"].eq(day), "date"].nunique()
        if not occurrences:
            continue
        daily = data.loc[data["weekday"].eq(day)]
        report = daily.groupby(["item_name", "unit"], as_index=False).agg(
            total_quantity=("analysis_quantity", "sum"),
            total_sales=("display_sales", "sum"),
        )
        report["Weekday"] = day
        report["Weekday Occurrences"] = occurrences
        report["Average Quantity per Weekday"] = report["total_quantity"] / occurrences
        report["Average Sales per Weekday (INR)"] = report["total_sales"] / occurrences
        reports.append(report.rename(columns={
            "item_name": "Item", "unit": "Unit", "total_quantity": "Total Quantity", "total_sales": "Total Sales (INR)",
        }))
    return pd.concat(reports, ignore_index=True) if reports else pd.DataFrame()


def download_sales_report(filtered, scope, start, end, statuses):
    day_count = scope["date"].dt.date.nunique()
    summary = item_summary(filtered, day_count)
    weekday = weekday_summary(filtered, scope)
    details = filtered[["date", "weekday", "item_name", "unit", "analysis_quantity", "display_sales", "outlet", "order_source", "status", "handler", "invoice"]].copy()
    details = details.rename(columns={
        "date": "Business Date", "weekday": "Weekday", "item_name": "Item", "unit": "Unit",
        "analysis_quantity": "Quantity", "display_sales": "Sales (INR)", "outlet": "Outlet",
        "order_source": "Order Source", "status": "Status", "handler": "Handled By", "invoice": "Invoice",
    }).sort_values(["Business Date", "Item"])
    subtitle = f"Period: {start:%d-%b-%Y} to {end:%d-%b-%Y} | Business dates used for daily averages: {day_count} | Status: {', '.join(statuses)}"
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Item summary", index=False, startrow=3)
        _style_sheet(writer.sheets["Item summary"], "Sales and Quantity Summary", subtitle, 4, {1: 34, 2: 14, 3: 18, 4: 22, 5: 18, 6: 27}, {"Total Sales (INR)", "Average Sales per Business Day (INR)"})
        weekday.to_excel(writer, sheet_name="Weekday averages", index=False, startrow=3)
        _style_sheet(writer.sheets["Weekday averages"], "Weekday Item Averages", "Each weekday average divides by the number of matching business dates in the selected period.", 4, {1: 14, 2: 34, 3: 14, 4: 20, 5: 18, 6: 18, 7: 27, 8: 27}, {"Total Sales (INR)", "Average Sales per Weekday (INR)"})
        details.to_excel(writer, sheet_name="Filtered transactions", index=False, startrow=3)
        _style_sheet(writer.sheets["Filtered transactions"], "Filtered Cleaned Transactions", subtitle, 4, {1: 16, 2: 13, 3: 34, 4: 14, 5: 14, 6: 16, 7: 13, 8: 16, 9: 13, 10: 18, 11: 16}, {"Sales (INR)"}, {"Business Date"})
    return out.getvalue()


def sales_page():
    st.title("Weekly Itemwise Sales Dashboard")
    st.caption("Quantity uses cleaned business units. Daily and weekday averages include zero-sale dates in the selected period.")
    with st.sidebar:
        st.header("Sales / cancel upload")
        sales_file = st.file_uploader("Sales file", type=["csv", "xlsx", "xls"], key="sales")
        cancel_file = st.file_uploader("Cancel file", type=["csv", "xlsx", "xls"], key="cancel")
        if st.button("Clean and save sales data", type="primary", disabled=not (sales_file and cancel_file)):
            try:
                with st.spinner("Cleaning, standardising item names and saving..."):
                    cleaned = clean_uploads(sales_file, cancel_file)
                    batch_id, saved = save_batch(cleaned, sales_file, cancel_file)
                st.cache_data.clear()
                st.success(f"{'Saved' if saved else 'Already saved'} {len(cleaned):,} cleaned records ({batch_id}).")
            except Exception as error:
                st.error(str(error))

    data = sales_data()
    if data.empty:
        st.info("Upload one Sales file and one Cancel file to start.")
        return
    data["unit"] = data.get("unit", "units").fillna("units").replace("", "units")
    with st.sidebar:
        st.divider()
        st.header("Current dashboard filters")
        lo, hi = data.date.min().date(), data.date.max().date()
        mode = st.radio("Period", ["Custom dates", "A month", "Latest 7 days", "Previous 7 days"], key="period")
        if mode == "A month":
            months = sorted(data.month.dropna().unique(), key=pd.to_datetime)
            choice = st.selectbox("Month", months)
            month_dates = data.loc[data.month.eq(choice), "date"]
            start, end = month_dates.min().date(), month_dates.max().date()
        elif mode == "Latest 7 days":
            start, end = max(lo, hi - timedelta(days=6)), hi
        elif mode == "Previous 7 days":
            end = hi - timedelta(days=7)
            start = max(lo, end - timedelta(days=6))
        else:
            start, end = st.date_input("Date range", value=(lo, hi), min_value=lo, max_value=hi)
        outlets = st.multiselect("Outlet", sorted(data.outlet.dropna().unique()))
        sources = st.multiselect("Order source", sorted(data.order_source.dropna().unique()))
        statuses = st.multiselect("Status", ["Completed", "Cancelled"], default=["Completed"], help="Completed is selected by default. Cancellation rows are shown as positive cancellation values when selected.")
        st.divider()
        st.header("Person segregation")
        handlers = st.multiselect("Handled by", sorted(data.handler.dropna().unique()))

    scope = data[(data.date.dt.date >= start) & (data.date.dt.date <= end)].copy()
    if outlets:
        scope = scope[scope.outlet.isin(outlets)]
    if sources:
        scope = scope[scope.order_source.isin(sources)]
    filtered = scope[scope.status.isin(statuses)].copy()
    if handlers:
        filtered = filtered[filtered.handler.isin(handlers)]
    if filtered.empty:
        st.warning("No data matches these filters.")
        return

    filtered["display_sales"] = pd.to_numeric(filtered["net_sales"], errors="coerce").fillna(0).abs()
    filtered["analysis_quantity"] = pd.to_numeric(filtered["analysis_quantity"], errors="coerce").fillna(0).abs()
    day_count = scope["date"].dt.date.nunique()
    selected = st.radio("Measure", ["Quantity", "Sales (INR)"], horizontal=True)
    metric = "analysis_quantity" if selected == "Quantity" else "display_sales"
    metric_label = "Quantity" if selected == "Quantity" else "Sales (INR)"

    ranking = filtered.groupby("item_name", as_index=False)[metric].sum().sort_values(metric, ascending=False)
    item_options = sorted(filtered["item_name"].dropna().unique())
    default_item = ranking.iloc[0]["item_name"] if not ranking.empty else item_options[0]
    selected_item = st.selectbox("Item for daily trend", item_options, index=item_options.index(default_item))
    selected_data = filtered[filtered.item_name.eq(selected_item)].copy()
    selected_unit = selected_data["unit"].mode().iat[0]
    selected_total = selected_data[metric].sum()
    selected_average = selected_total / day_count

    a, b, c, d = st.columns(4)
    a.metric(f"{selected_item} total {metric_label}", f"{selected_total:,.2f}")
    b.metric(f"Average per business day ({selected_unit if selected == 'Quantity' else 'INR'})", f"{selected_average:,.2f}")
    c.metric("Business dates included", f"{day_count:,}")
    d.metric("Selected item unit", selected_unit)

    st.subheader("Item-specific daily trend")
    st.caption(f"The line below is only for {selected_item}. It does not combine different items or units.")
    daily_item = selected_data.groupby("date", as_index=False)[metric].sum()
    comparison_units = sorted(filtered["unit"].dropna().unique())
    compare_unit = st.selectbox("Unit for item comparison", comparison_units, index=comparison_units.index(selected_unit) if selected_unit in comparison_units else 0)
    comparison = filtered[filtered.unit.eq(compare_unit)].groupby(["item_name", "unit"], as_index=False)[metric].sum()
    comparison["Average per Business Day"] = comparison[metric] / day_count
    comparison = comparison.sort_values("Average per Business Day", ascending=False).head(25)
    left, right = st.columns(2)
    y_label = f"{metric_label} ({selected_unit})" if selected == "Quantity" else metric_label
    with left:
        st.plotly_chart(px.line(daily_item, x="date", y=metric, markers=True, title=f"Daily {metric_label}: {selected_item} ({selected_unit})", labels={metric: y_label, "date": "Business date"}), use_container_width=True)
    with right:
        st.plotly_chart(px.bar(comparison.sort_values("Average per Business Day"), x="Average per Business Day", y="item_name", orientation="h", title=f"Top 25 items: daily average ({compare_unit})", labels={"item_name": "Item", "Average per Business Day": f"Average {metric_label} per business day"}), use_container_width=True)

    st.subheader("All items: totals and averages")
    st.caption("Quantities are kept separate by unit. The table is the single place to review total quantity, total sales, and the correct per-business-day averages.")
    summary = item_summary(filtered, day_count)
    st.dataframe(summary.round(2), hide_index=True, use_container_width=True)

    st.subheader("Item-wise weekday average")
    st.caption("For example, a Sunday average divides the total by every Sunday business date in the selected period, including Sundays with no sale for an item.")
    weekday_dates = scope[["date", "weekday"]].drop_duplicates()
    for day, tab in zip(WEEKDAYS, st.tabs(WEEKDAYS)):
        with tab:
            occurrences = weekday_dates.loc[weekday_dates.weekday.eq(day), "date"].nunique()
            weekday_data = filtered[filtered.weekday.eq(day)]
            if not occurrences:
                st.info(f"No {day} business dates are in these filters.")
                continue
            report = weekday_data.groupby(["item_name", "unit"], as_index=False)[metric].sum()
            average_label = f"Average {metric_label} per {day}"
            report[average_label] = report[metric] / occurrences
            report = report.sort_values(average_label, ascending=False)
            st.caption(f"Calculated across {occurrences} {day}{'' if occurrences == 1 else 's'}.")
            st.plotly_chart(px.bar(report.head(35), x="item_name", y=average_label, color="unit", title=f"{day}: average {metric_label} by item", labels={"item_name": "Item", "unit": "Unit"}).update_xaxes(tickangle=-45), use_container_width=True)
            st.dataframe(report.rename(columns={"item_name": "Item", "unit": "Unit", metric: f"Total {metric_label}"}).round(2), hide_index=True, use_container_width=True)

    with st.expander("Stored data and download"):
        st.dataframe(upload_summary(), hide_index=True, use_container_width=True)
        report_bytes = download_sales_report(filtered, scope, start, end, statuses)
        st.download_button("Download formatted sales analysis (Excel)", report_bytes, "sales_analysis.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def production_page():
    st.title("Dispatch & Production Planning")
    st.caption("Upload dispatch data to calculate weekday demand and recommended production from the 75th-percentile weekly requirement.")
    with st.sidebar:
        st.header("Dispatch upload")
        upload = st.file_uploader("Dispatch file", type=["csv", "xlsx", "xls"], key="dispatch")
        if st.button("Clean and save dispatch data", type="primary", disabled=not upload):
            try:
                cleaned = clean_dispatch_upload(upload)
                batch_id, saved = save_dispatch_batch(cleaned, upload)
                st.cache_data.clear()
                st.success(f"{'Saved' if saved else 'Already saved'} {len(cleaned):,} dispatch rows ({batch_id}).")
            except Exception as error:
                st.error(str(error))
    data = dispatch_data()
    if data.empty:
        st.info("Upload a dispatch file with Item Name, Quantity Delivered and Transfer Date.")
        return
    with st.sidebar:
        st.divider()
        st.caption("The downloaded Monday-Sunday pattern includes a fixed 10% production increase.")
        chosen = st.multiselect("Production item", sorted(data.item_name.unique()))
    if chosen:
        data = data[data.item_name.isin(chosen)]
    daily = data.groupby(["transfer_date", "item_name", "weekday"], as_index=False).quantity_delivered.sum()
    weekly = daily.assign(week_start=daily.transfer_date - pd.to_timedelta(daily.transfer_date.dt.dayofweek, unit="D")).groupby(["week_start", "item_name"], as_index=False).quantity_delivered.sum().rename(columns={"quantity_delivered": "Weekly Quantity"})
    benchmark = weekly.groupby("item_name")["Weekly Quantity"].agg(Average_Weekly="mean", Median_Weekly="median", P75_Weekly=lambda values: values.quantile(.75), P90_Weekly=lambda values: values.quantile(.90), Min_Weekly="min", Max_Weekly="max").reset_index()
    benchmark["Recommended Weekly Production"] = np.ceil(benchmark.P75_Weekly * 1.10).astype(int)
    day_benchmark = daily.groupby(["item_name", "weekday"])["quantity_delivered"].agg(Average="mean", Median="median", P75=lambda values: values.quantile(.75), P90=lambda values: values.quantile(.90)).reset_index()
    day_benchmark.weekday = pd.Categorical(day_benchmark.weekday, categories=WEEKDAYS, ordered=True)
    day_benchmark = day_benchmark.sort_values(["item_name", "weekday"])
    matrix = day_benchmark.pivot(index="item_name", columns="weekday", values="Median").reindex(columns=WEEKDAYS).reset_index()
    st.subheader("Recommended weekly production")
    st.dataframe(benchmark.round(0), hide_index=True, use_container_width=True)
    for day, tab in zip(WEEKDAYS, st.tabs(WEEKDAYS)):
        with tab:
            view = day_benchmark[day_benchmark.weekday.eq(day)].sort_values("P75", ascending=False)
            st.plotly_chart(px.bar(view, x="item_name", y="P75", title=f"{day} production benchmark (P75)").update_xaxes(tickangle=-45), use_container_width=True)
            st.dataframe(view.round(2), hide_index=True, use_container_width=True)
    st.download_button("Download Monday-Sunday pattern (+10%)", download_pattern(matrix, 10), "monday_sunday_production_pattern_plus_10.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


page = st.sidebar.radio("Page", ["Sales dashboard", "Dispatch & production"])
try:
    if page == "Sales dashboard":
        sales_page()
    else:
        production_page()
except DatabaseConnectionError as error:
    st.error(str(error))
    st.info("Your existing local data remains safe. Correct the Streamlit DATABASE_URL Secret, save it, and reboot the app.")