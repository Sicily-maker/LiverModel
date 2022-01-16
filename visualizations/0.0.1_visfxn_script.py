# -*- coding: utf-8 -*-
r"""Contains functions for visualizing time profiles of simulation results"""
from warnings import warn
import altair as alt
from six import iteritems


    def plot_conc_profile(mass_solution, observable=None, interactive = False,static=True, xlim=None,ylim=None,plot_type=None,xlabel=None,
                  ylabel=None,width=None,height=None):
        """Plot time profiles of solutions in a given :class:`~.MassSolution`.
        The legend is clickable and highlights the option.
        Pressing Shift-Click allows multiple items to be selected.
        

        Parameters
        ----------
        mass_solution : MassSolution
            The :class:`~.MassSolution` containing the time-dependent solutions
            to be plotted.
        observable : iterable, None
            An iterable containing string identifiers of the :mod:`mass` objects
            or the objects themselves that correspond to the keys for the desired
            solutions in the :class:`~.MassSolution`. If ``None`` or "all" in the case of interactive 
            then all solutions are plotted.
        interactive : True or False
            Makes the plot interactive with a moving tooltip showing the concentration values
            If interactive is True, then an observable list must be given, otherwise a warning is raised.
            If all metabolites is wanted, then observable must be ""all"", but the graph won't 
            render as well 
            Default is False

        **kwargs
            * time_vector
            * plot_function
            * title
            * xlabel
            * ylabel
            * xlim
            * ylim
            * grid
            * grid_color
            * grid_linestyle
            * grid_linewidth
            * prop_cycle
            * color
            * linestyle
            * linewidth
            * marker
            * markersize
            * legend_ncol
            * annotate_time_points
            * annotate_time_points_color
            * annotate_time_points_marker
            * annotate_time_points_markersize
            * annotate_time_points_labels
            * annotate_time_points_legend
            * annotate_time_points_zorder
            * deviation
            * deviation_zero_centered
            * deviation_normalization

            See :mod:`~mass.visualization` documentation for more information on
            optional ``kwargs``.

        Returns
        -------
        ax :  matplotlib.axes.Axes
            The :class:`~matplotlib.axes.Axes` instance containing the newly
            created plot.

        """