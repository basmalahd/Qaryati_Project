import pytest

from app.repositories.utils import escape_like
from app.schemas.common import build_page


@pytest.mark.parametrize("total, page_size, pages", [(0, 20, 0), (1, 20, 1), (20, 20, 1), (41, 20, 3)])
def test_build_page_counts_pages(total, page_size, pages):
    page = build_page([], total, 1, page_size)
    assert page["total_pages"] == pages and page["total"] == total


def test_escape_like_makes_wildcards_literal():
    assert escape_like("50%_x") == "50\\%\\_x"
    assert escape_like("a\\b") == "a\\\\b"
