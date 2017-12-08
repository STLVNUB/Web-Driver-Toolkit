import plistlib
import sys
import os
import time
import Downloader
import tempfile
import shutil
import subprocess
import re
import base64
import binascii
# Python-aware urllib stuff
if sys.version_info >= (3, 0):
    from urllib.request import urlopen
else:
    from urllib2 import urlopen

class WebDriver:

    def __init__(self):

        # Check the OS first
        if not str(sys.platform) == "darwin":
            self.head("Incompatible System")
            print(" ")
            print("This script can only be run from macOS/OS X.")
            print(" ")
            print("The current running system is \"{}\".".format(sys.platform))
            print(" ")
            self.grab("Press [enter] to quit...")
            print(" ")
            exit(1)

        self.dl = Downloader.Downloader()
        self.web_drivers = None
        self.os_build_number = None
        self.os_number = None
        self.wd_loc = None
        self.sip_checked = False
        self.installed_version = "Not Installed!"

        self.get_manifest()
        self.get_system_info()

    def _check_info(self):
        if os.path.exists("/System/Library/Extensions/NVDAStartupWeb.kext"):
            self.wd_loc = "/System/Library/Extensions/NVDAStartupWeb.kext"
        elif os.path.exists("/Library/Extensions/NVDAStartupWeb.kext"):
            self.wd_loc = "/Library/Extensions/NVDAStartupWeb.kext"
        else:
            self.wd_loc = None

    def _stream_output(self, comm, shell = False):
        output = ""
        try:
            if shell and type(comm) is list:
                comm = " ".join(comm)
            if not shell and type(comm) is str:
                comm = comm.split()
            p = subprocess.Popen(comm, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            while True:
                stdoutdata = p.stdout.readline()
                if stdoutdata:
                    output += stdoutdata.decode("utf-8")
                    sys.stdout.write(stdoutdata.decode("utf-8"))
                else:
                    break
            return output
        except:
            return output

    def _run_command(self, comm, shell = False):
        c = None
        try:
            if shell and type(comm) is list:
                comm = " ".join(comm)
            if not shell and type(comm) is str:
                comm = comm.split()
            p = subprocess.Popen(comm, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            c = p.communicate()
            return (c[0].decode("utf-8"), c[1].decode("utf-8"), p.returncode)
        except:
            if c == None:
                return ("", "Command not found!", 1)
            return (c[0].decode("utf-8"), c[1].decode("utf-8"), p.returncode)

    def run(self, command_list, leave_on_fail = False):
        # Command list should be an array of dicts
        if type(command_list) is dict:
            # We only have one command
            command_list = [command_list]
        output_list = []
        for comm in command_list:
            args   = comm.get("args",   [])
            shell  = comm.get("shell",  False)
            stream = comm.get("stream", False)
            sudo   = comm.get("sudo",   False)
            stdout = comm.get("stdout", False)
            stderr = comm.get("stderr", False)
            mess   = comm.get("message", None)
            
            if not mess == None:
                print(mess)

            if not len(args):
                # nothing to process
                continue
            if sudo:
                # Check if we have sudo
                out = self._run_command(["which", "sudo"])
                if "sudo" in out[0]:
                    # Can sudo
                    args.insert(0, "sudo")
            
            if stream:
                # Stream it!
                out = self._stream_output(args, shell)
            else:
                # Just run and gather output
                out = self._run_command(args, shell)
                if stdout and len(out[0]):
                    print(out[0])
                if stderr and len(out[1]):
                    print(out[1])
            # Append output
            if type(out) is str:
                # We streamed - assume success?
                out = ( out, "", 0 )
            output_list.append(out)
            # Check for errors
            if leave_on_fail and out[2] != 0:
                # Got an error - leave
                break
        if len(output_list) == 1:
            # We only ran one command - just return that output
            return output_list[0]
        return output_list

    def check_sip(self):
        # Checks our sip status and warns if needed
        sip_stats = self.run({"args" : ["csrutil", "status"]})[0]
        msg = "Unknown SIP Configuration!\n"
        title = "Unknown"
        if not sip_stats.startswith("System Integrity Protection status:"):
            # Error getting SIP status
            return None
        if sip_stats == "System Integrity Protection status: disabled.":
            # SIP is disabled - return true to imply we have the "go ahead"
            return True
        if sip_stats.startswith("System Integrity Protection status: enabled (Custom Configuration)."):
            # SIP is partially enabled - determine if fs protection and kext signing is disabled
            if "Filesystem Protections: disabled" in sip_stats and "Kext Signing: disabled" in sip_stats:
                # Still good - let's roll
                return True
            title = "Partially Disabled"
            msg = "SIP is only partially disabled!\nKext signing and/or fs protection are eanbled!\n"
            
        if sip_stats == "System Integrity Protection status: enabled.":
            # SIP is enabled completely
            title = "Enabled"
            msg = "System Integrity Protection is completely enabled!\n"
        self.head("SIP Is " + title)
        print(" ")
        print(msg)
        print("This may prevent the web drivers from being patched or loading.")
        print(" ")
        menu = self.grab("Would you like to continue? (y/n):  ")

        if not len(menu):
            return self.check_sip()
        
        if menu[:1].lower() == "n":
            return False
        elif menu[:1].lower() == "y":
            return True

        return self.check_sip()
        

    def check_path(self, path):
        # Add os checks for path escaping/quote stripping
        path = path.replace("\\", "").replace('"', "")
        # Remove trailing space if drag and dropped
        if path[len(path)-1:] == " ":
            path = path[:-1]
        # Expand tilde
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            print("That file doesn't exist!")
            return None
        return path

    # Helper methods
    def grab(self, prompt):
        if sys.version_info >= (3, 0):
            return input(prompt)
        else:
            return str(raw_input(prompt))

    # Header drawing method
    def head(self, text = "Web Driver Updater", width = 50):
        os.system("clear")
        print("  {}".format("#"*width))
        mid_len = int(round(width/2-len(text)/2)-2)
        middle = " #{}{}{}#".format(" "*mid_len, text, " "*((width - mid_len - len(text))-2))
        print(middle)
        print("#"*width)

    def custom_quit(self):
        self.head("Web Driver Updater")
        print("by CorpNewt\n")
        print("Thanks for testing it out, for bugs/comments/complaints")
        print("send me a message on Reddit, or check out my GitHub:\n")
        print("www.reddit.com/u/corpnewt")
        print("www.github.com/corpnewt\n")
        print("Have a nice day/night!\n\n")
        exit(0)

    def get_manifest(self):
        self.head("Retrieving Manifest...")
        print(" ")
        print("Retrieving manifest from \"https://gfe.nvidia.com/mac-update\"...\n")
        try:
            plist_data = self.dl.get_bytes("https://gfe.nvidia.com/mac-update")
            if not plist_data or not len(str(plist_data)):
                print("Looks like that site isn't responding!\n\nPlease check your intenet connection and try again.")
                time.sleep(3)
                self.web_drivers = {}
                return
            if sys.version_info >= (3, 0):
                self.web_drivers = plistlib.loads(plist_data)
            else:
                self.web_drivers = plistlib.readPlistFromString(plist_data)
        except:
            print("Something went wrong while getting the manifest!\n\nPlease check your intenet connection and try again.")
            time.sleep(3)
            self.web_drivers = {}

    def get_system_info(self):
        self.installed_version = "Not Installed!"
        self.os_build_number = self.run({"args" : ["sw_vers", "-buildVersion"]})[0].strip()
        self.os_number       = self.run({"args" : ["sw_vers", "-productVersion"]})[0].strip()
        if self.wd_loc:
            info_plist = plistlib.readPlist(self.wd_loc + "/Contents/Info.plist")            
            self.installed_version = info_plist["CFBundleGetInfoString"].split(" ")[-1].replace("(", "").replace(")", "")

    def check_dir(self, build):
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        os.chdir("../")
        if not os.path.exists("Web Drivers"):
            os.mkdir("Web Drivers")
        os.chdir("Web Drivers")
        if not os.path.exists(build):
            os.mkdir(build)
        os.chdir(build)
        return os.getcwd()

    def download_for_build(self, build):
        self.head("Downloading for " + build)
        print(" ")
        dl_update = None
        if not "updates" in self.web_drivers:
            print("The manifest was unreachable!\n\nPlease check your internet connection and update the manifest.")
            time.sleep(5)
            return
        for update in self.web_drivers.get("updates", []):
            if update["OS"].lower() == build.lower():
                dl_update = update
                break 
        if not dl_update:
            print("There isn't a version available for that build number!")
            time.sleep(5)
            return
        print("Downloading " + dl_update["version"])
        print(" ")
        self.check_dir(build)
        dl_file = self.dl.stream_to_file(dl_update["downloadURL"], dl_update["downloadURL"].split("/")[-1])
        if dl_file:
            print(dl_file + " downloaded successfully!")
            self.run({"args":["open", os.getcwd()]})
            time.sleep(5)

    def format_table(self, items, columns):
        max_length = 0
        current_row = 0
        row_list = [[]]
        cur_list = []
        msg = ""
        # Let's break things up and give a numerical value
        alpha = "abcdefghijklmnopqrstuvwxyz"
        new_items = []
        for i in items:
            # Split them up
            split = re.findall(r"[^\W\d_]+|\d+", i)
            start = split[0].rjust(4, "0")
            alph  = split[1]
            end   = split[2].rjust(6, "0")
            alpha_num = str(alpha.index(alph.lower())).rjust(2, "0")
            value = int(start + alpha_num + end)
            new_items.append({"build" : i, "value" : value})

        # Sort by numeric value instead of general build number
        # This is helpful in cases where 17B48 comes before 17B1002
        # even though 4 > 1
        sorted_list = sorted(new_items, key=lambda x:x["value"])
        for key in sorted_list:
            entry = key["build"]
            if len(entry) > max_length:
                max_length = len(entry)
            row_list[len(row_list)-1].append(entry)
            if len(row_list[len(row_list)-1]) >= columns:
                row_list.append([])
                current_row += 1
        for row in row_list:
            for entry in row:
                entry = entry.ljust(max_length)
                msg += entry + "  "
            msg += "\n"
        return msg

    def build_list(self):
        # Print 8 columns
        self.head("Web Drivers By Build Number")
        print(" ")
        build_list = []
        if not "updates" in self.web_drivers:
            # No manifest
            print("The manifest was unreachable!\n\nPlease check your internet connection and update the manifest.")
            time.sleep(5)
            return
        for update in self.web_drivers.get("updates", []):
            build_list.append(update["OS"])

        print("OS Build Number:  {}".format(self.os_build_number))
        print(" ")
        
        print("Available Build Numbers:\n")
        builds = self.format_table(build_list, 8)
        print(builds)
        print("M. Main Menu")
        print("Q. Quit")
        print(" ")
        menu = self.grab("Please type a build number to download the web driver:  ")

        if not len(menu):
            self.build_list()

        if menu[:1].lower() == "m":
            return
        elif menu[:1].lower() == "q":
            self.custom_quit()

        for build in build_list:
            if build.lower() == menu.lower():
                self.download_for_build(build)
                return
        self.build_list()

    def patch_menu(self):
        self.head("Web Driver Patch")
        print(" ")
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        if not self.wd_loc:
            print("NVDAStartupWeb.kext was not found in either /L/E or /S/L/E!\n")
            print("Please make sure you have the Web Drivers installed.")
            time.sleep(5)
            return
        info_plist = plistlib.readPlist(self.wd_loc + "/Contents/Info.plist")
        current_build = info_plist.get("IOKitPersonalities", {}).get("NVDAStartup", {}).get("NVDARequiredOS", None)

        print("OS Build Number:  {}".format(self.os_build_number))
        print("WD Target Build:  {}".format(current_build))

        print(" ")
        print("C. Set to Current Build Number")
        print("I. Input New Build Number")
        can_restore = False
        if os.path.exists(self.wd_loc + "/Contents/Info.plist.bak"):
            print("R. Restore Backup")
            print("D. Delete Backup")
            can_restore = True
        print(" ")
        print("M. Main Menu")
        print("Q. Quit")
        print(" ")

        menu = self.grab("Please make a selection:  ")

        if not len(menu):
            self.patch_menu()
            return

        if menu[:1].lower() == "q":
            self.custom_quit()
        elif menu[:1].lower() == "c":
            self.set_build(self.os_build_number)
        elif menu[:1].lower() == "i":
            self.custom_build()
        elif menu[:1].lower() == "r" and can_restore:
            self.restore_backup()
        elif menu[:1].lower() == "d" and can_restore:
            self.delete_backup()
        elif menu[:1].lower() == "m":
            return
        
        self.patch_menu()
        return

    def restore_backup(self):
        if not self.sip_checked:
            res = self.check_sip()
            if res == None or res == True:
                # Likely on Yosemite?
                self.sip_checked = True
            else:
                return

        self.head("Restoring Backup Info.plist")
        print(" ")
        if not os.path.exists(self.wd_loc + "/Contents/Info.plist.bak"):
            # Create a backup
            print("Backup doesn't exist...")
            time.sleep(5)
            return
        # Doing things
        c = [
            { 
                "args" : ["rm", self.wd_loc + "/Contents/Info.plist"], 
                "sudo" : True, 
                "message" : "Removing " + self.wd_loc + "/Contents/Info.plist...\n" 
            },
            { 
                "args" : ["sudo", "mv", "-f", self.wd_loc + "/Contents/Info.plist.bak", self.wd_loc + "/Contents/Info.plist"], 
                "sudo" : True,
                "message" : "Renaming Info.plist.bak to Info.plist...\n"
            },
            { 
                "args" : ["sudo", "chown", "0:0", self.wd_loc + "/Contents/Info.plist"], 
                "sudo" : True, 
                "message" : "Updating ownership and permissions...\n" 
            },
            { 
                "args" : ["sudo", "chmod", "755", self.wd_loc + "/Contents/Info.plist"], 
                "sudo" : True
            },
            { 
                "args" : ["sudo", "kextcache", "-i", "/"], 
                "sudo" : True,
                "stream" : True,
                "message" : "Rebuilding kext cache...\n" 
            }
        ]
        self.run(c, True)
        print(" ")
        print("Done.")
        time.sleep(5)
        return

    def delete_backup(self):
        self.head("Deleting Backup Info.plist")
        print(" ")
        if not os.path.exists(self.wd_loc + "/Contents/Info.plist.bak"):
            # Create a backup
            print("Backup doesn't exist...")
            time.sleep(5)
            return
        # Removing
        print("Removing " + self.wd_loc + "/Contents/Info.plist.bak...\n")
        self.run({"args":["rm", self.wd_loc + "/Contents/Info.plist.bak"],"sudo":True})
        print("Done.")
        time.sleep(5)
        return

    def set_build(self, build_number):
        if not self.sip_checked:
            res = self.check_sip()
            if res == None or res == True:
                # Likely on Yosemite?
                self.sip_checked = True
            else:
                return

        self.head("Setting NVDARequiredOS to {}".format(build_number))
        print(" ")
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        # Start our command list
        c = []

        info_plist = plistlib.readPlist(self.wd_loc + "/Contents/Info.plist")
        if not os.path.exists(self.wd_loc + "/Contents/Info.plist.bak"):
            # Create a backup
            self.run({
                "args" : ["cp", self.wd_loc + "/Contents/Info.plist", self.wd_loc + "/Contents/Info.plist.bak"],
                "sudo" : True,
                "message" : "Creating backup...\n"
            })
            # plistlib.writePlist(info_plist, self.wd_loc + "/Contents/Info.plist.bak")
        # Change the build number and write to the main plist
        print("Patching plist for build \"{}\"...\n".format(build_number))
        info_plist["IOKitPersonalities"]["NVDAStartup"]["NVDARequiredOS"] = build_number
        # Make a temp folder for our plist
        temp_folder = tempfile.mkdtemp()
        # Write the changes
        plistlib.writePlist(info_plist, temp_folder + "/Info.plist")
        # Build and run commands
        c = [
            {
                "args" : ["mv", "-f", temp_folder + "/Info.plist", self.wd_loc + "/Contents/Info.plist"],
                "sudo" : True
            },
            {
                "args" : ["chown", "0:0", self.wd_loc + "/Contents/Info.plist"],
                "sudo" : True,
                "message" : "Updating ownership and permissions...\n"
            },
            {
                "args" : ["chmod", "755", self.wd_loc + "/Contents/Info.plist"],
                "sudo" : True
            },
            {
                "args" : ["kextcache", "-i", "/"],
                "sudo" : True,
                "stream" : True,
                "message" : "Rebuilding kext cache...\n"
            }
        ]
        self.run(c, True)
        # Remove temp
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)
        print(" ")
        print("Done.")
        time.sleep(5)
        return

    def custom_build(self):
        self.head("Custom Build")
        print(" ")
        print("")

        if not self.wd_loc:
            print("NVDAStartupWeb.kext was not found in either /L/E or /S/L/E!\n")
            print("Please make sure you have the Web Drivers installed.")
            time.sleep(5)
            return
        info_plist = plistlib.readPlist(self.wd_loc + "/Contents/Info.plist")
        current_build = info_plist.get("IOKitPersonalities", {}).get("NVDAStartup", {}).get("NVDARequiredOS", None)

        print("OS Build Number:  {}".format(self.os_build_number))
        print("WD Target Build:  {}".format(current_build))

        print(" ")
        print("P. Patch Menu")
        print(" ")
        print("M. Main Menu")
        print("Q. Quit")
        print(" ")

        menu = self.grab("Please enter a new build number:  ")

        if not len(menu):
            self.custom_build()
            return

        if menu.lower() == "q":
            self.custom_quit()
        elif menu.lower() == "m":
            self.main()
        elif menu.lower() == "p":
            return
        
        # We have a build number
        self.set_build(menu)
        self.main()
        return

    def patch_installer(self):
        self.head("Patch Install Package")
        print(" ")
        print("M. Main Menu")
        print("Q. Quit")
        print(" ")
        menu = self.grab("Please drag and drop the install package to patch:  ")

        if not len(menu):
            self.patch_installer()
            return

        if menu.lower() == "q":
            self.custom_quit()
        elif menu.lower() == "m":
            return

        # Check path
        menu_path = self.check_path(menu)
        if not menu_path:
            print("That path doesn't exist...")
            time.sleep(3)
            self.patch_installer()
            return
        # Path exists
        temp_dir = tempfile.mkdtemp()
        try:
            self.patch_pkg(menu_path, temp_dir)
        except:
            print("Something went wrong!")
            time.sleep(3)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return

    def patch_pkg(self, package, temp):
        self.head("Patching Install Package")
        print(" ")
        script_path = os.path.dirname(os.path.realpath(__file__))
        print("Expanding package...\n")
        stat = self.run({"args" : ["pkgutil", "--expand", package, temp + "/package"]})
        if not stat[2] == 0:
            print("Something went wrong!\n")
            print(stat[1])
            return
        new_dist = ""
        print("Patching Distribution...\n")
        with open(temp + "/package/Distribution") as f:
            for line in f:
                if "if (!validatesoftware())" in line.lower():
                    continue
                if "if (!validatehardware())" in line.lower():
                    continue
                if "return false;" in line:
                    line = line.replace("return false;", "return true;")
                new_dist += line
        with open(temp + "/package/Distribution", "w") as f:
            f.write(new_dist)
        self.check_dir("Patched")
        print("Repacking...\n")
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        os.chdir("../Web Drivers/Patched/")
        self.run({"args" : ["pkgutil", "--flatten", temp + "/package", os.getcwd() + "/" + os.path.basename(package)[:-4] + " (Patched).pkg"]})
        print("Done.")
        self.run({"args":["open", os.getcwd()]})
        time.sleep(5)

    def remove_drivers(self):
        self.head("Removing Web Drivers")
        print(" ")
        print("Clearing web drivers from /S/L/E...\n")
        self.run({"args":["sudo", "rm", "-rf", "/System/Library/Extensions/GeForce*Web.*", "/System/Library/Extensions/NVDA*Web.kext"], "shell" : True})
        print("Clearing web drivers from /L/E...\n")
        self.run({"args":["sudo", "rm", "-rf", "/Library/Extensions/GeForce*Web.kext", "/Library/Extensions/NVDA*Web.kext"], "shell" : True})
        # Rebuild kextcache
        print("Rebuilding kext cache...\n")
        self._stream_output(["sudo", "kextcache", "-i", "/"])
        print(" ")
        print("Done.")
        time.sleep(5)

    def config_menu(self):
        self.head("Config.plist Patch Menu")
        print(" ")
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        if not self.wd_loc:
            print("NVDAStartupWeb.kext was not found in either /L/E or /S/L/E!\n")
            print("Please make sure you have the Web Drivers installed.")
            time.sleep(5)
            return
        info_plist = plistlib.readPlist(self.wd_loc + "/Contents/Info.plist")
        current_build = info_plist.get("IOKitPersonalities", {}).get("NVDAStartup", {}).get("NVDARequiredOS", None)

        print("OS Build Number:  {}".format(self.os_build_number))
        print("WD Target Build:  {}".format(current_build))
        print(" ")
        print("C. Current Build Number")
        print(" ")
        print("M. Main Menu")
        print("Q. Quit")
        print(" ")

        menu = self.grab("Please make a selection (or type a custom build number):  ")

        if not len(menu):
            self.config_menu()
            return

        if menu[:1].lower() == "m":
            return
        elif menu[:1].lower() == "q":
            self.custom_quit()
        elif menu[:1].lower() == "c":
            self.type_menu(self.os_build_number)
        else:
            self.type_menu(menu)
        self.config_menu()
        return

    def type_menu(self, build):
        self.head("Config.plist Patch: {}".format(build))
        print(" ")
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        if not self.wd_loc:
            print("NVDAStartupWeb.kext was not found in either /L/E or /S/L/E!\n")
            print("Please make sure you have the Web Drivers installed.")
            time.sleep(5)
            return
        info_plist = plistlib.readPlist(self.wd_loc + "/Contents/Info.plist")
        current_build = info_plist.get("IOKitPersonalities", {}).get("NVDAStartup", {}).get("NVDARequiredOS", None)
        if len(current_build) < len(build):
            # No amount of padding can save us
            print("Due to the nature of Clover's kext/Info.plist patching - the source and".format(current_build))
            print("target build numbers need to be the same length, or - with a padding")
            print("workaround, the target build number can be shorter.")
            print(" ")
            print("Manually patching the Info.plist is likely a better solution here.")
            time.sleep(5)
            return
        if build == current_build:
            print("Both builds are the same - this defeats the purpose of the patch.")
            time.sleep(5)
            return
        print("B. Show Base64 Values")
        print("H. Show Hex Values")
        print("P. Show Plist Patch")
        print(" ")
        print("M. Main Menu")
        print("C. Config.plist Patch Menu")
        print("Q. Quit")
        print(" ")
        menu = self.grab("Please make a selection:  ")

        if not len(menu):
            self.config_menu()
            return

        display_text = data_type = ""
        find_text = "<string>{}</string>".format(current_build)
        repl_text = "<string>{}</string>".format(build).rjust(len(find_text), " ")

        if menu[:1].lower() == "m":
            self.main()
            return
        elif menu[:1].lower() == "q":
            self.custom_quit()
        elif menu[:1].lower() == "b":
            data_type = "Base64"
            display_text += "Name:      NVDAStartupWeb\n"
            display_text += "Comment:   Nvidia {} to {}\n".format(current_build, build)
            display_text += "Disabled:  False\n"
            display_text += "Find:      {}\n".format(self.get_base(find_text))
            display_text += "Replace:   {}\n".format(self.get_base(repl_text))
            display_text += "InfoPlist: True"
        elif menu[:1].lower() == "h":
            data_type = "Hex"
            display_text += "Name:      NVDAStartupWeb\n"
            display_text += "Comment:   Nvidia {} to {}\n".format(current_build, build)
            display_text += "Disabled:  False\n"
            display_text += "Find:      {}\n".format(self.get_hex(find_text))
            display_text += "Replace:   {}\n".format(self.get_hex(repl_text))
            display_text += "InfoPlist: True"
        elif menu[:1].lower() == "p":
            # Get some plist wizardry
            data_type = "Plist"
            plist_dict = {
                "Name" : "NVDAStartupWeb",
                "Comment" : "Nvidia {} to {}".format(current_build, build),
                "InfoPlistPatch" : True,
                "Disabled" : False,
                "Find" : self.get_base_data(find_text),
                "Replace" : self.get_base_data(repl_text)
            }
            if sys.version_info >= (3, 0):
                plist_string = plistlib.dumps(plist_dict).decode("utf-8")
            else:
                plist_string = plistlib.writePlistToString(plist_dict)
            # Trim the plist
            display_text = "\n".join(plist_string.split("\n")[3:-2])
        
        if len(display_text):
            self.head("Config.plist Patch: {}".format(build))
            print(" ")
            print("Your {} Data:\n".format(data_type))
            print(display_text)
            print(" ")
            self.grab("Press [enter] to return...")
        self.type_menu(build)
        return
        
    def get_base(self, value):
        return base64.b64encode(value.encode("utf-8")).decode("utf-8")
    
    def get_base_data(self, value):
        return base64.b64encode(value)

    def get_hex(self, value):
        text = binascii.hexlify(value.encode("utf-8")).decode("utf-8")
        text_list = re.findall('........?', text)
        return " ".join(text_list)

    def main(self):
        self._check_info()
        self.get_system_info()
        self.head("Web Driver Updater")
        print(" ")
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        print("OS Version:       {} - {}".format(self.os_number, self.os_build_number))
        print("WD Version:       " + self.installed_version)

        if self.wd_loc:
            info_plist = plistlib.readPlist(self.wd_loc + "/Contents/Info.plist")
            current_build = info_plist.get("IOKitPersonalities", {}).get("NVDAStartup", {}).get("NVDARequiredOS", None)
            print("WD Target Build:  {}".format(current_build))
        
        if not "updates" in self.web_drivers:
            newest_version = "Manifest not available!"
        else:
            newest_version = "None for this build number!"
        for update in self.web_drivers.get("updates", []):
            if update["OS"].lower() == self.os_build_number.lower():
                newest_version = update["version"]
                break 

        if self.installed_version.lower() == newest_version.lower():
            print("Newest:           " + newest_version + " (Current)")
        else:
            print("Newest:           " + newest_version)
        
        print(" ")
        patch = False
        if self.wd_loc:
            print("P. Patch Menu")
            patch = True
        print("I. Patch Install Package")
        print("D. Download For Current")
        print("B. Download By Build Number")
        print("R. Remove Web Drivers")
        print("U. Update Manifest")
        print("C. Config.plist Patch Menu")
        print("")
        print("Q. Quit")
        print(" ")

        menu = self.grab("Please make a selection (just press enter to reload):  ")

        if not len(menu):
            return

        if menu[:1].lower() == "q":
            self.custom_quit()
        elif menu[:1].lower() == "p" and patch:
            self.patch_menu()
        elif menu[:1].lower() == "d":
            self.download_for_build(self.os_build_number)
        elif menu[:1].lower() == "b":
            self.build_list()
        elif menu[:1].lower() == "i":
            self.patch_installer()
        elif menu[:1].lower() == "u":
            self.get_manifest()
        elif menu[:1].lower() == "r":
            self.remove_drivers()
        elif menu[:1].lower() == "c":
            self.config_menu()
        
        return

wd = WebDriver()

while True:
    try:
        wd.main()
    except Exception as e:
        print(e)
        time.sleep(5)
