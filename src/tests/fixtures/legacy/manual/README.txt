Manual legacy import and clipboard check

Download Legacy Pickle Test Pack.zip and extract it before opening the project.
It contains a generated 1.x protocol-2 project and three PNGs, with portable
relative media paths. Use a build including the relative-media fix (f2a02162a
or later on legacy-pickle-safety); build 19145 predates that addition.

Expected playback: RED, GREEN, BLUE, each for two seconds, on one track.
Copy/paste a clip, Undo/Redo, then Save As, close and reopen.

No customer project, executable payload, shell command or network URL is included.
