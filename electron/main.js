/**
 * DS Agent 桌面应用 — Electron 入口
 *
 * 用法:
 *   npm install
 *   npm start              # 开发模式 (先启动 Docker)
 *   npm run build          # 打包为 .exe / .dmg
 */

const { app, BrowserWindow, Menu, shell, dialog, nativeTheme } = require("electron");
const path = require("path");

const APP_URL = process.env.DSAGENT_URL || "http://127.0.0.1:8000/dashboard";
const isDev = process.env.NODE_ENV === "development";

let mainWindow;

function createWindow() {
  // 跟随系统明暗
  nativeTheme.themeSource = "system";

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    title: "DS Agent — AI 运营指挥中心",
    icon: path.join(__dirname, "icon.png"),
    backgroundColor: nativeTheme.shouldUseDarkColors ? "#06090f" : "#f5f6f8",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    // 无边框 + 自绘标题栏
    frame: true,
    titleBarStyle: "default",
  });

  mainWindow.loadURL(APP_URL);

  // 菜单
  const menuTemplate = [
    {
      label: "DS Agent",
      submenu: [
        { label: "关于", click: () => dialog.showMessageBox(mainWindow, { title: "DS Agent", message: "跨境电商 AI 运营指挥中心\nv3.1", detail: "基于 LLM + MCP + Agent 架构" }) },
        { type: "separator" },
        { label: "退出", accelerator: "CmdOrCtrl+Q", click: () => app.quit() },
      ],
    },
    {
      label: "视图",
      submenu: [
        { label: "刷新", accelerator: "CmdOrCtrl+R", click: () => mainWindow.reload() },
        { label: "全屏", accelerator: "F11", click: () => mainWindow.setFullScreen(!mainWindow.isFullScreen()) },
        { type: "separator" },
        { label: "开发者工具", accelerator: "F12", click: () => mainWindow.webContents.toggleDevTools() },
      ],
    },
    {
      label: "帮助",
      submenu: [
        { label: "API 文档", click: () => shell.openExternal("http://127.0.0.1:8000/docs") },
        { label: "GitHub", click: () => shell.openExternal("https://github.com") },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(menuTemplate));

  mainWindow.on("closed", () => { mainWindow = null; });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("activate", () => { if (!mainWindow) createWindow(); });
