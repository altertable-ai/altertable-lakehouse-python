import subprocess
import sys


def test_base_sdk_does_not_import_optional_dependencies():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import builtins
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.split('.')[0] in {'ibis', 'pandas', 'pyarrow', 'duckdb'}:
        raise AssertionError(f'Unexpected optional import: {name}')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
from altertable_lakehouse import Client
client = Client(token='test-token')
client._client.close()
""",
        ],
        check=True,
    )


def test_missing_ibis_dependency_has_installation_guidance():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import builtins
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.split('.')[0] == 'ibis':
        raise ImportError('ibis is not installed')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
try:
    import altertable_lakehouse.ibis
except ImportError as error:
    assert 'altertable-lakehouse[ibis]' in str(error) or 'Python 3.10' in str(error)
else:
    raise AssertionError('Expected installation guidance')
""",
        ],
        check=True,
    )
