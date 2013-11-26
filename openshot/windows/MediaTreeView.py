
from classes.logger import log
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTreeView, QApplication

class MediaTreeView(QTreeView):
	drag_item_size = 32
	
	def mouseMoveEvent(self, event):
		#If mouse drag detected, set the proper data and icon and start dragging
		if event.buttons() & Qt.LeftButton == Qt.LeftButton and (event.pos() - self.startDragPos).manhattanLength() >= QApplication.startDragDistance():
			data = QMimeData()
			data.setText('Test value 1')
			drag = QDrag(self)
			drag.setMimeData(data)
			drag.setPixmap(QIcon.fromTheme('document-new').pixmap(QSize(self.drag_item_size,self.drag_item_size)))
			drag.setHotSpot(QPoint(self.drag_item_size/2,self.drag_item_size/2))
			drag.exec_()
	
	def dragEnterEvent(self, event):
		#If dragging urls onto widget, accept
		if event.mimeData().hasUrls():
			event.setDropAction(Qt.CopyAction)
			event.accept()

	#Without defining this method, the 'copy' action doesn't show with cursor
	def dragMoveEvent(self, event):
		pass
	
	#Handle a drag and drop being dropped on widget
	def dropEvent(self, event):
		log.info('Dropping file(s) on files tree.')
		for u in event.mimeData().urls():
			log.info('Url: ' + u.toString())
		event.accept()
		
	def mousePressEvent(self, event):
		self.startDragPos = event.pos()
			
	def __init__(self, *args):
		QTreeView.__init__(self, *args)
		
		#Keep track of mouse press start position to determine when to start drag
		self.startDragPos = None
		self.setAcceptDrops(True)
		
		#Load data model and add some items to it
		mod = QStandardItemModel(0, 2)
		parent_node = mod.invisibleRootItem()
		mod.setHeaderData(0, Qt.Horizontal, "Name")
		mod.setHeaderData(1, Qt.Horizontal, "Type")
		for i in range(4):
			item = QStandardItem("Clip" + str(i))
			parent_node.appendRow(item)
			index = mod.index(i,1)
			if i % 2 == 0:
				mod.setData(index, "Video")
			else:
				mod.setData(index, "Audio")
		self.setModel(mod)
	
	
	