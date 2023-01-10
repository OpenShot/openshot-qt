# Parse JSON profile definitions and provide some useful functions for managing profiles
# used in OpenShot.
#
# Args:
#  - "generate": Generate a new set of profile files for OpenShot (1 text file per profile)
#  - "validate": Parse through all definitions and validate the math (aspect ratios, sample ratios, etc...)
#  - "update": Update all JSON definition sample ratios
#  - "display": Print all JSON profiles to the screen

import re
import os
import sys
import json
import openshot


PATH = os.path.dirname(os.path.realpath(__file__))
PROFILE_PATH = os.path.dirname(PATH)
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
            else:
                self.indentation_level += 1
                output = [self.indent_str + self.encode(el) for el in o]
                self.indentation_level -= 1
                return "[\n" + ",\n".join(output) + "\n" + self.indent_str + "]"

        elif isinstance(o, dict):
            self.indentation_level += 1
            output = [self.indent_str + f"{json.dumps(k)}: {self.encode(v)}" for k, v in o.items()]
            self.indentation_level -= 1
            return "{\n" + ",\n".join(output) + "\n" + self.indent_str + "}"
        else:
            return json.dumps(o)

    @property
    def indent_str(self) -> str:
        return " " * self.indentation_level * self.indent

    def iterencode(self, o, **kwargs):
        """Required to also work with `json.dump`."""
        return self.encode(o)


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


def replace_preset_profile(match):
    """Replace matched string"""
    legacy_profile_name = match.groups(0)[0]
    for key, profile_details in legacy_profiles.items():
        for profile_tuple in profile_details:
            legacy_profile = profile_tuple[0]
            if legacy_profile_name == legacy_profile.info.description:
                new_profile_path = os.path.join(PROFILE_PATH, legacy_profile.Key())
                new_profile_obj = openshot.Profile(new_profile_path)
                return f"\t<projectprofile>{new_profile_obj.info.description}</projectprofile>"


# Check for arg value
mode = ""
if len(sys.argv) <= 1:
    print("Please pass a valid argument: 'generate', 'validate', 'update'")
    exit(1)
else:
    mode = sys.argv[1]

# Generate possible sample aspect ratios (1-100:1-100)
SAMPLE_RATIOS = [(10, 11), (12, 11), (40, 33), (8, 9), (32, 27), (1, 1), (4, 3), (16, 9), (8, 5), (32, 15),
                 (16, 15), (64, 45), (23, 24), (9, 10), (6, 5), (24, 11), (20, 11), (24, 17), (32, 17), (32, 11),
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
                    if size.num != dar.num and size.den != dar.den:
                        for s in SAMPLE_RATIOS:
                            common_rate = openshot.Fraction(s[0], s[1])
                            diff = (size.ToDouble() * common_rate.ToDouble()) - dar.ToDouble()
                            if 0.0 <= diff < smallest_diff:
                                smallest_diff = diff
                                smallest_fraction = s

                        if not smallest_fraction:
                            print(f"{p} - {r}: size: {size.num}:{size.den}, {dar.num}:{dar.den}")
                        else:
                            if smallest_diff > 0.01:
                                raise Exception(f" BAD SAMPLE RATIO: {smallest_diff} ({smallest_fraction[0]}:{smallest_fraction[0]}) for {p.get('width')}x{p.get('height')} @ {r.get('dar').get('num')}:{r.get('dar').get('den')}")
                            r["sar"] = {"num": smallest_fraction[0], "den": smallest_fraction[1]}
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
        if legacy_key in NEW_PROFILES.keys():
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
    # Delete legacy profiles
    for profile_name in os.listdir(PROFILE_PATH):
        profile_path = os.path.join(PROFILE_PATH, profile_name)
        if not os.path.isdir(profile_path):
            os.unlink(profile_path)

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

            # Format file name for new profile
            profile_abr = p[2]
            profile_notes = p[0].get("notes")
            fps_notes = p[1].get("notes")
            for possible_tag in [profile_abr, profile_notes, fps_notes]:
                if possible_tag and possible_tag not in ["HDTV", "VGA", "FB"] and possible_tag not in tags:
                    tags.append(possible_tag)

            interlaced_string = "i"
            progressive_string = "0"
            if not profile.info.interlaced_frame:
                interlaced_string = "p"
                progressive_string = "1"
            fps_string = f'{profile.info.fps.num}'
            if profile.info.fps.den != 1:
                fps_string = f'{profile.info.fps.ToDouble():.04}'

            profile_name = profile.Key()
            profile_path = os.path.join(PROFILE_PATH, profile_name)

        # Create new profile file
        profile_body = f"""description={" ".join(tags)} {profile.info.height}{interlaced_string} {fps_string} fps
frame_rate_num={profile.info.fps.num}
frame_rate_den={profile.info.fps.den}
width={profile.info.width}
height={profile.info.height}
progressive={progressive_string}
sample_aspect_num={profile.info.pixel_ratio.num}
sample_aspect_den={profile.info.pixel_ratio.den}
display_aspect_num={profile.info.display_ratio.num}
display_aspect_den={profile.info.display_ratio.num}"""

        # Write file
        print(f"Generating profile file: {profile_name}")
        with open(profile_path, "w") as profile_file_object:
            profile_file_object.write(profile_body)

    # Migrate any related presets
    PRESETS_PATH = os.path.join(os.path.dirname(os.path.dirname(PATH)), "presets")
    for preset_name in os.listdir(PRESETS_PATH):
        preset_path = os.path.join(PRESETS_PATH, preset_name)
        with open(preset_path, "r") as f:
            preset_body = f.read()
            preset_body = re.sub(PRESET_REGEX, replace_preset_profile, preset_body)
            with open(preset_path, "w") as f1:
                f1.write(preset_body)

if mode == "display":
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

            sar = profile.info.pixel_ratio
            sar.Reduce()
            print(f'{profile.Key()}\t\t{profile.ShortName()}\t\t{profile.LongName()}\t\t{profile.LongNameWithDesc()}')