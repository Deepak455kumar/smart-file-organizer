/**
 * Pure client-side zero-dependency ZIP archive generator.
 * Creates standard PKZip 2.0 archives compatible with Windows, macOS, Linux, and 7-Zip.
 */

class SimpleZipBuilder {
  constructor() {
    this.files = [];
    this.crcTable = this._makeCrcTable();
  }

  _makeCrcTable() {
    const table = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) {
        c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      }
      table[i] = c;
    }
    return table;
  }

  _crc32(uint8Array) {
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < uint8Array.length; i++) {
      crc = (crc >>> 8) ^ this.crcTable[(crc ^ uint8Array[i]) & 0xFF];
    }
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }

  /**
   * Add a file to the archive.
   * @param {string} path - Relative path inside archive (e.g. 'Images/pic.jpg')
   * @param {Uint8Array|ArrayBuffer|string} content - Raw content
   */
  addFile(path, content) {
    // Reject unsafe extraction paths instead of silently rewriting them.
    const normalizedPath = typeof path === "string" ? path.replace(/\\/g, "/") : "";
    if (!normalizedPath || /[\x00-\x1F:]/.test(normalizedPath) ||
        normalizedPath.split("/").some(part => !part || part === "." || part === "..")) {
      throw new Error("Unsafe ZIP entry path: " + path);
    }
    if (new TextEncoder().encode(normalizedPath).length > 0xFFFF) {
      throw new Error("ZIP entry path is too long: " + path);
    }
    if (this.files.some(file => file.path.toLowerCase() === normalizedPath.toLowerCase())) {
      throw new Error("Duplicate ZIP entry path: " + path);
    }
    if (this.files.length >= 0xFFFF) {
      throw new Error("Too many ZIP entries; ZIP64 is not supported.");
    }
    let data;
    if (typeof content === "string") {
      data = new TextEncoder().encode(content);
    } else if (content instanceof ArrayBuffer) {
      data = new Uint8Array(content);
    } else if (content instanceof Uint8Array) {
      data = content;
    } else {
      throw new Error("Unsupported content type for file: " + path);
    }

    if (data.length >= 0xFFFFFFFF) {
      throw new Error("File exceeds classic ZIP size limits; ZIP64 is not supported.");
    }
    this.files.push({
      path: normalizedPath,
      data: data,
    });
  }

  /**
   * Generate the ZIP file as a Uint8Array.
   * @returns {Uint8Array}
   */
  generate() {
    const archiveSize = this.files.reduce((size, file) =>
      size + 76 + 2 * new TextEncoder().encode(file.path).length + file.data.length, 22);
    if (archiveSize >= 0xFFFFFFFF) {
      throw new Error("Archive exceeds classic ZIP size limits; select fewer or smaller files.");
    }
    const entries = [];
    let offset = 0;
    const parts = [];

    const now = new Date();
    // DOS time and date
    const dosTime = ((now.getHours() << 11) | (now.getMinutes() << 5) | (Math.floor(now.getSeconds() / 2))) & 0xFFFF;
    const dosDate = (((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate()) & 0xFFFF;

    for (const file of this.files) {
      const nameBytes = new TextEncoder().encode(file.path);
      const dataBytes = file.data;
      const crc = this._crc32(dataBytes);
      const size = dataBytes.length;

      // Local File Header (30 bytes)
      const header = new Uint8Array(30);
      const view = new DataView(header.buffer);
      view.setUint32(0, 0x04034b50, true);  // Local header signature
      view.setUint16(4, 20, true);          // Version needed
      view.setUint16(6, 0x0800, true);      // General purpose bit flag (UTF-8)
      view.setUint16(8, 0, true);           // Compression method (0 = stored)
      view.setUint16(10, dosTime, true);    // Last mod time
      view.setUint16(12, dosDate, true);    // Last mod date
      view.setUint32(14, crc, true);        // CRC-32
      view.setUint32(18, size, true);       // Compressed size
      view.setUint32(22, size, true);       // Uncompressed size
      view.setUint16(26, nameBytes.length, true); // Filename length
      view.setUint16(28, 0, true);          // Extra field length

      entries.push({
        nameBytes,
        crc,
        size,
        offset,
        dosTime,
        dosDate,
      });

      parts.push(header, nameBytes, dataBytes);
      offset += header.length + nameBytes.length + dataBytes.length;
    }

    // Central Directory Headers
    const cdStart = offset;
    for (const entry of entries) {
      const cd = new Uint8Array(46);
      const view = new DataView(cd.buffer);
      view.setUint32(0, 0x02014b50, true);  // Central directory signature
      view.setUint16(4, 20, true);          // Version made by
      view.setUint16(6, 20, true);          // Version needed to extract
      view.setUint16(8, 0x0800, true);      // UTF-8 flag
      view.setUint16(10, 0, true);          // Compression method (stored)
      view.setUint16(12, entry.dosTime, true);
      view.setUint16(14, entry.dosDate, true);
      view.setUint32(16, entry.crc, true);
      view.setUint32(20, entry.size, true);
      view.setUint32(24, entry.size, true);
      view.setUint16(28, entry.nameBytes.length, true);
      view.setUint16(30, 0, true);          // Extra field length
      view.setUint16(32, 0, true);          // Comment length
      view.setUint16(34, 0, true);          // Disk number start
      view.setUint16(36, 0, true);          // Internal file attributes
      view.setUint32(38, 0, true);          // External file attributes
      view.setUint32(42, entry.offset, true); // Relative offset of local header

      parts.push(cd, entry.nameBytes);
      offset += cd.length + entry.nameBytes.length;
    }

    const cdSize = offset - cdStart;

    // End of Central Directory Record (22 bytes)
    const eocd = new Uint8Array(22);
    const eocdView = new DataView(eocd.buffer);
    eocdView.setUint32(0, 0x06054b50, true); // EOCD signature
    eocdView.setUint16(4, 0, true);          // Number of this disk
    eocdView.setUint16(6, 0, true);          // Disk with central directory
    eocdView.setUint16(8, entries.length, true);  // Total entries on this disk
    eocdView.setUint16(10, entries.length, true); // Total entries
    eocdView.setUint32(12, cdSize, true);         // Size of central directory
    eocdView.setUint32(16, cdStart, true);        // Offset of central directory
    eocdView.setUint16(20, 0, true);              // ZIP comment length

    parts.push(eocd);

    // Concatenate all Uint8Arrays
    const totalLength = parts.reduce((acc, p) => acc + p.length, 0);
    const result = new Uint8Array(totalLength);
    let writeOffset = 0;
    for (const part of parts) {
      result.set(part, writeOffset);
      writeOffset += part.length;
    }

    return result;
  }
}

// Attach to global scope for browser & Node
if (typeof window !== "undefined") {
  window.SimpleZipBuilder = SimpleZipBuilder;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = SimpleZipBuilder;
}
