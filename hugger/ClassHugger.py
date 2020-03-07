#   Licensed under the GNU General Public License v3.0
#   Copyright (c) of the author (github.com/wardsimon)
#   Created: 5/3/2020.

__author__ = 'github.com/wardsimon'
__version__ = '0.0.1'

from functools import wraps
from typing import Callable


class ClassHugger:

    def __init__(self, debug=False):
        self.__count = 0
        self.__history = []
        self.__create_list = []
        self.__unique_vars = []
        self.__unique_rets = []
        self.debug = debug
        self._auto_props = None
        self._old_set_attr = None
        self._old_get_attr = None
        self.__var_ident = 'var_'

    def hug(self, klass):
        old_init = klass.__init__
        self._old_set_attr = klass.__setattr__
        self._old_get_attr = klass.__getattribute__

        def patch_init(obj, *args, **kwargs):
            if self.debug:
                print(f"{klass.__name__} is created with {args}, {kwargs}")
            self.__history.append(self._makeScriptEntry(klass, 'create_obj', *args, index=self.__count, **kwargs))
            old_init(obj, *args, **kwargs)
            self.__create_list.append([self.__count, obj])
            self.__count += 1
            new_props = self._auto_props.symmetric_difference(set(klass.__dict__.keys()))
            if new_props:
                prop_dict = {}
                for prop in list(new_props):
                    prop_dict[prop] = klass.__dict__[prop]
                patch_methods_properties(prop_dict)

        def patch_methods_properties(this_dict):
            for key in this_dict.keys():
                if isinstance(this_dict[key], Callable):
                    setattr(klass, key, fun_wrap(this_dict[key]))
                elif isinstance(this_dict[key], property):
                    if this_dict[key].fget.__name__ != key:
                        setattr(klass, key,
                                property(fun_get_wrap(this_dict[key].fget, name=key),
                                         fun_set_wrap(this_dict[key].fset, name=key),
                                         this_dict[key].fdel))
                    else:
                        setattr(klass, key,
                                property(fun_get_wrap(this_dict[key].fget), fun_set_wrap(this_dict[key].fset),
                                         this_dict[key].fdel))
                elif isinstance(this_dict[key], (classmethod, staticmethod)):
                    setattr(klass, key, fun_wrap(this_dict[key], name=key))

        def patch_getter_setter(obj):
            obj.__getattribute__ = get_wrapper(self._old_get_attr)
            obj.__setattr__ = set_wrapper(self._old_set_attr)

        def fun_get_wrap(fun, name=None):
            if name is None:
                name = fun.__name__

            @wraps(fun)
            def inner(*args, **kwargs):
                self._argument_checker(*args, **kwargs)
                if self.debug:
                    print(f"I''m {args[0]} and getting {name}")
                res = fun(*args, **kwargs)
                ret = _argout(res)
                self.__history.append(self._makeScriptEntry(klass, 'prop_get', *[args[0], name, *args[1:]], returns=ret,
                                                            **kwargs))
                return res

            return inner

        def fun_set_wrap(fun, name=None):
            if name is None:
                name = fun.__name__

            def inner(*args, **kwargs):
                self._argument_checker(*args, **kwargs)
                self.__history.append(self._makeScriptEntry(klass, 'prop_set', *[args[0], name, *args[1:]], **kwargs))
                if self.debug:
                    print(f"I''m {args[0]} and getting {name}")
                return fun(*args, **kwargs)

            return inner

        def _argout(result):
            if result is None:
                ret = 0
            else:
                if result not in self.__unique_rets:
                    self.__unique_rets.append(result)
                if isinstance(result, tuple):
                    ret = len(result)
                else:
                    ret = 1
            return ret

        def fun_wrap(fun, name=None):
            if name is None:
                name = fun.__name__

            if self.debug:
                print(f"I''ve wrapped {klass.__name__}.{name}")

            @wraps(fun)
            def inner(*args, **kwargs):
                self._argument_checker(*args, **kwargs)
                if name != 'patch_init':
                    if self.debug:
                        print(f"I''m {args[0]}.{name} and have been called with {args[1:]}, {kwargs}")
                    if isinstance(fun, (classmethod, staticmethod)):
                        if isinstance(fun, classmethod):
                            res = getattr(fun, '__func__')(klass, *args, **kwargs)
                            self.__count -= 1
                            ret = _argout(res)
                            self.__history[-1] = self._makeScriptEntry(klass, 'magic_method', *[name, *args[1:]],
                                                                        returns=ret, index=self.__count, **kwargs)
                        else:
                            res = getattr(fun, '__func__')(*args[1:], **kwargs)
                            ret = _argout(res)
                            self.__history.append(self._makeScriptEntry(klass, 'magic_method', *[name, *args[1:]],
                                                                       returns=ret, index=self.__count, **kwargs))
                    else:
                        res = fun(*args, **kwargs)
                        ret = _argout(res)
                        self.__history.append(self._makeScriptEntry(klass, 'fn_call', *[args[0], name, *args[1:]],
                                                                    returns=ret, **kwargs))
                    return res
                return fun(*args, **kwargs)

            return inner

        def get_wrapper(fun):
            def checker(this_fun, thisitem):
                return thisitem in this_fun.__dict__.keys()

            @wraps(fun)
            def inner(*args, **kwargs):
                if args[1] == '__dict__':
                    return fun(*args, **kwargs)
                if not checker(args[0], args[1]):
                    return fun(*args, **kwargs)
                if isinstance(args[0].__dict__[args[1]], Callable):
                    return fun(*args, **kwargs)
                if args[1][0] != '_':
                    if self.debug:
                        print(f"I''m getting {args[0]}.{args[1]}")
                    self.__history.append(
                        self._makeScriptEntry(klass, 'prop_get', *[args[0], fun.__name__, *args[1:]], **kwargs))

                return fun(*args, **kwargs)

            return inner

        def set_wrapper(fun):
            def checker(this_fun, thisitem):
                return thisitem in this_fun.__dict__.keys()

            @wraps(fun)
            def inner(*args, **kwargs):
                if args[1] == '__dict__':
                    return fun(*args, **kwargs)
                if not checker(args[0], args[1]):
                    return fun(*args, **kwargs)
                if isinstance(args[0].__dict__[args[1]], Callable):
                    return fun(*args, **kwargs)
                if args[1][0] != '_':
                    if self.debug:
                        print(f"I''m setting {args[0]}.{args[1]} to {args[2]}")
                    self.__history.append(
                        self._makeScriptEntry(klass, 'prop_set', *args, **kwargs))
                return fun(*args, **kwargs)

            return inner

        klass.__init__ = patch_init
        patch_methods_properties(klass.__dict__)
        self._auto_props = {'__getattribute__', '__setattr__', *list(klass.__dict__.keys())}
        patch_getter_setter(klass)
        return klass

    @staticmethod
    def _makeScriptEntry(class_in, call_type, *args, index=None, returns=None, **kwargs):
        call_function = None
        call_obj = None
        create_index = index
        call_variables = None
        call_prop = None
        returns = returns
        if call_type == 'create_obj':
            call_variables = [args, kwargs]
            create_index = create_index
        elif call_type == 'fn_call':
            call_obj = args[0]
            call_function = args[1]
            call_variables = [args[2:], kwargs]
        elif call_type == 'prop_set':
            call_obj = args[0]
            call_prop = args[1]
            call_variables = args[2]
        elif call_type == 'prop_get':
            call_obj = args[0]
            call_prop = args[1]
        elif call_type == 'magic_method':
            call_function = args[0]
            call_variables = [args[1:], kwargs]
            create_index = create_index

        caller = dict(class_obj=class_in.__name__,
                      call_type=call_type,
                      call_obj=call_obj,
                      call_prop=call_prop,
                      create_index=create_index,
                      call_function=call_function,
                      call_variables=call_variables,
                      returns=returns)
        return caller

    def makeScript(self):
        def parseScriptEntry(entry):
            class_obj = entry['class_obj']
            call_type = entry['call_type']
            call_obj = entry['call_obj']
            call_prop = entry['call_prop']
            call_function = entry['call_function']
            call_variables = entry['call_variables']
            create_index = entry['create_index']
            returns = entry['returns']

            class_obj_name = class_obj.lower()

            if call_type == 'create_obj':
                temp = f'{class_obj_name}_{create_index} = {class_obj}('
                for var in call_variables[0]:
                    if var in self.__unique_vars:
                        index = self.__unique_vars.index(var)
                        temp += f'{self.__var_ident}{index}, '
                    else:
                        if isinstance(var, str):
                            var = '"' + var + '"'
                        temp += f'{var}, '
                if call_variables[0]:
                    temp = temp[:-2]
                temp_i = 0
                for key, item in call_variables[1].items():
                    if temp_i == 0 & len(call_variables[0]) > 0:
                        temp += ', '
                    if item in self.__unique_vars:
                        index = self.__unique_vars.index(item)
                        temp += f'{key}={self.__var_ident}{index}, '
                    else:
                        if isinstance(item, str):
                            item = '"' + item + '"'
                        temp += f'{key}={item}, '
                    temp_i += 1
                if call_variables[1]:
                    temp = temp[:-2]
                temp += ')\n'
                return temp

            if call_type == 'magic_method':
                temp = f'{class_obj_name}_{create_index} = {class_obj}.{call_function}('
                for var in call_variables[0]:
                    if var in self.__unique_vars:
                        index = self.__unique_vars.index(var)
                        temp += f'{self.__var_ident}{index}, '
                    else:
                        if isinstance(var, str):
                            var = '"' + var + '"'
                        temp += f'{var}, '
                if call_variables[0]:
                    temp = temp[:-2]
                temp_i = 0
                for key, item in call_variables[1].items():
                    if temp_i == 0 & len(call_variables[0]) > 0:
                        temp += ', '
                    if item in self.__unique_vars:
                        index = self.__unique_vars.index(item)
                        temp += f'{key}={self.__var_ident}{index}, '
                    else:
                        if isinstance(item, str):
                            item = '"' + item + '"'
                        temp += f'{key}={item}, '
                    temp_i += 1
                if call_variables[1]:
                    temp = temp[:-2]
                temp += ')\n'
                return temp

            objs = [obj[1] for obj in self.__create_list]
            idx = objs.index(call_obj)
            if call_type == 'fn_call':
                temp = ''
                for i in range(returns):
                    temp += f'value_{i}, '
                if returns > 0:
                    temp = temp[:-2]
                    temp += ' = '
                temp += f'{class_obj_name}_{idx}.{call_function}('
                for var in call_variables[0]:
                    if var in self.__unique_vars:
                        index = self.__unique_vars.index(var)
                        temp += f'{self.__var_ident}{index}, '
                    else:
                        if isinstance(var, str):
                            var = '"' + var + '"'
                        temp += f'{var}, '
                if call_variables[0]:
                    temp = temp[:-2]
                temp_i = 0
                for key, item in call_variables[1].items():
                    if temp_i == 0 & len(call_variables[0]) > 0:
                        temp += ', '
                    if item in self.__unique_vars:
                        index = self.__unique_vars.index(item)
                        temp += f'{key}={self.__var_ident}{index}, '
                    else:
                        if isinstance(item, str):
                            item = '"' + item + '"'
                        temp += f'{key}={item}, '
                    temp_i += 1
                if call_variables[1]:
                    temp = temp[:-2]
                temp += ')\n'
                return temp
            elif call_type == 'prop_set':
                temp = f'{class_obj_name}_{idx}.{call_prop} = '
                if call_variables in self.__unique_vars:
                    index = self.__unique_vars.index(call_variables)
                    temp += f'{self.__var_ident}{index}'
                else:
                    if isinstance(call_variables, str):
                        var = '"' + call_variables + '"'
                    temp += f'{call_variables}'
                temp += '\n'
                return temp
            elif call_type == 'prop_get':
                temp = ''
                for i in range(returns):
                    temp += f'value_{i}, '
                if returns > 0:
                    temp = temp[:-2]
                    temp += ' = '
                temp += f'obj_{idx}.{call_prop}\n'
                return temp

        text = '# Auto generated script\n\n'
        for call in self.__history:
            text += parseScriptEntry(call)
        return text

    def _argument_checker(self, *args, **kwargs):
        for arg in args:
            if self.__ismutalbe(arg):
                if arg not in self.__unique_vars:
                    self.__unique_vars.append(arg)
        for item in kwargs.values():
            if self.__ismutalbe(item):
                if item not in self.__unique_vars:
                    self.__unique_vars.append(item)

    @staticmethod
    def __ismutalbe(arg):
        ret = True
        if isinstance(arg, (int, float, complex, str, tuple, frozenset, bytes)):
            ret = False
        return ret