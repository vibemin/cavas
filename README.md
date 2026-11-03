# cavas

이미지에서 배경을 제거(누끼)하고 **투명 배경 PNG**로 저장하는 도구입니다.
[rembg](https://github.com/danielgatis/rembg)(U²-Net 등 AI 모델)를 사용합니다.

## 설치

```bash
pip install -e .
```

> 처음 실행할 때 모델 파일(약 170MB)이 `~/.u2net/`에 자동으로 다운로드됩니다.

## 저장 위치

기본적으로 결과물은 **iCloud Drive › 다운로드 › 8.캔버스** 안에 **날짜별 폴더**로 저장됩니다.

```
iCloud Drive/다운로드/8.캔버스/
├── 2026-11-03/
│   ├── photo_nobg.png
│   └── photo_nobg_2.png   ← 같은 이름이 있으면 번호가 붙어 덮어쓰지 않음
└── 2026-11-04/
```

- 실제 경로: `~/Library/Mobile Documents/com~apple~CloudDocs/Downloads/8.캔버스`
  (또는 `.../다운로드/8.캔버스`) — `8.캔버스` 폴더가 미리 있어야 합니다.
- 다른 곳을 기본 위치로 쓰려면 환경변수 `CAVAS_OUTPUT_DIR`를 설정하세요.
- `-o`로 직접 지정하거나 `--here`로 원본 옆에 저장할 수도 있습니다.

## 기본 동작

`cavas 이미지.jpg` 한 줄이면 다음이 모두 적용됩니다.

1. **배경 제거** — 테두리가 단색(흰 배경 일러스트·스티커 시트)이면 배경색을 지우는 방식,
   사진이면 AI 모델(rembg)을 자동으로 선택 (`--method color|ai`로 직접 지정 가능)
2. **물체별 분리** — 한 이미지에 물체가 여러 개면 하나씩 따로 저장 (`이미지_nobg_1.png`, `_2.png` …,
   위→아래, 왼쪽→오른쪽 순서). 별빛·김처럼 살짝 떨어진 조각은 가까운 물체에 붙음. 끄려면 `--no-split`
3. **크기 맞춤** — 각 결과의 긴 변(가로/세로 중 큰 쪽)을 3000px로. 바꾸려면 `-s 2000`, 원본 크기는 `-s 0`
4. **투명 배경 PNG**로 저장

## 사용법

```bash
# 파일 하나 → 8.캔버스/오늘날짜/photo_nobg.png
cavas photo.jpg

# 원본과 같은 폴더에 저장
cavas photo.jpg --here

# 저장 파일명 지정
cavas photo.jpg -o result.png

# 폴더 전체를 output/ 폴더로 일괄 처리 (하위 폴더 포함)
cavas ./images -o ./output -r

# 피사체 크기에 맞게 여백 자르기 (여백 20px)
cavas photo.jpg --crop --padding 20

# 머리카락 등 경계를 더 부드럽게
cavas portrait.jpg -a -m birefnet-portrait
```

| 옵션 | 설명 |
|---|---|
| `-o, --output` | 출력 파일(.png) 또는 폴더 (기본: 8.캔버스/오늘날짜) |
| `--here` | 원본 이미지와 같은 폴더에 저장 |
| `-s, --size` | 긴 변 크기 px (기본 3000, 0이면 원본 크기) |
| `--no-split` | 물체가 여러 개여도 한 장으로 저장 |
| `--method` | `auto`(기본) / `ai`(사진) / `color`(흰 배경 일러스트) |
| `-m, --model` | `u2net`(기본), `u2netp`, `u2net_human_seg`, `isnet-general-use`, `isnet-anime`, `silueta`, `birefnet-general`, `birefnet-portrait` |
| `-a, --alpha-matting` | 경계를 더 정교하게 처리 (느림) |
| `-c, --crop` | 투명 여백 잘라내기 (`-s 0`일 때만 필요, 그 외엔 자동) |
| `--padding N` | 피사체 주변에 투명 여백 N px |
| `--mask` | 흑백 마스크만 저장 |
| `-r, --recursive` | 하위 폴더까지 처리 |

지원 형식: png, jpg, jpeg, webp, bmp, tif, tiff

## Python에서 사용

```python
from PIL import Image
from cavas import remove_background

result = remove_background(Image.open("photo.jpg"))
result.save("photo_nobg.png")
```

## 테스트

```bash
pip install -e ".[dev]"
python -m pytest
```
