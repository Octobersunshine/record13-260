import io
import json

from flask import Flask, request, jsonify
import pandas as pd

app = Flask(__name__)

ALLOWED_AGGFUNCS = {"sum", "mean", "count"}


def _parse_aggfunc(aggfunc_str: str, values_list: list) -> dict:
    if not aggfunc_str:
        return {v: "sum" for v in values_list}

    stripped = aggfunc_str.strip()
    if stripped.startswith("{"):
        try:
            aggfunc_dict = json.loads(stripped)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid aggfunc JSON: {e}")

        if not isinstance(aggfunc_dict, dict):
            raise ValueError("aggfunc JSON must be an object")

        result = {}
        for col, funcs in aggfunc_dict.items():
            if col not in values_list:
                raise ValueError(f"aggfunc key '{col}' is not in values")
            if isinstance(funcs, str):
                func_list = [funcs]
            elif isinstance(funcs, list):
                func_list = funcs
            else:
                raise ValueError(f"aggfunc value for '{col}' must be string or array")

            for f in func_list:
                if f not in ALLOWED_AGGFUNCS:
                    raise ValueError(
                        f"Invalid aggfunc '{f}' for '{col}'. "
                        f"Allowed: {', '.join(sorted(ALLOWED_AGGFUNCS))}"
                    )

            result[col] = func_list[0] if len(func_list) == 1 else func_list

        for v in values_list:
            if v not in result:
                result[v] = "sum"

        return result

    func_list = [a.strip() for a in aggfunc_str.split(",") if a.strip()]
    for f in func_list:
        if f not in ALLOWED_AGGFUNCS:
            raise ValueError(
                f"Invalid aggfunc '{f}'. Allowed: {', '.join(sorted(ALLOWED_AGGFUNCS))}"
            )

    effective_funcs = func_list[0] if len(func_list) == 1 else func_list
    return {v: effective_funcs for v in values_list}


def _flatten_columns(columns) -> list:
    if not isinstance(columns, pd.MultiIndex):
        return [str(c) if c is not None else "" for c in columns]

    flattened = []
    for col_tuple in columns:
        parts = []
        for level_value in col_tuple:
            if level_value is None or (isinstance(level_value, float) and pd.isna(level_value)):
                continue
            s = str(level_value)
            if s == "" or s.lower() == "nan":
                continue
            parts.append(s)
        flattened.append("_".join(parts) if parts else "_".join(str(c) for c in col_tuple if c is not None))
    return flattened


def _json_value(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    if isinstance(v, (pd.Timedelta,)):
        return v.total_seconds()
    if isinstance(v, (pd.Period,)):
        return str(v)
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    try:
        import numpy as np
        if isinstance(v, np.ndarray):
            if v.ndim == 0:
                return _json_value(v.item())
            return [_json_value(x) for x in v.tolist()]
    except Exception:
        pass
    return v


def pivot_table_to_json(df: pd.DataFrame) -> str:
    work_df = df.reset_index()

    flat_columns = _flatten_columns(work_df.columns)
    work_df.columns = flat_columns

    records = work_df.to_dict(orient="records")

    cleaned = []
    for record in records:
        cleaned_record = {}
        for k, v in record.items():
            cleaned_record[k] = _json_value(v)
        cleaned.append(cleaned_record)

    return json.dumps(cleaned, ensure_ascii=False)


@app.route("/pivot", methods=["POST"])
def pivot():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    rows = request.form.get("rows")
    cols = request.form.get("cols")
    values = request.form.get("values")
    aggfunc = request.form.get("aggfunc", "sum")

    if not rows:
        return jsonify({"error": "Parameter 'rows' is required"}), 400
    if not values:
        return jsonify({"error": "Parameter 'values' is required"}), 400

    rows_list = [r.strip() for r in rows.split(",") if r.strip()]
    cols_list = [c.strip() for c in cols.split(",") if c.strip()] if cols else []
    values_list = [v.strip() for v in values.split(",") if v.strip()]

    try:
        aggfunc_dict = _parse_aggfunc(aggfunc, values_list)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        content = file.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(content))
    except Exception as e:
        return jsonify({"error": f"Failed to parse CSV: {str(e)}"}), 400

    for col in rows_list + cols_list + values_list:
        if col not in df.columns:
            return jsonify({"error": f"Column '{col}' not found in CSV"}), 400

    try:
        pivot_kwargs = {
            "index": rows_list,
            "values": values_list,
            "aggfunc": aggfunc_dict,
        }
        if cols_list:
            pivot_kwargs["columns"] = cols_list

        result_df = df.pivot_table(**pivot_kwargs)
    except Exception as e:
        return jsonify({"error": f"Failed to build pivot table: {str(e)}"}), 400

    result_json = pivot_table_to_json(result_df)

    return app.response_class(
        response=result_json,
        status=200,
        mimetype="application/json",
    )


@app.route("/columns", methods=["POST"])
def columns():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        content = file.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(content))
    except Exception as e:
        return jsonify({"error": f"Failed to parse CSV: {str(e)}"}), 400

    return jsonify({"columns": list(df.columns), "rows": len(df)})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
