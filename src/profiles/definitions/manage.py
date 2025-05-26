# Parse JSON profile definitions and provide some useful functions for managing profiles
# used in OpenShot.
#
# Args:
#  - "generate": Generate a new set of profile files for OpenShot (1 text file per profile)
#  - "validate": Parse through all definitions and validate the math (aspect ratios, sample ratios, etc...)
#  - "update": Update all JSON definition sample ratios
#  - "preview": Using only JSON definitions, display all profiles to the screen
#  - "display": Print all existing profiles to the screen
#  - "doc": Print documentation markdown (used for manually updating our docs)

import re
import os
import sys
import json
import openshot

from defusedxml import minidom as xml


PATH = os.path.dirname(os.path.realpath(__file__))
PROFILE_PATH = os.path.dirname(PATH)
PRESETS_PATH = os.path.join(os.path.dirname(PROFILE_PATH), "presets")
LEGACY_PROFILE_PATH = os.path.join(PROFILE_PATH, "legacy")
PRESET_REGEX = re.compile(r'.*<projectprofile>(.*)</projectprofile>')
legacy_profiles = {}
NEW_PROFILES = {}


class CompactJSONEncoder(json.JSONEncoder):
    """A JSON Encoder that puts nested lists on one line (more compact)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.indentation_level = 0

    def encode(self, o):
        """Encode JSON object *o* with lists that contain a 'dar' property."""
        if isinstance(o, (list, tuple)):
            if "dar" in o[0]:
                return "[" + ", ".join(json.dumps(el) for el in o) + "]"

            self.indentation_level += 1
            output = [self.indent_str + self.encode(el) for el in o]
            self.indentation_level -= 1
            return "[\n" + ",\n".join(output) + "\n" + self.indent_str + "]"

        if isinstance(o, dict):
            self.indentation_level += 1
            output = [self.indent_str + f"{json.dumps(k)}: {self.encode(v)}" for k, v in o.items()]
            self.indentation_level -= 1
            return "{\n" + ",\n".join(output) + "\n" + self.indent_str + "}"
        else:
            return json.dumps(o)

    @property
    def indent_str(self) -> str:
        return " " * self.indentation_level * self.indent


def save_profile(definition_path, json_details):
    """Save a profile with compact formatting"""
    print(f" - Updating JSON {definition_path}")
    with open(definition_path, "w") as f1:
        formatted_json = json.dumps(json_details, indent=4, cls=CompactJSONEncoder)
        formatted_json = re.sub('\n            ', ' ', formatted_json, flags=re.DOTALL)
        formatted_json = re.sub(',\n            ', ', ', formatted_json, flags=re.DOTALL)
        formatted_json = re.sub('}, {', '},\n                {', formatted_json, flags=re.DOTALL)
        formatted_json = re.sub('\\[{', '[\n                {', formatted_json, flags=re.DOTALL)
        formatted_json = re.sub('}]', '}\n            ]', formatted_json, flags=re.DOTALL)
        f1.write(formatted_json)


# Check for arg value
mode = ""
if len(sys.argv) <= 1:
    print("Please pass a valid argument: 'generate', 'validate', 'update'")
    exit(1)
else:
    mode = sys.argv[1]

# Generate possible sample aspect ratios (1-100:1-100)
SAMPLE_RATIOS = [(10, 11), (12, 11), (40, 33), (8, 9), (32, 27), (1, 1), (4, 3), (16, 9), (8, 5), (32, 15),
                 (16, 15), (16, 11), (64, 45), (23, 24), (9, 10), (6, 5), (24, 11), (20, 11), (24, 17), (32, 17), (32, 11),
                 (38, 27), (95, 66), (20, 17), (5, 6), (3, 4), (25, 32),
                 (59, 54), (59, 27), (15, 11), (59, 36)]

FOUND_SAMPLE_RATIOS = []
# for n in range(1, 1000):
#     for m in range(1, 1000):
#         SAMPLE_RATIOS.append((n, m))


for profile_name in os.listdir(LEGACY_PROFILE_PATH):
    profile_path = os.path.join(LEGACY_PROFILE_PATH, profile_name)
    if not os.path.isdir(profile_path):
        profile = openshot.Profile(profile_path)
        # Only consider profiles with 'legacy' name
        profile_key = profile.Key()
        if profile_key not in legacy_profiles:
            legacy_profiles[profile_key] = [(profile, profile_name)]
        else:
            legacy_profiles[profile_key].append((profile, profile_name))

# Parse each definition *.json file in /definitions/ directory
print("Reading JSON profile definitions")
for definition in os.listdir(PATH):
    if definition.endswith(".json"):
        print(f"- {definition}")
        definition_path = os.path.join(PATH, definition)
        with open(definition_path, "r") as f:
            json_details = json.loads(f.read())
            profile_abr = json_details.get("abbreviation")
            profile_category = json_details.get("category")

            # Loop through profiles
            for p in json_details.get("profiles", []):
                for r in p.get("fps", []):
                    # Populate Profile object (for helper functions)
                    profile = openshot.Profile()
                    profile.info.width = p.get("width")
                    profile.info.height = p.get("height")
                    profile.info.fps.num = r.get("num")
                    profile.info.fps.den = r.get("den")
                    profile.info.display_ratio.num = r.get("dar").get("num")
                    profile.info.display_ratio.den = r.get("dar").get("den")
                    profile.info.pixel_ratio.num = r.get("sar").get("num")
                    profile.info.pixel_ratio.den = r.get("sar").get("den")
                    profile.info.interlaced_frame = not r.get("progressive")

                    # Verify accurate DAR
                    size = openshot.Fraction(profile.info.width, profile.info.height)
                    dar = profile.info.display_ratio
                    size.Reduce()
                    dar.Reduce()
                    smallest_diff = 1.0
                    smallest_fraction = None
                    if size.num != dar.num or size.den != dar.den:
                        for s in SAMPLE_RATIOS:
                            common_rate = openshot.Fraction(s[0], s[1])
                            diff = (size.ToDouble() * common_rate.ToDouble()) - dar.ToDouble()
                            if 0.0 <= diff < smallest_diff:
                                smallest_diff = diff
                                smallest_fraction = s

                        if not smallest_fraction:
                            print(f"ERROR: {p} - {r}: size: {size.num}:{size.den}, {dar.num}:{dar.den}")
                        else:
                            if smallest_diff > 0.01:
                                raise Exception(f"ERROR: BAD SAMPLE RATIO: {smallest_diff} ({smallest_fraction[0]}")
                            r["sar"] = {"num": smallest_fraction[0], "den": smallest_fraction[1]}
                            if float(smallest_fraction[0] / smallest_fraction[1]) != 1.0 and "Anamorphic" not in r["notes"]:
                                r["notes"] = f'{r["notes"]} Anamorphic'.strip()
                            elif float(smallest_fraction[0] / smallest_fraction[1]) == 1.0 and "Anamorphic" in r["notes"]:
                                r["notes"] = r["notes"].replace("Anamorphic", "").strip()
                            FOUND_SAMPLE_RATIOS.append(smallest_fraction)
                    else:
                        # Add sample ratio
                        r["sar"] = {"num": 1, "den": 1}

                    profile_key = profile.Key()

                    # Add profile to dict
                    # We can have multiple matches for a single key though
                    if profile_key not in NEW_PROFILES:
                        NEW_PROFILES[profile_key] = [(p, r, profile_abr, profile_category)]
                    else:
                        NEW_PROFILES[profile_key].append((p, r, profile_abr, profile_category))

            if mode == "update":
                # Save definition json
                save_profile(definition_path, json_details)

if mode == "validate":
    # Compare legacy and new profiles
    unmatched = []
    matched = []
    for legacy_key in legacy_profiles.keys():
        if legacy_key not in NEW_PROFILES.keys():
            legacy = legacy_profiles[legacy_key]
            unmatched.append(f"{legacy_key} {legacy[0][1]}")
        else:
            legacy = legacy_profiles[legacy_key]
            new_profile = NEW_PROFILES[legacy_key]
            matched.append((legacy[0][1], new_profile))

    print(f"\nUnmatched Legacy Profiles: {len(unmatched)}/{len(legacy_profiles.keys())}")
    for key in unmatched:
        legacy = legacy_profiles[key.split(" ")[0]]
        s = openshot.Fraction(legacy[0][0].info.pixel_ratio.num, legacy[0][0].info.pixel_ratio.den)
        print(f" - {key} = {round(legacy[0][0].info.width * s.ToDouble())}x{legacy[0][0].info.height}")

    # Compare new profiles and legacy profiles
    unmatched = []
    # for new in NEW_PROFILES.keys():
    #     if new not in legacy_profiles.keys():
    #         unmatched.append(new)
    print(f"\nUnmatched New Profiles: {len(unmatched)}/{len(NEW_PROFILES.keys())}")
    # for key in unmatched:
    #     print(f" - {key}")

if mode == "generate":
    unique_profile_names = {}
    for new_key in reversed(sorted(NEW_PROFILES.keys())):
        tags = []
        for p in NEW_PROFILES[new_key]:
            # Populate Profile object (for helper functions)
            profile = openshot.Profile()
            profile.info.width = p[0].get("width")
            profile.info.height = p[0].get("height")
            profile.info.fps.num = p[1].get("num")
            profile.info.fps.den = p[1].get("den")
            profile.info.display_ratio.num = p[1].get("dar").get("num")
            profile.info.display_ratio.den = p[1].get("dar").get("den")
            profile.info.pixel_ratio.num = p[1].get("sar").get("num")
            profile.info.pixel_ratio.den = p[1].get("sar").get("den")
            profile.info.interlaced_frame = not p[1].get("progressive")
            profile.info.spherical = p[0].get("spherical", False)

            # Format file name for new profile
            profile_abr = p[2]
            profile_notes = p[0].get("notes")
            fps_notes = p[1].get("notes")
            for possible_tag in profile_notes.split(" ") + fps_notes.split(" "):
                if possible_tag and possible_tag not in tags:
                    tags.append(possible_tag)

            interlaced_string = "i"
            progressive_string = "0"
            if not profile.info.interlaced_frame:
                interlaced_string = "p"
                progressive_string = "1"
            fps_string = f'{profile.info.fps.num}'
            if profile.info.fps.den != 1:
                fps_string = f'{profile.info.fps.ToDouble():.04}'

            # Move tags (NTSC/PAL first, Anamorphic last)
            for first in ["SD", "HD", "NTSC", "PAL", "FHD", "UHD", "4K", "5K", "8K", "16K"]:
                if first in tags:
                    tags.remove(first)
                    tags.insert(0, first)
            for last in ["Anamorphic", ]:
                if last in tags:
                    tags.remove(last)
                    tags.append(last)

            if "Vertical" in tags:
                # Exception for vertical formats - we refer to the original width (i.e. 720p Vertical instead of 1280p)
                profile.info.description = f'{" ".join(tags)} {profile.info.width}{interlaced_string} {fps_string} fps'
            else:
                # Non-vertical resolutions (normal)
                profile.info.description = f'{" ".join(tags)} {profile.info.height}{interlaced_string} {fps_string} fps'

            # Track profile names for uniqueness
            if profile.info.description not in unique_profile_names.keys():
                unique_profile_names[profile.info.description] = [profile.Key()]
            elif profile.Key() not in unique_profile_names[profile.info.description]:
                unique_profile_names[profile.info.description].append(profile.Key())

            profile_name = profile.Key()
            profile_path = os.path.join(PROFILE_PATH, profile_name)

        # Determine if "Anamorphic" is correctly set
        if profile.info.pixel_ratio.ToFloat() != 1.0 and "Anamorphic" not in tags:
            print(f"Error: Anamorphic property is MISSING for {profile.Key()}")
        elif profile.info.pixel_ratio.ToFloat() == 1.0 and "Anamorphic" in tags:
            print(f"Error: Anamorphic property is NOT needed for {profile.Key()}")

        # Create new profile file
        # Check if spherical attribute should be included
        spherical_string = ""
        if hasattr(profile.info, "spherical") and profile.info.spherical == 1:
            spherical_string = "\nspherical=1"

        profile_body = f"""description={profile.info.description}
frame_rate_num={profile.info.fps.num}
frame_rate_den={profile.info.fps.den}
width={profile.info.width}
height={profile.info.height}
progressive={progressive_string}
sample_aspect_num={profile.info.pixel_ratio.num}
sample_aspect_den={profile.info.pixel_ratio.den}
display_aspect_num={profile.info.display_ratio.num}
display_aspect_den={profile.info.display_ratio.den}{spherical_string}"""

        # Write file
        print(f"Generating profile file: {profile_name}")
        with open(profile_path, "w") as profile_file_object:
            profile_file_object.write(profile_body)

    # Iterate through duplicate profile names (and give a unique descriptive name)
    # For now, we'll add the DAR to the end of the description
    for profile_name, keys in unique_profile_names.items():
        if len(keys) > 1:
            for key in keys:
                profile_path = os.path.join(PROFILE_PATH, key)
                profile = openshot.Profile(profile_path)
                # Create unique name (since more than 2 profiles use the same name)
                unique_profile_name = f'{profile_name} | {profile.info.display_ratio.num}:{profile.info.display_ratio.den}'
                print(f'Updating name for uniqueness: {unique_profile_name} in profile: {profile.Key()}')

                # Write file with description updated for uniqueness
                with open(profile_path, "r") as read_file_object:
                    profile_body = read_file_object.read()
                    profile_body = profile_body.replace(profile_name, unique_profile_name)
                    with open(profile_path, "w") as profile_file_object:
                        profile_file_object.write(profile_body)

if mode == "preview":
    # Print new profiles
    print(f"\nNEW Profiles: {len(NEW_PROFILES.keys())}")
    for new_key in reversed(sorted(NEW_PROFILES.keys())):
        for p in NEW_PROFILES[new_key]:
            # Populate Profile object (for helper functions)
            profile = openshot.Profile()
            profile.info.width = p[0].get("width")
            profile.info.height = p[0].get("height")
            profile.info.fps.num = p[1].get("num")
            profile.info.fps.den = p[1].get("den")
            profile.info.display_ratio.num = p[1].get("dar").get("num")
            profile.info.display_ratio.den = p[1].get("dar").get("den")
            profile.info.pixel_ratio.num = p[1].get("sar").get("num")
            profile.info.pixel_ratio.den = p[1].get("sar").get("den")
            profile.info.interlaced_frame = not p[1].get("progressive")
            profile.info.spherical = p[0].get("spherical", False)

            sar = profile.info.pixel_ratio
            sar.Reduce()
            print(f'{profile.Key()}\t\t{profile.ShortName()}\t\t{profile.LongName()}\t\t{profile.LongNameWithDesc()}')

if mode == "display":
    # Print existing profiles
    for profile_name in sorted(os.listdir(PROFILE_PATH)):
        profile_path = os.path.join(PROFILE_PATH, profile_name)
        if not os.path.isdir(profile_path):
            profile = openshot.Profile(profile_path)
            print(f'{profile.info.description}')

if mode == "doc":
    def lookup_layout(layout):
        if layout == "3":
            return "Stereo"
        if layout == "4":
            return "Mono"
        if layout == "7":
            return "Surround"

    # Print existing profiles
    #   ==========  ==================
    dividing_line = "   %s  %s  %s  %s  %s  %s  %s  %s" % ("".ljust(45, "="), "".ljust(6, "="), "".ljust(6, "="),
                                                           "".ljust(6, "="), "".ljust(6, "="), "".ljust(6, "="),
                                                           "".ljust(10, "="), "".ljust(18, "="))
    print(f"\n{dividing_line}")
    for profile_name in reversed(sorted(os.listdir(PROFILE_PATH))):
        profile_path = os.path.join(PROFILE_PATH, profile_name)
        if not os.path.isdir(profile_path):
            profile = openshot.Profile(profile_path)
            padded_name = profile.info.description.ljust(45)
            padded_width = str(profile.info.width).ljust(6)
            padded_height = str(profile.info.height).ljust(6)
            padded_ratio = f"{profile.info.display_ratio.num}:{profile.info.display_ratio.den}".ljust(6)
            padded_pixel_ratio = f"{profile.info.pixel_ratio.num}:{profile.info.pixel_ratio.den}".ljust(6)
            if profile.info.interlaced_frame:
                padded_interlaced = "Yes".ljust(10)
            else:
                padded_interlaced = "No".ljust(10)
            fps_padded = f"{profile.info.fps.ToFloat():.2f}".ljust(6)
            sar_display_width = round(profile.info.width * profile.info.pixel_ratio.ToFloat())
            padded_sar_display_width = str(sar_display_width).ljust(18)
            print(f"   {padded_name}  {padded_width}  {padded_height}  {fps_padded}  "
                  f"{padded_ratio}  {padded_pixel_ratio}  {padded_interlaced}  {padded_sar_display_width}")
    print(dividing_line)

    # Print existing presets
    presets = []
    preset_types = []
    preset_type_names = {}
    for preset_folder in [PRESETS_PATH]:
        for file in os.listdir(preset_folder):
            preset_path = os.path.join(preset_folder, file)

            xmldoc = xml.parse(preset_path)
            simple_type = xmldoc.getElementsByTagName("type")
            presets.append(simple_type[0].childNodes[0].data)
            if xmldoc.getElementsByTagName("projectprofile"):
                project_profiles = []
                for profile in xmldoc.getElementsByTagName("projectprofile"):
                    project_profiles.append(profile.childNodes[0].data)
            else:
                project_profiles = ["All Profiles"]

            # Get video and audio codec names (if any)
            video_codec = ""
            if xmldoc.getElementsByTagName("videocodec")[0].childNodes:
                video_codec = xmldoc.getElementsByTagName("videocodec")[0].childNodes[0].data
            audio_codec = ""
            if xmldoc.getElementsByTagName("audiocodec")[0].childNodes:
                audio_codec = xmldoc.getElementsByTagName("audiocodec")[0].childNodes[0].data

            preset_type_names[xmldoc.getElementsByTagName("type")[0].childNodes[0].data] = \
                xmldoc.getElementsByTagName("type")[0].childNodes[0].data
            preset_types.append({
                "type": xmldoc.getElementsByTagName("type")[0].childNodes[0].data,
                "title": xmldoc.getElementsByTagName("title")[0].childNodes[0].data,
                "videoformat": xmldoc.getElementsByTagName("videoformat")[0].childNodes[0].data,
                "videocodec": video_codec,
                "audiocodec": audio_codec,
                "audiochannels": xmldoc.getElementsByTagName("audiochannels")[0].childNodes[0].data,
                "audiochannellayout": xmldoc.getElementsByTagName("audiochannellayout")[0].childNodes[0].data,
                "videobitrate": { "low": xmldoc.getElementsByTagName("videobitrate")[0].attributes["low"].childNodes[0].data,
                                  "med": xmldoc.getElementsByTagName("videobitrate")[0].attributes["med"].childNodes[0].data,
                                  "high": xmldoc.getElementsByTagName("videobitrate")[0].attributes["high"].childNodes[0].data},
                "audiobitrate": { "low": xmldoc.getElementsByTagName("audiobitrate")[0].attributes["low"].childNodes[0].data,
                                  "med": xmldoc.getElementsByTagName("audiobitrate")[0].attributes["med"].childNodes[0].data,
                                  "high": xmldoc.getElementsByTagName("audiobitrate")[0].attributes["high"].childNodes[0].data},
                "samplerate": int(xmldoc.getElementsByTagName("samplerate")[0].childNodes[0].data),
                "projectprofile": project_profiles
            })

    for preset_type_name in preset_type_names:
        print()
        print(preset_type_name)
        print("".ljust(len(preset_type_name), "^"))

        for preset in sorted(preset_types, key=lambda d: d['title']):
            if preset.get("type") == preset_type_name:
                print()
                print(f"{preset.get('title')}")
                print("".ljust(len(preset.get('title')), "~"))
                print()
                print(f".. table::")
                print(f"   :widths: 30 30")
                print(f"")
                print(f"   =======================  ============")
                print(f"   Preset Attribute         Description")
                print(f"   =======================  ============")
                print(f"   Video Format             {preset.get('videoformat').upper()}")
                if preset.get('videocodec'):
                    print(f"   Video Codec              {preset.get('videocodec')}")
                if preset.get('audiocodec'):
                    print(f"   Audio Codec              {preset.get('audiocodec')}")
                    print(f"   Audio Channels           {preset.get('audiochannels')}")
                    print(f"   Audio Channel Layout     {lookup_layout(preset.get('audiochannellayout'))}")
                    print(f"   Sample Rate              {preset.get('samplerate')}")
                if preset.get('videocodec'):
                    if preset.get("videobitrate").get("low"):
                        print(f'   Video Bitrate (low)      {preset.get("videobitrate").get("low")}')
                    if preset.get("videobitrate").get("med"):
                        print(f'   Video Bitrate (med)      {preset.get("videobitrate").get("med")}')
                    if preset.get("videobitrate").get("high"):
                        print(f'   Video Bitrate (high)     {preset.get("videobitrate").get("high")}')
                if preset.get('samplerate') > 0:
                    if preset.get("audiobitrate").get("low"):
                        print(f'   Audio Bitrate (low)      {preset.get("audiobitrate").get("low")}')
                    if preset.get("audiobitrate").get("med"):
                        print(f'   Audio Bitrate (med)      {preset.get("audiobitrate").get("med")}')
                    if preset.get("audiobitrate").get("high"):
                        print(f'   Audio Bitrate (high)     {preset.get("audiobitrate").get("high")}')

                preset_profiles = sorted(preset.get("projectprofile"))
                profile_label = f'   | {preset_profiles[0]}'
                print(f"   Profiles              {profile_label}")
                if len(preset_profiles) > 1:
                    for profile in preset_profiles[1:]:
                        print(f'                            | {profile.ljust(26)}')
                print(f"   =======================  ============")
