from pathlib import Path

from PIL import Image

from cavas.core import crop_to_content, iter_images, output_path_for


def test_output_path_for_default_and_dir(tmp_path):
    src = tmp_path / "cat.jpg"
    assert output_path_for(src, None) == tmp_path / "cat_nobg.png"
    assert output_path_for(src, Path("out")) == Path("out/cat_nobg.png")


def test_crop_to_content():
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (20, 30, 40, 60))
    assert crop_to_content(img).size == (20, 30)
    assert crop_to_content(img, padding=5).size == (30, 40)


def test_iter_images_skips_outputs_and_non_images(tmp_path):
    for name in ["a.jpg", "b.PNG", "a_nobg.png", "notes.txt"]:
        (tmp_path / name).write_bytes(b"")
    found = [p.name for p in iter_images(tmp_path)]
    assert found == ["a.jpg", "b.PNG"]


def test_unique_path(tmp_path):
    from cavas.core import unique_path

    p = tmp_path / "a_nobg.png"
    assert unique_path(p) == p
    p.write_bytes(b"")
    assert unique_path(p) == tmp_path / "a_nobg_2.png"
    assert unique_path(p, {tmp_path / "a_nobg_2.png"}) == tmp_path / "a_nobg_3.png"


def test_default_output_root_and_dated_dir(tmp_path, monkeypatch):
    from datetime import date

    from cavas import core

    monkeypatch.setenv(core.ENV_OUTPUT_DIR, str(tmp_path))
    assert core.default_output_root() == tmp_path
    assert core.dated_dir(tmp_path, date(2026, 11, 3)) == tmp_path / "2026-11-03"

    monkeypatch.delenv(core.ENV_OUTPUT_DIR)
    icloud = tmp_path / "다운로드" / "8.캔버스"
    monkeypatch.setattr(core, "ICLOUD_CANDIDATES", [tmp_path / "Downloads" / "8.캔버스", icloud])
    assert core.default_output_root() is None
    icloud.mkdir(parents=True)
    assert core.default_output_root() == icloud


def test_resize_long_side():
    from cavas.core import resize_long_side

    assert resize_long_side(Image.new("RGBA", (400, 200)), 3000).size == (3000, 1500)
    assert resize_long_side(Image.new("RGBA", (1000, 4000)), 3000).size == (750, 3000)


def test_split_objects_separates_and_orders():
    from cavas.core import split_objects

    img = Image.new("RGBA", (1000, 500), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (600, 100, 900, 400))   # 오른쪽 큰 물체
    img.paste((0, 255, 0, 255), (100, 150, 300, 350))   # 왼쪽 물체
    img.paste((0, 0, 255, 255), (5, 5, 7, 7))           # 노이즈 (버려져야 함)
    parts = split_objects(img)
    assert [p.size for p in parts] == [(200, 200), (300, 300)]
    assert parts[0].getpixel((100, 100)) == (0, 255, 0, 255)
