"""Schema extraction and comparison utilities."""

import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Mapping from pandas / common dtype names to Spark-equivalent types.
_SPARK_TYPE_MAP: Dict[str, str] = {
    'int64': 'integer', 'int32': 'integer', 'int16': 'integer', 'int8': 'integer',
    'uint8': 'integer', 'uint16': 'integer', 'uint32': 'integer', 'uint64': 'integer',
    'integer': 'integer', 'int': 'integer',
    'float64': 'double', 'float32': 'double', 'float16': 'double', 'double': 'double',
    'object': 'string', 'string': 'string',
    'bool': 'boolean', 'boolean': 'boolean',
    'datetime64[ns]': 'timestamp', 'datetime64': 'timestamp',
    'timedelta64[ns]': 'string',
    'category': 'string',
}


def get_spark_type(dtype_str: str) -> str:
    """Map a pandas dtype string to its Spark equivalent."""
    dtype_lower = dtype_str.lower()
    if dtype_lower in _SPARK_TYPE_MAP:
        return _SPARK_TYPE_MAP[dtype_lower]
    if dtype_lower.startswith(('int', 'uint')):
        return 'integer'
    if dtype_lower.startswith('float'):
        return 'double'
    if dtype_lower.startswith('datetime'):
        return 'timestamp'
    return 'string'


def get_schema_df(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame describing each column's pandas and Spark types."""
    rows = [
        {
            'Column Name': col,
            'Pandas Type': dataframe[col].dtype.name,
            'Spark Type': get_spark_type(dataframe[col].dtype.name),
        }
        for col in dataframe.columns
    ]
    return pd.DataFrame(rows)


def schema_to_json_dict(df_schema: pd.DataFrame,
                        file_name: str, file_ext: str) -> dict:
    """Convert a schema DataFrame to a JSON-serialisable dict."""
    df_copy = df_schema.copy()
    df_copy.columns = [c.lower().replace(' ', '_') for c in df_copy.columns]
    return {
        'schema': df_copy.to_dict(orient='records'),
        'total_columns': len(df_copy),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_file': f"{file_name}.{file_ext}",
    }


class SchemaComparisonResult:
    """Container for schema comparison results."""

    __slots__ = ('only_in_first', 'only_in_second',
                 'type_mismatches', 'order_mismatches')

    def __init__(self, only_in_first: List[str], only_in_second: List[str],
                 type_mismatches: List[str], order_mismatches: List[str]):
        self.only_in_first = only_in_first
        self.only_in_second = only_in_second
        self.type_mismatches = type_mismatches
        self.order_mismatches = order_mismatches

    @property
    def has_differences(self) -> bool:
        return bool(self.only_in_first or self.only_in_second
                    or self.type_mismatches or self.order_mismatches)

    @property
    def total_differences(self) -> int:
        return (len(self.only_in_first) + len(self.only_in_second)
                + len(self.type_mismatches) + len(self.order_mismatches))


def compare_schemas(json1: dict, json2: dict) -> SchemaComparisonResult:
    """Compare two JSON schemas **bidirectionally**, including column order.

    Checks performed
    ----------------
    1. Columns present only in the first schema.
    2. Columns present only in the second schema.
    3. Columns that exist in both but have different Spark types.
    4. Columns that exist in both but appear at a different position
       (order mismatch).
    """
    schema1_types = {c['column_name']: c['spark_type'] for c in json1['schema']}
    schema2_types = {c['column_name']: c['spark_type'] for c in json2['schema']}

    names1 = [c['column_name'] for c in json1['schema']]
    names2 = [c['column_name'] for c in json2['schema']]

    # 1 & 2 — existence
    only_in_first = [n for n in names1 if n not in schema2_types]
    only_in_second = [n for n in names2 if n not in schema1_types]

    # 3 — type mismatches (only for columns present in both)
    type_mismatches = [
        f"{n}: {schema1_types[n]} vs {schema2_types[n]}"
        for n in names1
        if n in schema2_types and schema1_types[n] != schema2_types[n]
    ]

    # 4 — order mismatches (only for columns present in both)
    #     Build position maps only for common columns, preserving their
    #     relative order in each schema.
    common = [n for n in names1 if n in schema2_types]
    pos2 = {n: idx for idx, n in enumerate(names2) if n in schema1_types}

    order_mismatches: List[str] = []
    for idx1, name in enumerate(common):
        idx2 = pos2.get(name)
        if idx2 is not None and idx1 != idx2:
            order_mismatches.append(
                f"{name}: position {idx1 + 1} in file 1 vs "
                f"position {idx2 + 1} in file 2"
            )

    return SchemaComparisonResult(
        only_in_first, only_in_second, type_mismatches, order_mismatches,
    )
