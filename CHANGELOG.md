# Changelog

## 0.2.0 - v0.2 alpha

### Added

- Added rebuild-oriented v0.2 outputs:
  - `feature-map.md`
  - `rebuild-spec.md`
  - `refactor-plan.md`
  - `module-boundaries.md`
  - `contract-gaps.md`
  - `spec-diff.md`
- Added feature-map facts that connect frontend API calls to backend routes, contracts, data hints, and tests when evidence exists.
- Added contract-gap facts for unknown request, response, status, error behavior, unmatched API calls, and unmatched backend routes.
- Added module-boundary facts for frontend, backend API, data layer, runtime config, tests, and shared source.
- Added `specforge update` support for comparing against the previous `.specforge/facts.json`.
- Added golden-style v0.2 output tests.
- Added support for UTF-8 BOM package manifests on Windows.

### Changed

- Bumped package version to `0.2.0`.
- Updated README with v0.2 usage, output guide, and reading order.
- Updated LLM handoff and implementation guide to prioritize feature maps, rebuild specs, contract gaps, and spec diffs.

### Notes

- v0.2 is still an alpha release.
- The scanner remains deterministic and does not use LLMs.
- Unknown behavior remains marked as `unknown` or `gap` instead of being inferred.

## 0.1.0 - Initial alpha

### Added

- Added evidence-first project scanning.
- Added full-stack skeleton outputs for backend, frontend, Java Web, data layer, runtime config, tests, gaps, and LLM handoff.
- Added `init`, `update`, `scan`, `render`, and `forge` CLI flows.
