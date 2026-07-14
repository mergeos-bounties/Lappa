#!/usr/bin/env python3
"""Lappa CLI - Robotics development toolkit."""

import click
from pathlib import Path

@click.group()
def cli():
    """Lappa - Robotics development toolkit."""
    pass

@cli.command()
@click.option('--path', '-p', default='.', help='Package directory')
def list_demos(path):
    """List demo packages with paths."""
    pkg_dir = Path(path) / 'packages'
    
    if not pkg_dir.exists():
        click.echo(f"No packages directory found at {pkg_dir}")
        return
    
    demos = list(pkg_dir.glob('*/demo'))
    
    if not demos:
        click.echo("No demo packages found.")
        return
    
    click.echo(f"Found {len(demos)} demo packages:\n")
    for demo in sorted(demos):
        name = demo.parent.name
        click.echo(f"  {name:20s} {demo}")

if __name__ == '__main__':
    cli()
