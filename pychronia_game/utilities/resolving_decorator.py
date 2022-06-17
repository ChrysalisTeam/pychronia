import sys, types, inspect
from decorator import decorator
from functools import partial

IS_PY3K8 = (sys.version_info >= (3, 8))
IS_PY3K = (sys.version_info >= (3, 0))


def resolving_decorator(caller, func=None):
    """
    Similar to the famous decorator.decorator, except that the caller
    must be a function expecting "resolved" arguments, passed
    in keyword-only way, and corresponding to the local variables
    in entry of the wrapped function (i.e arguments preprocessed by
    inspect.getcallargs()).
    
    The main effect of this preprocessing is that ``*args`` and ``**kwargs``
    arguments become simple "args" and "kwargs" variables (respectively
    expecting a tuple and a dict as values).
    
    Example::
    
        @resolving_decorator
        def inject_session(func, **all_kwargs):
            if not all_kwargs["session"]:
                all_kwargs["session"] = "<SESSION>"
            return func(**all_kwargs)
        
        @inject_session
        def myfunc(session):
            return session
        
        assert myfunc(None) == myfunc(session=None) == "<SESSION>"
        assert myfunc("<stuff>") == myfunc(session="<stuff>") == "<stuff>"
        
    """

    assert caller

    if func is None:
        return partial(resolving_decorator, caller)

    else:
        flattened_func = flatten_function_signature(func)

        def caller_wrapper(base_func, *args, **kwargs):
            assert base_func == func

            all_kwargs = flattened_func.resolve_call_args(*args, **kwargs)
            return caller(flattened_func, **all_kwargs)

        final_func = decorator(caller_wrapper, func)
        assert final_func.__name__ == func.__name__
        return final_func


def resolve_call_args(flattened_func, *args, **kwargs):
    """
    Returns an "all_args" dict containing the keywords arguments which
    which to call *flattened_func*, as if args and kwargs had been processed by the
    original, unflattened function (possibly expecting ``*args`` and ``*kwargs``
    constructs).
    
    This is equivalent to using inspect.getcallargs() on the original function.
    
    That dict can then be modified at will (eg. to insert/replace some
    arguments), before being passed to the flattened function
    that way: ``res = flattened_func(**all_args)``.
    """
    return flattened_func.resolve_call_args(*args, **kwargs)


def flatten_function_signature(func):
    """
    Takes a standard function (with possibly ``*args`` and ``*kwargs`` constructs), and
    returns a new function whose signature has these special forms
    transformed into standard arguments, so that the new function
    could be called simply by passing it all the keyword arguments that
    should become its initial local variables.
    
    Thus, a function with this signature::
    
       old_function(a, b, c=3, *args, **kwargs)
    
    becomes one with this signature::
    
       new_function(a, b, c, args, kwargs)
    
    This makes it possible to easily tweaknormalize all call arguments into a
    simple dict, that way::
    
        new_function = flatten_function_signature(func)
        all_args = resolve_call_args(new_function, *args, **kwargs)
        # here modify the dit *all_args* at will
        res = new_function(all_args)
    
    ..warning:
        *func* must be a user-defined function, i.e a function defined 
        outside of classes, or the *im_func* attribute of a bound/unbound method.
    """

    old_function = func
    old_code_object = old_function.__code__

    """
    Notes on python2 code type:
    types.CodeType(argcount, nlocals, stacksize, flags, codestring, constants, names,
                 varnames, filename, name, firstlineno, lnotab[,freevars[, cellvars]])
                 
    Notes on python3 (<3.8) code type:             
    types.CodeType(co_argcount = ...  # type: int
                    co_kwonlyargcount = ...  # type: int
                    co_nlocals = ...  # type: int
                    co_stacksize = ...  # type: int
                    co_flags = ...  # type: int
                    co_code = ...  # type: bytes
                    co_consts = ...  # type: Tuple[Any, ...]
                    co_names = ...  # type: Tuple[str, ...]
                    co_varnames = ...  # type: Tuple[str, ...]
                    co_filename = ...  # type: Optional[str]
                    co_name = ...  # type: str
                    co_firstlineno = ...  # type: int
                    co_lnotab = ...  # type: bytes
                    co_freevars = ...  # type: Tuple[str, ...]
                    co_cellvars = ...  # type: Tuple[str, ...])
                    
    Notes on python3.8 code type:             
    types.CodeType(co_argcount = ...  # type: int
                    co_posonlyargcount = ...  # type: int
                    co_kwonlyargcount = ...  # type: int
                    co_nlocals = ...  # type: int
                    co_stacksize = ...  # type: int
                    co_flags = ...  # type: int
                    co_code = ...  # type: bytes
                    co_consts = ...  # type: Tuple[Any, ...]
                    co_names = ...  # type: Tuple[str, ...]
                    co_varnames = ...  # type: Tuple[str, ...]
                    co_filename = ...  # type: Optional[str]
                    co_name = ...  # type: str
                    co_firstlineno = ...  # type: int
                    co_lnotab = ...  # type: bytes
                    co_freevars = ...  # type: Tuple[str, ...]
                    co_cellvars = ...  # type: Tuple[str, ...])
    """

    print(">>>>>> inspect.getfullargspec OLD FUNCTION:", old_function.__name__, inspect.getfullargspec(old_function))

    # TODO - could be optimized out
    if IS_PY3K8:  # adds co_posonlyargcount
        pos_arg_names = """co_argcount co_posonlyargcount co_kwonlyargcount co_nlocals co_stacksize co_flags co_code co_consts co_names
                co_varnames co_filename co_name co_firstlineno co_lnotab co_freevars co_cellvars""".split()
    elif IS_PY3K:  # adds co_kwonlyargcount
        pos_arg_names = """co_argcount co_kwonlyargcount co_nlocals co_stacksize co_flags co_code co_consts co_names
                co_varnames co_filename co_name co_firstlineno co_lnotab co_freevars co_cellvars""".split()
    else:
        pos_arg_names = """co_argcount co_nlocals co_stacksize co_flags co_code co_consts co_names
                co_varnames co_filename co_name co_firstlineno co_lnotab co_freevars co_cellvars""".split()

    pos_arg_values = [getattr(old_code_object, name) for name in pos_arg_names]
    print(">>>>>>>pos_arg_values", pos_arg_values)

    func_param_names = pos_arg_values[pos_arg_names.index("co_varnames")]
    print(">>>>>>>func_param_names", func_param_names)

    #defaults = old_function.__defaults__
    argcount = pos_arg_values[0]
    assert isinstance(argcount, int)
    flags_idx = pos_arg_names.index("co_flags")
    flags = pos_arg_values[flags_idx]  # TODO - could be optimized out
    assert isinstance(flags, int)

    if flags & inspect.CO_VARARGS:
        # positional arguments were activated
        flags -= inspect.CO_VARARGS
        argcount += 1
        #defaults += ((),)

    if flags & inspect.CO_VARKEYWORDS:
        # keyword arguments were activated
        flags -= inspect.CO_VARKEYWORDS
        argcount += 1
        #defaults += ({},)

    pos_arg_values[0] = argcount
    pos_arg_values[flags_idx] = flags

    new_code_object = types.CodeType(*pos_arg_values)

    new_function = types.FunctionType(new_code_object,
                                      old_function.__globals__,
                                      old_function.__name__ + "PATCHED",
                                      (),
                                      # Function defaults are useless, since they must be resolved before by inspect.getcallargs()
                                      old_function.__closure__)

    new_signature = old_function.__func__.__signature__ if getattr(old_function, "__func__") else old_function.__signature__
    print(">>>> we use types.FunctionType", types.FunctionType, "to build new_function", new_function, "with signature", new_signature)

    # See https://github.com/micheles/decorator/blob/master/docs/documentation.md
    # Everything breaks when old_code_object has been corrupted by decorator module
    # Only those using decoratorx will work!!!

    new_function.__signature__ = new_signature
    new_function.__wrapped__ = old_function
    new_function.__qualname__ = old_function.__qualname__ + "PATCHED"
    new_function.__annotations__ = func.__annotations__
    new_function.__kwdefaults__ = func.__kwdefaults__
    new_function.__doc__ = func.__doc__
    new_function.__dict__.update(func.__dict__)

    ## OBSOLETE new_function.original_function = old_function  # Equivalent of __wrapped__ of decorator module

    def specific_resolve_call_args(*args, **kwargs):
        result = inspect.getcallargs(old_function, *args, **kwargs)
        #if inspect.ismethod(old_function) and old_function.__self__:
        #    del result[func_param_names[0]]
        print(">>>>> inspect.getcallargs(old_function, ...) returned", result, "for arguments:", old_function, args, kwargs)
        return result

    new_function.resolve_call_args = specific_resolve_call_args

    print(">>>>>> inspect.getfullargspec NEW FUNCTION:", new_function.__name__, inspect.getfullargspec(new_function))
    assert new_function.__name__ == old_function.__name__ + "PATCHED"

    print(">>>>>> flatten_function_signature on", old_function, "returned", new_function)
    return new_function


if __name__ == "__main__":

    # testing with normal functions and nested functions #

    # FIXME later add tests for positional-only arguments, when python3.7 support is dropped!

    def f(a, b=3, c=8, *d, **e):
        return locals()


    def gen(aa, bb):
        def f(a, b=3, c=8, *d, **e):
            cc = (aa, bb)
            return locals()

        return f


    for old_function in (f, gen(1, 2)):
        new_function = flatten_function_signature(old_function)
        assert new_function.__wrapped__ == old_function

        res1 = old_function(1, 2, 3, 4, 5, kw1="a", kw2="b")

        res2 = new_function(1, 2, 3, (4, 5), dict(kw1="a", kw2="b"))

        assert res1 == res2, (res1, res2)


    @resolving_decorator
    def inject_session(func, **all_kwargs):
        if not all_kwargs["session"]:
            all_kwargs["session"] = "<SESSION>"
        return func(**all_kwargs)


    @inject_session
    def func1(session):
        return session


    @inject_session
    def func2(a, session=None):
        return session


    @inject_session
    def func3(a, *session):
        return session


    @inject_session
    def func4(a, **session):
        return session


    assert func1(None) == "<SESSION>"
    assert func1(4) == 4
    assert func2(1, None) == "<SESSION>"
    assert func2(1, 5) == 5
    assert func3(1) == "<SESSION>"
    assert func3(1, 8) == (8,)
    assert func4(1) == "<SESSION>"
    assert func4(1, my=8) == dict(my=8)


    class DummyClass:
        def dummy_method(self, a, b=5, c=10, *d, **e):
            return locals()

        @inject_session
        def dummy_method_with_session(self, session):
            return locals()

    dummy_instance = DummyClass()

    flattened_method = flatten_function_signature(dummy_instance.dummy_method)
    call_args = resolve_call_args(flattened_method, "a_value")
    assert "self" in call_args, call_args  # flattened_method is UNBOUND now

    result = flattened_method(**call_args)
    assert result["self"] is dummy_instance
    del result["self"]
    assert result == {'a': 'a_value', 'd': (), 'e': {}, 'b': 5, 'c': 10}


    print("All tests OK")
