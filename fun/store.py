# -*- coding: utf-8 -*-

"""Minimal incremental object store using
- https://www.sqlite.org/json1.html#jpatch and
- https://sqlite.org/syntax/recursive-cte.html
"""

from sqlite3 import connect

create = """CREATE TABLE IF NOT EXISTS patches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inserted_at INTEGER(4) NOT NULL DEFAULT (strftime('%s', 'now')),
    previous_id INTEGER DEFAULT 0 REFERENCES patches(id) ON DELETE SET DEFAULT,
    patch JSON
);"""

insert = "INSERT INTO patches(previous_id, patch) VALUES (?, ?)"

select = """WITH RECURSIVE assemble_patches(id, object) AS (
    VALUES(0, '{}')
    UNION ALL
    SELECT p.id, JSON_PATCH(a.object, p.patch)
    FROM patches AS p
    JOIN assemble_patches AS a ON p.previous_id = a.id
)
    SELECT * FROM assemble_patches ORDER BY id DESC LIMIT 1;"""

if __name__ == "__main__":
    with connect(":memory:") as conn:
        cursor = conn.cursor()
        cursor.execute(create)
        cursor.executemany(insert, [
            (0, '{"a": 1}'),
            (1, '{"b": 2}'),
            (2, '{"a": 3}'),
            (3, '{"a": null}')
        ])
        res = cursor.execute(select)

    print(next(res))
