# cavas

이미지에서 배경을 제거(누끼)하고 **투명 배경 PNG**로 저장하는 도구입니다.
[rembg](https://github.com/danielgatis/rembg)(U²-Net 등 AI 모델)를 사용합니다.

## 설치

```bash
pip install -e .
```

> 처음 실행할 때 모델 파일(약 170MB)이 `~/.u2net/`에 자동으로 다운로드됩니다.

## 사용법

```bash
# 파일 하나 → photo_nobg.png (원본과 같은 폴더)
cavas photo.jpg

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
| `-o, --output` | 출력 파일(.png) 또는 폴더 |
| `-m, --model` | `u2net`(기본), `u2netp`, `u2net_human_seg`, `isnet-general-use`, `isnet-anime`, `silueta`, `birefnet-general`, `birefnet-portrait` |
| `-a, --alpha-matting` | 경계를 더 정교하게 처리 (느림) |
| `-c, --crop` / `--padding N` | 투명 여백 잘라내기 |
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
