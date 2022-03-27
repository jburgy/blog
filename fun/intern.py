from sqlite3 import connect

statements = """
CREATE TABLE IF NOT EXISTS dimension (
    dimensionid INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS fact (
    factid INTEGER PRIMARY KEY,
    dimension INTEGER REFERENCES dimension(dimensionid) ON UPDATE RESTRICT,
    value REAL
);

CREATE VIEW IF NOT EXISTS facts (factid, dimension, value) AS
    SELECT f.factid, d.name, f.value
    FROM FACT AS f
    JOIN dimension AS d ON f.dimension = d.dimensionid;

CREATE TRIGGER IF NOT EXISTS insert_fact
    INSTEAD OF INSERT ON facts
BEGIN
    INSERT OR IGNORE INTO dimension(name)
    VALUES (NEW.dimension);
    INSERT INTO fact(dimension, value)
    SELECT dimensionid, NEW.value FROM dimension WHERE name = NEW.dimension;
END;
""".split("\n" * 2)

records = [(k, x) for k in list("abcdef") for x in range(17)]

with connect(":memory:") as conn:
    c = conn.cursor()
    for statement in statements:
        c.execute(statement)
    c.executemany("INSERT INTO facts(dimension, value) VALUES(?, ?)", records)
    c.execute("SELECT dimension, SUM(value) AS value FROM facts GROUP BY dimension")
    print(c.fetchall())
