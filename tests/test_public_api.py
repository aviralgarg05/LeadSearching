import importlib
import types


def test_indexing_module_exports_build_index():
    mod = importlib.import_module("leadsearching.indexing")
    assert hasattr(mod, "build_index"), "build_index should be exported at package level"
    assert isinstance(getattr(mod, "build_index"), (types.FunctionType, types.BuiltinFunctionType))


def test_cli_help_exits_zero(monkeypatch):
    import sys
    import subprocess
    # Run the CLI with -h to ensure it prints help without importing heavy modules
    proc = subprocess.run([sys.executable, "cli.py", "-h"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "LeadSearching CLI" in proc.stdout


def test_cli_subcommand_help_exits_zero(monkeypatch):
    import sys
    import subprocess
    for subcmd in ["ingest", "index", "reset-db", "query"]:
        proc = subprocess.run([sys.executable, "cli.py", subcmd, "-h"], capture_output=True, text=True)
        assert proc.returncode == 0, f"help should work for {subcmd}"
