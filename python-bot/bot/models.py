from .db import Database


class Tariffs:
    def __init__(self, db: Database):
        self.db = db

    async def list_locations(self) -> list[str]:
        rows = await self.db.fetch("select distinct location from tariffs order by location")
        return [r["location"] for r in rows]

    async def list_by_location(self, location: str):
        rows = await self.db.fetch("select * from tariffs where location=$1 order by price asc", location)
        return rows

    async def all(self):
        return await self.db.fetch("select * from tariffs order by location, price")

    async def create(self, location: str, specs: str, price: float):
        # Ensure SQLite gets a native float
        price_val = float(price)
        return await self.db.fetchrow(
            "insert into tariffs(location,specs,price) values($1,$2,$3) returning *",
            location,
            specs,
            price_val,
        )


class Users:
    def __init__(self, db: Database):
        self.db = db

    async def upsert(self, username: str | None, telegram_id: int):
        row = await self.db.fetchrow("select * from users where telegram_id=$1", telegram_id)
        if row:
            return row
        return await self.db.fetchrow(
            "insert into users(username, telegram_id) values($1,$2) returning *",
            username,
            telegram_id,
        )


class Orders:
    def __init__(self, db: Database):
        self.db = db

    async def create(self, user_id: int, tariff_id: int, invoice_id: int | None):
        return await self.db.fetchrow(
            "insert into orders(user_id, tariff_id, status, invoice_id) values($1,$2,'created',$3) returning *",
            user_id,
            tariff_id,
            invoice_id,
        )

    async def by_user(self, user_id: int):
        return await self.db.fetch(
            "select o.*, t.location, t.specs, t.price from orders o left join tariffs t on t.id=o.tariff_id where user_id=$1 order by o.id desc",
            user_id,
        )

    async def by_invoice_id(self, invoice_id: int):
        return await self.db.fetchrow("select * from orders where invoice_id=$1", invoice_id)

    async def set_status(self, order_id: int, status: str):
        updated = await self.db.fetchrow("update orders set status=$2 where id=$1 returning *", order_id, status)
        if not updated:
            await self.db.execute("update orders set status=$2 where id=$1", order_id, status)
            # fetch full joined row
            updated = await self.with_user_by_id(order_id)
        return updated

    async def with_user_by_id(self, order_id: int):
        return await self.db.fetchrow(
            """
            select o.*, u.telegram_id, u.username, t.location, t.specs, t.price
            from orders o
            left join users u on u.id = o.user_id
            left join tariffs t on t.id = o.tariff_id
            where o.id=$1
            """,
            order_id,
        )

    async def with_user_by_invoice(self, invoice_id: int):
        return await self.db.fetchrow(
            """
            select o.*, u.telegram_id, t.location, t.specs, t.price
            from orders o
            left join users u on u.id = o.user_id
            left join tariffs t on t.id = o.tariff_id
            where o.invoice_id=$1
            """,
            invoice_id,
        )


