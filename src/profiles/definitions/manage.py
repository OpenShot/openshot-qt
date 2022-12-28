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


PATH = os.path.dirname(os.path.realpath(__file__))

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

# Parse legacy profiles
PROFILE_PATH = os.path.dirname(PATH)
legacy_profiles = {}
LEGACY_SAMPLE_RATIOS = {}
for profile_name in os.listdir(PROFILE_PATH):
    profile_path = os.path.join(PROFILE_PATH, profile_name)
    if not os.path.isdir(profile_path):
        profile = openshot.Profile(profile_path)
        profile_key = "%04dx%04d@%d/%d@%d:%d|%d" % (profile.info.width, profile.info.height, profile.info.fps.num,
                                            profile.info.fps.den, profile.info.display_ratio.num,
                                            profile.info.display_ratio.den, not profile.info.interlaced_frame)
        legacy_profiles[profile_key] = (profile, profile_name)
        LEGACY_SAMPLE_RATIOS[(profile.info.pixel_ratio.num, profile.info.pixel_ratio.den)] = profile

# Parse each definition *.json file in /definitions/ directory
print("Reading JSON profile definitions")
new_profiles = {}
for definition in os.listdir(PATH):
    if definition.endswith(".json"):
        print(f"- {definition}")
        definition_path = os.path.join(PATH, definition)
        with open(definition_path, "r") as f:
            json_details = json.loads(f.read())

            # Loop through profiles
            for p in json_details.get("profiles", []):
                for r in p.get("fps", []):
                    # Verify accurate DAR
                    size = openshot.Fraction(p.get("width"), p.get("height"))
                    dar = openshot.Fraction(r.get("dar").get("num"), r.get("dar").get("den"))
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

                    profile_key = "%04dx%04d@%d/%d@%d:%d|%d" % (p.get("width"), p.get("height"), r.get("num"),
                                                                r.get("den"),  r.get("dar").get("num"),
                                                                r.get("dar").get("den"), r.get("progressive"))
                    new_profiles[profile_key] = (p, r)

            if mode == "update":
                # Save definition json
                print(f" - Updating JSON {definition}")
                with open(definition_path, "w") as f1:
                    formatted_json = json.dumps(json_details, indent=4, cls=CompactJSONEncoder)
                    formatted_json = re.sub('\n            ', ' ', formatted_json, flags=re.DOTALL)
                    formatted_json = re.sub(',\n            ', ', ', formatted_json, flags=re.DOTALL)
                    formatted_json = re.sub('}, {', '},\n                {', formatted_json, flags=re.DOTALL)
                    formatted_json = re.sub('\\[{', '[\n                {', formatted_json, flags=re.DOTALL)
                    formatted_json = re.sub('}]', '}\n            ]', formatted_json, flags=re.DOTALL)
                    f1.write(formatted_json)

if mode == "validate":
    # Compare legacy and new profiles
    unmatched = []
    matched = []
    for legacy_key in legacy_profiles.keys():
        if legacy_key not in new_profiles.keys():
            legacy = legacy_profiles[legacy_key]
            unmatched.append(f"{legacy_key} {legacy[1]}")
        else:
            legacy = legacy_profiles[legacy_key]
            new_profile = new_profiles[legacy_key]
            matched.append((legacy[1], new_profile))

    print(f"\nUnmatched Legacy Profiles: {len(unmatched)}/{len(legacy_profiles.keys())}")
    for key in unmatched:
        legacy = legacy_profiles[key.split(" ")[0]]
        s = openshot.Fraction(legacy[0].info.pixel_ratio.num, legacy[0].info.pixel_ratio.den)
        print(f" - {key} = {round(legacy[0].info.width * s.ToDouble())}x{legacy[0].info.height}")

    # Compare new profiles and legacy profiles
    unmatched = []
    # for new in new_profiles.keys():
    #     if new not in legacy_profiles.keys():
    #         unmatched.append(new)
    print(f"\nUnmatched New Profiles: {len(unmatched)}/{len(new_profiles.keys())}")
    # for key in unmatched:
    #     print(f" - {key}")

if mode == "display":
    # Print new profiles
    print(f"\nNEW Profiles: {len(new_profiles.keys())}")
    for new_key in reversed(sorted(new_profiles.keys())):
        p = new_profiles[new_key]
        s = openshot.Fraction(p[1].get("sar").get("num"), p[1].get("sar").get("den"))
        s.Reduce()
        print(f' - {p[0].get("width")}x{p[0].get("height")} = {round(p[0].get("width") * s.ToDouble())}x{p[0].get("height")}\t\t({s.num}:{s.den})\t\t{new_key}')
