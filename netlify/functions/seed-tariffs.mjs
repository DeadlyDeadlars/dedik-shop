import { ensureSchema } from './db.mjs';
import { Tariffs } from './models.mjs';

const PRESET = [
  { location: 'Россия', specs: '3 Gb RAM / 2 Core CPU / SSD 40 Gb', price: 533 },
  { location: 'Россия', specs: '4 Gb RAM / 3 Core CPU / SSD 40 Gb', price: 598 },
  { location: 'Россия', specs: '4 Gb RAM / 2 Core CPU / SSD 40 Gb', price: 637 },
  { location: 'Россия', specs: '6 Gb RAM / 4 Core CPU / SSD 40 Gb', price: 650 },
  { location: 'Россия', specs: '8 Gb RAM / 4 Core CPU / SSD 70 Gb', price: 1014 },
  { location: 'Россия', specs: '16 Gb RAM / 8 Core CPU / SSD 120 Gb', price: 2054 },
  { location: 'Россия', specs: '24 Gb RAM / 10 Core CPU / SSD 120 Gb', price: 2405 },
  { location: 'Россия', specs: '32 Gb RAM / 10 Core CPU / SSD 250 Gb', price: 3510 },
  { location: 'Россия', specs: '64 Gb RAM / 20 Core CPU / SSD 500 Gb', price: 6354 },
  { location: 'Россия', specs: '128 Gb RAM / 32 Core CPU / SSD 2000 Gb', price: 10244 },
  { location: 'Германия', specs: '4 Gb RAM / 2 Core CPU / SSD 40 Gb', price: 624 },
];

export async function handler() {
  await ensureSchema();
  const existing = await Tariffs.all();
  if (existing.length === 0) {
    for (const t of PRESET) {
      await Tariffs.create(t);
    }
  }
  return { statusCode: 200, body: JSON.stringify({ ok: true, inserted: existing.length === 0 ? PRESET.length : 0 }) };
}


