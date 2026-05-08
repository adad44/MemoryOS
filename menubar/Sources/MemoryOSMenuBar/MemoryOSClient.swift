import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

@MainActor
final class MemoryOSClient: ObservableObject {
    @Published var backendURL: String {
        didSet {
            UserDefaults.standard.set(backendURL, forKey: "backendURL")
        }
    }
    @Published var webURL: String {
        didSet {
            UserDefaults.standard.set(webURL, forKey: "webURL")
        }
    }
    @Published var state: BackendState = .checking
    @Published var stats: StatsResponse?
    @Published var isRefreshingIndex = false
    @Published var capturePaused = false
    @Published var permissions = PermissionSnapshot.current()

    private let session = URLSession.shared
    private let pauseFlagURL: URL

    init() {
        backendURL = UserDefaults.standard.string(forKey: "backendURL") ?? "http://127.0.0.1:8765"
        webURL = UserDefaults.standard.string(forKey: "webURL") ?? "http://127.0.0.1:5173"
        let supportURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/MemoryOS", isDirectory: true)
        pauseFlagURL = supportURL.appendingPathComponent("capture.paused")
        capturePaused = FileManager.default.fileExists(atPath: pauseFlagURL.path)
    }

    func refresh() async {
        state = .checking
        do {
            let health: HealthResponse = try await request(path: "/health")
            guard health.ok else {
                state = .offline("Health check failed")
                return
            }
            stats = try await request(path: "/stats")
            state = .online
        } catch {
            state = .offline(error.localizedDescription)
        }
    }

    func refreshIndex() async {
        isRefreshingIndex = true
        defer { isRefreshingIndex = false }
        do {
            _ = try await request(
                path: "/refresh-index",
                method: "POST",
                body: ["backend": "tfidf"]
            ) as RefreshIndexResponse
            await refresh()
        } catch {
            state = .offline(error.localizedDescription)
        }
    }

    func openSearch() {
        open(urlString: webURL)
    }

    func openBackendDocs() {
        open(urlString: "\(backendURL)/docs")
    }

    func toggleCapturePaused() {
        do {
            try FileManager.default.createDirectory(
                at: pauseFlagURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            if capturePaused {
                try? FileManager.default.removeItem(at: pauseFlagURL)
                capturePaused = false
            } else {
                try "paused\n".write(to: pauseFlagURL, atomically: true, encoding: .utf8)
                capturePaused = true
            }
        } catch {
            state = .offline(error.localizedDescription)
        }
    }

    func refreshPermissions() {
        permissions = PermissionSnapshot.current()
    }

    func requestAccessibilityPermission() {
        let options = [
            kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true
        ] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
        openPermissionPane(.accessibility)
        refreshPermissions()
    }

    func requestScreenRecordingPermission() {
        _ = CGRequestScreenCaptureAccess()
        openPermissionPane(.screenRecording)
        refreshPermissions()
    }

    func openFullDiskAccessSettings() {
        openPermissionPane(.fullDiskAccess)
        refreshPermissions()
    }

    private func open(urlString: String) {
        guard let url = URL(string: urlString) else { return }
        NSWorkspace.shared.open(url)
    }

    private func openPermissionPane(_ pane: PermissionPane) {
        if let url = URL(string: pane.urlString), NSWorkspace.shared.open(url) {
            return
        }
        if let fallback = URL(string: "x-apple.systempreferences:com.apple.preference.security") {
            NSWorkspace.shared.open(fallback)
        }
    }

    private func request<T: Decodable>(
        path: String,
        method: String = "GET",
        body: [String: String]? = nil
    ) async throws -> T {
        guard let url = URL(string: backendURL + path) else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let body {
            request.httpBody = try JSONEncoder().encode(body)
        }

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
}

private enum PermissionPane {
    case accessibility
    case screenRecording
    case fullDiskAccess

    var urlString: String {
        switch self {
        case .accessibility:
            return "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        case .screenRecording:
            return "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
        case .fullDiskAccess:
            return "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
        }
    }
}

private struct RefreshIndexResponse: Decodable {
    let indexedCount: Int
    let artifactPath: String

    enum CodingKeys: String, CodingKey {
        case indexedCount = "indexed_count"
        case artifactPath = "artifact_path"
    }
}
