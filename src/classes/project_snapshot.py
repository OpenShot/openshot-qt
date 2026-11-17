# Copyright (c) 2026 OpenShot Studios, LLC
# This file is part of OpenShot Video Editor (https://www.openshot.org).
# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor. If not, see <https://www.gnu.org/licenses/>.

"""Immutable save inputs, split at collection entries to keep worker decoding small."""

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class ProjectSnapshot:
    metadata: bytes
    collections: tuple

    @classmethod
    def capture(cls, data):
        def encode(value):
            return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")

        metadata = encode({key: value for key, value in data.items() if not isinstance(value, list)})
        collections = tuple(
            (key, tuple(encode(item) for item in value))
            for key, value in data.items() if isinstance(value, list))
        return cls(metadata, collections)

    def decode(self, exclude=()):
        data = json.loads(self.metadata)
        for key, entries in self.collections:
            if key in exclude:
                continue
            # One C decoder call for an entire large project can hold the GIL
            # for seconds. Decode individual clips/files between Python steps.
            data[key] = [json.loads(entry) for entry in entries]
        return data

    def chunks(self):
        """Yield a valid JSON document without joining another large string."""
        yield b"{"
        yield self.metadata[1:-1]
        separator = b"," if self.metadata != b"{}" else b""
        for key, entries in self.collections:
            yield separator
            yield json.dumps(key).encode("utf-8")
            yield b":["
            for index, entry in enumerate(entries):
                if index:
                    yield b","
                yield entry
            yield b"]"
            separator = b","
        yield b"}"

    def digest(self):
        digest = hashlib.sha256()
        for chunk in self.chunks():
            digest.update(chunk)
        return digest.digest()
