from __future__ import annotations

from typing import cast, get_args

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile
from pdfrest.models._internal import ConvertPdfToPostscriptPayload
from pdfrest.types import PostScriptLevel

from ..resources import get_test_resource_path

POSTSCRIPT_LEVELS = cast(
    tuple[PostScriptLevel, ...],
    get_args(ConvertPdfToPostscriptPayload.model_fields["ps_level"].annotation),
)


def _postscript_level_id(ps_level: PostScriptLevel) -> str:
    return f"level-{ps_level}"


@pytest.fixture(scope="module")
def uploaded_pdf_for_postscript(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> PdfRestFile:
    resource = get_test_resource_path("20-pages.pdf")
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        return client.files.create_from_paths(resource)[0]


def _assert_postscript_response(
    output: PdfRestFile,
    output_bytes: bytes,
    output_prefix: str,
    ps_level: PostScriptLevel,
) -> None:
    assert output.name.startswith(output_prefix)
    assert output.name.endswith(".ps")
    assert output.type == "application/postscript"
    assert output.size == len(output_bytes)
    assert output.size > 0
    assert f"/resource/{output.id}" in str(output.url)
    assert output_bytes.startswith(b"%!PS-Adobe")
    assert f"%%LanguageLevel: {ps_level}".encode() in output_bytes.splitlines()
    assert output_bytes.count(b"%%Page:") == 2


@pytest.mark.parametrize(
    "ps_level",
    POSTSCRIPT_LEVELS,
    ids=_postscript_level_id,
)
def test_live_convert_pdf_to_postscript_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_postscript: PdfRestFile,
    ps_level: PostScriptLevel,
) -> None:
    output_prefix = f"live-postscript-level-{ps_level}"
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = client.convert_pdf_to_postscript(
            uploaded_pdf_for_postscript,
            ps_level=ps_level,
            page_range="2-3",
            binary_output=False,
            scale=0.75,
            rotate=True,
            shrink_to_fit=True,
            print_annotations=False,
            output=output_prefix,
        )
        output_bytes = client.files.read_bytes(response.output_file)

    assert str(response.input_id) == str(uploaded_pdf_for_postscript.id)
    assert response.warning is None
    _assert_postscript_response(
        response.output_file,
        output_bytes,
        output_prefix,
        ps_level,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ps_level",
    POSTSCRIPT_LEVELS,
    ids=_postscript_level_id,
)
async def test_live_async_convert_pdf_to_postscript_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_postscript: PdfRestFile,
    ps_level: PostScriptLevel,
) -> None:
    output_prefix = f"live-postscript-async-level-{ps_level}"
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        response = await client.convert_pdf_to_postscript(
            uploaded_pdf_for_postscript,
            ps_level=ps_level,
            page_range="4-5",
            binary_output=False,
            scale=1.25,
            rotate=True,
            shrink_to_fit=True,
            print_annotations=False,
            output=output_prefix,
        )
        output_bytes = await client.files.read_bytes(response.output_file)

    assert str(response.input_id) == str(uploaded_pdf_for_postscript.id)
    assert response.warning is None
    _assert_postscript_response(
        response.output_file,
        output_bytes,
        output_prefix,
        ps_level,
    )


def test_live_convert_pdf_to_postscript_rejects_invalid_level(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_postscript: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match="ps_level must be 2 or 3"),
    ):
        client.convert_pdf_to_postscript(
            uploaded_pdf_for_postscript,
            extra_body={"ps_level": 4},
        )


@pytest.mark.asyncio
async def test_live_async_convert_pdf_to_postscript_rejects_invalid_level(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_postscript: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match="ps_level must be 2 or 3"):
            await client.convert_pdf_to_postscript(
                uploaded_pdf_for_postscript,
                extra_body={"ps_level": 4},
            )


def test_live_convert_pdf_to_postscript_rejects_invalid_page_range(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_postscript: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match="invalid page range"),
    ):
        client.convert_pdf_to_postscript(
            uploaded_pdf_for_postscript,
            extra_body={"page_range": "1,,3"},
        )


@pytest.mark.asyncio
async def test_live_async_convert_pdf_to_postscript_rejects_invalid_page_range(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_postscript: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match="invalid page range"):
            await client.convert_pdf_to_postscript(
                uploaded_pdf_for_postscript,
                extra_body={"page_range": "1,,3"},
            )


def test_live_convert_pdf_to_postscript_rejects_invalid_scale(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_postscript: PdfRestFile,
) -> None:
    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match="scale must be greater than zero"),
    ):
        client.convert_pdf_to_postscript(
            uploaded_pdf_for_postscript,
            extra_body={"scale": 0},
        )


@pytest.mark.asyncio
async def test_live_async_convert_pdf_to_postscript_rejects_invalid_scale(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_pdf_for_postscript: PdfRestFile,
) -> None:
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(
            PdfRestApiError,
            match="scale must be greater than zero",
        ):
            await client.convert_pdf_to_postscript(
                uploaded_pdf_for_postscript,
                extra_body={"scale": 0},
            )
