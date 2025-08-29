import pg from 'pg';

const { Pool } = pg;

const DATABASE_URL = process.env.DATABASE_URL || '';

let pool;
export function getPool() {
  if (!pool) {
    if (!DATABASE_URL) {
      console.warn('DATABASE_URL is not set');
    }
    pool = new Pool({ connectionString: DATABASE_URL, max: 5, idleTimeoutMillis: 30_000 });
  }
  return pool;
}

export async function query(sql, params) {
  const client = await getPool().connect();
  try {
    const res = await client.query(sql, params);
    return res;
  } finally {
    client.release();
  }
}

export async function ensureSchema() {
  // Minimal idempotent schema setup
  await query(`
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
  `);
  // best-effort add missing columns
  await query(`do $$ begin
    begin alter table users add column if not exists telegram_id bigint; exception when others then end;
  end $$;`);
}


