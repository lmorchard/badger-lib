# mock.py
# Test tools for mocking and patching.
# Copyright (C) 2007-2010 Michael Foord & the mock team
# E-mail: fuzzyman AT voidspace DOT org DOT uk

# mock 0.7.0
# http://www.voidspace.org.uk/python/mock/

# Released subject to the BSD License
# Please see http://www.voidspace.org.uk/python/license.shtml

# Scripts maintained at http://www.voidspace.org.uk/python/index.shtml
# Comments, suggestions and bug reports welcome.


__all__ = (
    'Mock',
    'MagicMock',
    'mocksignature',
    'patch',
    'patch_object',
    'sentinel',
    'DEFAULT'
)

__version__ = '0.7.0b2'

import sys
import warnings

try:
    import inspect
except ImportError:
    # for alternative platforms that
    # may not have inspect
    inspect = None

try:
    BaseException
except NameError:
    # Python 2.4 compatibility
    BaseException = Exception

try:
    from functools import wraps
except ImportError:
    # Python 2.4 compatibility
    def wraps(original):
        def inner(f):
            f.__name__ = original.__name__
            return f
        return inner

try:
    unicode
except NameError:
    # Python 3
    basestring = unicode = str

try:
    long
except NameError:
    # Python 3
    long = int

inPy3k = sys.version_info[0] == 3


# getsignature and mocksignature heavily "inspired" by
# the decorator module: http://pypi.python.org/pypi/decorator/
# by Michele Simionato

def _getsignature(func, skipfirst):
    if inspect is None:
        raise ImportError('inspect module not available')
    assert inspect.ismethod(func) or inspect.isfunction(func)
    regargs, varargs, varkwargs, defaults = inspect.getargspec(func)

    # instance methods need to lose the self argument
    if not inPy3k:
        im_self = getattr(func, 'im_self', None)
    else:
        im_self = getattr(func, '__self__', None)
    if im_self is not None:
        regargs = regargs[1:]

    assert '_mock_' not in regargs, ("_mock_ is a reserved argument name, can't mock signatures using _mock_")
    if skipfirst:
        regargs = regargs[1:]
    signature = inspect.formatargspec(regargs, varargs, varkwargs, defaults, formatvalue=lambda value: "")
    return signature[1:-1]


def _copy_func_details(func, funcopy):
    funcopy.__name__ = func.__name__
    funcopy.__doc__ = func.__doc__
    funcopy.__dict__.update(func.__dict__)
    funcopy.__module__ = func.__module__
    if not inPy3k:
        funcopy.func_defaults = func.func_defaults
    else:
        funcopy.__defaults__ = func.__defaults__
        funcopy.__kwdefaults__ = func.__kwdefaults__


def mocksignature(func, mock=None, skipfirst=False):
    """
    mocksignature(func, mock=None, skipfirst=False)
    
    Create a new function with the same signature as `func` that delegates
    to `mock`. If `skipfirst` is True the first argument is skipped, useful
    for methods where `self` needs to be omitted from the new function.
    
    If you don't pass in a `mock` then one will be created for you.
    
    The mock is set as the `mock` attribute of the returned function for easy
    access.
    """
    if mock is None:
        mock = Mock()
    signature = _getsignature(func, skipfirst)
    src = "lambda %(signature)s: _mock_(%(signature)s)" % {'signature': signature}

    funcopy = eval(src, dict(_mock_=mock))
    _copy_func_details(func, funcopy)
    funcopy.mock = mock
    return funcopy


def _is_magic(name):
    return '__%s__' % name[2:-2] == name


class SentinelObject(object):
    def __init__(self, name):
        self.name = name
        
    def __repr__(self):
        return '<SentinelObject "%s">' % self.name


class Sentinel(object):
    """Access attributes to return a named object, usable as a sentinel."""
    def __init__(self):
        self._sentinels = {}
        
    def __getattr__(self, name):
        if name == '__bases__':
            # Without this help(mock) raises an exception
            raise AttributeError
        return self._sentinels.setdefault(name, SentinelObject(name))
    
    
sentinel = Sentinel()

DEFAULT = sentinel.DEFAULT

class OldStyleClass:
    pass
ClassType = type(OldStyleClass)

def _copy(value):
    if type(value) in (dict, list, tuple, set):
        return type(value)(value)
    return value


if inPy3k:
    class_types = type
else:
    class_types = (type, ClassType)


class Mock(object):
    
    def __new__(cls, *args, **kw):
        class Mock(cls):
            # every instance has its own class
            # so we can create magic methods on the
            # class without stomping on other mocks
            pass
        return object.__new__(Mock)
        
    def __init__(self, spec=None, side_effect=None, return_value=DEFAULT, 
                 name=None, parent=None, wraps=None):
        self._parent = parent
        self._name = name
        if spec is not None and not isinstance(spec, list):
            spec = [member for member in dir(spec) if not _is_magic(member)]
        
        self._methods = spec
        self._children = {}
        self._return_value = return_value
        self.side_effect = side_effect
        self._wraps = wraps
        
        self.reset_mock()
        

    def reset_mock(self):
        "Restore the mock object to its initial state."
        self.called = False
        self.call_args = None
        self.call_count = 0
        self.call_args_list = []
        self.method_calls = []
        for child in self._children.values():
            child.reset_mock()
        if isinstance(self._return_value, Mock):
            self._return_value.reset_mock()
        
    
    def __get_return_value(self):
        if self._return_value is DEFAULT:
            self._return_value = Mock()
        return self._return_value
    
    def __set_return_value(self, value):
        self._return_value = value
    
    __return_value_doc = "The value to be returned when the mock is called."
    
    return_value = property(__get_return_value, __set_return_value,
                            __return_value_doc)


    def __call__(self, *args, **kwargs):
        self.called = True
        self.call_count += 1
        self.call_args = callargs((args, kwargs))
        self.call_args_list.append(callargs((args, kwargs)))
        
        parent = self._parent
        name = self._name
        while parent is not None:
            parent.method_calls.append(callargs((name, args, kwargs)))
            if parent._parent is None:
                break
            name = parent._name + '.' + name
            parent = parent._parent
        
        ret_val = DEFAULT
        if self.side_effect is not None:
            if (isinstance(self.side_effect, BaseException) or 
                isinstance(self.side_effect, class_types) and
                issubclass(self.side_effect, BaseException)):
                raise self.side_effect
            
            ret_val = self.side_effect(*args, **kwargs)
            if ret_val is DEFAULT:
                ret_val = self.return_value
        
        if self._wraps is not None and self._return_value is DEFAULT:
            return self._wraps(*args, **kwargs)
        if ret_val is DEFAULT:
            ret_val = self.return_value
        return ret_val
    
    
    def __getattr__(self, name):
        if self._methods is not None:
            if name not in self._methods:
                raise AttributeError("Mock object has no attribute '%s'" % name)
        elif _is_magic(name):
            raise AttributeError(name)
        
        if name not in self._children:
            wraps = None
            if self._wraps is not None:
                wraps = getattr(self._wraps, name)
            self._children[name] = Mock(parent=self, name=name, wraps=wraps)
            
        return self._children[name]
    
    def __setattr__(self, name, value):
        if name in _all_magics:
            if not isinstance(value, Mock):
                setattr(self.__class__, name, get_method(name, value))
                original = value
                real = lambda *args, **kw: original(self, *args, **kw)
                value = mocksignature(value, real, skipfirst=True)
            else:
                setattr(self.__class__, name, value)
        return object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if name in _all_magics and name in self.__class__.__dict__:
            delattr(self.__class__, name)
        return object.__delattr__(self, name)
        
    def assert_called_with(self, *args, **kwargs):
        """
        assert that the mock was called with the specified arguments.
        
        Raises an AttributeError if the args and keyword args passed in are
        different to the last call to the mock.
        """
        assert self.call_args == (args, kwargs), 'Expected: %s\nCalled with: %s' % ((args, kwargs), self.call_args)


class callargs(tuple):
    """
    A tuple for holding the results of a call to a mock, either in the form
    `(args, kwargs)` or `(name, args, kwargs)`.
    
    If args or kwargs are empty then a callargs tuple will compare equal to
    a tuple without those values. This makes comparisons less verbose::
    
        callargs('name', (), {}) == ('name',)
        callargs('name', (1,), {}) == ('name', (1,))
        callargs((), {'a': 'b'}) == ({'a': 'b'},)
    """
    def __eq__(self, other):
        if len(self) == 3:
            if other[0] != self[0]:
                return False
            args_kwargs = self[1:]
            other_args_kwargs = other[1:]
        else:
            args_kwargs = tuple(self)
            other_args_kwargs = other

        if len(other_args_kwargs) == 0:
            other_args, other_kwargs = (), {}
        elif len(other_args_kwargs) == 1:
            if isinstance(other_args_kwargs[0], tuple):
                other_args = other_args_kwargs[0]
                other_kwargs = {}
            else:
                other_args = ()
                other_kwargs = other_args_kwargs[0]
        else:
            other_args, other_kwargs = other_args_kwargs

        return tuple(args_kwargs) == (other_args, other_kwargs)

def _dot_lookup(thing, comp, import_path):
    try:
        return getattr(thing, comp)
    except AttributeError:
        __import__(import_path)
        return getattr(thing, comp)


def _importer(target):
    components = target.split('.')
    import_path = components.pop(0)
    thing = __import__(import_path)

    for comp in components:
        import_path += ".%s" % comp
        thing = _dot_lookup(thing, comp, import_path)
    return thing


class _patch(object):
    def __init__(self, target, attribute, new, spec, create, mocksignature):
        self.target = target
        self.attribute = attribute
        self.new = new
        self.spec = spec
        self.create = create
        self.has_local = False
        self.mocksignature = mocksignature


    def copy(self):
        return _patch(self.target, self.attribute, self.new,
                      self.spec, self.create, self.mocksignature)


    def __call__(self, func):
        if isinstance(func, class_types):
            return self.decorate_class(func)
        else:
            return self.decorate_callable(func)

    def decorate_class(self, klass):
        for attr in dir(klass):
            attr_value = getattr(klass, attr)
            if attr.startswith("test") and hasattr(attr_value, "__call__"):
                setattr(klass, attr, self.copy()(attr_value))
        return klass

    def decorate_callable(self, func):
        if hasattr(func, 'patchings'):
            func.patchings.append(self)
            return func

        @wraps(func)
        def patched(*args, **keywargs):
            # don't use a with here (backwards compatability with 2.5)
            extra_args = []
            for patching in patched.patchings:
                arg = patching.__enter__()
                if patching.new is DEFAULT:
                    extra_args.append(arg)
            args += tuple(extra_args)
            try:
                return func(*args, **keywargs)
            finally:
                for patching in reversed(getattr(patched, 'patchings', [])):
                    patching.__exit__()

        patched.patchings = [self]
        if hasattr(func, 'func_code'):
            # not in Python 3
            patched.compat_co_firstlineno = getattr(func, "compat_co_firstlineno", 
                                                    func.func_code.co_firstlineno)
        return patched


    def get_original(self):
        target = self.target
        name = self.attribute
        create = self.create
        
        original = DEFAULT
        if _has_local_attr(target, name):
            try:
                original = target.__dict__[name]
            except AttributeError:
                # for instances of classes with slots, they have no __dict__
                original = getattr(target, name)
        elif not create and not hasattr(target, name):
            raise AttributeError("%s does not have the attribute %r" % (target, name))
        return original

    
    def __enter__(self):
        new, spec, = self.new, self.spec
        original = self.get_original()
        if new is DEFAULT:
            # XXXX what if original is DEFAULT - shouldn't use it as a spec
            inherit = False
            if spec == True:
                # set spec to the object we are replacing
                spec = original
                if isinstance(spec, class_types):
                    inherit = True
            new = Mock(spec=spec)
            if inherit:
                new.return_value = Mock(spec=spec)
        new_attr = new
        if self.mocksignature:
            new_attr = mocksignature(original, new)
            
        self.temp_original = original
        setattr(self.target, self.attribute, new_attr)
        return new


    def __exit__(self, *_):
        if self.temp_original is not DEFAULT:
            setattr(self.target, self.attribute, self.temp_original)
        else:
            delattr(self.target, self.attribute)
        del self.temp_original


def _patch_object(target, attribute, new=DEFAULT, spec=None, create=False, mocksignature=False):
    """
    patch.object(target, attribute, new=DEFAULT, spec=None, create=False, mocksignature=False)
    """
    return _patch(target, attribute, new, spec, create, mocksignature)
                
def patch_object(*args, **kwargs):
    "A deprecated form of patch.object(...)"
    warnings.warn(('Please use patch.object instead.'), DeprecationWarning, 2)
    return _patch_object(*args, **kwargs)

def patch(target, new=DEFAULT, spec=None, create=False, mocksignature=False):
    """
    patch(target, new=DEFAULT, spec=None, create=False, mocksignature=False)
    """
    try:
        target, attribute = target.rsplit('.', 1)    
    except (TypeError, ValueError):
        raise TypeError("Need a valid target to patch. You supplied: %r" % (target,))
    target = _importer(target)
    return _patch(target, attribute, new, spec, create, mocksignature)

class _patch_dict(object):
    """patch.dict(in_dict, values=(), clear=False)"""
    
    def __init__(self, in_dict, values=(), clear=False):
        if isinstance(in_dict, basestring):
            in_dict = _importer(in_dict)
        self.in_dict = in_dict
        # support any argument supported by dict(...) constructor
        self.values = dict(values)
        self.clear = clear
        self._original = None

    def __call__(self, f):
        @wraps(f)
        def _inner(*args, **kw):
            self._patch_dict()
            try:
                return f(*args, **kw)
            finally:
                self._unpatch_dict()
            
        return _inner

    def __enter__(self):
        self._patch_dict()
    
    def _patch_dict(self):
        values = self.values
        in_dict = self.in_dict
        clear = self.clear
        
        try:
            original = in_dict.copy()
        except AttributeError:
            # dict like object with no copy method
            # must support iteration over keys
            original = {}
            for key in in_dict:
                original[key] = in_dict[key]
        self._original = original
        
        if clear:
            _clear_dict(in_dict)
        
        try:
            in_dict.update(values)
        except AttributeError:
            # dict like object with no update method
            for key in values:
                in_dict[key] = values[key]
                    
    def _unpatch_dict(self):
        in_dict = self.in_dict
        original = self._original
        
        _clear_dict(in_dict)
            
        try:
            in_dict.update(original)
        except AttributeError:
            for key in original:
                in_dict[key] = original[key]
    
    
    def __exit__(self, *args):
        self._unpatch_dict()
        return False


def _clear_dict(in_dict):
    try:
        in_dict.clear()
    except AttributeError:
        keys = list(in_dict)
        for key in keys:
            del in_dict[key]


patch.object = _patch_object
patch.dict = _patch_dict

def _has_local_attr(obj, name):
    try:
        return name in vars(obj)
    except TypeError:
        # objects without a __dict__
        return hasattr(obj, name)


magic_methods = (
    "lt le gt ge eq ne "
    "getitem setitem delitem "
    "len contains iter "
    "hash repr str "
    "enter exit "
    "divmod neg pos abs invert "
    "complex int float index "
)

numerics = "add sub mul div truediv floordiv mod lshift rshift and xor or pow "
inplace = ' '.join('i%s' % n for n in numerics.split())
right = ' '.join('r%s' % n for n in numerics.split()) 
extra = ''
if inPy3k:
    extra = 'bool next '
else:
    extra = 'unicode long nonzero oct hex '
# __truediv__ and __rtruediv__ not available in Python 3 either

# not including __prepare__, __instancecheck__, __subclasscheck__
# (as they are metaclass methods)
# __del__ is not supported at all as it causes problems if it exists

_non_defaults = set('__%s__' % method for method in [
    'cmp', 'getslice', 'setslice', 'coerce', 'subclasses',
    'dir', 'format', 'get', 'set', 'delete', 'reversed',
    'missing', 
])

def get_method(name, func):
    def method(self, *args, **kw):
        return func(self, *args, **kw)
    method.__name__ = name
    return method

_magics = set('__%s__' % method for method in ' '.join([magic_methods, numerics, inplace, right, extra]).split())

_all_magics = _magics | _non_defaults


_side_effects = {
    '__hash__': lambda self: object.__hash__(self),
    '__repr__': lambda self: object.__repr__(self),
    '__str__': lambda self: object.__str__(self),
    '__unicode__': lambda self: unicode(object.__str__(self)),
}

_return_values = {
    '__int__': 0,
    '__contains__': False,
    '__len__': 0,
    '__iter__': iter([]),
    '__exit__': False,
    '__complex__': 0j,
    '__float__': 0.0,
    '__bool__': True,
    '__nonzero__': True,
    '__oct__': '0',
    '__hex__': '0x0',
    '__long__': long(0),
    '__index__': 0,
}

def _set_return_value(mock, method, name):
    if name in _side_effects:
        func = _side_effects[name]
        def wrap(*args, **kw):
            if method._return_value is DEFAULT:
                return func(mock)
            return method._return_value
        method.side_effect = wrap
    elif name in _return_values:
        method.return_value = _return_values[name]


class MagicMock(Mock):
    """
    MagicMock is a subclass of :Mock with default implementations
   of most of the magic methods. You can use MagicMock without having to
   configure the magic methods yourself.
   """
    def __init__(self, *args, **kw):
        Mock.__init__(self, *args, **kw)
        for entry in _magics:
            # could specify parent?
            m = Mock()
            setattr(self, entry, m)
            _set_return_value(self, m, entry)

