"""Tests for list demos command."""

from click.testing import CliRunner
from lappa.cli import cli

def test_list_demos_empty(tmp_path):
    """Test list demos with no packages."""
    runner = CliRunner()
    result = runner.invoke(cli, ['list-demos', '--path', str(tmp_path)])
    assert result.exit_code == 0
    assert 'No packages directory' in result.output

def test_list_demos_with_packages(tmp_path):
    """Test list demos with packages."""
    pkg_dir = tmp_path / 'packages' / 'my_robot' / 'demo'
    pkg_dir.mkdir(parents=True)
    
    runner = CliRunner()
    result = runner.invoke(cli, ['list-demos', '--path', str(tmp_path)])
    assert result.exit_code == 0
    assert 'my_robot' in result.output
