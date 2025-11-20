import os
import pandas as pd
import numpy as np
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.text import slugify
from django.http import HttpResponse
from typing import Optional, Tuple, List, Dict, Any

# ---------------------------
# NEW: Grok (xAI)
# ---------------------------
from groq import Groq


# ---------------------------
# Utility helpers
# ---------------------------
def find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = list(df.columns)
    for cand in candidates:
        for c in cols:
            if cand.lower() in c.lower():
                return c
    return None


def pct_change(new: float, old: float) -> Optional[float]:
    try:
        if old in [None, 0] or new is None:
            return None
        return (new - old) / old * 100.0
    except:
        return None


def clean_nans(obj):
    if isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_nans(v) for v in obj]
    if isinstance(obj, (pd.Series, pd.Index, np.ndarray)):
        try:
            return [clean_nans(v) for v in list(obj)]
        except:
            return None
    if isinstance(obj, pd.Timestamp):
        try:
            return obj.isoformat()
        except:
            return str(obj)
    if isinstance(obj, (np.floating, float)):
        if pd.isna(obj) or obj == np.inf or obj == -np.inf:
            return None
        return float(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if pd.isna(obj):
        return None
    return obj


# ---------------------------
# Detect areas
# ---------------------------
def detect_areas(query: str, df: pd.DataFrame) -> Tuple[Optional[str], List[str]]:
    q = (query or "").lower()
    area_col = None

    for col in df.columns:
        if ("area" in col.lower()) or ("local" in col.lower()) or ("location" in col.lower()):
            area_col = col
            break

    if area_col is None:
        return None, []

    found = []
    for v in df[area_col].dropna().unique():
        if isinstance(v, str) and v.lower() in q:
            found.append(v)

    return area_col, found


# ---------------------------
# Improved summary (existing logic)
# ---------------------------
def improved_summary(areas, df, area_col):
    if not areas:
        return f"No specific area detected. Dataset contains {len(df)} records."

    price_col = find_column(df, [
        "flat - weighted average rate",
        "weighted average rate",
        "avg price",
        "price"
    ])
    demand_col = find_column(df, [
        "total sold - igr",
        "total sold",
        "total_sales - igr"
    ])
    year_col = find_column(df, ["year"])

    parts = []

    for area in areas:
        subset = df[df[area_col].astype(str).str.lower() == area.lower()]

        if subset.empty:
            parts.append(f"No data found for {area}.")
            continue

        try:
            years = (
                subset[year_col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .apply(lambda x: int(float(x)))
                    .sort_values()
                    .tolist()
            )
        except:
            years = []

        latest_year = years[-1] if years else None
        prev_year = years[-2] if len(years) > 1 else None

        def safe_avg(col, year):
            if col is None or year is None:
                return None
            try:
                vals = subset[subset[year_col].astype(str).str.strip().astype(float) == float(year)][col].dropna()
                if not vals.empty:
                    return float(vals.mean())
                return None
            except:
                return None

        price_latest = safe_avg(price_col, latest_year)
        price_prev = safe_avg(price_col, prev_year)

        demand_latest = safe_avg(demand_col, latest_year)
        demand_prev = safe_avg(demand_col, prev_year)

        msg = f"Analysis for {area}:"
        if latest_year:
            msg += f" ({latest_year})"

        if price_latest is not None:
            msg += f" Avg flat price = {price_latest:,.2f}"
            change = pct_change(price_latest, price_prev)
            if change is not None:
                direction = "up" if change > 0 else "down"
                msg += f" ({direction} {abs(change):.1f}% vs {prev_year})"
            msg += "."

        if demand_latest is not None:
            msg += f" Avg total sold = {demand_latest:,.0f}"
            change2 = pct_change(demand_latest, demand_prev)
            if change2 is not None:
                direction2 = "up" if change2 > 0 else "down"
                msg += f" ({direction2} {abs(change2):.1f}% vs {prev_year})"
            msg += "."

        parts.append(msg)

    return " ".join(parts)


# ---------------------------
# NEW — Grok Summary Enhancer
# ---------------------------
def generate_llm_summary(areas, base_summary):
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        return base_summary

    try:
        client = Groq(api_key=api_key)

        prompt = f"""
Rewrite this real estate summary in a cleaner, more professional way.
Do NOT modify the numbers or add new data.

Areas: {areas}
Original Summary:
{base_summary}
        """

        response = client.chat.completions.create(
            model="grok-2-1212",
            messages=[
                {"role": "system", "content": "You rewrite real estate analysis summaries clearly and professionally."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=200
        )

        return response.choices[0].message["content"].strip()

    except Exception as e:
        print("GROK LLM ERROR:", e)
        return base_summary


# ---------------------------
# Main API — with NaN cleaning + GPT summary
# ---------------------------
class AnalyzeAPIView(APIView):

    def post(self, request):
        query = request.data.get("query", "")
        uploaded_file = request.FILES.get("file")

        try:
            if uploaded_file:
                filename = slugify(uploaded_file.name)
                filepath = os.path.join(settings.MEDIA_ROOT, filename)
                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

                with default_storage.open(filepath, "wb+") as dest:
                    for chunk in uploaded_file.chunks():
                        dest.write(chunk)

                df = pd.read_excel(filepath, engine="openpyxl")

            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                excel_path = os.path.join(base_dir, "data", "sample_realestate.xlsx")

                if not os.path.exists(excel_path):
                    return Response({"error": "Dataset not found. Please upload an Excel file."}, status=400)

                df = pd.read_excel(excel_path, engine="openpyxl")

        except Exception as e:
            return Response({"error": f"Failed to load Excel: {str(e)}"}, status=400)

        area_col, detected_areas = detect_areas(query, df)

        base_summary = improved_summary(detected_areas, df, area_col)
        summary = generate_llm_summary(detected_areas, base_summary)

        chart_data: Dict[str, List[Dict[str, Any]]] = {}
        table_data = []

        price_col = find_column(df, ["flat - weighted average rate", "weighted average rate"])
        demand_col = find_column(df, ["total sold - igr", "total sold"])
        year_col = find_column(df, ["year"])

        if detected_areas:
            for area in detected_areas:
                subset = df[df[area_col].astype(str).str.lower() == area.lower()]

                rows = []

                if year_col:
                    grouped = subset.groupby(year_col)
                    for y, grp in grouped:
                        try:
                            y_clean = int(float(str(y).strip()))
                        except:
                            continue

                        item = {"year": y_clean}

                        if price_col:
                            vals = grp[price_col].dropna()
                            item["price"] = float(vals.mean()) if not vals.empty else None

                        if demand_col:
                            vals2 = grp[demand_col].dropna()
                            item["demand"] = float(vals2.mean()) if not vals.empty else None

                        rows.append(item)

                    rows = sorted(rows, key=lambda x: x["year"])

                chart_data[area] = rows
                table_data.extend(subset.to_dict(orient="records"))

        else:
            rows = []
            if year_col:
                grouped = df.groupby(year_col)
                for y, grp in grouped:
                    try:
                        y_clean = int(float(str(y).strip()))
                    except:
                        continue

                    item = {"year": y_clean}

                    if price_col:
                        vals = grp[price_col].dropna()
                        item["price"] = float(vals.mean()) if not vals.empty else None

                    if demand_col:
                        vals2 = grp[demand_col].dropna()
                        item["demand"] = float(vals2.mean()) if not vals.empty else None

                    rows.append(item)

                rows = sorted(rows, key=lambda x: x["year"])
                chart_data["dataset"] = rows

            table_data = df.to_dict(orient="records")

        cleaned = {
            "summary": summary,
            "chart_data": clean_nans(chart_data),
            "table_data": clean_nans(table_data[:200])
        }

        return Response(cleaned, status=200)


# ---------------------------------------------------
# ⭐ NEW XLSX DOWNLOAD API (Bonus Feature)
# ---------------------------------------------------
class DownloadXLSXAPIView(APIView):

    def post(self, request):
        """
        Expects JSON:
        {
            "table_data": [ { row1 }, { row2 }, ... ]
        }
        Returns an XLSX file.
        """
        try:
            rows = request.data.get("table_data", [])
            if not rows:
                return Response({"error": "No table data provided"}, status=400)

            df = pd.DataFrame(rows)

            # Create Excel file in memory
            from io import BytesIO
            buffer = BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)

            response = HttpResponse(
                buffer,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="filtered_data.xlsx"'

            return response

        except Exception as e:
            return Response({"error": str(e)}, status=500)

