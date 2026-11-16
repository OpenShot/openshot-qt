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

from qt_api import Qt, QSortFilterProxyModel, QItemSelectionModel
from qt_api import QIcon, QStandardItemModel, QStandardItem
from qt_api import get_proxy_filter_regex, regex_is_empty, regex_matches

from classes.logger import log
from classes.app import get_app

from collections import defaultdict


class CreditsStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)



class CreditsFilterProxyModel(QSortFilterProxyModel):
    """Proxy class used for sorting and filtering credits"""

    def filterAcceptsRow(self, sourceRow, sourceParent):
        """Match filter against name, email, or website columns"""
        regex = get_proxy_filter_regex(self)
        if not regex_is_empty(regex):
            model = self.sourceModel()
            for column in [2, 3, 4]:
                index = model.index(sourceRow, column, sourceParent)
                value = model.data(index)
                if regex_matches(regex, str(value)):
                    return True
            return False
        return True


class CreditsModel():

    def update_model(self, clear=True):
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

            # Remove any person string keys that explicitly contain a value of None
            for field in ["name", "email", "website"]:
                if field in person and person.get(field) is None:
                    person.pop(field)

            if len(person.get("name", "")) < 2:
                # Skip blank names
                continue


            row = []
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled

            # Append type icon (PayPal, Kickstarter, Bitcoin, or Patreon)
            item = QStandardItem()
            for contrib in [n for n in self.icon_mapping if n in person.get("icons", "")]:
                (tooltip, icon) = self.icon_mapping.get(contrib, (None, None))
                item.setIcon(icon)
                item.setToolTip(tooltip)
            item.setFlags(flags)
            row.append(item)

            # Append Star icon (Multiple donations, big donations, five-timer kickstarter group, etc...)
            item = QStandardItem()
            if "s" in person.get("icons", ""):
                item.setIcon(QIcon(":/about/star-icon.svg"))
                item.setToolTip(_("Multiple Contributions!"))
            item.setFlags(flags)
            row.append(item)

            for field in ["name", "email", "website"]:
                item = QStandardItem(person.get(field, ""))
                item.setToolTip(person.get(field, ""))
                item.setFlags(flags)
                row.append(item)

            self.model.appendRow(row)

    def __init__(self, credits, *args):

        _ = get_app()._tr

        # Supporter icons
        self.icon_mapping = {
            "p": (
                _("PayPal Supporter!"), QIcon(":/about/paypal-icon.svg")
                ),
            "k": (
                _("Kickstarter Supporter!"),
                QIcon(":/about/kickstarter-icon.svg")
                ),
            "b": (
                _("Bitcoin Supporter!"), QIcon(":/about/bitcoin-icon.svg")
                ),
            "n": (
                _("Patreon Supporter!"), QIcon(":/about/patreon-icon.svg")
                ),
            "d": (
                _("Developer!"), QIcon(":/about/python-icon.svg")
                ),
        }

        # Create standard model
        self.app = get_app()
        self.model = CreditsStandardItemModel()
        self.model.setColumnCount(6)
        self.credits_list = credits

        # Create proxy model (for sorting and filtering)
        self.proxy_model = CreditsFilterProxyModel()
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitive)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortLocaleAware(True)

        # Create selection model to share between views (if needed)
        self.selection_model = QItemSelectionModel(self.proxy_model)
