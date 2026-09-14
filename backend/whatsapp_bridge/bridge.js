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
} = require("@whiskeysockets/baileys");

const app = express();
app.use(express.json());

const PORT = process.env.WA_PORT || 8001;
const AUTH_DIR = path.join(__dirname, "auth_info_baileys");

// Ensure auth dir exists
if (!fs.existsSync(AUTH_DIR)) {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
}

let sock = null;
let connectionStatus = "disconnected"; // "disconnected" | "connecting" | "connected"
let currentQrDataUrl = null;
let currentQrRaw = null;
let userAccountInfo = null; // { id, name, phone }
const recentMessages = []; // In-memory buffer of recent incoming messages

const logger = pino({ level: "error" }); // Quiet logger for clean terminal

async function startSock() {
  connectionStatus = "connecting";
  currentQrDataUrl = null;
  currentQrRaw = null;

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
        const userName = sock.user?.name || "Pengguna";

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
            const senderPhone = senderJid.split("@")[0];
            const pushName = msg.pushName || (isGroup ? "Grup WhatsApp" : "Kontak");
            
            // Extract text message content
            let text = "";
            if (msg.message.conversation) {
              text = msg.message.conversation;
            } else if (msg.message.extendedTextMessage?.text) {
              text = msg.message.extendedTextMessage.text;
            } else if (msg.message.imageMessage?.caption) {
              text = `[Foto] ${msg.message.imageMessage.caption}`;
            } else if (msg.message.videoMessage?.caption) {
              text = `[Video] ${msg.message.videoMessage.caption}`;
            } else if (msg.message.audioMessage) {
              text = "[Pesan Suara / Voice Note]";
            } else if (msg.message.documentMessage) {
              text = `[Dokumen] ${msg.message.documentMessage.fileName || ""}`;
            }

            if (text) {
              const msgObj = {
                id: msg.key.id,
                sender: pushName,
                phone: senderPhone,
                jid: senderJid,
                isGroup,
                text,
                timestamp: msg.messageTimestamp ? Number(msg.messageTimestamp) * 1000 : Date.now(),
                unread: true,
              };

              recentMessages.unshift(msgObj);
              if (recentMessages.length > 50) {
                recentMessages.pop();
              }

              console.log(`[WABridge Incoming] From ${pushName} (${senderPhone}): "${text.substring(0, 60)}"`);
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
  res.json({
    status: connectionStatus,
    has_qr: Boolean(currentQrDataUrl),
    user: userAccountInfo,
    recent_messages_count: recentMessages.length,
    unread_count: recentMessages.filter((m) => m.unread).length,
  });
});

// QR Code endpoint
app.get("/qr", (req, res) => {
  if (connectionStatus === "connected") {
    return res.json({ status: "connected", qr_data_url: null, message: "WhatsApp sudah terhubung." });
  }
  res.json({
    status: connectionStatus,
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
    res.json({ status: "ok", message: "Sesi WhatsApp berhasil dihapus." });
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
    return res.status(400).json({ status: "error", message: "WhatsApp belum terhubung. Silakan scan QR code terlebih dahulu." });
  }

  const { to, message } = req.body;
  if (!to || !message) {
    return res.status(400).json({ status: "error", message: "Parameter 'to' dan 'message' wajib diisi." });
  }

  let cleanTo = String(to).replace(/[^0-9]/g, "");
  // If starts with 08..., convert to 628...
  if (cleanTo.startsWith("08")) {
    cleanTo = "628" + cleanTo.substring(2);
  } else if (cleanTo.startsWith("8")) {
    cleanTo = "628" + cleanTo.substring(1);
  }

  const jid = cleanTo.includes("@") ? cleanTo : `${cleanTo}@s.whatsapp.net`;

  try {
    const sent = await sock.sendMessage(jid, { text: String(message) });
    console.log(`[WABridge Outgoing] Sent to ${cleanTo}: "${String(message).substring(0, 60)}"`);
    res.json({
      status: "ok",
      id: sent.key.id,
      recipient: cleanTo,
      message,
    });
  } catch (err) {
    console.error(`[WABridge Send Error] Failed to send to ${cleanTo}:`, err);
    res.status(500).json({ status: "error", message: err.message });
  }
});

// Start Baileys socket and Express server
app.listen(PORT, () => {
  console.log(`[WABridge] WhatsApp local bridge running on http://localhost:${PORT}`);
  startSock();
});
