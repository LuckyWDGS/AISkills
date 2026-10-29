# Epic Python Remote Execution without editor UI

Use only for a demonstrated official MCP gap. Operations already covered by MCP
stay on MCP. This is Epic's `PythonScriptPlugin` endpoint, not UnrealBridge and
not unrestricted execution inside ProgrammaticToolset.

The user wants background automation without mouse-driven consoles, window
activation or layout changes. Do not fall back to those UI actions automatically.

## Discover and configure

1. Select the intended project and discover the live MCP toolsets first.
2. Describe `ConfigSettingsToolset` and list the relevant sections. In the tested
   UE 5.8.4 build the settings section is `Project / Plugins / Python`.
3. Read `GetSectionSchema` and `GetSectionPropertyValues`. Preserve the original
   values before a setup change. The relevant live JSON property names were:
   `bRemoteExecution`, `remoteExecutionMulticastBindAddress`,
   `remoteExecutionMulticastGroupEndpoint`, and `remoteExecutionMulticastTtl`.
4. When enabling this endpoint is within the user's authorized direct-connection
   setup, use `SetSectionProperties` with `{"bRemoteExecution":true}`. Verify
   binding to `127.0.0.1` and TTL `0` beforehand and read the values back afterward.
   Do not widen binding, change firewall rules or enable it in unrelated projects.
   This saves a project setting; state that it was enabled when reporting setup.

In the tested 5.8.4 source, the settings' `PostEditChangeProperty` calls
`SyncRemoteExecutionToSettings`, so this configuration takes effect live without
restarting UE. Confirm discovery rather than assuming success from a Boolean
return. If a different build requires restart, do not restart an active editor
merely to add annotations without coordinating with the user.

## Connect with the bundled client

`scripts/python_remote.py` loads `remote_execution.py` from the selected engine
(`--engine-root`, `UE_ENGINE_ROOT`, or a running editor's install), waits for
discovery, and refuses to run unless exactly one editor matches `--project`:

```powershell
python scripts/python_remote.py nodes
python scripts/python_remote.py --project MyGame exec --file <session>/probe.py
```

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
