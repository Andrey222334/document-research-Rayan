import pytest

from app.import_csv import read_documents


def test_csv_multiline_and_rubrics(tmp_path):
    path = tmp_path / "posts.csv"
    path.write_text('text,created_date,rubrics\n"первая\nвторая",2019-07-25 12:42:13,"[\'один\', \'два\']"\n', encoding="utf-8-sig", newline="")
    document, = read_documents(path)
    assert document.id == 1
    assert document.text == "первая\nвторая"
    assert document.rubrics == ["один", "два"]
    assert document.created_date.isoformat() == "2019-07-25T12:42:13+00:00"


@pytest.mark.parametrize("rubrics", ["{}", "['ok', 1]", "__import__('os').getcwd()"])
def test_invalid_rubrics(tmp_path, rubrics):
    import csv

    path = tmp_path / "posts.csv"
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["text", "created_date", "rubrics"])
        writer.writerow(["текст", "2020-01-01", rubrics])
    with pytest.raises(ValueError, match="record 1"):
        read_documents(path)
