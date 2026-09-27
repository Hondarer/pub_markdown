'use strict';

// MkDocs 用 favicon SVG を、サイト直下の /favicon.ico 向け ICO にする。
// <link rel="icon"> が無いページは、この URL を自分から取りに行く。
//
// 画像は PNG を格納する。透過つきの ICO として Windows Vista 以降で読める。
// see: https://learn.microsoft.com/en-us/windows/win32/menurc/about-icons

const fs = require('fs');
const sharp = require('sharp');

// タブとブックマークが使う 16/32 と、SVG の viewBox と同じ 48。
const SIZES = [16, 32, 48];
// sharp は SVG を density（DPI）で一度描いてから縮小する。
// viewBox 48 を既定の 72 DPI で描くと原寸の 48 px になり、16 px への縮小が粗い。
const SVG_DENSITY = 72 * 4;

function packIco(images) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);
  const directory = Buffer.alloc(16 * images.length);
  let offset = 6 + directory.length;
  const parts = [header, directory];
  images.forEach((image, index) => {
    const entry = index * 16;
    const dimension = image.size >= 256 ? 0 : image.size;
    directory.writeUInt8(dimension, entry);
    directory.writeUInt8(dimension, entry + 1);
    directory.writeUInt16LE(1, entry + 4);
    directory.writeUInt16LE(32, entry + 6);
    directory.writeUInt32LE(image.png.length, entry + 8);
    directory.writeUInt32LE(offset, entry + 12);
    offset += image.png.length;
    parts.push(image.png);
  });
  return Buffer.concat(parts);
}

async function renderPng(svg, size) {
  return sharp(svg, { density: SVG_DENSITY })
    .resize(size, size, { fit: 'fill' })
    .png({ compressionLevel: 9 })
    .toBuffer();
}

async function main() {
  const svgPath = process.argv[2];
  if (!svgPath) {
    throw new Error('usage: node build-favicon-ico.js <svg>');
  }
  const svg = fs.readFileSync(svgPath);
  const images = [];
  for (const size of SIZES) {
    images.push({ size, png: await renderPng(svg, size) });
  }
  process.stdout.write(packIco(images));
}

main().catch((error) => {
  console.error(error && error.message ? error.message : String(error));
  process.exit(1);
});
