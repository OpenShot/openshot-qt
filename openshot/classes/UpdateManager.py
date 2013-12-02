#!/usr/bin/env python
#	OpenShot Video Editor is a program that creates, modifies, and edits video files.
#   Copyright (C) 2009  Jonathan Thomas, TJ
#
#	This file is part of OpenShot Video Editor (http://launchpad.net/openshot/).
#
#	OpenShot Video Editor is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	OpenShot Video Editor is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with OpenShot Video Editor.  If not, see <http://www.gnu.org/licenses/>.

from classes.logger import log

class UpdateInterface:
	def add(self, key, values):
		raise NotImplementedError("add() not implemted in UpdateInterface implementer.")
	def update(self, key, values, partial_update=False):
		raise NotImplementedError("update() not implemted in UpdateInterface implementer.")
	def remove(self, key):
		raise NotImplementedError("remove() not implemted in UpdateInterface implementer.")

class UpdateAction:
	"""An data structure representing a single update manager action, including any necessary data to reverse the action."""
	
	def __init__(self, type, key, values=None, partial_update=False):
		self.type = type
		self.key = key
		self.values = values
		self.old_values = None
		self.partial_update = partial_update
		
	def set_old_values(self, old_vals):
		self.old_values = old_vals
		
class UpdateManager:
	def __init__(self):
		self.updateListeners = []
		self.actionHistory = [] #List of actions performed to current state
		self.redoHistory = [] #List of actions undone
		
	def add_listener(self, listener):
		if not listener in self.updateListeners:
			self.updateListeners.append(listener)
		else:
			log.warning("Listener already added.")
		
	#This can only be called on actions already run,
	# as the old_values member is only populated during the
	# add/update/remove task on the project data store.
	# the old_values member is needed to reverse the changes
	# caused by actions.
	def get_reverse_action(self, action):
		reverse = UpdateAction(action.type, action.key, action.values, action.partial_update)
		#On adds, setup remove
		if action.type == "add":
			reverse.type = "remove"
		#On removes, setup add with old value
		elif action.type == "remove":
			reverse.type = "add"
			
		#On updates, just swap the old and new values data

		#Swap old and new values
		old_vals = reverse.old_values
		reverse.old_values = reverse.values
		reverse.values = old_vals
		
			
	def undo(self):
		log.info("History: %s", self.actionHistory)
		if len(self.actionHistory) > 0:
			last_action = self.actionHistory.pop()
			self.redoHistory.append(last_action)
			#Get reverse of last action and perform it
			reverse_action = self.get_reverse_action(last_action)
			self.dispatch_action(reverse_action)
		
	def redo(self):
		if len(self.redoHistory) > 0:
			#Get last undone action off redo history (remove)
			next_action = self.redoHistory.pop()
			self.actionHistory.append(next_action)
			#Perform next redo action
			self.dispatch_action(next_action)
	
	def dispatch_action(self, action):
		try:
			for listener in self.updateListeners:
				if action.type == "add":
					listener.add(action)
				elif action.type == "update":
					listener.update(action)
				elif action.type == "remove":
					listener.remove(action)
		except Exception as ex:
			log.error("Couldn't apply '%s' to update listener: %s", action.type, listener)
	
	#Perform new actions, clearing redo history for taking a new path
	def add(self, key, values):
		self.redoHistory.clear()
		self.actionHistory.append(UpdateAction('add', key, values))
		self.dispatch_action(self.actionHistory[-1])
	def update(self, key, values, partial_update=False):
		self.redoHistory.clear()
		self.actionHistory.append(UpdateAction('update', key, values, partial_update))
		self.dispatch_action(self.actionHistory[-1])
	def remove(self, key):
		self.redoHistory.clear()
		self.actionHistory.append(UpdateAction('remove', key))
		self.dispatch_action(self.actionHistory[-1])
