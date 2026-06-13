import io
import json

from flask import Flask, request, jsonify
import pandas as pd

app = Flask(__name__)

ALLOWED_AGGFUNCS = {"sum", "mean", "count"}


def pivot_table_to_json(df: pd.DataFrame) -> str:
    data = []
    if isinstance(df.columns, pd.MultiIndex):
        col_tuples = list(df.columns)
    else:
        col_tuples = [(str(c),) for c in df.columns]

    if isinstance(df.index, pd.MultiIndex):
        idx_names = list(df.index.names)
    else:
        idx_names = [df.index.name if df.index.name else "index"]

    for idx, row in df.iterrows():
        if isinstance(idx, tuple):
            idx_values = list(idx)
        else:
            idx_values = [idx]

        row_data = {}
        for name, val in zip(idx_names, idx_values):
            row_data[name] = _json_value(val)

        for col_tuple in col_tuples:
            if len(col_tuple) == 1:
                key = col_tuple[0]
            else:
                key = "_".join(str(c) for c in col_tuple)
            row_data[key] = _json_value(row[col_tuple] if len(col_tuple) > 1 else row[col_tuple[0]])

        data.append(row_data)

    return json.dumps(data, ensure_ascii=False)


def _json_value(v):
    if pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v


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
    aggfunc_list = [a.strip() for a in aggfunc.split(",") if a.strip()]

    for af in aggfunc_list:
        if af not in ALLOWED_AGGFUNCS:
            return jsonify({
                "error": f"Invalid aggfunc '{af}'. Allowed values: {', '.join(sorted(ALLOWED_AGGFUNCS))}"
            }), 400

    try:
        content = file.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(content))
    except Exception as e:
        return jsonify({"error": f"Failed to parse CSV: {str(e)}"}), 400

    for col in rows_list + cols_list + values_list:
        if col not in df.columns:
            return jsonify({"error": f"Column '{col}' not found in CSV"}), 400

    effective_aggfunc = aggfunc_list[0] if len(aggfunc_list) == 1 else aggfunc_list

    try:
        pivot_kwargs = {
            "index": rows_list,
            "values": values_list,
            "aggfunc": effective_aggfunc,
        }
        if cols_list:
            pivot_kwargs["columns"] = cols_list

        result_df = df.pivot_table(**pivot_kwargs)
    except Exception as e:
        return jsonify({"error": f"Failed to build pivot table: {str(e)}"}), 400

    result_json = pivot_table_to_json(result_df.reset_index() if not isinstance(result_df.index, pd.MultiIndex) and result_df.index.name is None else result_df)

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
