import aiosqlite
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE NOT NULL,
    first_name TEXT, last_name TEXT, phone TEXT, username TEXT,
    is_blocked INTEGER DEFAULT 0,
    registered_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS tests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT, title TEXT NOT NULL, level TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS questions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    a TEXT, b TEXT, c TEXT, d TEXT,
    correct INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS results(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    test_id INTEGER, test_title TEXT,
    correct INTEGER, total INTEGER, percent REAL,
    finished_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS words(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL, translation TEXT, example TEXT
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        # Eski bazalar uchun: tests jadvaliga "code" ustuni qo'shiladi
        async with db.execute("PRAGMA table_info(tests)") as cur:
            cols = [r[1] for r in await cur.fetchall()]
        if "code" not in cols:
            await db.execute("ALTER TABLE tests ADD COLUMN code TEXT")
        # Kodi yo'q eski testlarga avtomatik kod beriladi (T1, T2, ...)
        await db.execute("UPDATE tests SET code = 'T' || id WHERE code IS NULL OR code = ''")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tests_code ON tests(code)")
        await db.commit()


async def fetchall(sql, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            return await cur.fetchall()


async def fetchone(sql, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            return await cur.fetchone()


async def execute(sql, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql, params)
        await db.commit()
        return cur.lastrowid


async def executemany(sql, seq):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(sql, seq)
        await db.commit()


async def leaderboard(limit=10):
    return await fetchall(
        """SELECT u.first_name, u.last_name, ROUND(AVG(r.percent),1) AS avg, COUNT(*) AS c
           FROM results r JOIN users u ON u.tg_id = r.tg_id
           GROUP BY r.tg_id ORDER BY avg DESC, c DESC LIMIT ?""",
        (limit,),
    )


async def test_by_code(code, only_active=False):
    """Kod bo'yicha testni (savollar soni bilan) topadi."""
    sql = """SELECT t.*, COUNT(q.id) AS c FROM tests t
             LEFT JOIN questions q ON q.test_id = t.id
             WHERE t.code = ? {} GROUP BY t.id"""
    return await fetchone(sql.format("AND t.is_active = 1" if only_active else ""), (code,))
