Types
#####

Enumerations
************

.. autoclass:: exporgo.types._ExporgoIntEnum
   :members:
   :private-members:
   :inherited-members:
   :special-members:
   :undoc-members:
   :member-order: bysource

   .. autoclasstoc:: exporgo.types._ExporgoIntEnum
     :sections: public-attrs,private-attrs,public-methods,private-methods


.. autoclass:: exporgo.types.Category
   :members:
   :private-members:
   :inherited-members:
   :special-members:
   :undoc-members:
   :member-order: bysource

    .. attention::
        It is important to note that the order of execution is determined by the value of the enumeration without
        considering duplicates. That is, **the order of execution for steps with duplicate categories and priorities
        cannot be guaranteed**. Therefore, it is advised to compile your operations into one step for EACH category as a
        best practice.

    .. seealso::
        * :class:`Priority <exporgo.types.Priority>` enumeration for more information on how to order priority.
        * :class:`Step <exporgo.step.Step>` for more information on how to define a step.
        * :class:`Pipeline <exporgo.pipeline.Pipeline>` for more information on how to define a pipeline.

    .. autoclasstoc:: exporgo.types.Category
        :sections: public-attrs,private-attrs,public-methods,private-methods


.. autoclass:: exporgo.types.FileFormat
    :members:
    :private-members:
    :inherited-members:
    :special-members:
    :undoc-members:
    :member-order: bysource

    .. tip::
        While each file format has different strengths and weaknesses, the choice of file format is largely dependent
        on your preferences. Briefly summarized, JSON is a human-readable format that is easy for software to parse and
        generate, while YAML is a human-readable format that is easy for humans to read and write. TOML is somewhere
        in-between JSON and YAML.

    .. danger::
        Do not ask for XML support; XML is an abomination.

    .. autoclasstoc:: exporgo.types.FileFormat
        :sections: public-attrs,private-attrs,public-methods,private-methods


.. autoclass:: exporgo.types.Priority
    :members:
    :private-members:
    :inherited-members:
    :special-members:
    :undoc-members:
    :member-order: bysource

    .. attention::
        It is important to note that the order of execution is determined by the value of the enumeration without
        considering duplicates. That is, **the order of execution for steps with duplicate categories and priorities
        cannot be guaranteed**. Therefore, it is advised to compile your operations into one step for EACH category as a
        best practice.

    .. seealso::
        * :class:`Category <exporgo.types.Category>` enumeration for more information on order categories.
        * :class:`Step <exporgo.step.Step>` for more information on how to define a step.
        * :class:`Pipeline <exporgo.pipeline.Pipeline>` for more information on how to define a pipeline.

    .. autoclasstoc:: exporgo.types.Priority
        :sections: public-attrs,private-attrs,public-methods,private-methods


.. autoclass:: exporgo.types.Status
    :members:
    :private-members:
    :inherited-members:
    :special-members:
    :undoc-members:
    :member-order: bysource

    .. autoclasstoc:: exporgo.types.Status
        :sections: public-attrs,private-attrs,public-methods,private-methods

Type Aliases
************

.. autodata:: exporgo.types.Action

.. autodata:: exporgo.types.CollectionType

.. autodata:: exporgo.types.File

.. autodata:: exporgo.types.Folder

.. autodata:: exporgo.types.Modification
