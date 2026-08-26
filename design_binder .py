"""
Computational binder design pipeline targeting alpha-bungarotoxin (PDB 2ABX).

Uses RFdiffusion + ProteinMPNN + AlphaFold2-Multimer (binder mode), via the
Proto framework (https://github.com/evo-design/proto-language), to generate
and filter novel binder sequences against the toxin's receptor-binding
hotspot (A36, A38, A39, A40).

Requires a CUDA GPU. Originally run on Google Colab.

Install:
    pip install git+https://github.com/evo-design/proto-language.git
"""

import proto_language
print(proto_language.__file__)

import requests
pdb_content = requests.get("https://files.rcsb.org/download/2ABX.pdb").text

from proto_language.core import Segment, Construct, Constraint, Program
from proto_language.generator import RFdiffusionMPNNBinderGenerator, RFdiffusionMPNNBinderGeneratorConfig
from proto_language.optimizer import RejectionSamplingOptimizer, RejectionSamplingOptimizerConfig
from proto_language.constraint import structure_iptm_constraint, structure_plddt_constraint, protein_length_constraint
from proto_language.constraint.protein_structure.structure_constraint_config import AlphaFold2BinderStructureConfig
from proto_language.constraint.protein_structure.structure_confidence_constraint import StructureBasedConstraintConfig

# --- Target definition -------------------------------------------------
toxin_sequence = "IVCHTTATIPSSAVTCPPGENLCYRKMWCDAFCSSRGKVVELGCAATCPSKKPYEEVTCCSTDKCNHPPKRQPG"
target_segment = Segment(sequence=toxin_sequence, sequence_type="protein")
binder = Segment(length=60, sequence_type="protein")
construct = Construct(segments=[binder, target_segment])

# Receptor-binding hotspot residues on the toxin
hotspot_str = "A36,A38,A39,A40"
hotspot_list = ["A36", "A38", "A39", "A40"]

# --- AlphaFold2-binder structural confidence config ---------------------
binder_af2_config = AlphaFold2BinderStructureConfig(
    target_pdb=pdb_content,
    target_chains=["A"],
    binder_chain=None,
    target_hotspot=hotspot_str,
    binder_input_index=0,
    target_input_indices=[1],
    device="cuda",
)

structure_config = StructureBasedConstraintConfig(
    structure_tool="alphafold2_binder",
    alphafold2_binder_config=binder_af2_config,
)

# --- Generator: RFdiffusion (backbone) + ProteinMPNN (sequence) --------
binder_gen = RFdiffusionMPNNBinderGenerator(
    config=RFdiffusionMPNNBinderGeneratorConfig(
        target_structure=pdb_content,
        target_chains=["A"],
        hotspots=hotspot_list,
        inverse_folding="proteinmpnn",
    )
)
binder_gen.assign(binder)

# --- Constraints: interface confidence, structure confidence, length ---
constraints = [
    Constraint(inputs=[binder, target_segment], function=structure_iptm_constraint,
               function_config=structure_config, weight=1.0),
    Constraint(inputs=[binder, target_segment], function=structure_plddt_constraint,
               function_config=structure_config, weight=1.0),
    Constraint(inputs=[binder], function=protein_length_constraint,
               function_config={"min_length": 40, "max_length": 80}, weight=0.5),
]

# --- Optimize and run ----------------------------------------------------
optimizer = RejectionSamplingOptimizer(
    constructs=[construct], generators=[binder_gen], constraints=constraints,
    config=RejectionSamplingOptimizerConfig(num_samples=6, num_results=3),
)

program = Program(optimizers=[optimizer], num_results=3)
program.run()

# --- Results ---------------------------------------------------------
df = optimizer.to_dataframe()
print(df[['sequence', 'structure_iptm_constraint.score', 'structure_plddt_constraint.score']])

df.to_csv("binder_candidates_batch2.csv", index=False)

# Uncomment if running in Google Colab to download the results file:
# from google.colab import files
# files.download("binder_candidates_batch2.csv")
