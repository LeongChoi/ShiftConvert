# Third-party components

ShiftConvert application source is provided under GNU AGPL v3 or later, without warranty. Dependencies remain under their respective licenses. The installed runtime retains wheel metadata and license files. All application code is included in source/ and is editable. Qt DLLs remain dynamically linked and replaceable.

- CPython 3.12.10: PSF license. https://www.python.org/downloads/release/python-31210/
- PySide6 / Shiboken / Qt 6.8.3: LGPL v3 / GPL and Qt component licenses. https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://download.qt.io/archive/qt/6.8/6.8.3/
- PyMuPDF 1.26.7 / MuPDF: AGPL v3. https://github.com/pymupdf/PyMuPDF/tree/1.26.7
- pdf2docx 0.5.13: MIT. https://github.com/ArtifexSoftware/pdf2docx
- Pillow: HPND. https://github.com/python-pillow/Pillow
- pillow-heif: BSD-3-Clause; bundled libheif and codecs retain their own licenses. https://github.com/bigcat88/pillow_heif
- openpyxl: MIT. https://foss.heptapod.net/openpyxl/openpyxl
- python-docx: MIT. https://github.com/python-openxml/python-docx
- imageio-ffmpeg: BSD-2-Clause wrapper; bundled FFmpeg binary has its own license and build configuration. https://github.com/imageio/imageio-ffmpeg and https://ffmpeg.org/download.html
- NumPy: BSD-3-Clause; OpenCV: Apache-2.0 and bundled component licenses; lxml: BSD and bundled libxml2/libxslt licenses; fonttools: MIT; Fire: Apache-2.0; et-xmlfile: MIT; termcolor: MIT; typing-extensions: PSF.
- Microsoft runtime DLLs included by the official Python / PySide6 distributions retain Microsoft's redistribution terms.
- NSIS-generated installer and launcher: https://nsis.sourceforge.io/License

Exact Windows package versions and archive SHA-256 digests are recorded in requirements-windows-lock.txt and packaging/input-sha256.json. Optional LibreOffice and Tesseract are not distributed in this package.

This is a private preview build. Before public distribution, verify all dependency source/relinking obligations, binary build provenance, licensing and code signing for the exact shipped versions.
