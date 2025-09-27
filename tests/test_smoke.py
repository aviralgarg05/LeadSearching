from pathlib import Path
from leadsearch.config import get_settings
from leadsearch.ingest import ingest
from leadsearch.search import hybrid_search


def test_smoke_ingest_and_search(tmp_path, monkeypatch):
    # Create tiny CSV zip on the fly
    import zipfile, io
    csv_content = "username,name,bio,category,followerCount,followingCount,website,email,phone\n" \
        "user1,Alpha,Alpha bio,Cat,10,5,https://a.com,a@a.com,111\n" \
        "user2,Beta,Beta bio,Cat,20,10,https://b.com,b@b.com,222\n"
    zpath = tmp_path / "sample.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("d/sample.csv", csv_content)
    # Adjust settings for test
    monkeypatch.setenv("LS_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LS_INDEX_DIR", str(tmp_path / "index"))
    ingest(zpath, "d/*.csv", dataset="test", limit=None, no_vectors=True)
    res = hybrid_search("Alpha", k=5, alpha=0.0)  # lexical only
    assert any(r["username"] == "user1" for r in res)
