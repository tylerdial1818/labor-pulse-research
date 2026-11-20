from pathlib import Path

import pytest

from lpresearch.pipelines.utah_roi import model

REPO = Path(__file__).resolve().parents[1]
UTAH = REPO / "studies" / "utah_roi"
NODE_REFERENCE = UTAH / "reference" / "node-v0.1.0"


@pytest.fixture(scope="session")
def inputs():
    return model.load_model_inputs(UTAH)


@pytest.fixture(scope="session")
def evidence(inputs):
    return model.build_evidence_model(inputs)


@pytest.fixture(scope="session")
def reference_scenario(inputs):
    return next(s for s in inputs.scenarios if s["scenario"] == "Reference")


@pytest.fixture(scope="session")
def reference(inputs, evidence, reference_scenario):
    return model.evaluate_scenario(inputs, evidence, reference_scenario)
