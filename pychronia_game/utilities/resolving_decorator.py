import types, inspect, functools
from decorator import decorator
from functools import partial


def resolving_decorator(caller, func=None):
    """
    Similar to the famous decorator.decorator, except that the caller
    must be a function expecting "resolved" arguments, passed
    in keyword-only way, and corresponding to the local variables
    in entry of the wrapped function (i.e arguments preprocessed by
    inspect.getcallargs()).
    
    The main effect of this preprocessing is that ``*args`` and ``**kwargs``
    arguments become simple "args" and "kwargs" variables (respectively
    expecting a tupel and a dict asvalues).
    
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
    Note on python2 code type:
    types.CodeType(argcount, nlocals, stacksize, flags, codestring, constants, names,
                 varnames, filename, name, firstlineno, lnotab[,freevars[, cellvars]])
    """
    pos_arg_names = """co_argcount co_nlocals co_stacksize co_flags co_code co_consts co_names
            co_varnames co_filename co_name co_firstlineno co_lnotab co_freevars co_cellvars""".split()

    pos_arg_values = [getattr(old_code_object, name) for name in pos_arg_names]

    #defaults = old_function.__defaults__
    argcount = pos_arg_values[0]
    assert isinstance(argcount, (int, long))
    flags = pos_arg_values[3]
    assert isinstance(flags, (int, long))

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
    pos_arg_values[3] = flags

    new_code_object = types.CodeType(*pos_arg_values)

    new_function = types.FunctionType(new_code_object,
                                      old_function.__globals__,
                                      old_function.__name__,
                                      (),
                                      # defaults are useless, since they must be resolved before by inspect.getcallargs()
                                      old_function.__closure__)

    new_function.original_function = old_function
    new_function.resolve_call_args = functools.partial(inspect.getcallargs, old_function)

    #print inspect.getargspec(new_function)
    assert new_function.__name__ == old_function.__name__
    return new_function


if __name__ == "__main__":

    # testing with normal functions and nested functions #

    def f(a, b=3, c=8, *d, **e):
        return locals()


    def gen(aa, bb):
        def f(a, b=3, c=8, *d, **e):
            cc = (aa, bb)
            return locals()

        return f


    for old_function in (f, gen(1, 2)):
        new_function = flatten_function_signature(old_function)
        assert new_function.original_function == old_function

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

    print "All tests OK"
