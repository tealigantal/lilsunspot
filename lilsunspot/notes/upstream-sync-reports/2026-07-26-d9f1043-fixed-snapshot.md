# Hermes upstream fixed-target snapshot report

Date: 2026-07-26
Task: `LIL-HERMES-UPSTREAM-FULL-SYNC-01`

## Scope and status

This report fixes the official target and records a read-only source snapshot for capability discovery. The archive began as operator-recorded GitHub REST download evidence; its paths and normalized contents were later matched against the fetched official commit object. The archive itself remains non-merge evidence. The official commit object is now present locally at `upstream/sync-d9f1043` and is the sole allowed merge source.

## Fixed official target

- Official repository: `NousResearch/hermes-agent`.
- Target branch at observation time: `main`.
- Fixed target SHA: `d9f1043c3337818b1f29224a7deb5bbb17402370`.
- Commit author/committer time: `2026-07-26T08:26:39Z`.
- Subject: `Merge pull request #71840 from NousResearch/bb/status-stack-scope`.
- Official commit URL: `https://github.com/NousResearch/hermes-agent/commit/d9f1043c3337818b1f29224a7deb5bbb17402370`.
- Latest release observed: `v2026.7.20`, published `2026-07-20T18:35:55Z`.
- Source: authenticated GitHub REST API through the locally configured `gh` account; no credential value was recorded.

The target is fixed for this sync run. A later movement of official `main` belongs to a future sync run.

## Baselines and ancestry

- lilsunspot branch starting point: `a8880fad7094726b2c3e3ec34218e588c7d8bf19`.
- Recorded official base: `2b768535c9ba2a8d3b2c23fae1ee3a2f827f7f49`.
- Fetch-before local cache only: `upstream/main@f1345290edb87a5da7b28288dc39c46b0be79313`.
- GitHub compare status from the recorded base to the fixed target: `ahead`.
- Official compare merge base: `2b768535c9ba2a8d3b2c23fae1ee3a2f827f7f49`.
- Ahead / behind: `8485 / 0` commits.

The target Git objects were later fetched successfully. Local verification confirms merge base `2b768535c9ba2a8d3b2c23fae1ee3a2f827f7f49`, `git merge-base --is-ancestor` exit 0, and left/right counts `0 / 8485`.

## Git transfer state

Repeated initial full, main-only, `ls-remote`, filtered, OpenSSL-backed, and fixed-SHA smart-HTTP requests either reset or could not connect to GitHub port 443. A later retry succeeded. The fixed object is persisted at `refs/remotes/upstream/sync-d9f1043`; `upstream/main` was not moved. No merge, source checkout, or `UPSTREAM_COMMIT.txt` update was performed.

## Fixed source snapshot

- Download endpoint: official GitHub tarball API pinned to the fixed SHA.
- Ignored archive: `ignored/hermes-upstream-snapshot/d9f1043c3337818b1f29224a7deb5bbb17402370.tar.gz`.
- Archive bytes: `77085957`.
- Archive SHA-256: `E12EF7FBD2A3FEA01F434430B184D20F86CD9FAAA61499A8414A548A92E01DBA`.
- Version-controlled operator record: `lilsunspot/resources/hermes_upstream_snapshot_record.json`.
- Expected and observed unique archive root: `NousResearch-hermes-agent-d9f1043`.
- Extracted tree SHA-256: `CC6ABD19FE9B5A1727FF4D57C1F850E50AD2ABFF05ADAA32D539CF8F2D313205` across 7,460 files.
- Extracted source: ignored and not part of the lilsunspot working-tree diff.
- Synthetic audit-only commit inside the ignored snapshot: `8788a919b0babfa4bc2315d8ce6f70b82596f8cf`.

The synthetic commit exists only to compare two source trees locally. It must never be used as the official target or merged into lilsunspot.

## Tree-size comparison

Comparing the recorded official base object with the fetched official target object produced:

- `6162 files changed`.
- `1347582 insertions`.
- `118739 deletions`.

Largest changed top-level groups by file count:

| Group | Files |
| --- | ---: |
| `tests/` | 2119 |
| `apps/` | 1266 |
| `website/` | 679 |
| `optional-skills/` | 340 |
| `ui-tui/` | 229 |
| `skills/` | 210 |
| `contributors/` | 208 |
| `hermes_cli/` | 206 |
| `plugins/` | 198 |
| `agent/` | 149 |
| `web/` | 132 |
| `tools/` | 99 |
| `gateway/` | 71 |

This scale prohibits a blind merge-and-test approach. Capability ownership and package reachability must be inventoried before conflict resolution.

The official Git tree and GitHub tarball contain the same 7,460 paths. Windows `git archive` produced CRLF for 7,285 text files while the GitHub tarball used LF; after CRLF/LF normalization, content differences are zero. The synthetic snapshot commit has a different tree ID and remains audit-only. The official fetched commit object is the sole merge source.

## Initial machine-enumerated contract deltas

The existing AST audit logic was run directly against the fixed snapshot instead of the stale remote ref.

- Current lilsunspot checkout: 56 toolsets, 26 configurable toolsets, 60 top-level `DEFAULT_CONFIG` keys.
- Fixed target: 57 toolsets, 25 configurable toolsets, 77 top-level `DEFAULT_CONFIG` keys.
- Toolsets present in target but absent in current checkout: `coding`, `context_engine`, `project`.
- Toolsets present in current checkout but absent in target: `messaging`, `moa`.
- Configurable target entry absent locally: `context_engine`.
- Configurable local entries absent from target: `messaging`, `moa`.
- New target top-level config keys: `computer_use`, `context_file_max_chars`, `desktop`, `gateway`, `max_concurrent_sessions`, `max_live_sessions`, `mcp`, `mcp_discovery_timeout`, `moa`, `paste_collapse_char_threshold`, `paste_collapse_threshold`, `paste_collapse_threshold_fallback`, `platform_hints`, `proxy`, `streaming`, `tools`, `vertex`.

Directory enumeration also found initial movement rather than simple additions:

- Built-in skills: current 90, target 69; several skills moved to optional/plugin ownership.
- Optional skills: current 81, target 111.
- Plugin root directories: current 17, target 18; target adds `cron_providers`, `dashboard_auth`, and `security-guidance` roots while older example/cache roots are absent.
- Gateway file names show platform movement between core and plugins, so raw directory counts are not a capability count and must not be used as parity evidence.

## Authoritative enumeration points in the fixed target

The fixed target exposes the following machine-readable or runtime enumeration surfaces. These are the sources the full parity manifest must consume instead of maintaining hand-written snapshots.

- Agent/runtime: console scripts in `pyproject.toml`; `run_agent.AIAgent`; `agent/conversation_loop.py`; transport modules in `agent/transports/`; gateway entry in `gateway/run.py`; MCP server in `mcp_serve.py`.
- Providers/models: `providers.register_provider()` / `list_providers()` and bundled `plugins/model-providers/*/plugin.yaml`; runtime model capabilities through `agent/models_dev.py`; final context resolution in `agent/model_metadata.py`.
- Tools: `tools/registry.py` and its AST/runtime discovery of `registry.register(...)`; `model_tools.py` is the consumer. Static enumeration found 74 named built-in registrations: 69 carry a literal toolset and 5 Yuanbao registrations leave toolset ownership empty at the call site. The manifest marks this scan `complete: false` and records 2 skipped dynamic registration calls; plugin and runtime MCP tools are additional dynamic surfaces.
- Plugins: `hermes_cli/plugins.py` and all `plugins/**/plugin.yaml`. The target contains 93 manifests: 32 model-provider, 20 platform, 8 memory, 8 web, 7 image-generation, 4 dashboard-auth, 3 browser, 3 video-generation, 2 observability, and smaller categories.
- Skills: `skills/**/SKILL.md` (69) and `optional-skills/**/SKILL.md` (111), with index generation in `scripts/build_skills_index.py`.
- MCP catalog: `optional-mcps/**/manifest.yaml` (4: Blender, Linear, n8n, Unreal Engine), runtime in `tools/mcp_tool.py`, and CLI in `hermes_cli/subcommands/mcp.py`.
- Memory: `agent/memory_provider.py`, `agent/memory_manager.py`, and `plugins/memory/` (8 bundled providers: byterover, hindsight, holographic, honcho, mem0, openviking, retaindb, supermemory).
- Sessions: canonical agent persistence in `hermes_state.SessionDB` / `state.db`; gateway route/cache state in `gateway/session.py`. A `sessions.json` route index must not be mistaken for the canonical conversation database.
- Cron: `cron/jobs.py`, `cron/executions.py`, `cron/scheduler.py`, `cron/scheduler_provider.py`, plus `plugins/cron_providers/chronos` and automation blueprint/suggestion catalogs.
- Gateways: `gateway/platform_registry.platform_registry` and plugin manifests. AST enumeration found 9 classes that directly inherit `BasePlatformAdapter`; helper modules are excluded. The target also has 20 platform plugin manifests.
- Operator surfaces: CLI command registry in `hermes_cli/main.py`; Web route registry in `web/src/App.tsx`; TUI slash/widget registries in `ui-tui/src/app/slash/registry.ts` and `ui-tui/src/sdk/registry.ts`.
- Packaging: Python console/package metadata in `pyproject.toml`; root npm workspace; Electron desktop under `apps/desktop/`; Tauri bootstrap installer under `apps/bootstrap-installer/`; Nix, Docker and platform installer scripts.

Notable target capabilities absent or structurally different from the current product baseline include the official Electron desktop and bootstrap installer, ACP/Codex transports, MoA, learning graph, pets, billing/subscription/credits, verification and turn finalization, project/delegation/desktop-terminal tools, provider and platform plugins, expanded Web administration, extensible TUI widgets, and a native CJK FTS5 extension. Presence in the snapshot is inventory evidence only; installed lilsunspot reachability remains unverified.

## Immediate adapter implications

1. `lilsunspot/daemon/upstream_audit.py` is not sufficient for this target: it reads a Git ref and only checks three shallow registries. It would currently report the stale cached ref.
2. The lilsunspot capability graph must account for official removals/moves as well as additions; keeping `messaging` or `moa` as permanent legacy toolsets would create a compatibility fork.
3. `context_engine`, `coding`, `project`, the expanded config schema, plugin-provided platforms, and skill ownership moves require explicit owner, package, configuration, safety, and installed-app reachability rows.
4. PyInstaller/Tauri packaging must enumerate dynamic plugins, skills, tools and resource files from the fixed target instead of relying only on imports seen by the current sidecar spec.

## Independent adapter and packaging review

The independent read-only review classified these as the first merge blockers.

### P0

1. **Installed sidecar packaging is incomplete for the target.** `scripts/build_lilsunspotd_sidecar.ps1` collects only a narrow set of current modules. The target publishes or dynamically discovers `gateway.*`, `tui_gateway.*`, `cron.*`, `acp_adapter.*`, `plugins.*`, `providers.*` and gateway assets, but the current sidecar does not collect those complete packages/resources. Source imports or pytest cannot prove installed-app availability.
2. **The product provider registry truncates the official provider/transport surface.** `lilsunspot/daemon/providers.py`, `lilsunspot/resources/provider_registry.yaml` and the current save path require one of six product records and an `env_key`. This blocks target OAuth, credential-pool, named custom, Azure, Bedrock, Vertex, Codex and ACP transport paths. The target `AIAgent` also accepts transport/provider arguments not passed by the current `agent_runner.py`.
3. **Capability enumeration omits plugin toolsets.** `lilsunspot/daemon/capabilities.py` reads static `CONFIGURABLE_TOOLSETS`, while the target official path is `_get_effective_configurable_toolsets()` after plugin discovery. The current capability graph, save allowlist and agent configuration would silently omit plugin-provided toolsets.

### P1

1. `lilsunspot/daemon/chat_client.py` directly calls private `models_dev` and `image_routing` symbols. They still exist, but target vision resolution adds `requested_provider` semantics, so named custom providers can be misclassified. These calls need one narrow adapter and behavior contract tests.
2. `lilsunspot/daemon/weixin_runtime.py` maps text, image and document delivery, while the target Weixin adapter also exposes distinct video and voice paths. Falling through to document does not establish media parity.
3. `scripts/build_lilsunspotd_sidecar.ps1` probes a hard-coded `hermes_agent-0.14.0.dist-info`; the target reports `0.19.0`. A clean target environment, lock/metadata audit and version-independent probe are required.

The review also confirmed that `AIAgent.run_conversation`, the fallback-provider list, `gateway.session_context`, approval session callbacks, and the basic Weixin lifecycle/signatures remain compatible in the fixed snapshot. They are not current blockers, but still require post-merge tests.

## Remaining gates

- Fetch the exact official target Git objects and verify `git merge-base` locally.
- Complete read-only registry and adapter review against the fixed snapshot.
- Create the full machine-readable capability manifest and parity test before merge.
- Do not run `scripts/hermes_upstream_sync.ps1`; it merges a floating ref and updates the completion marker too early.
- Do not update `lilsunspot/UPSTREAM_COMMIT.txt` until installation and upgrade validation are complete.

## Machine manifest and validation checkpoint

- Generated manifest: `lilsunspot/resources/hermes_capability_manifest.json`.
- Generator/audit entry: `python -m lilsunspot.daemon.upstream_audit --upstream-root <fixed-source-root> --target-commit d9f1043c3337818b1f29224a7deb5bbb17402370 --snapshot-archive ignored/hermes-upstream-snapshot/d9f1043c3337818b1f29224a7deb5bbb17402370.tar.gz --snapshot-record lilsunspot/resources/hermes_upstream_snapshot_record.json --parity-overrides lilsunspot/resources/hermes_capability_parity_overrides.json --manifest-out lilsunspot/resources/hermes_capability_manifest.json`.
- Manifest counts: 57 toolsets, 25 configurable toolsets, 74 static named tool registrations, 93 plugin manifests, 69 built-in skills, 111 optional skills, 4 optional MCP manifests, 9 built-in gateway adapters.
- Binding semantics: `operator_recorded_archive_integrity`; this proves the archive digest, unique root and extracted tree agree with the independent record, not official Git ancestry or commit authenticity.
- Focused audit tests: 4 passed.
- Capability/product/audit regression: 27 passed; product upstream-check script: 3 passed with the Windows-compatible thread timeout method.
- `scripts/check.ps1`: daemon 158 passed and secret guard passed; desktop build was skipped because the isolated worktree has no untracked `node_modules`.

The manifest now contains a 519-row parity ledger with stable canonical IDs and separate mapping/readiness gates. All rows deliberately remain unmapped until per-item lilsunspot owner, product entry, configuration source, safety policy, typed package status and validation references are recorded. Installed readiness additionally requires concrete bundle/discovery/invocation and executed evidence.
