"""Extract J96/N66 19H422 and native N56 16H88 inputs."""
from patches.shared.impl.inputs import OUTPUTS, inputs_ready, generate as generate_inputs


def generate(n56, n66, j96, out, model="N56"):
    return generate_inputs(n56, n66, j96, out, build="19H422", model=model)
