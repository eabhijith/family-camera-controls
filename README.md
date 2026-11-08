# Family Camera Controls — experimental

Local Home Assistant custom integration for clearly labelled, short ONVIF
bottom-lens movement buttons. **This does not yet implement top-lens control.**

## Why this integration

Home Assistant 2026.10.4's `onvif.ptz` binds commands to a media profile token.
It has no native DVRIP channel parameter. Both inspected cameras expose one
ONVIF PTZ node shared by all profiles. Changing the dashboard alone cannot
select the top lens.

This initial implementation wraps the existing ONVIF service with explicit
per-camera button entities, bounded duration, a per-camera lock, and an extra
Stop request in `finally`. Propagated failures/timeouts raise an error; the
underlying core ONVIF integration catches some device errors and only logs them,
so this wrapper cannot detect every device-side failure. Successful
API calls still do not prove motor movement. Stop cannot be guaranteed when
the network or device is unavailable.

## Status

- Published as an experimental custom integration.
- Ten policy/wrapper tests pass. Wrapper tests use stubbed HA interfaces and
  cover failed moves triggering Stop, overlap rejection, Stop during a move,
  and unavailable-camera rejection. These are not full HA runtime tests.
  Config flows and button entities loaded in a
  Home Assistant 2026.10.4 installation; Stop actions were accepted.
- Physical movement, concurrency/failure behaviour and migration remain to be
  tested. HACS/hassfest validation and release packaging remain pending.
- Repository documentation, codeowner metadata and English translations are
  included. This is not a validated HACS release yet.
- Top lens: blocked pending verified native command/channel and legitimate
  camera authentication. No credential guessing, firmware flashing, or lock bypass.
- Outside: not supported by this ONVIF-only integration.

## Installation for controlled testing

1. Create/download a full HA backup first.
2. Copy `custom_components/family_camera_control` into HA's
   `/config/custom_components/` directory. Do not overwrite another integration.
3. Restart HA, then add **Family Camera Controls** in Devices & services.
4. Select one existing ONVIF camera entity and a room name.
5. Test one brief movement while watching the camera, then Stop.

Once a GitHub repository is published and validated, it can be added through
HACS as a custom **Integration** repository. This is different from the
Supervisor **App store repository** used for go2rtc. No app-store repository
is supplied by this project.

Config entries store only camera entity, room name and movement settings.
Existing ONVIF integration owns credentials. HA full backups include this
custom_components directory, config entries and associated dashboards.
No feature requires a script running on the Mac.

## Development

```sh
python3 -m unittest discover -s tests -v
```

## Optional dual-view dashboard card

Copy the two files from `www/` into HA's `www/family-camera-controls/` directory,
then register `/local/family-camera-controls/dual-lens-card.js` as a JavaScript
module dashboard resource. No camera password is stored in the card. It uses
Home Assistant authenticated snapshots, not publicly accessible camera URLs.

```yaml
type: custom:family-dual-lens-card
entity: camera.example
name: Camera views
split_fraction: 0.5
buttons:
  up: button.example_bottom_lens_up
  down: button.example_bottom_lens_down
  left: button.example_bottom_lens_left
  right: button.example_bottom_lens_right
  stop: button.example_bottom_lens_stop
```

The Both/Upper/Lower selector crops a vertically stacked composite image for
display. This does not separate the camera's native video sources or move the
upper lens. `split_fraction` can be calibrated to the actual image boundary.
Snapshots refresh every 3 seconds, with timeouts and stale-picture warnings;
this is not a continuous-video player. Keep a standard live-camera view for
continuous video. Direction buttons are only shown for lower/both views and
disabled when disconnected. Keyboard focus and large touch targets are included.

Run display-geometry tests with `node --test tests/test_view_geometry.mjs`.

The refined card uses readable 16px labels, 56px+ controls, authored SVG icons,
clear selected/focus states and a manual refresh button. Simulated browser
previews were checked at 390px and 1280px widths and in light/dark modes, with
no horizontal overflow. These previews do not contain household imagery.
Impeccable and UI/UX Pro Max guidance informed the refinement; no successful
automated Impeccable audit is claimed (its context launcher timed out).

### Electronic view-control research

Static analysis of a user-supplied Cofe Online APK identified a distinct
`OPElecPTZControl` SDK command argument (1402), with channel and pixel-offset parameters.
Its exact wire mapping and lens routing are not established.
`electronic_ptz.py` contains an independently written, bounded payload builder.
It has **no network transport or registered HA service**: authenticated camera
access and per-device lens mapping have not been verified. Do not advertise it
as working upper-lens control. No APKs, decompiled code or household captures
are distributed by this repository.

Payload bounds/defaults are local safety policies. Validating hexadecimal session
syntax does not authenticate the camera; validating a channel number does not
prove that it selects an upper lens. Mechanical split-view channel selection
must not be transplanted into electronic control without runtime evidence.

### EseeCloud multi-PTZ serializer research

Static inspection of the installed EseeCloud app resolved the inherited
`BaseSettingSession.setNetAPIMultiPtzControl` serializer. `netapi_ptz.py` implements
its observed `IPCam -> NetAPI -> "R/MultiPTZ/Control"` subtree and fields
`Chn`, `Cmd`, `Arg: 1`, `Arg2: 0`. The slash-containing string is one JSON key,
not an endpoint. Only step/stop commands are permitted by the local safety policy.

This is **not a complete wire request or working EseeCloud integration**.
Envelope/session fields, network framing, authentication and per-device lens
mapping remain unverified. No HA action exposes this research payload yet.
No third-party APKs or decompiled source are included.

Do not publish personal device addresses, HA exports, app captures or keys.

Source inspected:
https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/onvif/device.py
