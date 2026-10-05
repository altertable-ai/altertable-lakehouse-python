from __future__ import annotations

import sys
from typing import Any, Mapping, Optional, Union

if sys.version_info < (3, 10):
    raise ImportError("The Altertable Ibis backend requires Python 3.10 or newer.")

try:
    import ibis.expr.datatypes as dt
    import ibis.expr.operations as ops
    import ibis.expr.schema as sch
    import ibis.expr.types as ir
    import pyarrow as pa
    import pyarrow.parquet as pq
    import sqlglot as sg
    from ibis.backends.sql import SQLBackend
    from ibis.backends.sql.compilers.duckdb import DuckDBCompiler
    from ibis.common.exceptions import UnsupportedOperationError
    from ibis.formats.pandas import PandasData
    from ibis.formats.pyarrow import PyArrowData
except ImportError as exc:
    raise ImportError(
        "Install the Ibis backend with: pip install 'altertable-lakehouse[ibis]'"
    ) from exc

from .client import Client
from .models import QueryRequest, QueryResult

Database = Optional[Union[str, tuple[str, str]]]


class Backend(SQLBackend):
    """Read-oriented Ibis backend. SQL runs remotely through ``Client``."""

    name = "altertable"
    compiler = DuckDBCompiler()

    def do_connect(
        self,
        *,
        client: Optional[Client] = None,
        catalog: Optional[str] = None,
        database: Optional[str] = None,
        **client_options: Any,
    ) -> None:
        """Connect with Client credentials/options or an existing ``client``.

        ``database`` means the Altertable schema. The optional ``catalog`` and
        ``database`` are sent with every query. Existing clients remain owned by
        their caller; disconnect only closes clients constructed by this backend.
        """
        if client is not None and client_options:
            raise ValueError(
                "Pass either client or Client connection options, not both."
            )
        self.client = client if client is not None else Client(**client_options)
        self._owns_client = client is None
        self._catalog = catalog
        self._database = database

    @classmethod
    def from_connection(cls, con: Client, /, **kwargs: Any) -> Backend:
        """Wrap an existing SDK client without taking ownership of it."""
        return cls().connect(client=con, **kwargs)

    def _from_url(self, url: Any, **kwargs: Any) -> Backend:
        raise NotImplementedError("Use ibis.altertable.connect with Client options.")

    def disconnect(self) -> None:
        if self._owns_client:
            self.client._client.close()

    def _query(self, statement: str) -> QueryResult:
        return self.client.query_all(
            QueryRequest(
                statement=statement, catalog=self._catalog, schema=self._database
            )
        )

    @property
    def version(self) -> str:
        return self._query("SELECT version()").rows[0][0]

    @property
    def current_catalog(self) -> str:
        return self._catalog or self._query("SELECT current_database()").rows[0][0]

    @property
    def current_database(self) -> str:
        return self._database or self._query("SELECT current_schema()").rows[0][0]

    def list_catalogs(self, *, like: Optional[str] = None) -> list[str]:
        rows = self._query(
            "SELECT DISTINCT catalog_name FROM information_schema.schemata"
        ).rows
        return self._filter_with_like((row[0] for row in rows), like)

    def list_databases(
        self, *, like: Optional[str] = None, catalog: Optional[str] = None
    ) -> list[str]:
        query = sg.select("schema_name").distinct().from_("information_schema.schemata")
        query = query.where(
            sg.column("catalog_name").eq(catalog or self.current_catalog)
        )
        rows = self._query(query.sql(self.dialect)).rows
        return self._filter_with_like((row[0] for row in rows), like)

    def list_tables(
        self, *, like: Optional[str] = None, database: Database = None
    ) -> list[str]:
        location = self._to_sqlglot_table(database)
        query = (
            sg.select("table_name")
            .from_("information_schema.tables")
            .where(
                sg.column("table_catalog").eq(location.catalog or self.current_catalog),
                sg.column("table_schema").eq(location.db or self.current_database),
            )
        )
        rows = self._query(query.sql(self.dialect)).rows
        return self._filter_with_like((row[0] for row in rows), like)

    def get_schema(
        self,
        table_name: str,
        *,
        catalog: Optional[str] = None,
        database: Optional[str] = None,
    ) -> sch.Schema:
        table = sg.table(table_name, db=database, catalog=catalog, quoted=True)
        return self._get_schema_using_query(f"SELECT * FROM {table.sql(self.dialect)}")

    def _get_schema_using_query(self, query: str) -> sch.Schema:
        rows = self._query(f"DESCRIBE {query}").rows
        return sch.Schema(
            {
                name: self.compiler.type_mapper.from_string(
                    dtype, nullable=nullable == "YES"
                )
                for name, dtype, nullable, *_ in rows
            }
        )

    def _run_pre_execute_hooks(self, expr: ir.Expr) -> None:
        if expr.op().find((ops.ScalarUDF, ops.AggUDF)):
            raise UnsupportedOperationError("Altertable does not support Ibis UDFs.")
        if expr.op().find(ops.InMemoryTable):
            raise UnsupportedOperationError(
                "Altertable does not support Ibis memtables. Upload data with Client.upload."
            )
        for dtype in expr.as_table().schema().types:
            _check_result_type(dtype)

    def _register_in_memory_table(self, op: ops.InMemoryTable) -> None:
        raise UnsupportedOperationError("Altertable does not support Ibis memtables.")

    def raw_sql(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Ibis raw SQL cursors and mutations are unsupported. Use Client.query instead."
        )

    _safe_raw_sql = raw_sql
    create_table = raw_sql

    def to_pyarrow_batches(
        self,
        expr: ir.Expr,
        /,
        *,
        params: Optional[Mapping[ir.Scalar, Any]] = None,
        limit: Optional[Union[int, str]] = None,
        chunk_size: int = 1_000_000,
        **kwargs: Any,
    ) -> pa.RecordBatchReader:
        """Execute eagerly; batch the accumulated HTTP result in memory."""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._run_pre_execute_hooks(expr)
        table = expr.as_table()
        result = self.client.query_parquet(
            QueryRequest(
                statement=self.compile(table, params=params, limit=limit, **kwargs),
                catalog=self._catalog,
                schema=self._database,
            )
        )
        arrow_table = pq.read_table(pa.BufferReader(result)).rename_columns(
            table.columns
        )
        arrow_table = PyArrowData.convert_table(arrow_table, table.schema())
        return arrow_table.to_reader(max_chunksize=chunk_size)

    def execute(
        self,
        expr: ir.Expr,
        /,
        *,
        params: Optional[Mapping[ir.Scalar, Any]] = None,
        limit: Optional[Union[int, str]] = None,
        **kwargs: Any,
    ) -> Any:
        with self.to_pyarrow_batches(
            expr, params=params, limit=limit, **kwargs
        ) as reader:
            frame = reader.read_all().to_pandas(integer_object_nulls=True)
        frame = PandasData.convert_table(frame, expr.as_table().schema())
        return expr.__pandas_result__(frame)


def _check_result_type(dtype: dt.DataType) -> None:
    if isinstance(dtype, (dt.Unknown, dt.Interval, dt.GeoSpatial)):
        raise UnsupportedOperationError(
            f"Altertable Ibis results do not support {dtype}. "
            "Cast it to a supported type in SQL before executing."
        )
    if dtype.is_array():
        _check_result_type(dtype.value_type)
    elif dtype.is_map():
        _check_result_type(dtype.key_type)
        _check_result_type(dtype.value_type)
    elif dtype.is_struct():
        for child in dtype.types:
            _check_result_type(child)
