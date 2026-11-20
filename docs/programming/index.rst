Programming Guide
=================

API changes
-----------

Tools and workflows for FLIMAnalyzer, for example in a plugin, are written with the
classes and functions of the ``flim`` package: among them ``flim.core.tool.Tool``,
``flim.core.registry.register_tool``, the config classes of ``flim.core.config`` and
``flim.configs``, and the types of ``flim.core.types``. Before version 1.0.0, these
can change from one minor release to the next.

Where it is feasible, a renamed or removed name stays available for at least one
minor release:

* Using it issues a ``DeprecationWarning`` that names its replacement and the release
  that removes it.
* The release notes (``CHANGELOG.md``) list it under ``Deprecated``, and later under
  ``Removed``.

A change that cannot keep the old name working the same way, for example a field whose
values have another meaning, is listed under ``Changed``. To see the warnings when
your code uses a deprecated name, run Python with ``-W default::DeprecationWarning``
or run your tests with pytest, which shows them.
