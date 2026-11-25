/**
 * Smart File Organizer Web Edition v1.2.0
 * Pure client-side categorization, preview engine, and ZIP archiver.
 */

// Category mappings identical to config.py
const EXTENSION_CATEGORIES = {
  Images: [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
  Documents: [".pdf", ".doc", ".docx", ".txt", ".rtf"],
  Spreadsheets: [".csv", ".xls", ".xlsx"],
  Presentations: [".ppt", ".pptx"],
  Videos: [".mp4", ".mkv", ".avi", ".mov"],
  Audio: [".mp3", ".wav", ".flac"],
  Archives: [".zip", ".rar", ".7z"],
  Code: [".py", ".js", ".html", ".css", ".java", ".cpp"],
};

const DEFAULT_CATEGORY = "Other";

const EXTENSION_ICONS = {
  ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".webp": "🖼️", ".bmp": "🖼️",
  ".pdf": "📄", ".doc": "📄", ".docx": "📄", ".txt": "📄", ".rtf": "📄",
  ".csv": "📈", ".xls": "📈", ".xlsx": "📈",
  ".ppt": "📊", ".pptx": "📊",
  ".mp4": "🎬", ".mkv": "🎬", ".avi": "🎬", ".mov": "🎬",
  ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵",
  ".zip": "📦", ".rar": "📦", ".7z": "📦",
  ".py": "💻", ".js": "💻", ".html": "🌐", ".css": "🎨", ".java": "☕", ".cpp": "⚙️",
};

// Application State
const state = {
  rawFiles: [],        // Array of File objects
  previewItems: [],    // Processed preview records
  isScanning: false,
};

// Format Bytes
function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
}

// Categorization helper
function getCategory(filename) {
  const dotIndex = filename.lastIndexOf(".");
  if (dotIndex === -1) return DEFAULT_CATEGORY;
  const ext = filename.slice(dotIndex).toLowerCase();

  for (const [category, extensions] of Object.entries(EXTENSION_CATEGORIES)) {
    if (extensions.includes(ext)) {
      return category;
    }
  }
  return DEFAULT_CATEGORY;
}

// DOM Elements
const dropzone = document.getElementById("dropzone");
const fileInputMultiple = document.getElementById("file-input-multiple");
const fileInputDirectory = document.getElementById("file-input-directory");
const btnBrowseFiles = document.getElementById("btn-browse-files");
const btnBrowseFolder = document.getElementById("btn-browse-folder");
const selectedPathDisplay = document.getElementById("selected-path-display");

const statTotalFiles = document.getElementById("stat-total-files");
const statCategories = document.getElementById("stat-categories");
const statTotalSize = document.getElementById("stat-total-size");
const statReadyFiles = document.getElementById("stat-ready-files");

const btnScan = document.getElementById("btn-scan");
const btnOrganize = document.getElementById("btn-organize");
const btnReset = document.getElementById("btn-reset");

const tableSummaryCounter = document.getElementById("table-summary-counter");
const previewTbody = document.getElementById("preview-tbody");
const statusBanner = document.getElementById("status-banner");
const bannerIcon = document.getElementById("banner-icon");
const bannerText = document.getElementById("banner-text");

// Set Banner Notification
function setBanner(text, type = "info") {
  statusBanner.className = `notification-banner banner-${type}`;
  if (type === "success") bannerIcon.textContent = "✔";
  else if (type === "warning") bannerIcon.textContent = "⚠️";
  else bannerIcon.textContent = "ℹ";
  bannerText.textContent = text;
}

// File Selection & Drag-and-Drop Handling
function handleFilesSelected(fileList) {
  const newFiles = Array.from(fileList);
  if (!newFiles.length) return;

  // Filter out system dot-files (.DS_Store, desktop.ini, etc.)
  state.rawFiles = newFiles.filter(f => !f.name.startsWith(".") && f.name !== "Thumbs.db");
  
  const totalCount = state.rawFiles.length;
  selectedPathDisplay.textContent = `${totalCount} file(s) staged. Click "Scan & Preview" to analyze.`;
  
  btnScan.disabled = totalCount === 0;
  btnReset.disabled = totalCount === 0;
  btnOrganize.disabled = true;

  setBanner(`Loaded ${totalCount} file(s). Ready for preview scan.`, "info");
}

// Setup Event Listeners
btnBrowseFiles.addEventListener("click", (e) => {
  e.stopPropagation();
  fileInputMultiple.click();
});

btnBrowseFolder.addEventListener("click", (e) => {
  e.stopPropagation();
  fileInputDirectory.click();
});

dropzone.addEventListener("click", (e) => {
  // Programmatic input clicks bubble too; never open a second picker for them.
  if (e.target === fileInputMultiple || e.target === fileInputDirectory) return;
  fileInputMultiple.click();
});

fileInputMultiple.addEventListener("change", (e) => {
  handleFilesSelected(e.target.files);
  e.target.value = ""; // Allow selecting the same files again; state keeps the File objects.
});

fileInputDirectory.addEventListener("change", (e) => {
  handleFilesSelected(e.target.files);
  e.target.value = "";
});

// Drag and drop
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    handleFilesSelected(e.dataTransfer.files);
  }
});

// Preview & Categorization Engine
function runPreview() {
  if (!state.rawFiles.length) return;

  state.previewItems = [];
  const reservedDestinations = new Set();
  const categoryCountMap = new Map();
  let totalBytes = 0;

  for (const file of state.rawFiles) {
    const category = getCategory(file.name);
    categoryCountMap.set(category, (categoryCountMap.get(category) || 0) + 1);
    totalBytes += file.size;

    // Collision detection & unique destination generation
    const dotIndex = file.name.lastIndexOf(".");
    const stem = dotIndex !== -1 ? file.name.slice(0, dotIndex) : file.name;
    const suffix = dotIndex !== -1 ? file.name.slice(dotIndex) : "";

    let finalName = file.name;
    let isDuplicate = false;
    let destPath = `${category}/${finalName}`;

    let counter = 1;
    while (reservedDestinations.has(destPath.toLowerCase())) {
      finalName = `${stem}_${counter}${suffix}`;
      destPath = `${category}/${finalName}`;
      isDuplicate = true;
      counter++;
    }
    reservedDestinations.add(destPath.toLowerCase());

    state.previewItems.push({
      file: file,
      filename: file.name,
      category: category,
      destinationPath: destPath,
      finalName: finalName,
      size: file.size,
      isDuplicate: isDuplicate,
      status: isDuplicate ? "Renamed" : "Ready",
    });
  }

  // Update 4 Statistics Cards
  statTotalFiles.textContent = state.previewItems.length;
  statCategories.textContent = categoryCountMap.size;
  statTotalSize.textContent = formatBytes(totalBytes);
  statReadyFiles.textContent = state.previewItems.length;
  tableSummaryCounter.textContent = `Total: ${state.previewItems.length} files | Categories: ${categoryCountMap.size}`;

  // Render Table Rows
  renderPreviewTable();

  // Enable Organize Button
  btnOrganize.disabled = state.previewItems.length === 0;

  const msg = `Preview ready: ${state.previewItems.length} file(s) found across ${categoryCountMap.size} categories. Click "Organize & Download ZIP" to proceed.`;
  setBanner(msg, "success");
}

function renderPreviewTable() {
  previewTbody.innerHTML = "";

  if (!state.previewItems.length) {
    previewTbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="6">No files scanned yet. Drag files into the box above or click "Select Files".</td>
      </tr>
    `;
    return;
  }

  // Sort by category then filename
  const sorted = [...state.previewItems].sort((a, b) => {
    if (a.category !== b.category) return a.category.localeCompare(b.category);
    return a.filename.localeCompare(b.filename);
  });

  sorted.forEach((item, index) => {
    const tr = document.createElement("tr");

    const dotIndex = item.filename.lastIndexOf(".");
    const ext = dotIndex !== -1 ? item.filename.slice(dotIndex).toLowerCase() : "";
    const icon = EXTENSION_ICONS[ext] || "📄";

    const statusBadgeClass = item.isDuplicate ? "status-badge-renamed" : "status-badge-ready";
    const statusText = item.isDuplicate ? "⚠️ Renamed" : "✔ Ready";

    tr.innerHTML = `
      <td style="text-align: center; color: var(--text-secondary);">${index + 1}</td>
      <td><strong>${icon}</strong> ${escapeHtml(item.filename)}</td>
      <td><span class="cat-badge cat-${item.category}">${item.category}</span></td>
      <td><span class="code-span">${escapeHtml(item.destinationPath)}</span></td>
      <td style="text-align: right; color: var(--text-secondary);">${formatBytes(item.size)}</td>
      <td style="text-align: center;"><span class="${statusBadgeClass}">${statusText}</span></td>
    `;

    previewTbody.appendChild(tr);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Reset Handler
function resetAll() {
  state.rawFiles = [];
  state.previewItems = [];
  fileInputMultiple.value = "";
  fileInputDirectory.value = "";
  selectedPathDisplay.textContent = "No files selected. All processing runs 100% locally in your browser.";

  statTotalFiles.textContent = "0";
  statCategories.textContent = "0";
  statTotalSize.textContent = "0 B";
  statReadyFiles.textContent = "0";
  tableSummaryCounter.textContent = "Total: 0 files | Categories: 0";

  btnScan.disabled = true;
  btnOrganize.disabled = true;
  btnReset.disabled = true;

  renderPreviewTable();
  setBanner("Ready. Select files or a folder to preview safe categorization.", "info");
}

// Organize & Download ZIP Handler
async function handleOrganizeAndDownload() {
  if (!state.previewItems.length) return;

  btnOrganize.disabled = true;
  btnScan.disabled = true;
  btnReset.disabled = true;

  const total = state.previewItems.length;
  const categoriesSet = new Set(state.previewItems.map(i => i.category));
  const distinctCategories = categoriesSet.size;

  setBanner(`Packaging ${total} file(s) into categorized ZIP archive...`, "info");

  try {
    // This writer uses classic ZIP, without ZIP64. Reject before reading large files.
    if (total + 1 > 0xFFFF || state.previewItems.some(i => i.size >= 0xFFFFFFFF) ||
        state.previewItems.reduce((sum, i) => sum + i.size, 0) >= 0xFFFFFFFF) {
      throw new Error("Selection exceeds classic ZIP limits (under 4 GiB and at most 65,534 files). Select fewer or smaller files.");
    }
    const zip = new SimpleZipBuilder();
    const manifestItems = [];

    for (let i = 0; i < state.previewItems.length; i++) {
      const item = state.previewItems[i];
      setBanner(`Adding (${i + 1}/${total}): ${item.filename}...`, "info");

      const arrayBuffer = await item.file.arrayBuffer();
      zip.addFile(item.destinationPath, arrayBuffer);

      manifestItems.push({
        filename: item.filename,
        finalName: item.finalName,
        category: item.category,
        destinationPath: item.destinationPath,
        size: item.size,
      });
    }

    // Include manifest in the ZIP archive
    const manifest = {
      app_name: "Smart File Organizer Web Edition",
      app_version: "1.2.0",
      timestamp: new Date().toISOString(),
      total_organized: total,
      categories_count: distinctCategories,
      items: manifestItems,
    };
    zip.addFile(".smart_organizer_manifest.json", JSON.stringify(manifest, null, 2));

    // Generate ZIP file
    const zipBytes = zip.generate();
    const blob = new Blob([zipBytes], { type: "application/zip" });
    const downloadUrl = URL.createObjectURL(blob);

    // Trigger download
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = "organized_files.zip";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    setTimeout(() => URL.revokeObjectURL(downloadUrl), 15000);

    const categoryWord = distinctCategories === 1 ? "category" : "categories";
    const successMsg = `Successfully organized ${total} files into ${distinctCategories} ${categoryWord}. Your ZIP archive has downloaded!`;
    setBanner(successMsg, "success");

  } catch (err) {
    console.error("Error creating ZIP:", err);
    setBanner(`Failed to create ZIP archive: ${err.message}`, "warning");
  } finally {
    btnOrganize.disabled = false;
    btnScan.disabled = false;
    btnReset.disabled = false;
  }
}

btnScan.addEventListener("click", runPreview);
btnOrganize.addEventListener("click", handleOrganizeAndDownload);
btnReset.addEventListener("click", resetAll);

// Navigation View Switching
const navButtons = document.querySelectorAll(".nav-btn");
const views = document.querySelectorAll(".content-view");

navButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    const targetTab = btn.getAttribute("data-tab");
    navButtons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    views.forEach(v => {
      if (v.id === `view-${targetTab}`) {
        v.classList.add("active");
      } else {
        v.classList.remove("active");
      }
    });
  });
});

// Populate Rules Table on Load
function populateRulesTable() {
  const rulesTbody = document.getElementById("rules-tbody");
  if (!rulesTbody) return;
  rulesTbody.innerHTML = "";

  for (const [cat, exts] of Object.entries(EXTENSION_CATEGORIES)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="cat-badge cat-${cat}">${cat}</span></td>
      <td>${exts.map(e => `<span class="code-span">${e}</span>`).join(" ")}</td>
    `;
    rulesTbody.appendChild(tr);
  }

  const trDefault = document.createElement("tr");
  trDefault.innerHTML = `
    <td><span class="cat-badge cat-Other">${DEFAULT_CATEGORY}</span></td>
    <td style="color: var(--text-secondary);">Any unrecognized extension or extensionless file format</td>
  `;
  rulesTbody.appendChild(trDefault);
}

populateRulesTable();
