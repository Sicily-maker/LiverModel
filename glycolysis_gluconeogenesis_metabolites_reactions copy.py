#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import re
import warnings
from cobra.io.json import load_json_model as load_json_cobra_model
import escher
import mass
import numpy as np
import pandas as pd
import equilibrator_api
from equilibrator_api import ComponentContribution, Q_
import sympy as sym
from cobra import Model, Reaction, Metabolite
import cobra.test
from os.path import join
from mass.util import qcqa
from mass.util import qcqa_model
from cobra import DictList
from mass import (
    MassConfiguration, MassMetabolite, MassModel,
    MassReaction, Simulation, UnitDefinition)
from mass.io.json import save_json_model as save_json_mass_model
from mass.visualization import plot_comparison, plot_time_profile
from mass.visualization import (
    plot_ensemble_phase_portrait, plot_ensemble_time_profile)
mass_config = MassConfiguration()
mass_config.irreversible_Keq = float("inf")
print("MASSpy version: {0}".format(mass.__version__))
from six import iteritems
import matplotlib.pyplot as plt
from mass.thermo import (
    ConcSolver, sample_concentrations,
    update_model_with_concentration_solution)
from cobra.io.json import *
import cobra_dict as c_d
import csv


# In[2]:


#load Recon3D
model_dir = os.path.abspath("../massters_model")
data_dir = os.path.abspath("data")
R3D=load_json_cobra_model(filename=os.path.join(model_dir,"Recon3D.json"))


# In[3]:


_REQUIRED_REACTION_ATTRIBUTES = [
    "id",
    "name",
    "metabolites",
    "lower_bound",
    "upper_bound",
#     "gene_reaction_rule",
]

_REQUIRED_METABOLITE_ATTRIBUTES = ["id", "name", "charge","formula", "compartment"]
_ORDERED_OPTIONAL_METABOLITE_KEYS = [
   
    "_bound",
    "notes",
    "annotation",
]


# In[4]:


# def metabolite_to_dict(metabolite):
#     new_met = dict()
#     for key in _REQUIRED_METABOLITE_ATTRIBUTES:
#         new_met[key] = _fix_type(getattr(metabolite, key))
#     return new_met
from cobra_dict import metabolite_to_dict as metabolite_to_dict
from cobra_dict import reaction_to_dict as reaction_to_dict


# In[5]:


metabolite_list = [
# HEX1    
                    'glc__D_c',
                    'g6p_c',
                    'adp_c',
                    'atp_c',
                    'h_c',
# # GLCt1
#                     'glc__D_e',

# # #G6Pter
#                     'g6p_r',

# # #G6PPer , #GLCter
#                     'h2o_r',
#                     'glc__D_r',
#                     'pi_r',
#  'PGI',
                    'f6p_c', 
# 'H2Oter',
                    'h2o_c',

# 'PIter',
#                     'pi_r',
                    'pi_c',

#'H2Ot',
#                     'h2o_e',
#'PIt',
#                     'pi_e',

#'Ht'
#                     'h_e'  ,
# PFK/ FBP
                    'fdp_c',
# FBA/TPI
                    'dhap_c',
                    'g3p_c',
# GAPD
                    'nad_c',
                    'nadh_c',
                    '_13dpg_c',
#PGK
                    '_3pg_c',
#PGM
                    '_2pg_c',
#ENO
                    'pep_c',
#PYK
                    'pyr_c',
#PYRt2m #what should we do about h_i
#                     'h_m',
#                     'pyr_m',
# #PCm
# #                     'hco3_m',
#                     'pi_m',
#                     'atp_m',
#                     'adp_m',
#                     'oaa_m',
# #PEPCKm
#                     'gtp_m',
#                     'co2_m',
#                     'gdp_m',
#                     'pep_m',
# #PEPtm
#                     "lac__L_c",
#                     "lac__L_e",
#                     "pyr_e"
]


# In[6]:


#Function to add underscore in front of metabolite identifiers which start with a number
def prefix_number_id(id_str):
    """Prefix identifiers that start with numbers."""
    if re.match(r"^\d", id_str):
        id_str = "_" + id_str
    return id_str


# In[7]:


#Loop to edit the names using "prefix_number_id" function defined earlier
for metabolite in R3D.metabolites:
    new_met_id = prefix_number_id(metabolite.id)
    metabolite.id = new_met_id
R3D.repair()


# In[8]:


met_df=pd.DataFrame()
for met in metabolite_list:
    r3d_met= R3D.metabolites.get_by_id(met)
    m=metabolite_to_dict(r3d_met)
    df_2=pd.DataFrame.from_dict(m,orient='index')
    df_2=df_2.T
    met_df=met_df.append(df_2)

met_df=met_df.set_index('id')
met_df


# In[9]:


csv_met = os.path.join(data_dir,"met_df")
met_df.to_csv(csv_met)


# In[ ]:





# In[10]:


reaction_list = ['HEX1',
                'PGI',
                'FBP',
                'PFK',
                'FBA',
                'TPI',
                'GAPD',
                'PGK',
                'PGM',
                'ENO',
#                 'PEPtm',
#                 'PEPCKm',
                'PYK',
#                 'PCm',
                'LDH_L',
#                 'G6Pter',
#                 'G6PPer',
#                 'GLCter',
#                 'GLCt1',
#                 'PYRt2m', 
#                 'H2Oter', 
#                 'PIter', 
#                 'H2Ot', 
#                 'PIt', 
#                 'Ht', 
#                 'L_LACt2r', #lactose transport between lactate in cytosol and extracellular 
#                  'PYRt2',
#                 'ADK1',
                'ATPM',
#                 'DM_nadh'
                ]


# In[ ]:





# In[ ]:





# In[15]:


rxn_df=pd.DataFrame()
for rxn in reaction_list:
    r3d_rxn= R3D.reactions.get_by_id(rxn)
    r=reaction_to_dict(r3d_rxn)
#     print(r)
    df=pd.DataFrame.from_dict(r,orient='index')
    df=df.T
    rxn_df=rxn_df.append(df)

rxn_df=rxn_df.set_index('id')
rxn_df


# In[16]:


csv_rxn = os.path.join(data_dir,"reaction_df")
rxn_df.to_csv(csv_rxn)


# In[ ]:




