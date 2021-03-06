from __future__ import division  # floating point division by default
import os
from fractions import Fraction
from datetime import datetime
from itertools import repeat
from warnings import warn

from pickle import dumps, loads
from sympy.parsing.sympy_parser import parse_expr

import numpy
from numpy import abs, float64, zeros, ones, compress, \
    matrix, argmax, ceil

import numpy as np
from numpy.linalg import matrix_rank, svd
from scipy.io import loadmat, savemat
from scipy.sparse import dok_matrix
from sympy import lcm

import cobra  # https://github.com/opencobra/cobrapy
from cobra.util import array
# define constants

default_max_error = 1e-6        # maximum allowed value in S * v
default_bound = 1000.0          # absolute value for nonzero reaction bounds
default_rank_eps = 1e-9         # epsilon when calculating rank from svd
indicator_prefix = "indicator_"
acceptable_status = ('optimal', 'time_limit')


# create directories to store generated files
final_dir = os.path.join("final", "")
snapshot_dir = os.path.join("snapshots", "")
if "SCRATCH" in os.environ:  # snapshots go in $SCRATCH if it exists
    snapshot_dir = os.join(os.environ["SCRATCH"], "snapshots", "")

def make_directories():
    """make directories to write out result files"""
    for dir in [snapshot_dir, final_dir]:
        if not os.path.isdir(dir):
            os.mkdir(dir)

def now():
    """return the time and date as a filename-friendly string"""
    return str(datetime.now()).replace(":", "_").replace(" ", "_")


def add_decision_variables_to_model(model):
    reactions = [i.id for i in model.reactions]
    """Add an integer decision variable for the given reaction."""
    decision_vars = []
    for reaction_id in reactions:
        reaction = model.reactions.get_by_id(reaction_id)

        x_var = model.problem.Variable("{}{}".format(indicator_prefix, reaction_id),
                                       type="binary")
        lb = -10000 if reaction.lower_bound < 0 else 0
        ub = 10000 if reaction.upper_bound > 0 else 0
        pos_const = model.problem.Constraint(
            reaction.flux_expression - (x_var * lb),
            lb=0, name="y_{}_upper".format(reaction_id))

        neg_const = model.problem.Constraint(
            reaction.flux_expression - (x_var * ub),
            ub=0, name="y_{}_lower".format(reaction_id))
        decision_vars.extend([x_var, pos_const, neg_const])

    model.add_cons_vars(decision_vars)
    return model


def null(S, max_error=default_max_error * 1e-3, rank_cutoff=default_rank_eps):
    """calculate the null space of a matrix

    Parameters
    ----------
    S : a numpy.Matrix
    """
    assert isinstance(S, matrix)
    m, n = S.shape  # m is number of metabolites, n is number of reactions
    [u, sigma, v] = svd(S)
    null_mask = ones((n,))
    rank = sum(sigma > rank_cutoff)  # use this instead of matrix_rank
    null_mask[:rank] = 0

    N = compress(null_mask, v, axis=0).T
    #assert rank < n
    if rank >= n:
        warn("rank %d >= %d" % (rank, n))
        from IPython import embed; embed()
    assert abs(S * N).max() < max_error  # make sure it is a null space
    assert type(N) is matrix
    return N


def get_factor(number, max_error=1e-6, max_digits=2):
    if abs(number - round(number)) < max_error:
        return 1
    for digits in range(1, max_digits + 1):
        frac = Fraction(number).limit_denominator(10 ** digits)
        if abs(float(frac.numerator) / frac.denominator - number) < max_error:
            return frac.denominator
    return 1


def scale_vector(vector, S, lb, ub, max_error=1e-6, normalize=False):
    """scale a vector

    Attempts to scale the vector to the smallest possible integers, while
    maintaining S * vector = 0 and lb <= vector <= ub

    If normalize is True, integer scaling is still performed, but the result
    is then normalized (||vector|| = 1). If the integer scaling works, this
    still results in less floating point error.
    """
    def check(x):
        if abs(S * matrix(x).T).max() > max_error:
            return False
        if (x > ub).any() or (x < lb).any():
            return False
        return True
    def prepare_return(x):
        return x / sum(x * x) if normalize else x
    # scale the vector so the smallest entry is 1
    abolute_vector = abs(vector)
    scale = min(abolute_vector[abolute_vector > 1e-5])
    min_scaled_vector = vector * (1.0 / scale)
    min_scaled_vector[abs(min_scaled_vector) < 1e-9] = 0  # round down
    # if scaling makes the solution invalid, return the old one
    if not check(min_scaled_vector):
        return prepare_return(vector)
    # attempt scale the vector to make all entries integers
    factor = lcm([get_factor(i) for i in min_scaled_vector])
    int_scaled_vector = min_scaled_vector * float(factor)
    if max(abs(int_scaled_vector.round() - int_scaled_vector)) < max_error:
        int_scaled_vector = int_scaled_vector.round()
        if check(int_scaled_vector):
            return prepare_return(int_scaled_vector)
    # if this point is reached the integer scaling failed
    return prepare_return(min_scaled_vector)


def scale_matrix(fluxes, S, lb, ub, max_error=1e-6):
    """scale each vector in the matrix in place"""
    if isinstance(fluxes, matrix):
        #raise TypeError("scale_matrix only works on ndarray for now")
        fluxes_array = np.array(fluxes)
        scale_matrix(fluxes_array, S, lb, ub, max_error=max_error)
        fluxes[:, :] = fluxes_array
        return
    for i in range(fluxes.shape[1]):  # for each column
        fluxes[:, i] = scale_vector(fluxes[:, i], S, lb, ub)


def nnz(S):
    """count the number of nonzero elements in ndarray"""
    if hasattr(S, "nnz"):
        return S.nnz
    if isinstance(S, matrix):
        return len(S.nonzero()[0])
    total = S != 0
    for i in range(len(S.shape)):
        total = sum(total)
    return total


def prepare_model(model):
    """prepare model in place for minspan

    Ensures that 0 is always a possible solution in every vector, and
    that all upper and lower bounds are either 0 or 1000"""
    for reaction in model.reactions:
        if reaction.lower_bound > reaction.upper_bound:
            raise ValueError("reaction %s: lower bound > upper bound" % reaction)
        elif reaction.lower_bound == reaction.upper_bound:
            raise Exception("reaction %s has a fixed flux" % reaction)
        if reaction.lower_bound > 0:
            reaction.lower_bound = 0
            warn("Fixed: reaction %s flux range did not include 0" % reaction)
        elif reaction.lower_bound < 0 and reaction.lower_bound != -1 * default_bound:
            reaction.lower_bound = -1 * default_bound
            warn("Fixed: reaction %s has a non-default lower bound" % reaction)
        if reaction.upper_bound < 0:
            reaction.upper_bound = 0
            warn("Fixed: reaction %s flux range did not include 0" % reaction)
        elif reaction.upper_bound > 0 and reaction.upper_bound != default_bound:
            reaction.upper_bound = default_bound
            warn("Fixed: reaction %s has a non-default upper bound" % reaction)
        if len(reaction._metabolites) > 15:
            warn("Is reaction %s a biomass function" % reaction)
    # TODO fva check feasibility for each reaction


def calculate_minspan_column_helper(args):
    return calculate_minspan_column(*args)


def calculate_minspan_column(model_pickle, original_fluxes, column_index, N,
                             cores, timelimit, verbose):
    """calculate a single minspan column

    This function minimizes the number of nonzero elements in the column
    given by column_index while ensuring it remains a feasible vector and
    linearly independent of all other columns.
    """
    n = N.shape[0]
    fluxes = original_fluxes.copy()

    # extract the old column and set it to 0
    oldPath = fluxes[:, column_index].copy()  # the old columm
    binOldPath = (abs(oldPath) >=1e-10) * 1  # binary version
    fluxes[:, column_index] = 0  # set the column to 0

    # calculate N2, which the new vector must not be orthogonal to
    a = N.T * fluxes
    # a = matrix(numpy.linalg.lstsq(N, matrix(fluxes))[0])
    N2 = (N * matrix(null(a.T)))
    
    # ensure that the current solution is still feasible
    k = abs(oldPath * N2)[0, 0]
    # The MILP requires abs(N2 * x) >= 1. If k < 1, we can satisfy this
    # constraint by setting using x / k. However, we must ensure that by
    # scaling x we are not violating the lower or upper bounds. If we do, then
    # we must scale N2
    if k < 1:
        if abs(oldPath).max() / k > default_bound:
            N2 *= 1.0 / k
            print("N2 scaled")
        else:
            oldPath *= 1.0 / k

    # construct the MILP problem
    model = loads(model_pickle)  # already has binary indicators

    # create constraint that N2 * fluxes != 0
    # This will be done by specifying that abs(N2 * fluxes) > 1
    fi_plus = model.problem.Variable(name="fi_plus", type='binary')  # boolean for N2 * fluxes > eps
    fi_minus = model.problem.Variable(name="fi_minus", type='binary')  # boolean for N2 * fluxes < -eps
    model.add_cons_vars([fi_plus, fi_minus])
    
    # N2 * fluxes > eps | -N2 * fluxes > eps
    eps = 1
    fi_plus_constraints_expression = -(eps+1000) * fi_plus
    fi_minus_constraints_expression = -(eps+1000) * fi_minus
    assert len(N2.T.tolist()[0]) == len(model.reactions)

    for i, N2_val in enumerate(N2.T.tolist()[0]):
        fi_plus_constraints_expression += (N2_val * model.reactions[i].flux_expression)
        fi_minus_constraints_expression += (-N2_val * model.reactions[i].flux_expression)

    fi_plus_constraint = model.problem.Constraint(fi_plus_constraints_expression,
                                    name="fi_plus_constraint", lb=-1000)
    fi_minus_constraint = model.problem.Constraint(fi_minus_constraints_expression,
                                     name="fi_minus_constraint", lb=-1000)

    model.add_cons_vars([fi_plus_constraint, fi_minus_constraint])

    d = model.problem.Constraint(fi_plus + fi_minus, lb=1, name="or_constraint")
    model.add_cons_vars([d])


    # seed the variables with the old solution, and set extra arguments

    assert len(model.reactions) == len(oldPath)
    for i, r in enumerate(model.reactions):    
        val = float(oldPath[i])
        if val > 0:
            r.forward_variable.Start = val
            r.reverse_variable.Start = 0
        else:
            r.forward_variable.Start = 0
            r.reverse_variable.Start = abs(val)
    

    for i, r in enumerate(model.reactions):
        variable = model.variables.get(indicator_prefix + r.id)
        variable.Start = float(binOldPath[i])


    # "Reset" objective to nothing
    model.objective = model.problem.Objective(0)
    # Set objective
    objective_coefficients = {}
    for var in model.variables:
        if indicator_prefix not in var.name:
            continue
        elif indicator_prefix in var.name and var.type not in ['binary',
                                                             'integer']:
            raise TypeError('Decision var %s not binary or integer' % var.name)

        objective_coefficients[var] = 1

    model.objective.set_linear_coefficients(objective_coefficients)

    # solve the model with the new parameters
    model.solver.problem.setParam("Method", 2)
    
    #model.solver.problem.setParam('IntFeasTol', 1e-9)
    #model.solver.problem.setParam("BarHomogeneous", 1)
    model.solver.problem.setParam("Presolve", 2)
    model.solver.problem.setParam('TimeLimit', timelimit)
    # highest verbosity
    #model.solver.problem.setParam('OutputFlag', 1)
    model.solver.problem.setParam('MIPGap', 0.001)
    model.solver.problem.setParam('MIPGapAbs', 0.999)
    model.solver.problem.setParam('Threads', cores)

    solution = model.optimize('minimize')

        
    # extract the solution
    if solution.status in acceptable_status:
        bin_flux = np.array(solution.fluxes.values[n:2 * n])
        flux = np.array(solution.fluxes.values[:n])
        flux[abs(flux) < 1e-10] = 0  # round down
    else:
        print(solution.status)
        status = lp.status
        raise Exception("Solver failed with status %s" % status)
    return flux


def minspan(model, starting_fluxes=None, coverage=10, cores=4, processes="auto",
    mapper=map, timelimit=30, verbose=True,
    first_round_cores=None, first_round_timelimit=2):
    """run minspan

    Parameters
    ----------
    model: cobra.Model object
        The model to calculate the minspan for
    starting_fluxes: a 2-dimensional numpy.ndarray object, "auto", or None
        Initial starting fluxes to use for the minspan. If this is set to
        "auto", then automatically attempt to load the last endpoint from
        a previous run.
    coverage: int
        The maximum number of times to cycle through every column and minimize
    cores: int
        The number of cores to use for each branch-and-bound MILP solver
    processes: int or "auto"
        The number of columns to minimize at once. Use this to scale minspan
        across multiple nodes in a cluster, with each node minimizing a single
        column. If set to auto, this will be the number of parallel processes
        used in the mapper.
    mapper: function
        Function to map arguments on to another function, equivalent to
        the python function map. This is useful for parallelizing minspan by
        either passing in the map function from a multiprocessing.Pool or
        the map_sync function from an ipython cluster direct view.
    solver_name: str
        Name of the solver to use. If "auto" is given, will look for gurobi,
        then cplex, then take the first solver found if neither are available.
    timelimit: int or float
        The maximum amount of time for each MILP problem (seconds). The maximum
        possible runtime is ~ timelimit * dim(null(S)) * coverage
    verbose: boolean
        Whether solver should run verbose
    """
    # identify a solver if necessary
    # copy the model, extract S, add indicators, and store indicator-model
    model = model.copy()

    prepare_model(model)


    # We want S before the indicators are added
    S = array.create_stoichiometric_matrix(model)
    lb = np.array(model.reactions.list_attr("lower_bound"), dtype=float64)
    ub = np.array(model.reactions.list_attr("upper_bound"), dtype=float64)
    add_decision_variables_to_model(model)


    model_pickle = dumps(model)
    # figure out saving filenames
    make_directories()
    base_filename = snapshot_dir + "/save_"
    try:
        model_id = "%s_" % (model.id)
    except:
        model_id = ""
    column_filename = base_filename + model_id + \
        "round_%02d_column_%04d_time_%s.mat"
    round_filename = base_filename + model_id + "round_%02d_final_%s.mat"
    final_filename = final_dir + "minspan_" + model_id + "%s.mat"

    m, n = S.shape
    S = matrix(S)
    N = matrix(null(matrix(S)))
    null_dim = N.shape[1]  # dimension of the null space
    # if no original flux vector was passed in, start with the null space
    if starting_fluxes is None:
        fluxes = np.array(N, dtype=float64)
    else:  # make sure the flux vector passed in still spans the null space
        if starting_fluxes == "auto":
            starting_filenames = [i for i in os.listdir(snapshot_dir) if
                model.id in i]
            round_filenames = sorted((i for i in starting_filenames if "final" in i), reverse=True)
            starting_fluxes = loadmat(snapshot_dir + round_filenames[0])["fluxes"]
            print("loaded starting_fluxes from %s" % (snapshot_dir + round_filenames[0]))
            None  #TODO: look in snapshots
        fluxes = np.array(dok_matrix(starting_fluxes).todense(), dtype=float64)
        if N.shape != fluxes.shape:
            raise ValueError("starting fluxes should be the same size as null")
        if abs(S * fluxes).max() > default_max_error:
            error_msg = "starting fluxes do not span the null space"
            error_msg += ": max error of %E" % (abs(S * fluxes).max())
            raise ValueError(error_msg)

    improvement_tracker = []  # array to keep track of when the score improved
    nnz_log = [nnz(fluxes)]  # array to keep track of nnz with each iteration
    if verbose:
        print("starting minspan on model %s with %d dimensions" % (model.id, null_dim))
    for k in range(coverage):
        # random order of columns to try out
        column_order = list(range(null_dim))
        numpy.random.shuffle(column_order)
        # previous score
        prevNum = nnz(fluxes)
        if verbose:
            print("starting round %d at nnz=%d" % (k, prevNum))

        # different time limit and number of processes for each round
        if k == 0:  # round 0
            if starting_fluxes is None:  # no hot start provided
                use_timelimit = first_round_timelimit
                use_processes = 1
                if first_round_cores is not None:
                    use_cores = first_round_cores
                else:
                    use_cores = cores
            else:  # hot start was provided
                use_timelimit = timelimit
                use_processes = processes
                use_cores = cores
        else:  # future rounds
            use_timelimit = timelimit
            use_processes = processes
            use_cores = cores
        if use_processes == "auto":
            # determine the number of connected engines
            if mapper == map:
                use_processes = 1
            elif not hasattr(mapper, "im_self"):
                use_processes = 1
            elif hasattr(mapper.im_self, "client"):  # ipython
                use_processes = len(mapper.im_self.client.ids)
            elif hasattr(mapper.im_self, "_processes"): # multiprocessing
                use_processes = mapper.im_self._processes

        # iterate through columns in clumps
        for i in range(int(ceil(null_dim / float(use_processes)))):
            column_indices = \
                column_order[i * use_processes:(i + 1) * use_processes]
            # Call calculate_minspan_column. Mapper is used with the helper
            # function because the multiprocessing map function only takes a
            # single iterable.
            flux_vectors = list(mapper(calculate_minspan_column_helper,
                zip(repeat(model_pickle), repeat(fluxes), column_indices,
                    repeat(N), repeat(use_cores), repeat(use_timelimit),
                    repeat(verbose))))
            # out of all the flux vectors which were minimized, pick the one
            # which improved the most
            previous_nnz = [nnz(fluxes[:, a]) for a in column_indices]
            minimized_nnz = np.array([nnz(a) for a in flux_vectors])
            improvement = np.array(previous_nnz) - minimized_nnz
            # empty vectors of just 0 are not actually an improvement
            improvement[minimized_nnz == 0] = 0
            ranked_choices = improvement.argsort()[::-1]  # reverse sort
            best_choice = None
            for choice in ranked_choices:
                index_choice = column_indices[choice]
                if improvement[choice] < 0:
                    print("result was worse by %d (round %d, column %d)" % \
                        (-1 * improvement[choice], k, index_choice))
                    break  # because it is sorted all subsequent ones are worse
                if minimized_nnz[choice] == 0:
                    print("solver returned empty vector (round %d, column %d)" % (k, index_choice))
                if improvement[choice] == 0:
                    break # because it is sorted all subsequent ones are worse
                flux_choice = flux_vectors[choice]
                test_fluxes = fluxes.copy()
                test_fluxes[:, index_choice] = flux_choice
                if matrix_rank(test_fluxes, tol=default_rank_eps) != null_dim:
                    print("rank changed (round %d, column %d)" % (k, index_choice))
                    continue
                if abs(S * test_fluxes).max() > default_max_error:
                    print("No longer null space: error of %E (round %d, column %d)" % \
                        (abs(S * test_fluxes).max(), k, index_choice))
                    continue
                # if we reach this point, then we have a suitable vector
                best_choice = choice
            # replace the vector if a better one was found
            if best_choice is not None:
                flux = flux_vectors[best_choice]
                scaled_flux = scale_vector(flux, S, lb, ub, normalize=True)
                column_index = column_indices[best_choice]
                fluxes[:, column_index] = scaled_flux

                # check for improvement in this specific vector
                nnz_log.append(nnz(fluxes))
                if nnz_log[-1] < nnz_log[-2]:  # last nnz is smaller than previous
                    improvement_tracker.append((k, column_index))
                    if verbose:
                        print("improved: round %d, column %4d nnz=%d" % \
                            (k, column_index, nnz_log[-1]))

                # save the result
                savemat(column_filename % (k, column_index, now()),
                    {"fluxes": dok_matrix(fluxes)}, oned_as="column")
        # round is over
        #scale_matrix(fluxes, S, lb, ub)  # attempt to "integerize" values
        # save the result of the entire round using a sparse matrix
        savemat(round_filename % (k, now()),
            {"fluxes": dok_matrix(fluxes)}, oned_as="column")

        # if no overall improvement occured in this round, we are done
        if nnz(fluxes) == prevNum:
            break

    # save the final result
    savemat(final_filename % now(),
        {
            "fluxes": dok_matrix(fluxes),
            "history": np.array(improvement_tracker),
            "nnz_log": np.array(nnz_log)},
        oned_as="column")
    # done!
    return fluxes


if __name__ == "__main__":
    from cobra.io import load_matlab_model
    from time import time
    
    model = load_matlab_model("testing_models.mat", "ecoli_core")
    S = model.to_array_based_model().S
    start = time()
    solved_fluxes = minspan(model, cores=1, verbose=True)
    print("solved in %.2f seconds" % (time() - start))
    print("nnz", nnz(solved_fluxes))
    print("rank", matrix_rank(solved_fluxes))
    print("max(S * v) =", abs(S * solved_fluxes).max())
    #from IPython import embed; embed()
