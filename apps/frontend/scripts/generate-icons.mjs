// Renders the PWA icons from scripts/icon.svg. Run: node scripts/generate-icons.mjs
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
// sharp ships with Next.js (not hoisted under pnpm), so resolve it from next.
const sharp = require(require.resolve("sharp", { paths: [dirname(require.resolve("next/package.json"))] }));
const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "../public/icons");
const svg = await readFile(join(here, "icon.svg"));

const rounded = (size, radius) =>
  Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><rect width="${size}" height="${size}" rx="${radius}" fill="#fff"/></svg>`);

async function icon(name, size, { round = true, pad = 0 } = {}) {
  let img = sharp(svg).resize(size, size);
  if (pad) {
    // Maskable: full-bleed gradient, glyph shrunk into the 80% safe zone.
    const maskable = svg.toString().replace("translate(64 64) scale(6)", "translate(102 102) scale(4.8)");
    img = sharp(Buffer.from(maskable)).resize(size, size);
  } else if (round) {
    img = img.composite([{ input: rounded(size, Math.round(size * 0.22)), blend: "dest-in" }]);
  }
  await img.png().toFile(join(out, name));
  console.log("wrote", name);
}

await icon("icon-192.png", 192);
await icon("icon-512.png", 512);
await icon("icon-maskable-512.png", 512, { pad: 0.1 });
await icon("apple-touch-icon.png", 180, { round: false });
await icon("favicon-32.png", 32);
