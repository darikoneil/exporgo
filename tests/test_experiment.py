from unittest.mock import patch

import pytest
from joblib import parallel_config

from exporgo.exceptions import (DuplicateRegistrationError,
                                ExperimentNotRegisteredError,
                                InvalidExperimentTypeError)
from exporgo.experiment import (Experiment, ExperimentFactory,
                                ExperimentRegistry, GenericExperiment)


class TestExperiment:

    def test_initialization(self, tmp_path):
        exp = Experiment("TestExperiment", tmp_path)
        assert exp.name == "TestExperiment"
        assert exp.base_directory == tmp_path
        assert exp.mix_ins == []

    def test_remap(self, source, destination):
        exp = Experiment("TestExperiment", source)
        exp.remap(destination)
        assert exp.base_directory == destination


class TestExperimentRegistry:

    def test_register_and_get(self):

        @ExperimentRegistry.register()
        class MockExperiment(Experiment):
            def collect_data(self):
                pass
            def analyze_data(self):
                pass
            def generate_class_files(self):
                pass

        assert ExperimentRegistry.has("MockExperiment")
        assert ExperimentRegistry.get("MockExperiment") == MockExperiment

    def test_register_and_get_alias(self):

            @ExperimentRegistry.register("MockExperiment_2")
            class MockExperiment(Experiment):
                def collect_data(self):
                    pass
                def analyze_data(self):
                    pass
                def generate_class_files(self):
                    pass

            assert ExperimentRegistry.has("MockExperiment_2")
            assert ExperimentRegistry.get("MockExperiment_2") == MockExperiment

    # noinspection PyUnusedLocal
    def test_duplicate_registration(self):

        @ExperimentRegistry.register()
        class MockExperiment3(Experiment):
            def collect_data(self):
                pass
            def analyze_data(self):
                pass
            def generate_class_files(self):
                pass

        with pytest.raises(DuplicateRegistrationError):
            @ExperimentRegistry.register("MockExperiment3")
            class MockExperiment4(Experiment):
                def collect_data(self):
                    pass
                def analyze_data(self):
                    pass
                def generate_class_files(self):
                    pass

    def test_get_nonexistent(self):
        with pytest.raises(ExperimentNotRegisteredError):
            assert ExperimentRegistry.has("NonExistentExperiment") is False
            ExperimentRegistry.get("NonExistentExperiment")

    def test_inline_registration(self):

        class MockExperiment5(Experiment):
            def collect_data(self):
                pass
            def analyze_data(self):
                pass
            def generate_class_files(self):
                pass

        ExperimentRegistry.register()(MockExperiment5)
        assert ExperimentRegistry.has("MockExperiment5")
        assert ExperimentRegistry.get("MockExperiment5") == MockExperiment5

    # noinspection PyUnusedLocal
    def test_invalid_experiment_type(self):
        with pytest.raises(InvalidExperimentTypeError):
            @ExperimentRegistry.register()
            class MockExperiment6:
                ...


class TestExperimentFactory:

    @ExperimentRegistry.register()
    class MockExperiment6(Experiment):
        def collect_data(self):
            pass
        def analyze_data(self):
            pass
        def generate_class_files(self):
            pass

    @ExperimentRegistry.register()
    class MockExperiment7(Experiment):
        def collect_data(self):
            pass
        def analyze_data(self):
            pass
        def generate_class_files(self):
            pass

    @pytest.mark.parametrize("mix_ins", ("MockExperiment6",
                                         MockExperiment6,
                                         ["MockExperiment6", "MockExperiment7"],
                                         [MockExperiment6, MockExperiment7],
                                         ("MockExperiment6", "MockExperiment7"),
                                         (MockExperiment6, MockExperiment7)
                                         ))
    def test_create_experiment(self, tmp_path, mix_ins):

            factory = ExperimentFactory("MockExperiment", tmp_path)
            factory.add_mix_ins(mix_ins)
            instance = factory.instance_constructor()
            assert isinstance(instance, Experiment)


class TestGenericExperiment:

    def test_initialization(self, tmp_path):
        exp = GenericExperiment("GenericExperiment", tmp_path)
        assert exp.key == "GenericExperiment"
        assert exp.base_directory == tmp_path
        assert exp.file_tree.get("results").directory == tmp_path.joinpath("GenericExperiment").joinpath("results")
        assert exp.file_tree.get("figures").directory == tmp_path.joinpath("GenericExperiment").joinpath("figures")

    def test_collect_data(self, tmp_path, source):
        with patch("exporgo.experiment.select_directory", return_value = source):
            with parallel_config(n_jobs=1):
                exp = GenericExperiment("destination", tmp_path)
                exp.collect_data()
                assert exp.file_tree.num_files == len([file for file in source.rglob("*") if file.is_file()])
                assert (exp.file_tree.num_folders ==
                        3 + len([folder for folder in source.rglob("*") if not folder.is_file()]))

    def test_analyze_data(self, tmp_path):
        exp = GenericExperiment("GenericExperiment", tmp_path)
        with pytest.raises(NotImplementedError):
                exp.analyze_data()
