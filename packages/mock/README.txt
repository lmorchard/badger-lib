mock is a Python module that provides a core Mock class. It is intended to
reduce the need for creating a host of trivial stubs throughout your test suite.
After performing an action, you can make assertions about which methods /
attributes were used and arguments they were called with. You can also specify 
return values and set needed attributes in the normal way.

mock is tested on Python versions 2.4-2.7 and Python 3.

The mock module also provides utility functions / objects to assist with
testing, particularly monkey patching.

* `mock on google code (repository and issue tracker) <http://code.google.com/p/mock/>`_
* `mock documentation <http://www.voidspace.org.uk/python/mock/>`_
* `mock on PyPI <http://pypi.python.org/pypi/mock/>`_
* `Article on mocking, patching and stubbing <http://www.voidspace.org.uk/python/articles/mocking.shtml>`_

Mock is very easy to use and is designed for use with
`unittest <http://pypi.python.org/pypi/unittest2 unittest>`_. Mock is based on
the 'action -> assertion' pattern instead of 'record -> replay' used by many
mocking frameworks. See the 
`mock documentation <http://www.voidspace.org.uk/python/mock/>`_ for full
details.

Mock objects create all attributes and methods as you access them and store
details of how they have been used. You can configure them, to specify return
values or limit what attributes are available, and then make assertions about
how they have been used::

    >>> from mock import Mock
    >>> real = ProductionClass()
    >>> real.method = Mock(return_value=3)
    >>> real.method(3, 4, 5, key='value')
    3
    >>> real.method.assert_called_with(3, 4, 5, key='value')

``side_effect`` allows you to perform side effects, return different values or
raise an exception when a mock is called:

.. doctest::

   >>> from mock import Mock
   >>> mock = Mock(side_effect=KeyError('foo'))
   >>> mock()
   Traceback (most recent call last):
    ...
   KeyError: 'foo'
   >>> values = [1, 2, 3]
   >>> def side_effect():
   ...     return values.pop()
   ...      
   >>> mock.side_effect = side_effect
   >>> mock(), mock(), mock()
   (3, 2, 1)

Mock has many other ways you can configure it and control its behaviour. For
example the ``spec`` argument configures the mock to take its specification from
another object. Attempting to access attributes or methods on the mock that
don't exist on the spec will fail with an ``AttributeError``.

The ``patch`` decorator / context manager makes it easy to mock classes or
objects in a module under test. The object you specify will be replaced with a
mock (or other object) during the test and restored when the test ends::
    
   >>> from mock import patch
    >>> @patch('test_module.ClassName1')
    ... @patch('test_module.ClassName2')
    ... def test(MockClass1, MockClass2):
    ...     test_module.ClassName1()
    ...     test_module.ClassName2()
    
    ...     assert MockClass1.called
    ...     assert MockClass2.called
    ... 
    >>> test()
    
    >>> with patch.object(ProductionClass, 'method') as mock_method:
    ...     mock_method.return_value = None
    ...     real = ProductionClass()
    ...     real.method(1, 2, 3)
    ...
    >>> mock_method.assert_called_with(1, 2, 3)

There is also :func:`patch.dict` for setting values in a dictionary just
during a scope and restoring the dictionary to its original state when the test
ends:

.. doctest::

   >>> foo = {'key': 'value'}
   >>> original = foo.copy()
   >>> with patch.dict(foo, {'newkey': 'newvalue'}, clear=True):
   ...     assert foo == {'newkey': 'newvalue'}
   ...
   >>> assert foo == original

Mock now supports the mocking of Python magic methods. The easiest way of
using magic methods is with the ``MagicMock`` class. It allows you to do
things like::

    >>> from mock import MagicMock
    >>> mock = MagicMock()
    >>> mock.__str__.return_value = 'foobarbaz'
    >>> str(mock)
    'foobarbaz'
    >>> mock.__str__.assert_called_with()

Mock allows you to assign functions (or other Mock instances) to magic methods
and they will be called appropriately. The MagicMock class is just a Mock
variant that has all of the magic methods pre-created for you (well - all the
useful ones anyway).

The following is an example of using magic methods with the ordinary Mock
class::

    >>> from mock import Mock
    >>> mock = Mock()
    >>> mock.__str__ = Mock()
    >>> mock.__str__.return_value = 'wheeeeee'
    >>> str(mock)
    'wheeeeee'

:func:`mocksignature` is a useful companion to Mock and patch. It creates
copies of functions that delegate to a mock, but have the same signature as the
original function. This ensures that your mocks will fail in the same way as
your production code if they are called incorrectly:

.. doctest::

   >>> from mock import mocksignature
   >>> def function(a, b, c):
   ...     pass
   ... 
   >>> function2 = mocksignature(function)
   >>> function2.mock.return_value = 'fishy'
   >>> function2(1, 2, 3)
   'fishy'
   >>> function2.mock.assert_called_with(1, 2, 3)
   >>> function2('wrong arguments')
   Traceback (most recent call last):
    ...
   TypeError: <lambda>() takes exactly 3 arguments (1 given)

