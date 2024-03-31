import binaryninja
import binaryninjaui
from PySide6.QtCore import Qt, QRectF, QModelIndex, QStringListModel, Slot, Signal
from PySide6.QtWidgets import QVBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QTextEdit, QApplication, \
	QLineEdit, QHBoxLayout, QWidget, QAbstractItemView, QFrame, QListView, QTextBrowser, QSplitter
from PySide6.QtGui import QImage, QPainter, QFont, QColor, QPalette, QDesktopServices
from pygments import highlight
from pygments.lexers import ObjectiveCLexer
from pygments.formatters import HtmlFormatter
from pygments.styles import get_style_by_name
import ktool
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

		self.objc_image = objc.load_objc_image(data)
		self.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.class_list = []
		self.class_name = ""

		for cls in self.objc_image.classlist:
			self.class_list.append(cls.name)

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
		# method on link click
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
		binaryninjaui.View.setBinaryDataNavigable(self, False)
		self.setupView(self)
		self.data = data
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

		self.header_view_wrapper = QWidget(self)
		self.header_view_wrapper_layout = QVBoxLayout(self.header_view_wrapper)
		self.header_view_label = QLabel("Header")
		self.header_view_wrapper_layout.addWidget(self.header_view_label)
		self.header_view_wrapper_layout.addWidget(self.header_view)

		self.class_list_wrapper = QWidget(self)
		self.class_list_wrapper_layout = QVBoxLayout(self.class_list_wrapper)
		self.class_list_label = QLabel("Classes")
		self.class_list_wrapper_layout.addWidget(self.class_list_label)
		self.class_list_wrapper_layout.addWidget(self.class_list)

		# self.debug_text = QTextEdit(self)
		self.splitter = QSplitter(Qt.Horizontal)
		self.splitter.addWidget(self.class_list_wrapper)
		self.splitter.addWidget(self.header_view_wrapper)
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
		elif url.startswith("meth"):
			classname = url.split("/")[1]
			methodname = url.split("/")[2]
			objc_class = None
			for c in objc.load_objc_image(self.data).classlist:
				if c.name == classname:
					objc_class = c
					break
			if objc_class is None:
				print(f"Couldn't find class {classname} in image")
				return
			method = None
			for m in objc_class.methods:
				if m.sel == methodname:
					method = m
					break
			if method is not None:
				self.navigateLinear(method.imp)
			else:
				binaryninja.log_error(f'Couldn\'t find method {methodname} in class {classname}.')
		elif url.startswith("type"):
			type_name = url.split("/")[1]
			ctx: binaryninjaui.UIContext = binaryninjaui.UIContext.activeContext()
			if ctx is not None:
				ctx.navigateToType(type_name)
		elif url.startswith("ivar"):
			class_name = url.split("/")[1]
			ivar_name = url.split("/")[2]
			objc_class: ktool.objc.Class = None
			for c in objc.load_objc_image(self.data).classlist:
				if c.name == class_name:
					objc_class = c
					break
			if objc_class is None:
				print(f"Couldn't find class {class_name} in image")
				return
			ivar: ktool.objc.Ivar = None
			for i in objc_class.ivars:
				i: ktool.objc.Ivar = i
				if i.name == ivar_name:
					ivar = i
					break
			if ivar is not None:
				ctx: binaryninjaui.UIContext = binaryninjaui.UIContext.activeContext()
				if ctx is not None:
					if not ctx.navigateToType(f'class_{class_name}', ivar.offset):
						print(f'Failed to navigate to ivar {ivar_name} in class {class_name}')
		else:
			print(url)

	def updateHeaderView(self):
		class_name = self.class_list.class_name
		objc_image = objc.load_objc_image(self.data)
		header_text = objc.g_headers[self.data.file.session_id][class_name]
		formatter = HtmlFormatter(style=get_style_by_name('zenburn'))
		css = formatter.get_style_defs()
		css += css.replace('{', ' a {')
		highlighted_code = f'<style>{css}</style>{header_text}'
		self.header_view.set_contents(highlighted_code)

	def navigateLinear(self, offset):
		ctx: binaryninjaui.UIContext = binaryninjaui.UIContext.activeContext()
		if ctx is not None:
			frame: binaryninjaui.ViewFrame = ctx.getCurrentViewFrame()
			if frame is not None:
				frame.navigate(f'Linear:{frame.getCurrentDataType()}', offset)

	def getData(self):
		try:
			return self.data
		except Exception as e:
			# no clue man
			return None

	def getCurrentOffset(self):
		return 0

	def navigate(self, offset):
		return False


class ObjectiveCTriageViewType(binaryninjaui.ViewType):
	def __init__(self):
		binaryninjaui.ViewType.__init__(self, "Objective-C", "Objective-C Triage View")

	def getPriority(self, data, filename):
		return 1

	def create(self, data, view_frame):
		return ObjectiveCTriageView(view_frame, data)

	@classmethod
	def init(cls):
		global g_objctriage_viewtype
		g_objctriage_viewtype = cls()
		binaryninjaui.ViewType.registerViewType(g_objctriage_viewtype)


