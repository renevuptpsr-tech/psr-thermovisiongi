const ALLOWED_EXTENSIONS = [".xlsx", ".xlsm"];
const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024;
const MAX_CLOCK_SKEW_SECONDS = 300;

function doGet() {
  return jsonResponse_({
    ok: true,
    service: "PLN Thermovisi Google Drive Gateway",
    status: "ready"
  });
}

function authorizeDrive() {
  const folderId = PropertiesService.getScriptProperties().getProperty("TARGET_FOLDER_ID");
  if (!folderId) throw new Error("TARGET_FOLDER_ID belum dikonfigurasi.");
  return DriveApp.getFolderById(folderId).getName();
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      throw new Error("Request body kosong.");
    }
    const payload = JSON.parse(e.postData.contents);
    const properties = PropertiesService.getScriptProperties();
    const targetFolderId = properties.getProperty("TARGET_FOLDER_ID");
    const sharedSecret = properties.getProperty("UPLOAD_SHARED_SECRET");
    if (!targetFolderId || !sharedSecret) {
      throw new Error("Script Properties belum dikonfigurasi.");
    }
    validatePayload_(payload, targetFolderId, sharedSecret);

    const bytes = Utilities.base64Decode(payload.file_base64);
    if (bytes.length === 0 || bytes.length > MAX_FILE_SIZE_BYTES) {
      throw new Error("Ukuran file kosong atau melebihi batas 15 MB.");
    }
    const actualHash = bytesToHex_(
      Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes)
    );
    if (!constantTimeEqual_(actualHash, payload.file_sha256)) {
      throw new Error("Hash file tidak sesuai.");
    }

    const blob = Utilities.newBlob(bytes, payload.mime_type, payload.filename);
    const file = DriveApp.getFolderById(targetFolderId).createFile(blob);
    CacheService.getScriptCache().put("nonce:" + payload.nonce, "1", 600);
    return jsonResponse_({
      ok: true,
      drive_file_id: file.getId(),
      drive_web_view_link: file.getUrl()
    });
  } catch (error) {
    console.error(error);
    return jsonResponse_({ok: false, error: String(error.message || error)});
  }
}

function validatePayload_(payload, targetFolderId, sharedSecret) {
  const required = [
    "timestamp", "nonce", "filename", "mime_type", "folder_id",
    "file_sha256", "signature", "file_base64"
  ];
  required.forEach(function(key) {
    if (payload[key] === undefined || payload[key] === null || payload[key] === "") {
      throw new Error("Field wajib tidak tersedia: " + key);
    }
  });
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - Number(payload.timestamp)) > MAX_CLOCK_SKEW_SECONDS) {
    throw new Error("Request sudah kedaluwarsa atau waktu komputer tidak sinkron.");
  }
  if (!/^[a-f0-9]{32}$/.test(String(payload.nonce))) {
    throw new Error("Nonce tidak valid.");
  }
  if (CacheService.getScriptCache().get("nonce:" + payload.nonce)) {
    throw new Error("Request sudah pernah digunakan.");
  }
  if (String(payload.folder_id) !== String(targetFolderId)) {
    throw new Error("Folder tujuan tidak diizinkan.");
  }
  const filename = String(payload.filename);
  if (filename.includes("/") || filename.includes("\\") || filename.length > 180) {
    throw new Error("Nama file tidak valid.");
  }
  const lowerName = filename.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some(function(ext) { return lowerName.endsWith(ext); })) {
    throw new Error("Hanya file .xlsx atau .xlsm yang diizinkan.");
  }
  if (!/^[a-f0-9]{64}$/.test(String(payload.file_sha256))) {
    throw new Error("Format SHA-256 tidak valid.");
  }
  const canonical = [
    String(payload.timestamp),
    String(payload.nonce),
    filename,
    String(payload.mime_type),
    String(payload.folder_id),
    String(payload.file_sha256)
  ].join("\n");
  const expectedSignature = bytesToHex_(
    Utilities.computeHmacSha256Signature(canonical, sharedSecret)
  );
  if (!constantTimeEqual_(expectedSignature, String(payload.signature))) {
    throw new Error("Signature upload tidak valid.");
  }
}

function bytesToHex_(bytes) {
  return bytes.map(function(value) {
    const unsigned = (value + 256) % 256;
    return unsigned.toString(16).padStart(2, "0");
  }).join("");
}

function constantTimeEqual_(left, right) {
  left = String(left);
  right = String(right);
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index++) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function jsonResponse_(value) {
  return ContentService
    .createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
