#!/usr/bin/env python3
"""
Demo Package Template Generator for Lappa

Scaffolds a minimal ament package under demos/ directory.
"""

import argparse
import os
import sys
from pathlib import Path


PACKAGE_XML_TEMPLATE = """<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>{package_name}</name>
  <version>0.0.1</version>
  <description>{description}</description>
  <maintainer email="dev@mergeos.com">MergeOS Developer</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>

  <test_depend>ament_lint_auto</test_depend>
  <test_depend>ament_lint_common</test_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
"""

CMAKELISTS_TEMPLATE = """cmake_minimum_required(VERSION 3.8)
project({package_name})

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
"""

README_TEMPLATE = """# {package_name}

{description}

## Building

```bash
colcon build --packages-select {package_name}
```

## Testing

```bash
colcon test --packages-select {package_name}
```
"""


def create_package(package_name: str, description: str, demos_dir: Path) -> None:
    """Create a minimal ament package structure."""
    
    package_path = demos_dir / package_name
    
    if package_path.exists():
        print(f"Error: Package directory already exists: {package_path}", file=sys.stderr)
        sys.exit(1)
    
    # Create package directory structure
    package_path.mkdir(parents=True, exist_ok=True)
    (package_path / "src").mkdir(exist_ok=True)
    (package_path / "include" / package_name).mkdir(parents=True, exist_ok=True)
    
    # Write package.xml
    package_xml = PACKAGE_XML_TEMPLATE.format(
        package_name=package_name,
        description=description
    )
    (package_path / "package.xml").write_text(package_xml)
    
    # Write CMakeLists.txt
    cmakelists = CMAKELISTS_TEMPLATE.format(package_name=package_name)
    (package_path / "CMakeLists.txt").write_text(cmakelists)
    
    # Write README.md
    readme = README_TEMPLATE.format(
        package_name=package_name,
        description=description
    )
    (package_path / "README.md").write_text(readme)
    
    print(f"Successfully created package: {package_name}")
    print(f"Location: {package_path}")
    print("\nNext steps:")
    print(f"  cd {package_path}")
    print("  # Add your source files to src/")
    print("  # Update CMakeLists.txt to build your targets")
    print(f"  colcon build --packages-select {package_name}")


def find_demos_dir() -> Path:
    """Find the demos/ directory in the repository."""
    current = Path.cwd()
    
    # Check if we're already in demos/
    if current.name == "demos" and current.is_dir():
        return current
    
    # Check if demos/ exists in current directory
    demos = current / "demos"
    if demos.is_dir():
        return demos
    
    # Search up the directory tree for demos/
    for parent in current.parents:
        demos = parent / "demos"
        if demos.is_dir():
            return demos
    
    # Create demos/ in current directory as fallback
    demos = current / "demos"
    demos.mkdir(exist_ok=True)
    return demos


def main():
    parser = argparse.ArgumentParser(
        description="Generate a minimal ament package template under demos/"
    )
    parser.add_argument(
        "package_name",
        help="Name of the package to create"
    )
    parser.add_argument(
        "-d", "--description",
        default="Demo package",
        help="Package description (default: 'Demo package')"
    )
    parser.add_argument(
        "--demos-dir",
        type=Path,
        help="Path to demos directory (default: auto-detect)"
    )
    
    args = parser.parse_args()
    
    # Validate package name
    package_name = args.package_name
    if not package_name.replace("_", "").isalnum():
        print("Error: Package name must contain only alphanumeric characters and underscores", file=sys.stderr)
        sys.exit(1)
    
    # Find or use specified demos directory
    demos_dir = args.demos_dir if args.demos_dir else find_demos_dir()
    
    if not demos_dir.exists():
        print(f"Error: Demos directory does not exist: {demos_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Create the package
    create_package(package_name, args.description, demos_dir)


if __name__ == "__main__":
    main()