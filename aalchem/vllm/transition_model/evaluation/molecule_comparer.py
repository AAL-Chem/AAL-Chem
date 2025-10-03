from rdkit import Chem
from rdkit.Chem import inchi
from collections import Counter
from typing import List, Dict
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')
RDLogger.DisableLog('rdApp.info')


class MoleculeComparer:
    """
    A class for evaluating and comparing molecular structures using SMILES and SMARTS patterns.
    """

    def validate_reactant_smiles(self, reactant_list: List[str]):
        """
        Validates if all parts of a reactant string (separated by periods) are valid SMILES.
        
        Args:
            reactant_list (List[str]): A list of SMILES strings potentially containing multiple molecules
                                   separated by periods.
        
        Returns:
            bool: True if all parts are valid SMILES, False otherwise.
        """

        if len(reactant_list) == 1:
            assert '.' not in reactant_list[0], f"Invalid SMILES: {reactant_list[0]}"
        
        # Check if each part is a valid SMILES
        for reactant in reactant_list:
            mol = Chem.MolFromSmiles(reactant)
            if mol is None:
                return False
        
        # All parts were valid
        return True

    def template_matches_ground_truth(
        self,
        ground_truth_smiles, 
        template_pattern,
        consider_stereochemistry=True,
        min_ground_truth_specificity=0.75
    ):
        """
        Checks if a SMARTS template specifically represents enough of a ground truth molecule.
        
        Args:
            ground_truth_smiles (str): SMILES string of the ground truth molecule
            template_pattern (str): SMARTS pattern template to evaluate
            min_ground_truth_specificity (float): Minimum fraction of ground truth atoms
                                                that must be matched by specific (non-wildcard)
                                                atoms in the template
        
        Returns:
            bool: True if template sufficiently represents the ground truth molecule
        """
        # Parse the ground truth molecule
        ground_truth_mol = Chem.MolFromSmiles(ground_truth_smiles)
        if ground_truth_mol is None:
            print(f"Warning: Could not parse Ground Truth SMILES: {ground_truth_smiles}")
            return False
        
        # Parse the template
        template_mol = Chem.MolFromSmarts(template_pattern)
        if template_mol is None:
            print(f"Warning: Could not parse suggtested Template SMARTS pattern: {template_pattern}")
            return False
        
        # Get matches of template to ground truth
        matches = ground_truth_mol.GetSubstructMatches(template_mol, useChirality=consider_stereochemistry)
        if not matches:
            return False  # Template doesn't match ground truth at all
        
        # Total atoms in ground truth
        ground_truth_atoms = ground_truth_mol.GetNumAtoms()
        print(ground_truth_atoms)

        # Find the match that covers the most ground truth atoms
        max_covered_atoms = 0
        for match in matches:
            # Each match is a tuple of atom indices in the ground truth molecule
            # that correspond to the template atoms
            print(match)
            covered_atoms = len(set(match))  # Use set to handle any duplicates
            max_covered_atoms = max(max_covered_atoms, covered_atoms)
        
        # Calculate specificity ratio based on actual coverage
        specificity_ratio = max_covered_atoms / ground_truth_atoms
        print(f"Ground truth atoms: {ground_truth_atoms}")
        print(f"Max covered atoms: {max_covered_atoms}")
        print(f"Specificity ratio: {specificity_ratio}")
        
        # Return true if overlap meets minimum threshold
        return specificity_ratio >= min_ground_truth_specificity

    def get_molecule_census(self, mol):
        """
        Helper function to get a census of atoms and bonds in a molecule.

        Args:
            mol: An RDKit molecule object.

        Returns:
            tuple: A tuple containing two Counter objects:
                - Atom counts (e.g., {'C': 4, 'O': 1})
                - Bond counts (e.g., {SINGLE: 4, DOUBLE: 1})
        """
        atom_counts = Counter(atom.GetSymbol() for atom in mol.GetAtoms())
        bond_counts = Counter(bond.GetBondType() for bond in mol.GetBonds())
        return atom_counts, bond_counts

    def are_molecules_identical(self, smiles1, smiles2, consider_stereochemistry=True, method='inchi'):
        """
        Checks if two SMILES strings represent the same molecule.

        Args:
            smiles1 (str): The SMILES string of the first molecule.
            smiles2 (str): The SMILES string of the second molecule.
            consider_stereochemistry (bool): Whether to consider stereochemistry in the comparison.
                                           Default is True.
            method (str): Comparison method to use. Options:
                        - 'inchi': Uses InChI representation for accurate, standardized comparison.
                                  Handles tautomers and resonance structures well.
                        - 'canonical': Uses RDKit's canonical SMILES. Fast but sometimes misses
                                     complex equivalences like tautomers.
                        - 'graph': Uses atom/bond counting and substructure matching. Checks if
                                  molecules have identical atom and bond compositions, then verifies
                                  identical connectivity via mutual substructure matching.
                                  May fail with symmetric structures or complex cases.
                        Default is 'inchi' for most accurate comparison.

        Returns:
            bool: True if the molecules are identical, False otherwise.

        Note:
            - 'inchi' method: Most robust. Creates a canonical string representation that accounts
              for atom numbering, resonance forms, and tautomers.
            - 'canonical' method: Faster but less comprehensive. Two molecules with the same atoms
              and bonds in the same connectivity will have the same canonical SMILES.
            - 'graph' method: A two-step process that first compares atom and bond counts (fast filter),
              then checks if each molecule is a substructure of the other. This can sometimes
              fail with highly symmetric molecules where multiple valid substructure mappings exist.
        """
        # Create molecule objects from the SMILES strings
        mol1 = Chem.MolFromSmiles(smiles1)
        mol2 = Chem.MolFromSmiles(smiles2)

        # Handle cases where SMILES are invalid
        if mol1 is None or mol2 is None:
            print(f"Warning: Invalid SMILES provided. ('{smiles1}', '{smiles2}')")
            return False
            
        if method == 'canonical':
            # Compare canonical SMILES - simplest approach
            canon_smiles1 = Chem.MolToSmiles(mol1, isomericSmiles=consider_stereochemistry)
            canon_smiles2 = Chem.MolToSmiles(mol2, isomericSmiles=consider_stereochemistry)
            return canon_smiles1 == canon_smiles2
            
        elif method == 'inchi':
            # InChI provides a standardized representation that's excellent for identity checking
            # Convert molecules to InChI strings with or without stereochemistry

            assert consider_stereochemistry == True, "InChI comparison requires no stereochemistry"

            inchi1 = inchi.MolToInchi(mol1)
            inchi2 = inchi.MolToInchi(mol2)
            return inchi1 == inchi2
                
        elif method == 'graph':
            # Use the original graph-based approach
            # Get the census (counts of each atom type and bond type) for both molecules
            atom_counts1, bond_counts1 = self.get_molecule_census(mol1)
            atom_counts2, bond_counts2 = self.get_molecule_census(mol2)

            # If the census of atoms or bonds is different, they cannot be a perfect match
            if atom_counts1 != atom_counts2 or bond_counts1 != bond_counts2:
                return False

            # Check substructure match with or without considering stereochemistry
            return mol1.HasSubstructMatch(mol2, useChirality=consider_stereochemistry) and \
                   mol2.HasSubstructMatch(mol1, useChirality=consider_stereochemistry)
        
        else:
            raise ValueError(f"Unknown comparison method: {method}. Use 'inchi', 'canonical', or 'graph'")


    def evaluate_reactant_pair(self, ground_truth_reactants: List[str], predicted_reactants: List[str], 
                           is_template=False, consider_stereochemistry=True, comparison_type="inchi"):
        """
        Evaluate if predicted reactants match ground truth reactants.
        
        Args:
            ground_truth_reactants (list): List of ground truth reactant SMILES
            predicted_reactants (list): List of predicted reactant SMILES
            is_template (bool): Whether the prediction contains templates
            consider_stereochemistry (bool): Whether to consider stereochemistry in comparison
            comparison_type (str): Method to use for comparison ('inchi', 'canonical', 'graph')
            
        Returns:
            dict: Evaluation results with the following keys:
                - is_match: Boolean indicating if the prediction perfectly matches ground truth
                - comparison_type: The method used for comparison (inchi, canonical, graph, or template)
                - stereochemistry: Whether stereochemistry was considered in the comparison
        """
        # assert that if the len() of both lists is 1, that there is no . in there as we want to work on splitted reactants
        if len(ground_truth_reactants) == 1 and len(predicted_reactants) == 1:
            assert '.' not in ground_truth_reactants[0]
            assert '.' not in predicted_reactants[0]

        # If template matching is used, override the comparison type
        actual_comparison_type = "template" if is_template else comparison_type
        
        # Check if number of reactants matches first
        if len(ground_truth_reactants) != len(predicted_reactants):
            return {
                "is_match": False,
                "comparison_type": actual_comparison_type,
                "stereochemistry": consider_stereochemistry
            }
        
        # Make copies to track unmatched reactants
        remaining_gt = list(ground_truth_reactants)
        remaining_pred = list(predicted_reactants)
        
        # For each ground truth reactant, try to find a match in predicted reactants
        # GROUND TRUTH MATCHING ALGORITHM:
        # For each ground truth reactant, we try to find a matching predicted reactant.
        # We use list(remaining_gt) to create a copy of the list for safe iteration
        # while removing matched items from the original list.
        for gt_reactant in list(remaining_gt):
            found_match = False      # Flag to track if we found a match for this ground truth reactant
            matching_pred = None     # Will store the matching predicted reactant if found
            
            # For each unmatched predicted reactant, check if it matches the current ground truth reactant
            for pred_reactant in list(remaining_pred):
                # Choose comparison method based on whether we're dealing with templates
                if is_template:
                    # For templates: Use substructure matching
                    # This checks if the template (pred_reactant) represents a significant portion 
                    # of the ground truth molecule (at least 75% coverage)
                    is_match = self.template_matches_ground_truth(
                        gt_reactant,                          # The full molecule from ground truth
                        pred_reactant,                        # The template pattern to match against
                        consider_stereochemistry=consider_stereochemistry,
                        min_ground_truth_specificity=0.75     # At least 75% of GT atoms must be covered
                    )
                else:
                    # For regular molecules: Use exact matching via chosen method (inchi by default)
                    # This checks if the molecules are chemically identical
                    is_match = self.are_molecules_identical(
                        gt_reactant, 
                        pred_reactant,
                        method=comparison_type,              # inchi, canonical, or graph
                        consider_stereochemistry=consider_stereochemistry
                    )
                    
                # If we found a match, record it and stop checking other predictions
                if is_match:
                    found_match = True
                    matching_pred = pred_reactant
                    break  # Stop looking at other predicted reactants
            
            # After checking all predictions for this ground truth reactant
            if found_match:
                # Remove both reactants from their respective lists to ensure
                # 1-to-1 matching (each reactant can only match once)
                remaining_gt.remove(gt_reactant)
                remaining_pred.remove(matching_pred)
                # Continue to the next ground truth reactant
        
        # Perfect match if all reactants were matched
        perfect_match = len(remaining_gt) == 0 and len(remaining_pred) == 0
        
        return {
            "is_match": perfect_match,
            "comparison_type": actual_comparison_type,
            "stereochemistry": consider_stereochemistry
        }