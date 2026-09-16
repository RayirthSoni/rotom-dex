"""CLI commands run against a built database."""

import contextlib
import io
import json

from rotom_dex.cli import main


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


def test_check_coverage_and_query(db_path):
    code, out, _ = run("check", "--db", str(db_path))
    assert code == 0 and json.loads(out)["status"] == "ok"
    code, out, _ = run("coverage", "--db", str(db_path), "--game", "red")
    assert code == 0 and json.loads(out)["games"][0]["slug"] == "red"
    code, out, _ = run("coverage", "--db", str(db_path), "--format", "markdown")
    assert code == 0 and out.startswith("# Coverage report")
    code, out, _ = run("query", "ralts", "--game", "emerald", "--level", "10", "--db", str(db_path))
    body = json.loads(out)
    assert code == 0 and body["data"]["learnset"]["moves"]
    code, _, err = run("query", "ralts", "--game", "nope", "--db", str(db_path))
    assert code == 1 and "Unknown game" in err


def test_missing_database_is_reported(tmp_path):
    code, _, err = run("check", "--db", str(tmp_path / "absent.sqlite3"))
    assert code == 1 and "not found" in err.lower()
    assert not (tmp_path / "absent.sqlite3").exists()
