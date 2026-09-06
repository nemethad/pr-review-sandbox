# Project conventions

These are the conventions the review should apply to this repository, in
addition to generic security and correctness review.

## Python

- Database access goes through `app/repository/`. A raw SQL string or a driver
  call inside a handler is a finding regardless of how it is written.
- Configuration is read once in `app/config.py`. Do not read `os.environ`
  from handlers or repositories.

## Terraform

- Every resource carries `Project` and `Owner` tags. Cost allocation depends
  on it.
- Provider and module versions are pinned to an exact version, not a range.

## Exceptions

- Missing type hints in `scripts/` are not findings. That directory is
  deliberately throwaway.
- `tests/` may construct objects directly and may hardcode timestamps.
