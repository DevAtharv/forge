from __future__ import annotations

from io import BytesIO
import zipfile


def manifest_to_files(manifest: dict[str, dict[str, str | None] | str | None]) -> dict[str, str]:
    files: dict[str, str] = {}
    for path, value in (manifest or {}).items():
        if isinstance(value, dict):
            content = value.get("content") or ""
        else:
            content = value or ""
        files[str(path)] = str(content)
    return files


def build_project_bundle(*, project_slug: str, manifest: dict[str, dict[str, str | None] | str | None]) -> tuple[str, bytes]:
    bundle_name = f"{project_slug or 'forge-project'}.zip"
    files = manifest_to_files(manifest)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.writestr(path, files[path])
    return bundle_name, buffer.getvalue()
