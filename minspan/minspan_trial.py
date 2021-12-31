from cobra.io import json
import cobra.test
import os
from os.path import join
from glob import glob
from minspan import minspan,nnz
from cobra.io.json import load_json_model as load_json_model

model_dir = os.path.abspath("models")
trial_json = os.path.join(model_dir,"trial_json")
# cobra.io.save_json_model(trial, trial_json )




for model_file in glob(trial_json):
    model_name = model_file.split('/')[-1]
    if 'model' not in model_name:
        continue
    print(model_name)
    model= load_json_model(model_file)
    if 'NADPHM' in model.reactions:
        model.remove_reactions(['NADPHM'])
    # media = ['EX_lac__L_c', 'EX_pyr_c', 'EX_octa_c', 'EX_gln__L_c', 'EX_acetone_c', 'EX_bhb_c',
    #          'EX_glu__L_c', 'EX_ser__L_c', 'EX_cys__L_c', 'EX_gly_c', 'EX_ala__L_c', 'EX_so3_c',
    #         'EX_etoh_c', 'EX_fru_c']
    media = ['EX_glc__D_c']
    for met in media:
        if met in model.reactions:
            model.reactions.get_by_id(met).lower_bound = -1000.

    rxns = [i.id for i in model.reactions]
    blocked = cobra.flux_analysis.find_blocked_reactions(model)
    print(blocked)
    model.remove_reactions(blocked)

    solved_fluxes = minspan(model, cores=3, verbose=False, timelimit=60,solver_name="auto")
    
    df = pd.DataFrame(solved_fluxes.copy(), index=[i.id for i in model.reactions])
    df = df/df.abs().max()
    df.to_csv(model_dir % model_name)