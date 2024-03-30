import binaryninja
import os


def plugin_init(plugin_name, bn_version):
	from . import triage
	triage.ObjectiveCTriageViewType.init()
	pass
