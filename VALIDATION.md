# Validation — 2 November 2026

39 conversion tests passed on Linux with Python 3.12. Four additional offscreen Qt UI tests passed (43 total).

Covered: image codecs including HEIC encode/decode; strict output byte caps; failure cleanup; original preservation and repeat-output collision handling; combined image PDFs; PDF text/Word/page image export; PDF compression with text preserved and explicit rasterization; encrypted/scanned PDF errors; Chinese workbook content; worksheet splitting; formula cache errors; CSV/JSON/XLSX conversion; duplicate headers; imported formula strings kept literal; Unicode text pagination; image orientation/transparency; eight FFmpeg output formats decoded after conversion; English OCR.

UI checks: actual drop-event handling, combined PDF conversion with size limit through the worker, continue after corrupt-file failure, incompatible mixed queues and unavailable file-size controls.

Rendered and visually inspected the Qt desktop interface on Linux. Windows Python and Windows wheels were assembled without executing their code on Linux; NSIS cross-built the installer and launcher. Windows startup, install/uninstall, shell shortcuts, platform codecs and optional Windows LibreOffice/Tesseract integrations have NOT been run on Windows. Windows testing is required before treating this as a stable release. Chinese OCR language data were not tested. Large real-world PDFs, uncommon fonts/codecs and malformed-file robustness are not comprehensively covered.
