import sys, os
import argparse
import json


def find_binaryninja():
	# Check if the Binary Ninja install directory is in the path
	bn_path = os.environ.get("BINARYNINJA_PATH")
	if sys.platform == "win32":
		if not bn_path:
			bn_path = os.path.join(os.environ.get("ProgramFiles"), "Vector35", "BinaryNinja")
		if not bn_path:
			bn_path = os.path.join(os.environ.get("ProgramFiles(x86)"), "Vector35", "BinaryNinja")
	elif sys.platform == "darwin":
		if not bn_path:
			bn_path = "/Applications/Binary Ninja.app"
	else:
		print('Please specify the path to Binary Ninja using the BINARYNINJA_PATH environment variable')
		sys.exit(1)
	return bn_path


def find_plugin_install_dir():
	# Check if the Binary Ninja plugin install directory is in the path
	plugin_install_dir = os.environ.get("BN_INSTALL_DIR")
	if sys.platform == "win32":
		if not plugin_install_dir:
			plugin_install_dir = os.path.join(os.environ.get("APPDATA"), "Binary Ninja", "plugins")
	elif sys.platform == "darwin":
		if not plugin_install_dir:
			plugin_install_dir = os.path.join(os.environ.get("HOME"), "Library", "Application Support", "Binary Ninja", "plugins")
	else:
		if not plugin_install_dir:
			plugin_install_dir = os.path.join(os.environ.get("HOME"), ".binaryninja", "plugins")
	return plugin_install_dir


def find_settings_json():
	# Check if the Binary Ninja settings.json file is in the path
	settings_json = os.environ.get("BN_SETTINGS_JSON")
	if sys.platform == "win32":
		if not settings_json:
			settings_json = os.path.join(os.environ.get("APPDATA"), "Binary Ninja", "settings.json")
	elif sys.platform == "darwin":
		if not settings_json:
			settings_json = os.path.join(os.environ.get("HOME"), "Library", "Application Support", "Binary Ninja", "settings.json")
	else:
		if not settings_json:
			settings_json = os.path.join(os.environ.get("HOME"), ".binaryninja", "settings.json")
	return settings_json


def load_settings_json():
	settings_json = find_settings_json()
	if not settings_json:
		print('Please specify the path to the settings.json file using the BN_SETTINGS_JSON environment variable')
		sys.exit(1)
	with open(settings_json) as f:
		return json.load(f)

def print_settings_json():
	settings_json = load_settings_json()
	print(json.dumps(settings_json, indent=4))

def find_python_interpreter():
	# Check if the Python interpreter is in the path
	python_interpreter = os.environ.get("BN_PYTHON_INTERPRETER")
	if not python_interpreter:
		settings = load_settings_json()
		if "python.interpreter" not in settings:
			# Use the default Python interpreter
			# OS Check:
			if sys.platform == "win32":
				python_interpreter = ""
			elif sys.platform == "darwin":
				python_interpreter = find_binaryninja() + "/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
			else:
				python_interpreter = "/usr/bin/python"
		else:
			python_interpreter = settings["python.interpreter"]
	return python_interpreter

def find_pythonhome():
	# Check if the Python home directory is in the path
	settings = load_settings_json()
	pythonhome = ""
	if "python.interpreter" not in settings:
		if sys.platform == "win32":
			pythonhome = ""
		elif sys.platform == "darwin":
			pythonhome = find_binaryninja() + "/Contents/Resources/bundled-python3/"
		else:
			pythonhome = ""
	return pythonhome


def standard_license_text(license_name):
	import datetime
	if license_name == "MIT":
		return """

Copyright {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
""".format(year=datetime.datetime.now().year, author=input("Author for License Text: "))
	else:
		print(f"License text for {license_name} not embedded in this file, please add it manually")
		return ""


def project_setup():
	# repl
	print("Commands:\n\thelp - List project settings\n\tset <setting> <value> - Set a setting\n\texit - Exit")
	command = input("> ")
	while command != "exit":
		if command == "help":
			print("Settings:")
			print("\t - name")
			print("\t - license")
			print("\t - author")
			print("\t - version")
			print("\t - description")
			print("\t - minvers")
			print("\t - deps add/remove (comma seperated)")
			print("\t - is_ui_plugin")
		elif command.startswith("set"):
			with open("plugin.json", "r") as f:
				settings = json.load(f)
			setting = command.split(" ")[1]
			value = " ".join(command.split(" ")[2:])
			if setting == "name":
				project_name = value
				settings["name"] = project_name
			elif setting == "license":
				settings["license"] = value
				settings["license_text"] = standard_license_text(value)
			elif setting == "author":
				settings["author"] = value
			elif setting == "version":
				settings["version"] = value
			elif setting == "description":
				settings["description"] = value
			elif setting == "minvers":
				settings["minimumbinaryninjaversion"] = value
			elif setting == "deps":
				if value.startswith("add"):
					value = value[4:]
					settings["dependencies"]["pip"] += [i.strip() for i in value.strip().split(",")]
				elif value.startswith("remove"):
					value = value[7:]
					for i in [i.strip() for i in value.split(",")]:
						if i in settings["dependencies"]["pip"]:
							settings["dependencies"]["pip"].remove(i)
				settings["dependencies"]["pip"] = [i.strip() for i in value.strip().split(",")]
				with open('requirements.txt', 'w') as f:
					for item in settings["dependencies"]["pip"]:
						f.write(f"{item}\n")
			elif setting == "is_ui_plugin":
				if value.lower() == "true":
					if "ui" not in settings["type"]:
						settings["type"].append("ui")
				else:
					if "ui" in settings["type"]:
						settings["type"].remove("ui")
			with open("plugin.json", "w") as f:
				json.dump(settings, f, indent=4)

		command = input("> ")


def get_project_name():
	with open("plugin.json", "r") as f:
		settings = json.load(f)
	return settings["name"]


def get_project_version():
	with open("plugin.json", "r") as f:
		settings = json.load(f)
	return settings["version"]


def main():
	parser = argparse.ArgumentParser(description="Build utils for Binary Ninja plugins")
	parser.add_argument("--find-binaryninja", action="store_true", help="Find the Binary Ninja install directory")
	parser.add_argument("--find-plugin-install-dir", action="store_true", help="Find the plugin install directory")
	parser.add_argument("--find-python-interpreter", action="store_true", help="Find the Python interpreter")
	parser.add_argument("--find-pythonhome", action="store_true", help="Find the Python home directory")
	parser.add_argument("--get-project-name", action="store_true", help="Get the project name")
	parser.add_argument("--get-project-version", action="store_true", help="Get the project version")
	parser.add_argument("--print-settings-json", action="store_true", help="Print the settings.json file")
	parser.add_argument("--setup", action="store_true", help="Setup the project")

	args = parser.parse_args()
	# set cwd to script's dir
	cwd = os.getcwd()
	os.chdir(os.path.dirname(os.path.realpath(__file__)))
	if args.find_binaryninja:
		print(find_binaryninja())
	elif args.find_plugin_install_dir:
		print(find_plugin_install_dir())
	elif args.print_settings_json:
		print_settings_json()
	elif args.find_python_interpreter:
		print(find_python_interpreter())
	elif args.find_pythonhome:
		print(find_pythonhome())
	elif args.get_project_name:
		print(get_project_name())
	elif args.get_project_version:
		print(get_project_version())
	elif args.setup:
		project_setup()
	os.chdir(cwd)


if __name__ == "__main__":
	main()