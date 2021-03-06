# -*- coding: utf-8 -*-

from __future__ import absolute_import

from collections import OrderedDict
from operator import attrgetter, itemgetter

import numpy as np
from numpy import bool_, float_

from cobra.core import Gene, Metabolite, Model, Reaction
from cobra.util.solver import set_objective


_REQUIRED_REACTION_ATTRIBUTES = [
    "id",
    "name",
    "metabolites",
    "lower_bound",
    "upper_bound",
    "gene_reaction_rule",
]
_ORDERED_OPTIONAL_REACTION_KEYS = [
    "objective_coefficient",
    "subsystem",
    "notes",
    "annotation",
]
_OPTIONAL_REACTION_ATTRIBUTES = {
    "objective_coefficient": 0,
    "subsystem": "",
    "notes": {},
    "annotation": {},
}

_REQUIRED_METABOLITE_ATTRIBUTES = ["id", "name", "charge","formula", "compartment"]
_ORDERED_OPTIONAL_METABOLITE_KEYS = [
   
    "_bound",
    "notes",
    "annotation",
]
_OPTIONAL_METABOLITE_ATTRIBUTES = {
    "charge": None,
    "formula": None,
    "_bound": 0,
    "notes": {},
    "annotation": {},
}

_REQUIRED_GENE_ATTRIBUTES = ["id", "name"]
_ORDERED_OPTIONAL_GENE_KEYS = ["notes", "annotation"]
_OPTIONAL_GENE_ATTRIBUTES = {
    "notes": {},
    "annotation": {},
}

_ORDERED_OPTIONAL_MODEL_KEYS = ["name", "compartments", "notes", "annotation"]
_OPTIONAL_MODEL_ATTRIBUTES = {
    "name": None,
    #  "description": None, should not actually be included
    "compartments": [],
    "notes": {},
    "annotation": {},
}


def _fix_type(value):
    """convert possible types to str, float, and bool"""
    # Because numpy floats can not be pickled to json
    if isinstance(value, str):
        return str(value)
    if isinstance(value, float_):
        return float(value)
    if isinstance(value, bool_):
        return bool(value)
    if isinstance(value, set):
        return list(value)
    if isinstance(value, dict):
        return OrderedDict((key, value[key]) for key in sorted(value))
    # handle legacy Formula type
    if value.__class__.__name__ == "Formula":
        return str(value)
    if value is None:
        return ""
    return value


def _update_optional(cobra_object, new_dict, optional_attribute_dict, ordered_keys):
    """update new_dict with optional attributes from cobra_object"""
    for key in ordered_keys:
        default = optional_attribute_dict[key]
        value = getattr(cobra_object, key)
        if value is None or value == default:
            continue
        new_dict[key] = _fix_type(value)


def metabolite_to_dict(metabolite):
    new_met = OrderedDict()
    for key in _REQUIRED_METABOLITE_ATTRIBUTES:
        new_met[key] = _fix_type(getattr(metabolite, key))
    return new_met


def metabolite_from_dict(metabolite):
    new_metabolite = Metabolite()
    for k, v in metabolite.items():
        setattr(new_metabolite, k, v)
    return new_metabolite


def gene_to_dict(gene):
    new_gene = OrderedDict()
    for key in _REQUIRED_GENE_ATTRIBUTES:
        new_gene[key] = _fix_type(getattr(gene, key))
    _update_optional(
        gene, new_gene, _OPTIONAL_GENE_ATTRIBUTES, _ORDERED_OPTIONAL_GENE_KEYS
    )
    return new_gene


def gene_from_dict(gene):
    new_gene = Gene(gene["id"])
    for k, v in gene.items():
        setattr(new_gene, k, v)
    return new_gene


def reaction_to_dict(reaction):
    new_reaction = OrderedDict()
    for key in _REQUIRED_REACTION_ATTRIBUTES:
        if key != "metabolites":
            if key == "lower_bound" and (
                np.isnan(reaction.lower_bound) or np.isinf(reaction.lower_bound)
            ):
                new_reaction[key] = str(_fix_type(getattr(reaction, key)))
            elif key == "upper_bound" and (
                np.isnan(reaction.upper_bound) or np.isinf(reaction.upper_bound)
            ):
                new_reaction[key] = str(_fix_type(getattr(reaction, key)))
            else:
                new_reaction[key] = _fix_type(getattr(reaction, key))
            continue
        mets = {}
        for met in sorted(reaction.metabolites, key=attrgetter("id")):
            mets[str(met)] = reaction.metabolites[met]
        new_reaction["metabolites"] = mets
    _update_optional(
        reaction,
        new_reaction,
        _OPTIONAL_REACTION_ATTRIBUTES,
        _ORDERED_OPTIONAL_REACTION_KEYS,
    )
    return new_reaction


def reaction_from_dict(reaction, model):
    new_reaction = Reaction()
    for k, v in reaction.items():
        if k in {"objective_coefficient", "reversibility", "reaction"}:
            continue
        elif k == "metabolites":
            new_reaction.add_metabolites(
                OrderedDict(
                    (model.metabolites.get_by_id(str(met)), coeff)
                    for met, coeff in v.items()
                )
            )
        else:
            if k == "lower_bound" or k == "upper_bound":
                setattr(new_reaction, k, float(v))
            else:
                setattr(new_reaction, k, v)
    return new_reaction


def model_to_dict(model, sort=False):
    """Convert model to a dict.

    Parameters
    ----------
    model : cobra.Model
        The model to reformulate as a dict.
    sort : bool, optional
        Whether to sort the metabolites, reactions, and genes or maintain the
        order defined in the model.

    Returns
    -------
    OrderedDict
        A dictionary with elements, 'genes', 'compartments', 'id',
        'metabolites', 'notes' and 'reactions'; where 'metabolites', 'genes'
        and 'metabolites' are in turn lists with dictionaries holding all
        attributes to form the corresponding object.

    See Also
    --------
    cobra.io.model_from_dict
    """
    obj = OrderedDict()
    obj["metabolites"] = list(map(metabolite_to_dict, model.metabolites))
    obj["reactions"] = list(map(reaction_to_dict, model.reactions))
    obj["genes"] = list(map(gene_to_dict, model.genes))
    obj["id"] = model.id
    _update_optional(
        model, obj, _OPTIONAL_MODEL_ATTRIBUTES, _ORDERED_OPTIONAL_MODEL_KEYS
    )
    if sort:
        get_id = itemgetter("id")
        obj["metabolites"].sort(key=get_id)
        obj["reactions"].sort(key=get_id)
        obj["genes"].sort(key=get_id)
    return obj


def model_from_dict(obj):
    """Build a model from a dict.

    Models stored in json are first formulated as a dict that can be read to
    cobra model using this function.

    Parameters
    ----------
    obj : dict
        A dictionary with elements, 'genes', 'compartments', 'id',
        'metabolites', 'notes' and 'reactions'; where 'metabolites', 'genes'
        and 'metabolites' are in turn lists with dictionaries holding all
        attributes to form the corresponding object.

    Returns
    -------
    cora.core.Model
        The generated model.

    See Also
    --------
    cobra.io.model_to_dict
    """
    if "reactions" not in obj:
        raise ValueError("Object has no reactions attribute. Cannot load.")
    model = Model()
    model.add_metabolites(
        [metabolite_from_dict(metabolite) for metabolite in obj["metabolites"]]
    )
    model.genes.extend([gene_from_dict(gene) for gene in obj["genes"]])
    model.add_reactions(
        [reaction_from_dict(reaction, model) for reaction in obj["reactions"]]
    )
    objective_reactions = [
        rxn for rxn in obj["reactions"] if rxn.get("objective_coefficient", 0) != 0
    ]
    coefficients = {
        model.reactions.get_by_id(rxn["id"]): rxn["objective_coefficient"]
        for rxn in objective_reactions
    }
    set_objective(model, coefficients)
    for k, v in obj.items():
        if k in {"id", "name", "notes", "compartments", "annotation"}:
            setattr(model, k, v)
    return model
