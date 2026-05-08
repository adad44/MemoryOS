import ApplicationServices
import CoreGraphics
import Foundation

struct HealthResponse: Decodable {
    let ok: Bool
}

struct StatsResponse: Decodable {
    let totalCaptures: Int
    let indexedAvailable: Bool
    let latestCaptureAt: String?

    enum CodingKeys: String, CodingKey {
        case totalCaptures = "total_captures"
        case indexedAvailable = "indexed_available"
        case latestCaptureAt = "latest_capture_at"
    }
}

enum BackendState: Equatable {
    case checking
    case online
    case offline(String)

    var label: String {
        switch self {
        case .checking:
            return "Checking"
        case .online:
            return "Online"
        case .offline:
            return "Offline"
        }
    }
}

struct PermissionSnapshot {
    let accessibilityGranted: Bool
    let screenRecordingGranted: Bool
    let fullDiskAccessStatus: FullDiskAccessStatus

    var needsAttention: Bool {
        !accessibilityGranted || fullDiskAccessStatus != .likelyGranted
    }

    static func current() -> PermissionSnapshot {
        PermissionSnapshot(
            accessibilityGranted: AXIsProcessTrusted(),
            screenRecordingGranted: CGPreflightScreenCaptureAccess(),
            fullDiskAccessStatus: FullDiskAccessStatus.detect()
        )
    }
}

enum FullDiskAccessStatus: Equatable {
    case likelyGranted
    case needsReview
    case unknown

    var label: String {
        switch self {
        case .likelyGranted:
            return "Ready"
        case .needsReview:
            return "Needs access"
        case .unknown:
            return "Review"
        }
    }

    static func detect() -> FullDiskAccessStatus {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let candidates = [
            "Library/Mail",
            "Library/Messages",
            "Library/Safari"
        ]
        var foundProtectedPath = false

        for relativePath in candidates {
            let url = home.appendingPathComponent(relativePath, isDirectory: true)
            guard FileManager.default.fileExists(atPath: url.path) else {
                continue
            }
            foundProtectedPath = true

            do {
                _ = try FileManager.default.contentsOfDirectory(
                    at: url,
                    includingPropertiesForKeys: nil,
                    options: [.skipsHiddenFiles]
                )
                return .likelyGranted
            } catch {
                continue
            }
        }

        return foundProtectedPath ? .needsReview : .unknown
    }
}
