import pytest
from app.services.terraform_parser import TerraformParser


class TestEscapeUnescape:

    @pytest.fixture
    def parser(self, tmp_terraform_dir):
        return TerraformParser(str(tmp_terraform_dir))

    @pytest.mark.parametrize("raw,escaped", [
        ('hello', 'hello'),
        ('line1\nline2', 'line1\\nline2'),
        ('say "hi"', 'say \\"hi\\"'),
        ('back\\slash', 'back\\\\slash'),
        ('tab\r', 'tab\\r'),
    ])
    def test_escape_roundtrip(self, parser, raw, escaped):
        assert parser._escape_tfvars_value(raw) == escaped
        assert parser._unescape_tfvars_value(escaped) == raw


class TestReadTfvarsToMap:

    @pytest.fixture
    def parser(self, tmp_terraform_dir):
        return TerraformParser(str(tmp_terraform_dir))

    def test_reads_simple_key_values(self, parser, tmp_path):
        tfvars = tmp_path / "test.tfvars"
        tfvars.write_text('region = "us-west-2"\nname_prefix = "myapp"\n')
        result = parser._read_tfvars_to_map(tfvars)
        assert result == {"region": "us-west-2", "name_prefix": "myapp"}

    def test_skips_comments_and_blanks(self, parser, tmp_path):
        tfvars = tmp_path / "test.tfvars"
        tfvars.write_text('# comment\n\nregion = "us-east-1"\n')
        result = parser._read_tfvars_to_map(tfvars)
        assert result == {"region": "us-east-1"}

    def test_handles_unquoted_values(self, parser, tmp_path):
        tfvars = tmp_path / "test.tfvars"
        tfvars.write_text("count = 3\nenabled = true\n")
        result = parser._read_tfvars_to_map(tfvars)
        assert result["count"] == "3"
        assert result["enabled"] == "true"

    def test_strips_inline_comments(self, parser, tmp_path):
        tfvars = tmp_path / "test.tfvars"
        tfvars.write_text('count = 5 # five\n')
        result = parser._read_tfvars_to_map(tfvars)
        assert result["count"] == "5"

    def test_handles_escaped_quotes(self, parser, tmp_path):
        tfvars = tmp_path / "test.tfvars"
        tfvars.write_text('desc = "say \\"hi\\""\n')
        result = parser._read_tfvars_to_map(tfvars)
        assert result["desc"] == 'say "hi"'

    def test_returns_empty_for_missing_file(self, parser, tmp_path):
        assert parser._read_tfvars_to_map(tmp_path / "nope.tfvars") == {}


class TestWriteTfvarsLine:

    @pytest.fixture
    def parser(self, tmp_terraform_dir):
        return TerraformParser(str(tmp_terraform_dir))

    def test_creates_file_if_missing(self, parser, tmp_path):
        tfvars = tmp_path / "new.tfvars"
        parser._write_tfvars_line(tfvars, "region", "us-west-2")
        assert tfvars.read_text() == 'region = "us-west-2"\n'

    def test_updates_existing_variable(self, parser, tmp_path):
        tfvars = tmp_path / "test.tfvars"
        tfvars.write_text('region = "us-east-1"\nname = "old"\n')
        parser._write_tfvars_line(tfvars, "region", "ap-northeast-2")
        content = tfvars.read_text()
        assert 'region = "ap-northeast-2"' in content
        assert 'name = "old"' in content
        assert "us-east-1" not in content

    def test_appends_new_variable(self, parser, tmp_path):
        tfvars = tmp_path / "test.tfvars"
        tfvars.write_text('region = "us-east-1"\n')
        parser._write_tfvars_line(tfvars, "name", "myapp")
        content = tfvars.read_text()
        assert 'region = "us-east-1"' in content
        assert 'name = "myapp"' in content

    def test_escapes_special_characters(self, parser, tmp_path):
        tfvars = tmp_path / "test.tfvars"
        parser._write_tfvars_line(tfvars, "desc", 'line1\nline2')
        content = tfvars.read_text()
        assert 'desc = "line1\\nline2"' in content
