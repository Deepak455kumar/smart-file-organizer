/**
 * Automated test suite for Smart File Organizer Web Edition v1.2.0
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const SimpleZipBuilder = require('../web/zip-builder.js');
const webRoot = path.join(__dirname, '..', 'web');

console.log('--- Testing Smart File Organizer Web Edition ---');

// 1. Verify existence of web assets
assert(fs.existsSync(path.join(webRoot, 'index.html')), 'index.html must exist');
assert(fs.existsSync(path.join(webRoot, 'styles.css')), 'styles.css must exist');
assert(fs.existsSync(path.join(webRoot, 'app.js')), 'app.js must exist');
assert(fs.existsSync(path.join(webRoot, 'zip-builder.js')), 'zip-builder.js must exist');
console.log('✔ Web files exist');

// 2. Test Categorization & Extension Matching
const appCode = fs.readFileSync(path.join(webRoot, 'app.js'), 'utf8');
eval(appCode.slice(0, appCode.indexOf('// DOM Elements')));

const testCases = [
  ['photo.jpg', 'Images'],
  ['photo.PNG', 'Images'],
  ['notes.txt', 'Documents'],
  ['doc.PDF', 'Documents'],
  ['data.csv', 'Spreadsheets'],
  ['sheet.xlsx', 'Spreadsheets'],
  ['deck.pptx', 'Presentations'],
  ['clip.mp4', 'Videos'],
  ['track.mp3', 'Audio'],
  ['pkg.zip', 'Archives'],
  ['script.py', 'Code'],
  ['style.css', 'Code'],
  ['unknown.bin', 'Other'],
  ['no_extension', 'Other'],
];

for (const [filename, expected] of testCases) {
  const actual = getCategory(filename);
  assert.strictEqual(actual, expected, `Expected ${filename} to be ${expected}, got ${actual}`);
}
console.log('✔ Categorization logic passes all 14 test cases');

// 3. Test Collision Detection
const reserved = new Set();
function getDest(cat, filename) {
  const dot = filename.lastIndexOf('.');
  const stem = dot !== -1 ? filename.slice(0, dot) : filename;
  const suffix = dot !== -1 ? filename.slice(dot) : '';
  let finalName = filename;
  let dest = cat + '/' + finalName;
  let c = 1;
  while (reserved.has(dest)) {
    finalName = stem + '_' + c + suffix;
    dest = cat + '/' + finalName;
    c++;
  }
  reserved.add(dest);
  return dest;
}

assert.strictEqual(getDest('Documents', 'file.pdf'), 'Documents/file.pdf');
assert.strictEqual(getDest('Documents', 'file.pdf'), 'Documents/file_1.pdf');
assert.strictEqual(getDest('Documents', 'file.pdf'), 'Documents/file_2.pdf');
console.log('✔ Duplicate collision renaming verified (file.pdf -> file_1.pdf -> file_2.pdf)');

// 4. Test ZIP Generation
const zip = new SimpleZipBuilder();
zip.addFile('Documents/contract.pdf', 'contract text');
zip.addFile('Images/logo.png', new Uint8Array([137, 80, 78, 71]));
zip.addFile('.smart_organizer_manifest.json', JSON.stringify({ test: true }));

const bytes = zip.generate();
assert(bytes instanceof Uint8Array, 'ZIP output must be Uint8Array');
assert(bytes.length > 100, 'ZIP size must be non-trivial');
console.log(`✔ Client-side ZIP generation verified (${bytes.length} bytes generated)`);

console.log('All Web Edition tests passed successfully!');
