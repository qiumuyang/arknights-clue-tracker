import sqlite3
from datetime import datetime
from pathlib import Path

from pypinyin import lazy_pinyin

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    clue INTEGER NOT NULL CHECK(clue >= 1 AND clue <= 7),
    type TEXT NOT NULL CHECK(type IN ('+', '-')),
    was_new INTEGER NOT NULL DEFAULT 0,
    time TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_records_name ON records(name);
CREATE INDEX IF NOT EXISTS idx_records_time ON records(time);
CREATE INDEX IF NOT EXISTS idx_records_deleted ON records(deleted);
"""


def _row_to_dict(row: tuple, columns: list[str]) -> dict:
    return dict(zip(columns, row))


class Database:
    def __init__(self, path: str = "clues.db"):
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def add_record(
        self,
        name: str,
        clue: int,
        type_: str,
        was_new: bool = False,
        time: datetime | None = None,
    ) -> int:
        time = time or datetime.now()
        cur = self.conn.execute(
            "INSERT INTO records (name, clue, type, was_new, time) VALUES (?, ?, ?, ?, ?)",
            (name, clue, type_, int(was_new), time.isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_records(
        self,
        name: str | None = None,
        since: datetime | None = None,
        type_: str | None = None,
        clue: int | None = None,  # deprecated, use clues
        clues: list | None = None,
        include_deleted: bool = False,
        limit: int = 500,
        offset: int = 0,
        sort_col: str = "time",
        sort_dir: str = "desc",
    ) -> list[dict]:
        where = []
        params: list = []
        if not include_deleted:
            where.append("deleted = 0")
        if name:
            where.append("name = ?")
            params.append(name)
        if since:
            where.append("time >= ?")
            params.append(since.isoformat())
        if type_:
            where.append("type = ?")
            params.append(type_)
        if clues:
            where.append(f"clue IN ({','.join('?' * len(clues))})")
            params.extend(clues)
        elif clue:
            where.append("clue = ?")
            params.append(clue)
        sql = "SELECT * FROM records"
        if where:
            sql += " WHERE " + " AND ".join(where)
        safe_cols = {"time", "name", "clue"}
        col = sort_col if sort_col in safe_cols else "time"
        dir_ = "DESC" if sort_dir.lower() == "desc" else "ASC"
        sql += f" ORDER BY {col} {dir_}, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def count_records_filtered(
        self,
        name: str | None = None,
        since: datetime | None = None,
        type_: str | None = None,
        clue: int | None = None,  # deprecated, use clues
        clues: list | None = None,
        include_deleted: bool = False,
    ) -> int:
        where = []
        params: list = []
        if not include_deleted:
            where.append("deleted = 0")
        if name:
            where.append("name = ?")
            params.append(name)
        if since:
            where.append("time >= ?")
            params.append(since.isoformat())
        if type_:
            where.append("type = ?")
            params.append(type_)
        if clues:
            where.append(f"clue IN ({','.join('?' * len(clues))})")
            params.extend(clues)
        elif clue:
            where.append("clue = ?")
            params.append(clue)
        sql = "SELECT COUNT(*) FROM records"
        if where:
            sql += " WHERE " + " AND ".join(where)
        return self.conn.execute(sql, params).fetchone()[0]

    def update_record(self, id_: int, **kwargs) -> bool:
        allowed = {"time", "was_new"}
        sets = []
        params = []
        for k, v in kwargs.items():
            if k in allowed and v is not None:
                if k == "was_new":
                    sets.append("was_new = ?")
                    params.append(int(v))
                elif k == "time":
                    sets.append("time = ?")
                    params.append(v.isoformat())
        if not sets:
            return False
        params.append(id_)
        cur = self.conn.execute(f"UPDATE records SET {', '.join(sets)} WHERE id = ?", params)
        self.conn.commit()
        return cur.rowcount > 0

    def delete_record(self, id_: int) -> bool:
        cur = self.conn.execute("UPDATE records SET deleted = 1 WHERE id = ?", (id_,))
        self.conn.commit()
        return cur.rowcount > 0

    def get_summary(self, since: datetime | None = None, name: str | None = None) -> list[dict]:
        where = ["deleted = 0"]
        params = []
        if since:
            where.append("time >= ?")
            params.append(since.isoformat())
        if name:
            where.append("name = ?")
            params.append(name)
        sql = f"""
        SELECT name,
               SUM(CASE WHEN clue=1 AND type='+' THEN 1 WHEN clue=1 AND type='-' THEN -1 ELSE 0 END) AS c1,
               SUM(CASE WHEN clue=2 AND type='+' THEN 1 WHEN clue=2 AND type='-' THEN -1 ELSE 0 END) AS c2,
               SUM(CASE WHEN clue=3 AND type='+' THEN 1 WHEN clue=3 AND type='-' THEN -1 ELSE 0 END) AS c3,
               SUM(CASE WHEN clue=4 AND type='+' THEN 1 WHEN clue=4 AND type='-' THEN -1 ELSE 0 END) AS c4,
               SUM(CASE WHEN clue=5 AND type='+' THEN 1 WHEN clue=5 AND type='-' THEN -1 ELSE 0 END) AS c5,
               SUM(CASE WHEN clue=6 AND type='+' THEN 1 WHEN clue=6 AND type='-' THEN -1 ELSE 0 END) AS c6,
               SUM(CASE WHEN clue=7 AND type='+' THEN 1 WHEN clue=7 AND type='-' THEN -1 ELSE 0 END) AS c7,
               SUM(CASE WHEN type='+' THEN 1 WHEN type='-' THEN -1 ELSE 0 END) AS total
        FROM records WHERE {" AND ".join(where)}
        GROUP BY name ORDER BY total DESC
        """
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_players(self, query: str = "") -> list[str]:
        rows = self.conn.execute("SELECT DISTINCT name FROM records WHERE deleted = 0 ORDER BY name").fetchall()
        names = [r["name"] for r in rows]
        if not query:
            return names
        return self._match_names(names, query)

    def _match_names(self, names: list[str], query: str) -> list[str]:
        query = query.lower()
        candidates = []
        for name in names:
            if name.lower().startswith(query):
                candidates.append(name)
        if candidates:
            return candidates
        for name in names:
            pinyin = "".join(lazy_pinyin(name))
            if pinyin.startswith(query):
                candidates.append(name)
        if candidates:
            return candidates
        for name in names:
            pinyin = "".join(p[0] for p in lazy_pinyin(name))
            if pinyin.startswith(query):
                candidates.append(name)
        return candidates

    def get_latest_time(self, name: str) -> datetime | None:
        row = self.conn.execute(
            "SELECT time FROM records WHERE name = ? AND deleted = 0 ORDER BY time DESC LIMIT 1",
            (name,),
        ).fetchone()
        return datetime.fromisoformat(row["time"]) if row else None

    def import_from_file(self, filepath: str) -> dict:
        path = Path(filepath)
        if not path.exists():
            return {"imported": 0, "skipped": 0}
        existing = set()
        for r in self.conn.execute("SELECT name, clue, type, time FROM records WHERE deleted=0").fetchall():
            existing.add((r[0], r[1], r[2], r[3]))
        records = []
        skipped = 0
        for line in path.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 3:
                continue
            time_str, name, t_clue = parts
            if len(t_clue) < 2:
                continue
            type_ = t_clue[0]
            clue_str = t_clue[1:]
            if type_ not in ("+", "-") or not clue_str.isdigit():
                continue
            clue = int(clue_str)
            if not (1 <= clue <= 7):
                continue
            try:
                datetime.fromisoformat(time_str)
            except ValueError:
                continue
            key = (name, clue, type_, time_str)
            if key in existing:
                skipped += 1
                continue
            existing.add(key)
            records.append((name, clue, type_, 0, time_str))
        if records:
            self.conn.executemany(
                "INSERT INTO records (name, clue, type, was_new, time) VALUES (?, ?, ?, ?, ?)",
                records,
            )
            self.conn.commit()
        return {"imported": len(records), "skipped": skipped}

    def count_records(self, include_deleted: bool = False) -> int:
        sql = "SELECT COUNT(*) FROM records"
        if not include_deleted:
            sql += " WHERE deleted = 0"
        return self.conn.execute(sql).fetchone()[0]
