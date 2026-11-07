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

- Local development repository; not published to GitHub. Files were installed
  into HA for controlled runtime testing on 2026-11-07; setup status is tracked
  in the main setup notes.
- Pure policy tests run locally; HA runtime/loading tests still required.
- Before publication, add verified repository documentation URL/codeowners to
  the manifest, English translations, and run HACS/hassfest validation. Current
  metadata is a development draft, not a validated HACS release.
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

Do not publish personal device addresses, HA exports, app captures or keys.

Source inspected:
https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/onvif/device.py
