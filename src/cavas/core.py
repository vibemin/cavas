"""배경 제거 핵심 로직."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_MODEL = "u2net"


@lru_cache(maxsize=4)
def _get_session(model: str):
    # rembg 임포트는 무거우므로 실제로 필요할 때만 불러온다.
    from rembg import new_session

    return new_session(model)


def remove_background(
    image: Image.Image,
    model: str = DEFAULT_MODEL,
    alpha_matting: bool = False,
    only_mask: bool = False,
) -> Image.Image:
    """PIL 이미지에서 배경을 제거해 RGBA 이미지(또는 마스크)를 반환한다."""
    from rembg import remove

    image = ImageOps.exif_transpose(image)  # 휴대폰 사진 회전 정보 반영
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    result = remove(
        image,
        session=_get_session(model),
        alpha_matting=alpha_matting,
        only_mask=only_mask,
    )
    return result if only_mask else result.convert("RGBA")


def crop_to_content(image: Image.Image, padding: int = 0) -> Image.Image:
    """투명하지 않은 영역만 남기고 잘라낸다."""
    bbox = image.getchannel("A").getbbox() if image.mode == "RGBA" else image.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    left = max(left - padding, 0)
    top = max(top - padding, 0)
    right = min(right + padding, image.width)
    bottom = min(bottom + padding, image.height)
    return image.crop((left, top, right, bottom))


def output_path_for(src: Path, out_dir: Path | None, suffix: str = "_nobg") -> Path:
    target_dir = out_dir if out_dir is not None else src.parent
    return target_dir / f"{src.stem}{suffix}.png"


def process_file(
    src: Path,
    dst: Path,
    model: str = DEFAULT_MODEL,
    alpha_matting: bool = False,
    only_mask: bool = False,
    crop: bool = False,
    padding: int = 0,
) -> Path:
    """이미지 파일 하나를 처리해 투명 배경 PNG로 저장한다."""
    with Image.open(src) as img:
        img.load()
        result = remove_background(img, model=model, alpha_matting=alpha_matting, only_mask=only_mask)
    if crop and not only_mask:
        result = crop_to_content(result, padding=padding)
    dst.parent.mkdir(parents=True, exist_ok=True)
    result.save(dst, format="PNG", optimize=True)
    return dst


def iter_images(path: Path, recursive: bool = False) -> Iterator[Path]:
    """경로가 파일이면 그 파일을, 폴더면 내부 이미지 파일들을 돌려준다."""
    if path.is_file():
        yield path
        return
    pattern = "**/*" if recursive else "*"
    for p in sorted(path.glob(pattern)):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and not p.stem.endswith("_nobg"):
            yield p


def process_path(path: Path, out_dir: Path | None = None, recursive: bool = False, **kwargs) -> list[Path]:
    """파일 또는 폴더를 처리하고 저장된 파일 경로 목록을 반환한다."""
    saved = []
    for src in iter_images(path, recursive=recursive):
        target_dir = out_dir
        if out_dir is not None and path.is_dir():
            target_dir = out_dir / src.parent.relative_to(path)
        saved.append(process_file(src, output_path_for(src, target_dir), **kwargs))
    return saved
