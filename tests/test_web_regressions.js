// Zero-dependency integration tests: execute the actual app with bubbling DOM events.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const SimpleZipBuilder = require('../web/zip-builder.js');
const root = path.join(__dirname, '..', 'web');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const app = fs.readFileSync(path.join(root, 'app.js'), 'utf8');

class Element {
  constructor(id = '') {
    this.id = id; this.listeners = {}; this.children = []; this.value = '';
    this.files = []; this.disabled = false; this.clicks = 0;
    this.classList = { add() {}, remove() {} };
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  dispatch(type, event = {}) {
    event.target ||= this;
    event.stopPropagation ||= () => { event.stopped = true; };
    event.preventDefault ||= () => {};
    for (const fn of this.listeners[type] || []) fn(event);
    if (!event.stopped && this.parent) this.parent.dispatch(type, event);
  }
  click() {
    // Match HTML's guard against recursive programmatic clicks on the same element.
    if (this.clicking) return;
    this.clicks++; this.clicking = true;
    try { this.dispatch('click'); } finally { this.clicking = false; }
  }
  appendChild(child) { this.children.push(child); }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); }
  set innerHTML(value) { this.markup = value; this.children = []; }
  get innerHTML() { return this.markup || this.textContent || ''; }
}

function loadApp(code = app) {
  const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)]
    .map(([, id]) => [id, new Element(id)]));
  for (const id of ['file-input-multiple', 'file-input-directory', 'btn-browse-files', 'btn-browse-folder']) {
    elements[id].parent = elements.dropzone;
  }
  const result = { elements, downloads: [], errors: [] };
  const context = vm.createContext({
    document: { getElementById: id => elements[id], querySelectorAll: () => [],
      createElement: () => new Element(), body: new Element() },
    SimpleZipBuilder, Blob, URL: { createObjectURL: blob => {
      result.downloads.push(blob); return 'blob:test';
    }, revokeObjectURL() {} },
    setTimeout: () => {}, console: { error: (...args) => result.errors.push(args) },
  });
  vm.runInContext(code, context);
  result.run = expression => vm.runInContext(expression, context);
  return result;
}

function fixture(name, content, relativePath = name) {
  const bytes = Buffer.from(content);
  return { name, size: bytes.length, webkitRelativePath: relativePath,
    arrayBuffer: async () => Uint8Array.from(bytes).buffer };
}

async function main() {
  const fileTag = html.match(/<input[^>]*id="file-input-multiple"[^>]*>/)[0];
  const folderTag = html.match(/<input[^>]*id="file-input-directory"[^>]*>/)[0];
  assert.match(fileTag, /\bmultiple\b/);
  assert.doesNotMatch(fileTag, /webkitdirectory/);
  assert.match(folderTag, /\bwebkitdirectory\b/);

  // Prove this regression catches the original handler, rather than testing a copy.
  const broken = loadApp(app.replace(
    'if (e.target === fileInputMultiple || e.target === fileInputDirectory) return;', ''));
  broken.elements['btn-browse-folder'].click();
  assert.equal(broken.elements['file-input-multiple'].clicks, 1);

  const test = loadApp();
  const el = test.elements;
  el['btn-browse-folder'].click();
  assert.equal(el['file-input-directory'].clicks, 1);
  assert.equal(el['file-input-multiple'].clicks, 0, 'Folder click must not open file picker');
  el['btn-browse-files'].click();
  assert.equal(el['file-input-multiple'].clicks, 1);
  el.dropzone.click();
  assert.equal(el['file-input-multiple'].clicks, 2);
  console.log('PASS: picker attributes and bubbling regression (including original bug reproduction)');

  const fixtures = [fixture('report.txt', 'root bytes', 'Batch/report.txt'),
    fixture('report.txt', 'nested bytes', 'Batch/nested/report.txt'),
    fixture('REPORT.TXT', 'case bytes', 'Batch/deeper/REPORT.TXT'),
    fixture('photo.PNG', [137, 80, 78, 71], 'Batch/nested/photo.PNG'),
    fixture('unknown.bin', [0, 255, 1]), fixture('空.txt', 'Unicode content')];
  el['file-input-directory'].files = fixtures;
  el['file-input-directory'].value = 'selected';
  el['file-input-directory'].dispatch('change');
  assert.equal(el['file-input-directory'].value, '');
  el['btn-scan'].click();
  assert.equal(test.run('state.rawFiles.length'), 6);
  assert.equal(el['stat-total-files'].textContent, 6);
  assert.equal(el['stat-categories'].textContent, 3);
  assert.equal(el['stat-ready-files'].textContent, 6);
  assert.equal(el['stat-total-size'].textContent, `${fixtures.reduce((n, f) => n + f.size, 0)} B`);
  assert.equal(el['preview-tbody'].children.length, 6);
  assert.equal(test.run('state.previewItems[1].destinationPath'), 'Documents/report_1.txt');
  assert.equal(test.run('state.previewItems[2].destinationPath'), 'Documents/REPORT_2.TXT');
  for (const id of ['file-input-directory', 'file-input-multiple']) {
    el[id].files = []; el[id].dispatch('change'); el[id].dispatch('cancel');
    assert.equal(test.run('state.rawFiles.length'), 6);
    assert.equal(test.run('state.previewItems.length'), 6);
    assert.equal(el['btn-organize'].disabled, false);
  }
  el['file-input-directory'].files = fixtures;
  el['file-input-directory'].dispatch('change');
  assert.equal(test.run('state.rawFiles.length'), 6, 'Reselection replaces, never appends');
  el['btn-scan'].click();
  await test.run('handleOrganizeAndDownload()');
  assert.equal(test.downloads.length, 1);
  assert.equal(test.downloads[0].type, 'application/zip');
  assert.equal(test.errors.length, 0);
  assert.match(el['banner-text'].textContent, /Successfully organized 6 files/);

  const archive = Buffer.from(await test.downloads[0].arrayBuffer());
  // Independently verify CRCs, manifest, category paths, byte identity and real extraction.
  const python = spawnSync('python', ['-c', `
import io, json, pathlib, sys, tempfile, zipfile
expected = {
 'Documents/report.txt': b'root bytes',
 'Documents/report_1.txt': b'nested bytes',
 'Documents/REPORT_2.TXT': b'case bytes',
 'Images/photo.PNG': bytes([137,80,78,71]),
 'Other/unknown.bin': bytes([0,255,1]),
 'Documents/空.txt': b'Unicode content',
}
with zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())) as z:
 assert z.testzip() is None
 assert set(z.namelist()) == set(expected) | {'.smart_organizer_manifest.json'}
 manifest = json.loads(z.read('.smart_organizer_manifest.json'))
 assert manifest['total_organized'] == 6 and manifest['categories_count'] == 3
 assert {i['destinationPath'] for i in manifest['items']} == set(expected)
 with tempfile.TemporaryDirectory(dir=sys.argv[1]) as folder:
  z.extractall(folder)
  for name, content in expected.items():
   assert z.read(name) == content
   assert pathlib.Path(folder, name).read_bytes() == content
print('PASS: Python zipfile CRC, contents, manifest, UTF-8 paths and extraction')
`, __dirname], { input: archive, encoding: 'utf8' });
  assert.equal(python.status, 0, python.stderr || python.error?.message);
  console.log(python.stdout.trim());
  console.log('PASS: nested selection, preview, statistics, cancellation, reselection and download');

  el.dropzone.dispatch('drop', { dataTransfer: { files: [fixtures[0]] } });
  assert.equal(test.run('state.rawFiles.length'), 1);
  el['btn-reset'].click();
  assert.equal(test.run('state.rawFiles.length'), 0);
  assert.equal(el['btn-organize'].disabled, true);
  assert.equal(el['stat-total-files'].textContent, '0');

  for (const unsafe of ['../escape', 'Documents/../../escape', '/absolute', 'C:/escape',
    '\\\\server\\share', 'Documents/..\\escape', 'Documents/./file', 'Documents/file\0.txt']) {
    assert.throws(() => new SimpleZipBuilder().addFile(unsafe, 'x'), /Unsafe ZIP/);
  }
  assert.throws(() => new SimpleZipBuilder().addFile('Other/file', {}), /Unsupported content/);
  assert.throws(() => new SimpleZipBuilder().addFile('x'.repeat(65536), ''), /too long/);
  const duplicates = new SimpleZipBuilder();
  duplicates.addFile('Other/File', 'x');
  assert.throws(() => duplicates.addFile('Other/file', 'y'), /Duplicate ZIP/);
  // Metadata-only boundaries avoid allocating multi-gigabyte test buffers.
  const large = new SimpleZipBuilder();
  large.files = [{ path: 'Other/huge', data: { length: 0xFFFFFFFF } }];
  assert.throws(() => large.generate(), /Archive exceeds/);
  const many = new SimpleZipBuilder(); many.files.length = 65535;
  assert.throws(() => many.addFile('Other/file', ''), /Too many ZIP/);

  for (const bad of [
    { ...fixtures[0], size: 0xFFFFFFFF, arrayBuffer() { throw Error('Must not read'); } },
    { ...fixtures[0], arrayBuffer: async () => { throw Error('File cannot be read'); } },
  ]) {
    el['file-input-multiple'].files = [bad]; el['file-input-multiple'].dispatch('change');
    el['btn-scan'].click(); await test.run('handleOrganizeAndDownload()');
    assert.match(el['banner-text'].textContent, /Failed to create ZIP archive/);
    assert.equal(el['btn-organize'].disabled, false);
  }
  assert.equal(test.downloads.length, 1, 'Failures must not download incomplete archives');
  console.log('PASS: drag/drop, reset, unsafe paths, unsupported content, ZIP limits and read errors');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
