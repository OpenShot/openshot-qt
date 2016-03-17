"""Analyze the OS X app bundle for OpenShot, and find all external dependencies"""
import os
import subprocess
from subprocess import call

PATH = "/usr/local/qt5/5.5/clang_64/lib"

# Find files matching patterns
# for file in os.listdir(PATH):
#     if file.endswith(".framework"):
#         file_path = os.path.join(PATH, file)
#         file_parts = file_path.split("/")
#         #print(file_path)
#         #print(os.path.join("/Library/Frameworks/Python.framework/Versions/3.5/lib", file_parts[-1]))
#         call(["ln", "-s", file_path, os.path.join("/Library/Frameworks/Python.framework/Versions/3.5/lib", file_parts[-1])])



# # Find files matching patterns
# for root, dirs, files in os.walk(PATH):
#     for basename in files:
#         file_path = os.path.join(root, basename)
#         file_parts = file_path.split("/")
#
#         if "framework" in file_path and file_parts[-2] == "5" and "_debug" not in file_path:
#             print ("\nFixing %s" % file_path)
#             #print ("install_name_tool %s -id %s" % (file_path, file_path))
#             #call(["install_name_tool", file_path, "-id", file_path])
#
#             raw_output = subprocess.Popen(["oTool", "-L", file_path], stdout=subprocess.PIPE).communicate()[0].decode('utf-8')
#             if not "is not an object file" in raw_output:
#                 for output in raw_output.split("\n")[1:-1]:
#                     dependency_path = output.split('\t')[1].split(' ')[0]
#                     dependency_version = output.split('\t')[1].split(' (')[1].replace(')','')
#
#                     if "@rpath" in dependency_path:
#                         command = 'install_name_tool "%s" -change "%s" "%s"' % (file_path, dependency_path, dependency_path.replace("@rpath", PATH))
#                         print (command)
#                         #call(["install_name_tool", file_path, "-change", dependency_path, dependency_path.replace("@rpath", PATH)])


PATH = "/usr/local/qt5/5.5/clang_64"

# Find files matching patterns
for root, dirs, files in os.walk(PATH):
    for basename in files:
        file_path = os.path.join(root, basename)
        file_parts = file_path.split("/")

        if ".dylib" in file_path or ".so" in file_path:

            #print (file_path)
            print ("install_name_tool %s -id %s" % (file_path, file_path))
            call(["install_name_tool", file_path, "-id", file_path])

            raw_output = subprocess.Popen(["oTool", "-L", file_path], stdout=subprocess.PIPE).communicate()[0].decode('utf-8')
            for output in raw_output.split("\n")[1:-1]:
                if output and not "is not an object file" in output:
                    dependency_path = output.split('\t')[1].split(' ')[0]
                    dependency_version = output.split('\t')[1].split(' (')[1].replace(')','')

                    if "@rpath" in dependency_path:
                        command = 'install_name_tool "%s" -change "%s" "%s"' % (file_path, dependency_path, dependency_path.replace("@rpath", os.path.join(PATH, "lib")))
                        print (command)
                        call(["install_name_tool", file_path, "-change", dependency_path, dependency_path.replace("@rpath", os.path.join(PATH, "lib"))])


