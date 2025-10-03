import pandas as pd
import os
from aalchem.config import paths

from rdkit import Chem
from rdkit.Chem import AllChem
from IPython.display import display




class ReactionDataset:
    """
    Class for loading and preprocessing reaction datasets.
    """
    def __init__(self, name: str):
        self.name = name
        self.builder = None
        self.df = None
        self.dataset = None
        if name:
            self.load_dataset()
            self.preprocess()

    def load_dataset(self) -> pd.DataFrame:
        self.df = pd.read_csv(os.path.join(paths.DATA, self.name + ".csv"))

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, index: int) -> tuple[str, str]:
        return self.dataset.iloc[index]
    
    def preprocess(self):
        ## Add a column with the reactants and products
        for i, row in self.df.iterrows():
            try:
                col_name = 'retro_reaction'
                reactants = row[col_name].split('>>')[0]
                products  = row[col_name].split('>>')[1]
                self.df.at[i, 'reactants'] = ''.join(reactants) + ']'
                self.df.at[i, 'products'] = products
            except Exception as e:
                print(f"Error processing row {i}: {e}")
                self.df.at[i, 'reactants'] = ''
                self.df.at[i, 'products'] = ''


def remove_atom_mapping(reaction):
    """
    Removes atom mapping numbers from a reaction object.
    
    Args:
        reaction (rdkit.Chem.rdChemReactions.ChemicalReaction): The reaction object.
    
    Returns:
        rdkit.Chem.rdChemReactions.ChemicalReaction: The reaction object without atom mappings.
    """
    for mol in reaction.GetReactants():
        for atom in mol.GetAtoms():
            atom.SetAtomMapNum(0)
    for mol in reaction.GetProducts():
        for atom in mol.GetAtoms():
            atom.SetAtomMapNum(0)
    for mol in reaction.GetAgents():
        for atom in mol.GetAtoms():
            atom.SetAtomMapNum(0)
    return reaction



def get_reactant_smiles_from_reaction(reaction_smiles: str, disp: bool = False) -> list[str]:
    reaction = AllChem.ReactionFromSmarts(reaction_smiles)
    print(reaction)
    reaction = remove_atom_mapping(reaction)
    return [Chem.MolToSmiles(mol) for mol in reaction.GetReactants()]

def get_product_smiles_from_reaction(reaction_smiles: str, disp: bool = False) -> str:
    reaction = AllChem.ReactionFromSmarts(reaction_smiles)
    reaction = remove_atom_mapping(reaction)
    return Chem.MolToSmiles(reaction.GetProducts())[0]
