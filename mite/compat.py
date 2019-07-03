try:
    from contextlib import asynccontextmanager
except ImportError:
    import abc
    from functools import wraps

    # Implementation scavenged from Python 3.7.  It's included here to
    # maintain compatibility with Python 3.6.  It can be dropped once mite
    # requires 3.7 at minimum.

    class AbstractAsyncContextManager(abc.ABC):
        async def __aenter__(self):
            return self

        @abc.abstractmethod
        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        @classmethod
        def __subclasshook__(cls, C):
            if cls is AbstractAsyncContextManager:
                return _collections_abc._check_methods(C, "__aenter__",
                                                       "__aexit__")
            return NotImplemented


    class _GeneratorContextManagerBase:
        def __init__(self, func, args, kwds):
            self.gen = func(*args, **kwds)
            self.func, self.args, self.kwds = func, args, kwds
            doc = getattr(func, "__doc__", None)
            if doc is None:
                doc = type(self).__doc__
            self.__doc__ = doc


    class _AsyncGeneratorContextManager(_GeneratorContextManagerBase,
                                        AbstractAsyncContextManager):
        async def __aenter__(self):
            try:
                return await self.gen.__anext__()
            except StopAsyncIteration:
                raise RuntimeError("generator didn't yield") from None

        async def __aexit__(self, typ, value, traceback):
            if typ is None:
                try:
                    await self.gen.__anext__()
                except StopAsyncIteration:
                    return
                else:
                    raise RuntimeError("generator didn't stop")
            else:
                if value is None:
                    value = typ()
                try:
                    await self.gen.athrow(typ, value, traceback)
                    raise RuntimeError("generator didn't stop after throw()")
                except StopAsyncIteration as exc:
                    return exc is not value
                except RuntimeError as exc:
                    if exc is value:
                        return False
                    if isinstance(value, (StopIteration, StopAsyncIteration)):
                        if exc.__cause__ is value:
                            return False
                    raise
                except BaseException as exc:
                    if exc is not value:
                        raise


    def asynccontextmanager(func):
        @wraps(func)
        def helper(*args, **kwds):
            return _AsyncGeneratorContextManager(func, args, kwds)
        return helper
