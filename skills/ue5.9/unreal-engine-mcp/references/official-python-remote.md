# Epic Python Remote Execution without editor UI

This is the third route, after a domain tool and `PythonScriptingTools` over
MCP. Use it for one operation that neither MCP route covers, then return to
MCP. It is Epic's `PythonScriptPlugin` endpoint and runs in the background:
no console keystrokes, window activation or layout changes.

## Discover and configure

1. Select the intended project and discover the live MCP toolsets first.
2. Describe `ConfigSettingsToolset` and list the relevant sections. Look for
   the Python plugin's section (`Project / Plugins / Python`).
3. Read `GetSectionSchema` and `GetSectionPropertyValues`. Preserve the original
   values before a setup change. Expect property names such as
   `bRemoteExecution`, `remoteExecutionMulticastBindAddress`,
   `remoteExecutionMulticastGroupEndpoint` and `remoteExecutionMulticastTtl`;
   take the exact names from the schema.
4. When enabling this endpoint is within the user's authorized direct-connection
   setup, use `SetSectionProperties` with `{"bRemoteExecution":true}`. Verify
   binding to `127.0.0.1` and TTL `0` beforehand and read the values back afterward.
   Do not widen binding, change firewall rules or enable it in unrelated projects.
   This saves a project setting; state that it was enabled when reporting setup.

The setting is designed to take effect live. Confirm it with node discovery
instead of the Boolean return. When a build needs a restart for it, coordinate
with the user before restarting an active editor.

## Connect with the bundled client

`scripts/python_remote.py` loads `remote_execution.py` from the selected engine
(`--engine-root`, `UE_ENGINE_ROOT`, or a running editor's install), waits for
discovery, and refuses to run unless exactly one editor matches `--project`:

```powershell
python scripts/python_remote.py nodes
python scripts/python_remote.py --project MyGame exec --file <session>/probe.py
```

The bundled client loads `remote_execution.py` from the editor that runs the
requested project (newest engine otherwise) and reads whole messages, so
results larger than about 8 KB arrive complete.

The JSON result is Epic's `command_result` (`success`, `result`, `output` lines)
plus the selected node. From Python, call `python_remote.run_python(script,
project=...)`. The equivalent direct use of Epic's module is:

```python
sys.path.insert(0, str(engine_root / 'Plugins/Experimental/PythonScriptPlugin/Content/Python'))
import remote_execution
remote = remote_execution.RemoteExecution()
try:
    remote.start()
    # Bounded discovery wait outside the editor, then inspect remote.remote_nodes.
    # Match project_root and engine_root/version; require exactly one target.
    remote.open_command_connection(selected_node['node_id'])
    result = remote.run_command(script_path, exec_mode=remote_execution.MODE_EXEC_FILE)
    if not result['success']:
        raise RuntimeError(result['result'])
finally:
    remote.stop()
```

For scripts returning JSON through a printed marker, use
`ue_mcp.remote.marker_json(result, marker)`. Require literal `success=True`, no
Error lines, one Info marker and valid JSON; when invoking the CLI, also require
exit code zero. A marker printed before a later exception is not success, and
multiple markers are ambiguous. Preserve Warning lines in the raw evidence;
they do not become command failure by themselves. Validate the returned domain
schema as well: `null` annotations must not silently disable annotation checks.

Read the installed module's documented defaults instead of copying its transport
implementation. Tested defaults are multicast `239.0.0.1:6766`, bind
`127.0.0.1`, TTL `0`, and the client's local command endpoint `127.0.0.1:6776`.
If the command port is occupied, inspect the installed config API and choose an
available loopback endpoint; do not disconnect another active client.

Probe the public API read-only before authoring. Ordinary node properties may
not be Python-exposed even when a similarly named C++ field exists. Use native
comment frame APIs for annotation and validate Chinese text, member nodes and
unchanged MCP topology. Return to MCP for covered compile/save operations and
save only the intended asset. Keep script/results in ignored session output.

For read-only Blueprint comment bounds that `ObjectToolset` and Python properties do
not expose, Epic's `AssetExportTask` with `ObjectExporterT3D` can export the native
comment object's serializable model fields to a local temporary file. Set
`automated=True`, `prompt=False`, `selected=False`; inspect export success/errors
and verify object identity before using its fields. Windows non-ANSI exports
can be UTF-16 with a BOM. `blueprint_comment_geometry.py` handles decoding and
validation; `blueprint_lint.py` compares model containment against its MCP
snapshot. This route neither rebuilds Slate's member cache nor saves an asset.

## 验证记录

- 本页的设置项名称、热生效行为和消息截断修复来自 UE 5.8.4 的实测与安装源码；
  Epic 模块的 UE 5.3 版本一次 `recv` 只读 8 KB，5.8 版本在首次短读时停止，
  超过约 8 KB 的结果会被截断。
- UE 5.9.0 Preview / CL 60351404 上未重新执行 Remote Execution 的启用与连接；
  该构建的窄缺口均通过 `PythonScriptingTools` 完成。使用本路线前先读回设置
  schema 和节点发现结果。
