"""명령줄 인터페이스."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import DEFAULT_MODEL, iter_images, output_path_for, process_file

MODELS = [
    "u2net",              # 범용 (기본)
    "u2netp",             # 가벼운 버전
    "u2net_human_seg",    # 사람
    "isnet-general-use",  # 범용, 경계가 더 정교함
    "isnet-anime",        # 애니메이션/일러스트
    "silueta",
    "birefnet-general",   # 고품질 (느림)
    "birefnet-portrait",  # 인물 고품질
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cavas",
        description="이미지 배경을 제거(누끼)하고 투명 배경 PNG로 저장합니다.",
    )
    p.add_argument("inputs", nargs="+", type=Path, help="이미지 파일 또는 폴더")
    p.add_argument("-o", "--output", type=Path,
                   help="출력 경로. 입력이 파일 하나면 .png 파일 경로도 가능, 아니면 폴더 (기본: 원본 옆에 *_nobg.png)")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL, choices=MODELS, help=f"사용할 모델 (기본: {DEFAULT_MODEL})")
    p.add_argument("-a", "--alpha-matting", action="store_true", help="머리카락 등 경계를 더 부드럽게 (느림)")
    p.add_argument("-c", "--crop", action="store_true", help="피사체 크기에 맞게 여백 잘라내기")
    p.add_argument("--padding", type=int, default=0, help="--crop 사용 시 남길 여백(px)")
    p.add_argument("--mask", action="store_true", help="결과 대신 흑백 마스크만 저장")
    p.add_argument("-r", "--recursive", action="store_true", help="폴더 하위까지 처리")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    opts = dict(model=args.model, alpha_matting=args.alpha_matting,
                only_mask=args.mask, crop=args.crop, padding=args.padding)

    jobs: list[tuple[Path, Path]] = []
    for inp in args.inputs:
        if not inp.exists():
            print(f"[오류] 경로를 찾을 수 없음: {inp}", file=sys.stderr)
            return 1
        single_file_target = (
            len(args.inputs) == 1 and inp.is_file()
            and args.output is not None and args.output.suffix.lower() == ".png"
        )
        for src in iter_images(inp, recursive=args.recursive):
            if single_file_target:
                dst = args.output
            else:
                out_dir = args.output
                if out_dir is not None and inp.is_dir():
                    out_dir = out_dir / src.parent.relative_to(inp)
                dst = output_path_for(src, out_dir)
            jobs.append((src, dst))

    if not jobs:
        print("[알림] 처리할 이미지가 없습니다.", file=sys.stderr)
        return 1

    failed = 0
    for i, (src, dst) in enumerate(jobs, 1):
        try:
            process_file(src, dst, **opts)
            print(f"[{i}/{len(jobs)}] {src} -> {dst}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[{i}/{len(jobs)}] 실패: {src} ({e})", file=sys.stderr)

    print(f"완료: {len(jobs) - failed}개 성공, {failed}개 실패")
    return 1 if failed else 0
