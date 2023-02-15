OpenMoji
========

<img width="1157" alt="openmoji-github-keyvisual" src="https://user-images.githubusercontent.com/480224/71999652-1a60c000-3242-11ea-974a-96fef098147b.png">

Open-source emojis for designers, developers and everyone else! OpenMoji is an open-source project of the HfG Schwäbisch Gmünd by Benedikt Groß, Daniel Utz, 50+ students and external contributors.

👉 [OpenMoji.org/](http://openmoji.org/)

Interact, create, save, and share your work! 🌈`#openmoji`

This GitHub repository contains all of the source files and exported png/svg files of the OpenMoji project.

⚠️ Please note that the master branch is in active development, so if you're looking for stable production version please use one of the releases.


## Table of Contents

- [Styleguide](http://openmoji.org/styleguide) our beloved styleguide.
- [FAQ](FAQ.md) Check if your question has already been answered
- [Contributing](CONTRIBUTING.md) Pull Requests are welcome!
- [Developer Setup](CONTRIBUTING.md#developer-setup) how to setup node.js.
- [Font](font) infos on the OpenMoji-Color and OpenMoji-Black fonts.
- [Team](http://openmoji.org/about/#team) list of all authors and contributors.
- [Acknowledgements](http://openmoji.org/about/#acknowledgement) Thanks!


## Downloads & Distribution Channels
You can download, use and "consume" OpenMoji in various ways:

- [SVG](https://github.com/hfg-gmuend/openmoji/releases/latest): Color & Black (production ready)
- [Fonts](https://github.com/hfg-gmuend/openmoji/releases/latest): Color & Black (experimental)
- [PNG 618x618](https://github.com/hfg-gmuend/openmoji/releases/latest): Color & Black (production ready)
- [PNG 72x72](https://github.com/hfg-gmuend/openmoji/releases/latest): Color & Black (production ready)
- [OpenMoji app](https://itunes.apple.com/us/app/openmoji/id1462636288): for iOS with emoji picker
- [OpenMoji Stickers](https://itunes.apple.com/us/app/openmoji/id1462636288): for iOS Messages app
- [OpenMoji Github](https://github.com/hfg-gmuend/openmoji/): `git clone --dept 1 https://github.com/hfg-gmuend/openmoji.git` The OpenMoji repo is big! It is recommended to clone it without the entire history, note the --dept flag.
- [OpenMoji NPM Package](https://www.npmjs.com/package/openmoji): `npm install openmoji`. You can also get individual files via [UNPKG](https://unpkg.com/) direclty e.g.: unpkg.com/openmoji@12.1.0/color/svg/1F64B.svg
- [OpenMoji Jekyll Plugin](https://github.com/azadeh-afzar/OpenMoji-Jekyll-Plugin): `gem install jekyll-openmoji`


## Attribution Requirements
As an open source project, attribution is critical from a legal, practical and motivational perspective. Please give us credits! Common places for attribution are for example: to mention us in your project README, the 'About' section or the footer on a website/in mobile apps.

Attribution suggestion:

> All emojis designed by [OpenMoji](https://openmoji.org/) – the open-source emoji and icon project. License: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/#)


## Anatomy of the OpenMoji Repository

`black/` and `color/` Contains all exported .png and .svg files ¹

`data/` Contains the central openmoji.json with all meta informations for each emoji ¹

`font/` Contains the exported OpenMoji fonts ¹

`guidelines/` Contains various template files related to the styleguide ¹

`helpers/` Contains various helper scripts e.g. to export to .png and .svg, generate skintones variants, enforce the OpenMoji color palette etc. ²

`src/` Contains all source .svg files of OpenMoji. The files are broken up into folders and files corresponding with the Unicode groups and sub-groups ¹

`test/` Automated unit tests to ensure consistency across all source .svg files ²


## License
¹ OpenMoji graphics are licensed under the Creative Commons Share Alike License 4.0 ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/))

[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

² Code licensed under the GNU Lesser General Public License v3 ([LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.en.html))

[![License: LGPL-3.0](https://img.shields.io/badge/License-LGPL%20v3-lightgrey.svg)](https://www.gnu.org/licenses/lgpl-3.0.en.html)

## Instructions for Updating OpenShot with latest OpenMoji release

- Download latest OpenMoji release (**Source Zip**)
- Extract the `data/openmoji.json` file to `src/emojis/data` (very important - so we have metadata on the newest emojis)
- Extract the `color/svg` folder to `src/emojis/color/svg/` (clobber old OpenShot emojis)
- Run `python3 src/emojis/optimize-emojis.py` (this will create a new openmoji-optimized.json file used at runtime, and will delete all unused emojis from OpenShot)
- Rebuild the icon cache (`python3 images/generate_cache.py`)
- Rebuild the language translation templates (`python3 src/language/generate_translations.py`)