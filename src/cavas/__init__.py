"""cavas: 이미지 누끼 따기 (배경 제거 → 투명 PNG)."""

from .core import SUPPORTED_EXTENSIONS, remove_background, process_file, process_path

__all__ = ["SUPPORTED_EXTENSIONS", "remove_background", "process_file", "process_path"]
__version__ = "0.1.0"
