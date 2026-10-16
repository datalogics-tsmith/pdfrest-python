from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pdfrest import AsyncPdfRestClient, PdfRestClient
from pdfrest.models import PdfRestFile, PdfRestFileBasedResponse, PdfRestFileID
from pdfrest.models._internal import ConvertPostscriptToPdfPayload

from .convert_to_pdf_test_helpers import make_source_file
from .graphics_test_helpers import ASYNC_API_KEY, VALID_API_KEY, build_file_info_payload

MAX_JOB_OPTIONS_SIZE = 5 * 1024 * 1024


def _make_job_options_file(
    *,
    name: str = "valid.joboptions",
    mime_type: str = "application/octet-stream",
    size: int = 299,
) -> PdfRestFile:
    return make_source_file(
        str(PdfRestFileID.generate()),
        mime_type,
        name,
    ).model_copy(update={"size": size})


INVALID_JOB_OPTIONS_CASES: tuple[tuple[PdfRestFile | list[PdfRestFile], str], ...] = (
    (
        _make_job_options_file(mime_type="application/pdf"),
        r"Must be a \.joboptions file",
    ),
    (
        _make_job_options_file(name="profile.txt"),
        r"Must be a \.joboptions file",
    ),
    (
        _make_job_options_file(size=0),
        "between 1 byte and 5 MiB",
    ),
    (
        _make_job_options_file(size=MAX_JOB_OPTIONS_SIZE + 1),
        "between 1 byte and 5 MiB",
    ),
    ([], "at least 1 item"),
    (
        [_make_job_options_file(), _make_job_options_file()],
        "at most 1 item",
    ),
)
INVALID_JOB_OPTIONS_CASE_IDS = (
    "mime-type",
    "extension",
    "empty-file",
    "too-large",
    "empty-list",
    "multiple",
)


@pytest.mark.parametrize(
    "job_options_size",
    [
        pytest.param(1, id="minimum"),
        pytest.param(2, id="minimum-plus-one"),
        pytest.param(MAX_JOB_OPTIONS_SIZE - 1, id="maximum-minus-one"),
        pytest.param(MAX_JOB_OPTIONS_SIZE, id="maximum"),
    ],
)
@pytest.mark.parametrize(
    "job_options_name",
    [
        pytest.param("valid.joboptions", id="lowercase-extension"),
        pytest.param("valid.JOBOPTIONS", id="uppercase-extension"),
    ],
)
@pytest.mark.parametrize(
    "job_options_mime_type",
    [
        pytest.param("application/octet-stream", id="octet-stream"),
        pytest.param("application/postscript", id="postscript"),
        pytest.param("text/plain", id="plain-text"),
    ],
)
def test_convert_postscript_to_pdf_success(
    monkeypatch: pytest.MonkeyPatch,
    job_options_size: int,
    job_options_name: str,
    job_options_mime_type: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(1)),
        "application/postscript",
        "example.ps",
    )
    job_options = _make_job_options_file(
        name=job_options_name,
        mime_type=job_options_mime_type,
        size=job_options_size,
    )
    output_id = str(PdfRestFileID.generate())
    payload_dump = ConvertPostscriptToPdfPayload.model_validate(
        {
            "files": [input_file],
            "output": "converted",
            "compression": "lossless",
            "downsample": 150,
            "job_options": job_options,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, job_options.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            assert request.url.params["format"] == "info"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "converted.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_postscript_to_pdf(
            input_file,
            output="converted",
            compression="lossless",
            downsample=150,
            job_options=job_options,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "converted.pdf"
    assert response.output_file.type == "application/pdf"
    assert response.warning is None
    assert response.input_ids == [input_file.id, job_options.id]


def test_convert_postscript_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(1)),
        "application/eps",
        "example.eps",
    )
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["debug"] is True
            assert payload["compression"] == "lossy"
            assert payload["downsample"] == 600
            assert payload["id"] == str(input_file.id)
            assert payload["output"] == "custom"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "true"
            assert request.headers["X-Debug"] == "sync"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "custom.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    with PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client:
        response = client.convert_postscript_to_pdf(
            input_file,
            output="custom",
            compression="lossy",
            downsample=600,
            extra_query={"trace": "true"},
            extra_headers={"X-Debug": "sync"},
            extra_body={"debug": True},
            timeout=0.5,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.5) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.5)


def test_convert_postscript_to_pdf_validation_errors() -> None:
    with pytest.raises(ValidationError, match="Must be a PostScript or EPS file"):
        ConvertPostscriptToPdfPayload.model_validate(
            {
                "files": [
                    make_source_file(
                        str(PdfRestFileID.generate(2)),
                        "message/rfc822",
                        "message.eml",
                    )
                ]
            }
        )


@pytest.mark.parametrize(
    "size",
    [
        pytest.param(1, id="minimum"),
        pytest.param(2, id="minimum-plus-one"),
        pytest.param(MAX_JOB_OPTIONS_SIZE - 1, id="maximum-minus-one"),
        pytest.param(MAX_JOB_OPTIONS_SIZE, id="maximum"),
    ],
)
def test_convert_postscript_to_pdf_job_options_size_boundaries(size: int) -> None:
    input_file = make_source_file(
        str(PdfRestFileID.generate(2)),
        "application/postscript",
        "example.ps",
    )
    job_options = _make_job_options_file(size=size)

    payload = ConvertPostscriptToPdfPayload.model_validate(
        {"files": input_file, "job_options": job_options}
    ).model_dump(mode="json", by_alias=True, exclude_none=True)

    assert payload == {
        "id": str(input_file.id),
        "job_options_id": str(job_options.id),
    }


@pytest.mark.parametrize(
    ("job_options", "error_match"),
    [
        pytest.param(
            _make_job_options_file(name="profile.txt"),
            r"Must be a \.joboptions file",
            id="extension",
        ),
        pytest.param(
            _make_job_options_file(size=0),
            "between 1 byte and 5 MiB",
            id="empty",
        ),
        pytest.param(
            _make_job_options_file(size=MAX_JOB_OPTIONS_SIZE + 1),
            "between 1 byte and 5 MiB",
            id="too-large",
        ),
    ],
)
def test_convert_postscript_to_pdf_job_options_validation(
    job_options: PdfRestFile,
    error_match: str,
) -> None:
    input_file = make_source_file(
        str(PdfRestFileID.generate(2)),
        "application/postscript",
        "example.ps",
    )

    with pytest.raises(ValidationError, match=error_match):
        ConvertPostscriptToPdfPayload.model_validate(
            {"files": input_file, "job_options": job_options}
        )


@pytest.mark.parametrize(
    ("job_options", "error_match"),
    INVALID_JOB_OPTIONS_CASES,
    ids=INVALID_JOB_OPTIONS_CASE_IDS,
)
def test_convert_postscript_to_pdf_job_options_client_validation(
    monkeypatch: pytest.MonkeyPatch,
    job_options: PdfRestFile | list[PdfRestFile],
    error_match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(2)),
        "application/postscript",
        "example.ps",
    )
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    with (
        PdfRestClient(api_key=VALID_API_KEY, transport=transport) as client,
        pytest.raises(ValidationError, match=error_match),
    ):
        client.convert_postscript_to_pdf(input_file, job_options=job_options)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_options_size",
    [
        pytest.param(1, id="minimum"),
        pytest.param(2, id="minimum-plus-one"),
        pytest.param(MAX_JOB_OPTIONS_SIZE - 1, id="maximum-minus-one"),
        pytest.param(MAX_JOB_OPTIONS_SIZE, id="maximum"),
    ],
)
@pytest.mark.parametrize(
    "job_options_name",
    [
        pytest.param("valid.joboptions", id="lowercase-extension"),
        pytest.param("valid.JOBOPTIONS", id="uppercase-extension"),
    ],
)
@pytest.mark.parametrize(
    "job_options_mime_type",
    [
        pytest.param("application/octet-stream", id="octet-stream"),
        pytest.param("application/postscript", id="postscript"),
        pytest.param("text/plain", id="plain-text"),
    ],
)
async def test_async_convert_postscript_to_pdf_success(
    monkeypatch: pytest.MonkeyPatch,
    job_options_size: int,
    job_options_name: str,
    job_options_mime_type: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(2)),
        "application/x-eps",
        "graphic.eps",
    )
    job_options = _make_job_options_file(
        name=job_options_name,
        mime_type=job_options_mime_type,
        size=job_options_size,
    )
    output_id = str(PdfRestFileID.generate())
    payload_dump = ConvertPostscriptToPdfPayload.model_validate(
        {
            "files": [input_file],
            "output": "async-converted",
            "compression": "lossless",
            "job_options": job_options,
        }
    ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude_unset=True)

    seen: dict[str, int] = {"post": 0, "get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            seen["post"] += 1
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == payload_dump
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id, job_options.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            seen["get"] += 1
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "async-converted.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.convert_postscript_to_pdf(
            input_file,
            output="async-converted",
            compression="lossless",
            job_options=job_options,
        )

    assert seen == {"post": 1, "get": 1}
    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-converted.pdf"
    assert response.output_file.type == "application/pdf"
    assert response.input_ids == [input_file.id, job_options.id]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("job_options", "error_match"),
    INVALID_JOB_OPTIONS_CASES,
    ids=INVALID_JOB_OPTIONS_CASE_IDS,
)
async def test_async_convert_postscript_to_pdf_job_options_client_validation(
    monkeypatch: pytest.MonkeyPatch,
    job_options: PdfRestFile | list[PdfRestFile],
    error_match: str,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(2)),
        "application/postscript",
        "example.ps",
    )
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(RuntimeError))

    async with AsyncPdfRestClient(
        api_key=ASYNC_API_KEY,
        transport=transport,
    ) as client:
        with pytest.raises(ValidationError, match=error_match):
            await client.convert_postscript_to_pdf(
                input_file,
                job_options=job_options,
            )


@pytest.mark.asyncio
async def test_async_convert_postscript_to_pdf_request_customization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDFREST_API_KEY", raising=False)
    input_file = make_source_file(
        str(PdfRestFileID.generate(2)),
        "application/postscript",
        "graphic.ps",
    )
    output_id = str(PdfRestFileID.generate())
    captured_timeout: dict[str, float | dict[str, float] | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/pdf":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            captured_timeout["value"] = request.extensions.get("timeout")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["debug"] is True
            assert payload["compression"] == "lossy"
            assert payload["downsample"] == 600
            assert payload["id"] == str(input_file.id)
            assert payload["output"] == "async-custom"
            return httpx.Response(
                200,
                json={
                    "inputId": [input_file.id],
                    "outputId": [output_id],
                },
            )
        if request.method == "GET" and request.url.path == f"/resource/{output_id}":
            assert request.url.params["trace"] == "async"
            assert request.headers["X-Debug"] == "async"
            return httpx.Response(
                200,
                json=build_file_info_payload(
                    output_id, "async-custom.pdf", "application/pdf"
                ),
            )
        msg = f"Unexpected request {request.method} {request.url}"
        raise AssertionError(msg)

    transport = httpx.MockTransport(handler)
    async with AsyncPdfRestClient(api_key=ASYNC_API_KEY, transport=transport) as client:
        response = await client.convert_postscript_to_pdf(
            input_file,
            output="async-custom",
            compression="lossy",
            downsample=600,
            extra_query={"trace": "async"},
            extra_headers={"X-Debug": "async"},
            extra_body={"debug": True},
            timeout=0.6,
        )

    assert isinstance(response, PdfRestFileBasedResponse)
    assert response.output_file.name == "async-custom.pdf"
    timeout_value = captured_timeout["value"]
    assert timeout_value is not None
    if isinstance(timeout_value, dict):
        assert all(
            component == pytest.approx(0.6) for component in timeout_value.values()
        )
    else:
        assert timeout_value == pytest.approx(0.6)
