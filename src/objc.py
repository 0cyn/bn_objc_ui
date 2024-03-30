from io import BytesIO

import ktool
from lib0cyn.log import log
import binaryninja

g_image_map = {}
g_objc_image_map = {}
g_headers = {}


def printwrap(msg):
	print(ktool.util.strip_ansi(msg))


def load_image(data: 'binaryninja.BinaryView'):
	# log.LOG_LEVEL = ktool.LogLevel.DEBUG_TOO_MUCH
	log.LOG_FUNC = printwrap
	ktool.util.OUT_IS_TTY = False
	data_id = data.file.session_id
	if data_id in g_image_map:
		return g_image_map[data_id]

	data_bytes = bytearray(data.parent_view.read(data.parent_view.start, data.parent_view.length))
	data_io = BytesIO(data_bytes)
	image = ktool.load_image(data_io)

	g_image_map[data_id] = image
	return image


def load_objc_image(data: 'binaryninja.BinaryView'):
	data_id = data.file.session_id
	if data_id in g_objc_image_map:
		return g_objc_image_map[data_id]
	objc_image = ktool.load_objc_metadata(load_image(data))
	g_objc_image_map[data_id] = objc_image
	g_headers[data_id] = {}
	for objc_class in objc_image.classlist:
		objc_class.methods.sort(key=lambda h: h.signature)
		objc_class.properties.sort(key=lambda h: h.name)

	for objc_proto in objc_image.protolist:
		objc_proto.methods.sort(key=lambda h: h.signature)
		objc_proto.opt_methods.sort(key=lambda h: h.signature)
	type_resolver = ktool.headers.TypeResolver(objc_image)
	for objc_class in objc_image.classlist:
		g_headers[data_id][objc_class.name] = ktool.headers.Header(objc_image, type_resolver, objc_class, False).generate_html(True)

	return objc_image

