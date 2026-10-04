import re

import shorts


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", shorts.__version__)
