const express = require("express");
const http = require("http");
const pino = require("pino");
const QRCode = require("qrcode");
const path = require("path");
const fs = require("fs");
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  downloadMediaMessage,
} = require("@whiskeysockets/baileys");

const app = express();
app.use(express.json());

const PORT = process.env.WA_PORT || 8001;
const AUTH_DIR = path.join(__dirname, "auth_info_baileys");

// Ensure auth dir exists
if (!fs.existsSync(AUTH_DIR)) {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
}

// Staging directory for downloaded incoming WhatsApp media
const localAppData =
  process.env.LOCALAPPDATA ||
  (process.platform === "win32"
    ? path.join(process.env.USERPROFILE || "", "AppData", "Local")
    : path.join(process.env.HOME || "", ".anara"));
const WA_STAGING_DIR = path.join(localAppData, "anara", "staging", "whatsapp_uploads");
if (!fs.existsSync(WA_STAGING_DIR)) {
  fs.mkdirSync(WA_STAGING_DIR, { recursive: true });
}

let sock = null;
let connectionStatus = "disconnected"; // "disconnected" | "connecting" | "connected"
let currentQrDataUrl = null;
let currentQrRaw = null;
let userAccountInfo = null; // { id, name, phone }
const recentMessages = []; // In-memory buffer of recent incoming messages

const logger = pino({ level: "error" }); // Quiet logger for clean terminal

async function downloadBaileysMedia(targetMessage) {
  try {
    const buffer = await downloadMediaMessage(
      targetMessage,
      "buffer",
      {},
      {
        logger: pino({ level: "silent" }),
        reuploadRequest: sock ? sock.updateMediaMessage : undefined,
      }
    );
    if (buffer && buffer.length > 0) {
      return buffer;
    }
  } catch (err) {
    console.warn("[WABridge] Media download warning:", err.message);
  }
  return null;
}

async function startSock() {
  connectionStatus = "connecting";
  currentQrDataUrl = null;
  currentQrRaw = null;

  // Clean up previous socket if reconnecting to prevent listener memory leak
  if (sock) {
    try {
      sock.ev.removeAllListeners();
      sock.end();
    } catch (e) {}
    sock = null;
  }

  try {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
      version,
      logger,
      printQRInTerminal: false,
      auth: state,
      browser: ["Anara AI Assistant", "Chrome", "1.0.0"],
      syncFullHistory: false,
    });

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("connection.update", async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        currentQrRaw = qr;
        try {
          currentQrDataUrl = await QRCode.toDataURL(qr, {
            margin: 2,
            scale: 8,
            color: {
              dark: "#000000",
              light: "#FFFFFF",
            },
          });
          console.log("[WABridge] New QR Code generated ready for scanning.");
        } catch (qrErr) {
          console.error("[WABridge] Failed to generate QR data URL:", qrErr);
        }
      }

      if (connection === "close") {
        const shouldReconnect =
          lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
        connectionStatus = "disconnected";
        userAccountInfo = null;
        currentQrDataUrl = null;
        currentQrRaw = null;

        console.log(`[WABridge] Connection closed (reconnect=${shouldReconnect}):`, lastDisconnect?.error?.message);

        if (shouldReconnect) {
          setTimeout(startSock, 3000);
        }
      } else if (connection === "open") {
        connectionStatus = "connected";
        currentQrDataUrl = null;
        currentQrRaw = null;

        const userJid = sock.user?.id || "";
        const cleanPhone = userJid.split(":")[0].replace("@s.whatsapp.net", "");
        const userName = sock.user?.name || "User";

        userAccountInfo = {
          jid: userJid,
          phone: cleanPhone,
          name: userName,
        };

        console.log(`[WABridge] Connected successfully as ${userName} (+${cleanPhone})`);
      }
    });

    // Listen to incoming messages
    sock.ev.on("messages.upsert", async (m) => {
      if (m.type === "notify") {
        for (const msg of m.messages) {
          if (!msg.key.fromMe && msg.message) {
            const senderJid = msg.key.remoteJid || "";
            const isGroup = senderJid.endsWith("@g.us");
            const participantJid = isGroup ? (msg.key.participant || msg.participant || senderJid) : senderJid;
            const participantPhone = participantJid.split("@")[0].split(":")[0];
            const senderPhone = isGroup ? participantPhone : senderJid.split("@")[0];
            const pushName = msg.pushName || (isGroup ? "Anggota WhatsApp" : "Kontak");
            
            // Extract text and media content
            let text = "";
            let mediaType = null;
            let mimeType = null;
            let fileName = null;
            let localPath = null;
            let fileSize = null;

            const msgIdSafe = (msg.key.id || String(Date.now())).replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 12);
            const ts = Date.now();

            if (msg.message.conversation) {
              text = msg.message.conversation;
            } else if (msg.message.extendedTextMessage?.text) {
              text = msg.message.extendedTextMessage.text;
            } else if (msg.message.imageMessage) {
              mediaType = "photo";
              mimeType = msg.message.imageMessage.mimetype || "image/jpeg";
              fileName = `photo_${ts}_${msgIdSafe}.jpg`;
              const cap = (msg.message.imageMessage.caption || "").trim();
              text = cap ? `[Foto] ${cap}` : `[Foto terlampir]`;
            } else if (msg.message.videoMessage) {
              mediaType = "video";
              mimeType = msg.message.videoMessage.mimetype || "video/mp4";
              fileName = `video_${ts}_${msgIdSafe}.mp4`;
              const cap = (msg.message.videoMessage.caption || "").trim();
              text = cap ? `[Video] ${cap}` : `[Video terlampir]`;
            } else if (msg.message.audioMessage) {
              mediaType = "audio";
              mimeType = msg.message.audioMessage.mimetype || "audio/ogg";
              fileName = `voice_${ts}_${msgIdSafe}.ogg`;
              text = "[Pesan Suara / Voice Note]";
            } else if (msg.message.documentMessage) {
              mediaType = "document";
              mimeType = msg.message.documentMessage.mimetype || "application/octet-stream";
              fileName = msg.message.documentMessage.fileName || `doc_${ts}_${msgIdSafe}.bin`;
              const cap = (msg.message.documentMessage.caption || "").trim();
              text = cap ? `[Dokumen: ${fileName}] ${cap}` : `[Dokumen: ${fileName}]`;
            }

            // If incoming message has media, download binary file to staging directory
            if (mediaType) {
              const mediaBuf = await downloadBaileysMedia(msg);
              if (mediaBuf) {
                const targetDiskPath = path.join(WA_STAGING_DIR, fileName);
                try {
                  fs.writeFileSync(targetDiskPath, mediaBuf);
                  localPath = targetDiskPath;
                  fileSize = mediaBuf.length;
                  console.log(`[WABridge] Downloaded ${mediaType} attachment: ${targetDiskPath} (${(fileSize / 1024).toFixed(1)} KB)`);
                } catch (writeErr) {
                  console.warn(`[WABridge] Failed saving ${fileName}:`, writeErr.message);
                }
              }
            }

            // Extract Quoted / Reply-To Message Context from Baileys
            let quotedText = "";
            let quotedSender = "";
            let quotedLocalPath = null;
            let quotedMediaType = null;
            const contextInfo = msg.message.extendedTextMessage?.contextInfo ||
                                msg.message.imageMessage?.contextInfo ||
                                msg.message.videoMessage?.contextInfo ||
                                msg.message.documentMessage?.contextInfo;

            if (contextInfo && contextInfo.quotedMessage) {
              const qMsg = contextInfo.quotedMessage;
              let qMediaNode = null;
              let qFileName = `quoted_${ts}_${(contextInfo.stanzaId || "msg").slice(0, 8)}`;

              if (qMsg.conversation) {
                quotedText = qMsg.conversation;
              } else if (qMsg.extendedTextMessage?.text) {
                quotedText = qMsg.extendedTextMessage.text;
              } else if (qMsg.imageMessage) {
                quotedMediaType = "photo";
                qFileName += ".jpg";
                quotedText = qMsg.imageMessage.caption ? `[Foto] ${qMsg.imageMessage.caption}` : `[Foto terlampir]`;
                qMediaNode = qMsg;
              } else if (qMsg.videoMessage) {
                quotedMediaType = "video";
                qFileName += ".mp4";
                quotedText = qMsg.videoMessage.caption ? `[Video] ${qMsg.videoMessage.caption}` : `[Video terlampir]`;
                qMediaNode = qMsg;
              } else if (qMsg.audioMessage) {
                quotedMediaType = "audio";
                qFileName += ".ogg";
                quotedText = "[Pesan Suara / Voice Note]";
                qMediaNode = qMsg;
              } else if (qMsg.documentMessage) {
                quotedMediaType = "document";
                const qDocName = qMsg.documentMessage.fileName || `${qFileName}.bin`;
                qFileName = qDocName;
                quotedText = `[Dokumen: ${qDocName}]`;
                qMediaNode = qMsg;
              }

              const qParticipant = contextInfo.participant || "";
              quotedSender = qParticipant.split("@")[0] || "User";

              // Attempt downloading quoted media attachment if present
              if (qMediaNode) {
                const fakeQuotedMsg = {
                  key: {
                    remoteJid: senderJid,
                    id: contextInfo.stanzaId,
                    participant: contextInfo.participant,
                  },
                  message: qMsg,
                };
                const qBuf = await downloadBaileysMedia(fakeQuotedMsg);
                if (qBuf) {
                  const qDiskPath = path.join(WA_STAGING_DIR, qFileName);
                  try {
                    fs.writeFileSync(qDiskPath, qBuf);
                    quotedLocalPath = qDiskPath;
                    console.log(`[WABridge] Downloaded quoted ${quotedMediaType} attachment: ${qDiskPath}`);
                  } catch (qWriteErr) {
                    console.warn(`[WABridge] Failed saving quoted media ${qFileName}:`, qWriteErr.message);
                  }
                }
              }
            }

            if (text || localPath) {
              const msgObj = {
                id: msg.key.id,
                sender: pushName,
                phone: senderPhone,
                participant: participantPhone,
                jid: senderJid,
                isGroup,
                text: text || `[${(mediaType || "file").toUpperCase()} ATTACHED]`,
                localPath: localPath || undefined,
                fileName: fileName || undefined,
                mediaType: mediaType || undefined,
                mimeType: mimeType || undefined,
                fileSize: fileSize || undefined,
                quotedText: quotedText || undefined,
                quotedSender: quotedSender || undefined,
                quotedLocalPath: quotedLocalPath || undefined,
                quotedMediaType: quotedMediaType || undefined,
                timestamp: msg.messageTimestamp ? Number(msg.messageTimestamp) * 1000 : Date.now(),
                unread: true,
              };

              recentMessages.unshift(msgObj);
              if (recentMessages.length > 50) {
                recentMessages.pop();
              }

              console.log(`[WABridge Incoming] From ${pushName} (${senderPhone}): "${text.substring(0, 60)}" [media: ${mediaType || "none"}]`);
              forwardToAnara(msgObj);
            }
          }
        }
      }
    });
  } catch (err) {
    console.error("[WABridge] Error initializing socket:", err);
    connectionStatus = "disconnected";
    setTimeout(startSock, 5000);
  }
}

// Helper: forwards inbound message to Anara Backend Webhook
function forwardToAnara(msgObj) {
  try {
    const payload = JSON.stringify(msgObj);
    const req = http.request(
      {
        hostname: "localhost",
        port: 8000,
        path: "/api/integrations/whatsapp/webhook",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(payload),
        },
      },
      (res) => {
        // Response ignored
      }
    );
    req.on("error", () => {
      // Backend not yet ready or offline
    });
    req.write(payload);
    req.end();
  } catch (err) {
    // Non-blocking
  }
}

// ── REST API Endpoints ──────────────────────────────────────────

// Status endpoint
app.get("/status", (req, res) => {
  const reportedStatus = userAccountInfo ? connectionStatus : "disconnected";
  res.json({
    status: reportedStatus,
    raw_status: connectionStatus,
    has_qr: Boolean(currentQrDataUrl),
    user: userAccountInfo,
    recent_messages_count: recentMessages.length,
    unread_count: recentMessages.filter((m) => m.unread).length,
  });
});

// QR Code endpoint
app.get("/qr", (req, res) => {
  if (connectionStatus === "connected" && userAccountInfo) {
    return res.json({ status: "connected", qr_data_url: null, user: userAccountInfo, message: "WhatsApp is already connected." });
  }
  res.json({
    status: userAccountInfo ? connectionStatus : "disconnected",
    has_qr: Boolean(currentQrDataUrl),
    qr_data_url: currentQrDataUrl,
    raw_qr: currentQrRaw,
  });
});

// Logout / Reset session
app.post("/logout", async (req, res) => {
  try {
    connectionStatus = "disconnected";
    userAccountInfo = null;
    currentQrDataUrl = null;
    currentQrRaw = null;

    if (sock) {
      try {
        await sock.logout();
      } catch (e) {}
    }

    if (fs.existsSync(AUTH_DIR)) {
      fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    }

    setTimeout(startSock, 1000);
    res.json({ status: "ok", message: "WhatsApp session cleared successfully." });
  } catch (err) {
    res.status(500).json({ status: "error", message: err.message });
  }
});

// Get recent / unread messages
app.get("/messages", (req, res) => {
  const unreadOnly = req.query.unread_only === "true";
  const limit = parseInt(req.query.limit || "10", 10);
  
  let msgs = recentMessages;
  if (unreadOnly) {
    msgs = msgs.filter((m) => m.unread);
  }
  
  const result = msgs.slice(0, limit);
  // Mark as read in local buffer
  if (req.query.mark_read === "true") {
    result.forEach((m) => {
      m.unread = false;
    });
  }

  res.json({
    status: "ok",
    total: result.length,
    messages: result,
  });
});

// Send message
app.post("/send", async (req, res) => {
  if (connectionStatus !== "connected" || !sock) {
    return res.status(400).json({ status: "error", message: "WhatsApp is not connected. Please scan QR code first." });
  }

  const { to, message } = req.body;
  if (!to || !message) {
    return res.status(400).json({ status: "error", message: "Parameters 'to' and 'message' are required." });
  }

  const rawTo = String(to).trim();
  let jid;
  if (rawTo.endsWith("@g.us") || rawTo.endsWith("@s.whatsapp.net")) {
    jid = rawTo;
  } else {
    let cleanTo = rawTo.replace(/[^0-9]/g, "");
    if (cleanTo.startsWith("08")) {
      cleanTo = "628" + cleanTo.substring(2);
    } else if (cleanTo.startsWith("8")) {
      cleanTo = "628" + cleanTo.substring(1);
    }
    jid = `${cleanTo}@s.whatsapp.net`;
  }

  try {
    const sent = await sock.sendMessage(jid, { text: String(message) });
    console.log(`[WABridge Outgoing] Sent to ${jid}: "${String(message).substring(0, 60)}"`);
    res.json({
      status: "ok",
      id: sent.key.id,
      recipient: jid,
      message,
    });
  } catch (err) {
    console.error(`[WABridge Send Error] Failed to send to ${jid}:`, err);
    res.status(500).json({ status: "error", message: err.message });
  }
});

// Send document file (PDF, DOCX, ZIP, etc.)
app.post("/send-document", async (req, res) => {
  if (connectionStatus !== "connected" || !sock) {
    return res.status(400).json({ status: "error", message: "WhatsApp is not connected. Please scan QR code first." });
  }

  const { to, file_path, caption, filename } = req.body;
  if (!to || !file_path) {
    return res.status(400).json({ status: "error", message: "Parameters 'to' and 'file_path' are required." });
  }

  const resolvedPath = path.resolve(file_path);
  if (!fs.existsSync(resolvedPath)) {
    return res.status(404).json({ status: "error", message: `File not found: ${resolvedPath}` });
  }

  const rawToDoc = String(to).trim();
  let jid;
  if (rawToDoc.endsWith("@g.us") || rawToDoc.endsWith("@s.whatsapp.net")) {
    jid = rawToDoc;
  } else {
    let cleanTo = rawToDoc.replace(/[^0-9]/g, "");
    if (cleanTo.startsWith("08")) {
      cleanTo = "628" + cleanTo.substring(2);
    } else if (cleanTo.startsWith("8")) {
      cleanTo = "628" + cleanTo.substring(1);
    }
    jid = `${cleanTo}@s.whatsapp.net`;
  }

  try {
    const fileBuffer = fs.readFileSync(resolvedPath);
    const baseName = filename || path.basename(resolvedPath);
    const ext = path.extname(resolvedPath).toLowerCase();

    let mimeType = "application/octet-stream";
    if (ext === ".pdf") mimeType = "application/pdf";
    else if (ext === ".docx") mimeType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    else if (ext === ".doc") mimeType = "application/msword";
    else if (ext === ".zip") mimeType = "application/zip";
    else if (ext === ".csv") mimeType = "text/csv";
    else if (ext === ".txt") mimeType = "text/plain";
    else if (ext === ".json") mimeType = "application/json";
    else if (ext === ".png") mimeType = "image/png";
    else if (ext === ".jpg" || ext === ".jpeg") mimeType = "image/jpeg";

    const sent = await sock.sendMessage(jid, {
      document: fileBuffer,
      mimetype: mimeType,
      fileName: baseName,
      caption: caption || baseName,
    });

    console.log(`[WABridge Outgoing Document] Sent '${baseName}' to ${jid}`);
    res.json({
      status: "ok",
      id: sent.key.id,
      recipient: jid,
      filename: baseName,
      file_path: resolvedPath,
    });
  } catch (err) {
    console.error(`[WABridge Send Document Error]:`, err);
    res.status(500).json({ status: "error", message: err.message });
  }
});

// Start Baileys socket and Express server
app.listen(PORT, () => {
  console.log(`[WABridge] WhatsApp local bridge running on http://localhost:${PORT}`);
  startSock();
});
