# Architecture decision records

One decision per file, numbered, never rewritten. When a decision changes, the new
ADR supersedes the old one and both stay: the reasoning keeps its value after the
conclusion stops being true.

Format: context, decision, consequences ([Nygard](https://adr.github.io/)).
`Status` is `accepted`, `proposed` or `superseded by NNNN`.

Working notes, executed plans and closed investigations do **not** live here. The
code, its tests and the commit messages are their record; git history holds the rest.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-regatta-out-of-tree.md) | The regatta is an overlay that consumes the core unmodified | accepted |
| [0002](0002-ubuntu-native-reference-platform.md) | Ubuntu 24.04 native is the reference platform, containers elsewhere | accepted |
| [0003](0003-package-layout-and-audiences.md) | One uv package, three documents, invariants in `CLAUDE.md` | accepted |
| [0004](0004-hdrp-native-water-foam.md) | The wake is HDRP native water foam | accepted |
| [0005](0005-consumer-decoupling.md) | Bounded sender queue and per-topic QoS | proposed |
| [0006](0006-unity6-sole-source.md) | `LOTUSim-Unity6-modules` is the only source of Unity runtime code | accepted |
| [0007](0007-authored-sail-source.md) | The authored Blender sail source is kept, its export reproducible | accepted |
