# Changelog

All notable changes to this project will be documented in this file.

## [0.3.2](https://github.com/altertable-ai/altertable-lakehouse-python/compare/altertable-lakehouse-v0.3.1...altertable-lakehouse-v0.3.2) (2026-07-24)


### Documentation

* sync community documents ([#19](https://github.com/altertable-ai/altertable-lakehouse-python/issues/19)) ([4a21043](https://github.com/altertable-ai/altertable-lakehouse-python/commit/4a21043496bec41fa6687e62f1d55a8c93f30bf3))

## [0.3.1](https://github.com/altertable-ai/altertable-lakehouse-python/compare/altertable-lakehouse-v0.3.0...altertable-lakehouse-v0.3.1) (2026-06-30)


### Bug Fixes

* **api:** expose upsert API ([#14](https://github.com/altertable-ai/altertable-lakehouse-python/issues/14)) ([ae07019](https://github.com/altertable-ai/altertable-lakehouse-python/commit/ae07019c6ba11c06f14fab0b6b327f2ea2bdcb6f))

## [0.3.0](https://github.com/altertable-ai/altertable-lakehouse-python/compare/altertable-lakehouse-v0.2.0...altertable-lakehouse-v0.3.0) (2026-05-27)


### Features

* **client:** allow configuring TLS verification ([#8](https://github.com/altertable-ai/altertable-lakehouse-python/issues/8)) ([0356ca3](https://github.com/altertable-ai/altertable-lakehouse-python/commit/0356ca3df0268f0b07d78fa2d14e44079850a13e)), closes [#7](https://github.com/altertable-ai/altertable-lakehouse-python/issues/7)

## [0.2.0](https://github.com/altertable-ai/altertable-lakehouse-python/compare/altertable-lakehouse-v0.1.0...altertable-lakehouse-v0.2.0) (2026-03-09)


### Features

* implement altertable-lakehouse SDK based on v0.9.0 specs ([#2](https://github.com/altertable-ai/altertable-lakehouse-python/issues/2)) ([ee85ba3](https://github.com/altertable-ai/altertable-lakehouse-python/commit/ee85ba323f0709f2192217455fbda4635acd5159))

## [0.1.0] - 2026-03-09
### Added
- Initial release of the Python SDK for the Altertable Lakehouse API.
- Implemented `append`, `upsert`, `query`, `query_all`, `validate`, `get_query`, and `cancel_query` methods.
- Full typing support with `pydantic` models.
