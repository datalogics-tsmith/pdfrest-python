# /// script
# requires-python = ">=3.10"
# dependencies = ["pdfrest", "python-dotenv"]
# ///
"""Convert PostScript to PDF with a custom Distiller profile.

This sample demonstrates how to:

1. Upload the checked-in PostScript and ``.joboptions`` files.
2. Pass the uploaded profile to ``convert_postscript_to_pdf``.
3. Print the generated PDF's metadata and download URL.

Set ``PDFREST_API_KEY``, then run from the repository root with
``uv run examples/convert_postscript_to_pdf/convert_postscript_with_job_options_example.py``.
All required input files are included in the repository.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from pdfrest import PdfRestClient

RESOURCE_DIRECTORY = Path(__file__).resolve().parents[1] / "resources"
POSTSCRIPT_PATH = RESOURCE_DIRECTORY / "job-options-sample.ps"
JOB_OPTIONS_PATH = RESOURCE_DIRECTORY / "valid.joboptions"


def convert_postscript_with_job_options() -> None:
    """Upload a PostScript document and convert it with a custom profile."""
    load_dotenv()

    with PdfRestClient() as client:
        postscript = client.files.create_from_paths(POSTSCRIPT_PATH)[0]
        job_options = client.files.create_from_paths(JOB_OPTIONS_PATH)[0]
        response = client.convert_postscript_to_pdf(
            postscript,
            job_options=job_options,
            output="custom-profile",
        )

    output = response.output_file
    print(f"Created: {output.name}")
    print(f"MIME type: {output.type}")
    print(f"Size: {output.size} bytes")
    print(f"Download URL: {output.url}")


if __name__ == "__main__":  # pragma: no cover - manual example
    convert_postscript_with_job_options()
