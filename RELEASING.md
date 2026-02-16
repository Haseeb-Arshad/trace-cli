# Releasing TraceCLI to PyPI

This guide explains how to package and release `TraceCLI` to the Python Package Index (PyPI).

## Prerequisites

You will need `build` and `twine` installed:

```powershell
pip install --upgrade build twine
```

## Step 1: Update Version

Ensure the version in `pyproject.toml` is correct:

```toml
[project]
version = "0.1.2"
```

## Step 2: Build the Package

Run this command from the project root:

```powershell
python -m build
```

This will create a `dist/` directory with `.tar.gz` and `.whl` files.

## Step 3: Check the Build

Verify that the long description and metadata are correct:

```powershell
twine check dist/*
```

## Step 4: Upload to TestPyPI (Optional but Recommended)

It's good practice to try TestPyPI first:

```powershell
twine upload --repository testpypi dist/*
```

## Step 5: Upload to PyPI

When ready for the real deal:

```powershell
twine upload dist/*
```

> [!NOTE]  
> You will need a PyPI account and an API token. When prompted for a username, use `__token__` and use your API token as the password.

## Installation for Users

Once uploaded, users can install it via:

```powershell
pip install tracecli
```
