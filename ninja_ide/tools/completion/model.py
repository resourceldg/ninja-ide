# -*- coding: utf-8 -*-
#
# This file is part of NINJA-IDE (http://ninja-ide.org).
#
# NINJA-IDE is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# any later version.
#
# NINJA-IDE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with NINJA-IDE; If not, see <http://www.gnu.org/licenses/>.


late_resolution = 0


class _TypeData(object):

    def __init__(self, lineno, data_type, line_content, oper):
        self.lineno = lineno
        self.data_type = data_type
        self.line_content = line_content
        if data_type != late_resolution:
            oper = None
        self.operation = oper
        self.from_import = False
        if isinstance(data_type, str):
            self.is_native = True
        else:
            self.is_native = False
        self.can_resolve = True

    def get_data_type(self):
        return self.data_type

    def __eq__(self, other):
        return other.line_content == self.line_content


class Structure(object):

    def __init__(self):
        self.attributes = {}
        self.functions = {}
        self.parent = None

    def add_function(self, function):
        function.parent = self
        self.functions[function.name] = function

    def add_attributes(self, attributes):
        #attributes = {name: [(lineno, type),...]}
        for attribute in attributes:
            if attribute[0] in self.attributes:
                assign = self.attributes[attribute[0]]
            else:
                assign = Assign(attribute[0])
            assign.add_data(*attribute[1:])
            assign.parent = self
            self.attributes[assign.name] = assign

    def update_attributes(self, attributes):
        for name in self.attributes:
            if name in attributes:
                assign = self.attributes[name]
                old_assign = attributes[name]
                for type_data in assign.data:
                    if type_data in old_assign.data:
                        old_type = old_assign.data[
                            old_assign.data.index(type_data)]
                        if type_data.line_content == old_type.line_content:
                            type_data.data_type = old_type.data_type

    def update_functions(self, functions):
        for func_name in self.functions:
            if func_name in functions:
                old_func = functions[func_name]
                function = self.functions[func_name]
                function.update_functions(old_func.functions)
                function.update_attributes(old_func.attributes)
                # Function Arguments
                for arg in function.args:
                    if arg in old_func.args:
                        argument_type = function.args[arg].data[0]
                        old_type = old_func.args[arg].data[0]
                        if argument_type.line_content == old_type.line_content:
                            argument_type.data_type = old_type.data_type
                # Function Returns
                for type_data in function.return_type:
                    if type_data in old_func.return_type:
                        old_type = old_func.return_type[
                            old_func.return_type.index(type_data)]
                        if type_data.line_content == old_type.line_content:
                            type_data.data_type = old_type.data_type

    def get_attribute_type(self, name):
        """Return a tuple with:(Found, Type)"""
        result = (False, None)
        var_names = name.split('.')
        attr = self.attributes.get(var_names[0], None)
        if attr is not None:
            result = (True, attr.get_data_type())
        elif self.parent.__class__ is Function:
            result = self.parent.get_attribute_type(name)
        return result

    def _get_scope_structure(self, structure, scope):
        struct = structure
        if len(scope) > 0:
            scope_name = scope[0]
            new_struct = structure.functions.get(scope_name, None)
            struct = self._get_scope_structure(new_struct, scope[1:])
        return struct

    def _resolve_attribute(self, type_data, attrs):
        object_type = type_data.get_data_type()
        return (True, object_type)

    def recursive_search_type(self, structure, attrs, scope):
        result = (False, None)
        structure = self._get_scope_structure(structure, scope)
        if structure:
            attr_name = attrs[0]
            data_type = structure.get_attribute_type(attr_name)
            result = data_type
#            if assign is not None:
#                result = self._resolve_attribute(assign, attrs[1:])
        return result


class Module(Structure):

    def __init__(self):
        super(Module, self).__init__()
        self.imports = {}
        self.classes = {}

    def add_imports(self, imports):
        for imp in imports:
            line_content = "import %s" % imp[1]
            info = _TypeData(None, imp[1], line_content, None)
            self.imports[imp[0]] = info

    def add_class(self, clazz):
        clazz.parent = self
        self.classes[clazz.name] = clazz

    def update_classes(self, classes):
        for clazz_name in self.classes:
            if clazz_name in classes:
                clazz = self.classes[clazz_name]
                clazz.update_attributes(classes[clazz_name].attributes)
                clazz.update_functions(classes[clazz_name].functions)

    def get_type(self, main_attr, child_attrs='', scope=None):
        result = (False, None)
        if not scope:
            value = self.imports.get(main_attr,
                self.attributes.get(main_attr, None))
            if value is not None:
                result = (True, value.get_data_type())
        elif main_attr == 'self':
            clazz_name = scope[0]
            clazz = self.classes.get(clazz_name, None)
            if clazz is not None:
                result = clazz.get_attribute_type(child_attrs)
            if child_attrs == '' and clazz is not None:
                items = clazz.get_completion_items()
                result = (False, items)
        elif scope:
            scope_name = scope[0]
            structure = self.classes.get(scope_name,
                self.functions.get(scope_name, None))
            if structure is not None:
                attrs = [main_attr] + child_attrs.split('.')
                if len(attrs) > 1 and attrs[1] == '':
                    del attrs[1]
                result = self.recursive_search_type(
                    structure, attrs, scope[1:])
                if not result[0]:
                    value = self.imports.get(main_attr,
                        self.attributes.get(main_attr, None))
                    if value is not None:
                        result = (True, value.get_data_type())

        if result[1].__class__ is Clazz:
            result = (False, result[1].get_completion_items())
        return result

    def get_imports(self):
        module_imports = ['import __builtin__']
        for name in self.imports:
            module_imports.append(self.imports[name].line_content)
        return module_imports

    def need_resolution(self):
        if self._check_attr_func_resolution(self):
            return True
        for cla in self.classes:
            clazz = self.classes[cla]
            if self._check_attr_func_resolution(clazz):
                return True
        return False

    def _check_attr_func_resolution(self, structure):
        for attr in structure.attributes:
            attribute = structure.attributes[attr]
            for d in attribute.data:
                if d.data_type == late_resolution:
                    return True
        for func in structure.functions:
            function = structure.functions[func]
            for attr in function.attributes:
                attribute = function.attributes[attr]
                for d in attribute.data:
                    if d.data_type == late_resolution:
                        return True
        return False


class Clazz(Structure):

    def __init__(self, name):
        super(Clazz, self).__init__()
        self.name = name
        self.bases = []
        self.decorators = []

    def get_completion_items(self):
        attributes = [a for a in self.attributes]
        functions = [f for f in self.functions]
        if attributes or functions:
            attributes.sort()
            functions.sort()
            return (attributes, functions)
        return None


class Function(Structure):

    def __init__(self, name):
        super(Function, self).__init__()
        self.name = name
        self.args = {}
        self.decorators = []
        self.return_type = []

    def add_return(self, lineno, data_type, line_content, oper):
        info = _TypeData(lineno, data_type, line_content, oper)
        self.return_type.append(info)


class Assign(object):

    def __init__(self, name):
        self.name = name
        self.data = []
        self.parent = None

    def add_data(self, lineno, data_type, line_content, oper):
        info = _TypeData(lineno, data_type, line_content, oper)
        if info not in self.data:
            self.data.append(info)

    def get_data_type(self):
        if self.data[0].data_type is not late_resolution:
            return self.data[0].data_type
        else:
            return None
