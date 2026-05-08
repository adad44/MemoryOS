import AppKit
import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject private var client: MemoryOSClient
    @State private var showingSettings = false
    @State private var showingSetup = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            header
            if showingSetup {
                Divider()
                onboarding
            }
            Divider()
            stats
            actions
            if showingSettings {
                Divider()
                settings
            }
            Divider()
            footer
        }
        .padding(12)
        .frame(width: 320)
        .onAppear {
            client.refreshPermissions()
        }
    }

    private var header: some View {
        HStack(spacing: 10) {
            MemoryOSLogo(size: 28)
            VStack(alignment: .leading, spacing: 2) {
                Text("MemoryOS")
                    .font(.headline)
                HStack(spacing: 6) {
                    Circle()
                        .fill(statusColor)
                        .frame(width: 8, height: 8)
                    Text(client.state.label)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            Button {
                Task { await client.refresh() }
            } label: {
                Image(systemName: "arrow.clockwise")
            }
            .buttonStyle(.borderless)
            .help("Refresh status")
        }
    }

    private var onboarding: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Setup")
                    .font(.headline)
                Spacer()
                Button {
                    client.refreshPermissions()
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .help("Refresh permissions")
                Button {
                    showingSetup.toggle()
                } label: {
                    Image(systemName: showingSetup ? "chevron.up" : "chevron.down")
                }
                .buttonStyle(.borderless)
                .help(showingSetup ? "Hide setup" : "Show setup")
            }

            if showingSetup {
                permissionRow(
                    title: "Accessibility",
                    detail: "Required for active-window text capture",
                    status: client.permissions.accessibilityGranted ? "Ready" : "Needs access",
                    systemImage: client.permissions.accessibilityGranted ? "checkmark.circle.fill" : "exclamationmark.circle.fill",
                    tint: client.permissions.accessibilityGranted ? .green : .orange,
                    actionTitle: client.permissions.accessibilityGranted ? "Open" : "Allow"
                ) {
                    client.requestAccessibilityPermission()
                }

                permissionRow(
                    title: "Full Disk Access",
                    detail: "Recommended so file watching can read protected folders",
                    status: client.permissions.fullDiskAccessStatus.label,
                    systemImage: client.permissions.fullDiskAccessStatus == .likelyGranted ? "checkmark.circle.fill" : "folder.badge.gearshape",
                    tint: client.permissions.fullDiskAccessStatus == .likelyGranted ? .green : .orange,
                    actionTitle: "Open"
                ) {
                    client.openFullDiskAccessSettings()
                }

                permissionRow(
                    title: "Screen Recording",
                    detail: "Fallback only; not used by normal capture",
                    status: client.permissions.screenRecordingGranted ? "Ready" : "Optional",
                    systemImage: client.permissions.screenRecordingGranted ? "checkmark.circle.fill" : "rectangle.dashed",
                    tint: client.permissions.screenRecordingGranted ? .green : .secondary,
                    actionTitle: client.permissions.screenRecordingGranted ? "Open" : "Request"
                ) {
                    client.requestScreenRecordingPermission()
                }
            }
        }
    }

    private var stats: some View {
        VStack(alignment: .leading, spacing: 8) {
            statRow("Captures", value: "\(client.stats?.totalCaptures ?? 0)")
            statRow("Index", value: client.stats?.indexedAvailable == true ? "Ready" : "Missing")
            statRow("Capture", value: client.capturePaused ? "Paused" : "Active")
            statRow("Latest", value: formattedLatest)
        }
    }

    private var actions: some View {
        VStack(spacing: 8) {
            Button {
                client.openSearch()
            } label: {
                actionLabel("Open Search", systemImage: "magnifyingglass")
            }
            Button {
                client.toggleCapturePaused()
            } label: {
                actionLabel(client.capturePaused ? "Resume Capture" : "Pause Capture", systemImage: client.capturePaused ? "play.fill" : "pause.fill")
            }
            Button {
                Task { await client.refreshIndex() }
            } label: {
                actionLabel(client.isRefreshingIndex ? "Refreshing Index" : "Refresh Index", systemImage: "externaldrive")
            }
            .disabled(client.isRefreshingIndex)
            Button {
                client.openBackendDocs()
            } label: {
                actionLabel("Backend API", systemImage: "curlybraces")
            }
            Button {
                showingSettings.toggle()
            } label: {
                actionLabel(showingSettings ? "Hide Settings" : "Settings", systemImage: "gearshape")
            }
            Button {
                showingSetup.toggle()
            } label: {
                actionLabel(showingSetup ? "Hide Setup" : "Setup Permissions", systemImage: "lock.shield")
            }
        }
        .buttonStyle(.plain)
    }

    private var settings: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Backend URL")
                .font(.caption)
                .foregroundStyle(.secondary)
            TextField("Backend URL", text: $client.backendURL)
                .textFieldStyle(.roundedBorder)
            Text("Web URL")
                .font(.caption)
                .foregroundStyle(.secondary)
            TextField("Web URL", text: $client.webURL)
                .textFieldStyle(.roundedBorder)
        }
    }

    private var footer: some View {
        HStack {
            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
            .buttonStyle(.borderless)
            Spacer()
            Text("Local only")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private func statRow(_ label: String, value: String) -> some View {
        HStack {
            Text(label)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
                .lineLimit(1)
                .truncationMode(.middle)
        }
        .font(.callout)
    }

    private func actionLabel(_ title: String, systemImage: String) -> some View {
        HStack {
            Image(systemName: systemImage)
                .frame(width: 18)
            Text(title)
            Spacer()
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    private func permissionRow(
        title: String,
        detail: String,
        status: String,
        systemImage: String,
        tint: Color,
        actionTitle: String,
        action: @escaping () -> Void
    ) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: systemImage)
                .foregroundStyle(tint)
                .frame(width: 18)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(title)
                        .font(.callout)
                        .fontWeight(.medium)
                    Spacer()
                    Text(status)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Button(actionTitle) {
                action()
            }
            .buttonStyle(.borderless)
            .font(.caption)
            .padding(.top, 1)
        }
        .padding(8)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    private var formattedLatest: String {
        guard let latest = client.stats?.latestCaptureAt else {
            return "None"
        }
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: latest) else {
            return latest
        }
        return date.formatted(date: .abbreviated, time: .shortened)
    }

    private var statusColor: Color {
        switch client.state {
        case .checking:
            return .orange
        case .online:
            return .green
        case .offline:
            return .red
        }
    }
}
