# Necessary imports for ReactionTransformer class
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import rdChemReactions
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')
RDLogger.DisableLog('rdApp.info')
import rxn_insight as ri
import pandas
import argparse
import sys
import os

class ReactionTransformer:
    """
    A class to transform atom-mapped reactions and extract key information.
    NOTE: This expects reversed reaction format (products>reagents>reactants)
    """
    
    def __init__(self, reaction_smiles):
        """
        Initialize with an atom-mapped reaction SMILES in reversed format.
        
        Args:
            reaction_smiles (str): Atom-mapped reaction SMILES in format 'products>reagents>reactants'
        """
        canonicalized_reaction = self.canonicalize_reaction(reaction_smiles)
        self.reaction_smiles = canonicalized_reaction

        self.reaction = None
        self.rxn_insight = None
        self._parse_reaction()
    
    def _parse_reaction(self):
        """Parse the reaction using RDKit and RXN-Insight."""
        # Parse with RDKit
        self.reaction = AllChem.ReactionFromSmarts(self.reaction_smiles)
        
        # For RXN-Insight, we need the original format (reactants>reagents>products)
        original_format = self._reverse_to_original_format(self.reaction_smiles)
        self.rxn_insight = ri.Reaction(original_format, keep_mapping=True)
    
    def _reverse_to_original_format(self, reaction_smiles):
        """Convert from products>reagents>reactants back to reactants>reagents>products for RXN-Insight."""
        parts = reaction_smiles.split('>')
        if len(parts) == 3:
            products, reagents, reactants = parts

            # rxn_insight expects reactants>>products and cant deal with reagents
            return f"{reactants}>>{products}"
            #return f"{reactants}>{reagents}>{products}"
        else:
            raise ValueError(f"Unexpected reaction format: {reaction_smiles}")

    def canonicalize_reaction(self, reaction_smiles: str) -> str:
        """
        Canonicalizes the order of molecules in a reaction SMILES string.
        
        Returns:
            str: A canonical reaction SMILES string.
        """
        # Use AllChem.ReactionFromSmarts with useSmiles=True for robust parsing
        reaction = AllChem.ReactionFromSmarts(reaction_smiles, useSmiles=True)
        
        # The canonical flag sorts the molecules to create a canonical representation
        return rdChemReactions.ReactionToSmiles(reaction, canonical=True)

    def get_product_reagents_reactants(self):
        """
        Get product, reagents, and reactants from the reaction SMILES.
        
        Returns:
            tuple: (product, reagents, reactants) where:
                - product (str): Product SMILES.
                - reagents (str): Reagents SMILES string.
                - reactants (str): Reactants SMILES string.
        """
        
        # Split the reaction SMILES (format: products>reagents>reactants)
        parts = self.reaction_smiles.split('>')
        
        if len(parts) != 3:
            raise ValueError(f"Unexpected reaction format: {self.reaction_smiles}")
        
        product, reagents_str, reactants_str = parts
        
        if not product:
            raise ValueError("Product SMILES cannot be empty")

        # Process reagents
        reagents = reagents_str
        
        # Process reactants
        reactants = reactants_str
        
        if not reactants:
            raise ValueError("Reaction must have at least one reactant")
        
        return product, reagents, reactants

    def get_no_atom_mapping(self):
        """
        Get reaction SMILES without atom mapping.
        
        Returns:
            str: Reaction SMILES without atom mapping
        """
        # Create a copy of the reaction
        reaction_copy = rdChemReactions.ChemicalReaction(self.reaction)
        
        # Remove atom mapping
        for mol in reaction_copy.GetReactants():
            for atom in mol.GetAtoms():
                atom.SetAtomMapNum(0)
        for mol in reaction_copy.GetProducts():
            for atom in mol.GetAtoms():
                atom.SetAtomMapNum(0)
        for mol in reaction_copy.GetAgents():
            for atom in mol.GetAtoms():
                atom.SetAtomMapNum(0)
        
        return rdChemReactions.ReactionToSmiles(reaction_copy)
    
    def get_rxn_insight_class(self):
        """
        Get reaction class from RXN-Insight.
        
        Returns:
            str: Reaction class
        """
        info = self.rxn_insight.get_reaction_info()
        return info.get('CLASS', 'Unknown')
    
    def get_rxn_insight_name(self):
        """
        Get reaction name from RXN-Insight.
        
        Returns:
            str: Reaction name
        """
        info = self.rxn_insight.get_reaction_info()
        return info.get('NAME', 'Unknown')
    
    def _annotate_missing_atom_mapping(self, mols, existing_mapnums):
        """
        Annotate atoms with missing atom mapping numbers in the given molecules.
        
        Args:
            mols: list of RDKit Mol objects
            existing_mapnums: set of already used atom map numbers
        
        Returns:
            list of RDKit Mol objects with all atoms mapped
        """
        import copy
        annotated_mols = []
        next_mapnum = max(existing_mapnums) + 1 if existing_mapnums else 1
        for mol in mols:
            mol = copy.deepcopy(mol)
            for atom in mol.GetAtoms():
                if atom.GetAtomMapNum() == 0:
                    atom.SetAtomMapNum(next_mapnum)
                    next_mapnum += 1
            annotated_mols.append(mol)
        return annotated_mols

    def get_transformation_sites(self, include_bond_type_changes: bool = False):
        """
        Get atoms involved in transformation sites. This is the primary method.

        It can operate in two modes based on the `include_bond_type_changes` flag:
        1. False (default): Identifies only atoms at the site of a complete bond 
           formation or cleavage. Ignores changes in bond order (e.g., single to double).
        2. True: Identifies all atoms involved in any bond change, including bond order.

        Parameters:
        -----------
        include_bond_type_changes : bool, optional
            If True, considers changes in bond type as part of the transformation. 
            Defaults to False.

        Returns:
        --------
        str
            Space-separated list of transformation sites (e.g., "C:1 N:20").
        """
        product_mols = self.reaction.GetReactants()
        reactant_mols = self.reaction.GetProducts()
        product_mol = product_mols[0]

        # Collect all existing atom map numbers from product and reactant mols
        existing_mapnums = set()
        for mol in list(product_mols) + list(reactant_mols):
            for atom in mol.GetAtoms():
                n = atom.GetAtomMapNum()
                if n > 0:
                    existing_mapnums.add(n)

        # Annotate missing atom mapping in reactants
        annotated_reactant_mols = self._annotate_missing_atom_mapping(reactant_mols, existing_mapnums)

        def _get_bonds(mol, include_types):
            """Helper to get a set of unique bonds from a molecule."""
            bonds = set()
            if not mol: return bonds
            for bond in mol.GetBonds():
                atom1_map = bond.GetBeginAtom().GetAtomMapNum()
                atom2_map = bond.GetEndAtom().GetAtomMapNum()
                if atom1_map > 0 and atom2_map > 0:
                    bond_tuple = tuple(sorted((atom1_map, atom2_map)))
                    if include_types:
                        bond_tuple += (bond.GetBondType(),)
                    bonds.add(bond_tuple)
            return bonds

        product_bonds = _get_bonds(product_mol, include_bond_type_changes)
        transformation_atoms = set()

        if len(annotated_reactant_mols) == 1:
            reactant_mol = annotated_reactant_mols[0]
            
            product_atoms = {atom.GetAtomMapNum() for atom in product_mol.GetAtoms() if atom.GetAtomMapNum() > 0}
            reactant_atoms = {atom.GetAtomMapNum() for atom in reactant_mol.GetAtoms() if atom.GetAtomMapNum() > 0}
            
            added_or_removed_atoms = product_atoms.symmetric_difference(reactant_atoms)
            atoms_in_product = added_or_removed_atoms.intersection(product_atoms)
            
            reactant_bonds = _get_bonds(reactant_mol, include_bond_type_changes)
            
            changed_bonds = product_bonds.symmetric_difference(reactant_bonds)
            
            bond_change_atoms = set()
            for bond in changed_bonds:
                bond_change_atoms.update(bond[:2])
            
            transformation_atoms = atoms_in_product.union(bond_change_atoms)
            
        else:
            # Multiple reactants case: find bonds broken to form the reactants
            combined_reactants = annotated_reactant_mols[0]
            for i in range(1, len(annotated_reactant_mols)):
                combined_reactants = Chem.CombineMols(combined_reactants, annotated_reactant_mols[i])

            reactant_bonds = _get_bonds(combined_reactants, include_bond_type_changes)
            
            broken_bonds = product_bonds - reactant_bonds
            
            for bond in broken_bonds:
                transformation_atoms.update(bond[:2])

        # Map the identified atom numbers to symbols from the product molecule
        sites = []
        for atom in product_mol.GetAtoms():
            if atom.GetAtomMapNum() in transformation_atoms:
                sites.append(f"{atom.GetSymbol()}:{atom.GetAtomMapNum()}")
        
        return " ".join(sites)

    def forward_to_retro_reaction_class(self, reaction_type):
        """
        Convert a forward synthesis reaction type to its retrosynthetic equivalent.
        
        Parameters:
        -----------
        reaction_type : str
            The forward reaction type to be converted
            
        Returns:
        --------
        str : The corresponding retrosynthetic reaction type
        """
        # Mapping with explanations
        conversion_map = {
            "Heteroatom Alkylation and Arylation": "Dealkylation / Dearylation",  # Breaking C-N, C-O, or C-S bonds in retrosynthesis
            "Acylation": "Deacylation",  # Hydrolysis of amides/esters in retrosynthesis
            "Reduction": "Oxidation",  # Increasing oxidation state in retrosynthesis
            "C-C Coupling": "C-C Bond Cleavage / Disconnection",  # Breaking carbon-carbon bonds in retrosynthesis
            "Deprotection": "Protection",  # Adding protecting groups back in retrosynthesis
            "Miscellaneous": "Miscellaneous",  # Catch-all category with no clear opposite
            "Protection": "Deprotection",  # Removing protecting groups in retrosynthesis
            "Oxidation": "Reduction",  # Decreasing oxidation state in retrosynthesis
            "Aromatic Heterocycle Formation": "Heterocycle Ring Opening",  # Breaking the formed heterocyclic ring in retrosynthesis
            "Functional Group Interconversion": "Functional Group Interconversion",  # Often bidirectional transformations
            "Functional Group Addition": "Elimination"  # Removing groups to reform multiple bonds in retrosynthesis
        }

        # if the reaction_type is None or empty or NaN, return an error message
        if not reaction_type or pandas.isna(reaction_type):
            return None

        # Exact match
        if reaction_type in conversion_map:
            return conversion_map[reaction_type]
        
        # Case-insensitive match
        for key in conversion_map:
            if key.lower() == reaction_type.lower():
                return conversion_map[key]
        
        # Partial match (for abbreviated inputs)
        for key in conversion_map:
            if reaction_type.lower() in key.lower():
                return conversion_map[key]
        
        # If no match found
        return f"Unknown reaction type: {reaction_type}"

    def get_all_info(self):
        """
        Get all transformation information.
        
        Returns:
            dict: Dictionary containing all information
        """

        # product, reagents, reactants
        product, reagents, reactants = self.get_product_reagents_reactants()

        # get also the retro reaction class
        forward_reaction_class = self.get_rxn_insight_class()
        retro_reaction_class = self.forward_to_retro_reaction_class(forward_reaction_class)

        # Get the transformation sites, considering bond type changes
        changed_atom_sites = self.get_transformation_sites(include_bond_type_changes=False)
        # If no formed sites are found, try with bond type changes as a fallback given that some reactions may not have clear disconnection sites. This can also be used for reaction center identification.
        changed_atom_and_bond_sites = self.get_transformation_sites(include_bond_type_changes=True)
        
        
        # removed because the reaction center should include bond type changes
        
        return {
            'failed_canonicalization': False,
            'canonicalized_retro_reaction': self.reaction_smiles,
            'canonicalized_product': product,
            'canonicalized_reagents': reagents,
            'canonicalized_reactants': reactants,
            'no_atom_mapping': self.get_no_atom_mapping(),
            'rxn_insight_class': forward_reaction_class,
            'rxn_insight_class_retro': retro_reaction_class,
            'rxn_insight_name': self.get_rxn_insight_name(),
            'changed_atom_sites': changed_atom_sites,
            'changed_atom_and_bond_sites': changed_atom_and_bond_sites
        }

# Function to safely apply ReactionTransformer
def process_reaction(reaction_smiles):
    """Process a single reaction and return transformation info."""
    try:
        transformer = ReactionTransformer(reaction_smiles)
        return transformer.get_all_info()
    except Exception as e:
        print(f"Error processing reaction {reaction_smiles}: {str(e)}")
        return {
            'failed_canonicalization': True,
            'canonicalized_retro_reaction': None,
            'canonicalized_product': None,
            'canonicalized_reagents': None,
            'canonicalized_reactants': None,
            'no_atom_mapping': None,
            'rxn_insight_class': None,
            'rxn_insight_class_retro': None,
            'rxn_insight_name': None,
            'changed_atom_sites': None,
            'changed_atom_and_bond_sites': None
        }

def reverse_reaction_format(reaction_smiles):
    """
    Convert reaction from 'reactants>reagents>products' to 'products>reagents>reactants' format.
    
    Args:
        reaction_smiles (str): Reaction SMILES in format 'reactants>reagents>products'
        
    Returns:
        str: Reaction SMILES in format 'products>reagents>reactants'
    """
    parts = reaction_smiles.split('>')
    
    if len(parts) == 3:
        reactants, reagents, products = parts
        return f"{products}>{reagents}>{reactants}"
    else:
        # Handle cases where there might be different formatting
        raise ValueError(f"Unexpected reaction format: {reaction_smiles}")

def main():
    """Command-line interface for processing chemical reactions."""
    parser = argparse.ArgumentParser(description='Process chemical reaction data to extract transformations and generate processed output')
    parser.add_argument('input_file', help='Input CSV file containing reaction data')
    parser.add_argument('output_file', help='Output CSV file for processed data')
    # custom argument for reaction column
    parser.add_argument('--reaction-column', type=str, default='reactants>reagents>production', help='Column name containing reaction SMILES (default: reactants>reagents>production)')
    parser.add_argument('--chunk-size', type=int, default=1000, help='Number of reactions to process per chunk (default: 1000)')
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"Processing reactions from: {args.input_file}")
    print(f"Output will be saved to: {args.output_file}")
    print(f"Using reaction column: {args.reaction_column}")
    print(f"Chunk size: {args.chunk_size}")
    
    try:
        # Read the input data
        data = pandas.read_csv(args.input_file)
        print(f"Loaded {len(data)} reactions from input file")
        
        # Apply to entire dataset - convert format for retrosynthesis processing
        data['retro_reaction'] = data[args.reaction_column].apply(reverse_reaction_format)

        data['num_reactants'] = data['retro_reaction'].apply(lambda x: x.split('>')[-1].count('.') + 1)
        
        # Process all reactions in filtered dataset
        print("Processing reactions... This may take a while.")
        processed_results = []
        
        verbose_reaction = True  # Set to True if you want to see the current reaction being processed

        for idx, reaction in enumerate(data['retro_reaction']):
            if idx % args.chunk_size == 0:
                print(f"Processed {idx}/{len(data)} reactions...")

                if verbose_reaction:
                    print(f"Current reaction: {reaction}")
            
            result = process_reaction(reaction)
            processed_results.append(result)
        
        print(f"Finished processing {len(processed_results)} reactions.")
        
        # Add the new columns to the filtered dataset
        data['failed_canonicalization'] = [r['failed_canonicalization'] for r in processed_results]
        data['canonicalized_retro_reaction'] = [r['canonicalized_retro_reaction'] for r in processed_results]
        data['canonicalized_product'] = [r['canonicalized_product'] for r in processed_results]
        data['canonicalized_reagents'] = [r['canonicalized_reagents'] for r in processed_results]
        data['canonicalized_reactants'] = [r['canonicalized_reactants'] for r in processed_results]
        data['no_atom_mapping'] = [r['no_atom_mapping'] for r in processed_results]
        data['rxn_insight_class'] = [r['rxn_insight_class'] for r in processed_results]
        data['rxn_insight_class_retro'] = [r['rxn_insight_class_retro'] for r in processed_results]
        data['rxn_insight_name'] = [r['rxn_insight_name'] for r in processed_results]
        data['changed_atom_sites'] = [r['changed_atom_sites'] for r in processed_results]
        data['changed_atom_and_bond_sites'] = [r['changed_atom_and_bond_sites'] for r in processed_results]
        
        # Save the processed data
        data.to_csv(args.output_file, index=False)
        print(f"Successfully processed {len(data)} reactions and saved to {args.output_file}")
        
    except Exception as e:
        print(f"Error processing reactions: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()