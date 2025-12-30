"""
 @file
 @brief This file contains the classes needed for tracking updates and distributing changes
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>

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

from classes.logger import log
from classes.app import get_app
import json
import uuid


class UpdateWatcher:
    """ Interface for classes that listen for 'undo' and 'redo' events. """

    def updateStatusChanged(self, undo_status, redo_status):
        """ Easily be notified each time there are 'undo' or 'redo' actions
        available in the UpdateManager. """
        raise NotImplementedError("updateStatus() not implemented in UpdateWatcher implementer.")


class UpdateInterface:
    """ Interface for classes that listen for changes (insert, update, and delete). """

    def changed(self, action):
        """ This method is invoked each time the UpdateManager is changed.
        The action contains all the details of what changed,
        including the type of change (insert, update, or delete). """
        raise NotImplementedError("changed() not implemented in UpdateInterface implementer.")


class UpdateAction:
    """A data structure representing a single update manager action,
    including any necessary data to reverse the action."""

    def __init__(self, type=None, key=None, values=None, old_values=None, transaction=None):
        self.type = type  # insert, update, or delete
        self.key = key or []  # list which contains the path to the item, for example: ["clips",{"id":"123"}]
        self.values = values
        self.old_values = old_values
        self.transaction = transaction

        # Set transaction id - used with undo/redo to group
        # a set of related UpdateAction objects
        if not transaction:
            # Auto set transaction id to GUID
            self.transaction = str(uuid.uuid4())

    def copy(self):
        """Create and return a copy of UpdateAction - with no references to the original"""
        # Serialize as JSON string, then load JSON string and cast back into UpdateAction
        return UpdateAction(**json.loads(json.dumps(self, default=lambda o: o.__dict__)))

    def set_old_values(self, old_vals):
        self.old_values = old_vals

    def json(self, is_array=False, only_value=False):
        """ Get the JSON string representing this UpdateAction """

        # Build the dictionary to be serialized
        if only_value:
            data_dict = json.loads(json.dumps(self.values))
        else:
            data_dict = {"type": self.type,
                         "key": self.key,
                         "value": json.loads(json.dumps(self.values)),
                         "old_values": json.loads(json.dumps(self.old_values)),
                         "transaction": self.transaction}

            # Always remove 'history' key (if found). This prevents nested "history"
            # attributes when a project dict is loaded.
            try:
                if isinstance(data_dict.get("value"), dict) and "history" in data_dict.get("value"):
                    data_dict.get("value").pop("history", None)
                if isinstance(data_dict.get("old_values"), dict) and "history" in data_dict.get("old_values"):
                    data_dict.get("old_values").pop("history", None)
            except Exception as ex:
                log.warning('Failed to clear history attribute from undo/redo data. {}'.format(ex))

        if not is_array:
            # Use a JSON Object as the root object
            update_action_dict = data_dict
        else:
            # Use a JSON Array as the root object
            update_action_dict = [data_dict]

        # Serialize as JSON
        return json.dumps(update_action_dict)

    def load_json(self, value):
        """ Load this UpdateAction from a JSON string """

        # Load JSON string
        update_action_dict = json.loads(value, strict=False)

        # Set the Update Action properties
        self.type = update_action_dict.get("type")
        self.key = update_action_dict.get("key")
        self.values = update_action_dict.get("value")
        self.old_values = update_action_dict.get("old_values")
        self.transaction = update_action_dict.get("transaction", self.transaction)

        # Always remove 'history' key (if found). This prevents nested "history"
        # attributes when a project dict is loaded.
        try:
            if isinstance(self.values, dict) and "history" in self.values:
                self.values.pop("history", None)
            if isinstance(self.old_values, dict) and "history" in self.old_values:
                self.old_values.pop("history", None)
        except Exception as ex:
            log.warning('Failed to clear history attribute from undo/redo data. {}'.format(ex))


class UpdateManager:
    """ This class is used to track and distribute changes to listeners.
    Typically, only 1 instance of this class is needed, and many different
    listeners are connected with the add_listener() method. """

    def __init__(self):
        self.statusWatchers = []  # List of watchers
        self.updateListeners = []  # List of listeners
        self.actionHistory = []  # List of actions performed to current state
        self.redoHistory = []  # List of actions undone
        self.currentStatus = [None, None]  # Status of Undo and Redo buttons (true/false for should be enabled)
        self.ignore_history = False  # Ignore saving actions to history, to prevent a huge undo/redo list
        self.last_action = None  # The last action processed
        self.pending_action = None  # Last action not added to actionHistory list
        self.transaction_id = None  # The current transaction id to be attached to any UpdateActions created
        self.data_version = 0  # Incremented on every dispatch to invalidate caches

    def load_history(self, project):
        """Load history from project"""
        self.reset()

        # Get history from project data
        history = project.get("history")

        # Loop through each, and load serialized data into updateAction objects
        # Ignore any load actions or history update actions
        for actionDict in history.get("redo", []):
            action = UpdateAction()
            action.load_json(json.dumps(actionDict))
            if action.type != "load" and action.key[0] != "history":
                self.redoHistory.append(action)
            else:
                log.info("Loading redo history, skipped key: %s" % str(action.key))
        for actionDict in history.get("undo", []):
            action = UpdateAction()
            action.load_json(json.dumps(actionDict))
            if action.type != "load" and action.key[0] != "history":
                self.actionHistory.append(action)
            else:
                log.info("Loading undo history, skipped key: %s" % str(action.key))

        # Notify watchers of new status
        self.update_watchers()

    def save_history(self, project, history_length):
        """Save history to project"""
        redo_list = []
        undo_list = []

        # Loop through each updateAction object and serialize
        # Ignore any load actions or history update actions
        history_length_int = int(history_length)
        if history_length_int == 0:
            self.update_untracked(["history"], {"redo": [], "undo": []})
            return
        for action in self.redoHistory[-history_length_int:]:
            if action.type != "load" and action.key[0] != "history":
                actionDict = json.loads(action.json(), strict=False)
                redo_list.append(actionDict)
            else:
                log.info("Saving redo history, skipped key: %s" % str(action.key))
        for action in self.actionHistory[-history_length_int:]:
            if action.type != "load" and action.key[0] != "history":
                actionDict = json.loads(action.json(), strict=False)
                undo_list.append(actionDict)
            else:
                log.info("Saving undo history, skipped key: %s" % str(action.key))

        # Set history data in project
        self.update_untracked(["history"], {"redo": redo_list, "undo": undo_list})

    def reset(self):
        """ Reset the UpdateManager, and clear all UpdateActions and History.
        This does not clear listeners and watchers. """
        self.actionHistory.clear()
        self.redoHistory.clear()
        self.pending_action = None
        self.last_action = None

        # Notify watchers of new history state
        self.update_watchers()

    def disconnect_listener(self, listener):
        """Remove a listener from the update manager"""
        if listener in self.updateListeners:
            log.info("Remove listener from UpdateManager: %s" % str(listener))
            self.updateListeners.remove(listener)

    def add_listener(self, listener, index=-1):
        """ Add a new listener (which will invoke the changed(action) method
        each time an UpdateAction is available). """

        if listener not in self.updateListeners:
            if index <= -1:
                # Add listener to end of list
                self.updateListeners.append(listener)
            else:
                # Insert listener at index
                self.updateListeners.insert(index, listener)
        else:
            log.warning("Cannot add existing listener: {}".format(str(listener)))

    def add_watcher(self, watcher):
        """ Add a new watcher (which will invoke the updateStatusChanged() method
        each time a 'redo' or 'undo' action is available). """

        if watcher not in self.statusWatchers:
            self.statusWatchers.append(watcher)
        else:
            log.warning("Cannot add existing watcher: {}".format(str(watcher)))

    def update_watchers(self):
        """ Notify all watchers if any 'undo' or 'redo' actions are available. """

        new_status = (len(self.actionHistory) >= 1, len(self.redoHistory) >= 1)
        if self.currentStatus[0] != new_status[0] or self.currentStatus[1] != new_status[1]:
            for watcher in self.statusWatchers:
                watcher.updateStatusChanged(*new_status)

    # This can only be called on actions already run,
    # as the old_values member is only populated during the
    # add/update/remove task on the project data store.
    # the old_values member is needed to reverse the changes
    # caused by actions.
    def get_reverse_action(self, action):
        """ Convert an UpdateAction into the opposite type (i.e. 'insert' becomes an 'delete') """
        reverse = UpdateAction(action.type, action.key, action.values)
        # On adds, setup remove
        if action.type == "insert":
            reverse.type = "delete"

            # replace last part of key with ID (so the delete knows which item to delete)
            id = action.values["id"]
            action.key.append({"id": id})

        # On removes, setup add with old value
        elif action.type == "delete":
            reverse.type = "insert"
            # Remove last item from key (usually the id of the inserted item)
            if reverse.type == "insert" and isinstance(reverse.key[-1], dict) and "id" in reverse.key[-1]:
                reverse.key = reverse.key[:-1]

        # On updates, just swap the old and new values data
        # Swap old and new values
        reverse.old_values = json.loads(json.dumps(action.values))
        reverse.values = json.loads(json.dumps(action.old_values))

        return reverse

    def undo(self):
        """ Undo the last UpdateAction (and notify all listeners and watchers).
            Continue until all identical transaction ids have been found. """
        # Get all actions with the same transaction id as the last one, in reverse order
        last_transaction = self.actionHistory[-1].transaction if self.actionHistory else None
        last_transactions = [a for a in reversed(self.actionHistory) if a.transaction == last_transaction]
        remove_selection = any(a.type == "insert" for a in last_transactions)

        if remove_selection:
            # Remove selections for any items about to be deleted
            for action in last_transactions:
                if action.type == "insert":
                    object_id = action.values.get("id", None)
                    get_app().window.removeSelection(object_id, None)

            # Force property and selection timers to fire
            get_app().window.show_property_timer.stop()
            get_app().window.show_property_timer.timeout.emit()
            get_app().window.selection_timer.stop()
            get_app().window.selection_timer.timeout.emit()
            get_app().processEvents()

        # Iterate each action in this transaction
        for index, last_action in enumerate(last_transactions):
            self.actionHistory.remove(last_action)

            # Copy action
            last_action = last_action.copy()

            # Add action to redo list
            self.redoHistory.append(last_action)
            self.pending_action = None
            # Get reverse of last action and perform it
            reverse = self.get_reverse_action(last_action)

            # Ignore updates to UI on all actions except last one
            ignore_refresh = (index != len(last_transactions) - 1)
            get_app().window.IgnoreUpdates.emit(ignore_refresh, True)

            # Perform next undo action
            self.dispatch_action(reverse)

            # Verify selections are still valid objects
            get_app().window.verifySelections()

    def redo(self):
        """ Redo the last UpdateAction (and notify all listeners and watchers).
            Continue until all identical transaction ids have been found. """
        # Get all actions with the same transaction id as the last one, in reverse order
        last_transaction = self.redoHistory[-1].transaction if self.redoHistory else None
        last_transactions = [a for a in reversed(self.redoHistory) if a.transaction == last_transaction]

        # Iterate through each action in this transaction
        for index, next_action in enumerate(last_transactions):
            self.redoHistory.remove(next_action)

            # Copy action
            next_action = next_action.copy()

            # Remove ID from insert (if found)
            if next_action.type == "insert" and isinstance(next_action.key[-1], dict) and "id" in next_action.key[-1]:
                next_action.key = next_action.key[:-1]

            self.actionHistory.append(next_action)
            self.pending_action = None

            # Ignore updates to UI on all actions except last one
            ignore_refresh = (index != len(last_transactions) - 1)
            get_app().window.IgnoreUpdates.emit(ignore_refresh, True)

            # Perform next redo action
            self.dispatch_action(next_action)

    # Carry out an action on all listeners
    def dispatch_action(self, action):
        """ Distribute changes to all listeners (by calling their changed() method) """

        # Every dispatched action reflects a project mutation; bump the version
        self.data_version += 1

        try:
            # Loop through all listeners
            for listener in self.updateListeners:
                # Invoke change method on listener
                listener.changed(action)

        except Exception as ex:
            log.error("Couldn't apply '{}' to update listener: {}\n{}".format(action.type, listener, ex))
        self.update_watchers()

    # Perform load action (loading all project data), clearing history for taking a new path
    def load(self, values, reset_history=True):
        """ Load all project data via an UpdateAction into the UpdateManager
        (this action will then be distributed to all listeners) """

        self.last_action = UpdateAction('load', '', values)
        if reset_history:
            self.redoHistory.clear()
            self.actionHistory.clear()
        self.pending_action = None
        self.dispatch_action(self.last_action)

    # Perform new actions, clearing redo history for taking a new path
    def insert(self, key, values):
        """ Insert a new UpdateAction into the UpdateManager
        (this action will then be distributed to all listeners) """

        self.last_action = UpdateAction('insert', key, values, transaction=self.transaction_id)
        if self.ignore_history:
            self.pending_action = self.last_action
        else:
            self.redoHistory.clear()
            self.pending_action = None
            self.actionHistory.append(self.last_action)
        self.dispatch_action(self.last_action)

    def update(self, key, values):
        """ Update the UpdateManager with an UpdateAction
        (this action will then be distributed to all listeners) """

        self.last_action = UpdateAction('update', key, values, transaction=self.transaction_id)
        if self.ignore_history:
            self.pending_action = self.last_action
        else:
            if self.last_action.key and self.last_action.key[0] != "history":
                # Clear redo history for any update except a "history" update
                self.redoHistory.clear()
            self.pending_action = None
            self.actionHistory.append(self.last_action)
        self.dispatch_action(self.last_action)

    def update_untracked(self, key, values):
        """ Update the UpdateManager with an UpdateAction, without creating
        a new entry in the history table
        (this action will then be distributed to all listeners) """
        previous_ignore = self.ignore_history
        previous_pending = self.pending_action
        self.ignore_history = True
        self.update(key, values)
        self.ignore_history = previous_ignore
        self.pending_action = previous_pending

    def delete(self, key):
        """ Delete an item from the UpdateManager with an UpdateAction
        (this action will then be distributed to all listeners) """

        self.last_action = UpdateAction('delete', key, transaction=self.transaction_id)
        if self.ignore_history:
            self.pending_action = self.last_action
        else:
            self.redoHistory.clear()
            self.pending_action = None
            self.actionHistory.append(self.last_action)
        self.dispatch_action(self.last_action)

    def apply_last_action_to_history(self, previous_value):
        """ Apply the last action to the history """
        if self.pending_action:
            self.pending_action.set_old_values(previous_value)
            self.actionHistory.append(self.pending_action)
            self.last_action = self.pending_action
            self.pending_action = None

            # Notify watchers of new history state
            self.update_watchers()
