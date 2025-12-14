# 👤 Self-updating GitHub profile

[![Build README](https://github.com/vemonet/vemonet/actions/workflows/build.yml/badge.svg)](https://github.com/vemonet/vemonet/actions/workflows/build.yml)

## Run locally

Create a ["classic" GitHub token](https://github.com/settings/tokens) with the `public_repo` permission 

```sh
GITHUB_TOKEN="ghp_###" uv run build_readme.py
```

> Inspired by https://github.com/simonw/simonw

## Lint

```sh
uvx ruff format
uvx ruff check --fix
```

