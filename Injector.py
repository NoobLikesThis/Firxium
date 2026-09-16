from flask import Flask, request, jsonify, render_template, send_from_directory
import pymem
import pymem.process
import re
import time
import urllib.request
import psutil
import subprocess
import struct
import json

app = Flask(__name__)

PROCESS_NAME = "RobloxPlayerBeta.exe"
HPP_URL = "https://raw.githubusercontent.com/creatornawaf/FFlags-Offsets/refs/heads/main/FFlags.hpp"
OFFSETS_JSON_URL = "https://raw.githubusercontent.com/creatornawaf/FFlags-Offsets/refs/heads/main/offsets.json"
pm = None
base_address = None

OFFSETS = {}
OTHER_OFFSETS = {}
WORLD_STEPS_VALUE = 16.0


def load_hpp():
    global OFFSETS
    try:
        response = urllib.request.urlopen(HPP_URL)
        text = response.read().decode("utf-8")
    except Exception as e:
        print(f"Error fetching HPP from URL: {e}")
        return

    matches = re.findall(
        r'([A-Za-z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+)',
        text
    )

    OFFSETS = {
        name:int(offset,16)
        for name,offset in matches
    }

    print("loaded",len(OFFSETS),"flags")


def load_other_offsets():
    global OTHER_OFFSETS

    try:
        print("World Steps: Downloading offsets.json...")

        request = urllib.request.Request(
            OFFSETS_JSON_URL,
            headers={
                "User-Agent": "XSDR-Injector",
                "Cache-Control": "no-cache"
            }
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")

        data = json.loads(raw)

        if "Offsets" not in data:
            raise ValueError("JSON has no 'Offsets' object")

        if not isinstance(data["Offsets"], dict):
            raise ValueError("'Offsets' is not an object")

        OTHER_OFFSETS = data["Offsets"]

        print(
            "World Steps: Loaded "
            f"{data.get('Total Offsets', len(OTHER_OFFSETS))} offsets"
        )

        print(
            "World Steps: Roblox Version = "
            f"{data.get('Roblox Version', 'unknown')}"
        )

        print(
            "World Steps: Dumped At = "
            f"{data.get('Dumped At', 'unknown')}"
        )

        required = [
            ("FakeDataModel", "Pointer"),
            ("FakeDataModel", "RealDataModel"),
            ("DataModel", "Workspace"),
            ("Workspace", "World"),
            ("World", "worldStepsPerSec")
        ]

        for section, name in required:
            if section not in OTHER_OFFSETS:
                raise ValueError(
                    f"Missing section: {section}"
                )

            if name not in OTHER_OFFSETS[section]:
                raise ValueError(
                    f"Missing offset: {section}.{name}"
                )

        print("World Steps: Required offsets verified")

        return True

    except Exception as e:
        OTHER_OFFSETS = {}
        print(f"Error fetching offsets.json: {e}")
        return False    

def detect_type(flag):
    if flag.startswith(("DFFlag","FFlag","BFlag")):
        return "bool"
    if flag.startswith(("DFInt","FInt","FLog")):
        return "int"
    if flag.startswith(("FFloat","DFFloat")):
        return "float"
    if flag.startswith(("FString","DFString")):
        return "string"
    return "int"

def is_text_value(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return True
        if stripped.lower() in ["true", "false"]:
            return False
        try:
            int(stripped)
            return False
        except ValueError:
            pass
        try:
            float(stripped)
            return False
        except ValueError:
            pass
        return True
    return False


def auto_inject():
    global pm, base_address
    print("waiting for roblox...")
    while True:
        try:
            pm = pymem.Pymem(PROCESS_NAME)
            module = pymem.process.module_from_name(
                pm.process_handle,
                PROCESS_NAME
            )
            base_address = module.lpBaseOfDll
            print("attached to roblox at", hex(base_address))
            break
        except:
            time.sleep(2)


def write_value(addr, flag_type, value):
    if flag_type == "bool":
        pm.write_bool(
            addr,
            value in ["1","true","True",True]
        )
    elif flag_type == "int":
        pm.write_int(
            addr,
            int(value)
        )
    elif flag_type == "float":
        pm.write_float(
            addr,
            float(value)
        )
    elif flag_type == "string":
        data = value.encode() + b"\x00"
        pm.write_bytes(
            addr,
            data,
            len(data)
        )

def set_flag(name,value):
    if name not in OFFSETS:
        return "flag not found"

    offset = OFFSETS[name]
    addr = base_address + offset
    flag_type = detect_type(name)

    try:
        write_value(addr,flag_type,value)
        print(name,"direct")
        return "direct"
    except:
        pass

    try:
        ptr = pm.read_longlong(addr)
        write_value(ptr,flag_type,value)
        print(name,"pointer")
        return "pointer"
    except:
        pass

    if flag_type != "string" and is_text_value(value):
        try:
            write_value(addr,"string",value)
            print(name,"direct-string-fallback")
            return "direct-string"
        except:
            pass

        try:
            ptr = pm.read_longlong(addr)
            write_value(ptr,"string",value)
            print(name,"pointer-string-fallback")
            return "pointer-string"
        except:
            pass

    return "failed"

def inject_world_steps():
    """Separate injection method for World Steps"""
    global pm, base_address
    print("World Steps: waiting for roblox...")
    attempts = 0
    while attempts < 30:
        try:
            pm = pymem.Pymem(PROCESS_NAME)
            module = pymem.process.module_from_name(
                pm.process_handle,
                PROCESS_NAME
            )
            base_address = module.lpBaseOfDll
            print("World Steps: attached to roblox at", hex(base_address))
            return True
        except:
            attempts += 1
            time.sleep(2)
    return False

def find_world():

    global pm, base_address

    try:
        if pm is None or base_address is None:
            print("World Steps: Roblox is not attached")
            return None

        offsets = OTHER_OFFSETS

        fake_dm = offsets["FakeDataModel"]
        data_model = offsets["DataModel"]
        workspace_offsets = offsets["Workspace"]

        fake_dm_pointer = fake_dm["Pointer"]
        real_dm_offset = fake_dm["RealDataModel"]
        workspace_offset = data_model["Workspace"]
        world_offset = workspace_offsets["World"]

        print(
            "World Steps offsets:"
            f" FakeDM=0x{fake_dm_pointer:X},"
            f" RealDM=0x{real_dm_offset:X},"
            f" Workspace=0x{workspace_offset:X},"
            f" World=0x{world_offset:X}"
        )

        fake_dm_address = base_address + fake_dm_pointer

        fake_dm_instance = pm.read_ulonglong(fake_dm_address)

        if not fake_dm_instance:
            print("World Steps: FakeDataModel pointer is null")
            return None

        dm = pm.read_ulonglong(
            fake_dm_instance + real_dm_offset
        )

        if not dm:
            print("World Steps: RealDataModel pointer is null")
            return None

        workspace = pm.read_ulonglong(
            dm + workspace_offset
        )

        if not workspace:
            print("World Steps: Workspace pointer is null")
            return None

        world = pm.read_ulonglong(
            workspace + world_offset
        )

        if not world:
            print("World Steps: World pointer is null")
            return None

        print(f"World Steps: World found at {hex(world)}")

        return world

    except KeyError as e:
        print(f"World Steps: Missing JSON offset: {e}")
        return None

    except Exception as e:
        print(f"World Steps: Failed to resolve World: {e}")
        return None
        
def get_world_steps():
    """Read worldStepsPerSec using the live JSON offset."""

    global WORLD_STEPS_VALUE

    try:
        if pm is None:
            return WORLD_STEPS_VALUE

        world = find_world()

        if not world:
            return WORLD_STEPS_VALUE

        steps_offset = OTHER_OFFSETS["World"]["worldStepsPerSec"]

        steps_addr = world + steps_offset

        value = pm.read_float(steps_addr)

        if value is not None:
            WORLD_STEPS_VALUE = value
            return value

    except KeyError as e:
        print(f"World Steps: Missing JSON offset: {e}")

    except Exception as e:
        print(f"Get World Steps Error: {e}")

    return WORLD_STEPS_VALUE


def set_world_steps(value):
    """Set worldStepsPerSec using the live offsets.json data."""

    global pm, base_address, WORLD_STEPS_VALUE

    if pm is None or base_address is None:
        print("World Steps: Roblox is not attached")

        if not inject_world_steps():
            return False

    try:
        world = find_world()

        if not world:
            print("World Steps: Could not resolve World")
            return False

        steps_offset = OTHER_OFFSETS["World"]["worldStepsPerSec"]

        steps_addr = world + steps_offset

        current_value = pm.read_float(steps_addr)

        print(
            f"World Steps: Address = {hex(steps_addr)}"
        )

        print(
            f"World Steps: Current value = {current_value}"
        )

        new_value = float(value)

        pm.write_float(
            steps_addr,
            new_value
        )

        WORLD_STEPS_VALUE = new_value

        print(
            f"World Steps: Set to {new_value}"
        )

        return True

    except KeyError as e:
        print(f"World Steps: Missing JSON offset: {e}")
        return False

    except Exception as e:
        print(
            f"World Steps: Failed to set value: {e}"
        )
        return False
        
@app.route("/")
def home():
    return render_template("index.html")

@app.route('/Discord.png')
def discord_icon():
    return send_from_directory('templates', 'Discord.png')

@app.route("/flags")
def flags():
    return OFFSETS

@app.route("/setflag",methods=["POST", "GET"])
def api_setflag():
    data = request.json
    name = data["flag"]
    value = data["value"]
    mode = set_flag(name,value)
    return {
        "flag":name,
        "mode":mode
    }

@app.route("/inject", methods=["POST", "GET"])
def api_inject():
    auto_inject()
    print("injected successfully!")
    return "injected"

@app.route("/set_world_steps", methods=["POST"])
def api_set_world_steps():
    try:
        data = request.json
        if not data:
            return {"success": False, "error": "No data provided"}, 400
        
        value = data.get("value")
        if value is None:
            return {"success": False, "error": "No value provided"}, 400
        
        success = set_world_steps(float(value))
        
        if success:
            return {"success": True, "value": WORLD_STEPS_VALUE}
        else:
            return {"success": False, "error": "Could not find World instance"}, 500
    except Exception as e:
        return {"success": False, "error": str(e)}, 500

@app.route("/restart_roblox", methods=["POST"])
def restart_roblox():
    roblox_path = None
    for proc in psutil.process_iter(['name', 'exe']):
        try:
            if proc.info['name'] == "RobloxPlayerBeta.exe":
                roblox_path = proc.info['exe']
                proc.kill()
        except:
            pass

    time.sleep(2)
    if roblox_path:
        subprocess.Popen(roblox_path)
        auto_inject()
        return "restarted"
    return "roblox not found"

@app.route("/uninject", methods=["POST"])
def uninject():
    import psutil
    targets = ["cmd.exe"]
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] in targets:
                proc.kill()
        except:
            pass
    return "uninjected"

@app.route("/restart_injector", methods=["POST"])
def restart_injector():
    import os
    import time
    import subprocess
    import threading

    current_pid = os.getpid()
    bat_path = os.path.abspath("startserver.bat")

    def restart():
        time.sleep(1)
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        os._exit(0)

    threading.Thread(target=restart).start()
    return "restarting"

@app.route("/world_steps", methods=["GET"])
def api_get_world_steps():
    try:
        if not pm:
            return jsonify({"value": WORLD_STEPS_VALUE, "enabled": False})
        
        value = get_world_steps()
        return jsonify({"value": value, "enabled": True})
    except Exception as e:
        return jsonify({"value": WORLD_STEPS_VALUE, "error": str(e)})


load_hpp()
load_other_offsets()
auto_inject()

print("Join Our Discord Server https://discord.gg/U5TwSnQh6e")

app.run(port=5000)
