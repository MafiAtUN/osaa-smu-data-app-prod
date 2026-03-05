"""Tests for code validation in app.services.llm_service."""

import pytest

from app.services.llm_service import clean_import_statements, validate_code


class TestValidateCode:
    def test_safe_code_passes(self):
        validate_code("output = df.groupby('Country').mean()")

    def test_unsafe_import_os(self):
        with pytest.raises(ValueError, match="Unsafe keyword"):
            validate_code("import os\nos.system('rm -rf /')")

    def test_unsafe_eval(self):
        with pytest.raises(ValueError, match="Unsafe keyword"):
            validate_code("result = eval('1+1')")

    def test_unsafe_exec(self):
        with pytest.raises(ValueError, match="Unsafe keyword"):
            validate_code("exec('print(1)')")

    def test_unsafe_dunder(self):
        with pytest.raises(ValueError, match="Unsafe keyword"):
            validate_code("x = __import__('os')")

    def test_safe_pandas_import(self):
        validate_code("import pandas as pd\noutput = pd.DataFrame()")

    def test_safe_numpy_import(self):
        validate_code("import numpy as np\noutput = np.array([1,2,3])")


class TestCleanImports:
    def test_removes_import(self):
        code = "import pandas as pd\nimport numpy as np\noutput = df.head()"
        cleaned = clean_import_statements(code)
        assert "import pandas" not in cleaned
        assert "output = df.head()" in cleaned

    def test_removes_from_import(self):
        code = "from pandas import DataFrame\noutput = DataFrame()"
        cleaned = clean_import_statements(code)
        assert "from pandas" not in cleaned
        assert "output = DataFrame()" in cleaned

    def test_keeps_non_import_lines(self):
        code = "x = 1\ny = 2\noutput = x + y"
        assert clean_import_statements(code) == code
