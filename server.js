#!/usr/bin/env node
require("dotenv").config();

const express = require("express");
const multer = require("multer");
const os = require("os");
const path = require("path");
const fs = require("fs/promises");
const { spawn } = require("child_process");

const app = express();
const PORT = parseInt(process.env.PORT || "3200", 10);
const upload = multer({ dest: path.join(os.tmpdir(), "wm-") });

async function safeUnlink(p) {
  try {
    if (p) await fs.unlink(p);
  } catch {}
}

function resolvePythonBin() {
  // Windows: PY_BIN=C:\Python312\python.exe
  // Ubuntu:  PY_BIN=python3
  if (process.env.PY_BIN && process.env.PY_BIN.trim()) {
    return process.env.PY_BIN.trim().replace(/^"(.*)"$/, "$1");
  }
  return os.platform() === "win32" ? "python" : "python3";
}

app.post("/watermark/lunas", upload.single("file"), async (req, res) => {
  const inputPath = req.file?.path;
  if (!inputPath) {
    return res.status(400).json({ ok: false, error: "No file uploaded (field name must be 'file')." });
  }

  const outPath = path.join(os.tmpdir(), `wm-${Date.now()}.pdf`);

  // ✅ DEFAULT DI SERVER (user tidak kirim apa-apa)
  // Boleh kamu tweak nilainya, tapi request tetap hanya file.
  const options = {
    text: "LUNAS",
    rotate: -20,
    opacity: 0.18,
    wmWidthPctOfContent: 0.40,     // ✅ 10% ukuran konten
    shiftXPctOfContent: 0.065,     // ✅ geser kanan dikit
    shiftYPctOfContent: -0.020,     // ✅ geser bawah dikit
  };

  const py = resolvePythonBin();
  const scriptPath = path.join(__dirname, "tools", "watermark_lunas.py");

  const args = [
    scriptPath,
    "--input", inputPath,
    "--output", outPath,
    "--options", JSON.stringify(options),
  ];

  const child = spawn(py, args, { stdio: ["ignore", "pipe", "pipe"] });

  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (d) => (stdout += d.toString()));
  child.stderr.on("data", (d) => (stderr += d.toString()));

  child.on("close", async (code) => {
    await safeUnlink(inputPath);

    if (code !== 0) {
      await safeUnlink(outPath);
      return res.status(500).json({
        ok: false,
        error: "Watermark failed",
        detail: stderr || `exit code ${code}`,
        stdout,
        hint: "Jika curl pakai -o output.pdf, pastikan pakai -f agar error JSON tidak tersimpan jadi file PDF.",
      });
    }

    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", 'attachment; filename="invoice-LUNAS.pdf"');

    res.sendFile(outPath, async (err) => {
      await safeUnlink(outPath);
      if (err) console.error(err);
    });
  });
});

app.get("/health", (req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`API running on http://localhost:${PORT}`);
});
