from typing import Dict

import binaryninja
import binaryninjaui
from PySide6.QtCore import Qt, QRectF, QModelIndex, QStringListModel, Slot, Signal
import PySide6.QtCore as QtCore
from PySide6.QtWidgets import QVBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QTextEdit, QApplication, \
	QLineEdit, QHBoxLayout, QWidget, QAbstractItemView, QFrame, QListView, QTextBrowser, QSplitter, QTreeView
from PySide6.QtGui import QImage, QPainter, QFont, QColor, QPalette, QDesktopServices, QStandardItemModel, QStandardItem
from pygments import highlight
from pygments.lexers import ObjectiveCLexer
from pygments.formatters import HtmlFormatter
from pygments.styles import get_style_by_name
from . import objc

g_objctriage_viewtype = None


def data_has_objc_data(data):
	if data is None:
		return False
	if not isinstance(data, binaryninja.BinaryView):
		return False
	if data.parent_view is None:
		return False
	section = data.get_section_by_name("__objc_data")
	if section is None:
		return False
	return True


class ObjCClassList(QListView):
	def __init__(self, parent, data):
		QListView.__init__(self, parent)
		self.data = data
		self.model = QStringListModel()

		self.setFont(binaryninjaui.getMonospaceFont(self))

		self.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.class_list = []
		self.classes: Dict[str, 'objc.ObjCClass'] = {}
		self.class_name = ""

		objc_metadata = data.query_metadata('Objective-C')
		if objc_metadata is not None:
			methods = {}
			for mth in objc_metadata["methods"]:
				methods[mth["loc"]] = objc.ObjCCMethod(mth["name"], mth["types"], mth["loc"], mth["imp"])
			for cls in objc_metadata["classes"]:
				name = cls['name']
				instance_methods = []
				class_methods = []
				self.class_list.append(name)
				for imth in cls["instanceMethods"]:
					if imth in methods:
						instance_methods.append(methods[imth])
				for cmth in cls["classMethods"]:
					if cmth in methods:
						class_methods.append(methods[imth])
				self.classes[name] = objc.ObjCClass(name, cls["loc"], instance_methods, class_methods)
		for classname in self.class_list:
			self.classes[classname].load_non_metadata_fields(self.data, self.classes[classname].location, self.classes)

		self.model.setStringList(self.class_list)
		self.setModel(self.model)
		self.clicked.connect(self.on_clicked)

	def on_clicked(self, index):
		self.class_name = self.class_list[index.row()]
		self.classChanged.emit()

	@Signal
	def classChanged(self):
		pass


class HeaderView(QTextBrowser):
	link_clicked = Signal(str)

	def __init__(self, parent):
		QTextBrowser.__init__(self, parent)
		self.contents = ""
		self.setHtml(self.contents)
		self.setOpenExternalLinks(False)
		self.setOpenLinks(False)

		self.setFont(binaryninjaui.getMonospaceFont(self))
		self.zoomIn(2)

		self.anchorClicked.connect(self.linkClicked)

	@Slot(str)
	def linkClicked(self, url):
		self.link_clicked.emit(url.toString())

	def set_contents(self, contents):
		self.contents = contents
		self.setHtml(self.contents)


g_getData_called_counter = 0


class ObjectiveCTriageView(QWidget, binaryninjaui.View):
	def __init__(self, parent, data):
		self.data: binaryninja.BinaryView = data
		QWidget.__init__(self, parent)
		binaryninjaui.View.__init__(self)
		binaryninjaui.View.setBinaryDataNavigable(self, True)
		self.current_offset = True
		self.setupView(self)
		self.data: binaryninja.BinaryView = data
		if not data_has_objc_data(data):
			self.layout = QVBoxLayout()
			# Centered label saying there's no objc data
			self.no_data_label = QLabel("No Objective-C data found")
			self.no_data_label.setAlignment(Qt.AlignCenter)
			self.layout.addWidget(self.no_data_label)
			self.setLayout(self.layout)
			return
		# check if 'BOOL' type exists
		if self.data.get_type_by_name('BOOL') is None:
			binaryninja.log.log_warn('Did you run this without the Objective-C workflow enabled?')
			binaryninja.log.log_warn('Running "Analyze Structures" to try and fix this and create types')
			ctx: binaryninjaui.UIContext = binaryninjaui.UIContext.activeContext()
			if ctx is not None:
				act: binaryninjaui.UIActionHandler = ctx.getCurrentActionHandler()
				act.executeAction('Objective-C \\ Analyze Structures')
		self.layout = QVBoxLayout()
		self.header_view = HeaderView(self)
		self.class_list = ObjCClassList(self, data)

		self.classinfo_tab_collection = binaryninjaui.DockableTabCollection()
		self.classinfo_tabs = binaryninjaui.SplitTabWidget(self.classinfo_tab_collection)

		tab_style = binaryninjaui.GlobalAreaTabStyle()
		self.classinfo_tabs.setTabStyle(tab_style)

		self.header_view_wrapper = QWidget(self)
		self.header_view_wrapper_layout = QVBoxLayout(self.header_view_wrapper)
		self.header_view_wrapper_layout.addWidget(self.header_view)

		self.classinfo_tabs.addTab(self.header_view_wrapper, 'Header')
		self.classinfo_tabs.setCanCloseTab(self.header_view_wrapper, False)

		self.metadata_view_wrapper = QWidget(self)
		# self.classinfo_tabs.addTab(self.metadata_view_wrapper, 'Metadata')
		# self.classinfo_tabs.setCanCloseTab(self.metadata_view_wrapper, False)

		self.class_list_wrapper = QWidget(self)
		self.class_list_wrapper.setContentsMargins(0, 0, 0, 0)
		self.class_list_wrapper_layout = QVBoxLayout(self.class_list_wrapper)
		self.class_list_wrapper_layout.setContentsMargins(0, 0, 0, 0)
		self.class_list_wrapper_layout.addWidget(self.class_list)

		self.listings_tab_collection = binaryninjaui.DockableTabCollection()
		self.listings_tabs = binaryninjaui.SplitTabWidget(self.listings_tab_collection)
		self.listings_tabs.setTabStyle(tab_style)

		self.listings_tabs.addTab(self.class_list_wrapper, "Classes")
		self.listings_tabs.setCanCloseTab(self.class_list_wrapper, False)

		self.category_list_wrapper = QWidget(self)
		#
		# self.listings_tabs.addTab(self.category_list_wrapper, "Categories")
		# self.listings_tabs.setCanCloseTab(self.category_list_wrapper, False)
		#
		self.protocol_list_wrapper = QWidget(self)
		#
		# self.listings_tabs.addTab(self.protocol_list_wrapper, "Protocols")
		# self.listings_tabs.setCanCloseTab(self.protocol_list_wrapper, False)
		#
		self.cfstr_list_wrapper = QWidget(self)
		#
		# self.listings_tabs.addTab(self.cfstr_list_wrapper, "CFStrings")
		# self.listings_tabs.setCanCloseTab(self.cfstr_list_wrapper, False)

		# self.debug_text = QTextEdit(self)
		self.splitter = QSplitter(Qt.Horizontal)

		self.classinfo_tabs.selectWidget(self.header_view_wrapper)
		self.listings_tabs.selectWidget(self.class_list_wrapper)

		self.splitter.addWidget(self.listings_tabs)
		self.splitter.addWidget(self.classinfo_tabs)
		self.splitter.setSizes([300, 1200])
		self.layout.addWidget(self.splitter)
		# self.layout.addWidget(self.debug_text)
		self.setLayout(self.layout)
		self.class_list.classChanged.connect(self.updateHeaderView)
		self.header_view.link_clicked.connect(self.html_link_clicked)

	@Slot(str)
	def html_link_clicked(self, url):
		if url.startswith("https"):
			QDesktopServices.openUrl(url)
		elif url.startswith("addr"):
			offset = int(url.split("/")[1])
			self.navigateLinear(offset)
		elif url.startswith("type"):
			type_name = url.split("/")[1]
			ctx: binaryninjaui.UIContext = binaryninjaui.UIContext.activeContext()
			if ctx is not None:
				ctx.navigateToType(type_name)
		elif url.startswith("class"):
			class_name = url.split("/")[1]
			class_loc = self.class_list.classes[class_name].location

			model = self.class_list.model
			indexes = model.match(
				model.index(0, 0),
				QtCore.Qt.ItemDataRole.DisplayRole,
				class_name,
				hits=1,
				flags=QtCore.Qt.MatchFlag.MatchExactly
			)
			if indexes:
				self.class_list.setCurrentIndex(indexes[0])
				self.class_list.on_clicked(indexes[0])
				self.navigateLinear(class_loc)
		else:
			print(url)

	def updateHeaderView(self):
		class_name = self.class_list.class_name
		header_text = self.class_list.classes[class_name].render_html(self.class_list.classes.keys())
		formatter = HtmlFormatter(style=get_style_by_name('coffee'))
		css = formatter.get_style_defs()
		css += css.replace('{', ' a {')
		highlighted_code = f'<style>{css}</style>{header_text}'
		self.header_view.set_contents(highlighted_code)

	def navigateLinear(self, offset):
		ctx: binaryninjaui.UIContext = binaryninjaui.UIContext.activeContext()
		if ctx is not None:
			frame: binaryninjaui.ViewFrame = ctx.getCurrentViewFrame()
			if frame is not None:

				# If there isn't a synced pane open yet, do that now :)
				frames = ctx.getAllViewFramesForTab(ctx.getCurrentTab())
				if len(frames) == 1:
					file_ctx = frame.getFileContext()
					new_frame = binaryninjaui.ViewFrame(self, file_ctx, f"Linear:{frame.getCurrentDataType()}")
					new_pane = binaryninjaui.ViewPane(new_frame)
					ctx.openPane(new_pane, Qt.Orientation.Horizontal)
					new_frame.enableSync()

				frame.syncToOtherViews()
				frame.navigate(self.data, offset)

	def getData(self):
		try:
			return self.data
		except Exception as e:
			# no clue man
			return None

	def getCurrentOffset(self):
		return self.current_offset

	def navigate(self, offset):
		self.current_offset = offset
		return True


class ObjectiveCTriageViewType(binaryninjaui.ViewType):
	def __init__(self):
		binaryninjaui.ViewType.__init__(self, "Objective-C", "Objective-C Triage View")

	def getPriority(self, data, filename):
		if data_has_objc_data(data):
			return 100
		return 0

	def create(self, data, view_frame):
		return ObjectiveCTriageView(view_frame, data)

	@classmethod
	def init(cls):
		global g_objctriage_viewtype
		g_objctriage_viewtype = cls()
		binaryninjaui.ViewType.registerViewType(g_objctriage_viewtype)


