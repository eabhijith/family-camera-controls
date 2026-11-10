# Reviewed live-only fork

Source: https://github.com/ijtan/hikconnect-cloud-relay
Pinned commit: `61af5ad622616a2cf2f931390717288545dbe91b`.
Copyright (c) 2026 ijtan, MIT; full license in
`THIRD_PARTY_LICENSES/hikconnect-cloud-relay-MIT.txt` (repository root).
Cloud API, VTM framing, H.264 and FFmpeg relay derived from upstream.

Changes: no public custom HA HTTP routes, no RTSP server or binary downloads,
private `127.0.0.1` dynamic-port MPEG-TS source, native HA camera/auth handling,
vendor HTTPS API allowlist, no HTTP redirects, generic secret-free errors,
no automatic password retry on rejection, terminal auth failures trigger reauth,
password-selector flow, retain all API channel rows, no arbitrary host options.

Set up domain `hikconnect_cloud_relay` through HA Settings > Devices & services.
User must privately enter their Hik-Connect account credentials. Config entries
contain those credentials (HA storage/backups require appropriate protection).
One chosen channel per entry; adding another entry is possible, concurrency is
not verified. No local DVR password, Android SDK, JVM, USB, or connected phone.
No device writes, microphone, PTZ, alarm, door control, or recording playback.

Upstream's actual working claim is a DS-KIS703Y-P intercom, NOT arbitrary DVRs.
No real authentication/device calls have been made during this adaptation.
Shared devices are supported only if present in upstream's verified pagelist
response; no invented shared-device endpoint. API region redirects permit only
HTTPS hik-connect.com subdomains. The VTM token service remains pinned to
`euauth.ezvizlife.com`; non-EU account media is unverified, not guessed.

IMPORTANT: upstream VTM is unencrypted TCP. HTTPS protects account/API requests,
not cloud video or VTM session material on this transport. Encrypted VTM packets
are explicitly rejected. Do not treat this as end-to-end encrypted video.
Loopback feed is accessible to other processes in HA's network namespace; do
not forward its port or path through a reverse proxy. HA native camera endpoints
retain HA's standard authentication/access-token semantics, rather than custom
unauthenticated snapshot, MJPEG, health, or statistics routes.

Deployment still requires parent review and HA 2026.10 import/runtime testing.
