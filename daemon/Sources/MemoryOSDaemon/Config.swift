import Foundation

struct MemoryOSConfig {
    let databasePath: String
    let pollIntervalSeconds: TimeInterval
    let maxFileCharacters: Int
    let minCaptureCharacters: Int
    let watchedDirectories: [String]
    let allowedFileExtensions: Set<String>
    let blockedApps: Set<String>
    let noiseApps: Set<String>
    let ignoredHostFragments: [String]
    let excludedPathFragments: [String]
    let pauseFlagPath: String

    static func load() -> MemoryOSConfig {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let dataDir = ProcessInfo.processInfo.environment["MEMORYOS_DATA_DIR"]
            ?? "\(home)/Library/Application Support/MemoryOS"
        try? FileManager.default.createDirectory(
            atPath: dataDir,
            withIntermediateDirectories: true
        )

        let privacy = PrivacyConfig.load(from: "\(dataDir)/privacy.json")

        let defaultBlockedApps: Set<String> = [
            "1Password", "Keychain Access", "System Settings", "System Preferences"
        ]
        let defaultIgnoredHosts = [
            "bank", "chase.com", "wellsfargo.com", "capitalone.com",
            "paypal.com", "venmo.com"
        ]
        let defaultExcludedPaths = [
            "/Library/", "/.ssh/", "/.gnupg/", "/.Trash/"
        ]

        return MemoryOSConfig(
            databasePath: ProcessInfo.processInfo.environment["MEMORYOS_DB"]
                ?? "\(dataDir)/memoryos.db",
            pollIntervalSeconds: 8,
            maxFileCharacters: 2_000,
            minCaptureCharacters: 180,
            watchedDirectories: [
                "\(home)/Documents",
                "\(home)/Desktop",
                "\(home)/Downloads"
            ],
            allowedFileExtensions: [
                "pdf", "md", "txt", "py", "js", "ts", "tsx", "jsx", "swift",
                "json", "yaml", "yml", "html", "css", "csv"
            ],
            blockedApps: defaultBlockedApps.union(privacy?.blockedApps ?? []),
            noiseApps: [
                "Netflix", "Spotify", "TV", "Music", "Steam", "Games"
            ],
            ignoredHostFragments: defaultIgnoredHosts + (privacy?.blockedDomains ?? []),
            excludedPathFragments: defaultExcludedPaths + (privacy?.excludedPathFragments ?? []),
            pauseFlagPath: "\(dataDir)/capture.paused"
        )
    }
}

private struct PrivacyConfig: Decodable {
    let blockedApps: [String]
    let blockedDomains: [String]
    let excludedPathFragments: [String]

    enum CodingKeys: String, CodingKey {
        case blockedApps = "blocked_apps"
        case blockedDomains = "blocked_domains"
        case excludedPathFragments = "excluded_path_fragments"
    }

    static func load(from path: String) -> PrivacyConfig? {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else {
            return nil
        }
        return try? JSONDecoder().decode(PrivacyConfig.self, from: data)
    }
}
