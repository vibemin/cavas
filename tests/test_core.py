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
