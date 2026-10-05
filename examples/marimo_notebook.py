import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", sql_output="pandas")


@app.cell
def _():
    import ibis
    import marimo as mo

    return ibis, mo


@app.cell
def _(ibis):
    connection = ibis.altertable.connect()
    return (connection,)


@app.cell
def _(mo):
    minimum = mo.ui.slider(
        0, 40, value=10, label="Minimum customer total", debounce=True, show_value=True
    )
    minimum
    return (minimum,)


@app.cell
def _(connection, minimum, mo):
    totals = mo.sql(
        f"""
        WITH orders(customer, amount) AS (
            VALUES ('alice', 10), ('alice', 20), ('bob', 5)
        )
        SELECT customer, sum(amount) AS total
        FROM orders
        GROUP BY customer
        HAVING sum(amount) >= {minimum.value}
        ORDER BY customer
        """,
        engine=connection,
    )
    return (totals,)


if __name__ == "__main__":
    app.run()
