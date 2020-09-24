"""Analyze the OS X app bundle for OpenShot, and find all external dependencies"""
import os
import subprocess

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
unique_dependencies = {}

# Find files matching patterns
for root, dirs, files in os.walk(os.path.join(PATH, 'build', 'OpenShot Video Editor.app')):
    for basename in files:
        file_path = os.path.join(root, basename)

        output = str(subprocess.Popen(["oTool", "-L", file_path], stdout=subprocess.PIPE).communicate()[0])
        if "is not an object file" not in output:
            dependency_path = output.replace('\\n','').split('\\t')[1].split(' ')[0]
            dependency_version = output.replace('\\n','').split('\\t')[1].split(' (')[1].replace(')','')

            if "@executable_path" not in dependency_path and dependency_path not in unique_dependencies.keys():
                unique_dependencies[dependency_path] = file_path
                print("%s => %s (%s)" % (basename, dependency_path, dependency_version))
