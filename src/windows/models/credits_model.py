"""
 @file
 @brief This file contains the credits model, used by the about window
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem

from classes.logger import log
from classes.app import get_app

from collections import defaultdict


class CreditsStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)


class CreditsModel():

    def update_model(self, filter=None, clear=True):
        log.debug("updating credits model.")
        app = get_app()
        _ = app._tr

        # Clear all items
        if clear:
            log.debug('cleared credits model')
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels(["", "", _("Name"), _("Email"), _("Website")])

        for person in self.credits_list:
            # Get details of person
            data = defaultdict(list)
            data.update({
                "name": person.get("name"),
                "email": person.get("email"),
                "website": person.get("website"),
                "amount": person.get("amount", 0.0),
                "icons": person.get("icons"),
            })

            if filter and not (
                filter.lower() in data["name"].lower()
                or filter.lower() in data["email"].lower()
                or filter.lower() in data["website"].lower()
            ):
                continue

            if len(data["name"]) < 2:
                # Skip blank names
                continue

            row = []
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled

            # Append type icon (PayPal, Kickstarter, Bitcoin, or Patreon)
            item = QStandardItem()
            for contrib in [n for n in self.icon_mapping if n in data["icons"]]:
                (tooltip, icon) = self.icon_mapping.get(contrib, (None, None))
                item.setIcon(icon)
                item.setToolTip(_(tooltip))
            item.setFlags(flags)
            row.append(item)

            # Append Star icon (Multiple donations, big donations, five-timer kickstarter group, etc...)
            item = QStandardItem()
            if "s" in data["icons"]:
                item.setIcon(QIcon(":/about/star-icon.png"))
                item.setToolTip(_("Multiple Contributions!"))
            item.setFlags(flags)
            row.append(item)

            for field in ["name", "email", "website"]:
                item = QStandardItem(data[field])
                item.setFlags(flags)
                row.append(item)

            self.model.appendRow(row)

    def __init__(self, credits, *args):

        _ = get_app()._tr

        # Supporter icons
        self.icon_mapping = {
            "p": (
                _("PayPal Supporter!"), QIcon(":/about/paypal-icon.png")
                ),
            "k": (
                _("Kickstarter Supporter!"),
                QIcon(":/about/kickstarter-icon.png")
                ),
            "b": (
                _("Bitcoin Supporter!"), QIcon(":/about/bitcoin-icon.png")
                ),
            "n": (
                _("Patreon Supporter!"), QIcon(":/about/patreon-icon.png")
                ),
            "d": (
                _("Developer!"), QIcon(":/about/python-icon.png")
                ),
        }

        # Create standard model
        self.app = get_app()
        self.model = CreditsStandardItemModel()
        self.model.setColumnCount(6)
        self.credits_list = credits
