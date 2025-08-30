import os
import re
import asyncpg
import aiosqlite


class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None
        self._sqlite: aiosqlite.Connection | None = None

    def _is_sqlite(self) -> bool:
        return self._dsn.startswith("sqlite:///") or self._dsn.endswith(".db")

    def _sqlite_path(self) -> str:
        # Resolve DSN to a filesystem path relative to project root (python-bot)
        if self._dsn.startswith("sqlite:///"):
            raw = self._dsn[len("sqlite///"):]
        elif self._dsn.startswith("sqlite://"):
            raw = self._dsn[len("sqlite://"):]
        else:
            raw = self._dsn
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return raw if os.path.isabs(raw) else os.path.join(base_dir, raw)

    def _adapt_query(self, query: str):
        # Convert $1, $2 ... to ? placeholders for sqlite
        def repl(m):
            return "?"

        return re.sub(r"\$\d+", repl, query)

    async def connect(self):
        if self._is_sqlite():
            path = self._sqlite_path()
            dir_name = os.path.dirname(path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
            self._sqlite = await aiosqlite.connect(path)
            await self._sqlite.execute("PRAGMA foreign_keys = ON;")
        else:
            self._pool = await asyncpg.create_pool(self._dsn, max_size=5)

    async def close(self):
        if self._sqlite:
            await self._sqlite.close()
        if self._pool:
            await self._pool.close()

    async def fetch(self, query: str, *args):
        if self._sqlite:
            q = self._adapt_query(query)
            cur = await self._sqlite.execute(q, args)
            cols = [c[0] for c in cur.description]
            rows = await cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            recs = await conn.fetch(query, *args)
            return [dict(r) for r in recs]

    async def fetchrow(self, query: str, *args):
        if self._sqlite:
            q = self._adapt_query(query)
            cur = await self._sqlite.execute(q, args)
            row = await cur.fetchone()
            if row is None:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rec = await conn.fetchrow(query, *args)
            return dict(rec) if rec else None

    async def execute(self, query: str, *args):
        if self._sqlite:
            q = self._adapt_query(query)
            await self._sqlite.execute(q, args)
            await self._sqlite.commit()
            return "OK"
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def ensure_schema(self):
        if self._sqlite:
            # Use executescript to run multiple SQL statements at once
            await self._sqlite.executescript(
                """
                create table if not exists users (
                  id integer primary key autoincrement,
                  username text,
                  telegram_id integer,
                  role text default 'user',
                  created_at text default (datetime('now'))
                );
                create table if not exists tariffs (
                  id integer primary key autoincrement,
                  location text not null,
                  specs text not null,
                  price real not null
                );
                create table if not exists orders (
                  id integer primary key autoincrement,
                  user_id integer references users(id) on delete set null,
                  tariff_id integer references tariffs(id) on delete set null,
                  status text default 'created',
                  invoice_id integer,
                  created_at text default (datetime('now'))
                );
                create table if not exists user_active_promocodes (
                  id integer primary key autoincrement,
                  user_id integer references users(id) on delete cascade,
                  promo_code text not null,
                  discount_percent integer not null,
                  min_amount integer default 0,
                  created_at text default (datetime('now'))
                );
                """
            )
            await self._sqlite.commit()
            return
        await self.execute(
            """
            create table if not exists users (
              id serial primary key,
              username varchar(255),
              telegram_id bigint,
              role varchar(32) default 'user',
              created_at timestamp default now()
            );
            create table if not exists tariffs (
              id serial primary key,
              location varchar(64) not null,
              specs varchar(255) not null,
              price numeric not null
            );
            create table if not exists orders (
              id serial primary key,
              user_id int references users(id) on delete set null,
              tariff_id int references tariffs(id) on delete set null,
              status varchar(32) default 'created',
              invoice_id bigint,
              created_at timestamp default now()
            );
            create table if not exists user_active_promocodes (
              id serial primary key,
              user_id int references users(id) on delete cascade,
              promo_code varchar(255) not null,
              discount_percent integer not null,
              min_amount integer default 0,
              created_at timestamp default now()
            );
            """
        )


