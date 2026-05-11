const vscode = require("vscode");
const { exec } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

let output; // VS Code output channel for logging

function activate(context) {
  output = vscode.window.createOutputChannel("KinetiX");
  output.appendLine("KinetiX extension activated");

  const cmd = vscode.commands.registerCommand("ktx.snapshot", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor || !editor.document.fileName.endsWith(".ktx")) {
      vscode.window.showErrorMessage("Open a .ktx file first.");
      return;
    }

    const ktxPath = editor.document.fileName;
    const timeStr = await vscode.window.showInputBox({
      prompt: "Enter time (e.g. 00:05, 3.5, or 1:30)",
      placeHolder: "00:05",
    });
    if (!timeStr) return;

    const timeS = parseTime(timeStr);
    if (timeS === null) {
      vscode.window.showErrorMessage(`Invalid time: "${timeStr}". Use e.g. 00:05, 3.5, or 1:30.`);
      return;
    }

    const outPng = path.join(os.tmpdir(), `ktx_snapshot_${Date.now()}.png`);
    const script = path.join(context.extensionPath, "snapshot.py");
    const cmdLine = `python3 "${script}" "${ktxPath}" ${timeS} "${outPng}"`;

    output.appendLine(`Running: ${cmdLine}`);
    output.show(true);

    vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Rendering frame…" },
      () =>
        new Promise((resolve, reject) => {
          exec(cmdLine, { timeout: 120000, encoding: "utf8" }, (err, stdout, stderr) => {
            output.appendLine(`stdout: ${stdout || "(empty)"}`);
            if (stderr) output.appendLine(`stderr: ${stderr}`);

            if (err) {
              const msg = (stderr || "") || (stdout || "") || err.message;
              output.appendLine(`FAILED: ${msg.trim()}`);
              vscode.window.showErrorMessage(`Snapshot failed: ${msg.trim().split("\n")[0]}`);
              reject(err);
              return;
            }

            if (!fs.existsSync(outPng)) {
              output.appendLine(`PNG not found: ${outPng}`);
              vscode.window.showErrorMessage(`Snapshot PNG not found. Check KinetiX output panel.`);
              reject(new Error("no output"));
              return;
            }

            output.appendLine(`OK → ${outPng}`);
            showSnapshot(outPng, timeStr, ktxPath, context);
            resolve();
          });
        })
    );
  });

  context.subscriptions.push(cmd);
}

function parseTime(raw) {
  raw = raw.trim();
  const m = raw.match(/^(\d{1,2}):(\d{2})$/);
  if (m) return parseInt(m[1]) * 60 + parseInt(m[2]);
  const f = parseFloat(raw);
  if (!isNaN(f) && f >= 0) return f;
  return null;
}

function showSnapshot(pngPath, timeLabel, ktxPath, context) {
  const panel = vscode.window.createWebviewPanel(
    "ktxSnapshot",
    `Snapshot ${timeLabel} — ${path.basename(ktxPath)}`,
    vscode.ViewColumn.Beside,
    { enableScripts: false }
  );

  const buf = fs.readFileSync(pngPath);
  const base64 = buf.toString("base64");
  const dataUri = `data:image/png;base64,${base64}`;

  panel.webview.html = `<!DOCTYPE html>
<html>
<head><style>
  body { margin: 0; background: #0d0d18; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
  img { max-width: 100%; max-height: 100vh; object-fit: contain; box-shadow: 0 0 40px rgba(0,0,0,0.6); }
</style></head>
<body><img src="${dataUri}" /></body>
</html>`;

  panel.onDidDispose(() => {
    try { fs.unlinkSync(pngPath); } catch (_) {}
  });
}

function deactivate() {
  if (output) output.dispose();
}

module.exports = { activate, deactivate };
