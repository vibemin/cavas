"""배경 제거 핵심 로직."""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_MODEL = "u2net"

# macOS iCloud Drive 실제 경로
ICLOUD_DRIVE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
# Finder에서 '다운로드'로 보이는 폴더는 실제 이름이 Downloads일 수도, 다운로드일 수도 있다.
ICLOUD_CANDIDATES = [
    ICLOUD_DRIVE / "Downloads" / "8.캔버스",
    ICLOUD_DRIVE / "다운로드" / "8.캔버스",
]
ENV_OUTPUT_DIR = "CAVAS_OUTPUT_DIR"


def default_output_root() -> Path | None:
    """기본 저장 위치. 환경변수 CAVAS_OUTPUT_DIR > iCloud Drive/다운로드/8.캔버스 순."""
    env = os.environ.get(ENV_OUTPUT_DIR)
    if env:
        return Path(env).expanduser()
    for cand in ICLOUD_CANDIDATES:
        if cand.is_dir():
            return cand
    return None


def dated_dir(root: Path, day: date | None = None) -> Path:
    """root/YYYY-MM-DD 폴더 경로."""
    return root / (day or date.today()).isoformat()


def unique_path(path: Path, taken: set[Path] | frozenset[Path] = frozenset()) -> Path:
    """같은 이름의 파일이 있거나 taken에 있으면 _2, _3 ... 을 붙여 덮어쓰지 않게 한다."""
    cand, i = path, 2
    while cand.exists() or cand in taken:
        cand = path.with_name(f"{path.stem}_{i}{path.suffix}")
        i += 1
    return cand


@lru_cache(maxsize=4)
def _get_session(model: str):
    # rembg 임포트는 무거우므로 실제로 필요할 때만 불러온다.
    from rembg import new_session

    return new_session(model)


def detect_flat_background(image: Image.Image, tolerance: int = 12) -> tuple[int, int, int] | None:
    """테두리가 거의 한 가지 색이면(흰 배경 일러스트 등) 그 색을, 아니면 None을 돌려준다."""
    import numpy as np

    rgb = np.asarray(image.convert("RGB")).astype(np.int16)
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    color = np.median(border, axis=0)
    close = np.abs(border - color).max(axis=1) <= tolerance
    if close.mean() < 0.97:
        return None
    return tuple(int(c) for c in color)


def remove_flat_background(
    image: Image.Image,
    color: tuple[int, int, int],
    tolerance: int = 12,
    hole_min_ratio: float = 0.0004,
) -> Image.Image:
    """테두리와 이어진 단색 배경만 지운다 (물체 안쪽의 같은 색은 그대로 둔다).

    가장자리 픽셀은 배경색이 섞인 정도만큼 반투명하게 만들고 배경색을 빼서
    흰 테두리(헤일로)가 남지 않게 한다.
    """
    import numpy as np
    from scipy import ndimage

    rgba = np.asarray(image.convert("RGBA")).astype(np.float32)
    rgb, orig_a = rgba[..., :3], rgba[..., 3]
    bg = np.array(color, dtype=np.float32)
    diff = np.abs(rgb - bg).max(axis=2)

    near_bg = diff <= tolerance
    labels, _ = ndimage.label(near_bg)
    edge_labels = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, edge_labels[edge_labels > 0])

    # 물체 안에 갇힌 배경색 구멍(머그 손잡이 안쪽 등)도 투명하게.
    # 단, 작은 영역(눈 흰자)이나 안에 무언가 그려진 영역(얼굴)은 그림의 일부로 보고 남긴다.
    hole_min = hole_min_ratio * diff.size
    for i, slc in enumerate(ndimage.find_objects(labels), start=1):
        if slc is None or i in edge_labels:
            continue
        region = labels[slc] == i
        if region.sum() < hole_min:
            continue
        if (ndimage.binary_fill_holes(region) & ~region).any():
            continue
        background[slc] |= region

    alpha = np.where(background, 0.0, 1.0)
    # 배경과 맞닿은 2px 띠: 배경색과의 차이로 투명도 추정
    rim = ndimage.binary_dilation(background, iterations=2) & ~background
    soft = np.clip((diff - tolerance) / 60.0, 0.0, 1.0)
    alpha = np.where(rim, np.maximum(soft, 0.0), alpha)

    # 색 보정: C = a*F + (1-a)*B  →  F = (C - (1-a)*B) / a
    a3 = alpha[..., None]
    fg = np.where(a3 > 0, (rgb - (1 - a3) * bg) / np.maximum(a3, 1e-3), rgb)
    fg = np.clip(fg, 0, 255)
    out_a = alpha * orig_a
    out = np.dstack([fg, out_a]).round().astype(np.uint8)
    return Image.fromarray(out, mode="RGBA")


def remove_background(
    image: Image.Image,
    model: str = DEFAULT_MODEL,
    alpha_matting: bool = False,
    only_mask: bool = False,
    method: str = "auto",
) -> Image.Image:
    """PIL 이미지에서 배경을 제거해 RGBA 이미지(또는 마스크)를 반환한다.

    method:
      - "auto": 테두리가 단색(흰 배경 일러스트·스티커 시트 등)이면 "color", 아니면 "ai"
      - "ai":   AI 모델(rembg)로 피사체 인식 — 사진에 적합
      - "color": 테두리와 이어진 단색 배경을 지움 — 일러스트에 적합
    """
    image = ImageOps.exif_transpose(image)  # 휴대폰 사진 회전 정보 반영
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    if method in ("auto", "color"):
        color = detect_flat_background(image)
        if color is None and method == "color":
            color = (255, 255, 255)
        if color is not None:
            result = remove_flat_background(image, color)
            return result.getchannel("A") if only_mask else result

    from rembg import remove

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


def resize_long_side(image: Image.Image, size: int) -> Image.Image:
    """가로·세로 중 긴 쪽이 size(px)가 되도록 비율을 유지해 크기를 바꾼다."""
    w, h = image.size
    if size <= 0 or max(w, h) == size:
        return image
    scale = size / max(w, h)
    new = (max(1, round(w * scale)), max(1, round(h * scale)))
    return image.resize(new, Image.Resampling.LANCZOS)


def split_objects(image: Image.Image, min_area_ratio: float = 0.0002, attach_ratio: float = 0.05) -> list[Image.Image]:
    """투명 배경 이미지에서 떨어져 있는 피사체들을 각각 잘라 리스트로 돌려준다.

    큰 조각은 각각 하나의 물체가 되고, 작은 조각(별빛·김·반짝이처럼 살짝 떨어진 부분)은
    가장 가까운 큰 물체에 붙는다. 먼지 수준의 아주 작은 조각은 버린다.
    결과는 위→아래 줄 순서, 같은 줄에서는 왼쪽→오른쪽 순서다.
    """
    import numpy as np
    from scipy import ndimage

    alpha = np.asarray(image.getchannel("A"))
    solid = alpha > 10
    if not solid.any():
        return []

    # 안티앨리어싱으로 생긴 1~2px 틈은 이어 붙인다.
    labels, count = ndimage.label(ndimage.binary_dilation(solid, iterations=2))
    labels = np.where(solid, labels, 0)
    areas = np.bincount(labels.ravel(), minlength=count + 1)
    areas[0] = 0

    min_area = min_area_ratio * image.width * image.height
    real = [i for i in range(1, count + 1) if areas[i] >= min_area]
    if not real:
        return []
    ref = float(np.median([areas[i] for i in real]))
    big = {i for i in real if areas[i] >= 0.15 * ref}
    if not big:
        big = set(real)

    # 작은 조각 → 가장 가까운 큰 물체로 (일정 거리 이내일 때)
    big_mask = np.isin(labels, list(big))
    dist, (iy, ix) = ndimage.distance_transform_edt(~big_mask, return_indices=True)
    attach_dist = attach_ratio * (image.width ** 2 + image.height ** 2) ** 0.5
    owner = {i: i for i in big}
    for i in real:
        if i in big:
            continue
        ys, xs = np.nonzero(labels == i)
        k = int(np.argmin(dist[ys, xs]))
        if dist[ys[k], xs[k]] <= attach_dist:
            owner[i] = int(labels[iy[ys[k], xs[k]], ix[ys[k], xs[k]]])
        else:
            owner[i] = i  # 멀리 떨어진 작은 물체는 따로

    lut = np.zeros(count + 1, dtype=np.int32)
    for i, o in owner.items():
        lut[i] = o
    groups = lut[labels]

    parts = []
    for gid in sorted(set(owner.values())):
        keep = groups == gid
        ys, xs = np.nonzero(keep)
        top, bottom, left, right = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        a = np.where(keep, alpha, 0).astype(np.uint8)[top:bottom, left:right]
        part = image.crop((left, top, right, bottom))
        part.putalpha(Image.fromarray(a, mode="L"))
        parts.append(((top, left, bottom), part))

    # 위에서 아래로 줄을 나누고, 같은 줄 안에서는 왼쪽부터.
    # 다음 물체의 윗변이 현재 줄의 세로 중심보다 위에 있으면 같은 줄로 본다.
    parts.sort(key=lambda t: t[0][0])
    rows: list[list] = []
    for item in parts:
        top = item[0][0]
        if rows:
            row = rows[-1]
            center = sum((t[0][0] + t[0][2]) / 2 for t in row) / len(row)
            if top < center:
                row.append(item)
                continue
        rows.append([item])
    return [p for row in rows for _, p in sorted(row, key=lambda t: t[0][1])]


def _pad(image: Image.Image, padding: int) -> Image.Image:
    if padding <= 0:
        return image
    canvas = Image.new("RGBA", (image.width + 2 * padding, image.height + 2 * padding), (0, 0, 0, 0))
    canvas.paste(image, (padding, padding))
    return canvas


def process_file(
    src: Path,
    dst: Path,
    model: str = DEFAULT_MODEL,
    alpha_matting: bool = False,
    only_mask: bool = False,
    crop: bool = False,
    padding: int = 0,
    split: bool = False,
    size: int = 0,
    method: str = "auto",
) -> list[Path]:
    """이미지 파일 하나를 처리해 투명 배경 PNG로 저장하고, 저장된 경로 목록을 돌려준다.

    split=True 이면 물체마다 dst_1.png, dst_2.png ... 로 따로 저장한다.
    size>0 이면 각 결과의 긴 변을 size(px)로 맞춘다 (피사체에 맞게 잘라낸 뒤).
    """
    with Image.open(src) as img:
        img.load()
        result = remove_background(img, model=model, alpha_matting=alpha_matting,
                                   only_mask=only_mask, method=method)

    if only_mask:
        images = [result]
    elif split:
        images = split_objects(result) or [result]
    elif crop or size:
        images = [crop_to_content(result)]
    else:
        images = [result]

    if not only_mask:
        if size:
            # 여백을 포함한 최종 긴 변이 정확히 size가 되도록 여백만큼 빼고 맞춘다.
            images = [_pad(resize_long_side(im, max(1, size - 2 * padding)), padding) for im in images]
        elif padding and (crop or split):
            images = [_pad(im, padding) for im in images]

    dst.parent.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, im in enumerate(images, start=1):
        target = dst if len(images) == 1 else unique_path(dst.with_name(f"{dst.stem}_{i}.png"))
        im.save(target, format="PNG", compress_level=6)
        saved.append(target)
    return saved


def iter_images(path: Path, recursive: bool = False) -> Iterator[Path]:
    """경로가 파일이면 그 파일을, 폴더면 내부 이미지 파일들을 돌려준다."""
    if path.is_file():
        yield path
        return
    pattern = "**/*" if recursive else "*"
    for p in sorted(path.glob(pattern)):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and "_nobg" not in p.stem:
            yield p


def process_path(path: Path, out_dir: Path | None = None, recursive: bool = False, **kwargs) -> list[Path]:
    """파일 또는 폴더를 처리하고 저장된 파일 경로 목록을 반환한다."""
    saved = []
    for src in iter_images(path, recursive=recursive):
        target_dir = out_dir
        if out_dir is not None and path.is_dir():
            target_dir = out_dir / src.parent.relative_to(path)
        saved.extend(process_file(src, output_path_for(src, target_dir), **kwargs))
    return saved
