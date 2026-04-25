from enum import Enum
from io import BytesIO

import binaryninja

from dataclasses import dataclass
from typing import List, Dict, Union, Tuple


type_encodings = {"c": "char", "i": "int", "s": "short", "l": "long", "q": "NSInteger", "C": "unsigned char",
	"I": "unsigned int", "S": "unsigned short", "L": "unsigned long", "A": "uint8_t", "Q": "NSUInteger", "f": "float",
	"d": "CGFloat", "b": "BOOL", "@": "id", "B": "BOOL", "v": "void", "*": "char *", "#": "Class", ":": "SEL",
	"?": "unk", "T": "unk"}

g_image_map = {}
g_objc_image_map = {}
g_headers = {}


@dataclass
class ClassRenderOptions:
	render_properties: bool = True
	render_ivars: bool = True
	alpha_sort_props: bool = False
	alpha_sort_methods: bool = True


class Struct_Representation:
	def __init__(self, processor: 'TypeProcessor', type_str: str):
		# {name=dd}

		# Remove the outer {}, then get everything to the left of the equal sign
		self.name: str = type_str[1:-1].split('=')[0]

		if '=' not in type_str:
			self.fields = []
			return

		self.field_names = []

		process_string = type_str[1:-1].split('=', 1)[1]

		if process_string.startswith('"'):  # Named struct
			output_string = ""

			in_field = False
			in_substruct_depth = 0

			field = ""

			for character in process_string:
				if character == '{':
					in_substruct_depth += 1
					output_string += character
					continue

				elif character == '}':
					in_substruct_depth -= 1
					output_string += character
					continue

				if in_substruct_depth == 0:
					if character == '"':
						if in_field:
							self.field_names.append(field)
							in_field = False
							field = ""
						else:
							in_field = True
					else:
						if in_field:
							field += character
						else:
							output_string += character
				else:
					output_string += character

			process_string = output_string

		# Remove the outer {},
		# get everything after the first = sign,
		# Process that via the processor
		# Save the resulting list to self.fields
		self.fields = processor.process(process_string)

	def __str__(self):
		ret = "typedef struct " + self.name + " {\n"

		if not self.fields:
			ret += "} // Error Processing Struct Fields"
			return ret

		for i, field in enumerate(self.fields):
			field_name = f'field{str(i)}'

			if len(self.field_names) > 0:
				try:
					field_name = self.field_names[i]
				except IndexError:
					log.debug(f'Missing a field in struct {self.name}')

			if isinstance(field.value, Struct_Representation):
				field = field.value.name
			else:
				field = field.value

			ret += "    " + field + ' ' + field_name + ';\n'
		ret += '} ' + self.name + ';'
		if len(self.fields) == 0:
			ret += " // Error Processing Struct Fields"
		return ret


class EncodingType(Enum):
	METHOD = 0
	PROPERTY = 1
	IVAR = 2


class EncodedType(Enum):
	STRUCT = 0
	NAMED = 1
	ID = 2
	NORMAL = 3


class Type:
	def __init__(self, processor, type_string, pc=0):
		start = type_string[0]
		self.child = None
		self.pointer_count = pc

		if start in type_encodings.keys():
			self.type = EncodedType.NORMAL
			self.value = type_encodings[start]
			return

		elif start == '"':
			self.type = EncodedType.NAMED
			self.value = type_string[1:-1].lstrip('"').rstrip('"')
			return

		elif start == '{':
			self.type = EncodedType.STRUCT
			self.value = Struct_Representation(processor, type_string)
			return
		raise ValueError(f'Struct with type {start} not found')

	def __str__(self):
		pref = ""
		for i in range(0, self.pointer_count):
			pref += "*"
		return pref + str(self.value)


class TypeProcessor:
	def __init__(self):
		self.structs = {}
		self.type_cache = {}

	def save_struct(self, struct_to_save: Struct_Representation):
		if struct_to_save.name not in self.structs.keys():
			self.structs[struct_to_save.name] = struct_to_save
		else:
			if len(self.structs[struct_to_save.name].fields) == 0:
				self.structs[struct_to_save.name] = struct_to_save
			# If the struct being saved has more field names than the one we already have saved,
			#   save this one instead.
			if len(struct_to_save.field_names) > 0 and len(self.structs[struct_to_save.name].field_names) == 0:
				self.structs[struct_to_save.name] = struct_to_save

	def process(self, type_to_process: str):
		if type_to_process in self.type_cache:
			return self.type_cache[type_to_process]
		# noinspection PyBroadException
		try:
			tokens = self.tokenize(type_to_process)
			types = []
			pc = 0
			for i, token in enumerate(tokens):
				if token == "^":
					pc += 1
				else:
					typee = Type(self, token, pc)
					types.append(typee)
					if typee.type == EncodedType.STRUCT:
						self.save_struct(typee.value)
					pc = 0
			self.type_cache[type_to_process] = types
			return types
		except Exception:
			pass

	@staticmethod
	def tokenize(type_to_tokenize: str):
		# ^Idd^{structZero=dd{structName={innerStructName=dd}}{structName2=dd}}

		# This took way too long to write
		# Apologies for lack of readability, it splits up the string into a list
		# Makes every character a token, except root structs
		#   which it compiles into a full string with the contents and tacks onto said list
		tokens = []
		parsing_brackets = False
		bracket_count = 0
		buffer = ""
		for c in type_to_tokenize:
			if parsing_brackets:
				buffer += c
				if c == "{":
					bracket_count += 1
				elif c == "}":
					bracket_count -= 1
					if bracket_count == 0:
						tokens.append(buffer)
						parsing_brackets = False
						buffer = ""
			elif c in type_encodings or c == "^":
				tokens.append(c)
			elif c == "{":
				buffer += "{"
				parsing_brackets = True
				bracket_count += 1
			elif c == '"':
				try:
					tokens = [type_to_tokenize.split('@', 1)[1]]
				except Exception as ex:
					log.warning(f'Failed to process type {type_to_tokenize} with {ex}')
					return []
				break
		return tokens


type_processor = TypeProcessor()


def _renderable_type(method_type: Type):
	if method_type.type == EncodedType.NORMAL:
		return str(method_type)
	elif method_type.type == EncodedType.STRUCT:
		ptr_addition = ""
		for i in range(0, method_type.pointer_count):
			ptr_addition += '*'
		return 'struct ' + method_type.value.name + ' ' + ptr_addition


@dataclass
class ObjCCMethod:
	name: str
	typestr: str
	location: int
	imp_location: int

	def render_html(self) -> str:
		types = type_processor.process(self.typestr)

		try:
			return_string = _renderable_type(types[0]).strip()
		except TypeError:
			return_string = '?'

		try:
			arguments = [_renderable_type(i).strip() for i in types[1:]]
		except TypeError:
			arguments = ['?' for i in range(self.name.count(':'))]

		ret = '<span class="p">(</span><span class="p">' + return_string + '</span><span class="p">)</span>'

		if not arguments:
			return (
				ret
				+ f'<a href="addr/{self.imp_location}"> <span class="nf">{self.name}</span></a>'
				+ '<span class="p">;</span>'
			)

		segments = [f'<a href="addr/{self.imp_location}">']
		for i, item in enumerate(self.name.split(':')):
			if not item:
				continue
			try:
				segments.append(f'<span class="nf">{item}:</span>'
								'<span class="p">(</span>'
								f'<span class="nv">{arguments[i + 2]}</span>'
								'<span class="p">)</span>'
								f'arg{i} ')
			except IndexError:
				segments.append(f'<span class="nf">{item}</span> ')

		sig = ''.join(segments)
		# We blindly add a space at the end of every argument, we need to remove the final one here.
		sig = sig.rstrip()
		sig += f'</a><span class="p">;</span>'

		return ret + sig


class ObjCProperty:

	_ATTR_ENCODINGS = {"&": "retain", "N": "nonatomic", "W": "weak", "R": "readonly", "C": "copy"}

	def __init__(self, name, attr_string):
		super().__init__()
		self.name = name
		self.location = 0
		self.getter = None
		self.setter = None
		self.ivar = None
		self.type = None
		self.type_is_ptr = False
		self.attributes = []

		self._parse_attr_string(attr_string)

	def _parse_attr_string(self, attr_string):
		attr_tokens = [i for i in attr_string.split(',') if i != '']

		attr: str
		for attr in attr_tokens:
			op = attr[0]
			if op == "T":
				if attr[1] == "@":
					self.type_is_ptr = True
				self.type = str(type_processor.process(attr[1:])[0])
			if op == "V":
				self.ivar = attr[1:]
			if op == "G":
				self.getter = attr[1:]
			if op == "S":
				self.setter = attr[1:]
			if op in self._ATTR_ENCODINGS:
				self.attributes.append(ObjCProperty._ATTR_ENCODINGS[op])
		if self.getter is not None:
			self.attributes.append(f'getter={self.getter}')
		if self.setter is not None:
			self.attributes.append(f'setter={self.setter}')

	def render_html(self, cls: 'ObjCClass'):
		ret = ''
		if self.type is None or self.name == '' or self.name is None:
			self.type = '(unknown type)'
			ret += '// '

		if self.name == '' or self.name is None:
			self.name = '(unknown name)'

		ret += '<span class="k">@property</span> '

		if len(self.attributes) > 0:
			ret += '<span class="p">(</span>' + '<span class="p">,</span> '.join([f'<span class="p">{i}</span>' for i
																				  	in self.attributes
																				  ]) + '<span class="p">)</span> '
		if self.type.startswith('<'):
			ret += "NSObject"
			ret += self.type
		else:
			ret += f'<span class="bp"><a href="type/{self.type}">{self.type}</a></span>'
		if self.type_is_ptr:
			ret += '<span class="o">*</span>'
		ret += ' '
		ret += f'<span class="n">{self.name}</span><span class="p">;</span>'

		getter = self.getter
		getter_addr = 0
		if getter is None:
			getter = self.name
		setter = self.setter
		setter_addr = 0
		if setter is None:
			setter = 'set' + self.name[0].upper() + self.name[1:] + ':'
		for inst_method in cls.instance_methods:
			if inst_method.name == getter:
				getter_addr = inst_method.imp_location
			if inst_method.name == setter:
				setter_addr = inst_method.imp_location

		if getter_addr != 0 or setter_addr != 0:
			ret += '<span class="c1"> // '
			if getter_addr != 0:
				ret += f'<a href="addr/{getter_addr}">Getter</a> '
			if setter_addr != 0:
				if getter_addr != 0:
					ret += '|| '
				ret += f'<a href="addr/{setter_addr}">Setter</a> '
			ret += "</span>"

		return ret

@dataclass
class ObjCIvar:
	name: str
	type: str
	offset: int

	def render_html(self, classname, classlist):
		if self.type in classlist:
			typestr = "class/" + self.type
		else:
			typestr = "type/" + self.type
		return f' <span class="c1">/* <a href="type/{classname}"> 0x{self.offset:0{4}x}</a> */</span> ' \
			   f'<span class="bp"><a href="{typestr}">{self.type}</a></span> <span class="n">{self.name}</span>' \
			   f'<span class="p">;</span>'


@dataclass
class ObjCClass:
	name: str
	location: int
	instance_methods: List[ObjCCMethod]
	class_methods: List[ObjCCMethod]
	properties: List[ObjCProperty] = None

	def load_non_metadata_fields(self, view: binaryninja.BinaryView, loc: int, classes):

		self.superclass_name: str = None
		self.superclass_addr: int = None
		self.superclass_is_known: bool = False
		self.properties = []
		self.ivars = []

		super_ptr = loc + 0x8
		super_loc = view.read_int(super_ptr, 8, False)
		super_is_known = view.is_valid_offset(super_loc) and not view.is_offset_extern_semantics(super_loc)

		self.superclass_addr = super_loc
		if super_is_known:
			cls: 'ObjCClass'
			for supername, cls in classes.items():
				if cls.location == super_loc:
					self.superclass_name = supername
		else:
			if super_loc != 0 and view.get_symbol_at(super_loc) is not None:
				self.superclass_name = view.get_symbol_at(super_loc).name.split('$_')[1]

		self.superclass_is_known = super_is_known

		class_ro_ptr = loc + 0x20
		class_ro_loc = view.read_int(class_ro_ptr, 8, False)

		prop_list_ptr = class_ro_loc + 0x40
		prop_list_location = view.read_int(prop_list_ptr, 8, False)
		
		ivar_list_ptr = class_ro_loc + 0x30
		ivar_list_location = view.read_int(ivar_list_ptr, 8, False)

		if prop_list_location != 0:
			prop_cnt_ptr = prop_list_location + 4
			prop_cnt = view.read_int(prop_cnt_ptr, 4, False)
			prop_start = prop_list_location + 8
			for offset_mult in range(0, prop_cnt):
				offset = prop_start + (offset_mult * 0x10)
				name_ptr = view.read_int(offset, 8, False)
				attr_ptr = view.read_int(offset + 8, 8, False)
				# print(f'cls {self.name} {hex(self.location)} - @ {hex(offset)} -> {hex(name_ptr)} {hex(attr_ptr)}')

				name = ''
				attr = ''

				reader = view.reader(name_ptr)
				c = name_ptr
				while c != 0:
					c = reader.read8()
					name += chr(c)

				c = attr_ptr
				reader.seek(attr_ptr)
				while c != 0:
					c = reader.read8()
					attr += chr(c)

				self.properties.append(ObjCProperty(name[:-1], attr[:-1]))  # cut off \0 from ends.
				
		if ivar_list_location != 0:
			ivar_cnt_ptr = ivar_list_location + 4
			ivar_cnt = view.read_int(ivar_cnt_ptr, 4, False)
			ivar_start = ivar_list_location + 8

			for offset_mult in range(0, ivar_cnt):
				offset = ivar_start + (offset_mult * 0x20)

				ivar_offset_ptr = view.read_int(offset, 8, False)
				name_ptr = view.read_int(offset + 8, 8, False)
				attr_ptr = view.read_int(offset + 16, 8, False)

				ivar_offset = view.read_int(ivar_offset_ptr, 4, False)

				name = ""
				attr = ""

				reader = view.reader(name_ptr)
				c = name_ptr
				while c != 0:
					c = reader.read8()
					name += chr(c)

				reader = view.reader(attr_ptr)
				c = attr_ptr
				while c != 0:
					c = reader.read8()
					attr += chr(c)

				self.ivars.append(ObjCIvar(name, str(type_processor.process(attr)[0]), ivar_offset))

	def render_html(self, all_classnames, render_options: ClassRenderOptions = ClassRenderOptions()):
		r = f'<span class="o">@interface</span> <span class="s1"><a href="type/{self.name}">{self.name}</a></span>'

		if self.superclass_name not in [None, '']:
			r += '<span class="p"> : </span>'
			if self.superclass_is_known:
				r += f'<a href="class/{self.superclass_name}">'
				r += f'<span class="bp">{self.superclass_name}</span>'
			elif self.superclass_addr not in [None, 0]:
				r += f'<a href="addr/{self.superclass_addr}">'
				r += f'<span class="n">{self.superclass_name}</span>'
			if self.superclass_addr not in [None, 0] or self.superclass_is_known:
				r += f'</a>'

		r += f'<span class="c1"> // <a href="addr/{self.location}">Class Metadata</a> </span>'

		if len(self.ivars) > 0 and render_options.render_ivars:
			r += '<br>{<br>'
			for ivar in self.ivars:
				r += '  ' + ivar.render_html(self.name, all_classnames) + '<br>'
			r += '}'

		r += '<br><br>'
		if render_options.render_properties:
			for prop in self.properties:
				r += prop.render_html(self) + '<br>'
		r += '<br>'
		for instance_method in (sorted(self.instance_methods, key=lambda meth: meth.name)
								if render_options.alpha_sort_methods else self.instance_methods):
			r += '-' + instance_method.render_html() + '<br>'
		r += '<br>'
		for class_method in (sorted(self.class_methods, key=lambda meth: meth.name)
								if render_options.alpha_sort_methods else self.class_methods):
			r += '+' + class_method.render_html() + '<br>'
		r += '<br>'
		r += '<span class="o">@end</span><br>'

		return r
