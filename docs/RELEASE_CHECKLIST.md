# Release checklist

- [ ] Run `python -m pytest -q` on the supported Python matrix.
- [ ] Run opt-in live provider checks with non-production credentials.
- [ ] Build with `./packaging/macos/build_dmg.sh` on Apple Silicon.
- [ ] Verify the application plist, architecture, and deep signature.
- [ ] Verify, mount, inspect, and copy the DMG into an isolated directory.
- [ ] Start the copied frozen core with isolated support/workspace directories.
- [ ] Test project creation, independent worker attachment, token refusals, and
      final-artifact download.
- [ ] Generate PDF and DOCX through the UI; verify only the requested binary is
      committed, semantic audit sees the final bytes, CJK text renders, every
      supported preview opens safely, and unknown binaries remain download-only.
- [ ] Open a long audit at maximum scroll with a tall composer and attachments;
      confirm the final evidence stays visible above the composer. Exercise the
      SSH host dialog with Generator access both collapsed and expanded.
- [ ] Run Environment Doctor with current, missing, and outdated Git; verify
      real-time refresh, project-creation blocking, update guidance, local Git
      identity repair, and first-launch recovery without a usable Git binary.
- [ ] Close the native window during an active controller session, verify the
      shell/core remain alive, restore from Dock/menu bar, then verify explicit
      Quit stops the controller.
- [ ] Create two Chats in one Project, switch their isolated views, pin one Chat
      and the Project, reload, and verify Git-trailer recovery.
- [ ] Test a native folder choice, two editable repository names, name
      preflight, explicit adoption, one-click creation, and partial-failure UI
      recovery against an isolated test project.
- [ ] Verify provider-reported API and subscription token events, custom-model
      unpriced handling, local-ledger privacy, and immediate Usage SSE refresh.
- [ ] Register an SSH-config host, exercise unknown/changed-key and offline
      guidance, submit both Slurm and detached workstation jobs, restart the
      local controller, and verify reattachment, live status/logs, cancellation,
      input streaming, and portable remote-output download.
- [ ] Confirm no key, tokenized localhost URL, build directory, or app support
      data is tracked by Git.
- [ ] Confirm `main` is clean, version is 4.13.0, and README links target V4.
- [ ] Push `main`, create the `v4.13.0` release, upload DMG and checksum, and
      verify the repository default branch is `main`.
