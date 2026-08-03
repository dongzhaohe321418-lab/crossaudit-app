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
        window.title = "CrossAudit"
        window.titlebarAppearsTransparent = false
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

        let viewItem = NSMenuItem()
        main.addItem(viewItem)
        let viewMenu = NSMenu(title: "View")
        viewItem.submenu = viewMenu
        let reload = NSMenuItem(title: "Reload", action: #selector(reload(_:)), keyEquivalent: "r")
        reload.target = self
        viewMenu.addItem(reload)
        viewMenu.addItem(withTitle: "Enter Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
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
        } catch {
            showFailure("CrossAudit could not launch its core: \(error.localizedDescription)")
        }
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

    private func showLoading(_ message: String) {
        webView.loadHTMLString("""
        <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
        <style>html,body{height:100%;margin:0;background:#191a18;color:#f4f4f1;font:14px -apple-system;display:grid;place-items:center}
        main{text-align:center}.mark{width:42px;height:42px;border-radius:13px;background:#f4f4f1;color:#191a18;display:grid;place-items:center;margin:0 auto 16px;font-size:22px}
        p{color:#999b95}</style><main><div class=mark>◇</div><b>CrossAudit</b><p>\(htmlEscape(message))</p></main>
        """, baseURL: nil)
    }

    private func showFailure(_ message: String) {
        webView.loadHTMLString("""
        <!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
        <style>html,body{height:100%;margin:0;background:#191a18;color:#f4f4f1;font:14px -apple-system;display:grid;place-items:center}
        main{max-width:620px;padding:40px;text-align:center}h1{font-size:20px}p{color:#b6b7b2;line-height:1.6}</style>
        <main><h1>CrossAudit could not open</h1><p>\(htmlEscape(message))</p></main>
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
        guard message.name == "crossaudit",
              ["127.0.0.1", "localhost"].contains(message.frameInfo.securityOrigin.host),
              let body = message.body as? [String: Any],
              body["action"] as? String == "chooseWorkspace" else { return }
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
