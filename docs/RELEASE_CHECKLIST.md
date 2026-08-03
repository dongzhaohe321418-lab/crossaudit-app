# Release checklist

- [ ] Run `python -m pytest -q` on the supported Python matrix.
- [ ] Run opt-in live provider checks with non-production credentials.
- [ ] Build with `./packaging/macos/build_dmg.sh` on Apple Silicon.
- [ ] Verify the application plist, architecture, and deep signature.
- [ ] Verify, mount, inspect, and copy the DMG into an isolated directory.
- [ ] Start the copied frozen core with isolated support/workspace directories.
- [ ] Test project creation, independent worker attachment, token refusals, and
      final-artifact download.
- [ ] Confirm no key, tokenized localhost URL, build directory, or app support
      data is tracked by Git.
- [ ] Confirm `main` is clean, version is 4.1.0, and README links target V4.
- [ ] Push `main`, create the `v4.1.0` release, upload DMG and checksum, and
      verify the repository default branch is `main`.
