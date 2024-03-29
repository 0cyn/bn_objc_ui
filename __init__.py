from . import src
import binaryninja
import os

plugin_name = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
bn_version = binaryninja.core_version()

if 'USE_JETBRAINS_DEBUGGER' in os.environ and os.environ['USE_JETBRAINS_DEBUGGER'] == '1':
	port = 12345
	if 'JETBRAINS_DEBUGGER_PORT' in os.environ:
		port = int(os.environ['JETBRAINS_DEBUGGER_PORT'])
	binaryninja.connect_pycharm_debugger(port)

if 'USE_VSCODE_DEBUGGER' in os.environ and os.environ['USE_VSCODE_DEBUGGER'] == '1':
	port = 12345
	if 'VSCODE_DEBUGGER_PORT' in os.environ:
		port = int(os.environ['VSCODE_DEBUGGER_PORT'])
	binaryninja.connect_vscode_debugger(port)

binaryninja.log_info(f"Loaded {plugin_name} for Binary Ninja version {bn_version}")

src.plugin_init(plugin_name, bn_version)
