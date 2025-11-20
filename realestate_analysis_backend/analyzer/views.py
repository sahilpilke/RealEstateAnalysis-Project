import os
import pandas as pd
import numpy as np
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.text import slugify
from django.http import HttpResponse
from typing import Optional, Tuple, List, Dict, Any

from groq import Groq



# Helpers

def find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Return the first matching column name."""
    cols = list(df.columns)
    for cand in candidates:
        for c in cols:
            if cand.lower() in c.lower():
                return c
    return None


def pct_change(new: float, old: float) -> Optional[float]:
    """Calculate percentage change safely."""
    try:
        if old in [None, 0] or new is None:
            return None
        return (new - old) / old * 100.0
    except:
        return None


def clean_nans(obj):
    """Convert NaN/inf/numpy types into JSON-friendly values."""
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
        if pd.isna(obj) or obj in [np.inf, -np.inf]:
            return None
        return float(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if pd.isna(obj):
        return None
    return obj


def detect_areas(query: str, df: pd.DataFrame) -> Tuple[Optional[str], List[str]]:
    """Identify areas mentioned in the query."""
    q = (query or "").lower()
    area_col = None

    for col in df.columns:
        if any(k in col.lower() for k in ["area", "local", "location"]):
            area_col = col
            break

    if area_col is None:
        return None, []

    found = []
    for v in df[area_col].dropna().unique():
        if isinstance(v, str) and v.lower() in q:
            found.append(v)

    return area_col, found



# Summary generation

def improved_summary(areas, df, area_col):
    """Base summary before LLM enhancement."""
    if not areas:
        return f"No specific area detected. Dataset contains {len(df)} records."

    price_col = find_column(df, [
        "flat - weighted average rate", "weighted average rate", "avg price", "price"
    ])
    demand_col = find_column(df, [
        "total sold - igr", "total sold", "total_sales - igr"
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
        prev_year   = years[-2] if len(years) > 1 else None

        def safe_avg(col, year):
            if col is None or year is None:
                return None
            try:
                vals = subset[
                    subset[year_col].astype(str).str.strip().astype(float) == float(year)
                ][col].dropna()
                return float(vals.mean()) if not vals.empty else None
            except:
                return None

        price_latest  = safe_avg(price_col, latest_year)
        price_prev    = safe_avg(price_col, prev_year)
        demand_latest = safe_avg(demand_col, latest_year)
        demand_prev   = safe_avg(demand_col, prev_year)

        msg = f"Analysis for {area}:"
        if latest_year:
            msg += f" ({latest_year})"

        if price_latest is not None:
            msg += f" Avg flat price = {price_latest:,.2f}"
            change = pct_change(price_latest, price_prev)
            if change is not None:
                msg += f" ({'up' if change > 0 else 'down'} {abs(change):.1f}% vs {prev_year})"
            msg += "."

        if demand_latest is not None:
            msg += f" Avg total sold = {demand_latest:,.0f}"
            change2 = pct_change(demand_latest, demand_prev)
            if change2 is not None:
                msg += f" ({'up' if change2 > 0 else 'down'} {abs(change2):.1f}% vs {prev_year})"
            msg += "."

        parts.append(msg)

    return " ".join(parts)



# LLM summary enhancer (Grok)

def generate_llm_summary(areas, base_summary):
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        return base_summary

    try:
        client = Groq(api_key=api_key)

        prompt = f"""
Rewrite this real estate summary in a cleaner, more professional way.
Do NOT modify numbers or add new information.

Areas: {areas}
Original Summary:
{base_summary}
        """

        response = client.chat.completions.create(
            model="grok-2-1212",
            messages=[
                {"role": "system", "content": "Rewrite real estate analysis clearly and professionally."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=200
        )

        return response.choices[0].message["content"].strip()

    except Exception as e:
        print("GROK LLM ERROR:", e)
        return base_summary



# Main Analysis API

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
                    return Response({"error": "Dataset not found."}, status=400)
                df = pd.read_excel(excel_path, engine="openpyxl")

        except Exception as e:
            return Response({"error": f"Failed to load Excel: {str(e)}"}, status=400)

        area_col, detected_areas = detect_areas(query, df)

        base_summary = improved_summary(detected_areas, df, area_col)
        summary = generate_llm_summary(detected_areas, base_summary)

        chart_data = {}
        table_data = []

        price_col  = find_column(df, ["flat - weighted average rate", "weighted average rate"])
        demand_col = find_column(df, ["total sold - igr", "total sold"])
        year_col   = find_column(df, ["year"])

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
                            v = grp[price_col].dropna()
                            item["price"] = float(v.mean()) if not v.empty else None
                        if demand_col:
                            v2 = grp[demand_col].dropna()
                            item["demand"] = float(v2.mean()) if not v2.empty else None

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
                        v = grp[price_col].dropna()
                        item["price"] = float(v.mean()) if not v.empty else None
                    if demand_col:
                        v2 = grp[demand_col].dropna()
                        item["demand"] = float(v2.mean()) if not v.empty else None
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



# XLSX Download API

class DownloadXLSXAPIView(APIView):
    def post(self, request):
        try:
            rows = request.data.get("table_data", [])
            if not rows:
                return Response({"error": "No table data provided"}, status=400)

            df = pd.DataFrame(rows)

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
