# ShiftConvert 0.1.0

Offline Windows desktop conversion app. Open `START_HERE.html` for the user guide, supported conversions, installation and limitations.

## Run from source

Python 3.12: `python -m pip install -r requirements.txt`, then `python -m shiftconvert`.
Tests: `python -m pip install pytest` then `python -m pytest -q`.
Set `QT_QPA_PLATFORM=offscreen` to run UI tests on a headless host.
Optional LibreOffice and Tesseract are external executables. FFmpeg is supplied by imageio-ffmpeg if not on PATH.

## Build Windows installer

The bundled Python 3.12.10 runtime and Windows wheels can be assembled on any host, then NSIS creates the installer. See `packaging/build.py` and `packaging/installer.nsi`.

1. Download the official Python 3.12.10 embeddable x64 ZIP to `build-cache/python-embed.zip`.
2. Download Windows wheels: `python -m pip download --dest build-cache/wheels --only-binary=:all: --platform win_amd64 --python-version 312 --implementation cp -r requirements-windows-lock.txt`.
3. From the parent directory of this project: `python shiftconvert/packaging/build.py`.
4. Use NSIS 3: `makensis shiftconvert/packaging/launcher.nsi`, then `makensis shiftconvert/packaging/installer.nsi`. On Linux set NSISDIR to its share/nsis directory if locally extracted.

The installer and launcher are unsigned. This build has not been exercised on Windows; see VALIDATION.md. No network operations are performed by the running app. Default installation is per-user and does not require elevation.
