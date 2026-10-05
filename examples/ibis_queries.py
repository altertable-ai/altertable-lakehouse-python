import os

import ibis


def main() -> None:
    connection = ibis.altertable.connect(
        base_url=os.environ.get("ALTERTABLE_BASE_URL", "https://api.altertable.ai")
    )
    try:
        orders = connection.sql(
            "SELECT * FROM (VALUES ('alice', 10), ('alice', 20), ('bob', 5)) "
            "AS orders(customer, amount)"
        )
        totals = orders.group_by("customer").aggregate(total=orders.amount.sum())
        minimum = ibis.param("int64")
        result = totals.filter(totals.total >= minimum).order_by("customer")
        print(connection.compile(result, params={minimum: 10}))
        print(result.execute(params={minimum: 10}))
        print(result.to_pyarrow(params={minimum: 10}))
    finally:
        connection.disconnect()


if __name__ == "__main__":
    main()
