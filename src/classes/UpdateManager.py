""" 
 @file
 @brief This file contains the classes needed for tracking updates and distributing changes
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2014 OpenShot Studios, LLC
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

class UpdateWatcher:
	""" Interface for classes that listen for 'undo' and 'redo' events. """
	
	def updateStatusChanged(self, undo_status, redo_status):
		""" Easily be notified each time there are 'undo' or 'redo' actions available in the UpdateManager. """
		raise NotImplementedError("updateStatus() not implemented in UpdateWatcher implementer.")

class UpdateInterface:
	""" Interface for classes that listen for changes (insert, update, and delete). """
	
	def changed(self, action):
		""" This method is invoked each time the UpdateManager is changed. The action contains all the details of what changed,
		including the type of change (insert, update, or delete). """
		raise NotImplementedError("changed() not implemented in UpdateInterface implementer.")

class UpdateAction:
	"""An data structure representing a single update manager action, including any necessary data to reverse the action."""
	
	def __init__(self, type, key, values=None, partial_update=False):
		self.type = type	# insert, update, or delete
		self.key = key		# list which contains the path to the item, for example: ["clips",{"id":"123"}]
		self.values = values
		self.old_values = None
		self.partial_update = partial_update
		
	def set_old_values(self, old_vals):
		self.old_values = old_vals
		
class UpdateManager:
	""" This class is used to track and distribute changes to listeners. Typically, only 1 instance of this class is needed,
	and many different listeners are connected with the add_listener() method. """
	
	def __init__(self):
		self.statusWatchers = []	# List of watchers
		self.updateListeners = []	# List of listeners
		self.actionHistory = []		# List of actions performed to current state
		self.redoHistory = []		# List of actions undone
		self.currentStatus = [None, None] #Status of Undo and Redo buttons (true/false for should be enabled)
		
	def reset(self):
		""" Reset the UpdateManager, and clear all UpdateActions and History. This does not clear listeners and watchers. """
		self.actionHistory.clear()
		self.redoHistory.clear()
		
	def add_listener(self, listener):
		""" Add a new listener (which will invoke the changed(action) method each time an UpdateAction is available). """
		
		if not listener in self.updateListeners:
			self.updateListeners.append(listener)
		else:
			log.warning("Listener already added.")
			
	def add_watcher(self, watcher):
		""" Add a new watcher (which will invoke the updateStatusChanged() method each time a 'redo' or 'undo' action is available). """
		
		if not watcher in self.statusWatchers:
			self.statusWatchers.append(watcher)
		else:
			log.warning("Watcher already added.")
		
	def update_watchers(self):
		""" Notify all watchers if any 'undo' or 'redo' actions are available. """
		
		new_status = (len(self.actionHistory) >= 1, len(self.redoHistory) >= 1)
		if self.currentStatus[0] != new_status[0] or self.currentStatus[1] != new_status[1]:
			for watcher in self.statusWatchers:
				watcher.updateStatusChanged(*new_status)
		
	#This can only be called on actions already run,
	# as the old_values member is only populated during the
	# add/update/remove task on the project data store.
	# the old_values member is needed to reverse the changes
	# caused by actions.
	def get_reverse_action(self, action):
		""" Convert an UpdateAction into the opposite type (i.e. 'insert' becomes an 'delete') """
		
		#log.info("Reversing action: %s, %s, %s, %s", action.type, action.key, action.values, action.partial_update)
		reverse = UpdateAction(action.type, action.key, action.values, action.partial_update)
		#On adds, setup remove
		if action.type == "insert":
			reverse.type = "delete"
		#On removes, setup add with old value
		elif action.type == "delete":
			reverse.type = "insert"
			
		#On updates, just swap the old and new values data
		#Swap old and new values
		reverse.old_values = action.values
		reverse.values = action.old_values
		
		#log.info("Reversed values: %s, %s, %s, %s", reverse.type, reverse.key, reverse.values, reverse.partial_update)
		return reverse
			
	def undo(self):
		""" Undo the last UpdateAction (and notify all listeners and watchers) """
		
		if len(self.actionHistory) > 0:
			last_action = self.actionHistory.pop()
			self.redoHistory.append(last_action)
			#Get reverse of last action and perform it
			reverse_action = self.get_reverse_action(last_action)
			self.dispatch_action(reverse_action)
		
	def redo(self):
		""" Redo the last UpdateAction (and notify all listeners and watchers) """
		
		if len(self.redoHistory) > 0:
			#Get last undone action off redo history (remove)
			next_action = self.redoHistory.pop()
			self.actionHistory.append(next_action)
			#Perform next redo action
			self.dispatch_action(next_action)
	
	#Carry out an action on all listeners
	def dispatch_action(self, action):
		""" Distribute changes to all listeners (by calling their changed() method) """
		
		try:
			# Loop through all listeners
			for listener in self.updateListeners:
				# Invoke change method on listener
				listener.changed(action)

		except Exception as ex:
			log.error("Couldn't apply '%s' to update listener: %s\n%s", action.type, listener, ex)
		self.update_watchers()
	
	#Perform new actions, clearing redo history for taking a new path
	def insert(self, key, values):
		""" Insert a new UpdateAction into the UpdateManager (this action will then be distributed to all listeners) """
		
		self.redoHistory.clear()
		self.actionHistory.append(UpdateAction('insert', key, values))
		self.dispatch_action(self.actionHistory[-1])
		
	def update(self, key, values, partial_update=False):
		""" Update the UpdateManager with an UpdateAction (this action will then be distributed to all listeners) """
		
		self.redoHistory.clear()
		self.actionHistory.append(UpdateAction('update', key, values, partial_update))
		self.dispatch_action(self.actionHistory[-1])
		
	def delete(self, key):
		""" Delete an item from the UpdateManager with an UpdateAction (this action will then be distributed to all listeners) """
		
		self.redoHistory.clear()
		self.actionHistory.append(UpdateAction('delete', key))
		self.dispatch_action(self.actionHistory[-1])
