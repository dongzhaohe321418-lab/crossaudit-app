import AppKit
import Darwin
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate,
                         WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate,
                         WKScriptMessageHandler {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var core: Process?
    private var stdoutBuffer = Data()
    private var loadedURL = false
    private var logHandle: FileHandle?
    private var terminationSignals: [DispatchSourceSignal] = []
    private var statusItem: NSStatusItem?
    private var backgroundStatusItem: NSMenuItem?
    private var isTerminating = false
    private var logURL: URL?

    // UI_DESIGN_SPEC.md §1.1 dark `--bg` (#0C0F14). Shared by the native
    // window, the WebView underlay and the inline loading/failure screens so
    // the shell and the page read as one continuous dark surface.
    private static let backdrop = NSColor(
        srgbRed: 0x0C / 255.0, green: 0x0F / 255.0, blue: 0x14 / 255.0, alpha: 1)

    func applicationDidFinishLaunching(_ notification: Notification) {
        installTerminationHandlers()
        buildMenus()
        buildStatusMenu()
        buildWindow()
        launchCore()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { showMainWindow() }
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        isTerminating = true
        if let process = core, process.isRunning {
            process.terminate()
            process.waitUntilExit()
        }
        try? logHandle?.close()
    }

    private func installTerminationHandlers() {
        for value in [SIGINT, SIGTERM] {
            signal(value, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: value, queue: .main)
            source.setEventHandler { NSApp.terminate(nil) }
            source.resume()
            terminationSignals.append(source)
        }
    }

    private func buildWindow() {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.userContentController.add(self, name: "crossaudit")
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsMagnification = true

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1240, height: 800),
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered, defer: false)
        // The page draws its own identity in the top bar, so the native title
        // would duplicate it. window.title stays set for Mission Control, the
        // Window menu and accessibility; only the drawn text is hidden. With
        // .fullSizeContentView and a transparent titlebar the dark page runs
        // edge to edge behind the traffic lights.
        window.title = "CrossAudit"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.tabbingMode = .disallowed
        // Paint the backdrop natively so no white frame flashes before the
        // WebView commits its first (loading-screen) paint, and overscroll
        // rubber-banding reveals the same dark base as the page.
        window.backgroundColor = Self.backdrop
        webView.underPageBackgroundColor = Self.backdrop
        window.minSize = NSSize(width: 760, height: 560)
        window.contentView = webView
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.setFrameAutosaveName("CrossAuditMainWindow")
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        showLoading("Starting the supervised workspace…")
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        // Closing the workspace is deliberately different from quitting the
        // application. The local core and every detached Project worker remain
        // alive; the Dock icon or menu-bar item restores the same WebView.
        sender.orderOut(nil)
        backgroundStatusItem?.title = "Running in background"
        return false
    }

    private func buildMenus() {
        let main = NSMenu()
        NSApp.mainMenu = main

        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        appMenu.addItem(withTitle: "About CrossAudit", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        let settings = NSMenuItem(title: "Settings…", action: #selector(openSettings(_:)), keyEquivalent: ",")
        settings.target = self
        appMenu.addItem(settings)
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Hide CrossAudit", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let hideOthers = NSMenuItem(title: "Hide Others",
                                    action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(hideOthers)
        appMenu.addItem(withTitle: "Show All", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit CrossAudit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")

        let fileItem = NSMenuItem()
        main.addItem(fileItem)
        let fileMenu = NSMenu(title: "File")
        fileItem.submenu = fileMenu
        let newTask = NSMenuItem(title: "New Task", action: #selector(openNewTask(_:)), keyEquivalent: "n")
        newTask.target = self
        fileMenu.addItem(newTask)
        let projects = NSMenuItem(title: "Show Projects", action: #selector(showProjects(_:)), keyEquivalent: "p")
        projects.keyEquivalentModifierMask = [.command, .shift]
        projects.target = self
        fileMenu.addItem(projects)
        fileMenu.addItem(.separator())
        fileMenu.addItem(withTitle: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")

        // WKWebView participates in AppKit's responder chain, but editing key
        // equivalents are dispatched through the main menu. A programmatic app
        // without this standard Edit menu silently drops Command-V (including
        // in password inputs), Command-C, Command-X and Command-A. Keep targets
        // nil so AppKit sends every action to the focused DOM field rather than
        // giving the native shell access to clipboard or secret contents.
        let editItem = NSMenuItem()
        main.addItem(editItem)
        let editMenu = NSMenu(title: "Edit")
        editItem.submenu = editMenu
        editMenu.addItem(withTitle: "Undo", action: Selector(("undo:")), keyEquivalent: "z")
        let redo = NSMenuItem(title: "Redo", action: Selector(("redo:")), keyEquivalent: "z")
        redo.keyEquivalentModifierMask = [.command, .shift]
        editMenu.addItem(redo)
        editMenu.addItem(.separator())
        editMenu.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(.separator())
        editMenu.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")

        let viewItem = NSMenuItem()
        main.addItem(viewItem)
        let viewMenu = NSMenu(title: "View")
        viewItem.submenu = viewMenu
        let reload = NSMenuItem(title: "Reload", action: #selector(reload(_:)), keyEquivalent: "r")
        reload.target = self
        viewMenu.addItem(reload)
        // Control-Command-F is the system-wide full screen shortcut; a bare
        // Command-F here would shadow the page's find affordance.
        let fullScreen = NSMenuItem(title: "Enter Full Screen",
                                    action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        fullScreen.keyEquivalentModifierMask = [.command, .control]
        viewMenu.addItem(fullScreen)

        let windowItem = NSMenuItem()
        main.addItem(windowItem)
        let windowMenu = NSMenu(title: "Window")
        windowItem.submenu = windowMenu
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        windowMenu.addItem(.separator())
        windowMenu.addItem(withTitle: "Bring All to Front", action: #selector(NSApplication.arrangeInFront(_:)), keyEquivalent: "")
        NSApp.windowsMenu = windowMenu
    }

    private func buildStatusMenu() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = item.button {
            let image = NSImage(systemSymbolName: "diamond", accessibilityDescription: "CrossAudit")
            image?.isTemplate = true
            button.image = image
            button.toolTip = "CrossAudit is running"
        }

        let menu = NSMenu(title: "CrossAudit")
        let open = NSMenuItem(title: "Open CrossAudit", action: #selector(showMainWindow(_:)), keyEquivalent: "")
        open.target = self
        menu.addItem(open)
        let projects = NSMenuItem(title: "Show Projects", action: #selector(showProjects(_:)), keyEquivalent: "")
        projects.target = self
        menu.addItem(projects)
        menu.addItem(.separator())
        let state = NSMenuItem(title: "Running in background", action: nil, keyEquivalent: "")
        state.isEnabled = false
        menu.addItem(state)
        backgroundStatusItem = state
        menu.addItem(.separator())
        let quit = NSMenuItem(title: "Quit CrossAudit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        quit.target = NSApp
        menu.addItem(quit)
        item.menu = menu
        statusItem = item
    }

    private func launchCore() {
        guard let resources = Bundle.main.resourceURL else {
            showFailure("The application resource directory is missing.")
            return
        }
        let executable = resources.appendingPathComponent("core/CrossAuditCore")
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            showFailure("The CrossAudit core executable is missing or not executable.")
            return
        }
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("CrossAudit", isDirectory: true)
        try? FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
        let logURL = support.appendingPathComponent("CrossAudit.log")
        self.logURL = logURL
        rotateLogIfNeeded(logURL)
        _ = FileManager.default.createFile(atPath: logURL.path, contents: nil)
        logHandle = try? FileHandle(forWritingTo: logURL)
        _ = try? logHandle?.seekToEnd()

        let process = Process()
        process.executableURL = executable
        process.currentDirectoryURL = support
        var environment = ProcessInfo.processInfo.environment
        let bundledGH = resources.appendingPathComponent("bin/gh")
        let bundledCodex = resources.appendingPathComponent("bin/codex")
        if FileManager.default.isExecutableFile(atPath: bundledGH.path) {
            environment["CROSSAUDIT_BUNDLED_GH"] = bundledGH.path
        }
        if FileManager.default.isExecutableFile(atPath: bundledCodex.path) {
            environment["CROSSAUDIT_BUNDLED_CODEX"] = bundledCodex.path
        }
        environment["PATH"] = resources.appendingPathComponent("bin").path + ":" + (environment["PATH"] ?? "/usr/bin:/bin")
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment
        let output = Pipe()
        process.standardOutput = output
        process.standardError = logHandle
        output.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            self?.consumeCoreOutput(data)
        }
        process.terminationHandler = { [weak self] process in
            DispatchQueue.main.async {
                guard let self, !self.isTerminating else { return }
                if self.core === process { self.core = nil }
                self.loadedURL = false
                self.backgroundStatusItem?.title = "Background core stopped"
                self.statusItem?.button?.toolTip = "CrossAudit needs attention"
                self.showFailure("CrossAudit core stopped unexpectedly (exit \(process.terminationStatus)). See ~/Library/Application Support/CrossAudit/CrossAudit.log.")
                self.showMainWindow()
                NSApp.requestUserAttention(.criticalRequest)
            }
        }
        do {
            try process.run()
            core = process
            DispatchQueue.main.asyncAfter(deadline: .now() + 20) { [weak self, weak process] in
                guard let self, let process, self.core === process,
                      process.isRunning, !self.loadedURL else { return }
                process.terminate()
                self.showFailure("The local core did not become ready within 20 seconds. Retry, or open the diagnostic log for details.")
            }
        } catch {
            showFailure("CrossAudit could not launch its core: \(error.localizedDescription)")
        }
    }

    private func rotateLogIfNeeded(_ url: URL) {
        guard let size = try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize,
              size > 5 * 1024 * 1024 else { return }
        let previous = url.appendingPathExtension("1")
        try? FileManager.default.removeItem(at: previous)
        try? FileManager.default.moveItem(at: url, to: previous)
    }

    private func consumeCoreOutput(_ data: Data) {
        stdoutBuffer.append(data)
        while let newline = stdoutBuffer.firstIndex(of: 10) {
            let lineData = stdoutBuffer.prefix(upTo: newline)
            stdoutBuffer.removeSubrange(...newline)
            guard let line = String(data: lineData, encoding: .utf8),
                  line.hasPrefix("CROSSAUDIT_APP_URL=") else { continue }
            let raw = String(line.dropFirst("CROSSAUDIT_APP_URL=".count))
            guard let url = URL(string: raw) else { continue }
            DispatchQueue.main.async { [weak self] in
                self?.loadedURL = true
                self?.webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData))
            }
        }
    }

    // The inline screens mirror UI_DESIGN_SPEC.md §1 dark tokens (--bg
    // #0C0F14, --surface #161B23, --text #EDF0F5, --text-2 #A6AEBB, --accent
    // #6CA8F8, hairlines at rgba(228,237,248,.09/.18)) so the shell's own
    // pages are indistinguishable from the console they precede.
    private func showLoading(_ message: String) {
        webView.loadHTMLString("""
        <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
        <style>html,body{height:100%;margin:0;background:#0C0F14;color:#EDF0F5;-webkit-font-smoothing:antialiased;
        font:13px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI","PingFang SC",sans-serif;display:grid;place-items:center}
        main{text-align:center;padding:40px}
        .mark{width:44px;height:44px;border-radius:12px;margin:0 auto 20px;display:grid;place-items:center;
        font-size:20px;background:#161B23;border:1px solid rgba(228,237,248,.18)}
        h1{margin:0 0 6px;font-size:15px;font-weight:600;letter-spacing:-.01em}
        p{margin:0;color:#A6AEBB}
        .pulse{width:96px;height:2px;margin:24px auto 0;border-radius:999px;background:rgba(228,237,248,.09);overflow:hidden}
        .pulse::after{content:"";display:block;width:40%;height:100%;border-radius:999px;background:#6CA8F8;animation:sweep 1.4s ease-in-out infinite alternate}
        @keyframes sweep{from{transform:translateX(-40%)}to{transform:translateX(190%)}}
        @media(prefers-reduced-motion:reduce){.pulse::after{animation:none;width:100%;background:rgba(228,237,248,.18)}}</style>
        <main><div class=mark>◇</div><h1>CrossAudit</h1><p>\(htmlEscape(message))</p>
        <div class=pulse role=progressbar aria-label="Starting"></div></main>
        """, baseURL: nil)
    }

    private func showFailure(_ message: String) {
        webView.loadHTMLString("""
        <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
        <style>html,body{height:100%;margin:0;background:#0C0F14;color:#EDF0F5;-webkit-font-smoothing:antialiased;
        font:13px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI","PingFang SC",sans-serif;display:grid;place-items:center}
        main{max-width:560px;padding:40px 32px;text-align:center}
        h1{margin:0 0 10px;font-size:18px;font-weight:600;letter-spacing:-.015em}
        p{margin:0;font-size:14px;line-height:1.6;color:#A6AEBB}
        nav{display:flex;gap:10px;justify-content:center;margin-top:28px}
        button{font:inherit;font-weight:500;padding:8px 16px;border-radius:8px;cursor:pointer;border:1px solid transparent}
        button:active{transform:scale(.98)}
        button:focus-visible{outline:2px solid #6CA8F8;outline-offset:2px}
        .primary{background:#6CA8F8;color:#0C0F14}.primary:hover{background:#82B6F9}
        .quiet{background:transparent;color:#EDF0F5;border-color:rgba(228,237,248,.18)}
        .quiet:hover{background:rgba(148,178,224,.10)}
        @media(prefers-reduced-motion:reduce){button:active{transform:none}}</style>
        <main><h1>CrossAudit needs attention</h1><p>\(htmlEscape(message))</p><nav>
        <button class=primary onclick="send('restartCore')">Retry startup</button>
        <button class=quiet onclick="send('openDiagnosticLog')">Open diagnostic log</button>
        </nav></main><script>function send(action){window.webkit?.messageHandlers?.crossaudit?.postMessage({action})}</script>
        """, baseURL: nil)
    }

    private func htmlEscape(_ value: String) -> String {
        value.replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
    }

    private func runJavaScript(_ script: String) { webView.evaluateJavaScript(script, completionHandler: nil) }
    private func showMainWindow() {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        backgroundStatusItem?.title = core?.isRunning == true ? "Running in background" : "Background core stopped"
    }
    @objc private func showMainWindow(_ sender: Any?) { showMainWindow() }
    @objc private func openSettings(_ sender: Any?) { showMainWindow(); runJavaScript("document.getElementById('settings-open')?.click()") }
    @objc private func openNewTask(_ sender: Any?) { showMainWindow(); runJavaScript("document.getElementById('new-task')?.click()") }
    @objc private func showProjects(_ sender: Any?) { showMainWindow(); runJavaScript("document.getElementById('projects-home')?.click()") }
    @objc private func reload(_ sender: Any?) { webView.reload() }

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        guard message.name == "crossaudit", message.frameInfo.isMainFrame,
              let body = message.body as? [String: Any],
              let action = body["action"] as? String else { return }
        let origin = message.frameInfo.securityOrigin
        let local = ["127.0.0.1", "localhost"].contains(origin.host)
        let internalPage = origin.protocol == "file" || origin.protocol == "about" || origin.host.isEmpty
        guard local || internalPage else { return }
        if action == "restartCore" {
            guard core?.isRunning != true else { return }
            stdoutBuffer.removeAll(keepingCapacity: true)
            loadedURL = false
            showLoading("Restarting the supervised workspace…")
            launchCore()
            return
        }
        if action == "openDiagnosticLog" {
            if let logURL, FileManager.default.fileExists(atPath: logURL.path) {
                NSWorkspace.shared.open(logURL)
            } else if let support = logURL?.deletingLastPathComponent() {
                NSWorkspace.shared.open(support)
            }
            return
        }
        if local, action == "revealInFinder", let path = body["path"] as? String,
           !path.isEmpty, FileManager.default.fileExists(atPath: path) {
            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
            return
        }
        guard local, action == "chooseWorkspace" else { return }
        let panel = NSOpenPanel()
        panel.title = "Choose CrossAudit Workspace"
        panel.message = "New projects will be created as folders inside this location."
        panel.prompt = "Use This Folder"
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        if let current = body["current"] as? String,
           FileManager.default.fileExists(atPath: current) {
            panel.directoryURL = URL(fileURLWithPath: current, isDirectory: true)
        }
        panel.beginSheetModal(for: window) { [weak self] result in
            guard result == .OK, let url = panel.url,
                  let data = try? JSONSerialization.data(withJSONObject: ["path": url.path]),
                  let json = String(data: data, encoding: .utf8) else { return }
            self?.runJavaScript("window.crossauditWorkspaceSelected?.(\(json))")
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        let local = url.host == "127.0.0.1" || url.host == "localhost"
        if local || url.scheme == "about" {
            decisionHandler(navigationAction.shouldPerformDownload ? .download : .allow)
        } else if ["https", "http"].contains(url.scheme?.lowercased() ?? "") {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
        } else {
            decisionHandler(.cancel)
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if let http = navigationResponse.response as? HTTPURLResponse,
           (http.value(forHTTPHeaderField: "Content-Disposition") ?? "").lowercased().contains("attachment") {
            decisionHandler(.download)
        } else {
            decisionHandler(.allow)
        }
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        download.delegate = self
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        download.delegate = self
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                  suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = suggestedFilename
        panel.canCreateDirectories = true
        panel.beginSheetModal(for: window) { result in
            completionHandler(result == .OK ? panel.url : nil)
        }
    }

    func downloadDidFinish(_ download: WKDownload) { NSSound(named: "Glass")?.play() }
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        let alert = NSAlert(error: error)
        alert.beginSheetModal(for: window)
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = true
        panel.beginSheetModal(for: window) { result in
            completionHandler(result == .OK ? panel.urls : nil)
        }
    }
}

// A standalone swiftc-built AppKit executable does not have SwiftUI's implicit
// application lifecycle. Own the NSApplication and retain its delegate for the
// full run loop so applicationDidFinishLaunching always fires in an installed
// bundle, not only in development launch contexts.
let application = NSApplication.shared
let applicationDelegate = AppDelegate()
application.setActivationPolicy(.regular)
application.delegate = applicationDelegate
application.run()
