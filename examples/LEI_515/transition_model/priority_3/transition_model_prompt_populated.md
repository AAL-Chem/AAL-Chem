**Persona:**
You are an expert chemist specializing in synthetic reaction modeling.

**Primary Goal:**
Given a product molecule, a specified reaction center, and a reaction type, your task is to generate all chemically reasonable reactant molecules that would form the product. When a reaction name is provided, you will model that specific transformation. When it is not, you will suggest and model all plausible reactions for the given transformation. You will then validate each option based on practical chemical principles. The entire output must be a single, valid JSON object.

**Input Schema:**
* `reaction_center_atoms`: A string identifying the **approximate location** of the transformation, using atom mappings. This serves as a guide for the model to identify the precise reaction center.
    * **Example (Bond Cleavage):** `"C:5 N:7"`
    * **Example (Ring Formation/Cycloaddition):** `"c:1 c:2 c:3 c:4 c:5 c:6"`
    * **Example (FGI):** `"C:8 C:9"`
    * **Example (Protection):** `"N:26"`
    * **Example (Stereochemical Change):** `"C:25"`
* `product_smiles`: The atom-mapped SMILES string of the product molecule.
* `forward_reaction_name` (optional): The name of a specific forward reaction to be modeled.
* `retrosynthesis_reaction_examples` (optional): A list of retrosynthesis reaction SMILES strings to use as a blueprint.

**Internal Analysis Pipeline:**
To generate the final JSON object, you will internally execute the following data transformation pipeline. This is a strict, one-way sequence from Step 1 to the final output. The steps must be executed exactly once in order, without looping back to a previous step. The output of each step serves as the direct input for the next.

1.  **Step 1: Determine Reaction(s) to Model**
    * **Input:** The `forward_reaction_name` (optional) and `reaction_center_atoms` from the user.
    * **Process:** If a `forward_reaction_name` is provided, use it as the sole reaction. If not, analyze the `reaction_center_atoms` to generate a list of potential `forward_reaction_name`s.
    * **Output (Internal):** A list of reaction names to be modeled.

2.  **Step 2: Refine Reaction Center**
    * **Input:** The list of `forward_reaction_name`s (Step 1), the user's `reaction_center_atoms`, and any `retrosynthesis_reaction_examples`.
    * **Process:** For each `forward_reaction_name`, use your expert chemical knowledge and the provided examples to determine the **precise and complete reaction center**. The user's input is a guide for the location, but you must refine it by adding or removing atoms to match the true mechanism of the reaction.
    * **Output (Internal):** A mapping of each `forward_reaction_name` to its `precise_reaction_center_atoms` string.

3.  **Step 3: Extract Atom-Level Reaction Template**
    * **Input:** The list of `forward_reaction_name`s from Step 1, the **precise reaction center** from step 2, and the user-provided `retrosynthesis_reaction_examples`.
    * **Process:** For each `forward_reaction_name`, analyze its corresponding valid example(s). Your primary goal is to extract the **structural pattern** and **JSON format** of the transformation from these examples. By analyzing the transformation from the product to the reactant side, extract a formal, atom-level retrosynthetic rule (the "template"). If a specific chemical detail in an example's `modification_smarts` seems inconsistent with the `forward_reaction_name`, prioritize deriving the correct chemical group based on your expert knowledge, while strictly adhering to the JSON structure taught by the example. If no valid examples are provided, derive the template from your general chemical knowledge.

    * **Output (Internal):** A mapping of each reaction name to its extracted reaction template. The template **must** be a single JSON object following this structure:
        ```json
        // Template Structure: A self-contained rule object
        {
          "precise_reaction_center_atoms": "<space_separated_list_of_atom_maps>",
          "modifications": [
            {
              "target_atom_map": "<map_number_of_atom_to_modify>",
              "modification_smarts": "<SMILES_or_SMARTS_of_the_complete_functional_group_on_this_atom_in_the_reactant>"
            }
            // ... one object for each atom that is modified ...
          ]
        }
        ```

    * **Example 1 (Intermolecular Disconnection):** This pattern covers reactions where **one product is formed from two** reactant molecules.
        ```json
        {
          "precise_reaction_center_atoms": "C:1 C:7",
          "modifications": [
            { "target_atom_map": "1", "modification_smarts": "[c:1][X]" },
            { "target_atom_map": "7", "modification_smarts": "[c:7][Y]" }
          ]
        }
        ```

    * **Example 2 (Intramolecular Cyclization):** This pattern covers reactions where a new ring is formed within a **single precursor molecule**.
        ```json
        {
          "precise_reaction_center_atoms": "C:1 C:6",
          "modifications": [
            { "target_atom_map": "1", "modification_smarts": "[C:1]X" },
            { "target_atom_map": "6", "modification_smarts": "[C:6]Y" }
          ]
        }
        ```

    * **Example 3 (Functional Group Interconversion - FGI):** This pattern covers reactions where a functional group is transformed into another on a **single molecule**.
        ```json
        {
          "precise_reaction_center_atoms": "C:1 O:2",
          "modifications": [
            { "target_atom_map": "1", "modification_smarts": "[C:1]=[O:2]" }
          ]
        }
        ```

    * **Example 4 (Multi-Component Reaction - MCR):** This pattern covers reactions where **one product is formed from three or more** reactant molecules.
        ```json
        {
          "precise_reaction_center_atoms": "A:1 B:2 C:3",
          "modifications": [
            { "target_atom_map": "1", "modification_smarts": "[A]X" },
            { "target_atom_map": "2", "modification_smarts": "[B]Y" },
            { "target_atom_map": "3", "modification_smarts": "[C]Z" }
          ]
        }
        ```

4.  **Step 4: Generate Precursor Molecule(s)**
    * **Input:** The `product_smiles` and `precise_reaction_center_atoms`.
    * **Process:** Based on the number of fragments implied by the transformation type (e.g., two for an intermolecular disconnection, one for an FGI, three for a 3-component MCR), generate the corresponding core precursor molecule(s). This is done by cleaving the necessary bonds in the product or, for 1-to-1 transformations, identifying the single precursor scaffold.
    * **Output (Internal):** The distinct molecular fragment(s) with atom mapping preserved.

5.  **Step 5: Apply Reaction Template to Generate Reactant Permutations**
    * **Input:** The precursor(s) (Step 4) and the reaction templates (Step 3).
    * **Process:** For each reaction's template, apply the extracted retrosynthetic template to the precursor(s). The `precise_reaction_center_atoms` provided by the user defines the **locality** of the transformation. You must use your chemical expertise to apply the template correctly to the atoms **in and around this specified location**, ensuring the final transformation is chemically consistent with the template's logic. This process must include generating **all possible permutations** of the reactive groups. This directive must be interpreted with absolute completeness in two ways:
        1.  **Fragment-Role Permutations:** For a disconnection into multiple fragments with distinct reactive groups, you must generate reactant sets for **all** possible assignments of those groups to the fragments.
        2.  **Intra-Group Class Permutations:** If a generated reactive group belongs to a general chemical class (e.g., an "organohalide," "leaving group," or "protecting group"), you are required to generate an exhaustive list of separate options for **all chemically distinct members of that class known to be compatible with the reaction.**
        The model is **explicitly forbidden** from filtering this list based on commonality, synthetic efficiency, or perceived viability. If a variant is chemically possible, it must be included in the output.
    * **Output (Internal):** A list of all potential reactant options generated from this exhaustive process, each associated with a `forward_reaction_name`. No chemically possible permutations may be omitted. Please dont provide reagents as reactants.

6.  **Step 6: Validate and Justify Each Option**
    * **Input:** The list of potential reactant options from Step 5.
    * **Process:** For each generated option, perform a rigorous chemical validation.
        * A) **Stability:** Are the proposed reactants chemically stable?
        * B) **Chemoselectivity:** Would the reaction be selective? Are there other functional groups that would interfere?
        * C) **Stereochemical Consistency:** Is the transformation stereochemically sound? Does it correctly account for the creation or modification of stereocenters in the product?
        * D) **Plausibility:** Is the reaction electronically and sterically plausible for this specific pair?
    * **Output (Internal):** The same list of options, but now each object contains an `is_valid` boolean and a detailed `reasoning` string that explicitly addresses these validation points.

### **Step 7: Final Formatting and Grouping**
* **Input:** The validated and justified flat list of *real chemical options* from Step 6.
* **Process:**
    1.  **Group Options:** Begin by grouping the list of validated options by their `forward_reaction_name`.
    2.  **Extract Wildcard Reaction Class** Looking at the validated options and their reaction names, you must deduct a general reaction class template if possible using the `<CLASS:..>` tag. It signals that a member of this chemical class (e.g. `<CLASS:AmineProtectingGroup>`) should be used instead of an explicit molecular structure.
    3.  **Generate General Template Entry (if applicable):** For each extracted general reaction class template, you **should** create one additional, special permutation object derived from the two provided general reaction classes. This object serves as the general, machine-readable representation for the entire transformation class and should be placed at the **beginning** of the `reactant_permutations` list. The two possible options for this general reaction class template are:
        * For a **Defined Chemical Class** (e.g., `<CLASS:Halogen>`), where the reactants share a specific generalizable atoms across all precursor molecule(s) from Step 6, introduce the a SMARTS pattern (e.g., `[A,B,C]`) as a replacement for these generalizable atoms. If possible, create a joined template covering generalizable atoms on all possible reactants instead of creating multiple templates.
        * For a **Wildcard Addition Class** (e.g., `<CLASS:ProtectingGroup>`), where the specific reagent added in the retrosynthetic step is a strategic choice from a broad and variable unknown set, the added group is represented by a generic wildcard atom (`[*]`). This string is generated by taking the appropriate precursor molecule(s) from Step 6 and creating a new bond between the wildcard atom (`[*]`) and the product that generalizes the explicit reactant options.
        * This special permutation object must have the following structure:
            * `reactants`: A list containing the single, atom-mapped SMILES string with the general representation.
            * `is_valid`: `true`.
            * `is_template`: `true`. Indicating that this result is a wildcard template.
            * `reasoning`: A string that explicitly identifies this as the general template and names the chemical class in the format `<Class:XYZ>`.
    4.  **Assemble Final List:** For each unique reaction, create a single object containing the `forward_reaction_name` and its final `reactant_permutations` list. This list will now contain the general template entry at the top (if applicable), followed by all the validated, specific examples from Step 6.
    5.  **Finalize and Clean:** Assemble these grouped objects into the final `reaction_analysis` list according to the `Output Schema`. Keep the original atom mapping of the product where possible and do not introduce new atom maps on the reactant side, but use unmapped atoms.
* **Output:** The final, single JSON object.

**Output Schema — Strict JSON Only:**
```json
{
  "product": "<SMILES>",
  "reaction_analysis": [
    {
      "forward_reaction_name": "Name of Reaction 1 (e.g., Suzuki-Miyaura coupling)",
      "reactant_permutations": [
        {
          "reactants": ["<SMILES_1A>", "<SMILES_1B>"],
          "is_valid": true,
          "is_template": false,
          "reasoning": "This permutation is valid. The reactants are stable and the reaction is chemoselective."
        },
        {
          "reactants": ["<SMILES_2A>", "<SMILES_2B>"],
          "is_valid": false,
          "is_template": false,
          "reasoning": "This permutation is invalid due to severe steric hindrance at the reaction site."
        }
      ]
    }
    // ... one object for each unique reaction suggested in Step 1 ...
  ]
}

** Input **
  
"reaction_center_atoms": N:17 c:18
"forward_reaction_name": Buchwald-Hartwig/Ullmann-Goldberg/N-arylation secondary amine
"product_smiles": C[CH2:1][C:2]([C:3](=[O:4])[CH2:5][S:6](=[O:7])[c:8]1[cH:9][cH:10][c:11]([C:12](=[O:13])[N:14]2[CH2:15][CH2:16][N:17]([c:18]3[cH:19][c:20]([Cl:21])[cH:22][cH:23][cH:24]3)[C@@H:25]([CH3:26])[C@@H:27]2[CH3:28])[cH:29][c:30]1[Cl:31])([F:32])[F:33]
"retrosynthesis_reaction_examples": [
    "[CH3:1][CH:2]([CH3:3])[NH:4][c:5]1[c:6]([F:7])[cH:8][c:9]([F:10])[c:11](-[n:12]2[cH:13][c:14]([C:15](=[O:16])[OH:17])[c:18](=[O:19])[c:20]3[cH:21][c:22]([F:23])[c:24]([N:25]4[CH2:26][CH:27]([NH2:28])[CH2:29]4)[c:30]([Cl:31])[c:32]23)[n:33]1>CCO.CN(C)C=O.CN1CCCC1.Cl.Cl>F[c:24]1[c:22]([F:23])[cH:21][c:20]2[c:18](=[O:19])[c:14]([C:15](=[O:16])[OH:17])[cH:13][n:12](-[c:11]3[c:9]([F:10])[cH:8][c:6]([F:7])[c:5]([NH:4][CH:2]([CH3:1])[CH3:3])[n:33]3)[c:32]2[c:30]1[Cl:31].[NH:25]1[CH2:26][CH:27]([NH2:28])[CH2:29]1",
    "[CH3:1][N:2]([CH3:3])[c:4]1[c:5]([C:6](=[O:7])[NH:8][CH2:9][C:10](=[O:11])[NH:12][CH:13]2[CH2:14][N:15]([CH:16]3[CH2:17][CH2:18][CH:19]([c:20]4[cH:21][cH:22][cH:23][cH:24][cH:25]4)[CH2:26][CH2:27]3)[CH2:28]2)[cH:29][c:30]([C:31]([F:32])([F:33])[F:34])[cH:35][cH:36]1>>F[c:4]1[c:5]([C:6](=[O:7])[NH:8][CH2:9][C:10](=[O:11])[NH:12][CH:13]2[CH2:14][N:15]([CH:16]3[CH2:17][CH2:18][CH:19]([c:20]4[cH:21][cH:22][cH:23][cH:24][cH:25]4)[CH2:26][CH2:27]3)[CH2:28]2)[cH:29][c:30]([C:31]([F:32])([F:33])[F:34])[cH:35][cH:36]1.[CH3:1][NH:2][CH3:3]",
    "[CH3:1][O:2][C:3](=[O:4])[c:5]1[c:6]([O:7][CH3:8])[cH:9][c:10]([N:11]2[CH2:12][CH2:13][C:14]([F:15])([F:16])[CH2:17][CH2:18]2)[cH:19][cH:20]1>CCOC(C)=O.CN(C)C=O.Cl.O.O=C(O)O.[K+].[K+]>F[c:10]1[cH:9][c:6]([O:7][CH3:8])[c:5]([C:3]([O:2][CH3:1])=[O:4])[cH:20][cH:19]1.[NH:11]1[CH2:12][CH2:13][C:14]([F:15])([F:16])[CH2:17][CH2:18]1",
    "[CH3:1][CH2:2][O:3][C:4](=[O:5])[c:6]1[cH:7][n:8]([CH2:9][c:10]2[cH:11][cH:12][c:13]([Cl:14])[cH:15][cH:16]2)[c:17]2[cH:18][c:19]([N:20]3[CH2:21][CH2:22][N:23]([C:24](=[O:25])[O:26][C:27]([CH3:28])([CH3:29])[CH3:30])[CH2:31][CH2:32]3)[c:33]([F:34])[cH:35][c:36]2[c:37]1=[O:38]>CC#N>F[c:19]1[cH:18][c:17]2[n:8]([CH2:9][c:10]3[cH:11][cH:12][c:13]([Cl:14])[cH:15][cH:16]3)[cH:7][c:6]([C:4]([O:3][CH2:2][CH3:1])=[O:5])[c:37](=[O:38])[c:36]2[cH:35][c:33]1[F:34].[NH:20]1[CH2:21][CH2:22][N:23]([C:24](=[O:25])[O:26][C:27]([CH3:28])([CH3:29])[CH3:30])[CH2:31][CH2:32]1",
    "[O:1]=[N+:2]([O-:3])[c:4]1[cH:5][cH:6][c:7]([N:8]2[CH2:9][CH2:10][N:11]3[CH2:12][CH2:13][O:14][CH2:15][C@H:16]3[CH2:17]2)[cH:18][cH:19]1>CS(C)=O.O>F[c:7]1[cH:6][cH:5][c:4]([N+:2](=[O:1])[O-:3])[cH:19][cH:18]1.[NH:8]1[CH2:9][CH2:10][N:11]2[CH2:12][CH2:13][O:14][CH2:15][C@H:16]2[CH2:17]1"
]