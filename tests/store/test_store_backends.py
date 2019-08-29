import pytest
import json
import importlib
import os
import re

import six
if six.PY2: FileNotFoundError = IOError

import pandas as pd


from great_expectations.data_context.store import (
    StoreBackend,
    InMemoryStoreBackend,
    FilesystemStoreBackend,
)
from great_expectations.util import (
    gen_directory_tree_str,
)

def test_StoreBackendValidation():
    backend = StoreBackend({})

    backend._validate_key( ("I", "am", "a", "string", "tuple") )

    with pytest.raises(TypeError):
        backend._validate_key("nope")

    with pytest.raises(TypeError):
        backend._validate_key( ("I", "am", "a", "string", 100) )

    with pytest.raises(TypeError):
        backend._validate_key( ("I", "am", "a", "string", None) )

    # I guess this works. Huh.
    backend._validate_key( () )


def test_InMemoryStoreBackend():

    with pytest.raises(TypeError):
        my_store = InMemoryStoreBackend(
            config=None,
        )

    my_store = InMemoryStoreBackend(
        config={
            "separator" : "."
        },
    )

    my_key = ("A",)
    with pytest.raises(KeyError):
        my_store.get(my_key)
    
    print(my_store.store)
    my_store.set(my_key, "aaa")
    print(my_store.store)
    assert my_store.get(my_key) == "aaa"

    #??? Putting a non-string object into a store triggers an error.
    # TODO: Allow bytes as well.
    with pytest.raises(TypeError):
        my_store.set(("B",), {"x":1})

    assert my_store.has_key(my_key) == True
    assert my_store.has_key(("B",)) == False
    assert my_store.has_key(("A",)) == True
    assert my_store.list_keys() == [("A",)]

def test_FilesystemStoreBackend_two_way_string_conversion(tmp_path_factory):
    path = str(tmp_path_factory.mktemp('test_FilesystemStore__dir'))
    project_path = str(tmp_path_factory.mktemp('my_dir'))

    config = {
        "base_directory": project_path,
        "file_extension" : "txt",
        "key_length" : 3,
        "filepath_template" : "{0}/{1}/{2}/foo-{2}-expectations.{file_extension}",
        "replaced_substring" : "/",
        "replacement_string" : "__",
    }
    my_store = FilesystemStoreBackend(
        root_directory=os.path.abspath(path),
        config=config,
    )

    tuple_ = ("A/a", "B-b", "C")
    converted_string = my_store._convert_key_to_filepath(tuple_)
    print(converted_string)
    assert converted_string == "A__a/B-b/C/foo-C-expectations.txt"

    recovered_key = my_store._convert_filepath_to_key("A__a/B-b/C/foo-C-expectations.txt")
    print(recovered_key)
    assert recovered_key == tuple_

    with pytest.raises(ValueError):
        tuple_ = ("A/a", "B-b", "C__c")
        converted_string = my_store._convert_key_to_filepath(tuple_)


def test_FilesystemStoreBackend_verify_that_key_to_filepath_operation_is_reversible(tmp_path_factory):
    path = str(tmp_path_factory.mktemp('test_FilesystemStore__dir'))
    project_path = str(tmp_path_factory.mktemp('my_dir'))

    config = {
        "base_directory": project_path,
        "file_extension" : "txt",
        "key_length" : 3,
        "filepath_template" : "{0}/{1}/{2}/foo-{2}-expectations.{file_extension}",
        "replaced_substring" : "/",
        "replacement_string" : "__",
    }
    my_store = FilesystemStoreBackend(
        root_directory=os.path.abspath(path),
        config=config,
    )
    #This should pass silently
    my_store.verify_that_key_to_filepath_operation_is_reversible()


    config = {
        "base_directory": project_path,
        "file_extension" : "txt",
        "key_length" : 3,
        "filepath_template" : "{0}/{1}/foo-{2}-expectations.{file_extension}",
        "replaced_substring" : "/",
        "replacement_string" : "__",
    }
    my_store = FilesystemStoreBackend(
        root_directory=os.path.abspath(path),
        config=config,
    )
    #This also should pass silently
    my_store.verify_that_key_to_filepath_operation_is_reversible()


    config = {
        "base_directory": project_path,
        "file_extension" : "txt",
        "key_length" : 3,
        "filepath_template" : "{0}/{1}/foo-expectations.{file_extension}",
        "replaced_substring" : "/",
        "replacement_string" : "__",
    }
    my_store = FilesystemStoreBackend(
        root_directory=os.path.abspath(path),
        config=config,
    )
    with pytest.raises(AssertionError):
        #This should fail
        my_store.verify_that_key_to_filepath_operation_is_reversible()


def test_FilesystemStoreBackend(tmp_path_factory):
    path = "dummy_str"#str(tmp_path_factory.mktemp('test_FilesystemStoreBackend__dir'))
    project_path = str(tmp_path_factory.mktemp('test_FilesystemStoreBackend__dir'))#str(tmp_path_factory.mktemp('my_dir'))

    my_store = FilesystemStoreBackend(
        root_directory=os.path.abspath(path),
        config={
            "base_directory": project_path,
            "key_length" : 1,
            "filepath_template" : "my_file_{0}",
            "replaced_substring" : "/",
            "replacement_string" : "__",
        }
    )

    #??? Should we standardize on KeyValue, or allow each BackendStore to raise its own error types?
    with pytest.raises(FileNotFoundError):
        my_store.get(("AAA",))
    
    my_store.set(("AAA",), "aaa")
    assert my_store.get(("AAA",)) == "aaa"

    my_store.set(("BBB",), "bbb")
    assert my_store.get(("BBB",)) == "bbb"

    # NOTE: variable key lengths are not yet supported
    # I suspect the best option is to differentiate between stores meant for reading AND writing,
    # vs Stores that only need to support writing. If a store only needs to support writing,
    # we don't need to guarantee reversibility of keys, which makes the internals **much** simpler.

    # my_store.set("subdir/my_file_BBB", "bbb")
    # assert my_store.get("subdir/my_file_BBB") == "bbb"

    # my_store.set("subdir/my_file_BBB", "BBB")
    # assert my_store.get("subdir/my_file_BBB") == "BBB"

    # with pytest.raises(TypeError):
    #     my_store.set("subdir/my_file_CCC", 123)
    #     assert my_store.get("subdir/my_file_CCC") == 123

    # my_store.set("subdir/my_file_CCC", "ccc")
    # assert my_store.get("subdir/my_file_CCC") == "ccc"

    print(my_store.list_keys())
    assert set(my_store.list_keys()) == set([("AAA",), ("BBB",)])

    print(gen_directory_tree_str(project_path))
    assert gen_directory_tree_str(project_path) == """\
test_FilesystemStoreBackend__dir0/
    my_file_AAA
    my_file_BBB
"""


# def test_store_config(tmp_path_factory):
#     path = str(tmp_path_factory.mktemp('test_store_config__dir'))

#     config = {
#         "module_name": "great_expectations.data_context.store",
#         "class_name": "InMemoryStore",
#         "store_config": {
#             "serialization_type": "json"
#         },
#     }
#     typed_config = StoreMetaConfig(
#         coerce_types=True,
#         **config
#     )
#     print(typed_config)

#     loaded_module = importlib.import_module(typed_config.module_name)
#     loaded_class = getattr(loaded_module, typed_config.class_name)

#     typed_sub_config = loaded_class.get_config_class()(
#         coerce_types=True,
#         **typed_config.store_config
#     )

#     data_asset_snapshot_store = loaded_class(
#         root_directory=os.path.abspath(path),
#         config=typed_sub_config,
#     )

# def test_NamespacedFilesystemStore(tmp_path_factory):
#     path = str(tmp_path_factory.mktemp('test_NamespacedFilesystemStore__dir'))
#     project_path = str(tmp_path_factory.mktemp('my_dir'))

#     my_store = NamespacedFilesystemStore(
#         # root_directory=empty_data_context.root_directory,
#         root_directory=os.path.abspath(path),
#         config={
#             "resource_identifier_class_name": "ValidationResultIdentifier",
#             "base_directory": project_path,
#             "file_extension" : ".txt",
#         }
#     )

#     with pytest.raises(TypeError):
#         my_store.get("not_a_ValidationResultIdentifier")

#     with pytest.raises(KeyError):
#         my_store.get(ValidationResultIdentifier(**{}))
    
#     ns_1 = ValidationResultIdentifier(
#         from_string="ValidationResultIdentifier.a.b.c.quarantine.prod-100"
#     )
#     my_store.set(ns_1,"aaa")
#     assert my_store.get(ns_1) == "aaa"

#     ns_2 = ValidationResultIdentifier(
#         from_string="ValidationResultIdentifier.a.b.c.quarantine.prod-200"
#     )
#     my_store.set(ns_2, "bbb")
#     assert my_store.get(ns_2) == "bbb"

#     print(my_store.list_keys())
#     assert set(my_store.list_keys()) == set([
#         ns_1,
#         ns_2,
#     ])

#     # TODO : Reactivate this
#     # assert my_store.get_most_recent_run_id() == "200"


# def test_NamespacedFilesystemStore__validate_key(tmp_path_factory):
#     path = str(tmp_path_factory.mktemp('test_NamespacedFilesystemStore__dir'))
#     project_path = str(tmp_path_factory.mktemp('my_dir'))
 
#     my_store = NamespacedFilesystemStore(
#         root_directory=os.path.abspath(path),
#         config={
#             "resource_identifier_class_name": "ValidationResultIdentifier",
#             "base_directory": project_path,
#             "file_extension" : ".txt",
#         }
#     )

#     my_store._validate_key(ValidationResultIdentifier(
#         from_string="ValidationResultIdentifier.a.b.c.quarantine.prod-100"
#     ))

#     with pytest.raises(TypeError):
#         my_store._validate_key("I am string like")


# def test_NamespacedFilesystemStore_key_listing(tmp_path_factory):
#     path = str(tmp_path_factory.mktemp('test_NamespacedFilesystemStore_key_listing__dir'))
#     project_path = "some_dir/my_store"

#     my_store = NamespacedFilesystemStore(
#         root_directory=os.path.abspath(path),
#         config={
#             "resource_identifier_class_name": "ValidationResultIdentifier",
#             "base_directory": project_path,
#             "file_extension" : ".txt",
#         }
#     )

#     ns_1 = ValidationResultIdentifier(**{
#         "expectation_suite_identifier" : {
#             "data_asset_name" : DataAssetIdentifier("a", "b", "c"),
#             "expectation_suite_name" : "quarantine",
#         },
#         "run_id" : "prod-100",
#     })
#     my_store.set(ns_1,"aaa")

#     print(my_store.list_keys())
#     assert set(my_store.list_keys()) == set([
#         ValidationResultIdentifier(from_string="ValidationResultIdentifier.a.b.c.quarantine.prod-100")
#     ])

#     # TODO : Reactivate this
#     # assert my_store.get_most_recent_run_id() == "100"

# def test_NamespacedFilesystemStore_pandas_csv_serialization(tmp_path_factory):#, empty_data_context):
#     #TODO: We should consider using this trick everywhere, as a way to avoid directory name collisions
#     path = str(tmp_path_factory.mktemp('test_FilesystemStore_pandas_csv_serialization__dir'))

#     my_store = NamespacedFilesystemStore(
#         root_directory=os.path.abspath(path),
#         config={
#             "resource_identifier_class_name": "ValidationResultIdentifier",
#             "serialization_type": "pandas_csv",
#             "base_directory": path,
#             "file_extension": ".csv",
#             "file_prefix": "quarantined-rows-",
#         }
#     )

#     key1 = ValidationResultIdentifier(
#         from_string="ValidationResultIdentifier.a.b.c.quarantine.prod-20190801"
#     )
#     with pytest.raises(AssertionError):
#         my_store.set(key1, "hi")

#     my_df = pd.DataFrame({"x": [1,2,3], "y": ["a", "b", "c"]})
#     my_store.set(key1, my_df)

#     print(gen_directory_tree_str(path))
#     assert gen_directory_tree_str(path) == """\
# test_FilesystemStore_pandas_csv_serialization__dir0/
#     prod-20190801/
#         a/
#             b/
#                 c/
#                     quarantined-rows-quarantine.csv
# """

#     with open(os.path.join(path, "prod-20190801/a/b/c/quarantined-rows-quarantine.csv")) as f_:
#         assert f_.read() == """\
# x,y
# 1,a
# 2,b
# 3,c
# """

#     with pytest.raises(NotImplementedError):
#         my_store.get(key1)
    
